from ...scanner_types import ScannerDefinition, ScannerOperation

ZHONGTAI_L2_SZ = ScannerDefinition(
    key="zhongtai_l2_sz",
    name="中泰 A股 L2（深市，历史）",
    description="扫描已转换的中泰深市逐笔委托/成交 Parquet，校验后按交易日导入。",
    operations=(
        ScannerOperation(
            key="import_order",
            name="导入逐笔委托",
            description="扫描 SZ/YYYYMMDD/l2_order.parquet 并导入中泰逐笔委托数据集。",
            dataset_id="zhongtai.cn.stock.l2_order.sz",
            filename="l2_order.parquet",
        ),
        ScannerOperation(
            key="import_trade",
            name="导入逐笔成交",
            description="扫描 SZ/YYYYMMDD/l2_trade.parquet 并导入中泰逐笔成交数据集。",
            dataset_id="zhongtai.cn.stock.l2_trade.sz",
            filename="l2_trade.parquet",
        ),
    ),
)

SCANNERS = (ZHONGTAI_L2_SZ,)
