"""数据集字段的数据类型：Registry 校验、采集器归一化和 Parquet 映射的唯一来源。

只开放 Parquet 原生支持且语义明确的类型。``timestamp`` 统一表示**无时区的交易所
本地时间**（例如 ``2026-11-19 09:30:00``），带时区的值会被拒绝，避免静默换算。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pyarrow as pa

DATE_FORMAT = "%Y%m%d"

SUPPORTED_DATA_TYPES: dict[str, pa.DataType] = {
    "string": pa.string(),
    "int32": pa.int32(),
    "int64": pa.int64(),
    "float32": pa.float32(),
    "float64": pa.float64(),
    "boolean": pa.bool_(),
    "date": pa.date32(),
    "timestamp": pa.timestamp("us"),
}
DATA_TYPE_NAMES = tuple(SUPPORTED_DATA_TYPES)


def _unsupported(data_type: str) -> ValueError:
    return ValueError(
        f"不支持的数据类型：{data_type}；可选类型：{', '.join(DATA_TYPE_NAMES)}"
    )


def arrow_type(data_type: str) -> pa.DataType:
    """把契约类型转换为 Parquet/Arrow 类型。"""
    try:
        return SUPPORTED_DATA_TYPES[data_type]
    except KeyError:
        raise _unsupported(data_type) from None


def normalize_value(value: Any, data_type: str) -> Any:
    """把供应商源值转换为契约声明的类型；空值保持为空。"""
    arrow_type(data_type)
    if value is None or value == "":
        return None
    if data_type == "string":
        return str(value)
    if data_type == "date":
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return datetime.strptime(str(value), DATE_FORMAT).date()
    if data_type in {"int32", "int64"}:
        return int(value)
    if data_type in {"float32", "float64"}:
        return float(value)
    if data_type == "boolean":
        return bool(value)
    if data_type == "timestamp":
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
        if parsed.tzinfo is not None:
            raise ValueError("timestamp 字段只接受无时区的交易所本地时间")
        return parsed
    raise _unsupported(data_type)
