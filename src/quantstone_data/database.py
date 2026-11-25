import json
import os
from collections.abc import Generator
from pathlib import Path

from fastapi import Request
from sqlalchemy import Engine, bindparam, create_engine, event, inspect, text
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
        {"check_same_thread": False, "timeout": 60} if database_url.startswith("sqlite") else {}
    )
    engine = create_engine(database_url, connect_args=connect_args)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def _configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA busy_timeout=60000")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
            finally:
                cursor.close()
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def upgrade_sqlite_schema(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    inspector = inspect(engine)
    dataset_columns = {item["name"] for item in inspector.get_columns("datasets")}
    job_columns = {item["name"] for item in inspector.get_columns("collection_jobs")}
    added_update_frequency = "update_frequency" not in dataset_columns
    added_time_granularity = "time_granularity" not in dataset_columns
    added_is_historical = "is_historical" not in dataset_columns
    with engine.begin() as connection:
        if added_time_granularity:
            connection.execute(
                text(
                    "ALTER TABLE datasets ADD COLUMN time_granularity VARCHAR(32) "
                    "NOT NULL DEFAULT 'none'"
                )
            )
            connection.execute(
                text(
                    "UPDATE datasets SET time_granularity = 'day' "
                    "WHERE id IN ('tushare.cn.stock.daily', 'tushare.cn.stock.trade_cal')"
                )
            )
        if added_is_historical:
            connection.execute(
                text(
                    "ALTER TABLE datasets ADD COLUMN is_historical BOOLEAN "
                    "NOT NULL DEFAULT 0"
                )
            )
            connection.execute(
                text(
                    "UPDATE datasets SET is_historical = 1 "
                    "WHERE id LIKE 'zhongtai.cn.stock.l2_%.sz'"
                )
            )
        if added_update_frequency:
            connection.execute(
                text(
                    "ALTER TABLE datasets ADD COLUMN update_frequency VARCHAR(32) "
                    "NOT NULL DEFAULT 'manual'"
                )
            )
            connection.execute(
                text(
                    "UPDATE datasets SET update_frequency = 'daily' "
                    "WHERE id IN ('tushare.cn.stock.daily', 'tushare.cn.stock.stock_basic')"
                )
            )
            connection.execute(
                text(
                    "UPDATE datasets SET update_frequency = 'monthly' "
                    "WHERE id = 'tushare.cn.stock.trade_cal'"
                )
            )
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
        connection.execute(
            text(
                "UPDATE datasets SET storage_policy = "
                "json_set(storage_policy, '$.allow_empty_partitions', "
                "CASE WHEN id = 'tushare.cn.stock.stock_st' THEN json('true') "
                "ELSE json('false') END) "
                "WHERE storage_policy IS NOT NULL "
                "AND json_extract(storage_policy, '$.allow_empty_partitions') IS NULL"
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

        # index_basic 官方文档把基期、基点和发布日期标为必选，但真实历史记录存在空值。
        # 仅在尚未发布任何分区时放宽初始契约，避免修改已有数据集的实质契约。
        connection.execute(
            text(
                "UPDATE dataset_fields SET nullable = 1 WHERE name IN "
                "('base_date', 'base_point', 'list_date') AND schema_version_id IN ("
                "SELECT s.id FROM dataset_schema_versions s "
                "WHERE s.dataset_id = 'tushare.cn.index.index_basic'"
                ") AND NOT EXISTS (SELECT 1 FROM catalog_partitions p "
                "WHERE p.dataset_id = 'tushare.cn.index.index_basic')"
            )
        )
        connection.execute(
            text(
                "UPDATE datasets SET description = "
                "'TuShare index_basic 指数基本信息，覆盖 CSI、SSE、SZSE、SW。' "
                "WHERE id = 'tushare.cn.index.index_basic' AND description = "
                "'TuShare index_basic 指数基本信息，覆盖 MSCI、CSI、SSE、SZSE、CICC、SW、OTH。'"
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

        # L2 源目录使用 YYYYMMDD，但 Catalog 的日期分区键统一保存为 ISO YYYY-MM-DD。
        # 只修改元数据键；正式 Parquet 的既有相对路径保持不变，避免移动大文件。
        l2_dataset_ids = (
            "wind.cn.stock.l2_order.sz",
            "wind.cn.stock.l2_trade.sz",
            "tb_xxlpd.cn.stock.l2_order.sz",
            "tb_xxlpd.cn.stock.l2_trade.sz",
            "zhongtai.cn.stock.l2_order.sz",
            "zhongtai.cn.stock.l2_trade.sz",
        )
        compact_date_pattern = "[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]"
        iso_date_sql = (
            "substr(partition_key, 1, 4) || '-' || substr(partition_key, 5, 2) || '-' || "
            "substr(partition_key, 7, 2)"
        )
        connection.execute(
            text(
                f"UPDATE catalog_partitions SET partition_key = {iso_date_sql} "
                "WHERE dataset_id IN :dataset_ids AND length(partition_key) = 8 "
                "AND partition_key GLOB :date_pattern"
            ).bindparams(bindparam("dataset_ids", expanding=True)),
            {"dataset_ids": l2_dataset_ids, "date_pattern": compact_date_pattern},
        )
        connection.execute(
            text(
                f"UPDATE collection_runs SET partition_key = {iso_date_sql} "
                "WHERE job_id IN (SELECT id FROM collection_jobs WHERE dataset_id IN :dataset_ids) "
                "AND length(partition_key) = 8 AND partition_key GLOB :date_pattern"
            ).bindparams(bindparam("dataset_ids", expanding=True)),
            {"dataset_ids": l2_dataset_ids, "date_pattern": compact_date_pattern},
        )
        wind_bindings = {
            "wind.cn.stock.l2_order.sz": (
                '[{"purpose":"initial","collector_key":"wind_l2_sz",'
                '"operation":"wind_l2_initial","parameters":{}},'
                '{"purpose":"incremental","collector_key":"wind_l2_sz",'
                '"operation":"wind_l2_incremental","parameters":{}}]'
            ),
            "wind.cn.stock.l2_trade.sz": (
                '[{"purpose":"initial","collector_key":"wind_l2_sz",'
                '"operation":"wind_l2_initial","parameters":{}},'
                '{"purpose":"incremental","collector_key":"wind_l2_sz",'
                '"operation":"wind_l2_incremental","parameters":{}}]'
            ),
        }
        for dataset_id, bindings in wind_bindings.items():
            connection.execute(
                text(
                    "UPDATE datasets SET collection_bindings = :bindings "
                    "WHERE id = :dataset_id AND (collection_bindings IS NULL "
                    "OR collection_bindings = '[]' OR collection_bindings LIKE '%l2_order_%' "
                    "OR collection_bindings LIKE '%l2_trade_%')"
                ),
                {"dataset_id": dataset_id, "bindings": bindings},
            )
        index_daily_bindings = (
            '[{"purpose":"initial","collector_key":"tushare_cn_stock",'
            '"operation":"index_daily_initial","parameters":{}},'
            '{"purpose":"incremental","collector_key":"tushare_cn_stock",'
            '"operation":"index_daily_incremental","parameters":{}},'
            '{"purpose":"repair","collector_key":"tushare_cn_stock",'
            '"operation":"index_daily_repair","parameters":{}}]'
        )
        connection.execute(
            text(
                "UPDATE datasets SET collection_bindings = :bindings "
                "WHERE id = :dataset_id"
            ),
            {
                "dataset_id": "tushare.cn.index.index_daily",
                "bindings": index_daily_bindings,
            },
        )
        minute_bindings = (
            '[{"purpose":"initial","collector_key":"tb_lhsjk_023199",'
            '"operation":"minute_1m_initial","parameters":{}},'
            '{"purpose":"incremental","collector_key":"tb_lhsjk_023199",'
            '"operation":"minute_1m_incremental","parameters":{}},'
            '{"purpose":"repair","collector_key":"tb_lhsjk_023199",'
            '"operation":"minute_1m_repair","parameters":{}}]'
        )
        connection.execute(
            text(
                "UPDATE datasets SET collection_bindings = :bindings "
                "WHERE id = :dataset_id"
            ),
            {
                "dataset_id": "tb_lhsjk_023199.cn.stock.minute_1m",
                "bindings": minute_bindings,
            },
        )


def migrate_minute_provider_id(engine: Engine, data_root: Path) -> bool:
    """把分钟数据的临时淘宝渠道代号原地迁移为稳定卖家代号。"""
    if engine.dialect.name != "sqlite":
        return False
    old_id = "tb_minute.cn.stock.minute_1m"
    new_id = "tb_lhsjk_023199.cn.stock.minute_1m"
    old_collector = "tb_minute"
    new_collector = "tb_lhsjk_023199"
    with engine.connect() as connection:
        exists = connection.scalar(
            text("SELECT COUNT(*) FROM datasets WHERE id = :dataset_id"),
            {"dataset_id": old_id},
        )
        new_exists = connection.scalar(
            text("SELECT COUNT(*) FROM datasets WHERE id = :dataset_id"),
            {"dataset_id": new_id},
        )
    old_directory = data_root / "datasets" / old_id
    new_directory = data_root / "datasets" / new_id
    if not exists:
        if new_exists and old_directory.is_dir() and not new_directory.exists():
            old_directory.rename(new_directory)
        return False
    if new_exists:
        raise RuntimeError(f"分钟数据迁移目标已存在：{new_id}")
    if old_directory.is_dir() and new_directory.exists():
        raise RuntimeError(f"分钟数据迁移目录冲突：{new_directory}")

    directory_renamed = False
    if old_directory.is_dir():
        old_directory.rename(new_directory)
        directory_renamed = True
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO datasets (id, provider, region, instrument, dataset_name, "
                    "market, display_name, description, category_id, status, update_frequency, "
                    "time_granularity, is_historical, current_schema_version, collection_bindings, "
                    "storage_policy, created_at, updated_at) "
                    "SELECT :new_id, :new_provider, region, instrument, dataset_name, market, "
                    "display_name, description, category_id, status, update_frequency, "
                    "time_granularity, is_historical, current_schema_version, "
                    "replace(collection_bindings, :old_collector, :new_collector), storage_policy, "
                    "created_at, updated_at FROM datasets WHERE id = :old_id"
                ),
                {
                    "old_id": old_id,
                    "new_id": new_id,
                    "new_provider": new_collector,
                    "old_collector": old_collector,
                    "new_collector": new_collector,
                },
            )
            for table in (
                "dataset_schema_versions",
                "collection_jobs",
                "maintenance_jobs",
                "catalog_files",
                "catalog_partitions",
                "import_jobs",
            ):
                connection.execute(
                    text(f"UPDATE {table} SET dataset_id = :new_id WHERE dataset_id = :old_id"),
                    {"old_id": old_id, "new_id": new_id},
                )
            connection.execute(
                text(
                    "UPDATE collection_jobs SET collector_key = :new_collector "
                    "WHERE collector_key = :old_collector"
                ),
                {"old_collector": old_collector, "new_collector": new_collector},
            )
            for table, column in (
                ("catalog_files", "path"),
                ("catalog_partitions", "file_path"),
                ("collection_runs", "published_path"),
            ):
                connection.execute(
                    text(
                        f"UPDATE {table} SET {column} = replace({column}, :old_id, :new_id) "
                        f"WHERE {column} LIKE :old_pattern"
                    ),
                    {
                        "old_id": old_id,
                        "new_id": new_id,
                        "old_pattern": f"%{old_id}%",
                    },
                )
            connection.execute(
                text("DELETE FROM datasets WHERE id = :old_id"), {"old_id": old_id}
            )
    except Exception:
        if directory_renamed and new_directory.is_dir() and not old_directory.exists():
            new_directory.rename(old_directory)
        raise
    return True


def get_session(request: Request) -> Generator[Session, None, None]:
    with request.app.state.session_factory() as session:
        yield session


PROVIDER_RENAMES = (
    (
        "tushare.cn.etf.basic",
        "tushare.cn.etf.etf_basic",
        "tushare",
    ),
    (
        "tb.cn.stock.auction_process",
        "tb_lhsjk.cn.stock.auction_process",
        "tb_lhsjk",
    ),
    (
        "tb_lhsjk_023199.cn.stock.minute_1m",
        "tb_sbkj2077.cn.stock.minute_1m",
        "tb_sbkj2077",
    ),
    (
        "wind.cn.stock.l2_order.sz",
        "tb_xxlpd.cn.stock.l2_order.sz",
        "tb_xxlpd",
    ),
    (
        "wind.cn.stock.l2_trade.sz",
        "tb_xxlpd.cn.stock.l2_trade.sz",
        "tb_xxlpd",
    ),
)


def migrate_provider_ids(engine: Engine, data_root: Path) -> list[tuple[str, str]]:
    """原地重命名数据集供应商 ID，并同步 Catalog、任务和物理目录。"""
    if engine.dialect.name != "sqlite":
        return []
    migrated: list[tuple[str, str]] = []
    for old_id, new_id, new_provider in PROVIDER_RENAMES:
        with engine.connect() as connection:
            exists = connection.scalar(
                text("SELECT COUNT(*) FROM datasets WHERE id = :dataset_id"),
                {"dataset_id": old_id},
            )
            new_exists = connection.scalar(
                text("SELECT COUNT(*) FROM datasets WHERE id = :dataset_id"),
                {"dataset_id": new_id},
            )
        old_directory = data_root / "datasets" / old_id
        new_directory = data_root / "datasets" / new_id
        old_revisions = data_root / "revisions" / old_id
        new_revisions = data_root / "revisions" / new_id
        if not exists:
            continue
        if new_exists:
            raise RuntimeError(f"数据集迁移目标已存在：{new_id}")
        if old_directory.is_dir() and new_directory.exists():
            raise RuntimeError(f"数据集迁移目录冲突：{new_directory}")
        directory_renamed = False
        revisions_renamed = False
        if old_directory.is_dir():
            old_directory.rename(new_directory)
            directory_renamed = True
        if old_revisions.is_dir() and not new_revisions.exists():
            old_revisions.rename(new_revisions)
            revisions_renamed = True
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO datasets (id, provider, region, instrument, dataset_name, "
                        "market, display_name, description, category_id, status, update_frequency, "
                        "time_granularity, is_historical, current_schema_version, "
                        "collection_bindings, storage_policy, created_at, updated_at) "
                        "SELECT :new_id, :new_provider, region, instrument, dataset_name, market, "
                        "display_name, description, category_id, status, update_frequency, "
                        "time_granularity, is_historical, current_schema_version, "
                        "collection_bindings, storage_policy, created_at, updated_at "
                        "FROM datasets WHERE id = :old_id"
                    ),
                    {
                        "old_id": old_id,
                        "new_id": new_id,
                        "new_provider": new_provider,
                    },
                )
                for table in (
                    "dataset_schema_versions",
                    "collection_jobs",
                    "maintenance_jobs",
                    "catalog_files",
                    "catalog_partitions",
                    "import_jobs",
                ):
                    connection.execute(
                        text(
                            f"UPDATE {table} SET dataset_id = :new_id "
                            "WHERE dataset_id = :old_id"
                        ),
                        {"old_id": old_id, "new_id": new_id},
                    )
                for table, column in (
                    ("catalog_files", "path"),
                    ("catalog_partitions", "file_path"),
                    ("collection_runs", "published_path"),
                    ("collection_runs", "staged_path"),
                    ("import_jobs", "manifest_path"),
                ):
                    connection.execute(
                        text(
                            f"UPDATE {table} SET {column} = replace({column}, :old_id, :new_id) "
                            f"WHERE {column} LIKE :old_pattern"
                        ),
                        {
                            "old_id": old_id,
                            "new_id": new_id,
                            "old_pattern": f"%{old_id}%",
                        },
                    )
                connection.execute(
                    text("DELETE FROM datasets WHERE id = :old_id"),
                    {"old_id": old_id},
                )
            migrated.append((old_id, new_id))
        except Exception:
            if directory_renamed and new_directory.is_dir() and not old_directory.exists():
                new_directory.rename(old_directory)
            if revisions_renamed and new_revisions.is_dir() and not old_revisions.exists():
                new_revisions.rename(old_revisions)
            raise
    return migrated


NEUTRAL_COLLECTOR_KEYS = (
    ("wind_l2_sz", "l2_sz_baidu"),
    ("tb_auction", "auction_baidu"),
    ("tb_lhsjk_023199", "minute_baidu"),
)


def migrate_neutral_collector_keys(engine: Engine) -> list[tuple[str, str]]:
    """把带供应商品牌的采集器/扫描器内部 key 迁移为中性名称。"""
    if engine.dialect.name != "sqlite":
        return []
    migrated: list[tuple[str, str]] = []
    with engine.begin() as connection:
        for old_key, new_key in NEUTRAL_COLLECTOR_KEYS:
            connection.execute(
                text(
                    "UPDATE collection_jobs SET collector_key = :new_key "
                    "WHERE collector_key = :old_key"
                ),
                {"old_key": old_key, "new_key": new_key},
            )
            connection.execute(
                text(
                    "UPDATE import_jobs SET scanner_key = :new_key "
                    "WHERE scanner_key = :old_key"
                ),
                {"old_key": old_key, "new_key": new_key},
            )
            rows = connection.execute(
                text(
                    "SELECT id, collection_bindings FROM datasets "
                    "WHERE collection_bindings LIKE :pattern"
                ),
                {"pattern": f"%{old_key}%"},
            ).fetchall()
            for dataset_id, raw in rows:
                try:
                    bindings = json.loads(raw or "[]")
                except (TypeError, json.JSONDecodeError):
                    continue
                changed = False
                for binding in bindings:
                    if isinstance(binding, dict) and binding.get("collector_key") == old_key:
                        binding["collector_key"] = new_key
                        changed = True
                if changed:
                    connection.execute(
                        text(
                            "UPDATE datasets SET collection_bindings = :bindings "
                            "WHERE id = :dataset_id"
                        ),
                        {
                            "dataset_id": dataset_id,
                            "bindings": json.dumps(
                                bindings, ensure_ascii=False, separators=(",", ":")
                            ),
                        },
                    )
            migrated.append((old_key, new_key))
    return migrated
