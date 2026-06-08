from fastapi import FastAPI
from app.core.logging import configure_logging
from app.api.rest import system, auth, conversations, voice, feedback, user, persona_config, stats, documents, assets
from app.api.ws import chat as ws_chat
from app.api.ws import voice as ws_voice


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="Eira Backend", version="0.1.0", docs_url=None, redoc_url=None)
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
    app.include_router(ws_chat.router)
    app.include_router(ws_voice.router)
    return app


app = create_app()
