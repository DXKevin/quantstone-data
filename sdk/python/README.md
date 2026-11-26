# QuantStone SDK for Python

独立 Python 客户端项目，通过 QuantStone Data HTTP API 读取数据，不依赖服务器安装包。

```bash
python -m pip install -e sdk/python
```

```python
from quantstone_sdk import QuantStoneClient

qs = QuantStoneClient("http://127.0.0.1:8000/api/v1")
print(qs.datasets())
print(qs.coverage("tushare.cn.stock.daily"))

table = qs.read(
    "tushare.cn.stock.daily",
    start="2026-11-01",
    end="2026-11-24",
    ts_code="000001.SZ",
)
```

支持 `datasets`、`contracts`、`describe`、`coverage`、`read`、`read_pandas` 和 `download`。分区数据必须提供
日期范围或至少一个主键条件；快照数据允许完整读取。
