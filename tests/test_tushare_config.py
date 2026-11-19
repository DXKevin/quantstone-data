from pathlib import Path

import pytest

from quantstone_data.collectors.tushare_cn_stock.stock_basic import (
    DEFAULT_API_URL,
    CollectionError,
    load_api_url,
)


def test_tushare_api_url_defaults_to_official_endpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TUSHARE_API_URL", raising=False)

    assert load_api_url(tmp_path) == DEFAULT_API_URL


def test_tushare_api_url_can_come_from_environment_or_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TUSHARE_API_URL", raising=False)
    (tmp_path / ".env").write_text("TUSHARE_API_URL=http://proxy.example:32817\n")
    assert load_api_url(tmp_path) == "http://proxy.example:32817"

    monkeypatch.setenv("TUSHARE_API_URL", "https://runtime.example/api")
    assert load_api_url(tmp_path) == "https://runtime.example/api"


@pytest.mark.parametrize("value", ["ftp://example.com", "not-a-url", "https://user:pass@example.com"])
def test_tushare_api_url_rejects_unsafe_values(
    value: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TUSHARE_API_URL", value)

    with pytest.raises(CollectionError, match="TUSHARE_API_URL"):
        load_api_url(tmp_path)
