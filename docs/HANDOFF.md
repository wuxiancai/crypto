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
- 本轮继续补充 V0.4 Binance WebSocket transport，以及 V0.5 主策略/趋势转换仓位计算和止损候选选择。

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
- 创建本地 PostgreSQL Docker Compose：`crypto_quant_postgres`，默认宿主端口 `55432`。
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

## 验证结果

- `.venv/bin/python -m pytest -q`：50 passed。
- `DATABASE_URL=sqlite+pysqlite:///:memory: .venv/bin/alembic upgrade head`：通过，包含 `0002_backtest_archive`。
- `BINANCE_BASE_URL=https://testnet.binancefuture.com .venv/bin/python scripts/sync_klines.py --symbols BTCUSDT --intervals 15m --limit 5`：dry-run 成功。
- `DATABASE_URL=postgresql+psycopg://crypto:crypto@localhost:55432/crypto_quant BINANCE_BASE_URL=https://testnet.binancefuture.com .venv/bin/python scripts/sync_klines.py --symbols BTCUSDT ETHUSDT --intervals 15m --limit 5 --write`：写入成功。
- 本地 Postgres `klines` 行数：BTCUSDT 15m = 5，ETHUSDT 15m = 5。
- Binance 主网 futures endpoint 当前返回 HTTP 451，疑似当前网络/地区受限；尚未完成主网真实 K 线 dry-run。

## 下一步

1. 在可访问 Binance 主网 futures endpoint 的环境执行真实 BTCUSDT、ETHUSDT K 线 dry-run。
2. 执行 `scripts/sync_klines.py --write` 入库主网真实 K 线。
3. 继续 V0.5：实现止损候选选择、TP1/TP2/TP3 与 TP3 方向校验。
4. 继续 V0.5：实现 OrderPlan 与 ONE_WAY + ISOLATED 执行约束。

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

## 风险提醒

- 不要跳过真实 K 线入库直接写策略。
- 不要在 Stop Order Guard 和 Liquidation Guard 完成前写 Live Trading。
- 回测和 Paper 必须共用同一套策略、风控和多周期对齐函数。
- Mock 可以用于单元测试，但不能作为系统验收依据。
