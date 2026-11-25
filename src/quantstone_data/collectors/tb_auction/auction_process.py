from __future__ import annotations

import shutil
import zipfile
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from ...collection_protocol import CollectionContext, CollectionResult, DatasetArtifact
from . import baidu_client

DATASET_ID = "tb_lhsjk.cn.stock.auction_process"
CACHE_ROOT_NAME = "auction_process"

SCHEMA = pa.schema(
    [
        pa.field("ts_code", pa.string(), nullable=False),
        pa.field("trade_date", pa.date32(), nullable=False),
        pa.field("event_time", pa.int32(), nullable=False),
        pa.field("event_seq", pa.int32(), nullable=False),
        pa.field("matched_amount", pa.float64()),
        pa.field("matched_volume", pa.int64()),
        pa.field("unmatched_volume", pa.int64()),
        pa.field("book_side", pa.string()),
    ]
)


def convert_csv(source: Path, target: Path, trade_date: date) -> int:
    """转换供应商单日 CSV；同代码同时间的多行通过 event_seq 全部保留。"""
    try:
        import duckdb
    except ImportError as error:
        raise RuntimeError("集合竞价采集器缺少 duckdb") from error
    target.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    try:
        con.execute(
            """
            COPY (
                SELECT
                    CAST("股票代码" AS VARCHAR) AS ts_code,
                    CAST(? AS DATE) AS trade_date,
                    CAST("时间" AS INTEGER) AS event_time,
                    CAST(row_number() OVER (
                        PARTITION BY "股票代码", "时间"
                        ORDER BY "匹配金额（元）" NULLS FIRST,
                                 "匹配量（手）" NULLS FIRST,
                                 "未匹配量（手）" NULLS FIRST,
                                 "盘口买卖" NULLS FIRST
                    ) AS INTEGER) AS event_seq,
                    TRY_CAST("匹配金额（元）" AS DOUBLE) AS matched_amount,
                    TRY_CAST("匹配量（手）" AS BIGINT) AS matched_volume,
                    TRY_CAST("未匹配量（手）" AS BIGINT) AS unmatched_volume,
                    NULLIF(trim(CAST("盘口买卖" AS VARCHAR)), '') AS book_side
                FROM read_csv(?, header=true, all_varchar=true)
            ) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)
            """,
            [trade_date.isoformat(), str(source), str(target)],
        )
    finally:
        con.close()
    table = pq.read_table(target).cast(SCHEMA)
    pq.write_table(table, target, compression="zstd")
    return table.num_rows


def _artifact(context: CollectionContext, source: Path, day: date) -> DatasetArtifact:
    target = context.staging_dir / "outputs" / f"trade_date={day.isoformat()}.parquet"
    rows = convert_csv(source, target, day)
    return DatasetArtifact(DATASET_ID, target, {"trade_date": day.isoformat()}, rows)


def _cache_root(context: CollectionContext) -> Path:
    root = context.data_root or context.staging_dir.parent
    return Path(root) / "cache" / CACHE_ROOT_NAME


def collect_initial(
    context: CollectionContext, parameters: dict, _fields: list[dict]
) -> CollectionResult:
    day = date.fromisoformat(parameters["trade_date"])
    root = _cache_root(context)
    for parent in (root / "monthly", root / "extracted"):
        if parent.is_dir():
            for old in parent.iterdir():
                if old.stem.isdigit() and old.stem != f"{day:%Y%m}":
                    shutil.rmtree(old) if old.is_dir() else old.unlink()
    archive = root / "monthly" / f"{day:%Y%m}.zip"
    extracted = root / "extracted" / f"{day:%Y%m}"
    if not extracted.is_dir():
        try:
            baidu_client.fetch_shared_file(f"{day:%Y%m}.zip", archive, "月数据")
        except FileNotFoundError:
            source = context.staging_dir / f"{day:%Y%m%d}.csv"
            baidu_client.fetch_shared_file(source.name, source, "日数据")
            try:
                artifact = _artifact(context, source, day)
            finally:
                source.unlink(missing_ok=True)
            return CollectionResult(
                {DATASET_ID: [artifact]},
                {"source": "baidu_netdisk", "remote": source.name},
            )
        extracted.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as handle:
            handle.extractall(extracted)
        archive.unlink(missing_ok=True)
    source = next(iter(extracted.rglob(f"{day:%Y%m%d}.csv")), None)
    if source is None:
        raise FileNotFoundError(f"月包缺少 {day:%Y%m%d}.csv")
    artifact = _artifact(context, source, day)
    return CollectionResult(
        {DATASET_ID: [artifact]}, {"source": "baidu_netdisk", "remote": archive.name}
    )


def collect_daily(
    context: CollectionContext, parameters: dict, _fields: list[dict]
) -> CollectionResult:
    day = date.fromisoformat(parameters["trade_date"])
    source = context.staging_dir / f"{day:%Y%m%d}.csv"
    baidu_client.fetch_shared_file(source.name, source, "日数据")
    try:
        artifact = _artifact(context, source, day)
    finally:
        source.unlink(missing_ok=True)
    return CollectionResult(
        {DATASET_ID: [artifact]}, {"source": "baidu_netdisk", "remote": source.name}
    )
