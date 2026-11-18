from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from fastapi.testclient import TestClient

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
        session.add(
            CatalogPartition(
                dataset_id=DATASET_ID,
                partition_key=partition_key,
                file_path=relative,
                file_id=file_row.id,
                row_count=len(symbols),
                size_bytes=target.stat().st_size,
                sha256="0" * 64,
                collection_run_id="run",
            )
        )
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


def test_compaction_merges_daily_files_into_one(tmp_path: Path) -> None:
    with create_client(tmp_path) as client:
        create_dataset(client)
        write_partition(client, "2024-01-02", ["000001.SZ", "600000.SH"])
        write_partition(client, "2024-01-03", ["000001.SZ", "600000.SH"])

        compacted = client.post(f"/api/v1/datasets/{DATASET_ID}/compact?year=2024")
        assert compacted.status_code == 200, compacted.text
        assert compacted.json()["status"] == "compacted"
        assert compacted.json()["partitions"] == 2
        assert compacted.json()["rows"] == 4

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
        client.post(f"/api/v1/datasets/{DATASET_ID}/compact?year=2024")
        data_root = Path(client.app.state.data_root)
        revisions = data_root / "revisions" / DATASET_ID / "2024"

    assert any(revisions.iterdir())
