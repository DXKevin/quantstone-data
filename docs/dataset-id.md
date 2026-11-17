# Dataset ID convention

## Format

```text
<provider>.<region>.<instrument>.<dataset>[.<market>]
```

All segments use lowercase ASCII characters. Compound words inside one segment use underscores.

## Segments

- `provider`: stable code for the actual data supplier or product, not its purchase or delivery channel.
- `region`: data region, such as `cn` for Chinese mainland or `hk` for Hong Kong, China.
- `instrument`: instrument type, such as `stock`, `etf`, `futures`, or `option`.
- `dataset`: supplier API name or supplier-defined dataset name.
- `market`: optional market qualifier used only when markets require distinct contracts, such as `sh` or `sz` for L2 data.

## Examples

```text
tushare.cn.stock.daily
tushare.cn.stock.stk_limit
ths.cn.stock.daily
tb_l2.cn.stock.l2_order.sh
tb_l2.cn.stock.l2_order.sz
tb_l2.cn.stock.l2_trade.sh
tb_l2.cn.stock.l2_trade.sz
```

Dataset IDs are stable identifiers. Schema changes are represented by schema versions rather than by changing the dataset ID.
