from pathlib import Path

from fastapi.testclient import TestClient

from quantstone_data.main import create_app
from quantstone_data.reviewer_registry import REVIEWERS


def test_collector_registry_describes_operations_and_outputs(tmp_path: Path) -> None:
    app = create_app(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}", data_root=tmp_path / "data"
    )
    with TestClient(app) as client:
        response = client.get("/api/v1/collectors")

    assert response.status_code == 200
    collector = response.json()[0]
    assert collector["key"] == "tushare_cn_stock"
    operation = next(
        item for item in collector["operations"] if item["key"] == "stock_basic_initial"
    )
    assert operation["key"] == "stock_basic_initial"
    assert operation["purpose"] == "initial"
    assert operation["datasets"] == ["tushare.cn.stock.stock_basic"]
    assert operation["joint"] is False
    daily_incremental = next(
        item for item in collector["operations"] if item["key"] == "daily_incremental"
    )
    assert daily_incremental["parameters"] == [
        {
            "name": "end_date",
            "data_type": "date",
            "required": False,
            "description": "可选的更新截止日期，默认当天",
        }
    ]
    stock_st_initial = next(
        item for item in collector["operations"] if item["key"] == "stock_st_initial"
    )
    assert stock_st_initial["datasets"] == ["tushare.cn.stock.stock_st"]


def test_reviewer_registry_uses_dataset_ids() -> None:
    assert set(REVIEWERS) == {
        "tushare.cn.index.index_basic",
        "tushare.cn.index.index_daily",
        "tushare.cn.stock.adj_factor",
        "tushare.cn.stock.daily",
        "tushare.cn.stock.namechange",
        "tushare.cn.stock.stock_basic",
        "tushare.cn.stock.stock_st",
        "tushare.cn.stock.trade_cal",
        "tb_lhsjk.cn.stock.auction_process",
        "tb_sbkj2077.cn.stock.minute_1m",
        "tb_xxlpd.cn.stock.l2_order.sz",
        "tb_xxlpd.cn.stock.l2_trade.sz",
        "zhongtai.cn.stock.l2_order.sz",
        "zhongtai.cn.stock.l2_trade.sz",
    }

def test_scanner_registry_lists_wind_and_zhongtai(tmp_path: Path) -> None:
    app = create_app(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}", data_root=tmp_path / "data"
    )
    with TestClient(app) as client:
        response = client.get("/api/v1/scanners")

    assert response.status_code == 200
    scanners = {item["key"]: item for item in response.json()}
    assert set(scanners) == {"wind_l2_sz", "zhongtai_l2_sz"}
    assert {
        item["key"] for item in scanners["zhongtai_l2_sz"]["operations"]
    } == {"import_order", "import_trade"}
    assert {
        item["dataset_id"] for item in scanners["zhongtai_l2_sz"]["operations"]
    } == {"zhongtai.cn.stock.l2_order.sz", "zhongtai.cn.stock.l2_trade.sz"}


def test_legacy_tushare_collector_key_is_migrated(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    data_root = tmp_path / "data"
    payload = {
        "id": "tushare.cn.stock.stock_basic",
        "provider": "tushare",
        "region": "cn",
        "instrument": "stock",
        "dataset_name": "stock_basic",
        "market": None,
        "display_name": "A股股票信息",
        "description": "旧采集器绑定迁移测试",
        "collection_bindings": [
            {
                "purpose": "initial",
                "collector_key": "tushare",
                "operation": "stock_list_initial",
            },
            {
                "purpose": "incremental",
                "collector_key": "tushare",
                "operation": "stock_list_incremental",
            },
        ],
        "primary_key": ["ts_code"],
        "time_field": None,
        "fields": [
            {
                "name": "ts_code",
                "data_type": "string",
                "nullable": False,
                "description": "TS代码",
            }
        ],
    }

    with TestClient(create_app(database_url, data_root=data_root)) as client:
        assert client.post("/api/v1/datasets", json=payload).status_code == 201

    with TestClient(create_app(database_url, data_root=data_root)) as restarted:
        dataset = restarted.get("/api/v1/datasets/tushare.cn.stock.stock_basic")

    assert dataset.status_code == 200
    assert {item["collector_key"] for item in dataset.json()["collection_bindings"]} == {
        "tushare_cn_stock"
    }
    assert {item["operation"] for item in dataset.json()["collection_bindings"]} == {
        "stock_basic_initial",
        "stock_basic_incremental",
    }
    assert dataset.json()["storage_policy"] == {
        "logical_partition_field": None,
        "calendar_dataset_id": None,
        "allow_empty_partitions": False,
        "layout": "snapshot",
        "write_strategy": "replace_snapshot",
        "compaction": None,
    }


def dataset_payload() -> dict:
    return {
        "id": "tb_l2.cn.stock.l2_order.sh",
        "provider": "tb_l2",
        "region": "cn",
        "instrument": "stock",
        "dataset_name": "l2_order",
        "market": "sh",
        "display_name": "上海股票逐笔委托",
        "description": "供应商交付的上海市场 L2 逐笔委托数据",
        "primary_key": ["trade_date", "order_no"],
        "time_field": "event_time",
        "fields": [
            {
                "name": "trade_date",
                "data_type": "date",
                "nullable": False,
                "description": "交易日期",
            },
            {
                "name": "event_time",
                "data_type": "timestamp",
                "nullable": False,
                "description": "委托时间",
            },
            {
                "name": "order_no",
                "data_type": "int64",
                "nullable": False,
                "description": "委托序号",
            },
        ],
    }


def test_dataset_lifecycle(tmp_path: Path) -> None:
    app = create_app(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}", data_root=tmp_path / "data"
    )
    with TestClient(app) as client:
        created = client.post("/api/v1/datasets", json=dataset_payload())
        assert created.status_code == 201
        assert created.json()["status"] == "draft"
        assert created.json()["schema"]["primary_key"] == ["trade_date", "order_no"]

        listed = client.get("/api/v1/datasets")
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()] == [dataset_payload()["id"]]

        activated = client.post(f"/api/v1/datasets/{dataset_payload()['id']}/activate")
        assert activated.status_code == 200
        assert activated.json()["status"] == "active"

        deleting = client.delete(f"/api/v1/datasets/{dataset_payload()['id']}")
        assert deleting.status_code == 409


def test_dataset_id_must_match_segments(tmp_path: Path) -> None:
    app = create_app(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}", data_root=tmp_path / "data"
    )
    payload = dataset_payload()
    payload["id"] = "wrong.id"

    with TestClient(app) as client:
        response = client.post("/api/v1/datasets", json=payload)

    assert response.status_code == 422
    assert "dataset id must be" in response.text


def test_duplicate_dataset_is_rejected(tmp_path: Path) -> None:
    app = create_app(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}", data_root=tmp_path / "data"
    )
    with TestClient(app) as client:
        assert client.post("/api/v1/datasets", json=dataset_payload()).status_code == 201
        response = client.post("/api/v1/datasets", json=dataset_payload())

    assert response.status_code == 409


def test_draft_dataset_can_be_edited_but_direct_delete_requires_review(tmp_path: Path) -> None:
    app = create_app(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}", data_root=tmp_path / "data"
    )
    with TestClient(app) as client:
        created = client.post("/api/v1/datasets", json=dataset_payload())
        payload = {
            "display_name": "上海股票逐笔委托（修订）",
            "description": "修订后的说明",
            "primary_key": ["trade_date", "order_no"],
            "time_field": "event_time",
            "fields": dataset_payload()["fields"],
        }

        updated = client.put(f"/api/v1/datasets/{created.json()['id']}", json=payload)
        assert updated.status_code == 200
        assert updated.json()["display_name"] == payload["display_name"]
        assert updated.json()["description"] == payload["description"]

        deleted = client.delete(f"/api/v1/datasets/{created.json()['id']}")
        assert deleted.status_code == 409
        assert "批量删除审查" in deleted.json()["detail"]
        assert client.get(f"/api/v1/datasets/{created.json()['id']}").status_code == 200


def test_active_dataset_cannot_be_edited(tmp_path: Path) -> None:
    app = create_app(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}", data_root=tmp_path / "data"
    )
    with TestClient(app) as client:
        created = client.post("/api/v1/datasets", json=dataset_payload()).json()
        client.post(f"/api/v1/datasets/{created['id']}/activate")
        payload = {
            "display_name": "不应保存",
            "description": None,
            "primary_key": ["trade_date", "order_no"],
            "time_field": "event_time",
            "fields": dataset_payload()["fields"],
        }

        response = client.put(f"/api/v1/datasets/{created['id']}", json=payload)

    assert response.status_code == 409


def test_active_dataset_metadata_can_be_edited(tmp_path: Path) -> None:
    app = create_app(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}", data_root=tmp_path / "data"
    )
    with TestClient(app) as client:
        created = client.post("/api/v1/datasets", json=dataset_payload()).json()
        client.post(f"/api/v1/datasets/{created['id']}/activate")

        response = client.patch(
            f"/api/v1/datasets/{created['id']}",
            json={
                "display_name": "上海逐笔委托",
                "description": "启用后更新的说明",
            },
        )

    assert response.status_code == 200
    assert response.json()["display_name"] == "上海逐笔委托"
    assert response.json()["description"] == "启用后更新的说明"
    assert response.json()["status"] == "active"
    assert response.json()["current_schema_version"] == 1
    assert response.json()["schema"]["fields"] == created["schema"]["fields"]
