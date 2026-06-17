# Project Context

更新时间：2026-06-16

## 项目定位

本项目是一个面向 Binance USDⓈ-M Futures 的自动交易研发系统。目标是构建可回测、可模拟、可监控、可复盘、可安全停止的量化交易闭环。

核心策略框架：

- 多周期趋势识别。
- 主趋势回踩/反弹入场。
- 趋势转换试仓，捕捉 4h 尚未完全反转但 1h/15m 已经转向的 V 型反转早段。
- ATR 动态止损止盈。
- Funding 与 AI 新闻过滤只做风险过滤。
- 账户级、订单级、持仓级风控优先于任何交易信号。

## MVP 范围

MVP 只做 Backtest + Paper Trading，不直接进入 Live 实盘。

MVP 必须实现：

- BTCUSDT、ETHUSDT 两个交易对。
- 4h / 1h / 15m / 5m K 线。
- PostgreSQL 数据库记录行情、指标、信号、订单计划、Paper 成交、持仓、账户快照。
- EMA50、EMA200、ADX、DI_PLUS、DI_MINUS、ATR、Bollinger Bands。
- 主趋势回踩/反弹信号。
- 趋势转换早期/确认试仓信号。
- 单笔风险仓位计算。
- ATR 止损、固定 RR 止盈、保本止损。
- 事件驱动回测。
- Paper Trading。
- Kill Switch。
- 基础报警和状态页。

MVP 暂不实现：

- 真实 LLM 新闻过滤。
- 趋势转换 Live 实盘执行。
- 突破策略实盘执行。
- 多币种大规模扫描。
- 多交易所。

## 关键术语

- `TREND_PULLBACK`：主趋势回踩/反弹策略。
- `REVERSAL_PROBE`：趋势转换试仓策略。
- `REVERSAL_LONG_EARLY` / `REVERSAL_SHORT_EARLY`：早期试仓，风险上限 0.2% 账户权益。
- `REVERSAL_LONG_CONFIRMED` / `REVERSAL_SHORT_CONFIRMED`：确认试仓，风险上限 0.3% 账户权益。
- `TRANSITION`：4h 与 1h 趋势冲突状态。主趋势策略等待，但趋势转换模块继续评估。
- `Stop Order Guard`：持续检查真实持仓是否有有效止损单的保护模块。
- `Liquidation Guard`：下单前检查止损价、强平价、保证金安全距离的保护模块。

## 核心原则

1. 数据库先行，真实数据优先。
2. 回测、Paper、Live 必须共享策略、风控和多周期已收盘数据对齐逻辑。
3. 任何不确定状态默认禁止新开仓。
4. AI 只能输出 `ALLOW`、`WARN`、`BLOCK`，不能直接决定买卖。
5. 订单、持仓、风控必须可恢复、可复盘。
6. Live 必须通过启动前自检，不允许默认开启。
7. 系统必须简单优先：优先少模块、少抽象、少配置、可运行、可观察、可复盘；除非真实运行痛点已经出现，否则不提前引入复杂平台化设计。
