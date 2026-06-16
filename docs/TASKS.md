# Tasks

更新时间：2026-06-16

## 当前阶段

当前已进入 V0.1 数据与指标阶段。项目骨架、配置保护、基础 migration、K 线解析/校验、多周期已收盘对齐、基础指标和 K 线 repository 已完成第一版。

## V0.1 数据与指标

- [x] 初始化项目结构。
- [x] 建立配置加载与环境变量校验。
- [x] 建立 Alembic migration。
- [x] 创建 `symbols`、`klines`、`indicator_snapshots`、`config_snapshots` 基础表。
- [x] 实现 Binance USDⓈ-M K 线拉取。
- [ ] 写入 BTCUSDT、ETHUSDT 真实 K 线。
- [x] 实现 K 线完整性验证。
- [x] 实现多周期已收盘数据对齐函数。
- [ ] 实现 EMA、ATR、ADX、DI_PLUS、DI_MINUS、Bollinger Bands。
- [ ] 用第三方库或固定样本校验指标误差。

说明：

- 当前已实现 EMA、ATR、Bollinger Bands；ADX、DI_PLUS、DI_MINUS 尚未实现。
- Binance 主网 futures endpoint 在当前网络返回 HTTP 451；已用 `BINANCE_BASE_URL=https://testnet.binancefuture.com` 完成 dry-run 验证。
- 真实 PostgreSQL 入库尚未执行；K 线 repository 已用 SQLite 内存库测试 upsert 行为。

## V0.2 策略信号

- [ ] 实现趋势识别状态：UPTREND、DOWNTREND、RANGE、TRANSITION、UNKNOWN。
- [ ] 实现主趋势回踩做多。
- [ ] 实现主趋势反弹做空。
- [ ] 实现趋势转换早期试仓信号。
- [ ] 实现趋势转换确认试仓信号。
- [ ] 实现趋势转换评分封顶。
- [ ] 实现禁止追涨追跌过滤。
- [ ] 实现信号生成顺序：同步/风控/退出优先，新开仓靠后。

## V0.3 回测系统

- [ ] 实现事件驱动回测引擎。
- [ ] 复用实盘策略和风控规则。
- [ ] 模拟 maker/taker 手续费。
- [ ] 模拟市价滑点、止损滑点、极端滑点。
- [ ] 模拟限价未成交和部分成交。
- [ ] 模拟资金费率。
- [ ] 模拟交易所最小数量、最小名义价值、价格精度、数量精度。
- [ ] 模拟强平风险。
- [ ] 输出整体指标与按 strategy_type 拆分指标。
- [ ] 归档 backtest_run、config_snapshot、backtest_trades。

## V0.4 Paper Trading

- [ ] 实现实时行情订阅。
- [ ] 实现 Paper 撮合。
- [ ] 实现 Paper 持仓与账户权益。
- [ ] 接入主趋势策略 Paper 验证。
- [ ] 接入趋势转换策略 Paper 验证。
- [ ] 实现状态页或 CLI 状态输出。
- [ ] 实现基础报警。

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
