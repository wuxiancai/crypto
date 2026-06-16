# Tasks

更新时间：2026-06-18

## 当前阶段

当前 V0.3 回测系统继续补充撮合与统计能力，同时已进入 V0.4 Paper Trading 最小闭环开发。主网真实 K 线入库仍受当前网络 Binance futures HTTP 451 限制，需要在可访问环境补验。

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
- [ ] 模拟市价滑点、止损滑点、极端滑点。
- [ ] 模拟限价未成交和部分成交。
- [x] 模拟资金费率。
- [x] 模拟交易所最小数量、最小名义价值、价格精度、数量精度。
- [ ] 模拟强平风险。
- [x] 输出整体指标与按 strategy_type 拆分指标。
- [ ] 归档 backtest_run、config_snapshot、backtest_trades。

说明：

- 当前已实现最小事件驱动回测内核：按 K 线 open_time 顺序推进、单仓位、按风险预算开仓、止盈/止损退出、输出 trade 与 final_equity。
- 当前已支持 `TREND_PULLBACK` 与 `REVERSAL_PROBE` 信号；趋势转换信号会使用自身 `risk_pct` 风险上限。
- 当前已实现 maker/taker 手续费：入场按 taker，止损按 taker，止盈按 maker。
- 当前已输出整体指标与按 `strategy_type` 拆分的交易次数、胜负、gross_pnl、fees、net_pnl。
- 当前已实现资金费率模拟，资金费进入 trade 与整体指标。
- 当前已实现交易所 `quantity_step`、`min_qty`、`min_notional` 过滤；价格精度仍待进一步细化为不同订单类型的 tick 方向。
- 极端滑点、限价未成交、部分成交、强平风险仍未完成。

## V0.4 Paper Trading

- [ ] 实现实时行情订阅。
- [x] 实现 Paper 撮合。
- [x] 实现 Paper 持仓与账户权益。
- [x] 接入主趋势策略 Paper 验证。
- [x] 接入趋势转换策略 Paper 验证。
- [x] 实现状态页或 CLI 状态输出。
- [ ] 实现基础报警。

说明：

- 当前已实现 Paper Trading 最小内核：接收策略信号、单仓位撮合、止盈/止损退出、权益更新、fills 记录和 rejected_signals 计数。
- Paper 当前支持 `TREND_PULLBACK` 与 `REVERSAL_PROBE`，趋势转换信号同样使用自身 `risk_pct`。
- 当前已实现稳定的 Paper CLI 状态格式化输出。
- 实时行情订阅和报警仍未完成。

## V0.5 风控与订单计划

- [ ] 实现主策略仓位计算。
- [ ] 实现趋势转换分级仓位计算。
- [ ] 实现止损候选选择。
- [ ] 实现 TP1/TP2/TP3 与 TP3 方向校验。
- [ ] 实现 OrderPlan。
- [ ] 实现 ONE_WAY + ISOLATED 执行约束。
- [ ] 实现 Stop Order Guard。
- [ ] 实现 Liquidation Guard。
- [ ] 实现 Kill Switch。
- [ ] 实现订单、成交、持仓状态机。

## V0.6 AI/Funding 过滤

- [ ] 实现资金费率过滤。
- [ ] 实现 AI filter 接口。
- [ ] 实现 deterministic stub。
- [ ] 记录 AI 输入、输出、fallback 原因。
- [ ] 保持真实 LLM 默认关闭。

## V1.0 小资金实盘准备

- [ ] 测试网完整下单闭环。
- [ ] Live 启动前自检。
- [ ] API 权限和 IP 白名单检查。
- [ ] 小资金实盘专用配置。
- [ ] Paper Trading 连续 2 周无重大错误。
- [ ] Stop Order Guard 和 Liquidation Guard 演练通过。
- [ ] 主订单成交但止损失败的应急流程演练通过。
