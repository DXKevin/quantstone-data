"""QuantStone Data 的 Python 量化数据读取 SDK。"""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pyarrow as pa
import pyarrow.parquet as pq


class QuantStoneError(RuntimeError):
    """服务端拒绝请求或网络访问失败。"""


class QuantStoneClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000/api/v1",
        *,
        timeout: float = 120,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def datasets(self, *, active_only: bool = True) -> list[dict[str, Any]]:
        items = self._json("/datasets")
        return [item for item in items if not active_only or item["status"] == "active"]

    def contracts(self, *, active_only: bool = True) -> list[dict[str, Any]]:
        """一次返回所有数据集的完整契约，包括字段、主键和存储策略。"""
        return self._json(
            "/datasets/contracts",
            {"active_only": str(active_only).lower()},
        )

    def describe(self, dataset_id: str) -> dict[str, Any]:
        return self._json(f"/datasets/{dataset_id}")

    def coverage(self, dataset_id: str) -> dict[str, Any]:
        return self._json(f"/datasets/{dataset_id}/coverage")

    def read(
        self,
        dataset_id: str,
        *,
        start: date | str | None = None,
        end: date | str | None = None,
        **primary_key_filters: object,
    ) -> pa.Table:
        """按日期范围和主键读取数据，保留契约中的 Arrow 类型。"""
        with NamedTemporaryFile(suffix=".parquet") as target:
            self.download(
                dataset_id,
                target.name,
                start=start,
                end=end,
                **primary_key_filters,
            )
            return pq.read_table(target.name)

    def read_pandas(
        self,
        dataset_id: str,
        *,
        start: date | str | None = None,
        end: date | str | None = None,
        **primary_key_filters: object,
    ):
        return self.read(
            dataset_id,
            start=start,
            end=end,
            **primary_key_filters,
        ).to_pandas()

    def download(
        self,
        dataset_id: str,
        target: str | Path,
        *,
        start: date | str | None = None,
        end: date | str | None = None,
        format: str = "parquet",
        **primary_key_filters: object,
    ) -> Path:
        parameters: dict[str, object] = {"format": format, **primary_key_filters}
        if start is not None:
            parameters["start"] = start.isoformat() if isinstance(start, date) else start
        if end is not None:
            parameters["end"] = end.isoformat() if isinstance(end, date) else end
        destination = Path(target)
        destination.parent.mkdir(parents=True, exist_ok=True)
        request = Request(self._url(f"/datasets/{dataset_id}/download", parameters))
        try:
            with urlopen(request, timeout=self.timeout) as response, destination.open("wb") as sink:
                shutil.copyfileobj(response, sink)
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            destination.unlink(missing_ok=True)
            raise self._error(error) from error
        return destination

    def _json(
        self, path: str, parameters: dict[str, object] | None = None
    ) -> Any:
        try:
            with urlopen(
                Request(self._url(path, parameters)), timeout=self.timeout
            ) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            raise self._error(error) from error

    def _url(self, path: str, parameters: dict[str, object] | None = None) -> str:
        url = self.base_url + path
        values = {key: str(value) for key, value in (parameters or {}).items() if value is not None}
        return f"{url}?{urlencode(values)}" if values else url

    @staticmethod
    def _error(error: Exception) -> QuantStoneError:
        if isinstance(error, HTTPError):
            try:
                detail = json.loads(error.read().decode("utf-8")).get("detail")
            except (ValueError, UnicodeDecodeError):
                detail = None
            return QuantStoneError(detail or f"QuantStone API 返回 HTTP {error.code}")
        return QuantStoneError(f"无法访问 QuantStone API：{error}")


Client = QuantStoneClient
