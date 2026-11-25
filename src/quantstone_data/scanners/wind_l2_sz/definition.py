from ...scanner_types import ScannerDefinition, ScannerOperation

WIND_L2_SZ = ScannerDefinition(
    key="wind_l2_sz",
    name="Wind A股 L2（深市）",
    description="扫描已转换的深市逐笔委托/成交 Parquet，校验后按交易日导入。",
    operations=(
        ScannerOperation(
            key="import_order",
            name="导入逐笔委托",
            description="扫描 SZ/YYYYMMDD/l2_order.parquet 并导入逐笔委托数据集。",
            dataset_id="tb_xxlpd.cn.stock.l2_order.sz",
            filename="l2_order.parquet",
        ),
        ScannerOperation(
            key="import_trade",
            name="导入逐笔成交",
            description="扫描 SZ/YYYYMMDD/l2_trade.parquet 并导入逐笔成交数据集。",
            dataset_id="tb_xxlpd.cn.stock.l2_trade.sz",
            filename="l2_trade.parquet",
        ),
    ),
)

SCANNERS = (WIND_L2_SZ,)
