from .scanner_types import ScannerDefinition, ScannerOperation
from .scanners.wind_l2_sz.definition import SCANNERS as WIND_SCANNERS


def _build_scanner_registry(
    definitions: tuple[ScannerDefinition, ...],
) -> dict[str, ScannerDefinition]:
    registry: dict[str, ScannerDefinition] = {}
    for scanner in definitions:
        if scanner.key in registry:
            raise RuntimeError(f"duplicate scanner: {scanner.key}")
        operation_keys: set[str] = set()
        for operation in scanner.operations:
            if operation.key in operation_keys:
                raise RuntimeError(
                    f"duplicate scanner operation: {scanner.key}.{operation.key}"
                )
            operation_keys.add(operation.key)
            if not operation.filename:
                raise RuntimeError(
                    f"scanner operation filename is empty: {scanner.key}.{operation.key}"
                )
        registry[scanner.key] = scanner
    return registry


SCANNERS = _build_scanner_registry(WIND_SCANNERS)


def get_scanner(key: str) -> ScannerDefinition | None:
    return SCANNERS.get(key)


def get_scanner_operation(
    scanner_key: str, operation_key: str
) -> ScannerOperation | None:
    scanner = SCANNERS.get(scanner_key)
    if scanner is None:
        return None
    return next(
        (item for item in scanner.operations if item.key == operation_key), None
    )
