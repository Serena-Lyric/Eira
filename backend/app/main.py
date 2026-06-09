from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.middleware.audit import AuditMiddleware
from app.api.rest import system, auth, conversations, voice, feedback, user, persona_config, stats, documents, assets
from app.api.rest import admin_dashboard, admin_documents, admin_assets
from app.api.rest import admin_users, admin_personas, personas, admin_settings, admin_audit
from app.api.ws import chat as ws_chat
from app.api.ws import voice as ws_voice


def _validate_secrets_on_startup() -> None:
    """Validate JWT and OSS secrets are not left at insecure defaults.

    In dev mode we warn loudly; in staging/prod we refuse to start.
    """
    settings = get_settings()
    env = settings.app.env

    if env == "dev":
        if settings.jwt.secret == "":
            print("[WARNING] EIRA_JWT__SECRET 未设置，使用空默认值。dev 环境可接受，但不应在 staging/prod 出现。")
        elif settings.jwt.secret == "dev-only-change-me":
            print("[WARNING] EIRA_JWT__SECRET 仍为旧默认值 'dev-only-change-me'，请尽快更换。")
        if settings.oss.secret == "":
            print("[WARNING] EIRA_OSS__SECRET 未设置，使用空默认值。dev 环境可接受，但不应在 staging/prod 出现。")
        return

    # Staging / production — enforce strong secrets
    errors: list[str] = []
    if settings.jwt.secret == "":
        errors.append("EIRA_JWT__SECRET 环境变量必须设置（当前为空）")
    elif settings.jwt.secret == "dev-only-change-me":
        errors.append(
            "EIRA_JWT__SECRET 仍为已知不安全默认值 'dev-only-change-me'，"
            "请立即更换为强随机值（推荐: openssl rand -hex 64）"
        )
    if settings.oss.secret == "":
        errors.append("EIRA_OSS__SECRET 环境变量必须设置（当前为空）")

    if errors:
        msg = "\n".join(f"  [{i+1}] {e}" for i, e in enumerate(errors))
        raise RuntimeError(
            f"安全配置错误 — 服务拒绝启动 ({env} 环境):\n{msg}\n"
            f"请设置对应的 EIRA_* 环境变量后重试。"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _validate_secrets_on_startup()
    yield


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="Eira Backend",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(AuditMiddleware)
    app.include_router(system.router)
    app.include_router(auth.router)
    app.include_router(conversations.router)
    app.include_router(voice.router)
    app.include_router(feedback.router)
    app.include_router(feedback.admin_router)
    app.include_router(user.router)
    app.include_router(persona_config.router)
    app.include_router(stats.router)
    app.include_router(documents.router)
    app.include_router(assets.router)
    app.include_router(admin_dashboard.router)
    app.include_router(admin_documents.router)
    app.include_router(admin_assets.router)
    app.include_router(admin_users.router)
    app.include_router(admin_personas.router)
    app.include_router(personas.router)
    app.include_router(admin_settings.router)
    app.include_router(admin_audit.router)
    app.include_router(ws_chat.router)
    app.include_router(ws_voice.router)
    return app


app = create_app()
