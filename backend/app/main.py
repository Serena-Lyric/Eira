from fastapi import FastAPI
from app.core.logging import configure_logging
from app.api.rest import system, auth, conversations
from app.api.ws import chat as ws_chat


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="Eira Backend", version="0.1.0", docs_url=None, redoc_url=None)
    app.include_router(system.router)
    app.include_router(auth.router)
    app.include_router(conversations.router)
    app.include_router(ws_chat.router)
    return app


app = create_app()
