from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, Request

from .background import BackgroundJobExecutor
from .catalog import router as catalog_router
from .collection import recover_interrupted_jobs
from .collection import router as collection_router
from .collectors_api import router as collectors_router
from .database import (
    Base,
    create_session_factory,
    default_data_root,
    default_database_url,
    upgrade_sqlite_schema,
)
from .dataset_categories import router as dataset_categories_router
from .dataset_deletion import router as dataset_deletion_router
from .dataset_presets import router as dataset_presets_router
from .directory_import import recover_interrupted_import_jobs
from .directory_import import router as directory_import_router
from .logging_config import configure_logging, log_event
from .maintenance import recover_interrupted_maintenance_jobs
from .maintenance import router as maintenance_router
from .overview import router as overview_router
from .registry import router as registry_router
from .storage_api import router as storage_router


def create_app(database_url: str | None = None, data_root: str | Path | None = None) -> FastAPI:
    session_factory = create_session_factory(database_url or default_database_url())
    resolved_data_root = Path(data_root or default_data_root()).resolve()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        resolved_data_root.mkdir(parents=True, exist_ok=True)
        configure_logging(resolved_data_root)
        engine = session_factory.kw["bind"]
        Base.metadata.create_all(engine)
        upgrade_sqlite_schema(engine)
        with session_factory() as session:
            recovered_jobs = recover_interrupted_jobs(session)
            recovered_maintenance = recover_interrupted_maintenance_jobs(session)
            recovered_imports = recover_interrupted_import_jobs(session)
        if recovered_jobs or recovered_maintenance or recovered_imports:
            log_event(
                "interrupted_jobs_recovered",
                collection_jobs=recovered_jobs,
                maintenance_jobs=recovered_maintenance,
                import_jobs=recovered_imports,
                level=30,
            )
        executor = BackgroundJobExecutor()
        app.state.background_executor = executor
        log_event("application_started", data_root=resolved_data_root)
        try:
            yield
        finally:
            executor.shutdown()
            log_event("application_stopped")

    app = FastAPI(title="QuantStone Data", version="0.1.0", lifespan=lifespan)
    app.state.session_factory = session_factory
    app.state.data_root = resolved_data_root
    app.include_router(registry_router, prefix="/api/v1")
    app.include_router(dataset_deletion_router, prefix="/api/v1")
    app.include_router(dataset_categories_router, prefix="/api/v1")
    app.include_router(dataset_presets_router, prefix="/api/v1")
    app.include_router(collection_router, prefix="/api/v1")
    app.include_router(catalog_router, prefix="/api/v1")
    app.include_router(collectors_router, prefix="/api/v1")
    app.include_router(overview_router, prefix="/api/v1")
    app.include_router(storage_router, prefix="/api/v1")
    app.include_router(maintenance_router, prefix="/api/v1")
    app.include_router(directory_import_router, prefix="/api/v1")

    @app.middleware("http")
    async def log_http_request(request: Request, call_next):
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log_event(
                "http_request_failed",
                level=40,
                exc_info=True,
                method=request.method,
                path=request.url.path,
                duration_ms=round((perf_counter() - started) * 1000, 2),
            )
            raise
        if request.method != "GET" or response.status_code >= 400:
            log_event(
                "http_request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round((perf_counter() - started) * 1000, 2),
            )
        return response

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
