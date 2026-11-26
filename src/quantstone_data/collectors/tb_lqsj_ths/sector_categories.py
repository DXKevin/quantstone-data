from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pyarrow as pa
import pyarrow.parquet as pq

from ...collection_protocol import CollectionContext, CollectionResult, DatasetArtifact
from ...field_types import arrow_type, normalize_value
from ...provider_http import post_json

DATASET_ID = "tb_lqsj_ths.cn.index.sector_categories"
DEFAULT_API_URL = "https://data.diemeng.chat"
PAGE_SIZE = 1000
MAX_PAGE = 14


class ThsCollectionError(RuntimeError):
    pass


def _load_setting(name: str, project_root: Path | None = None) -> str | None:
    value = os.environ.get(name)
    if value:
        return value.strip()
    env_path = (project_root or Path.cwd()) / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == name and value.strip():
                return value.strip()
    return None


def load_api_key(project_root: Path | None = None) -> str:
    api_key = _load_setting("TB_LQSJ_THS_API_KEY", project_root)
    if api_key:
        return api_key
    raise ThsCollectionError("未配置 TB_LQSJ_THS_API_KEY")


def load_api_url(project_root: Path | None = None) -> str:
    url = _load_setting("TB_LQSJ_THS_API_URL", project_root) or DEFAULT_API_URL
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ThsCollectionError("TB_LQSJ_THS_API_URL 必须是有效的 http 或 https 地址")
    if parsed.username or parsed.password:
        raise ThsCollectionError("TB_LQSJ_THS_API_URL 不能包含用户名或密码")
    return url.rstrip("/")


def call_api(api_key: str, page: int, page_size: int = PAGE_SIZE) -> tuple[int, list[dict]]:
    body = post_json(
        "tb_lqsj_ths",
        f"{load_api_url()}/api/index/ths_sector_categories",
        {"page": page, "page_size": page_size},
        headers={"X-API-Key": api_key},
    )
    if body.get("code") != 200:
        raise ThsCollectionError(body.get("msg") or "THS 板块分类接口调用失败")
    data = body.get("data") or {}
    rows = data.get("list") or []
    if not isinstance(rows, list):
        raise ThsCollectionError("THS 板块分类接口的 data.list 不是数组")
    return int(data.get("total") or 0), rows


def _source_value(row: dict, field: dict) -> Any:
    return row.get(field.get("source_name") or field["name"])


def collect(context: CollectionContext, field_contracts: list[dict]) -> CollectionResult:
    by_code: dict[str, dict] = {}
    expected_total: int | None = None
    pages = 0
    for page in range(MAX_PAGE + 1):
        total, rows = call_api(context.token, page)
        pages += 1
        if expected_total is None:
            expected_total = total
        elif total != expected_total:
            raise ThsCollectionError("THS 板块分类分页期间 total 发生变化，请稍后重试")
        before = len(by_code)
        for row in rows:
            index_code = row.get("index_code")
            if index_code:
                by_code[str(index_code)] = row
        if len(by_code) >= total or len(rows) < PAGE_SIZE:
            break
        if len(by_code) == before:
            raise ThsCollectionError("THS 板块分类分页未前进")
    if expected_total is None or len(by_code) != expected_total:
        raise ThsCollectionError(
            f"THS 板块分类分页不完整：期望 {expected_total or 0} 条，实际 {len(by_code)} 条"
        )

    normalized = [
        {
            field["name"]: normalize_value(_source_value(row, field), field["data_type"])
            for field in field_contracts
        }
        for _index_code, row in sorted(by_code.items())
    ]
    schema = pa.schema(
        [
            pa.field(field["name"], arrow_type(field["data_type"]), field["nullable"])
            for field in field_contracts
        ]
    )
    table = pa.Table.from_pylist(normalized, schema=schema)
    target = context.staging_dir / "outputs" / "sector_categories.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, target, compression="zstd")
    return CollectionResult(
        outputs={DATASET_ID: [DatasetArtifact(DATASET_ID, target, {}, table.num_rows)]},
        provenance={
            "api": "ths_sector_categories",
            "api_url": load_api_url(),
            "pages": pages,
            "reported_total": expected_total,
        },
    )


def collect_initial(
    context: CollectionContext, _parameters: dict, field_contracts: list[dict]
) -> CollectionResult:
    return collect(context, field_contracts)


def collect_incremental(
    context: CollectionContext, _parameters: dict, field_contracts: list[dict]
) -> CollectionResult:
    return collect(context, field_contracts)
