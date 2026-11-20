import time
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq
from fastapi.testclient import TestClient
from sqlalchemy import select

from quantstone_data.main import create_app
from quantstone_data.models import CatalogFile, CatalogPartition, Dataset

DATASET_ID = "demo.cn.stock.daily"
STORAGE_POLICY = {
    "logical_partition_field": "trade_date",
    "layout": "yearly_with_delta",
    "write_strategy": "replace_partition",
    "compaction": "yearly",
    "calendar_dataset_id": None,
}


def create_client(tmp_path: Path) -> TestClient:
    app = create_app(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        data_root=tmp_path / "data",
    )
    return TestClient(app)


def create_dataset(client: TestClient) -> None:
    response = client.post(
        "/api/v1/datasets",
        json={
            "id": DATASET_ID,
            "provider": "demo",
            "region": "cn",
            "instrument": "stock",
            "dataset_name": "daily",
            "market": None,
            "display_name": "测试日线",
            "description": "读取与合并测试",
            "primary_key": ["trade_date", "symbol"],
            "time_field": "trade_date",
            "fields": [
                {
                    "name": "trade_date",
                    "data_type": "date",
                    "nullable": False,
                    "description": "日期",
                },
                {
                    "name": "symbol",
                    "data_type": "string",
                    "nullable": False,
                    "description": "代码",
                },
                {
                    "name": "close",
                    "data_type": "float64",
                    "nullable": True,
                    "description": "收盘",
                },
            ],
        },
    )
    assert response.status_code == 201, response.text
    assert client.post(f"/api/v1/datasets/{DATASET_ID}/activate").status_code == 200


def wait_maintenance_job(client: TestClient, job_id: str, timeout: float = 5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/maintenance-jobs/{job_id}")
        if response.json()["status"] in {"succeeded", "failed", "cancelled"}:
            return response
        time.sleep(0.01)
    raise AssertionError(f"maintenance job {job_id} did not finish")


def write_partition(client: TestClient, partition_key: str, symbols: list[str]) -> None:
    data_root = Path(client.app.state.data_root)
    relative = f"datasets/{DATASET_ID}/delta/2024/{partition_key}/part.parquet"
    target = data_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    table = pa.table(
        {
            "trade_date": [date.fromisoformat(partition_key)] * len(symbols),
            "symbol": symbols,
            "close": [10.0 + index for index in range(len(symbols))],
        }
    )
    pq.write_table(table, target, compression="zstd")

    with client.app.state.session_factory() as session:
        dataset = session.get(Dataset, DATASET_ID)
        assert dataset is not None
        dataset.storage_policy = STORAGE_POLICY
        file_row = CatalogFile(
            dataset_id=DATASET_ID,
            path=relative,
            row_count=len(symbols),
            size_bytes=target.stat().st_size,
            sha256="0" * 64,
        )
        session.add(file_row)
        session.flush()
        partition = session.scalar(
            select(CatalogPartition).where(
                CatalogPartition.dataset_id == DATASET_ID,
                CatalogPartition.partition_key == partition_key,
            )
        )
        if partition is None:
            partition = CatalogPartition(
                dataset_id=DATASET_ID,
                partition_key=partition_key,
                collection_run_id="run",
            )
            session.add(partition)
        partition.file_path = relative
        partition.file_id = file_row.id
        partition.row_count = len(symbols)
        partition.size_bytes = target.stat().st_size
        partition.sha256 = "0" * 64
        session.commit()


def test_read_rows_opens_each_file_once(tmp_path: Path) -> None:
    with create_client(tmp_path) as client:
        create_dataset(client)
        write_partition(client, "2024-01-02", ["000001.SZ", "600000.SH"])
        write_partition(client, "2024-01-03", ["000001.SZ", "600000.SH"])

        response = client.get(
            f"/api/v1/datasets/{DATASET_ID}/rows",
            params={"start": "2024-01-01", "end": "2024-01-31"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["files_read"] == 2
    assert body["row_count"] == 4
    assert set(body["columns"]) == {"trade_date", "symbol", "close"}


def test_filtered_read_scans_matching_files_to_report_total(tmp_path: Path) -> None:
    with create_client(tmp_path) as client:
        create_dataset(client)
        write_partition(client, "2024-01-02", ["000001.SZ", "600000.SH"])
        write_partition(client, "2024-01-03", ["000001.SZ", "600000.SH"])

        response = client.get(
            f"/api/v1/datasets/{DATASET_ID}/rows",
            params={"start": "2024-01-01", "end": "2024-01-31", "limit": 1},
        )

    assert response.status_code == 200
    assert response.json()["files_read"] == 2
    assert response.json()["row_count"] == 1
    assert response.json()["matched_count"] == 4
    assert response.json()["truncated"] is True


def test_unfiltered_read_is_always_a_twenty_row_preview(tmp_path: Path) -> None:
    with create_client(tmp_path) as client:
        create_dataset(client)
        write_partition(
            client,
            "2024-01-02",
            [f"{index:06d}.SZ" for index in range(25)],
        )

        response = client.get(
            f"/api/v1/datasets/{DATASET_ID}/rows",
            params={"limit": 100_000},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["row_count"] == 20
    assert body["matched_count"] is None
    assert body["filtered"] is False
    assert body["truncated"] is False


def test_read_rows_filters_by_partial_primary_key_and_reports_truncation(
    tmp_path: Path,
) -> None:
    with create_client(tmp_path) as client:
        create_dataset(client)
        write_partition(client, "2024-01-02", ["000001.SZ", "600000.SH"])
        write_partition(client, "2024-01-03", ["000001.SZ", "600000.SH"])

        response = client.get(
            f"/api/v1/datasets/{DATASET_ID}/rows",
            params={"symbol": "000001.SZ", "limit": 1},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["row_count"] == 1
    assert body["matched_count"] == 2
    assert body["filtered"] is True
    assert body["truncated"] is True
    assert body["rows"][0]["symbol"] == "000001.SZ"


def test_read_rows_rejects_non_primary_key_filter(tmp_path: Path) -> None:
    with create_client(tmp_path) as client:
        create_dataset(client)
        write_partition(client, "2024-01-02", ["000001.SZ"])
        response = client.get(
            f"/api/v1/datasets/{DATASET_ID}/rows",
            params={"close": "10.0"},
        )

    assert response.status_code == 422
    assert "只能按主键字段筛选" in response.json()["detail"]


def test_download_exports_all_filtered_rows_as_csv_or_parquet(tmp_path: Path) -> None:
    with create_client(tmp_path) as client:
        create_dataset(client)
        write_partition(client, "2024-01-02", ["000001.SZ", "600000.SH"])
        write_partition(client, "2024-01-03", ["000001.SZ", "600000.SH"])

        csv_response = client.get(
            f"/api/v1/datasets/{DATASET_ID}/download",
            params={"symbol": "000001.SZ", "format": "csv"},
        )
        parquet_response = client.get(
            f"/api/v1/datasets/{DATASET_ID}/download",
            params={"symbol": "000001.SZ", "format": "parquet"},
        )
        unfiltered_response = client.get(
            f"/api/v1/datasets/{DATASET_ID}/download",
            params={"format": "csv"},
        )

    assert csv_response.status_code == 200
    assert csv_response.headers["x-row-count"] == "2"
    csv_table = pacsv.read_csv(pa.BufferReader(csv_response.content))
    assert csv_table.num_rows == 2
    assert set(csv_table["symbol"].to_pylist()) == {"000001.SZ"}

    assert parquet_response.status_code == 200
    assert parquet_response.headers["x-row-count"] == "2"
    parquet_table = pq.read_table(pa.BufferReader(parquet_response.content))
    assert parquet_table.num_rows == 2
    assert set(parquet_table["symbol"].to_pylist()) == {"000001.SZ"}

    assert unfiltered_response.status_code == 422
    assert "至少填写一个主键" in unfiltered_response.json()["detail"]


def test_read_rows_fails_when_catalog_file_is_missing(tmp_path: Path) -> None:
    with create_client(tmp_path) as client:
        create_dataset(client)
        write_partition(client, "2024-01-02", ["000001.SZ"])
        with client.app.state.session_factory() as session:
            partition = session.scalar(select(CatalogPartition))
            assert partition is not None
            missing_path = partition.file_path
        (Path(client.app.state.data_root) / missing_path).unlink()

        response = client.get(f"/api/v1/datasets/{DATASET_ID}/rows")

    assert response.status_code == 409
    assert "Catalog 文件缺失，读取已中止" in response.json()["detail"]
    assert missing_path in response.json()["detail"]


def test_compaction_merges_daily_files_into_one(tmp_path: Path) -> None:
    with create_client(tmp_path) as client:
        create_dataset(client)
        write_partition(client, "2024-01-02", ["000001.SZ", "600000.SH"])
        write_partition(client, "2024-01-03", ["000001.SZ", "600000.SH"])

        submitted = client.post(f"/api/v1/datasets/{DATASET_ID}/compact?year=2024")
        compacted = wait_maintenance_job(client, submitted.json()["id"])
        assert submitted.status_code == 202, submitted.text
        assert compacted.json()["status"] == "succeeded"
        assert compacted.json()["result"]["status"] == "compacted"
        assert compacted.json()["result"]["partitions"] == 2
        assert compacted.json()["result"]["rows"] == 4

        rows = client.get(
            f"/api/v1/datasets/{DATASET_ID}/rows",
            params={"start": "2024-01-01", "end": "2024-01-31"},
        )

    assert rows.status_code == 200
    body = rows.json()
    assert body["files_read"] == 1
    assert body["row_count"] == 4
    assert body["rows"][0]["symbol"] == "000001.SZ"


def test_compaction_moves_replaced_files_to_revisions(tmp_path: Path) -> None:
    with create_client(tmp_path) as client:
        create_dataset(client)
        write_partition(client, "2024-01-02", ["000001.SZ"])
        submitted = client.post(f"/api/v1/datasets/{DATASET_ID}/compact?year=2024")
        wait_maintenance_job(client, submitted.json()["id"])
        data_root = Path(client.app.state.data_root)
        revisions = data_root / "revisions" / DATASET_ID / "2024"
        delta = data_root / "datasets" / DATASET_ID / "delta"

    assert any(revisions.iterdir())
    assert not delta.exists()


def test_recompaction_preserves_annual_rows_and_replaces_repaired_day(tmp_path: Path) -> None:
    with create_client(tmp_path) as client:
        create_dataset(client)
        write_partition(client, "2024-01-02", ["ORIGINAL-02"])
        write_partition(client, "2024-01-03", ["ORIGINAL-03"])
        first_submitted = client.post(f"/api/v1/datasets/{DATASET_ID}/compact?year=2024")
        first = wait_maintenance_job(client, first_submitted.json()["id"])
        assert first.json()["status"] == "succeeded"

        write_partition(client, "2024-01-03", ["REPAIRED-03"])
        second_submitted = client.post(f"/api/v1/datasets/{DATASET_ID}/compact?year=2024")
        second = wait_maintenance_job(client, second_submitted.json()["id"])
        rows = client.get(
            f"/api/v1/datasets/{DATASET_ID}/rows",
            params={"start": "2024-01-01", "end": "2024-01-31", "limit": 10},
        )

    assert second.status_code == 200, second.text
    assert second.json()["status"] == "succeeded"
    assert second.json()["result"]["status"] == "compacted"
    assert second.json()["result"]["source_files"] == 2
    assert second.json()["result"]["rows"] == 2
    assert rows.status_code == 200
    symbols = {item["trade_date"]: item["symbol"] for item in rows.json()["rows"]}
    assert symbols == {
        "2024-01-02": "ORIGINAL-02",
        "2024-01-03": "REPAIRED-03",
    }
