from datetime import date
from pathlib import Path

import pyarrow.parquet as pq

from quantstone_data.collectors.tb_auction.auction_process import convert_csv
from quantstone_data.collectors.tb_auction.definition import COLLECTOR


def test_repair_reuses_monthly_initial_collector() -> None:
    assert (
        COLLECTOR.operations["auction_process_repair"].function
        is COLLECTOR.operations["auction_process_initial"].function
    )


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
