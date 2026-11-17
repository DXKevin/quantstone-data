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

## 本地开发

启动后端：

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

运行测试：

```bash
pytest
```

## 当前接口

```text
POST   /api/v1/datasets
GET    /api/v1/datasets
GET    /api/v1/datasets/{dataset_id}
PUT    /api/v1/datasets/{dataset_id}
POST   /api/v1/datasets/{dataset_id}/activate
DELETE /api/v1/datasets/{dataset_id}
POST   /api/v1/collection-jobs
GET    /api/v1/collection-jobs
GET    /api/v1/collection-jobs/{job_id}
POST   /api/v1/collection-jobs/{job_id}/file
GET    /health
```

手动文件入库采用两步流程：先创建 `input_method=file_import` 的采集任务，再将文件上传到该任务的 `/file` 接口。文件只会进入外部数据根目录的 staging 区，不会直接发布为正式数据。

## 项目状态

处于早期设计和基础功能搭建阶段。

## 开源许可证

MIT License。
