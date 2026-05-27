from fastapi import FastAPI
from app.api.rest import system


def create_app() -> FastAPI:
    app = FastAPI(title="Eira Backend", version="0.1.0")
    app.include_router(system.router)
    return app


app = create_app()
