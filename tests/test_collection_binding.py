from quantstone_data.collection import _resolve_collection_binding
from quantstone_data.collection_schemas import CollectionOperation


def test_repair_reuses_incremental_collector_for_partitioned_dataset() -> None:
    bindings = [
        {"purpose": "initial", "collector_key": "demo", "operation": "initial"},
        {"purpose": "incremental", "collector_key": "demo", "operation": "incremental"},
    ]

    binding = _resolve_collection_binding(
        bindings,
        CollectionOperation.REPAIR,
        allow_repair_fallback=True,
    )

    assert binding == bindings[1]


def test_explicit_repair_binding_takes_precedence() -> None:
    bindings = [
        {"purpose": "incremental", "collector_key": "demo", "operation": "incremental"},
        {"purpose": "repair", "collector_key": "demo", "operation": "repair"},
    ]

    binding = _resolve_collection_binding(
        bindings,
        CollectionOperation.REPAIR,
        allow_repair_fallback=True,
    )

    assert binding == bindings[1]


def test_snapshot_dataset_does_not_gain_implicit_repair_binding() -> None:
    bindings = [
        {"purpose": "incremental", "collector_key": "demo", "operation": "incremental"},
    ]

    binding = _resolve_collection_binding(
        bindings,
        CollectionOperation.REPAIR,
        allow_repair_fallback=False,
    )

    assert binding is None
