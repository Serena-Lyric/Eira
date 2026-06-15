"""Xunfei (iFLYTEK) TTS provider — online text-to-speech via WebSocket.

API docs: https://www.xfyun.cn/doc/tts/online_tts/API.html

Auth: HMAC-SHA256 signature with APIKey + APISecret.
Endpoint: wss://tts-api.xfyun.cn/v2/tts
Output: PCM 16kHz 16bit mono audio bytes
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone

import structlog
import websockets

from .base import BaseTTSProvider

logger = structlog.get_logger(__name__)

XF_TTS_HOST = "tts-api.xfyun.cn"
XF_TTS_PATH = "/v2/tts"
XF_TTS_URL = f"wss://{XF_TTS_HOST}{XF_TTS_PATH}"

# Voice name constants
XF_VOICES = {
    "default": "xiaoyan",  # 讯飞小燕 — 标准女声
    "xiaoyan": "xiaoyan",
    "xiaoyu": "xiaoyu",    # 讯飞小宇 — 标准男声
    "xiaomei": "xiaomei",  # 讯飞小美 — 粤语女声
    "xiaolin": "xiaolin",  # 讯飞小琳 — 台湾普通话女声
}

# Text encoding for TTS requests
XF_TTS_ENCODING = "utf8"


class XunfeiTTSProvider(BaseTTSProvider):
    """Xunfei online text-to-speech provider.

    Required config fields:
        app_id: Xunfei application ID
        api_key: Xunfei API Key
        api_secret: Xunfei API Secret

    Optional:
        voice: Voice name (default: "xiaoyan")
        sample_rate: Audio sample rate (default: 16000)
    """

    def __init__(
        self,
        app_id: str,
        api_key: str,
        api_secret: str,
        api_base: str | None = None,
        voice: str = "xiaoyan",
        sample_rate: int = 16000,
        request_timeout: int = 30,
    ) -> None:
        self._app_id = app_id
        self._api_key = api_key
        self._api_secret = api_secret
        self._api_base = api_base or XF_TTS_URL
        self._voice = XF_VOICES.get(voice, voice)
        self._sample_rate = sample_rate
        self._request_timeout = request_timeout

    @property
    def provider_name(self) -> str:
        return "xunfei"

    def _build_auth_url(self) -> str:
        """Build the authenticated WebSocket URL with HMAC-SHA256 signature."""
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%a, %d %b %Y %H:%M:%S GMT")

        signature_origin = (
            f"host: {XF_TTS_HOST}\ndate: {date_str}\nGET {XF_TTS_PATH} HTTP/1.1"
        )

        signature_sha = hmac.new(
            self._api_secret.encode("utf-8"),
            signature_origin.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        signature_b64 = base64.b64encode(signature_sha).decode("utf-8")

        authorization_origin = (
            f'api_key="{self._api_key}", '
            f'algorithm="hmac-sha256", '
            f'headers="host date request-line", '
            f'signature="{signature_b64}"'
        )
        authorization_b64 = base64.b64encode(
            authorization_origin.encode("utf-8")
        ).decode("utf-8")

        from urllib.parse import urlencode

        params = urlencode({
            "authorization": authorization_b64,
            "date": date_str,
            "host": XF_TTS_HOST,
        })

        return f"{self._api_base}?{params}"

    async def stream(
        self,
        text: str,
        voice: str = "default",
        format: str = "opus",
    ) -> AsyncIterator[bytes]:
        """Stream synthesized speech as audio chunks.

        Args:
            text: Text to synthesize (max ~2000 characters per request).
            voice: Voice preset name.
            format: Output format — Xunfei returns PCM; we yield raw bytes.

        Yields:
            Audio bytes as they arrive from the TTS engine.
        """
        url = self._build_auth_url()
        resolved_voice = XF_VOICES.get(voice, self._voice)

        # Xunfei TTS business parameters
        business = {
            "aue": "raw",       # raw PCM output
            "auf": f"audio/L16;rate={self._sample_rate}",
            "vcn": resolved_voice,
            "tte": XF_TTS_ENCODING,
            "speed": 50,        # 0-100, 50 = normal speed
            "volume": 50,       # 0-100
            "pitch": 50,        # 0-100
        }

        # Build TTS request
        tts_request = {
            "common": {"app_id": self._app_id},
            "business": business,
            "data": {
                "status": 2,  # 2 = complete text (non-streaming TTS)
                "text": base64.b64encode(text.encode("utf-8")).decode("utf-8"),
            },
        }

        try:
            async with websockets.connect(  # type: ignore[attr-defined]
                url,
                max_size=1024 * 1024 * 5,
                ping_interval=5,
                open_timeout=self._request_timeout,
            ) as ws:
                await ws.send(json.dumps(tts_request))

                # Receive audio data
                while True:
                    try:
                        raw = await ws.recv()
                    except websockets.exceptions.ConnectionClosed:
                        break

                    if isinstance(raw, bytes):
                        # Binary frame = audio data
                        yield raw
                    elif isinstance(raw, str):
                        msg = json.loads(raw)
                        code = msg.get("code", -1)
                        if code != 0:
                            err_msg = msg.get("message", "unknown error")
                            logger.error(
                                "tts.xunfei.error",
                                code=code,
                                message=err_msg,
                            )
                            raise RuntimeError(
                                f"Xunfei TTS error (code={code}): {err_msg}"
                            )
                        # code=0 means success — final status frame
                        ced = msg.get("data", {}).get("ced", "")
                        if ced:
                            # Final status frame
                            break

        except Exception as exc:
            logger.error("tts.xunfei.error", error=str(exc))
            raise

    async def close(self) -> None:
        pass  # WebSocket is managed per-call via context manager
