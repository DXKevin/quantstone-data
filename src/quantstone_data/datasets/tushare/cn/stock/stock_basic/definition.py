DATASET_ID = "tushare.cn.stock.stock_basic"
COLLECTOR_KEY = "tushare.stock_basic"
REVIEWER_KEY = "tushare.stock_basic"

# 首版按 TuShare 官方默认范围采集当前上市股票。其他状态将在通用任务参数和
# 供应商限流调度完成后开放。
DEFAULT_LIST_STATUSES = ("L",)
