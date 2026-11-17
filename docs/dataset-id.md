# 数据集 ID 命名规范

## 格式

```text
<provider>.<region>.<instrument>.<dataset>[.<market>]
```

所有层级均使用小写 ASCII 字符。同一层级中的复合名称使用下划线连接。

## 各层级含义

- `provider`：实际数据供应商或数据产品的稳定代号，不使用购买渠道或交付渠道作为代号。
- `region`：数据区域，例如 `cn` 表示中国内地，`hk` 表示中国香港。
- `instrument`：品种，例如 `stock`、`etf`、`futures` 或 `option`。
- `dataset`：供应商 API 名称或供应商定义的数据集名称。
- `market`：可选的市场限定符。只有不同市场需要使用不同数据契约时才添加，例如 L2 数据中的 `sh` 或 `sz`。

## 示例

```text
tushare.cn.stock.daily
tushare.cn.stock.stk_limit
ths.cn.stock.daily
tb_l2.cn.stock.l2_order.sh
tb_l2.cn.stock.l2_order.sz
tb_l2.cn.stock.l2_trade.sh
tb_l2.cn.stock.l2_trade.sz
```

数据集 ID 是稳定标识符。数据结构发生变化时应增加 Schema 版本，而不是修改数据集 ID。
