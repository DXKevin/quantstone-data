from datetime import date
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from baidupcs_py.baidupcs.errors import BaiduPCSError

from quantstone_data.collectors.tb_auction.auction_process import convert_csv
from quantstone_data.collectors.tb_auction.baidu_client import _transfer_shared_file
from quantstone_data.collectors.tb_auction.definition import COLLECTOR


def test_repair_reuses_monthly_initial_collector() -> None:
    assert (
        COLLECTOR.operations["auction_process_repair"].function
        is COLLECTOR.operations["auction_process_initial"].function
    )


def test_baidu_storage_error_is_marked_retryable() -> None:
    class FailingApi:
        def transfer_shared_paths(self, *_args) -> None:
            raise BaiduPCSError("存储好像出问题了，请稍候再试", error_code=4)

    source = type(
        "Source",
        (),
        {"fs_id": 1, "uk": 2, "share_id": 3, "bdstoken": "token"},
    )()

    with pytest.raises(TimeoutError, match="百度网盘临时存储异常"):
        _transfer_shared_file(FailingApi(), "/target", source, "https://example.com")


def test_convert_csv_preserves_duplicate_code_time_rows(tmp_path: Path) -> None:
    source = tmp_path / "20261124.csv"
    source.write_text(
        "股票代码,时间,匹配金额（元）,匹配量（手）,未匹配量（手）,盘口买卖\n"
        "920001.BJ,91500000,100,1,2,买盘\n"
        "920001.BJ,91500000,200,2,1,卖盘\n",
        encoding="utf-8-sig",
    )
    target = tmp_path / "result.parquet"

    assert convert_csv(source, target, date(2026, 11, 24)) == 2
    table = pq.read_table(target)
    assert table["event_seq"].to_pylist() == [1, 2]
    assert table["ts_code"].to_pylist() == ["920001.BJ", "920001.BJ"]
