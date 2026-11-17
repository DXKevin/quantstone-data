from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .database import Base, create_session_factory, default_database_url
from .registry import router as registry_router


def create_app(database_url: str | None = None) -> FastAPI:
    session_factory = create_session_factory(database_url or default_database_url())

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        Base.metadata.create_all(session_factory.kw["bind"])
        yield

    app = FastAPI(title="QuantStone Data", version="0.1.0", lifespan=lifespan)
    app.state.session_factory = session_factory
    app.include_router(registry_router, prefix="/api/v1")

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
