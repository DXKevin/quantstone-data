from pathlib import Path

from fastapi.testclient import TestClient

from quantstone_data.main import create_app
from quantstone_data.models import CatalogFile, CatalogPartition, CollectionJob, CollectionRun


def payload(name: str) -> dict:
    return {
        "id": f"demo.cn.stock.{name}",
        "provider": "demo",
        "region": "cn",
        "instrument": "stock",
        "dataset_name": name,
        "market": None,
        "display_name": name,
        "description": None,
        "primary_key": ["trade_date"],
        "time_field": "trade_date",
        "fields": [
            {
                "name": "trade_date",
                "data_type": "date",
                "nullable": False,
                "description": "日期",
            }
        ],
    }


def test_batch_deletion_requires_fresh_review_and_removes_records_and_files(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    app = create_app(f"sqlite:///{tmp_path / 'test.db'}", data_root=data_root)
    dataset_id = "demo.cn.stock.daily"
    job_id = "11111111-1111-1111-1111-111111111111"
    run_id = "22222222-2222-2222-2222-222222222222"
    relative = f"datasets/{dataset_id}/snapshot.parquet"

    with TestClient(app) as client:
        assert client.post("/api/v1/datasets", json=payload("daily")).status_code == 201
        target = data_root / relative
        target.parent.mkdir(parents=True)
        target.write_bytes(b"physical-data")
        (data_root / "staging" / job_id).mkdir(parents=True)
        (data_root / "staging" / job_id / "review.json").write_text("{}")
        log = data_root / "logs" / "collection" / f"{job_id}.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("log")
        with app.state.session_factory() as session:
            job = CollectionJob(
                id=job_id,
                dataset_id=dataset_id,
                operation="initial",
                input_method="collector",
                status="succeeded",
                parameters={},
            )
            session.add(job)
            session.add(
                CollectionRun(
                    id=run_id,
                    job_id=job_id,
                    partition_key="snapshot",
                    status="succeeded",
                    published_path=relative,
                    row_count=10,
                )
            )
            catalog_file = CatalogFile(
                dataset_id=dataset_id,
                path=relative,
                row_count=10,
                size_bytes=13,
                sha256="a" * 64,
            )
            session.add(catalog_file)
            session.flush()
            session.add(
                CatalogPartition(
                    dataset_id=dataset_id,
                    partition_key="snapshot",
                    file_path=relative,
                    file_id=catalog_file.id,
                    row_count=10,
                    size_bytes=13,
                    sha256="a" * 64,
                    collection_run_id=run_id,
                )
            )
            session.commit()

        review = client.post(
            "/api/v1/datasets/deletion-review", json={"dataset_ids": [dataset_id]}
        )
        assert review.status_code == 200
        reviewed = review.json()
        assert reviewed["can_delete"] is True
        assert reviewed["items"][0]["collection_jobs"] == 1
        assert reviewed["items"][0]["catalog_partitions"] == 1
        assert reviewed["items"][0]["physical_files"] == 3

        wrong = client.post(
            "/api/v1/datasets/batch-delete",
            json={
                "dataset_ids": [dataset_id],
                "review_token": reviewed["review_token"],
                "confirmation": "错误确认",
            },
        )
        assert wrong.status_code == 422

        deleted = client.post(
            "/api/v1/datasets/batch-delete",
            json={
                "dataset_ids": [dataset_id],
                "review_token": reviewed["review_token"],
                "confirmation": reviewed["confirmation_text"],
            },
        )
        assert deleted.status_code == 200
        assert deleted.json()["deleted_dataset_ids"] == [dataset_id]
        assert client.get(f"/api/v1/datasets/{dataset_id}").status_code == 404
        assert not target.exists()
        assert not (data_root / "staging" / job_id).exists()
        assert not log.exists()


def test_deletion_review_blocks_busy_jobs_and_external_calendar_dependents(
    tmp_path: Path,
) -> None:
    app = create_app(f"sqlite:///{tmp_path / 'test.db'}", data_root=tmp_path / "data")
    calendar_id = "demo.cn.stock.calendar"
    with TestClient(app) as client:
        assert client.post("/api/v1/datasets", json=payload("calendar")).status_code == 201
        dependent = payload("daily")
        dependent["storage_policy"] = {
            "logical_partition_field": "trade_date",
            "calendar_dataset_id": calendar_id,
            "layout": "daily",
            "write_strategy": "append",
            "compaction": None,
        }
        assert client.post("/api/v1/datasets", json=dependent).status_code == 201
        with app.state.session_factory() as session:
            session.add(
                CollectionJob(
                    id="33333333-3333-3333-3333-333333333333",
                    dataset_id=calendar_id,
                    operation="initial",
                    input_method="collector",
                    status="running",
                    parameters={},
                )
            )
            session.commit()

        review = client.post(
            "/api/v1/datasets/deletion-review", json={"dataset_ids": [calendar_id]}
        ).json()
        assert review["can_delete"] is False
        assert any("排队或执行中的任务" in item for item in review["blockers"])
        assert any("仍被数据集引用" in item for item in review["blockers"])
