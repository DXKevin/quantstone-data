from pathlib import Path


def resolve_partition_target(
    data_root: Path,
    dataset_id: str,
    storage_policy: dict,
    partition_key: str,
    run_id: str,
) -> Path:
    layout = storage_policy.get("layout")
    base = data_root / "datasets" / dataset_id
    if layout == "yearly_with_delta":
        year = partition_key[:4]
        return base / "delta" / year / partition_key / f"{run_id}.parquet"
    if layout == "daily":
        return base / partition_key / f"{run_id}.parquet"
    if layout == "snapshot":
        return base / "snapshot" / f"{run_id}.parquet"
    raise ValueError(f"unsupported storage layout: {layout}")
