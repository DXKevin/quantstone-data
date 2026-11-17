from dataclasses import dataclass


@dataclass(frozen=True)
class DatasetHandler:
    collector_key: str
    reviewer_key: str


DATASET_HANDLERS = {
    "tushare.cn.stock.stock_basic": DatasetHandler(
        collector_key="tushare.stock_basic",
        reviewer_key="tushare.stock_basic",
    )
}


def handler_for(dataset_id: str) -> DatasetHandler | None:
    return DATASET_HANDLERS.get(dataset_id)
