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
        if "storage_policy" not in dataset_columns:
            connection.execute(text("ALTER TABLE datasets ADD COLUMN storage_policy JSON"))
        if "collector_operation" not in job_columns:
            connection.execute(
                text("ALTER TABLE collection_jobs ADD COLUMN collector_operation VARCHAR(128)")
            )
        if "parameters" not in job_columns:
            connection.execute(
                text("ALTER TABLE collection_jobs ADD COLUMN parameters JSON DEFAULT '{}'")
            )
        if "error" not in job_columns:
            connection.execute(text("ALTER TABLE collection_jobs ADD COLUMN error TEXT"))
        connection.execute(
            text(
                "UPDATE datasets SET collection_bindings = "
                "'[ {\"purpose\":\"initial\",\"collector_key\":\"tushare_cn_stock\","
                "\"operation\":\"stock_list_initial\"},"
                "{\"purpose\":\"incremental\",\"collector_key\":\"tushare_cn_stock\","
                "\"operation\":\"stock_list_incremental\"} ]' "
                "WHERE id = 'tushare.cn.stock.stock_basic' "
                "AND (collection_bindings IS NULL OR collection_bindings = '[]')"
            )
        )
        connection.execute(
            text(
                "UPDATE collection_jobs SET collector_key = 'tushare_cn_stock', "
                "collector_operation = CASE "
                "WHEN operation = 'incremental' THEN 'stock_list_incremental' "
                "ELSE 'stock_list_initial' END "
                "WHERE dataset_id = 'tushare.cn.stock.stock_basic' "
                "AND input_method = 'collector' "
                "AND (collector_operation IS NULL "
                "OR collector_operation IN ('stock_basic', 'tushare.stock_basic'))"
            )
        )
        connection.execute(
            text(
                "UPDATE datasets SET collection_bindings = "
                "REPLACE(collection_bindings, '\"collector_key\": \"tushare\"', "
                "'\"collector_key\": \"tushare_cn_stock\"') "
                "WHERE collection_bindings LIKE '%\"collector_key\": \"tushare\"%'"
            )
        )
        for binding_index in (0, 1):
            connection.execute(
                text(
                    "UPDATE datasets SET collection_bindings = "
                    f"json_set(collection_bindings, '$[{binding_index}].collector_key', "
                    "'tushare_cn_stock') "
                    f"WHERE json_extract(collection_bindings, "
                    f"'$[{binding_index}].collector_key') = 'tushare'"
                )
            )
        connection.execute(
            text(
                "UPDATE collection_jobs SET collector_key = 'tushare_cn_stock' "
                "WHERE collector_key = 'tushare'"
            )
        )
        connection.execute(
            text(
                "UPDATE datasets SET storage_policy = "
                "json_set(storage_policy, '$.calendar_dataset_id', "
                "'tushare.cn.stock.trade_cal') "
                "WHERE id = 'tushare.cn.stock.daily' "
                "AND storage_policy IS NOT NULL "
                "AND json_extract(storage_policy, '$.calendar_dataset_id') IS NULL"
            )
        )

        partition_columns = {
            row[1] for row in connection.execute(text("PRAGMA table_info(catalog_partitions)"))
        }
        if "file_id" not in partition_columns:
            connection.execute(text("ALTER TABLE catalog_partitions ADD COLUMN file_id INTEGER"))
        connection.execute(
            text(
                "INSERT OR IGNORE INTO catalog_files "
                "(dataset_id, path, row_count, size_bytes, sha256, created_at) "
                "SELECT dataset_id, file_path, SUM(row_count), SUM(size_bytes), "
                "MAX(sha256), CURRENT_TIMESTAMP "
                "FROM catalog_partitions GROUP BY dataset_id, file_path"
            )
        )
        connection.execute(
            text(
                "UPDATE catalog_partitions SET file_id = ("
                "SELECT id FROM catalog_files "
                "WHERE catalog_files.path = catalog_partitions.file_path"
                ") WHERE file_id IS NULL"
            )
        )


def get_session(request: Request) -> Generator[Session, None, None]:
    with request.app.state.session_factory() as session:
        yield session
