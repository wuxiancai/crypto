# Handoff

更新时间：2026-06-17

## 当前状态

- 已再次审查并优化 `prd.md`，当前版本为 `v0.3-dev-ready`。
- 已将长期上下文拆分为：
  - `docs/PROJECT_CONTEXT.md`
  - `docs/DECISIONS.md`
  - `docs/TASKS.md`
  - `docs/HANDOFF.md`
- 当前项目已有 git 仓库，并已按功能节点持续提交。
- V0.2 策略信号已完成第一版，下一阶段进入 V0.3 回测系统。

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

## 验证结果

- `.venv/bin/python -m pytest -q`：21 passed。
- `DATABASE_URL=sqlite+pysqlite:///:memory: .venv/bin/alembic upgrade head`：通过。
- `BINANCE_BASE_URL=https://testnet.binancefuture.com .venv/bin/python scripts/sync_klines.py --symbols BTCUSDT --intervals 15m --limit 5`：dry-run 成功。
- `DATABASE_URL=postgresql+psycopg://crypto:crypto@localhost:55432/crypto_quant BINANCE_BASE_URL=https://testnet.binancefuture.com .venv/bin/python scripts/sync_klines.py --symbols BTCUSDT ETHUSDT --intervals 15m --limit 5 --write`：写入成功。
- 本地 Postgres `klines` 行数：BTCUSDT 15m = 5，ETHUSDT 15m = 5。
- Binance 主网 futures endpoint 当前返回 HTTP 451，疑似当前网络/地区受限；尚未完成主网真实 K 线 dry-run。

## 下一步

1. 在可访问 Binance 主网 futures endpoint 的环境执行真实 BTCUSDT、ETHUSDT K 线 dry-run。
2. 执行 `scripts/sync_klines.py --write` 入库主网真实 K 线。
3. 进入 V0.3：实现事件驱动回测引擎，复用 V0.2 策略信号与信号编排入口。
4. 回测系统必须模拟手续费、滑点、资金费率、交易所精度和强平风险，不能只做理想成交。

## 最近提交

- `192eaaf test: add pullback strategy entry cases`
- `cce1b0c feat: add trend pullback entry signals`
- `3d18f52 test: add reversal strategy signal cases`
- `0e27c77 feat: add reversal probe signal engine`
- `da1b335 test: add signal routing priority cases`
- `42ba830 feat: add signal routing priority`

## 风险提醒

- 不要跳过真实 K 线入库直接写策略。
- 不要在 Stop Order Guard 和 Liquidation Guard 完成前写 Live Trading。
- 回测和 Paper 必须共用同一套策略、风控和多周期对齐函数。
- Mock 可以用于单元测试，但不能作为系统验收依据。
