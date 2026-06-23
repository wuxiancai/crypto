# Project Context

更新时间：2026-06-23

## 项目定位

本项目是一个面向 Binance USDⓈ-M Futures 的自动交易研发系统。目标是构建可回测、可模拟、可监控、可复盘、可安全停止的量化交易闭环。

核心策略框架：

- 分层趋势识别：日线决定主趋势，4h 决定子趋势，1h 确认执行，15m 触发入场。
- 独立策略系统：Paper、Backtest、Web 状态页和未来 Live 只调用策略系统输出，不复制策略规则。
- 日线主趋势仓、4h/1h 顺势加仓、4h hedge 反弹/回调仓。
- 多策略子仓：Paper/Backtest 先支持同一 symbol 主仓与 hedge 仓共存；Live HEDGE 模式必须单独自检和确认。
- ATR 动态止损止盈。
- Funding 与 AI 新闻过滤只做风险过滤。
- 账户级、订单级、持仓级风控优先于任何交易信号。

## MVP 范围

MVP 只做 Backtest + Paper Trading，不直接进入 Live 实盘。

MVP 必须实现：

- BTCUSDT、ETHUSDT 两个交易对。
- 1d / 4h / 1h / 15m / 5m K 线。
- PostgreSQL 数据库记录行情、指标、信号、订单计划、Paper 成交、持仓、账户快照。
- EMA15、MA60、ADX、DI_PLUS、DI_MINUS、ATR、Bollinger Bands。
- `SHORT_DAY_CORE` / `LONG_DAY_CORE` 日线主趋势信号。
- `SHORT_4H_1H_ADDON` / `LONG_4H_1H_ADDON` 顺势加仓信号。
- `LONG_4H_HEDGE` / `SHORT_4H_HEDGE` 4h hedge 信号。
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

- `SHORT_DAY_CORE`：日线空头主仓。
- `SHORT_4H_1H_ADDON`：日线空头下的 4h/1h 顺势空头加仓。
- `LONG_4H_HEDGE`：日线空头下的 4h 反弹多仓。
- `LONG_DAY_CORE`：日线多头主仓。
- `LONG_4H_1H_ADDON`：日线多头下的 4h/1h 顺势多头加仓。
- `SHORT_4H_HEDGE`：日线多头下的 4h 回调空仓。
- `TREND_PULLBACK`：历史兼容名称，后续不再作为新增策略系统的主策略名。
- `REVERSAL_PROBE`：历史兼容名称，后续如保留应映射到更明确的 hedge/transition 策略。
- `REVERSAL_LONG_EARLY` / `REVERSAL_SHORT_EARLY`：早期试仓，风险上限 0.2% 账户权益。
- `REVERSAL_LONG_CONFIRMED` / `REVERSAL_SHORT_CONFIRMED`：确认试仓，风险上限 0.3% 账户权益。
- `DAY_CORE`：日线主趋势仓 bucket。
- `FOUR_HOUR_ADDON`：4h/1h 顺势加仓 bucket。
- `FOUR_HOUR_HEDGE`：4h 反向 hedge bucket。
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
