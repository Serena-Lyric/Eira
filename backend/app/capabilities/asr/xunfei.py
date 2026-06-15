"""Xunfei (iFLYTEK) ASR provider — real-time speech recognition via WebSocket.

API docs: https://www.xfyun.cn/doc/asr/voicedictation/API.html

Auth: HMAC-SHA256 signature with APIKey + APISecret.
Endpoint: wss://iat-api.xfyun.cn/v2/iat
Audio: 16kHz, 16bit, mono PCM (or Speex/MP3/Opus)
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import time
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone

import structlog
import websockets
from websockets.asyncio.client import ClientConnection

from .base import AsrEvent, BaseASRProvider

logger = structlog.get_logger(__name__)

XF_ASR_HOST = "iat-api.xfyun.cn"
XF_ASR_PATH = "/v2/iat"
XF_ASR_URL = f"wss://{XF_ASR_HOST}{XF_ASR_PATH}"

# Audio frame status constants
STATUS_FIRST = 0
STATUS_CONTINUE = 1
STATUS_LAST = 2

# Default audio parameters
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_AUDIO_FORMAT = "audio/L16;rate=16000"  # 16bit PCM
DEFAULT_ENCODING = "raw"


class XunfeiASRProvider(BaseASRProvider):
    """Xunfei real-time speech recognition provider.

    Required config fields:
        app_id: Xunfei application ID
        api_key: Xunfei API Key
        api_secret: Xunfei API Secret
    """

    def __init__(
        self,
        app_id: str,
        api_key: str,
        api_secret: str,
        api_base: str | None = None,
        request_timeout: int = 30,
    ) -> None:
        self._app_id = app_id
        self._api_key = api_key
        self._api_secret = api_secret
        self._api_base = api_base or XF_ASR_URL
        self._request_timeout = request_timeout
        self._ws: ClientConnection | None = None

    @property
    def provider_name(self) -> str:
        return "xunfei"

    def _build_auth_url(self) -> str:
        """Build the authenticated WebSocket URL with HMAC-SHA256 signature."""
        # RFC 1123 date
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%a, %d %b %Y %H:%M:%S GMT")

        # Build signature origin
        signature_origin = f"host: {XF_ASR_HOST}\ndate: {date_str}\nGET {XF_ASR_PATH} HTTP/1.1"

        # HMAC-SHA256 sign
        signature_sha = hmac.new(
            self._api_secret.encode("utf-8"),
            signature_origin.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        signature_b64 = base64.b64encode(signature_sha).decode("utf-8")

        # Build authorization header
        authorization_origin = (
            f'api_key="{self._api_key}", '
            f'algorithm="hmac-sha256", '
            f'headers="host date request-line", '
            f'signature="{signature_b64}"'
        )
        authorization_b64 = base64.b64encode(
            authorization_origin.encode("utf-8")
        ).decode("utf-8")

        # Build final URL
        from urllib.parse import urlencode

        params = urlencode({
            "authorization": authorization_b64,
            "date": date_str,
            "host": XF_ASR_HOST,
        })

        return f"{self._api_base}?{params}"

    async def stream(
        self, audio: AsyncIterator[bytes], lang: str = "zh"
    ) -> AsyncIterator[AsrEvent]:
        """Stream audio to Xunfei IAT and yield recognition results.

        Xunfei IAT WebSocket protocol:
          1. FIRST frame:  text JSON with status=0, base64-encoded audio
          2. MIDDLE frames: binary audio data (raw PCM)
          3. LAST frame:   text JSON with status=2, base64-encoded audio (or empty)
        """
        url = self._build_auth_url()

        try:
            async with websockets.connect(  # type: ignore[attr-defined]
                url,
                max_size=1024 * 1024 * 10,  # 10MB max message
                ping_interval=5,
                open_timeout=self._request_timeout,
            ) as ws:
                self._ws = ws
                session_id = uuid.uuid4().hex

                # Consume the first audio chunk for the initial handshake
                first_chunk = b""
                try:
                    first_chunk = await audio.__anext__()
                except StopAsyncIteration:
                    pass  # No audio at all — send empty first frame

                # ── Step 1: Send initial JSON handshake (status=0) ──────
                first_payload = json.dumps({
                    "common": {"app_id": self._app_id},
                    "business": {
                        "language": self._resolve_lang(lang),
                        "domain": "iat",
                        "accent": "mandarin",
                        "vad_eos": 3000,
                    },
                    "data": {
                        "status": STATUS_FIRST,
                        "format": DEFAULT_AUDIO_FORMAT,
                        "encoding": DEFAULT_ENCODING,
                        "audio": base64.b64encode(first_chunk).decode("utf-8"),
                    },
                })
                await ws.send(first_payload)

                # ── Step 2: Send remaining audio as JSON frames (status=1) ──
                async for audio_chunk in audio:
                    if not audio_chunk:
                        continue
                    await ws.send(json.dumps({
                        "data": {
                            "status": STATUS_CONTINUE,
                            "format": DEFAULT_AUDIO_FORMAT,
                            "encoding": DEFAULT_ENCODING,
                            "audio": base64.b64encode(audio_chunk).decode("utf-8"),
                        },
                    }))

                # ── Step 3: Send end-of-stream marker (status=2) ───────
                await ws.send(json.dumps({
                    "data": {
                        "status": STATUS_LAST,
                        "format": DEFAULT_AUDIO_FORMAT,
                        "encoding": DEFAULT_ENCODING,
                        "audio": "",
                    },
                }))

                # ── Step 4: Receive results with generous timeout ──────
                # Xunfei needs vad_eos (3000ms) + processing time after
                # last frame before sending final results.
                received_final = False
                deadline = asyncio.get_event_loop().time() + 10.0
                while not received_final:
                    remaining = deadline - asyncio.get_event_loop().time()
                    if remaining <= 0:
                        logger.warning("asr.xunfei.timeout", session_id=session_id)
                        break
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 2.0))
                    except asyncio.TimeoutError:
                        continue
                    if isinstance(raw, str):
                        result = json.loads(raw)
                        event = self._parse_result(result, session_id)
                        if event is not None:
                            received_final = event.is_final
                            yield event
                    # Binary frames are unexpected but ignored

        except Exception as exc:
            logger.error("asr.xunfei.error", error=str(exc))
            raise

    def _parse_result(
        self, raw: dict, session_id: str, is_final: bool = False
    ) -> AsrEvent | None:
        """Parse a single JSON result frame from Xunfei IAT.

        Handles both response formats:
          - dwa=wpgs: data.result.ws[] → { cw: [{ w, sc }] }
          - legacy:    data.result.cn.st.rt[] → { ws: [{ cw: [{ w }] }] }
        """
        code = raw.get("code", -1)
        if code != 0:
            msg = raw.get("message", "unknown error")
            logger.warning("asr.xunfei.error_response", code=code, message=msg)
            return None

        data = raw.get("data", {})
        result = data.get("result", {})

        # Collect text — try both response formats
        texts: list[str] = []

        # Format A: dwa=wpgs — data.result.ws[]
        if "ws" in result and isinstance(result["ws"], list):
            for ws_item in result["ws"]:
                for cw in ws_item.get("cw", []):
                    w = cw.get("w", "")
                    if w:
                        texts.append(w)

        # Format B: legacy — data.result.cn.st.rt[]
        if not texts:
            cn = result.get("cn", {})
            st = cn.get("st", {}) if isinstance(cn, dict) else {}
            rt_list = st.get("rt", []) if isinstance(st, dict) else []
            for rt in rt_list:
                for ws_item in rt.get("ws", []):
                    for cw in ws_item.get("cw", []):
                        w = cw.get("w", "")
                        if w:
                            texts.append(w)

        text = "".join(texts)
        if not text:
            return None

        # Determine if final: ls flag, sn==ed, or data.status==2
        sn = result.get("sn", 0)
        ed = result.get("ed", 0)
        result_is_final = (
            is_final
            or data.get("ls", False)
            or result.get("ls", False)
            or data.get("status") == 2
            or (sn > 0 and sn == ed)
        )

        return AsrEvent(
            kind="final" if result_is_final else "partial",
            text=text,
            is_final=result_is_final,
        )

    @staticmethod
    def _resolve_lang(lang: str) -> str:
        """Map internal lang codes to Xunfei language codes."""
        lang_map = {
            "zh": "zh_cn",
            "en": "en_us",
            "ja": "ja_jp",
            "ko": "ko_kr",
        }
        return lang_map.get(lang, lang)

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
