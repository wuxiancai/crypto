# Tasks

更新时间：2026-06-18

## 当前阶段

当前 V0.6 AI/Funding 过滤纯风控层已完成，正在推进真实行情驱动的 Paper Trading 稳定性验证。当前暂无 Binance API Key，测试网/真实下单闭环延后到 API Key 可用后再做。主网真实 K 线入库仍受当前网络 Binance futures HTTP 451 限制，需要在可访问环境补验。

## V0.1 数据与指标

- [x] 初始化项目结构。
- [x] 建立配置加载与环境变量校验。
- [x] 建立 Alembic migration。
- [x] 创建 `symbols`、`klines`、`indicator_snapshots`、`config_snapshots` 基础表。
- [x] 实现 Binance USDⓈ-M K 线拉取。
- [ ] 写入 BTCUSDT、ETHUSDT 真实 K 线。
- [x] 实现 K 线完整性验证。
- [x] 实现多周期已收盘数据对齐函数。
- [x] 实现 EMA、ATR、ADX、DI_PLUS、DI_MINUS、Bollinger Bands。
- [x] 用第三方库或固定样本校验指标误差。

说明：

- 当前已实现 EMA、ATR、ADX、DI_PLUS、DI_MINUS、Bollinger Bands。
- 当前已添加 `tests/fixtures/indicator_golden.json` 固定样本校验。
- Binance 主网 futures endpoint 在当前网络返回 HTTP 451；已用 `BINANCE_BASE_URL=https://testnet.binancefuture.com` 完成 dry-run 验证。
- 本地 PostgreSQL 已启动并完成 migration；已用 Binance futures 测试网写入 BTCUSDT、ETHUSDT 各 5 根 15m K 线。
- 主网真实 K 线写入仍待可访问 Binance 主网 futures endpoint 的环境验证。

## V0.2 策略信号

- [x] 实现趋势识别状态：UPTREND、DOWNTREND、RANGE、TRANSITION、UNKNOWN。
- [x] 实现主趋势回踩做多。
- [x] 实现主趋势反弹做空。
- [x] 实现趋势转换早期试仓信号。
- [x] 实现趋势转换确认试仓信号。
- [x] 实现趋势转换评分封顶。
- [x] 实现禁止追涨追跌过滤。
- [x] 实现信号生成顺序：同步/风控/退出优先，新开仓靠后。

说明：

- 当前已实现 `TREND_PULLBACK` 主趋势入场信号。
- 做多要求：主趋势允许做多、价格回踩到 EMA50/ATR 区域、15m 看涨确认、RR 达标。
- 做空要求：主趋势允许做空、价格反弹到 EMA50/ATR 区域、15m 看跌确认、RR 达标。
- 当前 TP 使用固定目标 RR，止损使用最近 swing low / swing high。
- 当前已实现 `REVERSAL_PROBE` 趋势转换试仓信号。
- 趋势转换输出通用事件 `REVERSAL_LONG_ENTRY` / `REVERSAL_SHORT_ENTRY`，并通过 `signal_level = EARLY | CONFIRMED` 区分早期/确认。
- 趋势转换评分已执行 `min(raw_score, 100)` 封顶。
- 趋势转换做多/做空已实现距离 EMA50 过远的追涨追跌过滤。
- 当前已实现信号统一编排入口：数据同步阻断优先，其次退出信号，其次风控阻断，新开仓按主趋势优先、趋势转换次之。

## V0.3 回测系统

- [x] 实现事件驱动回测引擎。
- [x] 复用实盘策略和风控规则。
- [x] 模拟 maker/taker 手续费。
- [x] 模拟市价滑点、止损滑点、极端滑点。
- [x] 模拟限价未成交和部分成交。
- [x] 模拟资金费率。
- [x] 模拟交易所最小数量、最小名义价值、价格精度、数量精度。
- [x] 模拟强平风险。
- [x] 输出整体指标与按 strategy_type 拆分指标。
- [x] 归档 backtest_run、config_snapshot、backtest_trades。

说明：

- 当前已实现最小事件驱动回测内核：按 K 线 open_time 顺序推进、单仓位、按风险预算开仓、止盈/止损退出、输出 trade 与 final_equity。
- 当前已支持 `TREND_PULLBACK` 与 `REVERSAL_PROBE` 信号；趋势转换信号会使用自身 `risk_pct` 风险上限。
- 当前已实现 maker/taker 手续费：入场按 taker，止损按 taker，止盈按 maker。
- 当前已输出整体指标与按 `strategy_type` 拆分的交易次数、胜负、gross_pnl、fees、net_pnl。
- 当前已实现资金费率模拟，资金费进入 trade 与整体指标。
- 当前已实现交易所 `quantity_step`、`min_qty`、`min_notional` 过滤；价格精度仍待进一步细化为不同订单类型的 tick 方向。
- 当前已实现止损专用滑点与跳空越过止损时的极端成交价。
- 当前已实现限价未触达不成交、限价部分成交比例和 partial_fills 统计。
- 当前已实现价格 tick 方向细化：买入向上取 tick，卖出向下取 tick。
- 当前已实现强平风险模拟，触发强平时优先于止损退出并计入 liquidations。
- 当前已实现 `backtest_runs`、`config_snapshots`、`backtest_trades` 归档，并提供 repository 写入入口。

## V0.4 Paper Trading

- [x] 实现实时行情订阅。
- [x] 实现 Paper 撮合。
- [x] 实现 Paper 持仓与账户权益。
- [x] 接入主趋势策略 Paper 验证。
- [x] 接入趋势转换策略 Paper 验证。
- [x] 实现状态页或 CLI 状态输出。
- [x] 实现基础报警。

说明：

- 当前已实现 Paper Trading 最小内核：接收策略信号、单仓位撮合、止盈/止损退出、权益更新、fills 记录和 rejected_signals 计数。
- Paper 当前支持 `TREND_PULLBACK` 与 `REVERSAL_PROBE`，趋势转换信号同样使用自身 `risk_pct`。
- 当前已实现稳定的 Paper CLI 状态格式化输出。
- 当前已实现基础 Paper 报警：权益回撤阈值和 rejected_signals 阈值。
- 当前已实现可测试的异步 K 线流消费入口，可接入 Paper 引擎。
- 当前已实现 Binance WebSocket kline payload 解析、combined stream URL 构造、raw message 到已收盘 Kline 的异步转换。
- 当前已实现 Binance WebSocket transport 连接入口，支持真实 `websockets.connect` 与测试 connector 注入。

## V0.5 风控与订单计划

- [x] 实现主策略仓位计算。
- [x] 实现趋势转换分级仓位计算。
- [x] 实现止损候选选择。
- [x] 实现 TP1/TP2/TP3 与 TP3 方向校验。
- [x] 实现 OrderPlan。
- [x] 实现 ONE_WAY + ISOLATED 执行约束。
- [x] 实现 Stop Order Guard。
- [x] 实现 Liquidation Guard。
- [x] 实现 Kill Switch。
- [x] 实现订单、成交、持仓状态机。

说明：

- 当前已实现主策略按账户风险预算、止损距离、交易所数量/名义价值过滤计算仓位。
- 当前已实现趋势转换仓位计算：最终数量取风险上限和评分仓位上限的较小值；EARLY 使用 0.2% 风险，CONFIRMED 使用 0.3% 风险。
- 当前已实现止损候选选择：LONG 只接受低于入场价的止损，SHORT 只接受高于入场价的止损，并在最大止损距离内选择距离入场价最近的候选。
- 当前已实现趋势转换分批止盈计划：TP1 = 1R 平 30%，TP2 = 前高/前低平 30%，TP3 = 4h EMA200 或方向校验后的 3R/结构位平 40%，TP1 后移动止损到保本。
- 当前已实现 OrderPlan 合约：包含 symbol、side、strategy_type、order_type、entry_price、quantity、stop_loss、take_profit_levels、leverage、margin_type、position_mode、estimated_liquidation_price、liquidation_buffer_pct、reduce_only、client_order_id、strategy_version、config_snapshot_id。
- 当前已实现 MVP 执行约束：默认 leverage = 3，最大 leverage = 5，且只允许 ONE_WAY + ISOLATED。
- 当前已实现 Stop Order Guard 判定层：校验真实持仓是否存在 symbol 匹配、退出方向正确、数量覆盖、reduceOnly、状态 NEW、触发价方向正确的有效止损单；缺失时输出补挂止损动作。
- 当前已实现 Liquidation Guard 判定层：多单要求 liquidation_price < stop_loss < entry_price，空单要求 entry_price < stop_loss < liquidation_price，且止损价与强平价安全距离不低于 liquidation_buffer_pct。
- 当前已实现 Kill Switch 状态转移：触发后禁止新开仓，可标记是否平仓，并记录操作者、原因、触发时间和解除操作者。
- 当前已实现订单、成交、持仓状态机：覆盖订单提交、部分成交、完全成交、止损提交/确认/失败、止盈提交、退出成交；主订单成交但止损失败会进入 CRITICAL 并暂停新开仓。

## V0.6 AI/Funding 过滤

- [x] 实现资金费率过滤。
- [x] 实现 AI filter 接口。
- [x] 实现 deterministic stub。
- [x] 记录 AI 输入、输出、fallback 原因。
- [x] 保持真实 LLM 默认关闭。

说明：

- 当前已实现 Funding 过滤器：距离结算时间 <= 15 分钟禁止新开仓，abs(funding_rate) >= 0.0015 禁止新开仓，abs(funding_rate) >= 0.0005 输出 WARN 并将仓位乘数降为 0.5。
- 当前已实现 AI filter 接口与 deterministic stub：默认 `enabled = false` 时输出 ALLOW；新闻不可用时 fallback BLOCK；显式模拟重大风险事件时 BLOCK。
- 当前已实现 AI filter 日志 entry：记录输入 payload、输出 payload、fallback_reason、provider 和 evaluated_at，真实 LLM 仍未接入且默认关闭。

## V1.0 小资金实盘准备

- [ ] 测试网完整下单闭环。API Key 可用后再实现。
- [x] Live 启动前自检。
- [x] API 权限和 IP 白名单检查。
- [x] 小资金实盘专用配置。
- [ ] Paper Trading 连续 2 周无重大错误。
- [ ] Stop Order Guard 和 Liquidation Guard 演练通过。
- [ ] 主订单成交但止损失败的应急流程演练通过。

说明：

- 当前已实现 Live 启动前自检纯校验层：任一失败项都会禁止启动 Live，并一次性返回所有 failed_checks。
- 自检已覆盖：API 不允许提现、IP 白名单、USDⓈ-M Futures API 可用性、服务器时间偏差、database migration、缓存可用或降级、交易所规则同步、ONE_WAY、ISOLATED、leverage <= max_leverage、未知持仓、缺失止损持仓、Stop Order Guard、Liquidation Guard、数据延迟、Kill Switch、通知通道、小资金配置、`LIVE_TRADING_CONFIRM=I_UNDERSTAND_THE_RISK`。
- 当前已实现小资金实盘专用配置校验：必须使用 `small_capital_live` profile，账户权益上限 <= 1000，单笔风险 <= 0.5%，每日亏损上限 <= 1.5%，最大杠杆 <= 3，仅允许 BTCUSDT / ETHUSDT，且必须 ONE_WAY + ISOLATED。
- 当前阶段没有 Binance API Key，不做真实或测试网下单；先用真实行情驱动 Paper Trading，验证策略、风控、状态机和连续运行稳定性。
