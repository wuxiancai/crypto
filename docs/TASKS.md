# Tasks

更新时间：2026-06-19

## 当前阶段

当前 V0.6 AI/Funding 过滤纯风控层已完成，正在推进真实行情驱动的 Paper Trading 稳定性验证。当前暂无 Binance API Key，测试网/真实下单闭环延后到 API Key 可用后再做。主网真实 K 线入库仍受当前网络 Binance futures HTTP 451 限制，需要在可访问环境补验。

## Ubuntu 部署

- [x] 提供 Ubuntu 一键部署脚本。
- [x] 提供启动脚本。
- [x] 实现 PostgreSQL / Web 页面端口冲突自动顺延。
- [x] 生成 `.env.ports.generated` 记录最终端口和 DATABASE_URL。

说明：

- `scripts/deploy_ubuntu.sh` 用于首次部署，会安装依赖、启动 Docker/PostgreSQL、执行 migration、启动真实行情 Paper Trading 和中文 Web 状态页。
- `scripts/start_ubuntu.sh` 用于后续启动，会自动检测端口冲突并顺延。
- 默认 PostgreSQL 端口 `55432`，默认 Web 页面端口 `8765`；如被占用会自动尝试下一个端口。
- 部署说明见 `docs/UBUNTU_DEPLOY.md`。

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
- [x] 提供当前实时策略的历史 K 线 Web 回测页。

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
- 当前 Web 状态页已新增“策略回测”按钮，点击后以新标签页打开 `/backtest`。回测页复用当前实时策略适配器和 PaperTradingEngine，用 Binance REST 历史 K 线回放 4h / 1h / 15m 多周期策略；默认 EMA50 / EMA200、历史 K 线 250 根、1000 USDT，用户可输入 EMA 快线、EMA 慢线和历史 K 线根数比较不同参数。

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
- 当前已实现 Paper Trading 连续运行健康检查：检测 WebSocket 连接、行情延迟、Paper 回撤、拒单数量和运行时错误；该模块用于后续“连续 2 周无重大错误”的自动化验收。
- 当前已实现 Paper Trading 状态持久化/恢复入口：PaperSnapshot 可无损序列化为 JSON payload，并支持保存到本地状态文件和从状态文件恢复；Decimal 金额以字符串保存，避免浮点误差。
- 当前已实现持久化 Paper stream runner：启动时从状态文件恢复 PaperTradingEngine，每处理一根已收盘 K 线后写回 PaperSnapshot，避免真实行情模拟交易重启后丢失权益、持仓、成交和拒单计数。
- 当前已实现真实行情 Paper runner 与脚本入口：`scripts/run_paper_realtime.py` 会连接 Binance WebSocket 已收盘 K 线流，并使用持久化 Paper stream runner 保存状态。
- 当前真实行情 Paper runner 已支持多周期订阅，默认订阅 15m / 1h / 4h；已新增 MultiTimeframeKlineCache，用于按 symbol 聚合多周期已收盘 K 线。
- 当前已新增实时策略适配器：把 4h / 1h / 15m 已收盘 K 线历史转换为 EMA、ATR、ADX、DI、swing 与趋势转换结构输入，并复用现有趋势识别、`TREND_PULLBACK` 主趋势回踩策略和 `REVERSAL_PROBE` 趋势转换策略。
- 当前 `scripts/run_paper_realtime.py` 默认路径已不再永久 WAIT；不注入自定义策略函数时，会通过多周期缓存生成实时主趋势或趋势转换 Paper 信号。有持仓时默认不加仓，避免重复入场噪音。
- 当前已修复 signal router 字段丢失问题：主趋势与趋势转换信号经路由后会保留 entry_price、stop_loss、take_profit、risk_reward、risk_pct、score、signal_level 等执行/统计字段。
- 当前趋势转换信号已补充可执行 entry_price、ATR 止损与 2R take_profit，Paper 不再依赖默认止损止盈模拟趋势转换策略。
- 当前已新增极简中文 Web 状态页：`scripts/run_paper_status_web.py` 读取 `runtime/paper-state.json`，展示账户权益、持仓情况、全部模拟交易记录、买入价、卖出价、使用策略和 rejected signals，并每 5 秒自动刷新。
- 当前真实行情模拟交易默认本金已改为 1000 USDT。
- 当前已修复实时 Paper 启动后长时间无信号的问题：默认策略需要 4h / 1h / 15m 多周期指标历史，尤其 EMA200；现在启动时会先用 Binance REST 默认拉取最近 250 根真实已收盘 K 线预热策略缓存，再接 WebSocket 实时 K 线推进。
- 当前 Web 状态页已增加系统运行时间，方便判断模拟交易服务是否中途断开或重启。
- 当前 Web 状态页已增加错误日志框，只展示 `paper-realtime.log` 中的错误/异常/失败/`Historical warmup skipped` 行，并用红色字体显示。
- 当前已修复“运行很久但页面没有任何输出”的可观察性问题：Paper 状态文件会记录最近 50 条策略评估结果。早期 Web 状态页曾显示“最近策略输出”调试表；现在主页面已隐藏该表，避免无意义的 `SYSTEM / no actionable signal` 干扰用户阅读，复盘数据仍保留在状态文件中。
- 当前已修复 5m 高频输出淹没策略视图的问题：状态文件按“交易对 + 周期”保留最新策略输出，页面会同时展示各周期最新状态，而不是只被 5m 刷屏。
- 当前 Web 状态页已增加“策略K线图”：使用内嵌 SVG 绘制 4h / 1h / 15m K 线图，并叠加 EMA50、EMA200；用户可点击周期按钮切换对应图表。页面同时展示核心策略摘要，例如 `4h EMA200 > EMA50：空头基础`、主策略回踩规则和趋势转换试仓规则。
- 当前 Web 状态页已增加精简版“策略触发条件”：只展示当前最接近触发的策略方向，例如主趋势做空时不再显示主趋势做多；页面顶部显示交易对、当前趋势、已满足进度和“还差”条件，计算公式默认折叠到“计算明细”。主趋势诊断已拆分为空头/多头结构与动能确认；结构只按 EMA50/EMA200 排列判断，价格位置留给 15m 回踩/反弹条件。
- 当前 Web 状态页的“策略触发条件”已改为按交易对分别显示最新条件卡，避免 BTCUSDT / ETHUSDT 同时运行时只展示全局最新一条，导致用户拿 BTC 图对照 ETH 条件。
- 当前 Web 状态页已新增策略回测入口 `/backtest`，用于在等待长期 Paper Trading 之前，先用历史 K 线快速验证当前策略和不同 EMA 参数组合。
