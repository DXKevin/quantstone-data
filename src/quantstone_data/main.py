from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from .catalog import router as catalog_router
from .collection import router as collection_router
from .collectors_api import router as collectors_router
from .database import (
    Base,
    create_session_factory,
    default_data_root,
    default_database_url,
    upgrade_sqlite_schema,
)
from .registry import router as registry_router


def create_app(database_url: str | None = None, data_root: str | Path | None = None) -> FastAPI:
    session_factory = create_session_factory(database_url or default_database_url())
    resolved_data_root = Path(data_root or default_data_root()).resolve()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        resolved_data_root.mkdir(parents=True, exist_ok=True)
        engine = session_factory.kw["bind"]
        Base.metadata.create_all(engine)
        upgrade_sqlite_schema(engine)
        yield

    app = FastAPI(title="QuantStone Data", version="0.1.0", lifespan=lifespan)
    app.state.session_factory = session_factory
    app.state.data_root = resolved_data_root
    app.include_router(registry_router, prefix="/api/v1")
    app.include_router(collection_router, prefix="/api/v1")
    app.include_router(catalog_router, prefix="/api/v1")
    app.include_router(collectors_router, prefix="/api/v1")

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
