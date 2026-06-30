# Project Context

更新时间：2026-06-24

## 项目定位

本项目是一个面向 Binance USDⓈ-M Futures 的自动交易研发系统。目标是构建可回测、可模拟、可监控、可复盘、可安全停止的量化交易闭环。

核心策略框架：

- 下一代策略内核为 `WEEKLY_DAILY_H4_V1`：周线决定大环境和周线仓，日线在周线环境下做互斥的反弹或顺势仓，4H 只做严格执行与 breakout/pullback/continuation。
- 独立策略系统：Paper、Backtest 和 Web 状态页只调用策略系统输出，不复制策略规则。
- 仓位层级只允许 `WEEKLY / DAILY / H4`；方向、反弹、顺势、breakout、pullback、continuation 只作为属性，不再拆成旧 bucket 命名。
- 日线反弹单与顺势单互斥；4H 必须通过严格 no-trade / BOLL 开口 / breakout 过滤。
- ATR 动态止损止盈。
- Funding 与 AI 新闻过滤只做风险过滤。
- 账户级、订单级、持仓级风控优先于任何交易信号。

## MVP 范围

MVP / 第一版只做 Backtest + Paper Trading，不开发 Live 实盘、测试网下单、真实下单、API 下单适配器或小资金实盘。

## 版本边界

- 第一版：Backtest、Paper Trading、Web 状态、复盘、模拟风控和策略验证。
- 第二版：Live Trading、测试网下单、真实下单、API 下单适配器、小资金实盘。
- 第二版开发永久暂停，除非用户明确发出“开始开发第二版实盘交易”的指令。
- API Key 可用、Paper 连续稳定、Live 自检代码存在或 Guard 代码存在，都不能自动触发第二版。

MVP 当前策略主线必须实现：

- BTCUSDT、ETHUSDT 两个交易对。
- 1w / 1d / 4h K 线用于 `WEEKLY_DAILY_H4_V1`；5m/15m/1h 仅保留为历史数据或非当前内核用途。
- PostgreSQL 数据库记录行情、指标、信号、订单计划、Paper 成交、持仓、账户快照。
- EMA15、MA60、ADX、DI_PLUS、DI_MINUS、ATR、Bollinger Bands。
- `WEEKLY / DAILY / H4` 三类仓位层级。
- `TREND / REBOUND / BREAKOUT / PULLBACK / CONTINUATION` 交易模式属性。
- Regime Tagging、Throttle、Signal Score、Lifecycle、Equity Guard 控制层。
- 单笔风险仓位计算。
- ATR 止损、2R 止盈激活价、1R 锁盈和 ATR 动态移动止盈。
- 事件驱动回测。
- Paper Trading。
- Kill Switch。
- 基础报警和状态页。

MVP 暂不实现：

- 真实 LLM 新闻过滤。
- 任何 Live 实盘执行。
- 任何测试网或真实下单执行。
- 多币种大规模扫描。
- 多交易所。

## 关键术语

当前策略内核：

- `WEEKLY_DAILY_H4_V1`：当前唯一运行策略内核。
- `WEEKLY`：周线仓，周线大环境和最高级别仓位。
- `DAILY`：日线仓，周线环境下的互斥反弹或顺势仓。
- `H4`：4H 仓，严格执行级 breakout / pullback / continuation。
- `TREND`：顺势模式。
- `REBOUND`：反弹模式。
- `BREAKOUT`：突破模式。
- `PULLBACK`：回踩模式。
- `CONTINUATION`：延续模式。

历史术语，仅用于理解旧提交和旧文档，不再作为当前运行内核：

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
2. 第一版回测和 Paper 必须共享策略、风控和多周期已收盘数据对齐逻辑；未来第二版 Live 如被明确启动，也必须共享同一逻辑。
3. 任何不确定状态默认禁止新开仓。
4. AI 只能输出 `ALLOW`、`WARN`、`BLOCK`，不能直接决定买卖。
5. 订单、持仓、风控必须可恢复、可复盘。
6. Live 属于第二版且永久暂停；除非用户明确发令启动第二版，否则不允许开发或默认开启。
7. 系统必须简单优先：优先少模块、少抽象、少配置、可运行、可观察、可复盘；除非真实运行痛点已经出现，否则不提前引入复杂平台化设计。
