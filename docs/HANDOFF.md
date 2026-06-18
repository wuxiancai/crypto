# Handoff

更新时间：2026-06-18

## 当前状态

- 已再次审查并优化 `prd.md`，当前版本为 `v0.3-dev-ready`。
- 已将长期上下文拆分为：
  - `docs/PROJECT_CONTEXT.md`
  - `docs/DECISIONS.md`
  - `docs/TASKS.md`
  - `docs/HANDOFF.md`
- 当前项目已有 git 仓库，并已按功能节点持续提交。
- V0.3 回测系统已补充真实策略信号复用、maker/taker 手续费和按策略统计。
- V0.4 Paper Trading 已完成最小撮合与账户闭环。
- 本轮继续补充 V0.4 Binance WebSocket transport，完成 V0.5 风控与订单计划核心模块，完成 V0.6 AI/Funding 过滤纯风控层，并开始 V1.0 小资金实盘准备。用户已明确当前暂无 API Key，下一阶段主线改为真实行情驱动的 Paper Trading，真实/测试网下单延后。
- 用户明确要求系统越简单越好，后续开发必须避免过度设计。优先保持少模块、少抽象、少配置；任何新增组件都必须解决当前真实运行或复盘痛点。
- 已新增 Ubuntu 一键部署脚本和启动脚本，带端口冲突自动顺延机制。

## 本轮修复

- 统一 AI fallback：移除 `BLOCK_NEW_ENTRIES`，统一使用 `BLOCK`。
- 主趋势做多/做空也必须使用 DI_PLUS / DI_MINUS 判断方向。
- 趋势转换早期试仓风险固定为 0.2%，确认试仓风险固定为 0.3%。
- 趋势转换评分必须封顶 100。
- 明确 `REVERSAL_LONG_ENTRY` / `REVERSAL_SHORT_ENTRY` 是通用事件，必须带 `signal_level` 区分 EARLY / CONFIRMED。
- `reversal_strategy.enabled = true` 用于 Backtest/Paper，`live_enabled = false` 用于禁止默认实盘。
- OrderPlan 补充 leverage、margin_type、position_mode、estimated_liquidation_price、liquidation_buffer_pct。
- 数据库契约补充 `safety_checks`、`stop_order_checks`、`liquidation_checks`。
- Live 启动前自检补充地区/账户可用性、时间同步、ONE_WAY、ISOLATED、杠杆、Stop Order Guard、Liquidation Guard、数据延迟、小资金配置。

## 已完成开发

- 创建 Python 3.11 项目配置：`pyproject.toml`。
- 创建 `.env.example` 与 `.gitignore`。
- 建立 `app/` 基础包结构。
- 实现配置保护：Live 模式必须设置 `LIVE_TRADING_CONFIRM=I_UNDERSTAND_THE_RISK`。
- 实现 K 线模型与质量校验。
- 实现多周期已收盘窗口对齐。
- 实现 EMA、ATR、Bollinger Bands。
- 实现 ADX、DI_PLUS、DI_MINUS。
- 添加固定样本指标校验：`tests/fixtures/indicator_golden.json` 与 `app.indicators.validation`。
- 建立 SQLAlchemy metadata 与 Alembic migration。
- 创建 V0.1 基础表：`symbols`、`klines`、`indicator_snapshots`、`config_snapshots`。
- 实现 Binance K 线解析与拉取入口。
- 实现 K 线 upsert repository。
- 创建 `scripts/sync_klines.py` dry-run / write 入口。
- 创建本地 PostgreSQL Docker Compose，默认宿主端口 `55432`。
- 修复 K 线 `open_time` / `close_time` 为 BIGINT，避免币安毫秒时间戳溢出。
- 实现 V0.2 趋势识别状态机：UPTREND、DOWNTREND、RANGE、TRANSITION，并支持 TRANSITION 继续评估趋势转换。
- 实现 V0.2 主趋势回踩/反弹入场信号：`TREND_PULLBACK`。
- 主趋势做多要求：UPTREND、允许做多、价格在 EMA50/ATR 回踩区域、15m 看涨确认、RR 达标。
- 主趋势做空要求：DOWNTREND、允许做空、价格在 EMA50/ATR 反弹区域、15m 看跌确认、RR 达标。
- 实现 V0.2 趋势转换试仓信号：`REVERSAL_PROBE`。
- 趋势转换输出通用事件 `REVERSAL_LONG_ENTRY` / `REVERSAL_SHORT_ENTRY`，并通过 `signal_level` 区分 `EARLY` / `CONFIRMED`。
- 趋势转换评分已封顶 100，且已实现距离 EMA50 过远时的禁止追涨追跌过滤。
- 实现 V0.2 信号统一编排入口：数据同步阻断优先，其次退出信号，其次风控阻断，新开仓按主趋势优先、趋势转换次之。
- 实现 V0.3 最小事件驱动回测引擎：按 K 线顺序推进、单仓位、风险预算开仓、止盈/止损退出、统一费率手续费与基础滑点。
- V0.3 回测已支持 `TREND_PULLBACK` 与 `REVERSAL_PROBE`，趋势转换信号使用自身 `risk_pct` 风险上限。
- V0.3 回测已支持 maker/taker 手续费：入场 taker，止损 taker，止盈 maker。
- V0.3 回测已输出整体指标与按 `strategy_type` 拆分指标。
- V0.3 回测已支持 `quantity_step`、`min_qty`、`min_notional` 交易所过滤，并记录 rejected_entries。
- V0.3 回测已支持资金费率模拟，funding_fee 会进入 trade 与 metrics。
- V0.3 回测已支持止损专用滑点，且跳空越过止损时按更差的开盘价作为极端成交基准。
- V0.3 回测已支持限价未触达不成交、限价部分成交比例和 partial_fills 统计。
- V0.3 回测已支持价格 tick 方向细化：买入向上取 tick，卖出向下取 tick。
- V0.3 回测已支持强平风险模拟，触发强平时优先于止损退出并计入 liquidations。
- V0.3 已新增 `backtest_runs`、`backtest_trades` 表，并复用 `config_snapshots` 归档配置 hash。
- V0.3 已新增 `archive_backtest_result()` repository 写入入口。
- V0.4 已实现 Paper Trading 最小内核：信号入场、单仓位撮合、止盈/止损退出、权益更新、fills 记录、rejected_signals 计数。
- V0.4 Paper 已支持主趋势和趋势转换信号，趋势转换同样使用自身 `risk_pct`。
- V0.4 已实现 Paper CLI 状态格式化输出。
- V0.4 已实现基础 Paper 报警：权益回撤阈值和 rejected_signals 阈值。
- V0.4 已实现可测试的异步 K 线流消费入口，可接入 Paper 引擎。
- V0.4 已实现 Binance WebSocket kline payload 解析、combined stream URL 构造、raw message 到已收盘 Kline 的异步转换。
- V0.4 已实现 Binance WebSocket transport 连接入口，支持真实 `websockets.connect` 与测试 connector 注入。
- V0.5 已实现主策略仓位计算。
- V0.5 已实现趋势转换分级仓位计算：取风险上限和评分仓位上限中的较小值。
- V0.5 已实现止损候选选择：LONG 只接受低于入场价的止损，SHORT 只接受高于入场价的止损，并在最大止损距离内选择距离入场价最近的候选。
- V0.5 已实现趋势转换分批止盈计划：TP1 = 1R 平 30%，TP2 = 前高/前低平 30%，TP3 = 4h EMA200 或方向校验后的 3R/结构位平 40%，TP1 后移动止损到保本。
- V0.5 已实现 OrderPlan 合约：包含订单计划核心字段、分批止盈、强平估算、强平缓冲、client_order_id、策略版本和配置快照。
- V0.5 已实现 MVP 执行约束：默认 leverage = 3，最大 leverage = 5，且只允许 ONE_WAY + ISOLATED。
- V0.5 已实现 Stop Order Guard 判定层：校验真实持仓是否存在 symbol 匹配、退出方向正确、数量覆盖、reduceOnly、状态 NEW、触发价方向正确的有效止损单；缺失时输出补挂止损动作。
- V0.5 已实现 Liquidation Guard 判定层：多单要求 liquidation_price < stop_loss < entry_price，空单要求 entry_price < stop_loss < liquidation_price，且止损价与强平价安全距离不低于 liquidation_buffer_pct。
- V0.5 已实现 Kill Switch 状态转移：触发后禁止新开仓，可标记是否平仓，并记录操作者、原因、触发时间和解除操作者。
- V0.5 已实现订单、成交、持仓状态机：覆盖订单提交、部分成交、完全成交、止损提交/确认/失败、止盈提交、退出成交；主订单成交但止损失败会进入 CRITICAL 并暂停新开仓。
- V0.6 已实现 Funding 过滤器：距离结算时间 <= 15 分钟禁止新开仓，abs(funding_rate) >= 0.0015 禁止新开仓，abs(funding_rate) >= 0.0005 输出 WARN 并将仓位乘数降为 0.5。
- V0.6 已实现 AI filter 接口与 deterministic stub：默认 `enabled = false` 时输出 ALLOW；新闻不可用时 fallback BLOCK；显式模拟重大风险事件时 BLOCK。
- V0.6 已实现 AI filter 日志 entry：记录输入 payload、输出 payload、fallback_reason、provider 和 evaluated_at，真实 LLM 仍未接入且默认关闭。
- V1.0 已实现 Live 启动前自检纯校验层：任一失败项都会禁止启动 Live，并一次性返回所有 failed_checks。
- Live 自检已覆盖：API 不允许提现、IP 白名单、USDⓈ-M Futures API 可用性、服务器时间偏差、database migration、缓存可用或降级、交易所规则同步、ONE_WAY、ISOLATED、leverage <= max_leverage、未知持仓、缺失止损持仓、Stop Order Guard、Liquidation Guard、数据延迟、Kill Switch、通知通道、小资金配置、`LIVE_TRADING_CONFIRM=I_UNDERSTAND_THE_RISK`。
- V1.0 已实现小资金实盘专用配置校验：必须使用 `small_capital_live` profile，账户权益上限 <= 1000，单笔风险 <= 0.5%，每日亏损上限 <= 1.5%，最大杠杆 <= 3，仅允许 BTCUSDT / ETHUSDT，且必须 ONE_WAY + ISOLATED。
- 当前阶段不接入 Binance API 下单；先以真实行情驱动 Paper Trading，验证策略表现、风控和连续运行稳定性。测试网完整下单闭环等待 API Key 可用后再实现。
- 已实现 Paper Trading 连续运行健康检查：检测 WebSocket 连接、行情延迟、Paper 回撤、拒单数量和运行时错误；该模块用于后续“连续 2 周无重大错误”的自动化验收。
- 已实现 Paper Trading 状态持久化/恢复入口：PaperSnapshot 可无损序列化为 JSON payload，并支持保存到本地状态文件和从状态文件恢复；Decimal 金额以字符串保存，避免浮点误差。
- 已实现持久化 Paper stream runner：启动时从状态文件恢复 PaperTradingEngine，每处理一根已收盘 K 线后写回 PaperSnapshot，避免真实行情模拟交易重启后丢失权益、持仓、成交和拒单计数。
- 已实现真实行情 Paper runner 与脚本入口：`scripts/run_paper_realtime.py` 会连接 Binance WebSocket 已收盘 K 线流，并使用持久化 Paper stream runner 保存状态。
- 已实现极简中文 Web 状态页：`scripts/run_paper_status_web.py` 读取 `runtime/paper-state.json`，展示账户权益、持仓情况、全部模拟交易记录、买入价、卖出价、使用策略和 rejected signals，并每 5 秒自动刷新。
- 已实现 Ubuntu 部署入口：`scripts/deploy_ubuntu.sh` 首次部署，`scripts/start_ubuntu.sh` 后续启动。脚本会自动检测 PostgreSQL/Web 页面端口冲突并顺延，最终写入 `.env.ports.generated`。
- 已修复 Ubuntu 首次部署时 Docker 包冲突问题：`deploy_ubuntu.sh` 不再无条件安装 Ubuntu `docker.io`，会复用已有 Docker，或在 Docker CE 软件源可用时优先安装 `docker-ce`，避免 `containerd.io : Conflicts: containerd`。
- `start_ubuntu.sh` 的 Docker Compose 调用已增强：优先 `docker compose`，当前用户无 Docker 权限时尝试 `sudo docker compose`，再回退 `docker-compose`。
- 已修复 Python editable 安装失败问题：`pyproject.toml` 显式配置 setuptools 包发现规则，只打包 `app*`，排除 `runtime*`、`migrations*`、`tests*`，避免部署时出现 `Multiple top-level packages discovered in a flat-layout`。
- 已修复服务器已有 PostgreSQL / Docker 发布端口导致的部署冲突：端口分配会同时检查 socket 监听和 `docker ps` 已发布端口；`docker-compose.yml` 不再固定 Postgres 容器名，避免和旧容器或其他服务冲突。
- 已修复 `scripts/start_ubuntu.sh` 二次启动端口漂移问题：默认复用已有 `.env.ports.generated`，只有 `REGENERATE_PORTS=1` 或端口文件不存在时才重新分配端口；Compose 启动时使用 `--remove-orphans` 清理旧固定容器残留。
- 真实行情 Paper runner 已支持多周期订阅，默认订阅 15m / 1h / 4h；已新增 MultiTimeframeKlineCache，用于按 symbol 聚合多周期已收盘 K 线。
- 已新增实时策略适配器：把 4h / 1h / 15m 已收盘 K 线历史转换为 EMA、ATR、ADX、DI、swing 与趋势转换结构输入，并复用现有趋势识别、`TREND_PULLBACK` 主趋势回踩策略和 `REVERSAL_PROBE` 趋势转换策略。
- 真实行情 Paper runner 默认路径已接入实时策略适配器：不传 `signal_fn` 时，会用多周期缓存生成主趋势或趋势转换 Paper 信号；有持仓时默认 WAIT，避免重复入场。
- 已修复真实行情 Paper 一天无成交的主要运行态原因：之前 WebSocket 从启动后才开始累计 K 线，默认 EMA200 策略至少需要 200 根高周期历史，启动一天内 4h K 线远远不足；现在 runner 启动时会用 Binance REST 默认拉取最近 250 根真实历史 K 线预热缓存，再接 WebSocket。
- 已修复 signal router 字段丢失问题：主趋势与趋势转换信号经路由后会保留 entry_price、stop_loss、take_profit、risk_reward、risk_pct、score、signal_level 等执行/统计字段。
- 趋势转换信号已补充可执行 entry_price、ATR 止损与 2R take_profit，Paper 不再依赖默认止损止盈模拟趋势转换策略。
- Web 状态页已在顶部显示“系统运行时间”，便于确认服务是否中途断开或重启；运行时间随 Paper 状态文件持久化，重启恢复时保持连续。
- Web 状态页已增加“错误日志”框，只展示 `paper-realtime.log` 中的错误/异常/失败/`Historical warmup skipped` 行，并用红色字体显示；`start_ubuntu.sh` 会把实时 runner 日志路径传给状态页。
- 已定位“运行 11 小时仍 0 成交且页面无输出”的主要问题：当前成交计数为 0 不等于程序停了，`rejected_signals` 也只统计已有入场信号但被 Paper 撮合拒绝的情况；普通策略 `WAIT` 原因以前没有持久化和展示。现在 Paper 状态文件会保留最近 50 条策略评估结果，Web 状态页新增“最近策略输出”，0 成交时也能看到每根已收盘 K 线的动作、使用策略和等待原因。
- 已修复最近策略输出只看到 5m 的可观察性问题：根因是 5m K 线更新频率最高，会挤掉 15m/1h/4h 记录；现在状态文件按“交易对 + 周期”保留最新输出，页面可同时看到各周期最新状态。
- Web 状态页已新增“策略K线图”：用内嵌 SVG 绘制 4h / 1h / 15m 三套 K 线图并叠加 EMA50、EMA200；用户可点击周期按钮切换图表，交互方式接近交易所周期切换。页面同时展示核心规则摘要，如 `EMA200 > EMA50：空头基础`、主趋势回踩/反弹规则和趋势转换试仓规则。
- Web 状态页已新增“策略触发条件”：状态文件会持久化每次策略评估的条件明细和最近触发候选，页面逐行显示主趋势做多、主趋势做空、趋势转换做多、趋势转换做空的已满足/未满足状态，并显示类似 `即将触发：主趋势做空（5/6）` 的实时进度。

## 验证结果

- `.venv/bin/python -m pytest -q`：110 passed。
- `bash -n scripts/start_ubuntu.sh && bash -n scripts/deploy_ubuntu.sh`：通过。
- `.venv/bin/python -m pytest tests/test_deploy_ports.py -q`：3 passed。
- `.venv/bin/python -m pytest tests/test_deploy_script.py tests/test_deploy_ports.py -q`：5 passed。
- `.venv/bin/python -m pip install -e .`：通过，已验证 editable 安装不再触发 setuptools flat-layout 顶层包发现错误。
- `.venv/bin/python -m pytest -q`：116 passed。
- `.venv/bin/python -m pytest tests/test_deploy_ports.py -q`：5 passed，覆盖 Docker 已发布端口和 Compose 容器名冲突。
- `.venv/bin/python -m pytest -q`：118 passed。
- `.venv/bin/python -m pytest tests/test_deploy_script.py tests/test_deploy_ports.py -q`：9 passed，覆盖二次启动端口稳定和 orphan 清理。
- `.venv/bin/python -m pytest -q`：120 passed。
- `.venv/bin/python -m pytest tests/test_v1_0_real_market_paper_runner.py tests/test_v1_0_paper_persistence.py tests/test_v1_0_paper_status_web.py tests/test_v1_0_persistent_paper_stream.py -q`：12 passed。
- `.venv/bin/python -m pytest -q`：122 passed。
- `.venv/bin/python -m pytest tests/test_v1_0_real_market_paper_runner.py tests/test_v1_0_paper_status_web.py tests/test_deploy_script.py -q`：15 passed。
- `.venv/bin/python -m py_compile scripts/run_paper_status_web.py scripts/run_paper_realtime.py && bash -n scripts/start_ubuntu.sh`：通过。
- `.venv/bin/python -m pytest -q`：125 passed。
- `.venv/bin/python -m pytest tests/test_v1_0_persistent_paper_stream.py tests/test_v1_0_paper_persistence.py tests/test_v1_0_paper_status_web.py tests/test_v1_0_real_market_paper_runner.py -q`：16 passed。
- `.venv/bin/python -m pytest -q`：127 passed。
- `.venv/bin/python -m pytest tests/test_v1_0_persistent_paper_stream.py tests/test_v1_0_paper_persistence.py tests/test_v1_0_paper_status_web.py tests/test_v1_0_realtime_strategy_adapter.py tests/test_v1_0_real_market_paper_runner.py -q`：21 passed。
- `.venv/bin/python -m pytest -q`：129 passed。
- `.venv/bin/python -m pytest tests/test_v1_0_persistent_paper_stream.py tests/test_v1_0_paper_persistence.py tests/test_v1_0_paper_status_web.py tests/test_v1_0_realtime_strategy_adapter.py tests/test_v1_0_real_market_paper_runner.py -q`：22 passed。
- `.venv/bin/python -m pytest -q`：130 passed。
- `.venv/bin/python -m pytest tests/test_v1_0_realtime_strategy_adapter.py::test_realtime_strategy_reports_trigger_conditions_and_nearest_strategy tests/test_v1_0_paper_status_web.py::test_paper_status_page_shows_strategy_trigger_conditions -q`：2 passed。
- `.venv/bin/python -m pytest tests/test_v1_0_realtime_strategy_adapter.py tests/test_v1_0_paper_status_web.py tests/test_v1_0_persistent_paper_stream.py tests/test_v1_0_paper_persistence.py tests/test_v1_0_real_market_paper_runner.py -q`：24 passed。
- `.venv/bin/python -m py_compile app/paper/strategy_adapter.py app/paper/stream.py app/paper/trading.py app/paper/persistence.py app/paper/web_status.py app/strategy/signal_router.py`：通过。
- `.venv/bin/python -m pytest -q`：132 passed。
- 2026-06-17 已启动真实行情 Paper Trading：`.venv/bin/python scripts/run_paper_realtime.py --symbols BTCUSDT ETHUSDT --intervals 5m 15m 1h 4h --websocket-base-url wss://fstream.binancefuture.com --state-path runtime/paper-state.json`。
- 真实行情源验证：`wss://fstream.binancefuture.com` 可收到 BTCUSDT / ETHUSDT Binance Futures K 线推送；`runtime/paper-state.json` 已在收到已收盘 K 线后创建。
- 2026-06-17 已启动 Web 状态页：`.venv/bin/python scripts/run_paper_status_web.py --host 127.0.0.1 --port 8765 --state-path runtime/paper-state.json`，访问地址 `http://127.0.0.1:8765`。
- Web 状态页验证：`http://127.0.0.1:8765/api/status` 返回 `RUNNING`，页面显示 equity、open position、fills、rejected signals。
- 2026-06-17 已按用户要求改为中文页面，并将真实行情模拟交易默认本金改为 1000 USDT；当前 `runtime/paper-state.json` 已以 1000 USDT 创建。
- 当前运行进程：真实行情模拟交易 PID `67579`，Web 状态页 PID `67621`。
- `DATABASE_URL=sqlite+pysqlite:///:memory: .venv/bin/alembic upgrade head`：通过，包含 `0002_backtest_archive`。
- `BINANCE_BASE_URL=https://testnet.binancefuture.com .venv/bin/python scripts/sync_klines.py --symbols BTCUSDT --intervals 15m --limit 5`：dry-run 成功。
- `DATABASE_URL=postgresql+psycopg://crypto:crypto@localhost:55432/crypto_quant BINANCE_BASE_URL=https://testnet.binancefuture.com .venv/bin/python scripts/sync_klines.py --symbols BTCUSDT ETHUSDT --intervals 15m --limit 5 --write`：写入成功。
- 本地 Postgres `klines` 行数：BTCUSDT 15m = 5，ETHUSDT 15m = 5。
- Binance 主网 futures endpoint 当前返回 HTTP 451，疑似当前网络/地区受限；尚未完成主网真实 K 线 dry-run。

## 下一步

1. 在可访问 Binance 主网 futures endpoint 的环境执行真实 BTCUSDT、ETHUSDT K 线 dry-run。
2. 执行 `scripts/sync_klines.py --write` 入库主网真实 K 线。
3. 下一步继续真实行情 Paper Trading：把实时 Paper 的每次信号、拒绝原因、成交、持仓快照持久化到数据库表，便于连续 2 周稳定性验证和复盘统计。
4. 后续把 V0.5 的 OrderPlan / Guard / 状态机接入 Paper/Live 执行适配器时，需要补充交易所规则校验、状态持久化、补挂止损、市价平仓、CRITICAL 告警和 `risk_events` 持久化。

## 最近提交

- `192eaaf test: add pullback strategy entry cases`
- `cce1b0c feat: add trend pullback entry signals`
- `3d18f52 test: add reversal strategy signal cases`
- `0e27c77 feat: add reversal probe signal engine`
- `da1b335 test: add signal routing priority cases`
- `42ba830 feat: add signal routing priority`
- `bbda45e test: add event backtest engine cases`
- `cfcf3f9 feat: add event driven backtest engine`
- `0523bf5 test: add reversal backtest metrics case`
- `5b7734c feat: reuse reversal signals in backtests`
- `00e7aef test: add maker taker fee backtest case`
- `4e31302 feat: add maker taker backtest fees`
- `e3653c1 test: add paper trading lifecycle cases`
- `0ad7e0c feat: add paper trading engine`
- `07c3a6a test: add reversal paper trading case`
- `0dd8bf1 feat: support reversal paper trading`
- `895cf21 test: add exchange filter backtest cases`
- `deb71cd feat: add exchange filters to backtests`
- `068a0f2 test: add funding fee backtest case`
- `7a6f029 feat: add funding fees to backtests`
- `2746c9a test: add paper status formatting case`
- `d6f25da feat: add paper status formatter`
- `e10189f test: add extreme stop slippage case`
- `f62c9d2 feat: add extreme stop slippage to backtests`
- `ec1da50 test: add limit fill backtest cases`
- `5eb6149 feat: add limit fill simulation to backtests`
- `569cd7a test: add paper alert cases`
- `6ed1eb0 feat: add paper alert rules`
- `14064fa test: add tick rounding backtest case`
- `59b71b7 feat: add directional tick rounding to backtests`
- `abc13e6 test: add liquidation backtest case`
- `e0c75f0 feat: add liquidation risk to backtests`
- `b9533c2 test: add paper kline stream case`
- `b875d2e feat: add paper kline stream runner`
- `81dfffb test: add backtest archive case`
- `37c9019 feat: archive backtest runs and trades`
- `e23c4e0 test: add binance websocket kline parsing`
- `58c375b feat: parse binance websocket klines`
- `e938369 test: add binance websocket stream provider cases`
- `2f56647 feat: add binance websocket kline stream helpers`
- `68b3587 test: add binance websocket transport case`
- `ab6d57c feat: add binance websocket transport`
- `2d2b29f test: add position sizing cases`
- `cc39e8d feat: add position sizing rules`
- `6152b72 test: add stop loss selection cases`
- `720d601 feat: add stop loss candidate selection`
- `2ad0a87 test: add reversal take profit cases`
- `db86b73 feat: add reversal take profit plan`
- `3b69fa5 test: add order plan contract cases`
- `0f68c36 feat: add order plan contract`
- `9621be1 test: add stop order guard cases`
- `8379e30 feat: add stop order guard evaluation`
- `0a2fae2 test: add liquidation guard cases`
- `cd90c16 feat: add liquidation guard evaluation`
- `88a3959 test: add kill switch cases`
- `e6099d0 feat: add kill switch state transitions`
- `6a1c7e8 test: add execution state machine cases`
- `cabe0da feat: add execution state machine`
- `3491627 test: add funding filter cases`
- `bd5dca5 feat: add funding filter`
- `33d8c19 test: add ai filter stub cases`
- `6494d1f feat: add deterministic ai filter`
- `b72ba25 test: add ai filter log case`
- `f9081d3 feat: add ai filter log entry`
- `1fc4062 test: add live preflight checks`
- `b5b9c75 feat: add live preflight checks`
- `e57248d test: add small capital config checks`
- `771416d feat: add small capital config validation`
- `bc304c0 test: add paper runtime health checks`
- `77d3d3a feat: add paper runtime health checks`
- `aaef40d test: add paper snapshot persistence cases`
- `4644aaf feat: add paper snapshot persistence`
- `6569e43 test: add paper state file store cases`
- `6f3a3dc feat: add paper state file store`
- `d1aa428 test: add persistent paper stream case`
- `2f6264b feat: persist paper stream state`
- `92b2368 test: add real market paper runner case`
- `67d0f5e feat: add real market paper runner`
- `fda8992 test: cover injected real market paper strategy`
- `3b5a270 test: add multitimeframe kline cache cases`
- `bd0918b feat: add multitimeframe kline cache`
- `71d69e2 test: add multi interval binance stream url`
- `1954808 feat: add multi interval binance stream helpers`
- `fec4ca9 test: require multi interval paper runner config`
- `2bcf48d feat: support multi interval paper runner`
- `654065b test: add realtime strategy adapter cases`
- `ba6baea feat: add realtime strategy adapter`
- `7b93f4f test: require default realtime paper strategy`
- `af62e50 feat: wire realtime strategy into paper runner`
- `cada0fb test: require signal router field preservation`
- `007822e feat: preserve routed signal fields`
- `9c51e30 test: require executable reversal signal prices`
- `4090519 feat: add executable reversal signal prices`
- `c07c006 test: require realtime reversal strategy signal`
- `7fa6746 feat: wire realtime reversal paper strategy`
- `151e9c0 test: require strategy trigger condition diagnostics`
- `a3aee57 feat: show strategy trigger condition diagnostics`

## 风险提醒

- 不要跳过真实 K 线入库直接写策略。
- 不要在 Stop Order Guard 和 Liquidation Guard 完成前写 Live Trading。
- 回测和 Paper 必须共用同一套策略、风控和多周期对齐函数。
- Mock 可以用于单元测试，但不能作为系统验收依据。
- 不要把系统做复杂。下一步 Paper 复盘优先用最小可用持久化和 CLI 输出，暂不引入消息队列、复杂调度平台、插件系统或大型监控平台。
