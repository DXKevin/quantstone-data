from __future__ import annotations

import threading
import zipfile
from datetime import date
from pathlib import Path, PurePosixPath

import pyarrow as pa
import pyarrow.parquet as pq

from ...collection_protocol import CollectionContext, CollectionResult, DatasetArtifact
from . import baidu_client

DATASET_ID = "tb_minute.cn.stock.minute_1m"
ANNUAL_ROOT = "沪深股票/1分钟_按年汇总"
DAILY_ROOT = "沪深股票/每日更新/1分钟"
CACHE_ROOT_NAME = "minute_1m"
_YEAR_LOCK = threading.Lock()

SCHEMA = pa.schema(
    [
        pa.field("ts_code", pa.string(), nullable=False),
        pa.field("trade_date", pa.date32(), nullable=False),
        pa.field("bar_time", pa.int32(), nullable=False),
        pa.field("open", pa.float64(), nullable=True),
        pa.field("high", pa.float64(), nullable=True),
        pa.field("low", pa.float64(), nullable=True),
        pa.field("close", pa.float64(), nullable=True),
        pa.field("volume", pa.int64(), nullable=True),
        pa.field("amount", pa.float64(), nullable=True),
        pa.field("pct_chg", pa.float64(), nullable=True),
        pa.field("amplitude", pa.float64(), nullable=True),
    ]
)


def _normalize_sql(csv_glob: str, trade_date: str | None = None) -> str:
    where = ""
    if trade_date:
        where = (
            "WHERE CAST(CAST(\"时间\" AS TIMESTAMP) AS DATE) "
            f"= DATE '{trade_date}'"
        )
    return f"""
SELECT
    CASE lower(substr("代码", 1, 2))
        WHEN 'sh' THEN substr("代码", 3) || '.SH'
        WHEN 'sz' THEN substr("代码", 3) || '.SZ'
        ELSE "代码"
    END AS ts_code,
    CAST(CAST("时间" AS TIMESTAMP) AS DATE) AS trade_date,
    CAST(
        hour(CAST("时间" AS TIMESTAMP)) * 10000
        + minute(CAST("时间" AS TIMESTAMP)) * 100
        AS INTEGER
    ) AS bar_time,
    CAST("开盘价" AS DOUBLE) AS open,
    CAST("最高价" AS DOUBLE) AS high,
    CAST("最低价" AS DOUBLE) AS low,
    CAST("收盘价" AS DOUBLE) AS close,
    CAST("成交量" AS BIGINT) AS volume,
    CAST("成交额" AS DOUBLE) AS amount,
    CAST("涨幅" AS DOUBLE) AS pct_chg,
    CAST("振幅" AS DOUBLE) AS amplitude
FROM read_csv('{csv_glob}', header=true, union_by_name=true)
{where}
"""


def _cache_root(context: CollectionContext) -> Path:
    root = context.data_root or context.staging_dir.parent
    return Path(root) / "cache" / CACHE_ROOT_NAME


def _download(relative_path: str, target: Path, folder: str) -> Path:
    """把分享文件转存到年数据/日数据目录，下载后保留转存文件。"""
    target.parent.mkdir(parents=True, exist_ok=True)
    return baidu_client.fetch_shared_file(relative_path, target, folder)


def _extract(zip_path: Path, target_dir: Path) -> Path:
    if target_dir.exists():
        for item in target_dir.iterdir():
            if item.is_file():
                item.unlink()
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            name = PurePosixPath(member.filename)
            if name.is_absolute() or ".." in name.parts:
                raise ValueError(f"压缩包包含非法路径：{member.filename}")
        archive.extractall(target_dir)
    return target_dir


def _raise_file_limit() -> None:
    try:
        import resource
    except ImportError:
        return
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    target = min(hard, 65535)
    if soft < target:
        resource.setrlimit(resource.RLIMIT_NOFILE, (target, hard))


def _duckdb():
    try:
        import duckdb
    except ImportError as error:
        raise RuntimeError(
            "分钟采集器缺少 duckdb，请安装项目 minute 可选依赖"
        ) from error
    _raise_file_limit()
    return duckdb


def _build_year_partitions(zip_path: Path, year_dir: Path) -> Path:
    duckdb = _duckdb()
    csv_dir = _extract(zip_path, year_dir / "csv")
    daily_dir = year_dir / "daily"
    if daily_dir.exists():
        for item in sorted(daily_dir.rglob("*"), reverse=True):
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                item.rmdir()
    daily_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = year_dir / "duckdb_tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA memory_limit='4GB'")
    con.execute(f"PRAGMA temp_directory='{temp_dir.as_posix()}'")
    try:
        sql = _normalize_sql((csv_dir / "*.csv").as_posix())
        con.execute(
            f"COPY ({sql}) TO '{daily_dir.as_posix()}' "
            "(FORMAT PARQUET, PARTITION_BY (trade_date), "
            "OVERWRITE_OR_IGNORE, COMPRESSION ZSTD)"
        )
    finally:
        con.close()
        for item in sorted(csv_dir.rglob("*"), reverse=True):
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                item.rmdir()
        for item in sorted(temp_dir.rglob("*"), reverse=True):
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                item.rmdir()
        zip_path.unlink(missing_ok=True)
    (daily_dir / ".complete").write_text("ok", encoding="utf-8")
    return daily_dir


def _ensure_year_cache(context: CollectionContext, year: int) -> Path:
    cache_root = _cache_root(context)
    year_dir = cache_root / str(year)
    daily_dir = year_dir / "daily"
    if (daily_dir / ".complete").is_file():
        return daily_dir
    with _YEAR_LOCK:
        if (daily_dir / ".complete").is_file():
            return daily_dir
        # 清理更早年份的本地缓存；百度网盘源文件不动。
        for old in (cache_root.iterdir() if cache_root.exists() else []):
            if old.is_dir() and old.name.isdigit() and int(old.name) < year:
                _remove_tree(old)
        zip_path = year_dir / f"{year}_1min.zip"
        if not zip_path.is_file():
            _download(f"{ANNUAL_ROOT}/{year}_1min.zip", zip_path, "年数据")
        return _build_year_partitions(zip_path, year_dir)


def _remove_tree(path: Path) -> None:
    if not path.exists():
        return
    for item in sorted(path.rglob("*"), reverse=True):
        if item.is_file():
            item.unlink()
        elif item.is_dir():
            item.rmdir()
    path.rmdir()


def _cleanup_previous_dates(daily_dir: Path, current: date) -> None:
    for item in daily_dir.glob("trade_date=*"):
        if not item.is_dir():
            continue
        try:
            item_date = date.fromisoformat(item.name.split("=", 1)[1])
        except ValueError:
            continue
        if item_date < current:
            _remove_tree(item)


def _read_daily(daily_dir: Path, trade_date: str) -> pa.Table:
    partition_dir = daily_dir / f"trade_date={trade_date}"
    files = sorted(partition_dir.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"1分钟年度缓存缺少 {trade_date}：{partition_dir}")
    table = pa.concat_tables([pq.read_table(item) for item in files])
    for name in ("trade_date",):
        if name not in table.column_names:
            table = table.append_column(
                name, pa.array([date.fromisoformat(trade_date)] * table.num_rows, pa.date32())
            )
    return table.select([field.name for field in SCHEMA])


def _write_artifact(
    context: CollectionContext, table: pa.Table, trade_date: str
) -> DatasetArtifact:
    target = context.staging_dir / "outputs" / f"trade_date={trade_date}.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    typed = table.cast(SCHEMA)
    pq.write_table(typed, target, compression="zstd")
    return DatasetArtifact(
        dataset_id=DATASET_ID,
        path=target,
        partition={"trade_date": trade_date},
        row_count=typed.num_rows,
    )


def _build_daily_artifact(
    context: CollectionContext, zip_path: Path, trade_date: str
) -> DatasetArtifact:
    duckdb = _duckdb()
    extract_dir = context.staging_dir / "minute_csv"
    _extract(zip_path, extract_dir)
    target = context.staging_dir / "outputs" / f"trade_date={trade_date}.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = context.staging_dir / "duckdb_tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA memory_limit='4GB'")
    con.execute(f"PRAGMA temp_directory='{temp_dir.as_posix()}'")
    try:
        sql = _normalize_sql((extract_dir / "*.csv").as_posix(), trade_date)
        con.execute(
            f"COPY ({sql}) TO '{target.as_posix()}' "
            "(FORMAT PARQUET, COMPRESSION ZSTD)"
        )
    finally:
        con.close()
        _remove_tree(extract_dir)
        _remove_tree(temp_dir)
        zip_path.unlink(missing_ok=True)
    row_count = pq.ParquetFile(target).metadata.num_rows
    return DatasetArtifact(
        dataset_id=DATASET_ID,
        path=target,
        partition={"trade_date": trade_date},
        row_count=row_count,
    )


def collect_initial(
    context: CollectionContext, parameters: dict, field_contracts: list[dict]
) -> CollectionResult:
    trade_date = parameters["trade_date"]
    day = date.fromisoformat(trade_date)
    daily_dir = _ensure_year_cache(context, day.year)
    _cleanup_previous_dates(daily_dir, day)
    table = _read_daily(daily_dir, trade_date)
    artifact = _write_artifact(context, table, trade_date)
    return CollectionResult(
        outputs={DATASET_ID: [artifact]},
        provenance={
            "source": "baidu_netdisk",
            "remote": f"{ANNUAL_ROOT}/{day.year}_1min.zip",
            "trade_date": trade_date,
        },
    )


def collect_incremental(
    context: CollectionContext, parameters: dict, field_contracts: list[dict]
) -> CollectionResult:
    trade_date = parameters["trade_date"]
    day = date.fromisoformat(trade_date)
    remote = f"{DAILY_ROOT}/{day:%Y-%m}/{day:%Y%m%d}_1min.zip"
    zip_path = context.staging_dir / f"{day:%Y%m%d}_1min.zip"
    _download(remote, zip_path, "日数据")
    artifact = _build_daily_artifact(context, zip_path, trade_date)
    return CollectionResult(
        outputs={DATASET_ID: [artifact]},
        provenance={"source": "baidu_netdisk", "remote": remote, "trade_date": trade_date},
    )
