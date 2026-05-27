from fastapi import FastAPI
from app.core.logging import configure_logging
from app.api.rest import system


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="Eira Backend", version="0.1.0")
    app.include_router(system.router)
    return app


app = create_app()
