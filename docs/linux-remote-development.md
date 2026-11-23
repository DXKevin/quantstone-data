# Linux 内网远程开发交接

## 目标与边界

项目将从 Windows 本地目录迁移到 Linux 内网服务器继续开发。代码通过 GitHub 仓库迁移，
真实金融数据、SQLite Catalog、密钥和运行日志不进入 Git。

Linux 开发环境已于 2026-11-19 完成初始化。当前代码目录为
`/home/quantadmin/project/quantstone-data`，正式数据根目录为
`/home/hhd_data/quantstone-data`。本轮从空
Catalog 开始，尚未迁移 Windows 上的 SQLite Catalog 或真实数据，也尚未配置常驻服务。

## 推荐目录

```text
/opt/quantstone-data/       Git 工作目录
/data/quantstone-data/      QuantStone 正式数据、staging、日志和 revisions
/data/import/l2/            L2 历史文件迁移落点，不直接视为正式数据
```

具体路径可以调整，但代码目录、正式数据目录和历史迁移源目录应分开。不要把真实数据放进
Git 工作目录。

## 代码环境迁移

```bash
git clone git@github.com:DXKevin/quantstone-data.git /opt/quantstone-data
cd /opt/quantstone-data

python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'

cd web
npm install
npm run build
```

不得从 Windows 复制 `.venv`、`node_modules`、`.pytest_cache`、`.ruff_cache` 或 pip 临时目录。
Linux 应重新安装 Python 3.11+、Node.js 和项目依赖。

## 配置与启动

密钥由 Linux 进程环境变量或仓库根目录下未提交的 `.env` 提供：

```bash
export QUANTSTONE_DATA_ROOT=/home/hhd_data/quantstone-data
export TUSHARE_TOKEN='...'
export TUSHARE_API_URL='http://proxy.example:32817'  # 可选，默认 https://api.tushare.pro
```

`TUSHARE_API_URL` 必须是兼容 TuShare POST 协议的完整 HTTP(S) 地址。它只改变网络入口，数据集
供应商仍为 TuShare，不改变数据集 ID、契约、审核器或存储路径。项目的三个 TuShare 采集器
统一读取该配置，避免部分接口仍访问官方域名。

开发阶段启动：

```bash
cd /home/quantadmin/project/quantstone-data
./scripts/quantstone-dev.sh start
```

同一内网的浏览器可访问 `http://<服务器内网IP>:5173`。Vite 已将 `/api` 和 `/health`
代理到服务器本机 `127.0.0.1:8000`，浏览器不需要直接请求 8000 端口。防火墙只应向可信
内网开放 5173 端口。脚本通过用户级 systemd 持续运行服务，并支持 `stop`、`restart`、
`status` 和 `logs`；当前用户未启用 linger，因此服务器重启后的自动启动仍需另行配置。

当前后台任务线程、取消集合、供应商并发门和限流器都在进程内，因此后端只能运行一个 Uvicorn
worker，不能使用 `--workers` 启动多进程。任务线程数不设统一上限，但同一数据集串行、同一
供应商 API 并发为 1。服务重启会把未完成任务标记失败，不能自动续跑。

## 当前 Catalog 与数据位置

当前默认位置并不完全统一：

- SQLite Catalog：相对于后端启动工作目录的 `var/quantstone-data.db`；
- Parquet、staging、revisions 和日志：`QUANTSTONE_DATA_ROOT`；
- 未配置数据根目录时：用户家目录下的 `.quantstone-data`。

迁移现有状态时必须同时复制 SQLite 文件与其引用的整个数据根目录，并保持 Catalog 中的
相对路径对应。复制前应先停止 Windows 后端并确认没有 `queued`、`running` 或
`cancelling` 任务。第一轮也可以只在 Linux 创建空环境，确认前后端正常后再迁移现有状态。

长期应让数据库位置也通过配置确定；该改造尚未实现。

## L2 历史数据

已有逐笔历史数据位于 Linux 目录并按市场、日期组织。不要通过浏览器逐个上传，也不要
直接复制进 QuantStone 正式数据目录。

推荐流程：

```text
系统工具完成文件迁移或挂载
→ 放入独立 import 目录
→ 专用目录扫描器生成待导入清单
→ 数据集审核器检查 Parquet 内容
→ 发布器写入正式目录并更新 Catalog
```

目录扫描器尚未实现。它可能需要针对现有 L2 来源定制，识别沪深市场、逐笔委托/逐笔成交、
交易日期、压缩包和文件命名。扫描器不是 Catalog，也不能用磁盘扫描结果替代正式覆盖记录。

## Linux 接管状态

已完成：

1. 在 Linux 使用 `main` 工作区接管项目；
2. 使用 Python 3.12 创建 `.venv` 并安装开发依赖；
3. 安装前端依赖并通过生产构建；
4. 在本地 `.env` 配置 `QUANTSTONE_DATA_ROOT=/home/hhd_data/quantstone-data`；
5. 创建数据根目录的 `datasets`、`staging`、`quarantine`、`revisions` 和 `logs` 子目录；
6. 从空 Catalog 初始化 `var/quantstone-data.db`；
7. 完成全量测试并验证后端健康接口和日志写入。

待完成：

1. 配置 `TUSHARE_TOKEN`；
2. 决定是否配置 systemd 常驻服务；
3. 确认服务器目录导入模型后开发 L2 专用扫描器；
4. 如仍需保留 Windows 历史状态，另行制定数据迁移与 Catalog 合并方案，不直接覆盖当前 Catalog。

## 交接给后续 Agent 的待确认项

- Linux 服务器内网 IP 和最终对外访问方式；
- L2 import 目录；
- 是否仍需迁移 Windows 当前 Catalog 与 TuShare 数据；
- 服务先采用开发命令还是配置 systemd；
- L2 源文件当前格式、目录结构以及迁移后是否允许移动；
- 扫描器的重复文件判定、失败恢复和多数据集联合导入规则。
