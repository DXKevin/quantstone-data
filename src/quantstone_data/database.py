import os
from collections.abc import Generator
from pathlib import Path

from fastapi import Request
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def default_database_url() -> str:
    database_path = Path("var") / "quantstone-data.db"
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{database_path.as_posix()}"


def default_data_root() -> Path:
    configured = os.environ.get("QUANTSTONE_DATA_ROOT")
    return Path(configured).expanduser() if configured else Path.home() / ".quantstone-data"


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def upgrade_sqlite_schema(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    inspector = inspect(engine)
    dataset_columns = {item["name"] for item in inspector.get_columns("datasets")}
    job_columns = {item["name"] for item in inspector.get_columns("collection_jobs")}
    with engine.begin() as connection:
        if "collection_bindings" not in dataset_columns:
            connection.execute(
                text("ALTER TABLE datasets ADD COLUMN collection_bindings JSON DEFAULT '[]'")
            )
        if "collector_operation" not in job_columns:
            connection.execute(
                text("ALTER TABLE collection_jobs ADD COLUMN collector_operation VARCHAR(128)")
            )
        connection.execute(
            text(
                "UPDATE datasets SET collection_bindings = "
                "'[ {\"purpose\":\"initial\",\"collector_key\":\"tushare\","
                "\"operation\":\"stock_list_initial\"},"
                "{\"purpose\":\"incremental\",\"collector_key\":\"tushare\","
                "\"operation\":\"stock_list_incremental\"} ]' "
                "WHERE id = 'tushare.cn.stock.stock_basic' "
                "AND (collection_bindings IS NULL OR collection_bindings = '[]')"
            )
        )


def get_session(request: Request) -> Generator[Session, None, None]:
    with request.app.state.session_factory() as session:
        yield session
