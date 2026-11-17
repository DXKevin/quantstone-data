import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from quantstone_data.main import create_app


def dataset_payload(dataset_id: str = "demo.cn.stock.daily") -> dict:
    provider, region, instrument, dataset_name = dataset_id.split(".")
    return {
        "id": dataset_id,
        "provider": provider,
        "region": region,
        "instrument": instrument,
        "dataset_name": dataset_name,
        "market": None,
        "display_name": "测试日线",
        "description": "采集任务测试使用",
        "primary_key": ["trade_date", "symbol"],
        "time_field": "trade_date",
        "fields": [
            {
                "name": "trade_date",
                "data_type": "date",
                "nullable": False,
                "description": "交易日期",
            },
            {
                "name": "symbol",
                "data_type": "string",
                "nullable": False,
                "description": "证券代码",
            },
        ],
    }


def create_client(tmp_path: Path) -> TestClient:
    app = create_app(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        data_root=tmp_path / "data",
    )
    return TestClient(app)


def create_dataset(client: TestClient, *, activate: bool = True) -> str:
    dataset_id = dataset_payload()["id"]
    response = client.post("/api/v1/datasets", json=dataset_payload())
    assert response.status_code == 201
    if activate:
        assert client.post(f"/api/v1/datasets/{dataset_id}/activate").status_code == 200
    return dataset_id


def test_only_active_datasets_can_create_collection_jobs(tmp_path: Path) -> None:
    with create_client(tmp_path) as client:
        dataset_id = create_dataset(client, activate=False)
        response = client.post(
            "/api/v1/collection-jobs",
            json={
                "dataset_id": dataset_id,
                "operation": "incremental",
                "input_method": "collector",
                "collector_key": "mock",
            },
        )

    assert response.status_code == 409


def test_initial_collection_requires_date_range(tmp_path: Path) -> None:
    with create_client(tmp_path) as client:
        dataset_id = create_dataset(client)
        response = client.post(
            "/api/v1/collection-jobs",
            json={
                "dataset_id": dataset_id,
                "operation": "initial",
                "input_method": "collector",
                "collector_key": "mock",
            },
        )

    assert response.status_code == 422
    assert "requires a date range" in response.text


def test_incremental_collector_job_can_be_created_without_dates(tmp_path: Path) -> None:
    with create_client(tmp_path) as client:
        dataset_id = create_dataset(client)
        response = client.post(
            "/api/v1/collection-jobs",
            json={
                "dataset_id": dataset_id,
                "operation": "incremental",
                "input_method": "collector",
                "collector_key": "mock",
            },
        )

        assert response.status_code == 201
        assert response.json()["status"] == "created"
        listed = client.get(f"/api/v1/collection-jobs?dataset_id={dataset_id}")

    assert listed.status_code == 200
    assert [job["id"] for job in listed.json()] == [response.json()["id"]]


def test_manual_file_import_is_staged_with_integrity_metadata(tmp_path: Path) -> None:
    content = b"trade_date,symbol\n2026-11-17,600000.SH\n"
    with create_client(tmp_path) as client:
        dataset_id = create_dataset(client)
        created = client.post(
            "/api/v1/collection-jobs",
            json={
                "dataset_id": dataset_id,
                "operation": "initial",
                "input_method": "file_import",
                "start_date": "2026-11-17",
                "end_date": "2026-11-17",
            },
        )
        assert created.status_code == 201
        assert created.json()["status"] == "awaiting_file"

        staged = client.post(
            f"/api/v1/collection-jobs/{created.json()['id']}/file",
            files={"file": ("daily.csv", content, "text/csv")},
        )
        assert staged.status_code == 200
        body = staged.json()
        assert body["status"] == "staged"
        assert body["source_file_name"] == "daily.csv"
        assert body["source_size_bytes"] == len(content)
        assert body["source_sha256"] == hashlib.sha256(content).hexdigest()

        staged_file = tmp_path / "data" / body["staged_path"]
        assert staged_file.read_bytes() == content

        duplicate = client.post(
            f"/api/v1/collection-jobs/{created.json()['id']}/file",
            files={"file": ("daily.csv", content, "text/csv")},
        )

    assert duplicate.status_code == 409
