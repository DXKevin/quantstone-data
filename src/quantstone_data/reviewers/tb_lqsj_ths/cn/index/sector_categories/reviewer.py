import pyarrow.compute as pc
import pyarrow.parquet as pq

from ......reviewer_types import ReviewContext, ReviewReport
from .....checks import check_not_empty, check_primary_key, check_required_fields

VALID_TYPES = {"N", "I", "R", "S", "ST", "TH", "BB"}


def review(context: ReviewContext) -> ReviewReport:
    table = pq.ParquetFile(context.artifact_path).read()
    errors = [
        *check_required_fields(table, context.schema),
        *check_not_empty(table),
        *check_primary_key(table, context.schema),
    ]
    if "type" in table.column_names:
        invalid_types = sorted(
            value for value in set(table.column("type").to_pylist()) if value not in VALID_TYPES
        )
        if invalid_types:
            errors.append(
                {
                    "code": "invalid_sector_type",
                    "message": f"存在未知板块类型：{', '.join(map(str, invalid_types))}",
                }
            )
    if "count" in table.column_names:
        negative_count = pc.sum(pc.less(table.column("count"), 0)).as_py() or 0
        if negative_count:
            errors.append(
                {
                    "code": "negative_constituent_count",
                    "message": f"存在 {negative_count} 行负数成分股数量",
                }
            )
    if "index_code" in table.column_names:
        invalid_codes = sum(
            not isinstance(value, str) or not value.endswith(".TI")
            for value in table.column("index_code").to_pylist()
        )
        if invalid_codes:
            errors.append(
                {
                    "code": "invalid_index_code",
                    "message": f"存在 {invalid_codes} 行非 .TI 板块代码",
                }
            )
    return ReviewReport(
        reviewer="tb_lqsj_ths.cn.index.sector_categories",
        passed=not errors,
        row_count=table.num_rows,
        errors=tuple(errors),
    )
