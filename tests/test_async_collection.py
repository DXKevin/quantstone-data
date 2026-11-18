import asyncio
import threading
import time
from pathlib import Path

import httpx

from quantstone_data.main import create_app


def trade_calendar_payload() -> dict:
    return {
        "id": "tushare.cn.stock.trade_cal",
        "provider": "tushare",
        "region": "cn",
        "instrument": "stock",
        "dataset_name": "trade_cal",
        "market": None,
        "display_name": "A股交易日历",
        "description": "异步执行测试",
        "collection_bindings": [
            {
                "purpose": "initial",
                "collector_key": "tushare_cn_stock",
                "operation": "trade_cal_initial",
            }
        ],
        "storage_policy": {
            "logical_partition_field": None,
            "calendar_dataset_id": None,
            "layout": "snapshot",
            "write_strategy": "replace_snapshot",
            "compaction": None,
        },
        "primary_key": ["exchange", "cal_date"],
        "time_field": "cal_date",
        "fields": [
            {
                "name": "exchange",
                "data_type": "string",
                "nullable": False,
                "description": "交易所",
            },
            {
                "name": "cal_date",
                "data_type": "date",
                "nullable": False,
                "description": "日历日期",
            },
            {
                "name": "is_open",
                "data_type": "int32",
                "nullable": False,
                "description": "是否交易",
            },
            {
                "name": "pretrade_date",
                "data_type": "date",
                "nullable": True,
                "description": "上一交易日",
            },
        ],
    }


def test_execute_returns_before_background_collection_finishes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    started = threading.Event()
    release = threading.Event()

    def slow_trade_cal(_token, start_date, _end_date, _fields):
        started.set()
        assert release.wait(timeout=3)
        return [
            {
                "exchange": "SSE",
                "cal_date": start_date.strftime("%Y%m%d"),
                "is_open": 1,
                "pretrade_date": None,
            }
        ]

    monkeypatch.setattr(
        "quantstone_data.collectors.tushare_cn_stock.trade_cal._call_trade_cal",
        slow_trade_cal,
    )
    monkeypatch.setenv("TUSHARE_TOKEN", "test-token")

    async def scenario() -> None:
        app = create_app(
            f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
            data_root=tmp_path / "data",
        )
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                dataset = await client.post(
                    "/api/v1/datasets",
                    json=trade_calendar_payload(),
                )
                activated = await client.post(
                    "/api/v1/datasets/tushare.cn.stock.trade_cal/activate"
                )
                assert dataset.status_code == 201
                assert activated.status_code == 200
                created = await client.post(
                    "/api/v1/collection-jobs",
                    json={
                        "dataset_id": "tushare.cn.stock.trade_cal",
                        "operation": "initial",
                        "input_method": "collector",
                        "parameters": {
                            "start_date": "2026-01-01",
                            "end_date": "2026-12-31",
                        },
                    },
                )
                job_id = created.json()["id"]
                submitted = await client.post(f"/api/v1/collection-jobs/{job_id}/execute")
                assert submitted.status_code == 202
                assert submitted.json()["status"] == "queued"
                assert await asyncio.to_thread(started.wait, 2)
                running = await client.get(f"/api/v1/collection-jobs/{job_id}")
                assert running.json()["status"] == "running"
                release.set()
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    finished = await client.get(f"/api/v1/collection-jobs/{job_id}")
                    if finished.json()["status"] == "succeeded":
                        break
                    await asyncio.sleep(0.01)
                assert finished.json()["status"] == "succeeded"

    asyncio.run(scenario())
