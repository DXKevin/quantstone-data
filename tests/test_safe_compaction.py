from datetime import UTC, date, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from sqlalchemy import select

import quantstone_data.storage as storage
from quantstone_data.database import Base, create_session_factory
from quantstone_data.models import CatalogFile, CatalogPartition, Dataset
from quantstone_data.storage import compact_year

DATASET_ID = "demo.cn.stock.safe_daily"


def _session_factory(tmp_path: Path):
    factory = create_session_factory(f"sqlite:///{tmp_path / 'catalog.db'}")
    Base.metadata.create_all(factory.kw["bind"])
    return factory


def _seed_partition(
    session,
    data_root: Path,
    partition_key: str,
    symbol: str,
    *,
    relative_path: str,
    catalog_rows: int = 1,
) -> None:
    target = data_root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        pa.table(
            {
                "trade_date": [date.fromisoformat(partition_key)],
                "symbol": [symbol],
            }
        ),
        target,
    )
    file_row = CatalogFile(
        dataset_id=DATASET_ID,
        path=relative_path,
        row_count=1,
        size_bytes=target.stat().st_size,
        sha256="source",
    )
    session.add(file_row)
    session.flush()
    session.add(
        CatalogPartition(
            dataset_id=DATASET_ID,
            partition_key=partition_key,
            file_path=relative_path,
            file_id=file_row.id,
            row_count=catalog_rows,
            size_bytes=target.stat().st_size,
            sha256="source",
            collection_run_id=f"run-{partition_key}",
            published_at=datetime.now(UTC),
        )
    )


def _seed_dataset(session) -> None:
    session.add(
        Dataset(
            id=DATASET_ID,
            provider="demo",
            region="cn",
            instrument="stock",
            dataset_name="safe_daily",
            display_name="安全合并测试",
            status="active",
            storage_policy={
                "layout": "yearly_with_delta",
                "logical_partition_field": "trade_date",
                "compaction": "yearly",
            },
        )
    )
    session.flush()


def test_compaction_keeps_current_catalog_version_for_each_date(tmp_path: Path) -> None:
    factory = _session_factory(tmp_path)
    data_root = tmp_path / "data"
    with factory() as session:
        _seed_dataset(session)
        annual = f"datasets/{DATASET_ID}/annual/2024.parquet"
        annual_path = data_root / annual
        annual_path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(
            pa.table(
                {
                    "trade_date": [date(2024, 1, 2), date(2024, 1, 3)],
                    "symbol": ["ORIGINAL-02", "ORIGINAL-03"],
                }
            ),
            annual_path,
        )
        annual_file = CatalogFile(
            dataset_id=DATASET_ID,
            path=annual,
            row_count=2,
            size_bytes=annual_path.stat().st_size,
            sha256="annual",
        )
        session.add(annual_file)
        session.flush()
        session.add(
            CatalogPartition(
                dataset_id=DATASET_ID,
                partition_key="2024-01-02",
                file_path=annual,
                file_id=annual_file.id,
                row_count=1,
                size_bytes=annual_path.stat().st_size,
                sha256="annual",
                collection_run_id="run-original",
            )
        )
        repaired = f"datasets/{DATASET_ID}/delta/2024/2024-01-03/repaired.parquet"
        _seed_partition(session, data_root, "2024-01-03", "REPAIRED-03", relative_path=repaired)
        session.commit()

        result = compact_year(session, data_root, DATASET_ID, 2024)
        partitions = list(
            session.scalars(
                select(CatalogPartition)
                .where(CatalogPartition.dataset_id == DATASET_ID)
                .order_by(CatalogPartition.partition_key)
            )
        )

    assert result["rows"] == 2
    assert {item.file_path for item in partitions} == {annual}
    merged = pq.read_table(data_root / annual).to_pydict()
    assert merged["symbol"] == ["ORIGINAL-02", "REPAIRED-03"]
    assert not (data_root / repaired).exists()
    assert any((data_root / "revisions" / DATASET_ID / "2024").iterdir())


def test_compaction_refuses_partition_row_count_mismatch(tmp_path: Path) -> None:
    factory = _session_factory(tmp_path)
    data_root = tmp_path / "data"
    relative = f"datasets/{DATASET_ID}/delta/2024/2024-01-02/part.parquet"
    with factory() as session:
        _seed_dataset(session)
        _seed_partition(
            session,
            data_root,
            "2024-01-02",
            "000001.SZ",
            relative_path=relative,
            catalog_rows=2,
        )
        session.commit()

        with pytest.raises(ValueError, match="分区行数与 Catalog 不一致"):
            compact_year(session, data_root, DATASET_ID, 2024)
        partition = session.scalar(select(CatalogPartition))

    assert partition is not None
    assert partition.file_path == relative
    assert (data_root / relative).is_file()
    assert not (data_root / f"datasets/{DATASET_ID}/annual/2024.parquet").exists()


def test_compaction_refuses_catalog_change_before_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory = _session_factory(tmp_path)
    data_root = tmp_path / "data"
    relative = f"datasets/{DATASET_ID}/delta/2024/2024-01-02/part.parquet"
    with factory() as session:
        _seed_dataset(session)
        _seed_partition(
            session,
            data_root,
            "2024-01-02",
            "000001.SZ",
            relative_path=relative,
        )
        session.commit()
        original_snapshot = storage._partition_snapshot
        calls = 0

        def changing_snapshot(partitions):
            nonlocal calls
            calls += 1
            snapshot = original_snapshot(partitions)
            return snapshot if calls == 1 else snapshot + (("changed",),)

        monkeypatch.setattr(storage, "_partition_snapshot", changing_snapshot)
        with pytest.raises(RuntimeError, match="Catalog 分区发生变化"):
            compact_year(session, data_root, DATASET_ID, 2024)
        partition = session.scalar(select(CatalogPartition))

    assert partition is not None
    assert partition.file_path == relative
    assert (data_root / relative).is_file()
    annual_dir = data_root / f"datasets/{DATASET_ID}/annual"
    assert not annual_dir.exists() or not list(annual_dir.iterdir())
