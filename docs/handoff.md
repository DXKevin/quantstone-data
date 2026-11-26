# Agent 工作交接

本文档是 Codex 与 DeepSeek Harness 在同一个项目目录中串行接力的当前状态记录。

长期架构与项目原则见 [项目架构、设计原则与开发约定](architecture-and-decisions.md)。本文件只保留接手下一轮工作所需的信息，避免重复记录完整架构。

## 交接规则

- 开始工作前先阅读 `AGENTS.md` 和本文件；
- 接手时检查 Git 状态和最近提交；
- 一次只推进一个边界明确的任务；
- 工作完成后更新本文件中的当前状态；
- 长期有效的新决定同步写入架构文档；
- 完成测试、提交并推送后才算正常交接；
- 不保留无说明的未提交修改。

## 2026-11-26 当前交接摘要（优先阅读）

- 分支 `main`，工作区干净，最新提交见 `git log -1`；本次交接提交已推送；
- 前后端已启动：后端 `0.0.0.0:8000`，前端 `0.0.0.0:5173`，局域网地址
  `http://192.168.1.57:5173`；当前仅 THS 成分股 repair 任务
  `32c96e15-c9b6-47b1-8221-baeeed3a7e39` 正在运行；
- 当前 22 个数据集均为 active；`tb_lqsj_ths.cn.index.sector_categories` 已发布
  1 个 snapshot、1,676 行；`tb_lqsj_ths.cn.index.daily` 已完成 2007-08-01 至
  2026-11-25 采集，4,695 个分区、3,203,076 行；
- `tb_lqsj_ths.cn.index.constituent_stocks` 正在从 2014-01-02 补全，2019-06-19
  起的供应商无后缀代码已按代码段补 `.SH/.SZ/.BJ`；2014-01-02 至 2019-06-18 已发布；
- Catalog 实际为 **约 42,895 个分区、198,088,711,162 行**；
  数据根 `/home/hhd_data` 已用 2.0 TB、可用 5.3 TB；系统盘 `/home` 仅余约 163 GB；
- `tb_xxlpd.cn.stock.l2_order.sz` / `l2_trade.sz` 各有 **174 个分区**，覆盖
  `2026-03-11` 至 `2026-11-23`：order 23,855,129,427 行、trade 21,055,637,280 行；
  两组已改为联合首次/增量操作；
- 中泰深市 L2 两个数据集各有 **2,213 个分区**，覆盖 `2017-01-03` 至 `2026-03-23`：
  order 80,424,316,422 行、trade 69,267,477,633 行；只保留股票、仅上午
  `09:15–11:30`，`manual` + `is_historical=true`；
- 所有 L2 日期分区键已统一为 ISO `YYYY-MM-DD`，目录扫描仍识别 `YYYYMMDD` 文件夹；
- `tushare.cn.index.index_basic` 已发布 1 个 snapshot、10,733 行；成功任务
  `e8c8de96-9ac9-4bfd-8555-edd6c87c005d`；旧失败任务
  `ace1fc71-0161-4265-8da1-537e9c6bf74c` 是修复前记录，保留即可，不要重试覆盖；
- `tushare.cn.index.index_daily` 已完成重新首次采集和年度合并，当前 4,100 个分区、
  49,706 行，覆盖 2010-01-04 至 2026-11-23；不要再重复采集；
- `tushare.cn.etf.etf_basic` 已完成首次和增量快照，当前 1 个 snapshot、3,266 行；
  分别请求 L/D/P 三种状态并按 ts_code 去重，保留 `.OF` 和字母后缀代码；
- `tushare.cn.etf.fund_daily` 已覆盖 2015-01-05 至 2026-11-24，当前 **2,889 个分区、
  2,855,165 行**；按交易日采集接口返回的全部场内基金，未按 ETF 清单反向过滤；
- `tushare.cn.etf.fund_adj` 已完成 2015-01-05 至 2026-11-24 的续采，
  当前 **2,889 个分区、3,044,532 行**；`08705889` 已成功结束；
- `tushare.cn.stock.stk_limit` 已完成 2007-01-04 至 2026-11-24 全量采集：
  **4,833 个分区、16,166,543 行**；
- `tushare.cn.stock.suspend_d` 主键为 `ts_code + trade_date + suspend_type`，
  `suspend_timing` 不做格式强校验；已完成 2010-01-04 至 2026-11-25 采集：
  **4,102 个分区、463,419 行**，任务 `3465b41d` 已成功；
- `tb_sbkj2077.cn.stock.minute_1m`（沪深股票 1 分钟，不复权，日分区）已完成 2015-01-05 至
  2026-11-24 采集，共 **2,889 个分区、2,718,527,482 行**；
- `tb_lhsjk.cn.stock.auction_process` 已采集 2020-01-02 至 2026-11-24，共
  **1,670 个分区、481,295,947 行**；
- Wind L2 旧单输出任务留下的 `2026-11-20/2026-11-23` trade 缺口已由联合修复任务
  `bf8a1c1c` 补齐，压缩包和解压缓存已清理；Wind 后续缓存目录统一为 `cache/wind_l2`；
- 中泰真实数据已完成转换和导入；临时脚本仍保留在 `/home/quantadmin/l2_migration/`，
  不在 Git 仓库内；
- 独立 Python SDK 位于 `sdk/python/`，包名 `quantstone-sdk`，导入 `quantstone_sdk`；
  支持 `datasets/describe/coverage/read/read_pandas/download`；
- Rust SDK 位于 `sdk/rust/`：同步 HTTP 客户端，支持 `datasets/describe/coverage/read/download`，
  `read` 返回 Arrow RecordBatch 的 `Table` 包装；不提供 Pandas 等价方法；
- 分钟数据供应商标识已迁移为 `tb_sbkj2077`，正式数据 2,889 个分区、2,718,527,482 行，
  旧路径为 0；Wind L2 ID 改为 `tb_xxlpd`，集合竞价 ID 改为 `tb_lhsjk`。

尚未完成：

- **多存储根（dataset 多卷分片）尚未实现**。用户已确认方向，且明确“程序不知道物理硬盘，
  只知道多个 dataset 路径”：
  - 应建 `storage_roots`（id/name/path/enabled/priority）；
  - `catalog_files` 增 `root_id` + 相对路径；
  - 现有数据默认归第一个 root，新分区可写第二个 root；
  - 读取/发布/删除/合并/扫描统一解析 `root + relative_path`；
  - 不复制 SQLite，不按磁盘建多个数据库；物理盘/LVM 只属于部署层；
  - 尚未确定两个根路径和分片策略，需先和用户确认再动代码。

接手注意：

- 修改/重启后端前先确认没有 `running`/`queued`/`cancelling` 的采集、导入或合并任务；
- `imports/wind_l2_test` 的 20261118 测试转换输出仍在，是目录导入测试源；正式 Catalog
  已发布到 `datasets/`，不依赖该测试源；
- L2 审核器检查 Schema、非空、行数和分区日期，不做上亿行主键全量唯一性校验；
- Catalog 全量前端页已按要求回退，当前只有按数据集的接口和概览热力图；
- 服务端 Python 测试 150 项通过、`ruff` 和前端构建通过；Python SDK 测试 1 项、Rust `cargo test` 5 项通过。

## 2026-11-26 — DeepSeek Harness（THS 成分股补后缀）

问题：

- 全量成分股 repair 在 2019-06-19 审核失败，供应商返回无后缀 `688001`；
- 审核器要求 `688001.SH`。

修复：

- 采集器按代码段补齐后缀（6/9→SH、0/1/2/3→SZ、4/8/920→BJ）；
- 从 2019-06-19 创建 repair 任务 `32c96e15`，已越过失败日；
- 2014-01-02 至 2019-06-18 的成功分区保留；
- 完整测试 150 项通过。

## 2026-11-26 — DeepSeek Harness（批量契约接口）

完成：

- 新增 `GET /api/v1/datasets/contracts?active_only=true`，一次返回完整数据集契约；
- 默认仅 active，`active_only=false` 可获取全部；
- Python SDK 新增 `contracts(active_only=True)`，Rust SDK 新增
  `contracts()` / `contracts_with_options()`；
- 真实接口返回 22 个 active 数据集，首个契约包含 8 个字段；
- 服务端测试 146 项、Python SDK 1 项、Rust 5 项通过。

## 2026-11-26 — DeepSeek Harness（SDK 独立项目）

完成：

- Python SDK 从服务端包拆到 `sdk/python/`，独立包名 `quantstone-sdk`，导入路径
  `quantstone_sdk`；服务端 `quantstone_data` 不再导出客户端；
- 保留原 Python SDK 的 `datasets/describe/coverage/read/read_pandas/download` 行为；
- Rust SDK 移到 `sdk/rust/`，保持原有方法语义；
- 新增 `sdk/README.md` 说明两个独立 SDK；
- 验证：Python SDK 1 项通过、Rust 4 项通过、服务端 146 项通过，
  `ruff`/`cargo clippy`/前端构建通过。

安装：

```bash
python -m pip install -e sdk/python
```

## 2026-11-26 — DeepSeek Harness（读取下载修复与通配符）

问题：

- 快照数据集 `download(...)` 无筛选时返回 422 `Malformed filters`；
- 根因是导出路径把空 Parquet filter 列表传给 PyArrow；
- `ts_code=000001.*` 等通配符没有匹配语义。

修复：

- 导出路径改为空 filter 传 `None`，快照无筛选可完整下载；
- 读取和下载对字符串主键支持 `*`/`?` 通配符，先做分区裁剪，再按字符串匹配；
- 实测 stock_basic：无筛选下载 5,925 行；`ts_code=000001.*` 返回 1 行；
- 服务端测试 148 项、Python SDK 1 项、Rust 5 项通过。

## 2026-11-26 — DeepSeek Harness（Rust SDK）

完成：

- 新增独立 crate `sdk/rust/`，包名 `quantstone-sdk`；
- 同步 HTTP 客户端：`datasets`、`datasets_with_options`、`describe`、`coverage`、`read`、
  `download`，并提供 `Client` 别名和默认 API 地址；
- `ReadOptions` / `DownloadOptions` 支持日期范围、主键过滤和 Parquet/CSV；
- `read` 返回自定义 `Table`，内部保存 Arrow Schema 和 RecordBatch 列表，类型由服务端
  Parquet 契约保持；不提供 Rust/Pandas 的 `read_pandas`；
- 错误类型保留服务端 `detail` 文本；
- `cargo test` 4 项通过，`cargo clippy --all-targets -- -D warnings` 通过；
- 真实 API 示例 `examples/read_daily.rs` 成功读取 A股日线并得到 17 行、11 列。

## 2026-11-26 — DeepSeek Harness（THS 日线代码去重）

问题：

- THS 日线 2026-03-02 接口 `total=2247`，标准化后只有 2,232 个唯一代码；
- 15 个指数同时返回 `700012R.TI` 和 `TI.700012R` 两种写法，数据完全相同；
- 原逻辑用标准化后的唯一代码数对比 `total`，因此误判分页不完整。

修复：

- 完整性改为按分页原始行数校验；发布前按标准化 `ths_code` 去重；
- 日线分页固定 1,000 条，避免供应商大页截断；
- 保留单日最多 3 次重试；
- 从 2026-03-02 创建续采任务 `c59af52b`，已验证越过失败日；
- 完整测试 147 项通过，`ruff` 和前端构建通过。

## 2026-11-26 — DeepSeek Harness（THS 日线分页重试）

问题：

- THS 日线续采任务 `9c1d6583` 在 2026-03-02 失败：
  “期望 2247 条，实际 2232 条”；
- 直接复查接口已能返回完整 2247 条，属于供应商瞬时分页缺失。

修复：

- THS 日线单日采集增加最多 3 次完整重试，间隔 2/4 秒；
- 仍不完整才失败，不静默发布少数据；
- 从 2026-03-02 创建续采任务 `efa38818`，目标 2026-11-25；
- 完整测试 147 项通过，`ruff` 和前端构建通过。

## 2026-11-26 — DeepSeek Harness（数据根清理）

- 删除已完成导入的原始 Wind L2 源 `imports/wind_l2`（约 175G）、
  `imports/wind_l2_test`、`imports/zhongtai_l2`；
- 删除旧分钟缓存 `cache/minute_1m` 和全部旧 staging，保留运行中的 THS
  任务目录 `staging/9c1d6583-2fe9-4d65-b7f3-cb80d00884d6`；
- 保留正式 `datasets/`、`imports/jobs` 审计清单、`revisions/` 历史副本和日志；
- 数据根占用从约 2.2 TB 降至 2.0 TB，Catalog 文件路径全部仍位于 `datasets/`。

## 2026-11-26 — Codex（THS 板块分类全流程）

完成：

- 新增 `tb_lqsj_ths.cn.index.sector_categories` 快照契约，主键 `index_code`，字段为
  `index_code/name/count/exchange/list_date/type/code`；
- 新增 `tb_lqsj_ths_index` 采集器，使用 `X-API-Key`、按 `page=0..14` 完整分页，并校验
  各页 `total` 稳定及最终记录数完整；
- 新增专用审核器，校验字段、非空、主键、板块类型、`.TI` 后缀和非负成分数量；
- 采集器凭证改为各供应商独立加载：TuShare 读取 `TUSHARE_TOKEN`，新供应商读取
  `TB_LQSJ_THS_API_KEY`，文件采集器不再被迫依赖 TuShare 凭证；
- API Key 已写入本机未提交 `.env`，未进入 Git；
- 真实接口验证成功：2 页、1,676 行、7 种板块类型，审核通过；其中 4 行 `count` 为空，
  契约已按真实数据设为可空。

正式结果：

- 数据集已从预置创建并启用；首次任务 `745a887e-7a2a-48ed-94b3-26be84c9d4c4`
  成功，Catalog 为 1 个 snapshot、1,676 行、33,378 bytes、无缺失文件；
- 新增单元测试 3 项通过，真实采集和专用审核器通过，`ruff check .` 与前端构建通过；
- 当前环境的 FastAPI `TestClient` 在 lifespan 启动前阻塞，完整 pytest 无法结束；版本为
  FastAPI 0.165.0 / Starlette 1.10.0 / httpx 0.28.1，并提示应安装 `httpx2`。这是测试运行环境
  的兼容问题，未影响临时 Uvicorn 上的正式 API 全流程；不要把中断的 pytest 误判为业务测试失败。

## 2026-11-26 — Codex（THS 板块日线全流程）

完成：

- 新增并启用 `tb_lqsj_ths.cn.index.daily`，主键 `ths_code + trade_date`，按交易日日分区，
  使用 `yearly_with_delta` 并支持首次、增量和日期范围修复；
- 契约保留接口 12 个字段：`ths_code/trade_date/open/high/low/close/pre_close/avg_price/`
  `change/pct_change/vol/turnover_rate`；
- 采集器按单日请求、循环分页并核对供应商 `total`，不使用当前板块分类数量判断历史完整性；
- 修正供应商特殊指数代码格式漂移：`TI.700012R` 技术标准化为 `700012R.TI`，避免同一指数
  的历史时间序列被拆分；
- 正式首次任务 `89dba06e-519f-460b-a24f-4ed4dd2bf37a` 成功，发布 2026-11-25：
  1 个分区、1,871 行、93,221 bytes、无缺失文件；
- 真实抽样确认单日板块数随历史变化：2010-01-04 为 68 条、2025-08-13 为 1,523 条，
  2026-11-25 为 1,871 条；不能拿当前分类快照强制校验历史覆盖。
- 本轮采集器测试 44 项通过，`ruff check .` 与前端构建通过；完整 pytest 仍受上一节记录的
  `TestClient` 环境兼容问题影响。
- 已启动全历史 repair 任务 `f69e193d-218b-40fa-b507-0a464d56cfdc`；启动检查为 running，
  最终在 2021-02-02 审核停止。续采任务 `f30920b3-94f1-4587-b8d6-2200a34200cb` 又在
  2021-02-19 遇到 `864027.TI` 的另一处 OHLC 原始异常，证明逐条例外不可维护。THS 日线
  审核已取消 OHLC 包含关系的阻断，保留供应商原值；其他 Schema、主键、分区日期、代码与
  非负数值检查不变。新任务 `9c1d6583-2fe9-4d65-b7f3-cb80d00884d6` 已确认跨过失败日并
  持续回补。
- 当前分类快照 1,676 个代码，已采集日线为 2,225 个不同代码，其中 621 个不在分类快照；
  `864027.TI` 仅见于 2021-01-04 至 2021-07-01，但另有不在分类快照的代码持续返回到
  2026-11-25。用户确认暂时保持现状：日线保留接口全部代码，不使用当前分类快照过滤；未来
  如需纯板块日线，应取得带历史有效期和类型的基础资料后另建数据集。

## 2026-11-26 — DeepSeek Harness（suspend_timing 格式放宽）

问题：

- suspend_d repair 在 2021-01-12 审核失败，`suspend_timing` 出现
  `09:46:07-09:56:07` 的带秒格式，原审核器要求 `HH:MM-HH:MM`。

修复：

- 取消 `suspend_timing` 时间格式强校验，仅保留字段、非空、主键和
  `suspend_type` 域校验；
- 从失败日 2021-01-12 创建 repair 任务 `3465b41d`，目标 2026-11-25；
- 2021-01-11 之前的成功分区保留；
- 完整测试 138 项通过。

## 2026-11-26 — DeepSeek Harness（suspend_timing 多区间）

问题：

- suspend_d repair 在 2012-08-08 审核失败，`suspend_timing` 为
  `09:43-10:13,11:08-14:55`，原审核器只允许单个区间。

修复：

- 审核器放宽为逗号/分号分隔的多个时间段；
- 从失败日 2012-08-08 创建 repair 任务 `ec6ebe4b`，目标 2026-11-25；
- 2012-08-07 之前的成功分区保留；
- 完整测试 138 项通过。

## 2026-11-26 — DeepSeek Harness（suspend_d 主键修复）

问题：

- `suspend_d` repair 在 2011-05-23 审核失败，主键重复；
- 同日同股票 `600572.SH` 同时存在 `S` 和 `R` 两条记录，原主键
  `ts_code + trade_date` 不成立。

修复：

- 契约和已有 Schema 主键改为 `ts_code + trade_date + suspend_type`；
- 审核器按新主键校验；成功分区保留；
- 新增启动迁移，把已有 `dataset_schema_versions.primary_key` 原地更新；
- 后续修复 `suspend_timing` 多区间和带秒格式，最终续采任务 `3465b41d` 成功，
  覆盖 2010-01-04 至 2026-11-25；
- 完整测试 138 项通过，`ruff` 和前端构建通过。

## 2026-11-25 — DeepSeek Harness（股票涨跌停与停复牌）

完成：

- 新增并启用 `tushare.cn.stock.stk_limit`，按交易日日分区，
  主键 `ts_code + trade_date`，支持年度合并；
- 新增并启用 `tushare.cn.stock.suspend_d`，按交易日日分区，
  主键 `ts_code + trade_date`，支持年度合并；
- 新增首次、增量、repair 操作和专用审核器；
- 真实首次采集 2026-11-24：stk_limit 5,658 行、suspend_d 11 行；
- 先前失败的 fund_adj 续采任务 `08705889` 已完成 2015-01-05 至 2026-11-24，
  当前 2,889 个分区、3,044,532 行；
- 完整测试 138 项通过，`ruff` 和前端构建通过。

## 2026-11-25 — DeepSeek Harness（ETF 涨跌停与 502 恢复）

完成：

- `tushare.cn.etf.etf_limit` 已激活并完成 2026-11-24 首次采集，发布 2,244 行；
- 基金复权因子的两次 repair 均在 502 上游错误处停止；成功分区保留，
  最新一次停在 2021-12-13；
- 代理恢复后从 2021-12-14 创建续采任务 `08705889-497f-bc2a-bf036e811f31`；
- 为 `fund_adj` / `etf_limit` 增加更长重试：6 次、30 秒起、最大 300 秒退避。

当前：

- 续采任务 `08705889` 已成功结束；fund_adj 覆盖 2015-01-05 至 2026-11-24，
  2,889 个分区、3,044,532 行。

## 2026-11-25 — DeepSeek Harness（TuShare ETF 涨跌停价格）

完成：

- 新增 `tushare.cn.etf.etf_limit` 契约、预置、采集器操作和审核器；
- 字段 `ts_code/trade_date/pre_close/up_limit/down_limit/asset_type/exchange`，
  主键 `ts_code + trade_date`，按交易日日分区，支持年度合并；
- 新增 `etf_limit_initial` / `etf_limit_incremental` / `etf_limit_repair`；
- 测试 134 项通过，`ruff` 和前端构建通过。

## 2026-11-25 — DeepSeek Harness（TuShare 基金复权因子）

完成：

- 新增并启用 `tushare.cn.etf.fund_adj`，按交易日日分区，主键
  `ts_code + trade_date`，支持年度合并；
- 契约字段为 `ts_code/trade_date/adj_factor`；
- 新增 `fund_adj_initial` / `fund_adj_incremental` / `fund_adj_repair`，
  按交易日采集并使用 `offset`/`limit=2000` 分页；
- 新增专用审核器，校验字段、非空、主键、分区日期和因子为正；
- 真实首次和 repair 任务均成功，2026-11-24 发布 2,241 行；
- 完整测试 132 项通过，`ruff` 和前端构建通过。

## 2026-11-25 — DeepSeek Harness（TuShare 场内基金日线）

完成：

- 新增并启用 `tushare.cn.etf.fund_daily`，按交易日日分区，主键
  `ts_code + trade_date`，支持年度合并；
- 新增 `tushare_cn_etf` 的 `fund_daily_initial` / `fund_daily_incremental` /
  `fund_daily_repair` 操作，按交易日请求一次 `fund_daily`；
- 契约字段为 `ts_code/trade_date/open/high/low/close/pre_close/change/pct_chg/vol/amount`；
- 保存接口返回的全部场内基金；接口虽名为 ETF 日线，也会返回封闭式基金等其他场内基金，
  不按 `etf_basic` 反向过滤；
- 新增专用审核器，检查字段、非空、主键和 OHLC 关系；
- 真实首次和 repair 任务均成功；当前已覆盖 2015-01-05 至 2026-11-24，
  2,889 个分区、2,855,165 行；
- 完整测试 130 项通过，`ruff` 和前端构建通过。

## 2026-11-25 — DeepSeek Harness（TuShare ETF 基础信息）

完成：

- 新增并启用 `tushare.cn.etf.etf_basic`（原名 `tushare.cn.etf.basic` 不符合 API 命名），
  snapshot 存储，`ts_code` 主键；
- 契约包含 `ts_code/csname/extname/cname/index_code/index_name/setup_date/list_date/
  list_status/exchange/mgr_name/custod_name/mgt_fee/etf_type`；
- 新增独立 `tushare_cn_etf` 采集器，分别请求 L/D/P 三种状态并按 `ts_code` 去重；
- 新增专用审核器，校验必填字段、非空、主键唯一、代码/状态/交易所域；
- 保留供应商返回的 `.OF` 代码和 `159908J.SZ` 一类字母后缀，不在基础信息层过滤；
- 真实首次和增量任务均成功，发布 3,266 行、113 KB；
- 完整测试 128 项通过，`ruff` 和前端构建通过。

## 2026-11-25 — DeepSeek Harness（供应商 ID 重命名）

完成：

- 集合竞价：`tb.cn.stock.auction_process` → `tb_lhsjk.cn.stock.auction_process`；
- 分钟：`tb_lhsjk_023199.cn.stock.minute_1m` → `tb_sbkj2077.cn.stock.minute_1m`；
- Wind L2：`wind.cn.stock.l2_order.sz` / `l2_trade.sz` →
  `tb_xxlpd.cn.stock.l2_order.sz` / `l2_trade.sz`；
- 同步 provider、预置契约、采集器/审核器注册、扫描器 dataset ID 和测试；
- 启动迁移原地重命名 `datasets/` 和 `revisions/` 目录，更新 Registry、Schema、Catalog、
  采集/维护/导入任务和文件路径，不复制 Parquet；
- 采集器/扫描器内部 key 同步改为中性名称：`l2_sz_baidu`、`auction_baidu`、`minute_baidu`；同步迁移任务、导入任务和数据集绑定。

验证：

- 126 项测试通过，`ruff` 和前端构建通过；
- 真实 Catalog 迁移后 22,105 个分区、197,827,329,699 行保留；
- 旧 `datasets/` 目录为 0，新目录文件完整。

## 2026-11-24 — DeepSeek Harness（分钟数据集重建）

- 用户要求从 2015 年开始采集；已严格删除并重建
  `tb_sbkj2077.cn.stock.minute_1m`；
- 删除前 2 个测试分区（2000-06-09、2026-11-23）和任务记录已清理；
- 当前 active、0 个 Catalog 分区、0 个任务；本地分钟缓存已删除；
- 首次采集应选择 `2015-01-01` 至 `2026-11-23`；全量尚未启动。

## 2026-11-24 — DeepSeek Harness（沪深 1 分钟数据）

完成：

- 新增 `tb_sbkj2077.cn.stock.minute_1m` 契约并启用：沪深股票、1 分钟、不复权，
  不保存名称，日分区，不做年度合并；
- 首次采集按年读取 `1分钟_按年汇总/YYYY_1min.zip`，在本地构建按日缓存后逐日发布；
  增量读取 `每日更新/1分钟/YYYY-MM/YYYYMMDD_1min.zip`；
- 使用 DuckDB 处理年度 5,000+ 股票 CSV；百度分享只转存当前一个 zip 到 `年数据`/`日数据`，转存文件保留，
  本地下载/解压缓存发布后清理；
- 新增审核器，检查 Schema、分区日期、bar_time 范围和 key 非空；
- 真实首次测试 `2000-06-09` 成功：189,908 行、1 个 Catalog 分区；
- 完整测试 116 项通过，`ruff` 和前端构建通过。

下一步：

- 运行 2000–2026 全量首次采集，再验证每日增量；
- 全量完成后可评估是否需要把分钟数据分卷存储。

## 2026-11-24 — DeepSeek Harness（index_daily 删除重建）

- 用户确认后严格删除 `tushare.cn.index.index_daily`，清除了 287 个 Catalog 分区、
  物理文件、任务和日志；
- 已从预置契约重新创建并启用，当前 0 分区、0 任务；
- initial 现在按年批量；repair 仍按增量单日；不再需要从旧失败任务恢复。

## 2026-11-24 — DeepSeek Harness（index_daily 额度失败修复）

问题：

- 用户运行 `index_daily` 历史首次采集 `ced17ae5` 到 2011-02-11 中断，错误为
  “请求额度暂不可用，请稍后重试”；
- `raise_api_error` 未识别该中文额度文本，抛成普通 `CollectionError`，绕过重试；
- 同时 50 次/分钟对该账号偏高。

修复：

- `RATE_LIMIT_KEYWORDS` 增加“请求额度”“额度暂不可用”；
- `index_daily` 限流降到 20 次/分钟，重试改为 6 次、15 秒起、最大 120 秒；
- 增加中文额度错误可重试测试；
- 已验证：中文额度消息现在抛 `RateLimitExceeded`，定向测试 18 项通过，完整 110 项通过。

恢复方式：

- 已成功分区保留（2010-01-04 至 2011-02-10，共 265 个），不要删除；
- 修复后建议从 `2011-02-11` 起创建 **repair** 任务补跑，而不是直接重试旧首次任务；
  直接重试会从 2010-01-01 重新请求，浪费额度。

## 2026-11-24 — DeepSeek Harness（指数日线）

完成：

- 新增预置数据集 `tushare.cn.index.index_daily`，包含 13 个主要指数，主键
  `ts_code + trade_date`，日分区、`yearly_with_delta`、年度合并；
- 新增 `index_daily_initial` / `index_daily_incremental` 采集操作；
- 首次按年拉取（非 CSI 一批 + CSI 逐个，每年 3 次），进程内按年缓存后逐日写分区；
  增量和 repair 都按交易日调用一次；清单中
  `start_date` 之前的指数自动跳过，不参与当天校验；到达 `start_date` 后缺失才失败；
- 指数清单在 `src/quantstone_data/collectors/tushare_cn_stock/index_daily_universe.json`，
  包含 `ts_code/name/start_date`；`start_date` 已按 `index_daily` 实际最早交易日探测
  （000001 从 1990-12-19、932000 从 2013-12-31、000688 从 2019-12-31 等），不是直接
  采用 `index_basic` 的基日/发布日；新增指数只改 JSON；
- 新增 `tushare.cn.index.index_daily` 审核器，检查 Schema、主键、分区日期和 OHLC；
- 真实接口测试：`2026-11-23` 返回并发布 13 行；
- 定向测试 19 项通过；完整套件 112 项通过，`ruff check .` 和前端构建通过；
- 新增显式 `index_daily_repair` 操作和 repair 绑定；repair 复用增量单日路径，首次才按年批量。

下一步：

- 运行完整历史的 `index_daily` 首次采集；
- 2026 年数据可执行年度合并，验证 `annual/2026.parquet`。

## 2026-11-24 — Codex（Wind 深市 L2 联合更新）

完成：

- 将 Wind 深市 L2 从委托/成交各自首次、增量的 4 个单输出操作，改为首次、增量 2 个联合操作；
- 两个 Wind 数据集绑定同一联合操作，从任一数据集创建任务都会同时输出并发布委托和成交；
- 每个交易日只下载、解压一次，随后连续转换两个 Parquet；两个输出分别使用自己的数据契约审核；
- 联合任务执行入口使用采集器操作作为资源锁，避免从两个输出数据集同时提交同一联合采集；
- 创建联合任务前会确认所有输出数据集都已创建、启用并配置存储策略；
- 任务列表显示“联合更新 · 2 个数据集”及两个数据集 ID，采集能力页显示联合更新；
- SQLite 启动迁移会把现有 Wind 数据集的旧单输出绑定切换到新联合操作。

验证：

- Wind 转换与联合输出测试：4 项通过；
- `ruff check .`：通过；
- `npm run build`：通过；
- 包含 API TestClient 的定向测试在当前 Codex PTY 中执行 15 秒无输出后中止；这是已有 lifespan
  挂起问题，本轮没有得到完整 pytest 结果。

下一步：

- 服务重启后确认采集能力页显示 2 个联合操作；首次真实下载建议先选择一个交易日，核对两个
  Catalog 分区都由同一任务发布。

## 2026-11-24 — Codex（TuShare index_basic）

完成：

- 新增预置数据集 `tushare.cn.index.index_basic`，使用 snapshot 存储和 `ts_code` 主键；
- 契约包含 TuShare 官方 13 个输出字段，`base_date`、`list_date`、`exp_date` 存为 date；
- 首次和增量采集均遍历 `CSI/SSE/SZSE/SW` 四个市场，按 `ts_code` 去重后
  生成完整快照，避免默认参数只返回 SSE；
- 新增 `index_basic_initial` / `index_basic_incremental` 操作和专用审核器；
- 用户要求最后自行运行采集任务，因此只创建并启用数据集，不代为创建或执行采集任务。
- 按当前官方市场表修正为 `CSI/SSE/SZSE/SW` 四个市场；此前列出的
  `MSCI/CICC/OTH` 在真实接口中均返回 0 行，现已停止无效请求。

验证：

- 首次真实任务暴露官方“必选”字段仍有空值，已将 `base_date/base_point/list_date` 调整为可空；
- CSI 首批返回恰好达到 8,000 行上限，已加入 offset 分页，避免静默截断；
- 使用当前真实 TuShare 代理完成临时采集验证：10,733 行、`ts_code` 全部唯一，市场值为
  `CSI/SSE/SW/SZSE`，三个放宽字段分别有 24/26/22 个空值；临时文件已删除，未发布数据；
- index_basic 定向测试 3 项通过；
- `ruff check .`：通过。

## 2026-11-20 历史交接摘要（已被顶部 2026-11-24 摘要覆盖）

- 当前工作 Agent：DeepSeek Harness 结束，等待 Codex 接手
- 工作分支：`main`，工作区干净，最新提交见 `git log -1`（交接提交已推送）
- 代码目录：`/home/quantadmin/project/quantstone-data`
- 数据根目录：`/home/hhd_data/quantstone-data`
- SQLite：`var/quantstone-data.db`（Wind 委托全量导入后至少新增 170 个 Catalog 分区）
- 服务：`./scripts/quantstone-dev.sh status|restart|logs`，后端 8000，前端 5173
- 当前 7 个数据集均为 active：TuShare 3 个、Wind L2 2 个、中泰 L2 2 个。

本轮完成：

- Wind 深市 L2 `tb_xxlpd.cn.stock.l2_order.sz` / `l2_trade.sz` 已建契约并启用；
- Wind 20260311–20261119 共 171 天已完成 order 转换和 Catalog 导入，合计
  23,478,980,276 行；trade 已转换 171 天，但 Catalog 目前只导入 20261118 一天、104,411,003 行；
- 正式目录导入功能已实现：`ImportJob`、扫描器、清单、审核、执行、取消 API，前端“采集 → 目录导入”；
- Wind 扫描器 `l2_sz_baidu`、中泰扫描器 `zhongtai_l2_sz` 均已注册，各有 order/trade 两个操作；
- 中泰深市 L2 `zhongtai.cn.stock.l2_order.sz` / `l2_trade.sz` 已建契约并启用，字段名/类型/主键与 Wind 对齐；
- 中泰设置为 `manual` + `is_historical=true`，不进日更完成率和覆盖热力图；
- 数据集契约新增 `is_historical`，前端可勾选，热力图和日更统计会排除历史数据集；
- 中泰来源已确认为 `stock_day_a_l2/SZ`，历史约 2017-01 至 2026-03；只迁移股票前缀
  `000/001/002/003/300/301/302`，源数据只覆盖上午 09:15–11:30；
- 中泰 trade 的 `side` 直接比较 `BidApplSeqNum` / `OfferApplSeqNum`，不需要 join order；
- 临时脚本不在 Git 仓库内：
  - `/home/quantadmin/l2_migration/convert_wind_l2.py`
  - `/home/quantadmin/l2_migration/convert_zhongtai_l2.py`
  - 同目录两个 README。

尚未完成：

- Wind trade 其余 170 天尚未导入；转换目录已存在 171 个 order 和 171 个 trade Parquet；
- 中泰转换脚本只做了语法和内存小样本检查，没有跑真实数据；中泰扫描器也尚未导入真实数据；
- 中泰源只有上午数据，且包含 ETF/基金/可转债/B 股/REITs；转换器只保留股票，20260323 股票上午输出应为
  order 85,917,403 行、trade 76,321,044 行；
- **多存储根（dataset 多卷分片）尚未实现**。用户已确认方向，且明确“程序不知道物理硬盘，只知道多个 dataset 路径”：
  - 应建 `storage_roots`（id/name/path/enabled/priority）；
  - `catalog_files` 增 `root_id` + 相对路径；
  - 现有数据默认归第一个 root，新分区可写第二个 root；
  - 读取/发布/删除/合并/扫描统一解析 `root + relative_path`；
  - 不复制 SQLite，不按磁盘建多个数据库；物理盘/LVM 只属于部署层；
  - 尚未确定两个根路径和分片策略，需先和用户确认再动代码。

接手注意：

- 修改/重启后端前先确认没有 `running`/`queued` 的采集、导入或合并任务；
- 不要删除 `imports/wind_l2_test` 中的 20261118 测试转换输出；它是目录导入的测试源。
  Catalog 已发布到正式 `datasets/` 目录，不依赖该测试源；
- L2 审核器检查 Schema、非空、行数和分区日期，不做上亿行主键全量唯一性校验；
- Catalog 全量前端页已按要求回退，当前只有按数据集的接口和概览热力图；
- 本轮验证：`pytest -q` 76 项通过、`ruff check .` 通过、`npm run build` 通过。

### 2026-11-20 — Codex（统一 L2 日期分区键）

完成：

- 定位 Wind L2 已导入但覆盖热力图全缺失的原因：目录导入保存 `YYYYMMDD`，热力图按
  ISO `YYYY-MM-DD` 查找；
- Wind/中泰目录仍扫描 `YYYYMMDD` 文件夹，但新 Manifest、Catalog 和 Collection Run 统一使用
  `YYYY-MM-DD`；
- 增加 SQLite 启动迁移，将四个 Wind/中泰 L2 数据集已有的紧凑日期分区键转换为 ISO 日期；
- 迁移只更新 Catalog 与运行记录，不移动或重写正式 Parquet 文件。

验证：

- 目录导入、旧分区迁移和概览定向测试：6 项通过；
- `pytest -q`：77 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过。
- 服务重启后的真实数据库迁移：Wind 委托 171 个分区为 `2026-03-11` 至 `2026-11-19`，
  Catalog 与 Collection Run 均无残留 8 位日期键；
- 覆盖率 API 最近 30 个交易日返回完整 29、缺失 0、当天待更新 1。

下一步：无。

### 2026-11-20 — Codex（清理合并后的空 delta 目录）

完成：

- 定位 daily 年度合并只移动 delta Parquet、未删除原日期目录的问题；
- 年度合并与分区替换删除旧文件后，逐级清理空日期、年份和 delta 目录；
- 清理严格限制在当前数据集目录内，遇到非空目录立即停止，不影响仍被 Catalog 引用的文件；
- 当前 daily `delta` 下曾检测到 2,880 个空目录，另有 7 个来自失败或取消任务的无引用
  delta 文件；这 7 个文件未被 `catalog_partitions` 引用，对应日期均已包含在 2018 年度文件中；
- 已清理 2,891 个空目录（含日期目录清除后变空的年份目录），随后删除 7 个孤儿文件及其
  `catalog_files` 记录；当前 daily 的 delta Parquet、空 delta 目录和无引用 Catalog 文件均为 0。

验证：

- 存储合并定向测试：3 项通过；
- `pytest -q`：77 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过。
- 清理后复核：2018 年 243 个有效分区全部指向唯一的 `annual/2018.parquet`，日期范围仍为
  `2018-01-02` 至 `2018-12-28`。

下一步：无。

### 2026-11-20 — Codex（目录导入支持快速移动）

完成：

- 目录导入新增“移动/复制”文件处理方式，默认使用移动；同一文件系统内通过原子重命名进入
  staging，再原子发布到正式目录，避免超大 Parquet 的整文件复制；
- 复制模式保留源文件，适用于需要继续保留转换输出的场景；
- 移动模式遇到跨文件系统时明确报错并提示改用复制，不静默退化为慢速复制；审核或发布失败时
  尝试将文件恢复到原始路径；
- 前端新建目录导入任务时可直接选择文件处理方式，并明确显示移动会在成功后删除源文件。
- 服务器目录导入发布时不再计算完整 SHA-256，Catalog 中以空字符串表示未计算，避免对每个
  1–2 GB L2 Parquet 再做一次全文件读取；其他发布路径仍保留 SHA-256。
- L2 正式物理目录日期统一为 `YYYY-MM-DD`；启动时会原子迁移历史 `YYYYMMDD` 目录并同步更新
  CatalogFile、CatalogPartition 和 CollectionRun 路径，数据库失败时恢复目录。
- 数据集覆盖率只有在分区数达到预期交易日数时才显示 `100%`；尚缺分区但按一位小数会四舍五入
  到 100 的情况固定显示为 `99.9%`。

验证：

- 目录导入测试：3 项通过，覆盖默认移动删除源文件、复制模式保留源文件；
- `pytest -q`：77 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过；
- `npm run build`：通过。

下一步：无。

### 2026-11-20 — Codex（中泰 L2 单日转换与扫描验证）

完成：

- 使用临时转换脚本转换 `20260323`，源目录为中泰深市 L2，输出位于
  `/home/hhd_data/quantstone-data/imports/zhongtai_l2/sz/20260323`；
- 委托源 104,585,828 行，过滤股票后输出 85,917,403 行、677,012,552 字节；
- 成交源 93,981,175 行，过滤股票后输出 76,321,044 行、957,859,084 字节；
- 委托扫描任务 `db5428e4-e890-4c7b-b9a6-2d5bb8c21b59` 与成交扫描任务
  `14b5dc67-cd78-4a05-8078-8bfbb5678d35` 均为 `review_ready`，各 1 个 ready 文件、0 异常；
- 只完成转换和扫描，尚未执行正式导入，两个源文件仍保留在 imports 目录。

下一步：确认单日结果后可执行两个导入任务，或先启动全量转换。

### 2026-11-20 — Codex（TuShare stock_st 数据集）

完成：

- 新增预置契约 `tushare.cn.stock.stock_st`，保留官方 5 个字段，按 `trade_date` 分区，主键为
  `ts_code + trade_date`，使用交易日历与 `yearly_with_delta` 存储；
- TuShare A 股采集器新增 `stock_st_initial` / `stock_st_incremental`，通过现有代理 API 配置按
  交易日请求并输出 Parquet；
- 新增 stock_st 审核器，检查必填字段、主键唯一性、分区日期和 TS 代码格式，并允许合法空分区；
- 分区采集调度从硬编码 daily 数据集改为按存储策略识别，支持后续同类按日数据集。

验证：预置契约、注册表、stock_st 单日采集发布和既有 daily 回归定向测试均通过；
`pytest -q` 79 项通过，`ruff check .` 通过。

真实服务验证：正式单日任务 `f3f256e7-957f-4147-8783-fb1c0753414c` 已审核通过并发布
`2026-11-19` 分区，196 行、3,519 字节。此前代理因 `stock_st` 权限未开通，对 2015 年请求
返回成功但数据为空；2026-11-23 开通权限后复测，`2015-01-05` 返回 46 行，2015 全年返回
12,647 行、覆盖 244 个交易日（`2015-01-05` 至 `2015-12-31`）。日期参数和采集器实现正确；
不能把权限不足造成的空响应当成历史覆盖缺失。

空分区策略已明确：`stock_st` 契约配置 `allow_empty_partitions=true`，允许 0 行交易日通过审核、
发布空 Parquet，并在 Catalog 中记录为已覆盖；日 K 等数据集默认 `false`，0 行继续审核失败。
验证：`pytest -q` 79 项通过，`ruff check .` 通过，`npm run build` 通过。

### 2026-11-20 — Codex（预置契约重复创建恢复）

完成：

- 预置契约列表已存在的数据集显示状态和“查看数据集”入口；
- 页面数据过期时若创建请求遇到已存在的数据集，前端自动读取并打开现有数据集，不再展示
  `dataset already exists` 英文错误。

验证：`npm run build` 通过，`ruff check .` 通过。

### 2026-11-23 — Codex（单进程多线程与供应商 API 串行）

完成：

- 后台执行器从单工作线程改为按任务创建线程，不设置统一线程数量上限；
- 采集、目录导入和年度合并按数据集资源键互斥，不同数据集可以并行，同一数据集保持串行；
- 新增共享供应商 HTTP 客户端，`daily`、`stock_st`、`stock_basic`、`trade_cal` 无论位于哪个
  采集器文件，都共享 TuShare 并发门，任意时刻最多一个 TuShare HTTP 请求；
- 供应商并发门只覆盖网络请求，原有滑动窗口频率限制、重试、取消和历史任务记录保持不变。

验证：`pytest -q` 80 项通过，`ruff check .` 通过，`npm run build` 通过；定向测试确认不同资源
并行、同一资源串行、等待任务可取消，且同一供应商最大活动 HTTP 请求数为 1。

### 2026-11-23 — Codex（交易日历增量窗口）

完成：

- 定位任务 `80856075-a9d6-4536-8b34-59ecda959a14` 失败原因为增量请求固定从 1990 年开始，
  13,841 天超过当前兼容代理单次最多 3,000 天的限制；
- 交易日历增量改为请求最近 3,000 天，并与当前正式快照合并后整体替换；窗口以前的历史保留；
- 增量任务会读取 Catalog 当前快照，缺少快照或供应商窗口返回 0 行时拒绝覆盖。

验证：交易日历首次采集及 3,000 天窗口增量合并定向测试通过；`pytest -q` 81 项通过，
`ruff check .` 通过。

真实服务验证：重试任务 `3e387680-1ade-45aa-b0c0-2cec1df38cfe` 成功，快照由 13,486 行更新为
13,490 行，日期范围保持为 `1990-12-19` 至 `2027-11-24`，旧历史未丢失。同步修复 Catalog
分区被新文件替换时 `published_at` 未更新的问题，使界面显示本次实际发布时间。

## 当前状态

以下为历史累计清单，早期状态以顶部 2026-11-24 摘要为准。

更新时间：2026-11-24
当前工作 Agent：Codex 已交接，DeepSeek Harness 接手
工作分支：`main`  
远程仓库：`git@github.com:DXKevin/quantstone-data.git`

已完成：

- 建立 FastAPI、SQLAlchemy、SQLite 后端；
- 建立 React、TypeScript、Vite 前端；
- 实现 Dataset Registry 基础数据模型；
- 实现数据集创建、列表、详情、草稿编辑、草稿删除和启用；
- 实现数据集 ID、字段、主键和时间字段校验；
- 实现中文数据集管理界面；
- 建立数据集 ID 规范和完整架构文档；
- 实现采集任务创建、列表和详情 API；
- 实现首次、增量、修复和重建任务类型；
- 实现采集器与手动文件两种输入方式；
- 实现手动文件上传到外部 staging，并记录文件完整性元数据；
- 实现采集任务列表与创建页面；
- 实现手动文件上传及 staging 状态展示；
- 实现 `tushare.cn.stock.stock_basic` 的真实采集器代码绑定；
- 实现采集任务执行接口，真实结果写入 staging CSV；
- 实现 stock_basic 审核器，检查契约字段、主键非空、主键重复和空数据；
- 审核结果写入 staging 下的 `review.json`，任务进入审核通过或审核异常状态；
- 前端支持执行已创建的采集器任务并查看审核摘要；
- 创建任务时不再要求用户填写内部采集器标识，日期范围改为按需启用；
- stock_basic 专用代码已按 `provider/region/instrument/dataset` 四层 ID 目录组织；
- 实现正式采集器注册模型，操作声明参数、执行入口和输出数据集；
- 数据集契约保存采集器与操作绑定，启用时校验输出归属；
- 新增采集器目录 API 和前端采集器页面；
- 前端数据集表单、详情和采集任务清楚显示采集器绑定；
- 数据集改为按任务目的绑定具体 operation；首次和增量可以调用不同函数；
- operation 直接关联 Python 函数，对外模型不增加 handler 字段；
- 每个采集器独立导出 CollectorDefinition，总注册表只显式汇总并在启动时校验；
- 数据集采集绑定支持默认 parameters，任务运行参数合并后校验；
- 前端采集器页面按输出数据集分组，首次和增量在同一紧凑行展示；
- 引入 PyArrow，数据集物理输出统一为 Parquet；
- 实现采集器入口/出口基础协议：Context、Result 和 DatasetArtifact；
- TuShare daily 支持按交易日采集、Parquet 转换和专用审核；
- 实现 Collection Run、日增量发布和 CatalogPartition；
- 数据集支持逻辑分区、布局、写入和合并策略；
- 真实采集 2024-01-02 日 K 成功，共 5,329 行；
- 后端最近完整基线为 41 个测试通过；本轮新增筛选下载和任务重试测试尚待完整执行；
- 前端生产构建通过；
- Ruff 检查通过；
- 删除旧 `datasets/` 代码目录，数据集契约只保存在 Registry 数据库；
- 采集实现归入 `collectors/tushare_cn_stock/`；
- 审核器按数据集 ID 路径组织，并以 `dataset_id` 直接注册，不增加 reviewer ID；
- 通用审核规则与数据集专属业务规则分离；
- 发布流程拆为 `publishing` 服务、路径解析和 Catalog 写入模块；
- 创建采集任务页面由 operation 参数定义动态生成表单；
- 注册并启用 `tushare.cn.stock.trade_cal` A股交易日历数据集；
- 实现 trade_cal 首次采集、增量全量刷新、专属审核和 snapshot 发布。
- 日期分区数据集必须显式绑定 `calendar_dataset_id`；启用时校验日历契约，创建任务时校验日历已发布；
- daily Planner 已改为读取正式交易日历，只对 `is_open = 1` 的日期运行，不再按工作日推测；
- 采集任务前端会展开失败分区、审核规则和中文原因，审核器显示目标数据集 ID；
- 实现 JSON Lines 结构化日志、应用日志轮转和按任务自动分流；
- 采集、审核、发布、文件暂存和 API 异常已记录关键事件；
- Token、密码、Cookie 等敏感字段在日志格式化时自动脱敏。
- 实现存储概览与 Catalog 分区查询 API（前端入口已按用户要求移除，API 保留）；
- 增加暂存运行及 Catalog 缺失文件健康指标。
- 实现统一采集执行框架：按 operation 声明滑动窗口限流、限流/网络错误退避重试；
- TuShare daily 首次与增量共用每分钟 50 次窗口，达到上限时等待而非失败；
- 实现任务执行期状态 `running`、`cancelling`、`cancelled`；
- 实现任务进度接口，按交易日历计算预期分区数和完成百分比；
- 实现协作式取消（分区边界生效）和任务记录删除（仅非执行状态）；
- 前端任务列表支持进度轮询、取消和删除，执行按钮带旋转状态，点击任务行就地展开分区明细；
- 新增“数据概览”首页：按数据集聚合分区数、行数、体积、覆盖率和最新分区，点击卡片进入详情；
- 新增覆盖热力图：数据集 × 交易日展示完整、缺失、采集失败、文件异常、待采集状态；
- 热力图失败格子显示具体审核原因（如“接口返回 0 行”“分区日期不一致”）；
- 拆分物理文件与逻辑分区：新增 `catalog_files`，分区通过 `file_id` 引用文件；
- 新增按文件分组的行读取接口 `GET /api/v1/datasets/{id}/rows`；
- 新增年度合并接口 `POST /api/v1/datasets/{id}/compact?year=YYYY`，旧文件移入 `revisions/`；
- 完成 daily 2024 年合并：242 个日文件 → 1 个年度文件（1,293,893 行，35.6 MB）；
- 数据集详情支持 Catalog 已发布数据预览：无筛选 20 行，按部分或完整主键筛选最多预览 100,000 行；
- 预览表格采用固定高度虚拟滚动，筛选结果可完整下载为 CSV 或 Parquet；
- 失败、审核异常和已取消的采集器任务可以复制为新任务重试，并通过 `retry_of_job_id` 追溯；
- 采集任务列表显示本地化创建时间，创建表单切换输入方式不再无条件重置任务目的；
- `tushare.cn.stock.stock_basic` 已升级到统一 CollectionResult 协议并接入 snapshot 正式发布；
- `tushare.cn.stock.stock_basic` 首次和增量采集均合并 `L`、`D`、`P` 三种股票状态；
- `tushare.cn.stock.stock_basic` 预置契约包含供应商接口的全部 17 个字段；
- stock_basic 只对代理返回的浮点 `symbol` 用 `ts_code` 前缀恢复，代理返回的空值保持为空；
- 字段契约类型收敛为 8 个 Parquet 原生类型并在 Registry 校验，采集器共用 `field_types`；
- 股票列表采集操作由 `stock_list_*` 更名为 `stock_basic_*`，启动时迁移已有绑定和历史任务；
- 修复采集任务取消在 SQLite 锁冲突时返回 500；日分区执行在供应商调用前释放事务；
- 运行日志支持 `min_level` 过滤，前端可按信息/警告/错误分级查看；
- 旧股票信息数据集启动时自动补齐 snapshot 存储策略，审核通过后登记 Catalog 并可直接预览；
- 采集任务详情新增“运行日志”页签，可查看采集、审核、发布、限流和重试事件，并在执行期间自动刷新；
- 新增任务日志读取 API，默认返回最近 500 条；执行框架日志已携带 job_id，可正确进入任务日志文件；
- 修复任务重试状态归属：旧任务只在复制新任务期间显示“重试中”，随后自动展开并跟踪新任务；任务结束后强制刷新状态、分区明细和已打开的日志，不再残留“采集中”；
- 采集执行改为真正的后台任务：执行接口立即返回 `202 + queued`，单工作线程依次完成采集、审核和发布；前端只轮询状态、进度和日志；
- 排队任务支持直接取消，后台开始处理后进入 `running` 并沿用协作式取消；
- 新增独立的 `MaintenanceJob` 模型，年度合并改为 `202 + queued` 后台维护任务；
- 采集和年度合并共用单工作线程，避免同时修改 Catalog 和物理文件；数据集详情新增年度合并入口、任务状态轮询和排队取消；
- Linux 开发环境已完成初始化：代码位于 `/home/quantadmin/project/quantstone-data`，数据根目录为 `/home/hhd_data/quantstone-data`；
- 使用 Python 3.12 建立 `.venv`，前后端依赖已安装，并从空 Catalog 初始化 `var/quantstone-data.db`；
- 新增 `scripts/quantstone-dev.sh`，统一管理前后端的启动、停止、重启、状态和日志；前端监听局域网 5173 端口；
- 已启用数据集可以修改显示名称和说明；身份字段与数据契约继续锁定，等待版本化变更能力；
- 当前 Linux Registry 已创建并启用 `tushare.cn.stock.trade_cal`，尚未执行首次采集；
- 新增项目级“预置契约”目录，首批包含 TuShare `trade_cal`、`stock_basic` 和 `daily`，可在前端一键创建 Registry 草稿；
- 前端将原“采集器”和“采集任务”侧栏入口合并为“采集”，页面内通过“任务 / 采集能力”页签切换；
- 前端将“预置契约”并入“数据集”入口，页面内通过“数据集 / 预置契约”页签切换；
- 数据集详情新增契约采集按钮；新数据集完成首次采集前，前后端均阻止增量、修复和重建任务；
- 新增用户维护的数据集大类，可创建、改名、删除空大类，并在数据集详情中手动归类；列表按大类分组展示，每个大类卡片右上角可直接添加或移动数据集；
- 新增经过影响审查、阻止条件、确认文字和状态令牌保护的批量数据集物理删除；

尚未实现：

- 通用采集任务 Planner 和任务参数模型；
- 更多采集器/审核器实现（当前注册 TuShare stock_basic、daily 和 trade_cal）；
- 联合采集运行及多数据集输出记录（注册模型已能识别，执行层尚未实现）；
- staging 后续处理和 quarantine；
- 数据质量报告；
- 通用手动文件解析、审核与发布；
- 更完整的 Data Catalog；
- 原子发布；
- 数据读取 SDK。

## 建议下一步

当前优先级：

1. 先与用户确认多存储根的两个根路径、分片策略和迁移方式，再实现 `storage_roots` /
   `catalog_files.root_id`；不要按物理硬盘建多个 SQLite。
2. 复核 Wind 173 天、中泰 2,213 天 L2 和 index_daily 4,100 天的 Catalog/文件完整性。
3. 运行 `tb_sbkj2077.cn.stock.minute_1m` 首次采集，起始日期 `2015-01-01`；源分享按需
   单文件转存，首次按年、增量按日，发布后清本地缓存。
4. 如需看 Catalog 审计视图，用户已明确暂时不要；保持按数据集接口和概览热力图即可。

不得把现有 TuShare Token、百度网盘账号或真实金融数据提交到 Git；本地 `.env` 只供运行使用。

## 已知问题与注意事项

- 多存储根尚未实现；当前仍只有单一 `data_root`，Dataset 多卷分片只是待确认方案；
- Wind 与中泰 L2 已完成导入；Wind 173 天、中泰 2,213 天，不要再对相同日期重复导入；
- 中泰源只有上午 09:15–11:30，且包含 ETF/基金/可转债/B 股/REITs；当前只保留股票，
  `is_historical=true`，不能按全天全证券解读；
- 中泰 trade 没有委托代码字段，`order_code` 为占位 0；`side` 是成交记录内两个委托 ID 的
  规范化还原；
- L2 审核器不做上亿行主键全量唯一性校验；需要时单独离线验证；
- `tushare.cn.index.index_basic` 的旧失败任务 `ace1fc71` 仅保留历史，成功 snapshot 由
  `e8c8de96` 产生，不要重试覆盖成功数据；
- Catalog 全量前端页已按用户要求回退，当前没有独立 Catalog 浏览入口。
- `schema_version` 当前作为内部契约格式字段固定为 v1，不提供数据集内的 Schema 升级能力；
- 当前 SQLite 表由 `create_all` 建立，尚未引入 Alembic；
- FastAPI 测试会出现 Starlette 关于 `httpx` 的弃用警告，不影响现有测试结果；
- 真实数据必须存放在仓库之外；
- 前后端由 `scripts/quantstone-dev.sh` 统一启动，不要额外启动重复服务；
- 通过 SFTP 或脚本连续修改前端文件时，Vite 的文件监听偶尔会漏掉最后一次变更，
  并继续提供中间状态的模块（表现为整页白屏）。清空 `web/node_modules/.vite` 并重启
  前端即可恢复；排查时先看浏览器控制台，不要只看构建是否通过。
- Linux 服务通过 `scripts/quantstone-dev.sh` 管理，Git 推送已验证可用；
- 默认 SQLite 仍位于工作目录的 `var/quantstone-data.db`，而数据文件位于
  `QUANTSTONE_DATA_ROOT`，迁移时必须成套处理；
- 手动上传目前没有文件大小上限，应在真实大文件使用前增加可配置限制；
- `STAGED` 文件尚未解析、校验或发布；
- Catalog 已拆分为文件与分区，历史修订只保留 `revisions/` 下的文件副本，没有版本回滚；
- 读取接口遇到 Catalog 指向的文件缺失时会返回 `409` 并中止，不会返回部分数据；
- `revisions/` 目录没有清理策略，合并后旧文件会持续占用磁盘；
- 年度合并已异步执行，但运行中的合并不能取消；服务重启会把未完成维护任务标记失败，需要重新提交；
- 增量采集不能最终实现为“最大日期加一天”，必须由交易日历和 Catalog 缺口共同决定。
- Windows 旧环境曾发布 `trade_cal` 与 daily 数据，但尚未迁移到当前 Linux；当前 Linux 的
  `trade_cal` 与 daily 均已创建并启用；历史 Catalog 与数据仍未迁移；
- 当前后台任务只存在于单个服务进程内；任务线程数不设统一上限，不同数据集可并行，同一数据集串行；服务重启不会自动续跑排队或执行中的任务，而会将其标记失败；
- 限流器只存在于进程内，多进程部署需要改为共享限流；
- 取消请求和执行中集合只存在于进程内；服务重启后会把遗留的 `running` / `cancelling` 任务自动标记为失败；
- 取消在分区边界生效，单个分区内无法中断；
- 当前兼容 TuShare 的代理存在响应类型漂移：`stock_basic` 的退市批次曾将 343 条 `symbol`
  返回为浮点数、1 条返回为空；采集器已从同一行 `ts_code` 恢复，但接入其他接口时仍需按
  数据契约做类型校验，不能假定代理严格保持官方文档类型；
- TuShare `https://api.tushare.pro` 在本轮验证期间直接返回 Nginx 502；本机无代理环境变量，属于上游或本机网络链路问题；系统会在重试耗尽后把中文原因写入任务、运行记录和日志，由前端轮询展示；
- 筛选下载会在服务端生成完整临时文件，前端 `fetch` 仍会把下载 Blob 放入浏览器内存，超大导出后续应改为浏览器原生流式下载；

## 最近一次交接记录

### 2026-11-19 — DeepSeek Harness（中泰 L2 契约与 Wind 对齐评估）

完成：

- 分析 `/home/ssd_data/stock_database/stock_a_quote/stock_day_a_l2/SZ/{order,trade}/20260323`；
- 创建并启用 `zhongtai.cn.stock.l2_order.sz`、`zhongtai.cn.stock.l2_trade.sz`；
- 两个契约与 Wind 深市 L2 使用完全相同的字段名/类型/主键，读取时可复用同一套列解析；
- 中泰设为 `manual` 更新频率并标记 `is_historical=true`，不进入日更统计和覆盖热力图；
- 数据集契约新增 `is_historical` 布尔字段，历史数据集不参与热力图/日更跟踪；
- 预置契约页新增两个中泰数据集。

映射结论：

```text
SecurityID        -> symbol（加 .SZ）和 exchange_code
tradedate         -> trade_date
TransactTime/     -> event_time（HHMMSSmmm）
tradetime
ChannelNo         -> channel_code（string）
ApplSeqNum        -> exchange_order_no / trade_no
OrderType 2/1/U   -> 0/1/U
Side 1/2          -> B/S
Price * 10000     -> price（int64）
OrderQty/TradeQty -> volume
ExecType F/4      -> 0(成交)/C(撤单)
BidApplSeqNum     -> bid_order_no
OfferApplSeqNum   -> ask_order_no
```

已核对：20260323 order 104,585,828 行、trade 93,981,175 行；`(SecurityID, ApplSeqNum)`
在 order/trade 内均无重复；中泰全量约 2,246 个交易日（2017-01 至 2026-03），源约
809 GB order + 1.1 TB trade。

限制：

- 中泰 trade 没有 BS 标志，但 trade 自带 `BidApplSeqNum`/`OfferApplSeqNum`，单频道下直接比较两个 ID 即可还原主动方，不需要 join order；Wind 对照 6,987 万笔 100% 一致，撤单为空；
- 中泰 trade 没有委托代码，`order_code` 导入时填 0 或空；
- `OrderType` 2/1/U 和 `Side` 1/2 的映射是读取归一化假设，需要按中泰源文档再确认；
- 中泰临时转换脚本已写：`/home/quantadmin/l2_migration/convert_zhongtai_l2.py`，
  仅保留股票前缀，trade 的 `side` 直接比较 `BidApplSeqNum`/`OfferApplSeqNum`，未跑数据；
- 中泰扫描器 `zhongtai_l2_sz` 已注册，包含 `import_order`/`import_trade`；
- 中泰契约和扫描器的小数据集成测试已通过，真实数据尚未转换/导入。

### 2026-11-19 — DeepSeek Harness（Wind L2 迁移脚本与目录导入）

完成：

- 临时转换脚本保存在 `/home/quantadmin/l2_migration/convert_wind_l2.py`，说明见同目录
  `README.md`；脚本不属于前后端项目，按契约重写列名/类型并输出到
  `/home/hhd_data/quantstone-data/imports/wind_l2/sz`；
- 转换脚本在 `20261118` 上验证：order 116,393,103 行、trade 104,411,003 行，耗时约
  45 秒，输出约 0.91 GB / 1.23 GB；`exchange_code` 恢复六位字符串，`order_code` 输出
  字符串 `"0"`，主键组合单日唯一；
- 已实现正式目录导入功能：`ImportJob` 模型、`l2_sz_baidu` 扫描器、清单/审核/执行/取消
  API、L2 审核器、前端“采集 → 目录导入”页面；
- 已把 `20261118` 的 order/trade 从 `imports/wind_l2_test` 扫描并导入 Catalog：
  两个数据集各有 1 个分区，行数与转换输出一致；
- 导入任务与采集/合并共用单工作线程，源目录限制在 `imports/` 或
  `QUANTSTONE_IMPORT_ROOTS`；
- 修复采集任务列表 500：`InputMethod` 增加 `directory_import`，导入任务生成的
  CollectionJob 可以正常序列化；前端采集页输入方式显示“目录导入”。

验证：

- `pytest -q`：74 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过；
- `npm run build`：通过；
- 实跑扫描 → `review_ready` → 导入 → `succeeded`，Catalog 可预览。

已知限制：

- 转换只跑了 `20261118`，其余 169 天需要用户手动执行全量脚本；
- 全量约 170 天、550 GB 源，预计转换约 2 小时、输出约 350 GB；
- L2 审核器目前检查 Schema、非空、行数和分区日期，不做上亿行主键全量唯一性校验；
- 测试数据在 `imports/wind_l2_test`，正式全量输出应在默认的 `imports/wind_l2/sz`。

### 2026-11-19 — DeepSeek Harness（创建深市 Wind L2 数据集）

完成：

- 读取并分析 `/home/ssd_data/stock_database/stock_a_quote/stock_day_a_l2_wind/data/SZ/20261118` 和原始 Wind PDF 说明；
- 首次创建后用户删除了两个数据集；按 PDF 修正契约后，已用预置契约重新创建并启用；
- 两个数据集的 `symbol`、`exchange_code` 都使用 `string`；`event_time` 使用
  `HHMMSSmmm` 的 `int32`；价格使用 0.0001 元的 `int64`；
- 按原始 PDF 修正：`委托编号`（频道代码）和 trade 的 `委托代码` 都是 `char(1)`，统一
  使用 `string`；合并 Parquet 中的 `0.0` 浮点是类型推断漂移，不代表原始类型；
- `l2_order` 保留源文件 10 个字段，主键 `trade_date + symbol + exchange_order_no`；
  `channel_code` 只保留为普通字段，不进入主键；
- `l2_trade` 保留源文件 12 个字段，主键 `trade_date + symbol + trade_no`；`channel_code`
  只保留为普通字段，不进入主键；字段说明只保留字段语义，不再写 C 行价格/BS 空等数据事实；
- 两个数据集均为日分区、日更、逐笔颗粒，交易日历绑定 `tushare.cn.stock.trade_cal`；
- 预置契约同步加入两个深市数据集；后端重启后预置页可见。

待办：

- 两个数据集的 `collection_bindings` 为空，等待目录扫描器实现后再绑定；
- 沪市目录当前只有 `order.parquet`，且 `委托类型` 等值域与深市不同，需单独建契约；
- 重写迁移时按原始 PDF 的 `char(1)` 类型恢复字符串，不依据合并 Parquet 的推断类型；
- 推送状态：当前 `main` 领先 `origin/main` 1 个提交；GitHub SSH 连接被重置，尚未推送，
  待网络恢复后执行 `git push origin main`。

### 2026-11-19 — DeepSeek Harness（左侧导航可收起）

完成：

- 左侧导航增加“收起侧栏/展开侧栏”按钮，收起后宽度从 224px 变为 64px，只显示图标；
- 收起状态写入 `localStorage`，刷新后保持；
- 导航项增加 `title`，收起时悬停仍可看到名称。

验证：

- `npm run build`：通过；
- 无头浏览器实测：宽度 224 → 64，收起后导航文字隐藏。

### 2026-11-19 — DeepSeek Harness（最小时间颗粒与日更面板对齐）

完成：

- 数据集契约新增 `time_granularity`：`tick` / `second_3` / `second` / `minute` /
  `hour` / `day` / `none`；
- 启动迁移为旧数据集补齐：日 K、交易日历为 `day`，股票列表为 `none`，其余默认 `none`；
- 创建/编辑数据集表单、基本信息展示和 API 类型同步；
- 预置契约设置：日 K `day`、股票列表 `none`、交易日历 `day`；
- 日更完成率面板对齐进度条：固定列宽；去掉快照行冗余提示和 0 缺失/0 失败的噪声；
- 确认交易日历更新频率为 `monthly`，不再进入日更统计。

验证：

- `pytest`：73 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过；
- `npm run build`：通过；
- 无头浏览器实测：日更明细两条进度条左边界一致；数据集详情显示“更新频率/最小时间颗粒”。

### 2026-11-19 — DeepSeek Harness（数据集更新频率）

完成：

- 数据集契约新增 `update_frequency`：`daily` / `weekly` / `monthly` / `manual`；
- 数据库启动迁移为旧数据集补齐字段：daily 和 stock_basic 设为 `daily`，trade_cal 设为
  `monthly`，其余默认 `manual`；
- 预置契约、创建/编辑表单、基本信息展示和 API 类型同步更新；
- 日更完成率面板只统计 `daily` 数据集，月更的交易日历不再误入日更统计。

验证：

- `pytest`：73 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过；
- `npm run build`：通过。

### 2026-11-19 — DeepSeek Harness（日更数据完成率）

完成：

- 新增 `GET /api/v1/overview/daily-completion?days=30`，聚合按日分区数据集的最新交易日
  状态、完成数、缺失/失败/异常/待采集数和完成率；
- 快照数据集（股票列表、交易日历）也纳入面板，按最近一次成功发布/采集是否覆盖最新
  交易日判断“已更新/需更新”；
- 数据概览增加“日更数据完成率”面板，明细默认收起，点击“完成率明细”展开；
- 完成率分母排除当天“待采集”，避免开盘前误判为缺口；
- 补充接口测试和文档。

验证：

- `pytest -q`：73 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过；
- `npm run build`：通过；
- 当前 daily 已补齐到 2026-11-19，实测最近 30 个交易日 `30/30 · 100%`。

### 2026-11-19 — DeepSeek Harness（年度合并自动识别）

完成：

- 新增 `POST /api/v1/datasets/{dataset_id}/compact-all`：扫描 Catalog，自动找出仍由
  日增量文件承载的年份，为每个待合并年份创建维护任务；已有排队/执行中任务的年份跳过；
- 数据集详情新增“自动合并全部年份”按钮，保留原单年份合并；前端当前通过 Catalog 分区
  接口自行识别年份并逐个调用单年份接口，因此无需等待后端重启即可使用；
- 补充异步接口测试和文档。

验证：

- `pytest -q`：73 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过；
- `npm run build`：通过。

未完成部署：当前 daily 增量任务 `a6139be5` 正在执行，为避免再次中断没有重启后端。
新接口 `/compact-all` 尚未在当前进程生效，但前端“自动合并全部年份”已改为读取现有
Catalog 分区并逐个调用单年份接口，现在即可使用；等任务结束并重启后端后，API 也会提供
批量入口。重启前务必确认没有 `running` / `queued` 任务。

### 2026-11-19 — DeepSeek Harness（数据概览增加采集概览）

完成：

- 新增 `GET /api/v1/overview/collection`，聚合任务总数、执行中/排队/等待文件数量、
  最近 24 小时成功/失败数、最近完成时间和最近 5 个采集任务；
- 数据概览页在数据汇总卡之后增加“采集概览”面板，展示上述指标和最近任务列表；点击任务
  进入采集页并展开该任务；面板常显，“最近采集任务”列表默认收起、点击展开；
- 数据集卡片增加“首次采集”“增量更新”快捷按钮，放在“已启用”徽标左侧；已有 Catalog
  分区的数据集只显示“增量更新”，无分区的只显示“首次采集”；需要参数的首次采集弹窗填写；
- 快照等不按日分区的数据集保留覆盖率进度条：已发布快照显示 100%，未初始化显示 0%；
- 明确覆盖率分母为“最早 Catalog 分区到今天”的交易日，不使用某次任务的日期范围；
  日期分区数据集无已发布分区时显示“尚无已发布分区”，不再误判为快照；
- 补充接口和前端测试。

验证：

- `pytest -q`：72 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过；
- `npm run build`：通过；
- 接口实测：当前 10 个任务，最近 5 个任务和 24 小时成功/失败统计均正常返回。
- 无头浏览器实测：卡片“首次采集”能打开参数弹窗；点击“A股股票列表”的“增量更新”后
  任务立即创建并执行成功。

注意：为加载新接口重启了后端，重启时一个从 2018-07-28 开始的 daily 增量任务被中断并
标记失败；它已发布 310 个分区，最新到 2019-11-06。需要新建增量任务从 Catalog 水位继续。
之后部署快捷操作时又重启了一次，中断了从 2019-11-07 开始的 daily 增量任务
`295257ac`；它已发布 150 个分区到 2020-06-18。再次新建增量任务会从 2020-06-19 继续。

### 2026-11-19 — DeepSeek Harness（任务完成时间与分页）

完成：

- 进度接口新增 `started_at`、`finished_at`、`elapsed_seconds`、`eta_seconds`、
  `expected_finish_at`、`eta_basis`；日分区任务按平均分区耗时估算剩余时间，快照任务按同一
  `collector_operation` 最近成功任务的中位耗时估算；
- 任务列表改为 `limit` / `offset` 分页，返回 `{items, total, limit, offset}`，默认 20 条；
- 分区运行明细改为分页并返回总数，按分区倒序，前端支持“加载更多”；
- 前端任务列表显示预计完成时间和剩余时长，新增分页控件；轮询只刷新当前页。

验证：

- `pytest -q`：71 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过；
- `npm run build`：通过；
- 实测一个 10 个分区的 daily 任务：处理到 5/10 时返回 `eta_seconds=3`，
  取消接口返回 200，任务最终进入 `cancelled`；运行明细分页返回 `total=6`。

注意：该实测任务重新发布了 2018-07-16 至 2018-07-23 之间的已有分区，覆盖范围没有变化，
只是走了一遍采集、审核和发布流程。

### 2026-11-19 — DeepSeek Harness（取消 500 与日志级别筛选）

完成：

- 定位取消任务返回 500 的根因：daily 执行循环在供应商调用期间仍持有 SQLite 读事务，
  取消接口写 `cancelling` 时触发 `database is locked`；同时也让首次点击“取消”只进入确认态，
  看起来像没有响应；
- daily 在每个分区调用供应商前先提交 `fetching` 状态，释放数据库事务；SQLite 连接超时
  提高到 15 秒；
- 取消接口先登记进程内取消请求，状态写库遇到锁冲突时仍返回 `cancelling`，由工作线程在
  分区边界写回 `cancelled`；其他数据库错误返回 503 而不是 500；
- 前端第一次点击取消会提示“再次点击确认取消”，避免误以为没有响应；
- 运行日志接口新增 `min_level`（DEBUG/INFO/WARNING/ERROR/CRITICAL），前端增加级别下拉，
  按“信息以上 / 警告以上 / 错误以上”过滤，并保留错误级别高亮；
- 架构文档补充取消请求的落库失败处理。

验证：

- `pytest -q`：70 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过；
- `npm run build`：通过；
- 重启后确认旧任务被标记失败、取消终态任务返回 409、日志级别过滤接口可用。

注意：为加载取消修复重启了后端；重启时正在执行的 daily 首次采集任务被启动恢复标记为
失败，已发布的 862 个分区保留。后续应新建增量任务，从 Catalog 水位继续。

### 2026-11-19 — DeepSeek Harness（stock_basic 操作更名）

完成：

- `stock_list_initial` / `stock_list_incremental` 更名为 `stock_basic_initial` /
  `stock_basic_incremental`，与 `daily_*`、`trade_cal_*` 的命名方式一致；
- 同步修改预置契约、采集器注册、测试和架构文档；
- `upgrade_sqlite_schema` 增加迁移：已有 `collection_bindings` 与历史任务的
  `collector_operation` 会从旧名改为新名；
- 重启服务后确认 Linux Registry 绑定、历史任务和采集能力接口均已使用新名。

验证：

- `pytest -q`：69 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过；
- 后端 `/api/v1/collectors`、stock_basic 数据集绑定和 SQLite 记录均已核对。

### 2026-11-19 — DeepSeek Harness（字段类型收敛与 Parquet 映射）

完成：

- 新增 `field_types.py`，统一 `string`、`int32`、`int64`、`float32`、`float64`、
  `boolean`、`date`、`timestamp` 的归一化与 Parquet 映射；
- `DatasetFieldCreate` 校验类型枚举，未知类型返回 422；
- 三个 TuShare 采集器删除各自的 `_convert` / `_arrow_type`，改用共享实现；
- `date` 接受 `YYYYMMDD`、`date`、`datetime`；`timestamp` 表示无时区的交易所本地时间，
  带时区的值会被拒绝；分钟数据的 `2023-08-25 09:00:00` 格式已覆盖测试；
- 新增 Parquet 往返、日期/时间转换、API 拒绝未知类型等测试；
- 明确 L2 以基本类型交付时，逐笔时间使用 `int32` / `int64` 并在字段说明中写明编码，
  不强制转换成 `timestamp`；`trade_date` 保持 `date`；
- 架构文档补充字段类型、Parquet 映射和暂不开放范围。

验证：

- `pytest -q`：68 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过；
- `npm run build`：通过。

### 2026-11-19 — DeepSeek Harness（stock_basic 空值保持为空）

完成：

- 代理返回空 `symbol` 时不再用 `ts_code` 前缀补值；只有浮点数等非空非字符串值才恢复；
- 集成测试改为断言暂停上市样例的 `symbol` 为 null；
- 同步更新架构文档中的代理兼容说明。

验证：

- `pytest -q`：61 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过。

注意：Linux 当前已发布的 stock_basic 快照仍含旧逻辑补出的 `T600018`；如需按新规则落库，
应重新执行一次增量快照采集。

### 2026-11-19 — Codex（代理类型问题与 TuShare SDK 分析，仅交接）

结论：

- 本轮没有修改采集器实现；仅补充分析和交接记录；
- 类型错误来自代理响应：`D` 退市批次中 `symbol` 为 343 个 JSON 数值和 1 个空值，官方契约
  则声明该字段为字符串；`L` 上市批次的 5,580 个 `symbol` 均为字符串；
- 这种分布很像代理内部使用表格或缓存处理纯数字代码时发生的类型推断：空值使数字列变成
  浮点列，随后序列化为 `920680.0`。这是基于响应形态的推断，尚无代理服务端源码可证实；
- 当前直连实现与 TuShare SDK 请求的是同一套 Pro JSON 协议。TuShare 官方开源客户端的
  `DataApi.query()` 只解析 JSON，再执行 `pandas.DataFrame(items, columns=columns)`，没有根据
  接口字段说明强制字符串类型，也不会补回股票代码前导零；
- 因此改用 SDK 不能保证消除该问题。对本次 `D` 批次，SDK 很可能把 `symbol` 推断成
  `float64`；合并 `L`、`D`、`P` 后仍会混有字符串、浮点数和空值。写入固定 Arrow 字符串
  Schema 时仍可能报错，即使能够写入，也可能保存错误的 `.0` 或丢失前导零；
- SDK 的价值主要是少写请求封装和跟随官方调用方式，不负责本项目的数据契约、类型标准化、
  审核、发布与代理兼容。无论是否改用 SDK，契约边界的显式类型转换和质量检查都必须保留。

当前状态：

- 保持直接调用 Pro JSON 协议；`symbol` 异常值已从同一行 `ts_code` 无损恢复；
- 已发布快照为 5,924 行、17 列，所有 `symbol` 均与 `ts_code` 一致；
- 用户要求先不切换 SDK，后续如重新评估，应先做同一代理、同一参数的 SDK/原始 JSON 对照
  实验，再决定是否引入 `tushare` 与 `pandas` 依赖；即使切换也不得删除现有规范化和测试。

下一步：无实现任务，等待用户决定是否专门评估 SDK 依赖与调用封装。

### 2026-11-19 — Codex（兼容代理股票代码类型）

完成：

- 定位股票列表首次采集失败原因为代理将 343 条退市股票的 `symbol` 返回成浮点数；
- 从同一行 `ts_code` 恢复异常或缺失的 `symbol`，保留六位代码及前导零；
- 字符串契约字段对非字符串标量执行显式字符串转换，日期字段仍严格校验；
- 增加集成测试，覆盖浮点和空值两种代理响应。
- 已重试用户失败的首次采集任务，成功发布 5,924 行、17 列的完整快照。

验证：

- stock_basic 定向测试：1 项通过（1 条 Starlette/httpx 弃用警告）；
- `pytest -q`：61 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过；
- 当前代理只读统计：共 5,924 行，343 条 `symbol` 为浮点数、1 条为空，均可由 `ts_code` 无损恢复。
- 发布文件检查：`symbol` 无空值、无 `.0` 后缀，与 `ts_code` 中的股票代码 5,924 行全部一致。

下一步：无。

### 2026-11-19 — Codex（补全股票列表字段）

完成：

- 将 `stock_basic` 预置契约从 3 个字段补全为 TuShare 接口的 17 个字段；
- `list_date`、`delist_date` 按项目存储规范转换为日期，其余字段保留供应商名称和字符串语义；
- 增加受限启动迁移：仅对精确匹配旧三字段契约且没有 Catalog 文件的数据集原位补全，已有物理数据不自动改变契约；
- 当前本地股票列表数据集没有已发布文件，重启后会安全补全，不需要删除重建。

验证：

- 预置与 stock_basic 定向测试：3 项通过（1 条 Starlette/httpx 弃用警告）；
- `pytest -q`：61 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过；
- 当前代理只读验证返回 5,580 行，并按请求返回全部 17 个字段。

下一步：

- 对 A股股票列表执行首次采集，生成包含全部股票状态与 17 个字段的首个完整快照。

### 2026-11-19 — Codex（股票列表采集全部状态）

完成：

- `stock_basic` 默认状态由仅 `L` 改为依次请求 `L`、`D`、`P`；
- 首次采集和增量更新都会合并上市、退市和暂停上市股票并发布完整快照；
- 更新采集能力说明和项目预置契约说明；
- 测试验证三种状态均被请求并进入同一个审核结果。

验证：

- stock_basic 定向测试：1 项通过（1 条 Starlette/httpx 弃用警告）；
- `pytest -q`：60 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过；
- 当前代理只读验证：`L=5,580`、`D=344`、`P=0`，合计 5,924 条。

下一步：

- 对现有 A股股票列表数据集重新执行首次采集，以完整快照替换此前仅包含上市股票的数据。

### 2026-11-19 — Codex（可配置 TuShare API 入口）

完成：

- 新增可选配置 `TUSHARE_API_URL`，默认使用 TuShare 官方地址；
- `stock_basic`、`daily` 和 `trade_cal` 三个采集器统一读取运行时配置；
- 校验 API URL 仅允许不含账号密码的 HTTP(S) 地址；
- CollectionResult provenance 记录实际 API URL，不记录 Token；
- 当前 Linux 本机 `.env` 已配置用户提供的代理地址，该文件保持忽略且不提交。

验证：

- TuShare API 地址配置测试：5 项通过；
- `pytest -q`：60 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过；
- 当前代理 `stock_basic` 只读连通性验证成功，返回 5,580 行。

下一步：

- 无。

### 2026-11-19 — Codex（修正禁用按钮光标）

完成：

- 普通禁用的主按钮和危险按钮由等待光标改为禁止光标；
- 删除确认文字不匹配、“首次采集已完成”等条件禁用状态不再错误显示转圈等待光标。

验证：

- `pytest -q`：55 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过；
- `npm run build`：通过。

下一步：

- 无。

### 2026-11-19 — Codex（批量物理删除数据集）

完成：

- 数据集目录新增批量选择和“审查删除影响”入口；
- 审查汇总数据行、物理文件、空间、采集任务、运行、维护任务和 Catalog；
- 排队、运行、取消中的任务会阻止删除；仍被外部数据集引用的交易日历也会阻止删除；
- 用户必须输入包含全部数据集 ID 的完整确认文字；审查令牌失效后必须重新审查；
- 删除覆盖 Registry 契约、任务、运行、Catalog、任务日志、staging、正式数据和 revisions；
- 文件先移入同数据根目录的临时删除区，数据库提交失败时自动恢复；
- 关闭旧的草稿直接删除入口，所有数据集统一经过严格审查。

验证：

- 删除审查与 Registry 定向测试：11 项通过（1 条 Starlette/httpx 弃用警告）；
- `pytest -q`：55 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过；
- `npm run build`：通过。

下一步：

- 在局域网页面检查批量选择、阻止原因和长数据集 ID 确认文字的展示。

### 2026-11-19 — Codex（独立数据集契约策略）

完成：

- 数据集列表移除没有实际操作价值的 Schema 列；
- 明确已启用契约发生实质变化时创建独立的新数据集；
- 新数据集拥有独立的采集器绑定、审核规则、Catalog 和物理文件；
- 新旧数据集不建立版本、替代或父子关系，旧数据集按需保留或停用；
- 更新数据集 ID 和架构文档，删除尚待实现的 Schema v2 版本化方向。

验证：

- `pytest -q`：53 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过；
- `npm run build`：通过。

下一步：

- 无。

### 2026-11-19 — Codex（修正概览发布时间时区）

完成：

- 修复数据概览卡片把 UTC 发布时间误当成本地时间显示的问题；
- 概览 API 会为 SQLite 返回的无时区时间补充 UTC 偏移，浏览器据此转换为本地时间；
- 增加时间序列化测试，覆盖 SQLite 丢失时区信息的情况。

验证：

- `pytest -q tests/test_overview.py`：2 项通过（1 条 Starlette/httpx 弃用警告）；
- `pytest -q`：53 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过。

下一步：

- 其他新增时间字段也应返回明确的时区偏移，前端再转换为浏览器本地时间。

运行确认：

- 服务重启后，交易日历的 `published_at` 已返回 `2026-11-19T05:17:37.882852+00:00`；
- 北京时区浏览器会显示为 `11月19日 13:17`。

### 2026-11-19 — Codex（从大类卡片快速添加数据集）

完成：

- 每个大类卡片右上角新增“添加数据集”按钮；
- 点击按钮后在当前卡片内选择数据集，无需进入“管理大类”区域；
- 未分类数据集会加入当前大类，已有归属的数据集会移动到当前大类；
- “未分类”分组不显示添加按钮，大类管理区域继续负责创建、改名、删除和集中归类。

验证：

- `pytest -q`：52 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过；
- `npm run build`：通过。

下一步：

- 在局域网浏览器中确认大类标题区域的快速添加交互和窄屏布局。

### 2026-11-19 — Codex（在大类管理区域直接归类）

完成：

- 每个数据集大类直接显示其下的数据集；
- 大类管理区域可通过下拉框添加数据集，无需进入数据集详情；
- 选择其他大类中的数据集时会直接移动到当前大类；
- 每个数据集标签提供移出按钮，可恢复为“未分类”；
- 数据集详情中的分类入口继续保留，支持两种操作路径。

验证：

- `pytest -q`：52 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过；
- `npm run build`：通过。

下一步：

- 在“管理大类”中创建“A股数据”，并直接添加现有 daily 与 `trade_cal`。

### 2026-11-19 — Codex（数据集大类与手动归类）

完成：

- 新增 `DatasetCategory` 模型以及 SQLite 启动迁移；
- 新增数据集大类的列表、创建、修改和删除 API；包含数据集的大类禁止删除；
- 数据集增加可空的 `category_id`，详情页可手动归类或移回“未分类”；
- 数据集列表按大类分组展示，并提供内联的大类管理区域；
- 大类明确为目录组织信息，不影响数据集契约、采集、审核、存储和 Catalog。

验证：

- 数据集大类与 Registry 定向测试：10 项通过；
- `pytest -q`：52 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过；
- `npm run build`：通过。
- 当前 Linux Registry 启动迁移成功；现有 daily 与 `trade_cal` 保持未分类，前后端运行正常。

下一步：

- 按实际使用需要创建“A股数据”等大类，并将现有数据集手动归类。


### 2026-11-19 — Codex（数据集详情发起采集与首次采集门禁）

完成：

- 数据集详情按契约绑定显示“首次采集”“增量更新”等操作按钮；
- 点击后进入采集任务创建页，并预选目标数据集、任务目的和采集器输入；
- 新增采集就绪状态接口，区分“等待首次采集”和“可增量更新”；
- 后端强制未完成首次发布的数据集只能创建 `initial` 任务；已有 Catalog 正式分区的数据集
  视为已经初始化，兼容迁移数据；
- 首次采集成功后禁用重复的首次采集按钮，并开放契约中的后续操作。

验证：

- `pytest -q`：51 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过；
- `npm run build`：通过。
- 当前 Linux `trade_cal` 就绪状态返回 `initial_required: true`，前后端服务重启后正常。

下一步：

- 在 `trade_cal` 详情点击“首次采集”，填写日期范围并生成当前 Linux 环境的正式日历快照。

### 2026-11-19 — Codex（合并数据集与预置契约页面）

完成：

- 侧栏移除独立的“预置契约”入口；
- 在“数据集”页面增加“数据集 / 预置契约”页签；
- 从预置创建草稿后自动切回新数据集详情，原创建、编辑和详情流程保持不变。

验证：

- `pytest -q`：50 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过；
- `npm run build`：通过。

下一步：

- 继续创建首次 `trade_cal` 采集任务，生成当前 Linux 环境的正式日历快照。

### 2026-11-19 — Codex（合并采集页面）

完成：

- 将侧栏的“采集器”和“采集任务”合并为单一“采集”入口；
- 在采集页面增加“任务 / 采集能力”页签；
- 原任务创建、记录、运行明细和采集器能力目录保持原有功能。

验证：

- `pytest -q`：50 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过；
- `npm run build`：通过。

下一步：

- 继续创建首次 `trade_cal` 采集任务，生成当前 Linux 环境的正式日历快照。

### 2026-11-19 — Codex（项目级预置契约）

完成：

- 新增代码版本管理的预置契约目录与 `GET /api/v1/dataset-presets`；
- 首批固定 TuShare `trade_cal`、`stock_basic`、`daily` 的字段、主键、采集绑定和存储策略；
- 前端侧栏新增“预置契约”区域，可查看契约摘要并一键创建 Registry 草稿；
- 已存在的数据集显示当前状态，预置不会自动同步或覆盖 Registry；
- 架构文档明确 Registry 仍是运行时权威来源，预置只作为显式创建模板。

验证：

- `pytest -q`：50 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过；
- `npm run build`：通过。

下一步：

- 通过预置创建 `stock_basic` 或 `daily` 前，先按实际需要复核字段范围；
- `daily` 启用和采集仍要求 `trade_cal` 已发布正式快照。

### 2026-11-19 — Codex（创建 TuShare 交易日历数据集）

完成：

- 在当前 Linux Registry 创建并启用 `tushare.cn.stock.trade_cal`；
- 配置 `trade_cal_initial` 与 `trade_cal_incremental` 采集绑定；
- 配置 `snapshot + replace_snapshot` 存储策略；
- Schema v1 包含 `exchange`、`cal_date`、`is_open`、`pretrade_date`，主键为
  `exchange + cal_date`。

验证：

- 数据集详情接口返回 `active`；
- 首次与增量采集操作的双向归属校验通过；
- Catalog 当前为空，本次未调用 TuShare 接口、未消耗额度。

下一步：

- 创建首次采集任务并明确日期范围，再调用 TuShare 生成首个正式交易日历快照。

遗留问题：

- daily 等日期分区数据集必须等交易日历正式发布后才能创建采集任务。

### 2026-11-19 — Codex（已启用数据集基本信息编辑）

完成：

- 新增 `PATCH /api/v1/datasets/{dataset_id}`，允许任意状态的数据集修改显示名称和说明；
- 保留草稿完整编辑接口，已启用数据集仍不能覆盖 Schema、主键、采集绑定和存储策略；
- 数据集详情为非草稿状态增加“编辑基本信息”入口和独立表单；
- 明确数据集身份字段保持不可修改；当时暂留的版本化方向已被后续“创建独立数据集”决策取代。

验证：

- `pytest -q`：49 项通过，1 条 Starlette/httpx 弃用警告；
- `ruff check .`：通过；
- 前端 `npm run build`：通过。

下一步：

- 已由后续决策取代：实质契约变化时创建独立的新数据集。

遗留问题：

- 已启用数据集的契约字段不能修改；实质变化时创建独立的新数据集。

### 2026-11-19 — Codex（Linux 服务启动）

完成：

- 新增 `scripts/quantstone-dev.sh`，支持 `start`、`stop`、`restart`、`status` 和 `logs`；
- 后端通过 `.env` 启动并监听 `0.0.0.0:8000`，前端监听 `0.0.0.0:5173`；
- 前后端由用户级 systemd 临时单元托管，脚本退出和 SSH 会话断开后仍持续运行；
- 前后端标准输出写入仓库忽略的 `var/logs/`，应用结构化日志仍写入数据根目录；
- 启动脚本会检查依赖、等待前后端可用，并显示 RFC 1918 局域网访问地址；
- 前后端当前已启动，局域网入口为 `http://192.168.1.57:5173`。

验证：

- `bash -n scripts/quantstone-dev.sh`：通过；
- 本机前端与 `http://192.168.1.57:5173` 均返回 HTTP 200；
- 通过前端代理访问 `/health` 返回 `{"status":"ok"}`；
- 监听状态确认 Vite 与 Uvicorn 分别绑定 `0.0.0.0:5173` 和 `0.0.0.0:8000`。

下一步：

- 从同一局域网的另一台电脑打开 `http://192.168.1.57:5173` 做浏览器验收；
- 如服务器重启后需要自动恢复服务，再配置 systemd，而不是依赖手动运行开发脚本。

遗留问题：

- 当前使用 Vite 开发服务器，适合内网开发，不是生产部署方案；
- 用户级 systemd 当前 `Linger=no`，尚未配置服务器重启后的自动启动。

### 2026-11-19 — Codex（Linux 环境初始化）

完成：

- 确认当前 Linux 工作区为 `/home/quantadmin/project/quantstone-data`，分支与 `origin/main` 一致；
- 使用系统 Python 3.12 创建 `.venv`，安装项目开发依赖；
- 安装前端 npm 依赖并生成生产构建；
- 将本地 `.env` 的 `QUANTSTONE_DATA_ROOT` 配置为 `/home/hhd_data/quantstone-data`；
- 创建正式数据、staging、quarantine、revisions 和日志目录；
- 从空 Catalog 初始化 `var/quantstone-data.db`，实际启动后端并确认数据根目录配置生效；
- 更新 Linux 接管文档和 README 中的 Linux 启动命令。

验证：

- `pytest -q`：48 项通过，1 条 Starlette/httpx 弃用警告；
- `ruff check .`：通过；
- 前端 `npm run build`：通过；
- 后端使用 `--env-file .env` 启动成功，`GET /health` 返回 `{"status":"ok"}`；
- `/home/hhd_data/quantstone-data/logs/application.log` 记录的 `data_root` 为
  `/home/hhd_data/quantstone-data`；验证后后端已关闭。

下一步：

- 配置 TuShare Token，并决定是否使用 systemd 常驻运行；
- 确认 L2 import 根目录、源文件组织方式和目录扫描器设计；
- 确认是否仍需迁移 Windows 历史 Catalog 与数据。

遗留问题：

- 当前 Catalog 为空，未迁移旧环境的 Registry、任务和 TuShare 数据；
- 服务器内网 IP 与最终访问方式尚未写入项目配置；
- 受限执行沙箱会阻塞 AnyIO 的跨线程测试门户，全量测试需在主机环境运行，项目本身验证通过。

### 2026-11-19 — Codex

完成：

- 修复股票信息数据集遗留的旧采集器 key `tushare`，迁移为 `tushare_cn_stock`；
- 将迁移改为基于 SQLite JSON 路径更新，不再依赖 JSON 空格格式；
- 数据集详情新增已发布数据预览面板，动态展示字段和最多 20 行数据；
- 预览空数据、加载状态和读取错误均有独立提示；
- 预览面板支持按一个或多个主键字段精确筛选；无筛选固定返回 20 行，筛选后最多返回 100,000 行；
- 筛选查询返回准确匹配总数，超过上限时在前端明确提示结果已截断；非主键筛选由后端拒绝；
- 预览表格改为 520px 固定高度和虚拟滚动，只渲染视口附近约 32 行，不再用完整 DOM 撑长页面。
- 主键筛选结果支持下载为 CSV 或 Parquet，导出全部匹配行且不受预览上限影响；
- 未提供主键筛选时禁止下载，服务端临时导出文件在响应结束后自动删除。
- 失败、审核异常和已取消的采集器任务支持重试；重试复制为新任务并记录 `retry_of_job_id`，原任务不变；
- 重试复制原任务已经解析完成的执行配置，兼容历史任务中的旧参数；前端创建后立即执行新任务；
- 修复创建任务表单：切换为采集器输入时，如果当前任务目的受支持，不再重置第一步选择。
- 采集任务列表在任务 ID 下方显示按浏览器本地时区格式化的创建时间。
- stock_basic 采集器升级为统一 CollectionResult 协议，并复用通用 snapshot 审核、发布和 Catalog 流程；
- SQLite 启动迁移为现有 stock_basic 数据集补齐 `snapshot + replace_snapshot` 存储策略。
- daily、snapshot 和旧执行路径统一处理上游 HTTP、网络及限流异常；重试耗尽后任务与运行记录保存相同的中文错误原因。
- 前端任务详情将分区“执行明细”与过程“运行日志”分开展示；日志接口从现有 JSON Lines 文件读取，不重复建立日志存储。
- 修复重试与执行结束后的前端缓存同步，旧任务不再替新任务显示“重试中”，失败分区不再残留 `fetching` 状态。
- 采集执行接口改为异步提交：新增 `queued` 状态和单工作线程后台队列，接口立即返回，供应商调用不再占用原始 HTTP 请求。
- 前端改为提交后轮询后台状态；排队任务可直接取消，重试任务提交后自动聚焦新任务。
- 新增持久化维护任务并将年度合并接入共享后台队列；数据集详情可选择年份、提交合并、查看结果和取消排队；
- 修复 stock_basic 启动迁移无法识别 JSON `null` 存储策略的问题。
- 确认大规模 L2 历史迁移不使用浏览器上传：系统工具负责文件传输，后续由显式专用目录扫描器生成清单，再走审核、发布和 Catalog；
- 新增 Linux 内网远程开发交接文档，并移除 Agent 指南对 Windows 绝对路径的依赖。

验证：

- 新增旧采集器绑定迁移测试和主键筛选读取测试；
- `ruff check src tests`：通过；
- 前端 `npm run build`：通过；
- 真实服务验证：无筛选返回 20 行；按 `ts_code` 返回 695 行；按 `trade_date` 返回 5,329 行；非主键筛选返回 422。
- 真实服务验证：同一 `ts_code` 的 CSV 与 Parquet 均导出 695 行，响应后临时文件剩余 0 个。
- 真实服务验证：历史失败任务成功复制为新 `created` 任务，operation、参数和追溯 ID 均正确；验证任务随后删除。
- 隔离数据库和模拟供应商验证：stock_basic 任务进入 `succeeded`，Catalog 生成 `snapshot` 分区，正式 Parquet 可按 `ts_code` 预览；
- 任务日志读取与执行框架测试：6 项通过；前端 `npm run build`：通过。
- 重试状态与执行明细刷新修复后，前端 `npm run build`：通过。
- 后台队列、异步 ASGI 采集、日志及执行框架测试：8 项通过；异步集成测试验证采集器阻塞期间接口已返回 `202 + queued`；前端构建通过。
- 全量 `pytest -q`：48 项通过；前端构建通过；真实服务确认合并接口返回 `202`，维护任务列表可用。

下一步：

- 下一位 Agent 先在 Linux 按交接文档重建环境并跑全量验证；环境稳定后再设计目录扫描器。

遗留问题：

- 本地现有 stock_basic 历史任务不会自动回放发布；需要在 TuShare 恢复后新建或重试任务生成首个正式 snapshot；
- 虚拟滚动解决了 DOM 和布局卡顿，但 100,000 行仍会一次性传输并保存在浏览器内存中。

### 2026-11-18 — Codex

完成：

- 数据读取遇到 Catalog 文件缺失时返回 `409` 并列出路径，不再静默跳过；
- 在打开文件前统一检查查询范围内的 Catalog 文件，避免返回部分结果；
- 日期分区过滤下推到 Parquet/Arrow；
- `limit` 在 Arrow 表阶段截取后才转换为 Python，并在达到上限后停止打开后续文件。

验证：

- 新增缺失文件中止读取、达到 limit 后不打开多余文件的测试；
- `pytest`：40 个测试通过；
- `ruff check src tests`：通过。

下一步：

- 为读取能力封装首版 Python SDK：`describe`、`coverage`、`read`；
- 评估大年度文件按 row group 流式读取，进一步降低 Arrow 内存占用。

遗留问题：

- 当前没有独立的数据读取前端页面；读取错误主要通过 API 返回，概览和热力图负责展示文件异常；
- Parquet 谓词能否跳过 row group 取决于文件统计信息和物理布局。

### 2026-11-18 — Codex

完成：

- 修复股票列表、交易日历等快照任务取消后仍可能发布成功的问题；
- 快照供应商调用前释放 SQLite 写事务，使并发取消请求可以正常落库；
- 在供应商调用返回、审核完成和发布开始前检查取消；
- 发布临界区拒绝取消，避免 `succeeded` 与 `cancelling` 互相覆盖；
- 取消后删除本次暂存结果，任务和运行记录均标记为 `cancelled`。

验证：

- 新增真实并发请求形式的快照取消测试，确认 Catalog 不产生分区；
- `pytest`：38 个测试通过；
- `ruff check src tests`：通过；
- 前端 `npm run build`：通过。

下一步：

- 优化年度文件读取，避免小 `limit` 请求把整年数据转换为 Python 对象；
- 读取遇到 Catalog 文件缺失时返回明确错误，不再静默跳过。

遗留问题：

- 外部供应商的单次网络调用无法强制中断，取消会在该调用返回后生效；
- 执行仍通过同步 HTTP 请求运行。

### 2026-11-18 — Codex

完成：

- 为采集任务增加持久化的任务级错误字段；
- 所有采集执行路径统一在异常退出时落成 `failed`，不再遗留 `running`；
- 应用启动时自动识别并结束上次进程遗留的 `running/cancelling` 任务；
- 前端任务明细直接展示任务失败原因。

验证：

- 增加普通采集器失败状态与应用重启恢复测试；
- `pytest`：37 个测试通过；
- `ruff check src tests`：通过；
- 前端 `npm run build`：通过。

下一步：

- 完善快照任务的协作式取消语义；
- 优化年度文件读取，避免小 `limit` 请求把整年数据转换为 Python 对象。

遗留问题：

- 执行仍通过同步 HTTP 请求运行；服务重启会安全标记失败，但不会自动续跑；
- 取消仍只能在采集器调用或分区边界之后生效。

### 2026-11-18 — Codex

完成：

- 修复年度文件生成后再次合并可能只保留最新 delta、导致全年数据丢失的问题；
- 二次合并按 Catalog 当前文件指向过滤已有年度文件，并加入修复后的最新日文件；
- 合并前校验所有源文件存在、包含逻辑分区字段，且结果覆盖全部预期分区；
- 覆盖已有年度文件前先将旧版本移入 `revisions/`。

验证：

- 新增“先合并、修复单日、再次合并”的回归测试；
- `pytest`：36 个测试通过；
- `ruff check src tests`：通过。

下一步：

- 修复普通采集器异常后任务可能停留在 `running` 的状态问题；
- 完善快照任务取消语义和年度文件读取性能。

遗留问题：

- 文件替换与 SQLite Catalog 提交尚未形成可崩溃恢复的跨文件系统事务；
- `revisions/` 仍没有自动清理策略。

### 2026-11-18 — DeepSeek Harness

完成：

- 新增 `catalog_files` 表，`catalog_partitions` 通过 `file_id` 引用物理文件；
- 发布时同时写入文件行和分区行，替换分区时清理不再被引用的旧文件；
- 概览与存储统计改为按文件去重，多个分区共用一个文件时不会重复累计体积；
- 新增读取接口，按 `file_id` 分组，每个文件只打开一次；
- 新增年度合并接口，把日文件合并为年度文件，旧文件保留在 `revisions/`；
- 已验证 daily 2024 年合并：242 个文件合成 1 个，行数 1,293,893 不变。

验证：

- `pytest`：35 个测试通过（新增 3 个读取与合并测试）；
- `ruff check src tests`：通过；
- 本地实测：合前读一年打开 242 个文件，合后打开 1 个；存储体积从 167.4 MB 降到 147.6 MB。

下一步：

- 合并 daily 2025 与 2026 年数据；
- 评估是否在发布后按年自动触发合并。

遗留问题：

- 合并命令是同步 HTTP 请求，年份跨度大时会长时间占用连接；
- 没有版本回滚，误合并只能从 `revisions/` 人工恢复；
- 合并后旧文件仍在 revisions 目录，占用磁盘，需要清理策略。

### 2026-11-18 — DeepSeek Harness

完成：

- 覆盖接口为失败分区补充审核原因：读取任务的 `review.json`，把规则错误压缩成中文说明；
- 悬停热力图失败格子可以看到具体原因，例如“接口返回 0 行；分区日期不一致”。

验证：

- `pytest`：32 个测试通过；
- `ruff check src tests`：通过；
- 本地接口：2026-11-18 显示“接口返回 0 行；分区日期不一致（期望 2026-11-18，实际 []）”。

下一步：

- 校验前判断供应商当日数据是否已就绪，避免把“尚未发布”误判为审核失败。

遗留问题：

- 审核原因只读取任务级 `review.json`；历史上已删除任务的分区失败原因无法还原。

### 2026-11-18 — DeepSeek Harness

完成：

- 新增 `GET /api/v1/overview/coverage?days=N`：按数据集和交易日返回覆盖状态及明细；
- 新增覆盖热力图：完整、缺失、采集失败、文件异常、待采集五种状态，支持 30/90/250 天切换；
- 当天未采集记为“待采集”，取消任务产生的残留失败运行不计为数据问题；
- 点击热力图格子进入对应数据集详情。

验证：

- `pytest`：31 个测试通过（新增 4 个覆盖相关测试）；
- `ruff check src tests`：通过；
- 前端 `npm run build`：通过；
- 本地接口返回：daily 最近 30 个交易日 29 个完整、1 个审核失败（2026-11-18）。

下一步：

- 热力图支持横向缩放或按需加载更长区间；
- 为失败单元格展示审核错误摘要。

遗留问题：

- 热力图按当前交易日历的覆盖范围取数，日历未覆盖的日期无法显示；
- 同一天多次采集时，失败与成功运行并存的情况只按“有分区即完整”处理。

### 2026-11-18 — DeepSeek Harness

完成：

- 新增数据集概览接口 `GET /api/v1/overview/datasets`：聚合分区数、文件数、行数、体积、
  最新分区、缺失文件和按交易日历计算的覆盖率；
- 新增“数据概览”页面，数据卡网格展示上述指标，点击卡片进入数据集详情；
- 侧边栏默认首页改为概览。

验证：

- `pytest`：27 个测试通过（新增 1 个概览测试）；
- `ruff check src tests`：通过；
- 前端 `npm run build`：通过；
- 本地接口返回：daily 695 个分区、3,765,507 行、167.4 MB、覆盖 99.9%。

下一步：

- 概览中加入按时间维度（数据集 × 交易日）的覆盖热力图；
- 数据卡支持筛选（状态、供应商、品种）。

遗留问题：

- 覆盖率只统计最早已发布分区到今天的范围，不包含更早的历史缺口；
- 概览接口每次请求都读取日历 Parquet，数据量大后可加缓存。

### 2026-11-18 — DeepSeek Harness

完成：

- 任务列表改为点击行就地展开明细：进度、分区级运行记录、行数、文件与错误原因；
- 移除前端“数据存储”入口和页面组件，存储概览与 Catalog 查询仍保留为后端 API；
- 修复取消状态竞态：先落库 `cancelling` 再通知执行线程，避免任务卡在“正在取消”；
- 修复列表按钮被挤成竖排、收集器 key 与 operation 换行错位、确认删除颜色不明显的问题。

验证：

- `pytest`：26 个测试通过；
- `ruff check src tests`：通过；
- 前端 `npm run build`：通过。

下一步：

- 在界面上验证明细面板与取消流程；
- 继续 CatalogFile / CatalogPartition 拆分与年度合并。

遗留问题：

- 明细面板一次渲染全部分区，分区数很多时未做分页或虚拟滚动；
- 数据存储信息目前只能通过 API 查看。

### 2026-11-18 — DeepSeek Harness

完成：

- 增加执行期任务状态：`running`、`cancelling`、`cancelled`；
- 增加任务进度接口，按交易日历给出预期分区、已发布数和百分比；
- 增加协作式取消接口，在分区边界检查取消请求；
- 增加任务记录删除接口，仅允许非执行状态，保留已发布数据；
- 前端任务列表轮询进度、显示 `已发布 N / 总数`、支持取消和删除，执行按钮增加旋转动画。

验证：

- `pytest`：26 个测试通过（原 22 + 新增 4）；
- `ruff check src tests`：通过；
- 前端 `npm run build`：通过。

下一步：

- 服务重启后在界面上验证进度、取消和删除；
- 解决服务重启把 `running` 任务留在中间状态的问题（启动时标记中断或任务租约）。

遗留问题：

- 取消只在分区边界生效；
- 执行状态与取消请求均为进程内状态，重启后需要人工处理残留 `running` 任务。

### 2026-11-18 — DeepSeek Harness

完成：

- 新增统一执行框架 `execution.py`：滑动窗口限流、限流等待、限流/网络错误指数退避重试；
- 采集、快照和手动入库三条执行路径统一经过 `run_operation`；
- TuShare daily 首次与增量共享每分钟 50 次窗口，限流错误可识别并重试；
- 补充执行框架测试，覆盖窗口等待、跨 operation 共享窗口、重试与放弃。

验证：

- `pytest`：22 个测试通过（原 17 个 + 新增 5 个）；
- `ruff check src tests`：通过；
- 前端 `npm run build`：通过；
- 未调用真实 TuShare 接口，避免消耗额度。

下一步：

- 在限流框架下新建 daily 增量任务，从 2024-04-30 之后续跑；
- 继续拆分物理 CatalogFile 与逻辑 CatalogPartition。

遗留问题：

- 执行仍同步阻塞 HTTP 请求，长范围采集需要数分钟；
- 限流器为进程内状态，多进程部署需改为共享限流。

### 2026-11-18 — Codex

完成：

- 为日期分区契约增加显式交易日历依赖及旧 daily 数据迁移；
- daily 运行日期改由已发布交易日历生成，休市日不再调用供应商接口；
- 缺少、未启用、未发布、文件缺失和覆盖不足均返回可操作的中文提示；
- 审核异常前端展示失败日期和具体规则说明。

验证：

- `pytest`：17 个测试通过；
- `ruff check src tests`：通过；
- 前端 `npm run build`：通过。

下一步：

- 为 TuShare daily 执行加入每分钟 50 次的限流、等待和可恢复重试；
- 再新建 daily 增量任务，从 Catalog 最新分区 2024-04-30 之后继续。

遗留问题：

- 当前执行器没有供应商限流调度，长日期范围会在第 51 次 daily 请求处失败；
- 交易日历任务 `745d56b3-398d-4880-942c-2dba41d22bd2` 已成功，两个 daily 失败任务继续保留用于追溯；
- Codex 启动的前后端服务均已关闭，8000 和 5173 端口已释放。

### 2026-11-18 — Codex

完成：

- 将侧边栏预留入口改为可用的“数据存储”页面；
- 新增存储概览 API 和全量 Catalog 分区查询；
- 展示数据根目录、正式文件、行数、体积、SHA-256、暂存和缺失文件指标。

验证：

- `pytest`：15 个测试通过；
- `ruff check .`：通过；
- 前端生产构建：通过；
- 当前本地接口返回 1 个正式文件、5,329 行、0 个缺失文件。

下一步：

- 增加 Catalog 文件详情与任务追溯跳转；
- 后续拆分 CatalogFile 与 CatalogPartition 后调整物理体积统计。

遗留问题：

- 当前 Catalog 模型仍是一条逻辑分区直接保存一个文件路径，尚未支持多个分区共用年度文件。

### 2026-11-18 — Codex

完成：

- 新增结构化日志系统；
- 应用日志写入 `<data_root>/logs/application.log` 并轮转；
- 带 job_id 的记录同时写入 `logs/collection/<job_id>.log`；
- 接入采集、审核、发布、文件暂存和 HTTP 写请求事件；
- 增加敏感字段递归脱敏。

验证：

- `pytest`：15 个测试通过；
- `ruff check .`：通过；
- 本地服务重启后成功生成 `application_started` JSON 日志。

下一步：

- 在前端增加任务日志查看入口；
- 为日志增加保留期限配置和下载 API。

遗留问题：

- 当前日志只保存在本机文件系统，尚无前端查看和集中检索。

### 2026-11-18 — Codex

完成：

- 接入 `tushare.cn.stock.trade_cal`，采用 SSE 日历和 snapshot 存储；
- 增加交易日历采集 operation、审核器和快照发布测试；
- 当前本地 Registry 已创建并启用该数据集。

验证：

- `pytest`：14 个测试通过；
- `ruff check .`：通过。

下一步：

- TuShare 每小时一次的接口额度恢复后，重新执行 1990-01-01 至 2027-12-31 首次采集；
- 使用已发布交易日历替换 daily Planner 的工作日临时判断。

遗留问题：

- 首次真实采集因先前分段请求耗尽每小时一次额度而失败，尚无正式快照；
- 失败任务已保留用于追溯，Catalog 未写入半成品。

### 2026-11-18 — Codex

完成：

- 删除 `datasets/` 代码目录并迁移采集实现；
- 建立按数据集 ID 注册的审核器结构和通用检查；
- 将日 K 发布与 Catalog 更新抽取为通用发布模块；
- 保持 TuShare daily 端到端闭环通过。

验证：

- `pytest`：13 个测试通过；
- `ruff check .`：通过；
- 前端生产构建：通过。

下一步：

- 为手动 Parquet 入库接入同一审核和发布流程；
- 继续拆分物理 CatalogFile 与逻辑 CatalogPartition。

遗留问题：

- 当前发布仍缺少崩溃后的原子恢复机制；
- stock_basic 审核通过后尚未接入正式发布。

### 2026-11-18 — Codex

完成：

- 以 `tushare.cn.stock.daily` 跑通单日真实采集闭环；
- 新增 Parquet 协议、Collection Run、审核、delta 发布和 CatalogPartition；
- 更新真实 daily 数据契约并配置 `yearly_with_delta` 存储策略；
- 将旧 stock_basic 输出从 CSV 改为 Parquet。

验证：

- 真实采集 2024-01-02：5,329 行，Parquet 243,312 字节，审核和 Catalog 登记成功；
- `pytest`：12 个测试通过；
- `ruff check .`：通过；
- `npm run build`：通过。

下一步：

- 拆分物理文件和逻辑分区 Catalog，并实现年度合并与权威交易日历。

遗留问题：

- 当前 Planner 只排除周末，尚未排除 A 股节假日；
- 跨多个交易日执行会受到 TuShare 账号限频，需要调度与重试。

### 2026-11-17 — Codex

完成：

- 建立数据集到采集器/审核器的最小代码绑定；
- 实现 TuShare stock_basic 真实采集、CSV staging 和审核报告；
- 取消首次/修复/重建任务一律要求日期范围的错误假设；
- 增加任务执行接口和端到端模拟测试。

验证：

- TuShare 真实接口连通，单次 `L` 状态查询返回 5580 行；
- 完整同步连续调用触发账号频率限制，因此首版范围收窄为 `L`；
- `pytest`：10 个测试通过；
- `ruff check .`：通过；
- `npm run build`：通过。

下一步：

- 增加通用任务参数、供应商限流以及数据库审核追溯记录。

遗留问题：

- 尚未发布正式数据；当前审核通过结果仍只存在 staging。

补充：已增加前端“执行采集”和“查看审核”操作，以及审核报告查询接口。
补充：数据集专用实现改为严格映射数据集 ID 的目录结构。
补充：已实现采集器注册模型与前端采集器目录；联合操作目前可识别但尚不能执行。
补充：采集绑定进一步改为 `purpose → collector_key + operation`，旧 stock_basic 绑定已自动迁移。

### 2026-11-17 — Codex

完成：

- 新增采集任务导航、统计和任务记录列表；
- 新增任务创建表单；
- 支持选择任务目的、日期范围和输入方式；
- 支持创建任务后立即上传手动文件；
- 支持为等待文件的任务补充上传；
- 在界面中明确区分 staging 与正式入库。

验证：

- 浏览器完成手动文件创建、上传和状态展示联调；
- `npm run build`：通过；
- `pytest`：9 个测试通过；
- `ruff check .`：通过；
- 验收产生的临时数据库记录和文件已清理。

下一步：

- 实现 Planner 和模拟采集器。

遗留问题：

- 还没有解析、校验、Catalog 和正式发布。

### 2026-11-17 — Codex

完成：

- 新增采集任务数据模型和 API；
- 支持四种任务目的及两种输入方式；
- 实现手动文件上传到外部 staging；
- 记录文件名、相对路径、大小和 SHA-256；
- 增加任务规则和文件落盘测试。

验证：

- `pytest`：9 个测试通过；
- `ruff check .`：通过。

下一步：

- 实现采集任务前端页面和手动文件上传界面。

遗留问题：

- 还没有 Planner、解析、校验、Catalog 和正式发布。

### 2026-11-17 — Codex

完成：

- 汇总此前讨论，新增完整架构与设计决定文档；
- 新增 Agent 接力机制；
- 将接力流程写入 `AGENTS.md`。

验证：

- 本次只修改 Markdown 文档；
- 已运行 `git diff --check`。

下一步：

- 按“建议下一步”开始采集任务模块。

## 后续 Agent 更新模板

### 2026-11-24 — Codex（目录导入记录完全并入任务表）

完成：

- 修正上一版只合并创建入口、扫描记录仍单独展示的问题；
- 创建服务器目录任务时立即建立关联 CollectionJob，统一状态为扫描中、待确认、导入中、成功、
  失败或取消；
- 采集任务行直接提供扫描清单、确认导入和取消操作，展开后沿用执行明细与日志；
- 删除前端独立 ImportJobs 组件，ImportJob 仅保留为后端 Manifest 内部记录；
- 删除目录采集任务时同步删除内部 ImportJob、Manifest 和任务级 staging。

验证：

- 状态 Schema、审核报告与 SQLite 并发定向测试：5 项通过；
- `ruff check src tests`：通过；
- `web/npm run build`：通过。
- 服务重启后用空目录创建真实修复任务：API 创建响应立即返回 `collection_job_id`，统一任务列表
  可查到 `input_method=directory_import`、`operation=repair` 的同一记录；测试任务、内部 ImportJob
  和空目录随后全部清理，服务保持正常。

下一步：无。

遗留问题：既有 TestClient 集成测试在当前 Codex 环境仍卡在 lifespan 启动；该现象在反向应用
功能改动后同样存在。

### 2026-11-23 — Codex（目录导入合并到采集任务）

完成：

- 移除采集导航中的独立“目录导入”页面入口；
- “创建采集任务”的数据输入增加“服务器目录”，支持扫描操作、源目录、移动/复制和日期范围；
- 扫描中与待确认的目录任务直接显示在采集任务页，确认后生成普通 CollectionJob，完成任务只在
  统一任务记录中显示，避免重复；
- 目录导入保留内部 ImportJob/Manifest，并把用户选择的首次、增量、修复或重建目的传递给最终
  CollectionJob；
- 复权因子回填任务 `58c45fd3-1d60-4d1e-8e12-618930d59a24` 已成功，2,887 个分区全部发布。

验证：

- `pytest tests/test_review_reports.py tests/test_catalog_concurrency.py tests/test_import_schemas.py -q`：
  5 项通过；
- `ruff check src tests`：通过；
- `web/npm run build`：通过。
- 前后端已安全重启；健康检查、2 个扫描器/4 个操作和前端页面均正常，线上 OpenAPI 已包含
  `ImportJobCreate.purpose`。

下一步：无。

遗留问题：当前 Codex 环境运行既有 TestClient 集成测试仍会卡在 lifespan 启动，反向应用本轮改动
后同样复现；定向纯后端测试和前端类型构建均已通过。

### 2026-11-23 — Codex（目录导入审核报告）

完成：

- 目录导入在创建关联采集任务时，将 Manifest 中已通过的逐文件审核结果写成通用
  `staging/<collection_job_id>/review.json`，并登记到采集任务 `staged_path`；
- “查看审核”兼容旧目录导入任务：缺少任务级报告时从对应 ImportJob Manifest 自动补建；
- 报告只汇总实际进入导入流程的 `ready` 分区；源目录缺文件、重复项等扫描结果继续在目录导入
  Manifest 中展示，不会把已经成功的采集任务错误标记为审核失败。

验证：

- 审核报告与 SQLite 并发定向测试：4 项通过；
- `ruff check src tests`：通过。

下一步：复权因子任务运行期间不重启后端；任务结束后再重启以加载旧任务自动补建逻辑。

遗留问题：无。

### 2026-11-23 — Codex（SQLite 并发写入保护）

完成：

- SQLite 连接启用 WAL、60 秒写锁等待、`synchronous=NORMAL` 与外键检查；
- 采集发布、目录导入发布和年度合并共享进程内 Catalog 短事务锁，不限制采集与审核阶段并发；
- 分区发布统一在锁内完成文件移动、Catalog 写入和提交，提交失败后回滚 Session 并将文件退回 staging；
- 日分区和快照采集的异常路径在复用 Session 前显式回滚，避免失败事务污染后续状态写入；
- 新增并发配置、写入串行化和发布失败文件恢复测试。

验证：

- `pytest tests/test_catalog_concurrency.py -q`：3 项通过；
- `ruff check src tests`：通过；
- 常驻服务重启后真实 SQLite 连接为 `journal_mode=wal`、`busy_timeout=60000`、
  `synchronous=1 (NORMAL)`、`foreign_keys=1`，健康检查通过；
- 中泰逐笔委托剩余导入与复权因子回填并发运行：导入任务
  `fe513445-b6bb-4e8a-b2ee-2bf1d1ca3450` 成功发布 1,109 个分区、58,544,360,738 行，期间
  复权因子成功发布首批 100 个分区，未再出现 `database is locked`；中泰委托 Catalog 当前共
  2,213 个分区、80,424,316,422 行；
- 全量 pytest 在当前 Codex 执行环境中卡在既有 TestClient lifespan 启动；临时反向应用全部改动后
  同一既有用例仍然卡住，因此未获得本轮全量测试结果，需在常驻服务重启前后继续验证。

下一步：

- 复权因子回填任务 `58c45fd3-1d60-4d1e-8e12-618930d59a24` 仍在运行，任务结束前不得重启后端；
- 任务结束后核对最终分区数与错误日志，再执行所需年度合并。

遗留问题：

- SQLite 方案只支持当前单进程后端；多 worker 或多实例部署需要 PostgreSQL 或跨进程锁；
- 文件移动后进程被强制终止的崩溃窗口仍需启动对账机制处理。

### 2026-11-23 — Codex（TuShare A股复权因子）

完成：

- 新增预置契约 `tushare.cn.stock.adj_factor`，字段为 `ts_code/trade_date/adj_factor`，主键为
  `ts_code + trade_date`，复用 A 股交易日历与 `yearly_with_delta` 日分区布局；
- 新增首次、增量采集器和专用审核器，检查 Schema、非空、主键、分区日期以及复权因子非空且大于 0；
- 数据集已在真实 Registry 创建、启用并归入“A股数据”；真实单日 `2026-11-20` 采集审核通过，
  返回 5,585 行；
- 首次范围与日 K Catalog 完全一致：`2015-01-05` 至 `2026-11-20`，共 2,887 个交易日；
- 根据真实代理行为新增英文 `Rate limit exceeded` 识别，并将 Python `TimeoutError` 纳入通用重试；
  `adj_factor` 使用每分钟 150 次滑动窗口、供应商并发 1、单分区最多 5 次重试。

验证：

- `pytest -q`：86 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过；
- 真实单日采集、审核、发布：通过。

当前任务：

- 全范围首次采集任务 `60cfe1cf-8f37-4632-bd4e-3e8ddecbe1c1` 正在运行；不得在任务结束前重启后端；
- 已发布分区会逐日保留；任务完成后核对分区数、日期范围、失败分区和总行数，再执行年度合并。

遗留问题：全范围回填受代理频率限制，仍需等待后台任务完成。

### 2026-11-23 — Codex（TuShare 股票曾用名全流程）

完成：

- 新增预置契约 `tushare.cn.stock.namechange`，保留官方六个字段，复合主键为
  `ts_code + start_date + name`；
- 新增全量 snapshot 采集器、增量全量替换入口和专用审核器，不按股票拆分物理文件；
- 代理无参数实测返回 14,266 行，六个字段完整，仅当前有效名称的 `end_date` 合理为空，复合主键无重复；
- 已在真实 Registry 创建并启用数据集，归入“A股数据”，首次采集任务
  `1e7c6e4c-c64f-4416-b80c-cd972bbe35f7` 成功发布；
- 正式 Catalog 为一个 `snapshot` 分区，14,266 行、217,918 字节，审核 0 错误；样例
  `600848.SH` 可查询到 6 条连续名称历史，当前“上海临港”的 `end_date` 为空。

验证：

- `pytest -q`：83 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过；
- 真实采集、审核、发布、Catalog 与行查询：通过。

下一步：无。

遗留问题：无。

### 2026-11-23 — Codex（日更数据总完成率）

完成：

- 日更完成率接口新增跨数据集汇总，按所有参与统计的数据集应完成项加权计算，不对各数据集百分比做简单平均；
- 日期分区数据集以最近 N 个交易日的应覆盖分区计数（含当天待采集分区），快照型日更数据集各计一个应完成项；
- 概览页在明细折叠区上方显示总百分比、总进度、完成/应完成数量和异常汇总，原有数据集明细保留。

验证：

- `pytest -q`：82 项通过（1 条 Starlette/httpx 弃用警告）；
- `ruff check .`：通过；
- `web/npm run build`：通过；

下一步：无。

遗留问题：无。

交接时用最新内容替换或更新上面的“当前状态”“建议下一步”和“已知问题”，并在此处追加一条简短记录：

### 2026-11-24 — Codex（Wind L2 百度网盘采集器）

完成：

- 阅读并迁移 `var/wind-l2-automation` 的分享查找、转存、大小校验和多连接下载逻辑；
- 新增 `wind_l2_sz` 采集器，订单/成交各有首次和增量入口，既有两个 Wind 数据集自动补绑定；
- 压缩包在服务器本地通过 `7z` 解压，GBK CSV 用 PyArrow 分批转换为现有深市契约 Parquet；
- 订单和成交共享日压缩包与解压目录并串行处理，两种输出完成后清理原始工作文件；
- 新增 Linux 依赖安装脚本，锁定 BaiduPCS-Py 提交并处理其 Python 3.12 构建兼容问题；
- 旧自动化 Cookie 已迁移到项目未提交 `.env` 的 `WIND_L2_BAIDUPCS_COOKIE`，只读认证检查通过。

验证：

- `pytest tests/test_wind_l2_collector.py -q`：3 项通过；
- 小样本覆盖 GBK、深市过滤、异常委托价、可空成交代码和契约 Schema；
- Linux BaiduPCS-Py 可导入，`aget` 可执行文件可发现，百度网盘只读认证检查通过；
- `ruff check .`：通过；`npm run build`：通过。
- 全量 `pytest -q` 在当前 Codex 环境 60 秒内无输出并超时，与既有 TestClient lifespan 卡住问题一致。

下一步：从界面分别为 Wind 深市逐笔委托和逐笔成交创建同一天任务，首次真实下载时观察网盘速度、
压缩包内部目录结构和单日转换耗时；本轮未主动下载数 GB 的真实日包。

遗留问题：当前只实现已确认契约的深市股票；沪市需要独立契约和转换器。

### 2026-11-24 — Codex（采集器日期修复任务）

完成：

- 按日期分区且已绑定采集器的数据集，在创建采集器任务时显示“缺口修复”；
- 修复优先复用显式 repair 绑定，否则复用 incremental，只有 initial 时再回退到 initial；
- 修复表单强制选择开始和结束日期，单日修复可选择同一天，日期会写入任务并逐交易日执行；
- 后端同步校验修复日期，快照数据集不会自动获得修复绑定。

验证：

- `pytest tests/test_collection_binding.py -q`：3 项通过；
- `ruff check .`：通过；
- `npm run build`：通过。

下一步：无。

遗留问题：无。

### 2026-11-24 — Codex（安全年度合并）

完成：

- 年度合并以 Catalog 当前有效逻辑分区为准，已有年度文件只读取仍由它承载的日期，修复日期采用最新 delta；
- Parquet 改为批次流式读取和写入，不再把整个年度一次性载入内存；
- 候选文件发布前校验分区集合和逐日行数，并重新比对 Catalog 输入快照；输入变化时拒绝覆盖；
- 年度文件替换与 Catalog 切换支持数据库失败恢复，旧 delta 仅在 Catalog 成功切换后归档；
- 数据集详情页说明合并会按当前有效分区重建并在审核后整体切换。

验证：

- `pytest tests/test_safe_compaction.py -q`：3 项通过；
- `ruff check .`：通过；
- `npm run build`：通过；
- 既有 TestClient 测试在当前 Codex 环境仍卡在 lifespan 启动，定向 `tests/test_storage.py` 90 秒无输出超时。

下一步：无。

遗留问题：旧 delta 归档失败会在维护任务结果的 `cleanup_warnings` 中保留，之后可人工清理，不影响年度文件生效。

### 2026-11-24 — Codex（任务列表列对齐）

完成：

- 任务列表的表头和数据行统一使用固定列轨道，操作按钮数量不再改变整行列宽；
- 操作列预留三枚常用按钮的空间，长采集器标识在输入方式列内换行；
- 窄屏继续通过表格横向滚动查看完整内容。

验证：

- `npm run build`：通过；
- `ruff check .`：通过；
- `pytest -q`：当前 Codex 环境 60 秒内无输出并超时，与本文件已记录的 TestClient lifespan
  卡住现象一致；本轮仅修改前端 CSS，不涉及后端逻辑。

下一步：无。

遗留问题：无。

### 2026-11-24 — Codex（2026 年分钟数据 CSV 兼容）

完成：

- 定位 2026 年年度包失败原因为 `sh601091_2026.csv` 的未使用“名称”列包含未转义双引号，
  DuckDB 自动识别引用符后无法解析；
- 分钟 CSV 改为固定逗号分隔、禁用引号语义、非严格 RFC 模式并先按字符串读取，契约字段仍
  显式转换；列数错误仍会失败，不启用 `ignore_errors`；
- 清除真正的空白占位 CSV；年度转换失败时保留 zip、解压文件和 DuckDB 临时现场，成功后
  继续清理；
- 真实任务 `91b1f4e1-1422-41ab-9391-d056880a5bfa` 成功发布 2026-01-05 至
  2026-11-23 共 214 个分区、268,373,990 行；分钟数据累计 2,888 个分区、
  2,717,268,498 行。

验证：

- `tests/test_minute_1m_collector.py`：6 项通过；
- 真实 2026 年年度包完成下载、转换、审核和发布，最后分区 1,258,984 行；
- `ruff check .`：通过；
- 全量 `pytest -q` 运行 120 秒无输出，按项目已知 TestClient lifespan 卡住问题中止；定向测试
  已覆盖本次改动。

下一步：无。

遗留问题：失败任务记录保留作为审计历史，无需再次重试。

### 2026-11-25 — Codex（刷新入口合并与缓存目录统一）

完成：

- 概览页顶部“刷新全部”同时刷新概览、日更完成率、最近任务和覆盖热力图，移除热力图内重复按钮；
- 任务页“刷新任务”同时刷新任务列表和当前展开的执行明细/日志，运行任务继续每 2.5 秒自动轮询；
- 数据预览“刷新”改为“重新读取”，使用已应用的查询条件重新读取物理数据；
- Wind L2 工作目录从 `downloads/wind_l2` 统一迁到数据根的 `cache/wind_l2`；分钟数据继续使用
  `cache/minute_1m`，集合竞价预留 `cache/auction_process`。

验证：

- Wind L2 与分钟采集器定向测试：10 项通过；
- `ruff check .`：通过；
- `web/npm run build`：通过。

下一步：实现 `tb_lhsjk.cn.stock.auction_process` 契约、百度网盘采集器、转换器和审核器，并用一天
真实数据跑通全流程。

遗留问题：集合竞价流程尚未进入代码实现。

### 2026-11-25 — Codex（集合竞价过程数据）

完成：

- 新增并启用 `tb_lhsjk.cn.stock.auction_process`，注册首次、增量、修复采集操作和专用审核器；
- 百度分享改用 BaiduPCS 分享元数据遍历，不依赖易变化的网页 `locals-data`；
- 首次优先月包、缺失时回退单日 CSV，缓存位于 `cache/auction_process`；
- 主键增加 `event_seq`，真实样本 35 条同代码同时间重复记录全部保留；
- 真实任务 `e9b89ab5` 成功发布 2026-11-24 分区，共 274,612 行、5,581 只证券。

验证：

- 转换器测试通过，真实样本行数、时间范围和重复记录核对通过；
- `ruff check .` 通过；真实百度下载、转换、审核、发布全流程成功。

下一步：用户可从界面按月包范围创建历史首次采集；完成整年后执行年度合并。

遗留问题：月包路径按分享根目录的 `YYYYMM.zip` 匹配，若供应商调整目录层级，元数据遍历仍按
文件名查找，不受层级变化影响。

### 2026-11-25 — Codex（集合竞价按月历史补采入口）

- 修复首次发布后无法继续使用月包的问题：`auction_process_repair` 改为复用月包采集函数；
- 创建任务中的目的显示为“范围补采 / 修复”，选中集合竞价数据集后明确显示“集合竞价按月
  历史补采 / 修复”，支持单日、整月和跨月范围；
- 增量更新继续读取单日 CSV，不改变日常更新行为。

### 2026-11-25 — Codex（修复任务日期参数传递）

完成：

- 修复创建“范围补采 / 修复”任务时日期范围只写入任务字段、未传给采集器参数的问题；
- 所有明确填写日期范围的采集任务现在统一将 `start_date`、`end_date` 传给采集器；
- 增加接口级回归测试，覆盖集合竞价修复操作的必填日期参数校验。

验证：

- `ruff check src/quantstone_data/collection.py tests/test_collection.py`：通过；
- 实际后端成功创建 2026-10-01 至 2026-10-31 的集合竞价修复任务，任务参数包含完整日期范围；
- 验证任务未执行并已删除；定向 `TestClient` 测试受项目已知 lifespan 卡住问题影响未结束。

下一步：无。

遗留问题：无。

### 2026-11-25 — Codex（集合竞价百度转存重试）

完成：

- 定位任务 `9850dd3b` 在成功发布 2020-01-02 至 2020-03-31 后，转存 `202004.zip`
  时遇到百度网盘错误码 4“存储异常”；此前 58 个成功分区均已保留；
- 将百度错误码 4 转换为可重试的临时异常，按采集器策略最多重试 3 次；
- 从 2020-04-01 创建续采任务 `98d8d5e6`，避免重复采集已成功的 1—3 月。

验证：

- 集合竞价采集器与执行框架测试：9 项通过；
- `ruff check`：通过；
- 续采任务已成功发布 2020 年 4 月全部 21 个交易日，继续向后运行且失败数为 0。

下一步：

- 任务 `98d8d5e6-3a2b-4dc4-a499-557a43ec0676` 已成功发布至 2020-06-19，随后因
  2020-06-22 的 09:26:03 快照超过原审核上限而停止；审核窗口已修正为 09:15—09:30；
- 服务已重启并加载新规则，续采任务 `df2d51f5-9822-4802-96d1-3ecfd7f2a2ef` 从
  2020-06-22 开始运行，已越过原失败日期并发布至 2020-07-01，失败数为 0；任务运行期间
  不要重启后端。

遗留问题：无。

### 2026-11-25 — Codex（Python 量化数据读取 SDK）

完成：

- 新增 `QuantStoneClient`，支持 `datasets`、`describe`、`coverage`、`read`、
  `read_pandas` 和 `download`；
- SDK 通过 HTTP API 读取，不依赖服务器 Catalog 文件路径；`read` 返回保留契约类型的
  PyArrow Table；
- 下载接口支持 `start` / `end` 日期范围，服务端只读取对应 Catalog 分区；
- 新增数据集覆盖摘要接口，返回分区数、行数、体积、首尾分区和缺失文件数；
- 分区数据要求日期范围或主键条件，避免误读完整逐笔数据集；快照允许完整读取。

验证：

- SDK 数据集发现、URL 参数和 Parquet 类型保真测试通过；
- 服务重启后通过真实 HTTP API 读取分钟数据：`000001.SZ` 的 2026-11-24 数据返回 241 行，
  Arrow Schema 与契约一致；
- `ruff check` 通过；同步 `TestClient` 集成测试仍受项目已知 lifespan 卡住问题影响。

下一步：

- 无。

遗留问题：

- 当前 API 仅适合可信内网，尚未加入访问令牌、权限和限流。

### 2026-11-25 — Codex（分钟数据供应商标识迁移）

完成：

- 将临时渠道代号 `tb_minute` 更正为卖家代号 `tb_lhsjk_023199`，数据集 ID 改为
  `tb_sbkj2077.cn.stock.minute_1m`；
- 同步修改预置契约、采集器、审核器、测试和文档；
- 新增启动迁移，原地更新 Registry、Schema、Catalog、任务和发布路径，并在同一数据盘直接
  重命名数据集目录，不复制或重写 Parquet。

验证：

- 迁移和分钟采集器测试 7 项通过；
- 使用正式 Catalog 备份演练迁移：2,889 个分区、2,718,527,482 行、9 条历史任务全部保留，
  旧路径为 0，外键检查无异常；
- `ruff check .` 和源码编译通过。

下一步：

- 无。

遗留问题：无。正式迁移已完成：新 ID 保留 2,889 个分区、2,718,527,482 行和 9 条历史
任务，物理目录原地改名为 `datasets/tb_sbkj2077.cn.stock.minute_1m`（34 GB），旧路径为 0，
外键与文件完整性正常；真实覆盖 API 返回 2015-01-05 至 2026-11-24、缺失文件 0。

```markdown
### YYYY-MM-DD — Agent 名称

完成：

- ...

验证：

- ...

下一步：

- ...

遗留问题：

- ...
```
