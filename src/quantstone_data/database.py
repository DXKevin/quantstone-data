import json
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
    connect_args = (
        {"check_same_thread": False, "timeout": 15} if database_url.startswith("sqlite") else {}
    )
    engine = create_engine(database_url, connect_args=connect_args)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def upgrade_sqlite_schema(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    inspector = inspect(engine)
    dataset_columns = {item["name"] for item in inspector.get_columns("datasets")}
    job_columns = {item["name"] for item in inspector.get_columns("collection_jobs")}
    with engine.begin() as connection:
        if "category_id" not in dataset_columns:
            connection.execute(
                text(
                    "ALTER TABLE datasets ADD COLUMN category_id VARCHAR(36) "
                    "REFERENCES dataset_categories(id) ON DELETE SET NULL"
                )
            )
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_datasets_category_id ON datasets (category_id)")
        )
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
        if "retry_of_job_id" not in job_columns:
            connection.execute(
                text("ALTER TABLE collection_jobs ADD COLUMN retry_of_job_id VARCHAR(36)")
            )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_collection_jobs_retry_of_job_id "
                "ON collection_jobs (retry_of_job_id)"
            )
        )
        connection.execute(
            text(
                "UPDATE datasets SET collection_bindings = "
                "'[ {\"purpose\":\"initial\",\"collector_key\":\"tushare_cn_stock\","
                "\"operation\":\"stock_basic_initial\"},"
                "{\"purpose\":\"incremental\",\"collector_key\":\"tushare_cn_stock\","
                "\"operation\":\"stock_basic_incremental\"} ]' "
                "WHERE id = 'tushare.cn.stock.stock_basic' "
                "AND (collection_bindings IS NULL OR collection_bindings = '[]')"
            )
        )
        connection.execute(
            text(
                "UPDATE collection_jobs SET collector_key = 'tushare_cn_stock', "
                "collector_operation = CASE "
                "WHEN operation = 'incremental' THEN 'stock_basic_incremental' "
                "ELSE 'stock_basic_initial' END "
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
        # stock_list_* 是早期命名，已统一为 stock_basic_*；迁移已有绑定和历史任务。
        operation_renames = (
            ("stock_list_initial", "stock_basic_initial"),
            ("stock_list_incremental", "stock_basic_incremental"),
        )
        for binding_index in (0, 1):
            for old_operation, new_operation in operation_renames:
                connection.execute(
                    text(
                        "UPDATE datasets SET collection_bindings = "
                        f"json_set(collection_bindings, '$[{binding_index}].operation', :new) "
                        "WHERE json_extract(collection_bindings, "
                        f"'$[{binding_index}].operation') = :old"
                    ),
                    {"old": old_operation, "new": new_operation},
                )
        for old_operation, new_operation in operation_renames:
            connection.execute(
                text(
                    "UPDATE collection_jobs SET collector_operation = :new "
                    "WHERE collector_operation = :old"
                ),
                {"old": old_operation, "new": new_operation},
            )
        connection.execute(
            text(
                "UPDATE datasets SET storage_policy = json(:storage_policy) "
                "WHERE id = 'tushare.cn.stock.stock_basic' "
                "AND (storage_policy IS NULL OR json_type(storage_policy) = 'null')"
            ),
            {
                "storage_policy": json.dumps(
                    {
                        "logical_partition_field": None,
                        "calendar_dataset_id": None,
                        "layout": "snapshot",
                        "write_strategy": "replace_snapshot",
                        "compaction": None,
                    }
                )
            },
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

        # 早期 stock_basic 预置误将供应商的完整接口缩减为 3 个字段。仅在契约仍是
        # 精确的旧三字段形态且尚未发布数据时原位修正，避免改变已有物理数据的契约。
        stock_basic_schema_id = connection.execute(
            text(
                "SELECT s.id FROM dataset_schema_versions s "
                "WHERE s.dataset_id = 'tushare.cn.stock.stock_basic' AND s.version = 1 "
                "AND NOT EXISTS (SELECT 1 FROM catalog_files c "
                "WHERE c.dataset_id = s.dataset_id) "
                "AND (SELECT COUNT(*) FROM dataset_fields f "
                "WHERE f.schema_version_id = s.id) = 3 "
                "AND (SELECT GROUP_CONCAT(ordered.name, ',') FROM "
                "(SELECT f.name FROM dataset_fields f "
                "WHERE f.schema_version_id = s.id ORDER BY f.position) ordered) = "
                "'ts_code,name,list_status'"
            )
        ).scalar_one_or_none()
        if stock_basic_schema_id is not None:
            connection.execute(
                text(
                    "UPDATE dataset_fields SET position = CASE name "
                    "WHEN 'ts_code' THEN 0 WHEN 'name' THEN 2 WHEN 'list_status' THEN 11 END, "
                    "nullable = CASE WHEN name = 'ts_code' THEN 0 ELSE 1 END "
                    "WHERE schema_version_id = :schema_id"
                ),
                {"schema_id": stock_basic_schema_id},
            )
            missing_fields = (
                ("symbol", "string", "股票代码", 1),
                ("area", "string", "地域", 3),
                ("industry", "string", "所属行业", 4),
                ("fullname", "string", "股票全称", 5),
                ("enname", "string", "英文全称", 6),
                ("cnspell", "string", "拼音缩写", 7),
                ("market", "string", "市场类型", 8),
                ("exchange", "string", "交易所代码", 9),
                ("curr_type", "string", "交易货币", 10),
                ("list_date", "date", "上市日期", 12),
                ("delist_date", "date", "退市日期", 13),
                ("is_hs", "string", "沪深港通标的", 14),
                ("act_name", "string", "实控人名称", 15),
                ("act_ent_type", "string", "实控人企业性质", 16),
            )
            connection.execute(
                text(
                    "INSERT INTO dataset_fields "
                    "(schema_version_id, name, data_type, nullable, description, unit, "
                    "source_name, position) VALUES "
                    "(:schema_id, :name, :data_type, 1, :description, NULL, :name, :position)"
                ),
                [
                    {
                        "schema_id": stock_basic_schema_id,
                        "name": name,
                        "data_type": data_type,
                        "description": description,
                        "position": position,
                    }
                    for name, data_type, description, position in missing_fields
                ],
            )
        connection.execute(
            text(
                "UPDATE datasets SET description = "
                "'TuShare stock_basic 全部股票基础信息，包含上市、退市和暂停上市状态。' "
                "WHERE id = 'tushare.cn.stock.stock_basic' "
                "AND description = 'TuShare stock_basic 当前上市股票基础信息。'"
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
