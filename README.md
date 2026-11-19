# QuantStone Data

QuantStone Data 是一个用于注册、采集、校验、存储和查询金融数据集的开源系统。

项目直接管理供应商定义的数据集，不强制不同供应商采用统一的业务数据结构。每个数据集都有明确的数据契约，描述字段、采集方式、校验规则、存储策略和 Schema 版本。

## 当前目标

第一个里程碑是实现数据集注册中心，并走通一个数据集的完整生命周期：

1. 注册数据集及其字段。
2. 创建首次采集或增量更新计划。
3. 将数据采集到临时区。
4. 按数据集契约校验数据。
5. 发布数据文件并更新目录。

## 数据集 ID

数据集 ID 遵循以下结构：

```text
<provider>.<region>.<instrument>.<dataset>[.<market>]
```

示例：

```text
tushare.cn.stock.daily
tb_l2.cn.stock.l2_order.sh
tb_l2.cn.stock.l2_trade.sz
```

完整规则见 [数据集 ID 命名规范](docs/dataset-id.md)。

项目的完整定位、架构原则、当前实现与待定事项见
[项目架构、设计原则与开发约定](docs/architecture-and-decisions.md)。

Linux 内网远程开发的迁移步骤和当前限制见
[Linux 远程开发交接](docs/linux-remote-development.md)。

## 本地开发

Linux 启动后端：

```bash
python3.12 -m venv .venv
TEMP="$PWD/var/tmp" TMP="$PWD/var/tmp" .venv/bin/python -m pip install -e '.[dev]'
.venv/bin/uvicorn quantstone_data.main:app --env-file .env --host 0.0.0.0 --port 8000
```

仓库根目录的 `.env` 至少配置 `QUANTSTONE_DATA_ROOT`；使用 `.env` 时启动命令必须包含
`--env-file .env`。Windows PowerShell 启动方式：

```powershell
python -m venv .venv
python -m pip install -e ".[dev]"
$env:QUANTSTONE_DATA_ROOT = "D:\QuantStoneData"
uvicorn quantstone_data.main:app --reload
```

如果不设置 `QUANTSTONE_DATA_ROOT`，默认使用当前用户目录下的 `.quantstone-data`。真实数据和 staging 文件不应放入 Git 仓库。

API 默认地址为 `http://127.0.0.1:8000`，交互式接口文档位于
`http://127.0.0.1:8000/docs`。

另开一个终端启动前端：

```bash
cd web
npm install
npm run dev
```

管理界面默认位于 `http://127.0.0.1:5173`。

Linux 可以使用管理脚本同时启动前后端，并允许同一局域网中的浏览器访问：

```bash
./scripts/quantstone-dev.sh start
./scripts/quantstone-dev.sh status
./scripts/quantstone-dev.sh logs
./scripts/quantstone-dev.sh stop
```

脚本通过用户级 systemd 持续运行服务，将前端和后端绑定到 `0.0.0.0`，前端默认使用
5173 端口。其他电脑访问 `http://<服务器内网IP>:5173`；浏览器的 `/api` 请求由 Vite
转发到服务器本机 8000 端口。运行日志通过脚本的 `logs` 子命令读取，文件位于 `var/logs/`。

当前管理界面支持数据集管理、采集任务创建、任务记录查看，以及手动文件上传到 staging。
侧栏使用统一的“采集”入口，页面内可在“任务”和“采集能力”之间切换。

运行测试：

```bash
pytest
```

## 当前接口

```text
POST   /api/v1/datasets
GET    /api/v1/datasets
GET    /api/v1/dataset-presets
GET    /api/v1/datasets/{dataset_id}
PUT    /api/v1/datasets/{dataset_id}
PATCH  /api/v1/datasets/{dataset_id}
POST   /api/v1/datasets/{dataset_id}/activate
DELETE /api/v1/datasets/{dataset_id}
GET    /api/v1/collectors
GET    /api/v1/collectors/{collector_key}/operations/{operation_key}
GET    /api/v1/catalog/partitions?dataset_id=...
POST   /api/v1/collection-jobs
GET    /api/v1/collection-jobs
GET    /api/v1/collection-jobs/{job_id}
GET    /api/v1/collection-jobs/{job_id}/runs
GET    /api/v1/collection-jobs/{job_id}/logs
GET    /api/v1/collection-jobs/{job_id}/progress
POST   /api/v1/collection-jobs/{job_id}/execute
POST   /api/v1/collection-jobs/{job_id}/cancel
POST   /api/v1/collection-jobs/{job_id}/file
GET    /api/v1/maintenance-jobs?dataset_id=...
GET    /api/v1/maintenance-jobs/{job_id}
POST   /api/v1/maintenance-jobs/{job_id}/cancel
POST   /api/v1/datasets/{dataset_id}/compact?year=YYYY
GET    /health
```

`PUT` 仅用于修改草稿的完整数据契约；`PATCH` 用于修改显示名称和说明，已启用数据集也可使用。
“预置契约”页面展示随项目代码版本管理的常用契约，并通过现有创建接口生成 Registry 草稿；
预置不会自动创建、同步或覆盖数据集。

手动文件入库采用两步流程：先创建 `input_method=file_import` 的采集任务，再将文件上传到该任务的 `/file` 接口。文件只会进入外部数据根目录的 staging 区，不会直接发布为正式数据。

项目从本地 `.env` 或进程环境变量读取 `TUSHARE_TOKEN`，密钥文件不会提交到 Git。
采集任务的执行接口立即返回 `202 + queued`，后台单工作线程依次完成采集、审核和发布；
前端通过任务状态、进度和日志接口持续更新，不需要保持原始执行请求。
年度合并使用独立的维护任务记录，但与采集任务共用同一个后台工作线程，避免二者并发修改
Catalog 和 Parquet 文件。

`tushare.cn.stock.daily` 已走通第一个 Parquet 纵向闭环：按交易日建立 Run、写入
staging Parquet、执行主键和分区审核、发布为日增量文件，并在 Catalog 登记逻辑分区。

## 项目状态

处于早期设计和基础功能搭建阶段。

## 开源许可证

MIT License。
