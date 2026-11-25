import io
import json
from datetime import date

import pyarrow as pa
import pyarrow.parquet as pq

from quantstone_data.sdk import QuantStoneClient


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def test_sdk_discovers_active_datasets_and_reads_typed_parquet(monkeypatch) -> None:
    table = pa.table(
        {
            "trade_date": pa.array([date(2026, 11, 24)], type=pa.date32()),
            "ts_code": ["000001.SZ"],
        }
    )
    sink = pa.BufferOutputStream()
    pq.write_table(table, sink)
    parquet = sink.getvalue().to_pybytes()
    requested: list[str] = []

    def fake_urlopen(request, timeout):
        requested.append(request.full_url)
        if request.full_url.endswith("/datasets"):
            return Response(
                json.dumps(
                    [
                        {"id": "active", "status": "active"},
                        {"id": "draft", "status": "draft"},
                    ]
                ).encode()
            )
        return Response(parquet)

    monkeypatch.setattr("quantstone_data.sdk.urlopen", fake_urlopen)
    client = QuantStoneClient("http://quantstone.local/api/v1")

    assert [item["id"] for item in client.datasets()] == ["active"]
    result = client.read(
        "tushare.cn.stock.daily",
        start="2026-11-24",
        end="2026-11-24",
        ts_code="000001.SZ",
    )

    assert result.equals(table)
    assert "start=2026-11-24" in requested[-1]
    assert "end=2026-11-24" in requested[-1]
    assert "ts_code=000001.SZ" in requested[-1]
