# QuantStone SDK for Rust

这是 QuantStone Data HTTP API 的同步 Rust 客户端，方法语义尽量与项目中的 Python SDK
保持一致：

- `datasets` / `datasets_with_options`
- `describe`
- `coverage`
- `read`：返回带 Schema 的 Arrow `Table` 包装
- `download`：支持 Parquet/CSV，写入指定路径
- `Client` 类型别名和默认 API 地址

Rust 的 Arrow crate 不再提供 Python/PyArrow 那样的 `Table` 类型，因此 `read` 返回本 crate
的 `Table`，内部保存 `SchemaRef` 和 `RecordBatch` 列表；时间、日期、整数等类型仍由服务端
Parquet 契约保持。

## 使用

本地 crate 依赖：

```toml
[dependencies]
quantstone-sdk = { path = "../rust-sdk" }
```

```rust
use quantstone_sdk::{DownloadOptions, QuantStoneClient, ReadOptions};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let client = QuantStoneClient::new("http://127.0.0.1:8000/api/v1")?;

    for dataset in client.datasets()? {
        println!("{}", dataset["id"]);
    }

    let table = client.read(
        "tushare.cn.stock.daily",
        &ReadOptions::new()
            .start("2026-11-01")
            .end("2026-11-24")
            .filter("ts_code", "000001.SZ"),
    )?;
    println!("rows: {}", table.num_rows());

    client.download(
        "tushare.cn.stock.daily",
        "daily.parquet",
        &DownloadOptions::new()
            .start("2026-11-01")
            .end("2026-11-24")
            .filter("ts_code", "000001.SZ"),
    )?;
    Ok(())
}
```

分区数据必须提供日期范围或至少一个主键过滤条件；快照数据可以直接完整读取。错误类型
`QuantStoneError` 会保留服务端 JSON 的 `detail` 文本。
