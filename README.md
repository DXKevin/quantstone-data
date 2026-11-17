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

## 本地开发

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
uvicorn quantstone_data.main:app --reload
```

API 默认地址为 `http://127.0.0.1:8000`，交互式接口文档位于
`http://127.0.0.1:8000/docs`。

运行测试：

```bash
pytest
```

## 当前接口

```text
POST   /api/v1/datasets
GET    /api/v1/datasets
GET    /api/v1/datasets/{dataset_id}
POST   /api/v1/datasets/{dataset_id}/activate
DELETE /api/v1/datasets/{dataset_id}
GET    /health
```

## 项目状态

处于早期设计和基础功能搭建阶段。

## 开源许可证

MIT License。
