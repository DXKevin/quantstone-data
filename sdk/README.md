# QuantStone SDKs

SDK 是独立项目，通过稳定的 QuantStone Data HTTP API 读取数据，不依赖服务器内部 SQLite
或 Parquet 路径。

- [Python SDK](python/)：`quantstone-sdk`，返回 PyArrow Table，包含 `read_pandas`
- [Rust SDK](rust/)：`quantstone-sdk`，返回 Arrow RecordBatch 的 `Table` 包装

两边保持相同的方法语义：`datasets`、`describe`、`coverage`、`read`、`download`，并保留
服务端 JSON 错误中的 `detail` 文本。
