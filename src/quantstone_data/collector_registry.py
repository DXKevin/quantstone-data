from .collector_types import CollectorDefinition, CollectorOperation
from .collectors.tb_auction import COLLECTOR as TB_AUCTION
from .collectors.tb_lhsjk_023199 import COLLECTOR as TB_MINUTE
from .collectors.tushare_cn_etf import COLLECTOR as TUSHARE_CN_ETF
from .collectors.tushare_cn_stock import COLLECTOR as TUSHARE_CN_STOCK
from .collectors.wind_l2_sz import COLLECTOR as WIND_L2_SZ


def _build_registry(definitions: tuple[CollectorDefinition, ...]) -> dict[str, CollectorDefinition]:
    registry: dict[str, CollectorDefinition] = {}
    for collector in definitions:
        if collector.key in registry:
            raise RuntimeError(f"duplicate collector key: {collector.key}")
        if not collector.operations:
            raise RuntimeError(f"collector has no operations: {collector.key}")
        for operation_key, operation in collector.operations.items():
            if operation_key != operation.key:
                raise RuntimeError(f"operation key mismatch: {collector.key}.{operation_key}")
            if not callable(operation.function):
                raise RuntimeError(f"operation is not callable: {collector.key}.{operation_key}")
            if not operation.datasets:
                raise RuntimeError(f"operation has no outputs: {collector.key}.{operation_key}")
            names = [parameter.name for parameter in operation.parameters]
            if len(names) != len(set(names)):
                raise RuntimeError(
                    f"duplicate operation parameter: {collector.key}.{operation_key}"
                )
        registry[collector.key] = collector
    return registry


COLLECTORS = _build_registry((TUSHARE_CN_STOCK, TUSHARE_CN_ETF, WIND_L2_SZ, TB_MINUTE, TB_AUCTION))


def get_collector(key: str) -> CollectorDefinition | None:
    return COLLECTORS.get(key)


def get_operation(collector_key: str, operation_key: str) -> CollectorOperation | None:
    collector = get_collector(collector_key)
    return collector.operations.get(operation_key) if collector else None


def validate_operation_parameters(
    operation: CollectorOperation,
    parameters: dict,
    *,
    require_all: bool,
) -> None:
    definitions = {parameter.name: parameter for parameter in operation.parameters}
    unknown = set(parameters) - set(definitions)
    if unknown:
        raise ValueError(f"unknown operation parameters: {sorted(unknown)}")
    if require_all:
        missing = [
            parameter.name
            for parameter in operation.parameters
            if parameter.required and parameter.name not in parameters
        ]
        if missing:
            raise ValueError(f"required operation parameters are missing: {missing}")
