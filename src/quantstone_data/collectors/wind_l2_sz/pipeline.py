from __future__ import annotations

import os
import shutil
import subprocess
import threading
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from uuid import uuid4

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from ...collection_protocol import CollectionContext, CollectionResult, DatasetArtifact
from .baidu import ensure_archive

ORDER_ID = "wind.cn.stock.l2_order.sz"
TRADE_ID = "wind.cn.stock.l2_trade.sz"
_PIPELINE_LOCK = threading.Lock()


@dataclass(frozen=True)
class WindSpec:
    key: str
    dataset_id: str
    csv_name: str
    output_name: str
    schema: pa.Schema


ORDER = WindSpec(
    "order",
    ORDER_ID,
    "逐笔委托.csv",
    "l2_order.parquet",
    pa.schema(
        [
            pa.field("symbol", pa.string(), False),
            pa.field("exchange_code", pa.string(), False),
            pa.field("trade_date", pa.date32(), False),
            pa.field("event_time", pa.int32(), False),
            pa.field("channel_code", pa.string(), False),
            pa.field("exchange_order_no", pa.int64(), False),
            pa.field("order_type", pa.string(), False),
            pa.field("side", pa.string(), False),
            pa.field("price", pa.int64(), False),
            pa.field("volume", pa.int64(), False),
        ]
    ),
)
TRADE = WindSpec(
    "trade",
    TRADE_ID,
    "逐笔成交.csv",
    "l2_trade.parquet",
    pa.schema(
        [
            pa.field("symbol", pa.string(), False),
            pa.field("exchange_code", pa.string(), False),
            pa.field("trade_date", pa.date32(), False),
            pa.field("event_time", pa.int32(), False),
            pa.field("trade_no", pa.int64(), False),
            pa.field("trade_code", pa.string(), True),
            pa.field("order_code", pa.string(), True),
            pa.field("side", pa.string(), True),
            pa.field("price", pa.int64(), False),
            pa.field("volume", pa.int64(), False),
            pa.field("ask_order_no", pa.int64(), False),
            pa.field("bid_order_no", pa.int64(), False),
        ]
    ),
)


def _column(batch: pa.RecordBatch, name: str) -> pa.Array:
    index = batch.schema.get_field_index(name)
    if index < 0:
        raise ValueError(f"Wind CSV 缺少字段：{name}")
    return batch.column(index)


def _text(batch: pa.RecordBatch, name: str, *, nullable: bool = False) -> pa.Array:
    value = pc.utf8_trim_whitespace(pc.cast(_column(batch, name), pa.string()))
    if nullable:
        value = pc.if_else(pc.equal(value, ""), pa.scalar(None, pa.string()), value)
    return value


def _trade_date(batch: pa.RecordBatch, expected: date) -> pa.Array:
    raw = pc.cast(_column(batch, "自然日"), pa.string())
    parsed = pc.cast(pc.strptime(raw, format="%Y%m%d", unit="s"), pa.date32())
    invalid = pc.sum(pc.cast(pc.not_equal(parsed, pa.scalar(expected)), pa.int64())).as_py()
    if invalid:
        raise ValueError(f"Wind CSV 自然日与目标日期不一致：{invalid} 行")
    return parsed


def _transform(batch: pa.RecordBatch, spec: WindSpec, expected: date) -> pa.Table:
    symbol = _text(batch, "万得代码")
    exchange_code = pc.utf8_slice_codeunits(symbol, 0, 6)
    common = [symbol, exchange_code, _trade_date(batch, expected)]
    if spec.key == "order":
        price_text = pc.replace_substring(_text(batch, "委托价格"), "18446744073709541616", "0")
        values = common + [
            pc.cast(_column(batch, "时间"), pa.int32()),
            _text(batch, "委托编号"),
            pc.cast(_column(batch, "交易所委托号"), pa.int64()),
            _text(batch, "委托类型"),
            _text(batch, "委托代码"),
            pc.cast(price_text, pa.int64()),
            pc.cast(_column(batch, "委托数量"), pa.int64()),
        ]
    else:
        values = common + [
            pc.cast(_column(batch, "时间"), pa.int32()),
            pc.cast(_column(batch, "成交编号"), pa.int64()),
            _text(batch, "成交代码", nullable=True),
            _text(batch, "委托代码", nullable=True),
            _text(batch, "BS标志", nullable=True),
            pc.cast(_column(batch, "成交价格"), pa.int64()),
            pc.cast(_column(batch, "成交数量"), pa.int64()),
            pc.cast(_column(batch, "叫卖序号"), pa.int64()),
            pc.cast(_column(batch, "叫买序号"), pa.int64()),
        ]
    return pa.Table.from_arrays(values, schema=spec.schema)


def convert_extracted_day(source: Path, target: Path, spec: WindSpec, expected: date) -> int:
    stock_dirs = sorted(
        item
        for item in source.iterdir()
        if item.is_dir() and item.name[:1] in {"0", "3"}
    )
    if not stock_dirs:
        raise RuntimeError(f"解压目录没有深市股票文件：{source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f"{target.name}.tmp")
    temporary.unlink(missing_ok=True)
    writer = pq.ParquetWriter(temporary, spec.schema, compression="zstd", use_dictionary=True)
    rows = 0
    try:
        for stock_dir in stock_dirs:
            csv_path = stock_dir / spec.csv_name
            if not csv_path.is_file():
                raise FileNotFoundError(f"Wind 股票目录缺少 {spec.csv_name}：{stock_dir}")
            reader = pacsv.open_csv(
                csv_path,
                read_options=pacsv.ReadOptions(encoding="gbk", block_size=8 * 1024 * 1024),
                convert_options=pacsv.ConvertOptions(
                    column_types={
                        "委托类型": pa.string(),
                        "委托代码": pa.string(),
                        "委托价格": pa.string(),
                        "成交代码": pa.string(),
                        "BS标志": pa.string(),
                    }
                ),
            )
            for batch in reader:
                table = _transform(batch, spec, expected)
                writer.write_table(table)
                rows += table.num_rows
        writer.close()
    except Exception:
        writer.close()
        temporary.unlink(missing_ok=True)
        raise
    if rows == 0:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"Wind {spec.key} 转换结果为空：{expected}")
    os.replace(temporary, target)
    return rows


def _extract(archive: Path, root: Path, run_date: date) -> Path:
    expected = root / f"{run_date:%Y%m%d}"
    if expected.is_dir():
        return expected
    root.mkdir(parents=True, exist_ok=True)
    temporary_root = root / f".{run_date:%Y%m%d}.tmp-{uuid4().hex}"
    try:
        subprocess.run(
            ["7z", "x", "-y", f"-o{temporary_root}", str(archive)],
            check=True,
            capture_output=True,
            text=True,
        )
        extracted = temporary_root / f"{run_date:%Y%m%d}"
        if not extracted.is_dir():
            raise RuntimeError(f"Wind 压缩包解压后缺少日期目录：{extracted}")
        os.replace(extracted, expected)
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)
    return expected


def collect_wind_l2(
    context: CollectionContext,
    parameters: dict,
    _field_contracts: list[dict],
) -> CollectionResult:
    if context.data_root is None:
        raise RuntimeError("Wind L2 采集器缺少 data_root")
    run_date = date.fromisoformat(str(parameters["trade_date"]))
    work_root = context.data_root / "downloads" / "wind_l2"
    archive = work_root / "archives" / f"{run_date:%Y%m}" / f"{run_date:%Y%m%d}.7z"
    extract_root = work_root / "extracted"
    outputs: dict[str, list[DatasetArtifact]] = {}
    with _PIPELINE_LOCK:
        ensure_archive(run_date, archive)
        source = _extract(archive, extract_root, run_date)
        for spec in (ORDER, TRADE):
            target = context.staging_dir / "outputs" / spec.output_name
            rows = convert_extracted_day(source, target, spec, run_date)
            outputs[spec.dataset_id] = [
                DatasetArtifact(
                    dataset_id=spec.dataset_id,
                    path=target,
                    partition={"trade_date": run_date.isoformat()},
                    row_count=rows,
                )
            ]
        shutil.rmtree(source)
        archive.unlink(missing_ok=True)
    return CollectionResult(
        outputs=outputs,
        provenance={"source": "baidu_netdisk", "archive": archive.name},
    )
