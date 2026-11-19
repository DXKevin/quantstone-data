# QuantStone Data Agent Guide

在修改本项目之前，请先完整阅读：

- `docs/architecture-and-decisions.md`
- `docs/dataset-id.md`
- `docs/handoff.md`
- `docs/linux-remote-development.md`（Linux 接管期间）

## Agent 接力方式

Codex 与 DeepSeek Harness 串行使用同一个 Git 工作目录。项目正在从 Windows 本地开发迁移到
Linux 内网服务器；接手 Agent 必须以当前工作区的仓库根目录为准，不得继续依赖旧的
`C:\Users\24495\Desktop\project\quantstone-data` 绝对路径。迁移说明见
`docs/linux-remote-development.md`。

同一时间只能有一个 Agent 修改项目。不要为普通接力创建额外副本、worktree 或长期分支。

### 开始工作

1. 确认当前目录是 `quantstone-data` 仓库根目录；
2. 完整阅读本文件和上述 `docs` 文档；
3. 运行 `git status --short --branch`；
4. 查看最近提交：`git log -5 --oneline`；
5. 阅读 `docs/handoff.md` 中的“当前状态”“下一步”和“已知问题”；
6. 如果发现未提交修改，先判断是否为上一个 Agent 留下的工作，不得擅自丢弃或覆盖。

### 结束工作

1. 完成与改动风险相匹配的测试；
2. 更新 `docs/handoff.md`，准确记录完成内容、下一步、测试结果和遗留问题；
3. 更新受到影响的中文文档；
4. 检查 `git diff`，确保没有密钥、真实数据或无关文件；
5. 创建内容明确的 Git 提交；
6. 推送到 `origin/main`；
7. 确认 `git status` 干净后再交接。

如果因权限、网络或用户决策无法完成提交或推送，必须在 `docs/handoff.md` 中明确写出未提交文件和原因。

基本要求：

- 项目文档和面向用户的界面默认使用中文；
- 不要擅自引入跨供应商统一业务 Schema；
- 不要提交真实金融数据、账号、密钥或下载凭证；
- 新功能应配套测试，并区分“已实现”“规划方向”和“待定事项”；
- 提交前运行 `pytest`、`ruff check .` 和 `npm run build`（涉及前端时）。
- 不要删除或回退另一个 Agent 的修改，除非用户明确要求；
- 不要把聊天记录当作唯一上下文，重要决定必须写入项目文档；
- 安装依赖时将 `TEMP` 和 `TMP` 指向项目 `var/tmp`，不要让 pip 临时目录散落在项目根目录；
- `docs/handoff.md` 只记录当前接力所需的信息，长期架构决定应写入 `docs/architecture-and-decisions.md`。
- Linux 远程开发阶段不得假设 Windows 盘符、路径分隔符或本机服务地址；新增路径必须通过配置或数据根目录解析。
- 当前后台队列、取消状态和限流器都是单进程内状态，后端只允许启动一个 Uvicorn worker。
