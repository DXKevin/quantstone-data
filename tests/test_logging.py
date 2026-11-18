import json
from pathlib import Path

from quantstone_data.logging_config import configure_logging, log_event


def test_structured_logs_are_routed_and_secrets_are_redacted(tmp_path: Path) -> None:
    logger = configure_logging(tmp_path)
    log_event(
        "collector_called",
        job_id="job-123",
        dataset_id="tushare.cn.stock.trade_cal",
        token="must-not-appear",
        parameters={"api_token": "also-secret", "end_date": "2027-12-31"},
    )
    for handler in logger.handlers:
        handler.flush()

    application = (tmp_path / "logs" / "application.log").read_text(encoding="utf-8")
    job_log = (tmp_path / "logs" / "collection" / "job-123.log").read_text(
        encoding="utf-8"
    )
    record = json.loads(application.strip())

    assert record["event"] == "collector_called"
    assert record["job_id"] == "job-123"
    assert record["token"] == "***"
    assert record["parameters"]["api_token"] == "***"
    assert record["parameters"]["end_date"] == "2027-12-31"
    assert "must-not-appear" not in application
    assert json.loads(job_log)["dataset_id"] == "tushare.cn.stock.trade_cal"
