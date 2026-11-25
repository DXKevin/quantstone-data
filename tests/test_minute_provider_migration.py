from pathlib import Path

from quantstone_data.database import (
    Base,
    create_session_factory,
    migrate_minute_provider_id,
    migrate_provider_ids,
)
from quantstone_data.models import (
    CatalogFile,
    CatalogPartition,
    CollectionJob,
    CollectionRun,
    Dataset,
    DatasetSchemaVersion,
)

OLD_ID = "tb_minute.cn.stock.minute_1m"
NEW_ID = "tb_sbkj2077.cn.stock.minute_1m"


def test_minute_provider_migration_keeps_catalog_and_moves_directory(tmp_path: Path) -> None:
    factory = create_session_factory(f"sqlite:///{tmp_path / 'catalog.db'}")
    engine = factory.kw["bind"]
    Base.metadata.create_all(engine)
    data_root = tmp_path / "data"
    old_file = data_root / "datasets" / OLD_ID / "2026-11-24.parquet"
    old_file.parent.mkdir(parents=True)
    old_file.write_bytes(b"parquet")

    with factory() as session:
        dataset = Dataset(
            id=OLD_ID,
            provider="tb_minute",
            region="cn",
            instrument="stock",
            dataset_name="minute_1m",
            display_name="沪深股票1分钟K",
            status="active",
            collection_bindings=[
                {
                    "purpose": "initial",
                    "collector_key": "tb_minute",
                    "operation": "minute_1m_initial",
                    "parameters": {},
                }
            ],
        )
        dataset.schemas = [DatasetSchemaVersion(version=1, primary_key="trade_date")]
        session.add(dataset)
        session.flush()
        job = CollectionJob(
            id="11111111-1111-1111-1111-111111111111",
            dataset_id=OLD_ID,
            operation="initial",
            input_method="collector",
            status="succeeded",
            collector_key="tb_minute",
            parameters={},
        )
        session.add(job)
        catalog_file = CatalogFile(
            dataset_id=OLD_ID,
            path=f"datasets/{OLD_ID}/2026-11-24.parquet",
            row_count=1,
            size_bytes=7,
            sha256="0" * 64,
        )
        session.add(catalog_file)
        session.flush()
        run = CollectionRun(
            id="22222222-2222-2222-2222-222222222222",
            job_id=job.id,
            partition_key="2026-11-24",
            status="succeeded",
            published_path=f"datasets/{OLD_ID}/2026-11-24.parquet",
        )
        session.add(run)
        session.add(
            CatalogPartition(
                dataset_id=OLD_ID,
                partition_key="2026-11-24",
                file_path=catalog_file.path,
                file_id=catalog_file.id,
                row_count=1,
                size_bytes=7,
                sha256="0" * 64,
                collection_run_id=run.id,
            )
        )
        session.commit()

    assert migrate_minute_provider_id(engine, data_root) is True
    assert migrate_provider_ids(engine, data_root) == [
        (
            "tb_lhsjk_023199.cn.stock.minute_1m",
            "tb_sbkj2077.cn.stock.minute_1m",
        )
    ]

    with factory() as session:
        assert session.get(Dataset, OLD_ID) is None
        dataset = session.get(Dataset, NEW_ID)
        assert dataset is not None
        assert dataset.provider == "tb_sbkj2077"
        assert dataset.collection_bindings[0]["collector_key"] == "tb_lhsjk_023199"
        assert session.get(CollectionJob, job.id).dataset_id == NEW_ID
        assert session.get(CollectionJob, job.id).collector_key == "tb_lhsjk_023199"
        assert session.get(CollectionRun, run.id).published_path == (
            f"datasets/{NEW_ID}/2026-11-24.parquet"
        )
        assert session.get(CatalogFile, catalog_file.id).dataset_id == NEW_ID
        partition = session.get(CatalogPartition, 1)
        assert partition is not None
        assert partition.dataset_id == NEW_ID
        assert partition.file_path == f"datasets/{NEW_ID}/2026-11-24.parquet"

    assert not old_file.exists()
    assert (data_root / "datasets" / NEW_ID / old_file.name).is_file()
