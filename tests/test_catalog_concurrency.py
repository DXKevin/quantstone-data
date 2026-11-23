import os
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

from sqlalchemy import text

from quantstone_data.database import create_session_factory
from quantstone_data.publishing import service
from quantstone_data.publishing.path_resolver import resolve_partition_target


def test_sqlite_connections_use_wal_and_wait_for_writers(tmp_path) -> None:
    factory = create_session_factory(f"sqlite:///{tmp_path / 'catalog.db'}")

    with factory() as session:
        assert session.execute(text("PRAGMA journal_mode")).scalar_one() == "wal"
        assert session.execute(text("PRAGMA busy_timeout")).scalar_one() == 60_000
        assert session.execute(text("PRAGMA synchronous")).scalar_one() == 1
        assert session.execute(text("PRAGMA foreign_keys")).scalar_one() == 1


def test_publish_failure_restores_artifact_to_staging(tmp_path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    artifact = data_root / "staging" / "run.parquet"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"parquet")
    run = SimpleNamespace(id="run-id")
    policy = {"layout": "daily"}
    target = resolve_partition_target(
        data_root, "demo.cn.stock.tick", policy, "2026-11-20", run.id
    )

    def fail_after_move(*_args, **_kwargs):
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(artifact, target)
        raise RuntimeError("database is locked")

    monkeypatch.setattr(service, "publish_partition", fail_after_move)
    session = MagicMock()

    try:
        service.publish_partition_transaction(
            session,
            data_root=data_root,
            dataset_id="demo.cn.stock.tick",
            storage_policy=policy,
            partition_key="2026-11-20",
            artifact_path=artifact,
            row_count=1,
            run=run,
        )
    except RuntimeError as error:
        assert str(error) == "database is locked"
    else:
        raise AssertionError("发布失败应向调用方抛出异常")

    session.rollback.assert_called_once_with()
    assert artifact.read_bytes() == b"parquet"
    assert not target.exists()


def test_catalog_publish_transactions_are_serialized(tmp_path, monkeypatch) -> None:
    active = 0
    maximum_active = 0
    state_lock = threading.Lock()
    barrier = threading.Barrier(2)

    def slow_publish(*_args, **_kwargs):
        nonlocal active, maximum_active
        with state_lock:
            active += 1
            maximum_active = max(maximum_active, active)
        time.sleep(0.05)
        with state_lock:
            active -= 1
        return SimpleNamespace()

    monkeypatch.setattr(service, "publish_partition", slow_publish)

    def publish(index: int) -> None:
        barrier.wait()
        service.publish_partition_transaction(
            MagicMock(),
            data_root=tmp_path,
            dataset_id="demo.cn.stock.tick",
            storage_policy={"layout": "daily"},
            partition_key=f"2026-11-{index + 1:02d}",
            artifact_path=tmp_path / f"{index}.parquet",
            row_count=1,
            run=SimpleNamespace(id=f"run-{index}"),
        )

    threads = [threading.Thread(target=publish, args=(index,)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert maximum_active == 1
