# 币安 USDT 永续合约量化交易系统

本项目是一个面向 Binance USDⓈ-M Futures 的量化交易研发系统，当前重点是先把“可回测、可模拟、可监控、可复盘、可安全停止”的闭环跑通，而不是直接做真实下单。

当前主线能力：

- 多周期趋势识别。
- 分层策略系统：日线 core、4h/1h addon、4h hedge。
- Paper/Backtest 多策略子仓。
- 事件驱动回测。
- 真实行情驱动的 Paper Trading。
- 中文 Web 状态页与回测页面。
- PostgreSQL 持久化与 Alembic migration。
- 风控模块、状态机和 Live 前自检基础能力。

当前默认运行模式以 `Backtest` 和 `Paper Trading` 为主，`Live Trading` 仍处于准备阶段，默认不开启。

## 当前实现范围

当前代码已经完成或可直接使用的部分：

- Python 3.11 项目，依赖管理基于 `pip install -e .`。
- 数据源为 Binance USDⓈ-M Futures REST + WebSocket。
- 默认交易对为 `BTCUSDT`、`ETHUSDT`。
- 默认周期为 `4h / 1h / 15m / 5m`。
- PostgreSQL 通过 Docker Compose 启动。
- 回测页支持最近 `3m / 6m / 1y / 2y` 历史区间。
- Web 页面支持查看 Paper 状态、策略条件、最近成交和回测结果。

当前不建议理解为“生产级实盘系统”的部分：

- 默认不做真实下单。
- AI 新闻过滤仍是 deterministic stub，不负责预测方向。
- Funding 过滤与 Live Guard 已有判定层，但尚未接入完整实盘执行闭环。

## 目录结构

```text
app/
  backtest/      回测引擎
  config/        配置读取
  data/          Binance REST 数据、数据质量
  database/      SQLAlchemy / Alembic / repository
  deploy/        端口分配与部署辅助
  execution/     风控、订单计划、状态机、Kill Switch
  indicators/    EMA / MA / ATR / DMI 等
  paper/         Paper Trading、Web 状态页、策略适配器
  risk/          AI / Funding / 止盈止损 / 仓位管理
  strategy/      主趋势与趋势转换策略
scripts/
  deploy_ubuntu.sh
  start_ubuntu.sh
  run_paper_realtime.py
  run_paper_status_web.py
docs/
tests/
```

## 策略说明

当前策略开发的 truth source 是 [Layered Strategy System Design](docs/superpowers/specs/2026-06-23-layered-strategy-system-design.md)。README 只保留摘要；实现前后如果出现冲突，以该设计文档和 `docs/DECISIONS.md` 为准。

### 策略总览

下一阶段系统将从“单一主趋势回踩/反弹策略”升级为独立的分层策略系统：

1. 日线决定主趋势。
2. 4h 决定主趋势启动、子趋势和 hedge 反弹/回调。
3. 1h 决定执行确认。
4. 15m 决定具体入场、止损和执行触发。

Paper、Backtest、Web 状态页和未来 Live 执行只能消费策略系统输出，不应再各自复制策略规则。

### 策略命名

空头主趋势场景：

- `SHORT_DAY_CORE`：日线空头主仓。
- `SHORT_4H_1H_ADDON`：日线空头下的 4h/1h 顺势空头加仓。
- `LONG_4H_HEDGE`：日线空头下的 4h 反弹多仓。

多头主趋势场景：

- `LONG_DAY_CORE`：日线多头主仓。
- `LONG_4H_1H_ADDON`：日线多头下的 4h/1h 顺势多头加仓。
- `SHORT_4H_HEDGE`：日线多头下的 4h 回调空仓。

旧名称 `TREND_PULLBACK` 和 `REVERSAL_PROBE` 只作为历史兼容语义保留，不再作为新增策略系统的主策略命名。

### 默认参数

默认均线参数：

- 快线：`EMA15`
- 慢线：`MA60`
- ATR 周期：`14`
- DMI 周期：`12`
- Swing Lookback：`20`
- 最小 ADX：`20`

默认时间框架：

- 主趋势：`1d`
- 子趋势：`4h`
- 执行确认：`1h`
- 入场触发：`15m`
- 运行观察：`5m`

所有策略参数必须集中在策略配置里。后续优化回测或新增策略时，应调整参数或新增策略配置，不应修改 Paper、Backtest 或 Web 展示层的业务规则。

### 持仓模型

下一阶段 Paper/Backtest 必须支持策略子仓模型：

- 同一 symbol 可以同时存在主趋势 core 仓和反向 hedge 仓。
- 同一 symbol 可以存在受数量限制的 addon 仓。
- 每个子仓必须记录 `strategy_type` 和 strategy bucket。

典型共存关系：

- `SHORT_DAY_CORE` 可以和 `LONG_4H_HEDGE` 共存。
- `SHORT_DAY_CORE` 可以和 `SHORT_4H_1H_ADDON` 共存。
- `LONG_DAY_CORE` 可以和 `SHORT_4H_HEDGE` 共存。
- `LONG_DAY_CORE` 可以和 `LONG_4H_1H_ADDON` 共存。

真实 Live 若要支持同一 symbol 多空共存，必须使用 Binance Futures HEDGE position mode。Paper/Backtest 先实现策略子仓模型，Live 仍需独立自检和用户确认后才能接入。

### 风控与撮合规则

当前 Backtest / Paper 共享的重要规则仍保留：

- 默认初始权益 `1000 USDT`。
- 默认杠杆 `10x`。
- 默认 maker fee `0.02%`。
- 默认 taker fee `0.05%`。
- 默认资金费结算周期 `8h`。
- 默认拒绝明显不划算的单子，即手续费占计划风险过高时拒绝开仓。

这些规则要从单仓位撮合升级为多策略子仓撮合。

## 当前运行方式

项目当前最实用的运行方式有两个：

1. 启动真实行情驱动的 Paper Trading。
2. 打开 Web 状态页，在浏览器中查看状态与执行回测。

核心脚本：

- `scripts/deploy_ubuntu.sh`：Ubuntu 首次部署脚本。
- `scripts/start_ubuntu.sh`：跨平台的启动脚本，负责 `.venv`、Postgres、migration、Paper 和 Web。
- `scripts/run_paper_realtime.py`：实时 Paper Trading 进程。
- `scripts/run_paper_status_web.py`：中文 Web 状态页与 `/backtest` 页面。

## 环境要求

### 通用要求

- 操作系统：macOS 或 Ubuntu
- Python：`3.11+`
- Docker：可运行 `docker compose`
- 网络：需要能访问 Binance Futures REST / WebSocket，至少其中对应当前使用场景的 endpoint 可达

### Python 依赖

项目当前依赖见 `pyproject.toml`，主要包括：

- `httpx`
- `pydantic`
- `pydantic-settings`
- `psycopg[binary]`
- `SQLAlchemy`
- `alembic`
- `websockets`

安装方式统一使用：

```bash
.venv/bin/python -m pip install -e .
```

## 配置文件说明

项目里有两个容易混淆的配置文件。

### 1. `.env`

`.env` 主要用于应用层配置，尤其是：

- `ENVIRONMENT`
- `EXECUTION_MODE`
- `DATABASE_URL`
- `BINANCE_BASE_URL`
- `LIVE_TRADING_CONFIRM`

可以先从示例复制：

```bash
cp .env.example .env
```

示例内容：

```env
ENVIRONMENT=paper
EXECUTION_MODE=paper
DATABASE_URL=postgresql+psycopg://crypto:crypto@localhost:55432/crypto_quant
POSTGRES_PORT=55432
BINANCE_BASE_URL=https://fapi.binance.com
```

其中最重要的一项是：

- `BINANCE_BASE_URL`：回测、历史预热、REST 拉 K 线会使用这个地址。

如果你的当前网络无法访问 Binance 主网 Futures REST，可以在本机改成测试网或你当前网络可达的 endpoint，例如：

```env
BINANCE_BASE_URL=https://testnet.binancefuture.com
```

### 2. `.env.ports.generated`

这个文件由 `scripts/start_ubuntu.sh` 自动生成，主要用于启动时的运行时端口和脚本变量：

- `POSTGRES_PORT`
- `PAPER_WEB_PORT`
- `DATABASE_URL`
- `BINANCE_WEBSOCKET_BASE_URL`
- `PAPER_STATE_PATH`

不要手动长期维护它；需要时可以删除后重新生成。

## macOS 部署与启动

macOS 没有单独的 `deploy_macos.sh`。当前推荐做法是：

1. 先在 macOS 装好 Python 和 Docker。
2. 再直接运行 `scripts/start_ubuntu.sh`。

原因是：

- `deploy_ubuntu.sh` 明确依赖 `apt-get` 和 `systemctl`，只适合 Ubuntu。
- `start_ubuntu.sh` 本身主要做的是通用启动动作，在 macOS 上同样适用。

### 1. 安装基础依赖

如果还没有 Homebrew：

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

安装 Python 与 Docker Desktop：

```bash
brew install python@3.11
brew install --cask docker
```

然后手动启动 Docker Desktop，确认命令可用：

```bash
docker compose version
```

### 2. 准备项目

进入项目目录：

```bash
cd /Users/wuxiancai/Documents/crypto
```

准备 `.env`：

```bash
cp .env.example .env
```

如果你本机访问 Binance 主网 REST 会失败，建议先把 `.env` 里的 `BINANCE_BASE_URL` 改成测试网：

```env
BINANCE_BASE_URL=https://testnet.binancefuture.com
```

### 3. 一键启动

直接运行：

```bash
bash scripts/start_ubuntu.sh
```

脚本会自动执行：

- 创建 `.venv`
- 安装项目依赖
- 自动分配端口并生成 `.env.ports.generated`
- 通过 Docker Compose 启动 PostgreSQL
- 执行 `alembic upgrade head`
- 后台启动 `run_paper_realtime.py`
- 后台启动 `run_paper_status_web.py`

启动完成后可查看：

- 端口文件：`.env.ports.generated`
- 日志目录：`runtime/logs`

### 4. 访问页面

启动后访问：

```text
http://127.0.0.1:8765
```

如果端口被占用，实际端口可能不是 `8765`，请以 `.env.ports.generated` 里的 `PAPER_WEB_PORT` 为准：

```bash
cat .env.ports.generated
```

### 5. 常见的 macOS 问题

#### 问题一：回测时报 `Binance kline request failed after retries`

这通常不是“没有先部署”造成的，而是本机网络无法访问 `BINANCE_BASE_URL` 对应的 Binance Futures REST。

排查方式：

```bash
curl https://fapi.binance.com/fapi/v1/ping
curl https://testnet.binancefuture.com/fapi/v1/ping
```

如果主网不通、测试网可通，就把 `.env` 中的：

```env
BINANCE_BASE_URL=https://fapi.binance.com
```

改成：

```env
BINANCE_BASE_URL=https://testnet.binancefuture.com
```

然后重新启动。

#### 问题二：`docker compose` 不可用

通常是 Docker Desktop 没有启动，或首次安装后还没完成初始化。

先打开 Docker Desktop，再执行：

```bash
docker compose version
```

#### 问题三：Python 版本不对

如果 `python3` 不是 `3.11+`，可以显式指定：

```bash
PYTHON_BIN=python3.11 bash scripts/start_ubuntu.sh
```

### 6. 手动启动方式

如果你不想直接跑 `start_ubuntu.sh`，也可以手动分步执行。

先准备虚拟环境和依赖：

```bash
cd /Users/wuxiancai/Documents/crypto
python3.11 -m venv .venv
.venv/bin/python -m ensurepip --upgrade
.venv/bin/python -m pip install -U pip setuptools wheel
.venv/bin/python -m pip install -e .
```

生成端口并启动数据库：

```bash
.venv/bin/python -m app.deploy.ports
set -a
source .env.ports.generated
set +a
docker compose --env-file .env.ports.generated up -d postgres
DATABASE_URL="$DATABASE_URL" .venv/bin/python -m alembic upgrade head
```

启动实时 Paper：

```bash
set -a
source .env.ports.generated
set +a

.venv/bin/python scripts/run_paper_realtime.py \
  --symbols BTCUSDT ETHUSDT \
  --intervals 5m 15m 1h 4h \
  --websocket-base-url "$BINANCE_WEBSOCKET_BASE_URL" \
  --state-path "$PAPER_STATE_PATH"
```

启动状态页：

```bash
set -a
source .env.ports.generated
set +a

.venv/bin/python scripts/run_paper_status_web.py \
  --host 127.0.0.1 \
  --port "$PAPER_WEB_PORT" \
  --state-path "$PAPER_STATE_PATH" \
  --error-log-path runtime/logs/paper-realtime.log
```

## Ubuntu 部署与启动

Ubuntu 上推荐区分“首次部署”和“后续启动”。

### 1. 首次部署

进入项目目录执行：

```bash
bash scripts/deploy_ubuntu.sh
```

这个脚本会自动：

- 安装 `python3`、`python3-venv`、`python3-pip`
- 检查并安装 Docker / Docker Compose
- 启动 Docker 服务
- 调用 `scripts/start_ubuntu.sh`

### 2. 后续启动

依赖已准备完成后，只需要：

```bash
bash scripts/start_ubuntu.sh
```

### 3. 重新分配端口

默认会复用已有的 `.env.ports.generated`，这样 Web 页面地址更稳定。

如果确实要重新分配端口：

```bash
REGENERATE_PORTS=1 bash scripts/start_ubuntu.sh
```

### 4. Ubuntu 上推荐的部署流程

```bash
cd /path/to/crypto
cp .env.example .env
bash scripts/deploy_ubuntu.sh
```

后续重启：

```bash
cd /path/to/crypto
bash scripts/start_ubuntu.sh
```

## 启动完成后你能看到什么

### 1. Paper 状态主页

首页会展示：

- 账户权益
- 当前持仓
- 最近成交
- 策略条件摘要
- 错误日志摘要
- 多周期策略图

### 2. 回测页面

状态页服务里已经内置 `/backtest` 页面。

可以从主页进入，或者直接访问：

```text
http://127.0.0.1:8765/backtest
```

回测页支持：

- 交易对选择：`BTCUSDT` / `ETHUSDT`
- 快线 / 慢线类型：`EMA` / `MA`
- 快慢线周期配置
- 历史区间：`3m / 6m / 1y / 2y`
- 手续费/风险上限参数
- 最近回测结果展示

回测数据会缓存到：

```text
runtime/backtest-klines/
```

成功回测后，结果会写入数据库。

## 日志、状态文件与数据库

### 日志目录

```text
runtime/logs/
```

常用查看命令：

```bash
tail -f runtime/logs/paper-realtime.log
tail -f runtime/logs/paper-status-web.log
```

### Paper 状态文件

```text
runtime/paper-state.json
```

这个文件保存了：

- 当前权益
- 当前持仓
- 历史 fills
- rejected signals
- 最近策略评估
- 运行时间

项目支持从这个文件恢复 Paper 状态，避免重启后丢失上下文。

### PostgreSQL

数据库默认通过 Docker Compose 启动，默认宿主端口为：

- `55432`

如果被占用，会自动顺延到 `55433`、`55434` 等。

## 停止服务

停止 Paper 和 Web：

```bash
pkill -f scripts/run_paper_realtime.py
pkill -f scripts/run_paper_status_web.py
```

停止 PostgreSQL：

```bash
docker compose --env-file .env.ports.generated down
```

## 测试与验证

安装开发依赖：

```bash
.venv/bin/python -m pip install -e ".[dev]"
```

运行全部测试：

```bash
.venv/bin/python -m pytest -q
```

只跑核心启动与部署测试：

```bash
.venv/bin/python -m pytest tests/test_deploy_script.py tests/test_deploy_ports.py -q
```

## 常见问题

### 1. 为什么 Ubuntu 要先 `deploy_ubuntu.sh`，macOS 却不用？

因为 Ubuntu 脚本把系统依赖安装也做了，macOS 没法直接用 `apt-get` 那一套。

可以这样理解：

- Ubuntu：
  - 首次：`deploy_ubuntu.sh`
  - 后续：`start_ubuntu.sh`
- macOS：
  - 先手动安装 Python 和 Docker
  - 然后直接：`start_ubuntu.sh`

### 2. 为什么启动成功了，但回测没有结果？

最常见原因：

- 本机网络无法访问 `BINANCE_BASE_URL`
- Docker 没有正常启动，数据库不可用
- `.env` 里的配置和 `.env.ports.generated` 的运行端口不一致

建议优先检查：

```bash
cat .env
cat .env.ports.generated
tail -n 100 runtime/logs/paper-realtime.log
tail -n 100 runtime/logs/paper-status-web.log
```

### 3. `.env` 和 `.env.ports.generated` 为什么会同时存在？

职责不同：

- `.env`：偏应用配置，特别是 `BINANCE_BASE_URL`
- `.env.ports.generated`：偏启动时自动分配的端口与运行时脚本变量

### 4. 是否已经支持真实下单？

当前主线路线不是实盘，而是“真实行情驱动的 Paper Trading + 回测验证 + 风控完善”。Live 模式的基础校验和模块已经在代码中准备了一部分，但默认不作为当前推荐运行方式。

## 相关文档

- `docs/PROJECT_CONTEXT.md`
- `docs/UBUNTU_DEPLOY.md`
- `docs/HANDOFF.md`
- `prd.md`
