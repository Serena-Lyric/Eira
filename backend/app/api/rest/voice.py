"""Voice endpoints: TTS (text-to-speech) and ASR (speech recognition)."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from app.core.deps import get_current_user, check_write_rate_limit
from app.domain.identity.models import User

router = APIRouter(prefix="/voice", tags=["voice"])


# ── Request schemas ──────────────────────────────────────────────────

class TtsRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000, description="要转换为语音的文本")
    voice: str | None = Field(default=None, description="语音角色 ID，默认使用系统配置")
    speed: float | None = Field(default=1.0, ge=0.5, le=2.0, description="语速倍率")


class AsrConfigOut(BaseModel):
    """ASR 服务配置（前端用于初始化语音识别）。"""
    provider: str = Field(description="ASR 提供商: xunfei / aliyun / whisper")
    app_id: str | None = Field(default=None, description="提供商的 App ID")
    api_key: str | None = Field(default=None, description="提供商的 API Key（前端使用）")
    api_secret: str | None = Field(default=None, description="提供商的 API Secret")
    websocket_url: str | None = Field(default=None, description="实时 ASR WebSocket URL")
    enabled: bool = Field(default=False, description="语音输入功能是否启用")


class AsrResultOut(BaseModel):
    """ASR 识别结果。"""
    text: str = Field(description="识别出的文本内容")


# ── ASR ──────────────────────────────────────────────────────────────

@router.post("/asr", response_model=AsrResultOut, summary="语音识别（REST fallback）")
async def speech_to_text(
    audio: UploadFile = File(..., description="音频文件（webm / wav / mp3 等）"),
    user: User = Depends(get_current_user),
    _rate: None = Depends(check_write_rate_limit),
) -> AsrResultOut:
    """将语音音频识别为文本。

    异步方式：读取完整音频后一次性送入 ASR provider 进行识别。
    实时语音识别应优先使用 WebSocket（/ws/voice）。
    """
    from app.capabilities.asr.factory import create_asr_provider
    from app.capabilities.effective_settings import get_effective_asr_settings

    settings = await get_effective_asr_settings()
    provider = create_asr_provider(settings)

    # Read the uploaded audio
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="音频文件为空")

    try:
        # Feed audio as an async iterator of chunks (matching streaming interface)
        async def _audio_chunks():
            chunk_size = 4096
            for i in range(0, len(audio_bytes), chunk_size):
                yield audio_bytes[i : i + chunk_size]

        final_text = ""
        async for event in provider.stream(_audio_chunks()):
            final_text = event.text
            if event.is_final:
                break

        return AsrResultOut(text=final_text)

    finally:
        await provider.close()


# ── TTS ──────────────────────────────────────────────────────────────

@router.post("/tts", summary="文本转语音")
async def text_to_speech(
    req: TtsRequest,
    user: User = Depends(get_current_user),
    _rate: None = Depends(check_write_rate_limit),
) -> Response:
    """将文本转换为语音音频。

    使用系统配置的 TTS 引擎（阿里云 NLS / Azure / 讯飞 / Mock）将文本合成语音。
    返回 audio/opus 格式的音频数据。开发环境下 Mock provider 返回测试数据。
    """
    from app.capabilities.tts.factory import create_tts_provider
    from app.capabilities.effective_settings import get_effective_tts_settings

    settings = await get_effective_tts_settings()
    provider = create_tts_provider(settings)

    try:
        chunks: list[bytes] = []
        async for chunk in provider.stream(
            req.text,
            voice=req.voice or "default",
            format="opus",
        ):
            chunks.append(chunk)

        audio = b"".join(chunks)
        return Response(content=audio, media_type="audio/opus")
    finally:
        await provider.close()


# ── ASR Config ───────────────────────────────────────────────────────

@router.get("/asr/config", response_model=AsrConfigOut, summary="获取 ASR 配置")
async def get_asr_config(
    user: User = Depends(get_current_user),
) -> AsrConfigOut:
    """返回语音识别服务配置。

    前端根据此配置初始化语音输入功能（讯飞实时 ASR 等）。
    配置项包括 provider、app_id、api_key 等前端所需的参数。
    """
    from app.capabilities.effective_settings import get_effective_asr_settings
    asr = await get_effective_asr_settings()
    return AsrConfigOut(
        provider=asr.provider,
        app_id=asr.app_id or None,
        api_key=asr.api_key or None,
        api_secret=None,
        websocket_url=asr.api_base or None,
        enabled=asr.provider != "mock" and bool(asr.api_key),
    )
