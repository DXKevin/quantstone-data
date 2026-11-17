# QuantStone Data Agent Guide

在修改本项目之前，请先完整阅读：

- `docs/architecture-and-decisions.md`
- `docs/dataset-id.md`

基本要求：

- 项目文档和面向用户的界面默认使用中文；
- 不要擅自引入跨供应商统一业务 Schema；
- 不要提交真实金融数据、账号、密钥或下载凭证；
- 新功能应配套测试，并区分“已实现”“规划方向”和“待定事项”；
- 提交前运行 `pytest`、`ruff check .` 和 `npm run build`（涉及前端时）。
