import asyncio
import threading
import time
from pathlib import Path

import httpx

from quantstone_data.main import create_app
from quantstone_data.models import CatalogPartition, Dataset

DATASET_ID = "demo.cn.stock.daily"


def dataset_payload() -> dict:
    return {
        "id": DATASET_ID,
        "provider": "demo",
        "region": "cn",
        "instrument": "stock",
        "dataset_name": "daily",
        "market": None,
        "display_name": "测试日线",
        "description": "异步维护任务测试",
        "primary_key": ["trade_date", "symbol"],
        "time_field": "trade_date",
        "fields": [
            {
                "name": "trade_date",
                "data_type": "date",
                "nullable": False,
                "description": "交易日",
            },
            {
                "name": "symbol",
                "data_type": "string",
                "nullable": False,
                "description": "代码",
            },
        ],
    }


def test_compaction_is_background_and_queued_job_can_be_cancelled(
    tmp_path: Path,
    monkeypatch,
) -> None:
    started = threading.Event()
    release = threading.Event()

    def slow_compaction(_session, _data_root, _dataset_id, year):
        started.set()
        assert release.wait(timeout=3)
        return {
            "dataset_id": DATASET_ID,
            "year": year,
            "status": "compacted",
            "partitions": 2,
            "rows": 4,
        }

    monkeypatch.setattr("quantstone_data.maintenance.compact_year", slow_compaction)

    async def scenario() -> None:
        app = create_app(
            f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
            data_root=tmp_path / "data",
        )
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                created = await client.post("/api/v1/datasets", json=dataset_payload())
                activated = await client.post(f"/api/v1/datasets/{DATASET_ID}/activate")
                assert created.status_code == 201
                assert activated.status_code == 200
                with app.state.session_factory() as session:
                    dataset = session.get(Dataset, DATASET_ID)
                    assert dataset is not None
                    dataset.storage_policy = {
                        "logical_partition_field": "trade_date",
                        "calendar_dataset_id": "demo.cn.stock.trade_cal",
                        "layout": "yearly_with_delta",
                        "write_strategy": "replace_partition",
                        "compaction": "yearly",
                    }
                    session.commit()

                first = await client.post(f"/api/v1/datasets/{DATASET_ID}/compact?year=2024")
                assert first.status_code == 202
                assert first.json()["status"] == "queued"
                assert await asyncio.to_thread(started.wait, 2)
                running = await client.get(f"/api/v1/maintenance-jobs/{first.json()['id']}")
                assert running.json()["status"] == "running"

                second = await client.post(f"/api/v1/datasets/{DATASET_ID}/compact?year=2025")
                assert second.status_code == 202
                cancelled = await client.post(
                    f"/api/v1/maintenance-jobs/{second.json()['id']}/cancel"
                )
                assert cancelled.json()["status"] == "cancelled"

                release.set()
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    finished = await client.get(
                        f"/api/v1/maintenance-jobs/{first.json()['id']}"
                    )
                    if finished.json()["status"] == "succeeded":
                        break
                    await asyncio.sleep(0.01)
                assert finished.json()["result"]["rows"] == 4

    asyncio.run(scenario())


def test_auto_compaction_detects_years_with_delta_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_compaction(_session, _data_root, _dataset_id, year):
        return {
            "dataset_id": DATASET_ID,
            "year": year,
            "status": "compacted",
            "partitions": 1,
            "rows": 1,
        }

    monkeypatch.setattr("quantstone_data.maintenance.compact_year", fake_compaction)

    async def scenario() -> None:
        app = create_app(
            f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
            data_root=tmp_path / "data",
        )
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                assert (
                    await client.post("/api/v1/datasets", json=dataset_payload())
                ).status_code == 201
                assert (
                    await client.post(f"/api/v1/datasets/{DATASET_ID}/activate")
                ).status_code == 200
                with app.state.session_factory() as session:
                    dataset = session.get(Dataset, DATASET_ID)
                    assert dataset is not None
                    dataset.storage_policy = {
                        "logical_partition_field": "trade_date",
                        "calendar_dataset_id": "demo.cn.stock.trade_cal",
                        "layout": "yearly_with_delta",
                        "write_strategy": "replace_partition",
                        "compaction": "yearly",
                    }
                    session.add_all(
                        [
                            CatalogPartition(
                                dataset_id=DATASET_ID,
                                partition_key="2022-01-04",
                                file_path=f"datasets/{DATASET_ID}/annual/2022.parquet",
                                row_count=1,
                                size_bytes=1,
                                sha256="seed",
                                collection_run_id="seed",
                            ),
                            CatalogPartition(
                                dataset_id=DATASET_ID,
                                partition_key="2023-01-03",
                                file_path=f"datasets/{DATASET_ID}/delta/2023/2023-01-03/a.parquet",
                                row_count=1,
                                size_bytes=1,
                                sha256="seed",
                                collection_run_id="seed",
                            ),
                            CatalogPartition(
                                dataset_id=DATASET_ID,
                                partition_key="2024-01-02",
                                file_path=f"datasets/{DATASET_ID}/delta/2024/2024-01-02/a.parquet",
                                row_count=1,
                                size_bytes=1,
                                sha256="seed",
                                collection_run_id="seed",
                            ),
                        ]
                    )
                    session.commit()

                response = await client.post(f"/api/v1/datasets/{DATASET_ID}/compact-all")
                assert response.status_code == 202
                body = response.json()
                assert [job["parameters"]["year"] for job in body["jobs"]] == [2023, 2024]
                assert body["candidate_years"] == [2023, 2024]
                assert body["skipped_years"] == []

    asyncio.run(scenario())
