from fastapi import FastAPI
from app.core.logging import configure_logging
from app.api.rest import system, auth


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="Eira Backend", version="0.1.0")
    app.include_router(system.router)
    app.include_router(auth.router)
    return app


app = create_app()
