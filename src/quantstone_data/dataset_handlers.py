from dataclasses import dataclass

from .datasets.tushare.cn.stock.stock_basic.definition import (
    COLLECTOR_KEY,
    DATASET_ID,
    REVIEWER_KEY,
)


@dataclass(frozen=True)
class DatasetHandler:
    collector_key: str
    reviewer_key: str


DATASET_HANDLERS = {
    DATASET_ID: DatasetHandler(
        collector_key=COLLECTOR_KEY,
        reviewer_key=REVIEWER_KEY,
    )
}


def handler_for(dataset_id: str) -> DatasetHandler | None:
    return DATASET_HANDLERS.get(dataset_id)
