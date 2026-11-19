from pathlib import Path

from fastapi.testclient import TestClient

from quantstone_data import collection as collection_module
from quantstone_data.main import create_app
from quantstone_data.models import CollectionJob

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
        "description": "任务生命周期测试",
        "primary_key": ["trade_date", "symbol"],
        "time_field": "trade_date",
        "fields": [
            {"name": "trade_date", "data_type": "date", "nullable": False, "description": "交易日"},
            {"name": "symbol", "data_type": "string", "nullable": False, "description": "代码"},
        ],
    }


def create_client(tmp_path: Path) -> TestClient:
    app = create_app(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        data_root=tmp_path / "data",
    )
    return TestClient(app)


def create_import_job(client: TestClient) -> str:
    assert client.post("/api/v1/datasets", json=dataset_payload()).status_code == 201
    assert client.post(f"/api/v1/datasets/{DATASET_ID}/activate").status_code == 200
    response = client.post(
        "/api/v1/collection-jobs",
        json={
            "dataset_id": DATASET_ID,
            "operation": "initial",
            "input_method": "file_import",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_created_job_reports_progress(tmp_path: Path) -> None:
    with create_client(tmp_path) as client:
        job_id = create_import_job(client)
        response = client.get(f"/api/v1/collection-jobs/{job_id}/progress")

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == job_id
    assert body["status"] == "awaiting_file"
    assert body["succeeded"] == 0
    assert body["failed"] == 0
    assert body["expected_total"] is None
    assert body["percent"] is None


def test_job_can_be_cancelled_before_running(tmp_path: Path) -> None:
    with create_client(tmp_path) as client:
        job_id = create_import_job(client)
        response = client.post(f"/api/v1/collection-jobs/{job_id}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_running_job_cancel_registers_request(tmp_path: Path) -> None:
    with create_client(tmp_path) as client:
        job_id = create_import_job(client)
        collection_module._RUNNING_JOBS.add(job_id)
        try:
            response = client.post(f"/api/v1/collection-jobs/{job_id}/cancel")
            assert job_id in collection_module._CANCEL_REQUESTS
        finally:
            collection_module._RUNNING_JOBS.discard(job_id)
            collection_module._CANCEL_REQUESTS.discard(job_id)

    assert response.status_code == 200
    assert response.json()["status"] == "cancelling"


def test_finished_job_cannot_be_cancelled(tmp_path: Path) -> None:
    with create_client(tmp_path) as client:
        job_id = create_import_job(client)
        assert client.post(f"/api/v1/collection-jobs/{job_id}/cancel").status_code == 200
        second = client.post(f"/api/v1/collection-jobs/{job_id}/cancel")

    assert second.status_code == 409


def test_job_record_can_be_deleted(tmp_path: Path) -> None:
    with create_client(tmp_path) as client:
        job_id = create_import_job(client)
        deleted = client.delete(f"/api/v1/collection-jobs/{job_id}")
        missing = client.get(f"/api/v1/collection-jobs/{job_id}")

    assert deleted.status_code == 204
    assert missing.status_code == 404


def test_startup_marks_interrupted_job_as_failed(tmp_path: Path) -> None:
    with create_client(tmp_path) as client:
        job_id = create_import_job(client)
        with client.app.state.session_factory() as session:
            job = session.get(CollectionJob, job_id)
            assert job is not None
            job.status = "running"
            session.commit()

    with create_client(tmp_path) as restarted:
        response = restarted.get(f"/api/v1/collection-jobs/{job_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert "应用重启" in response.json()["error"]
