# Tasks

更新时间：2026-06-23

## 当前阶段

当前 V0.6 AI/Funding 过滤纯风控层已完成，真实行情驱动 Paper Trading 已跑通基础闭环。用户已确认下一阶段不再继续微调旧 `TREND_PULLBACK`，而是升级为独立的分层策略系统：日线主趋势、4h 子趋势、1h 确认、15m 入场，并支持 Paper/Backtest 多策略子仓和主仓/hedge 仓共存。当前暂无 Binance API Key，测试网/真实下单闭环延后到 API Key 可用后再做。

## 下一阶段：分层策略系统

- [x] 编写并复核分层策略系统设计文档：`docs/superpowers/specs/2026-06-23-layered-strategy-system-design.md`。
- [x] 新增独立策略系统模块，集中管理策略参数和信号生成。
- [x] 支持策略名：`SHORT_DAY_CORE`、`SHORT_4H_1H_ADDON`、`LONG_4H_HEDGE`、`LONG_DAY_CORE`、`LONG_4H_1H_ADDON`、`SHORT_4H_HEDGE`。
- [x] 策略系统输入必须包含 1d / 4h / 1h / 15m 已收盘 K 线历史。
- [x] 所有策略参数集中到 `LayeredStrategyConfig`，默认 `EMA15 / MA60, ATR14, DMI12, Swing20`。
- [x] PaperTradingEngine 从单仓位模型升级为按 strategy bucket 管理的多策略子仓模型。
- [x] Backtest engine 支持同一 symbol 多空子仓共存，并按 strategy_type / bucket 统计指标。
- [x] Web 状态页改为展示日线主趋势、4h 子趋势、策略候选、子仓列表和动态均线名称。
- [x] 回测页和批量回测页支持分层策略参数。
- [x] 用真实 BTCUSDT 历史验证：截图对应的 2026-05-13 后能捕捉日线空头主趋势，2026-06-12 20:00 后能捕捉日线空头下的 4h 反弹多仓。
- [x] 多头趋势必须实现完全对称逻辑。
- [x] 实时 Paper Trading 已新增最小复盘持久化，把信号评估、拒绝信号、成交和平仓后/每根 K 线持仓快照写入 `paper_runtime_events`。

说明：

- 2026-06-23 已新增 `app.strategy.layered_strategy`，实时 Paper 默认开启分层策略；旧 4h/1h/15m 测试路径在没有 1d 数据时保持兼容。
- 2026-06-23 Paper snapshot 新增 `open_positions`，同时保留旧 `open_position` 兼容字段；状态页可展示多个 strategy bucket 子仓。
- 2026-06-23 回测页当前已通过 PaperTradingEngine 获得多子仓撮合能力，并默认拉取 1d/4h/1h/15m；`StrategyBacktestResult` 已提供 `strategy_metrics` 和 `bucket_metrics` 聚合结果，批量回测默认参数已同步为 `EMA15 / MA60, ATR14, Swing20, fee/risk=0, TRAILING, enable_reversal_probe=false`。
- 2026-06-23 策略回测结果已新增最大回撤指标，按已平仓权益曲线计算 `max_drawdown` 和 `max_drawdown_pct`，并在回测页面顶部展示。
- 2026-06-23 策略回测结果已新增盈亏比 `profit_loss_ratio`，按平均盈利单净利润 / 平均亏损单绝对净亏损计算，并在回测页面顶部展示。
- 2026-06-23 策略回测结果已新增 `symbol_metrics`，按交易对聚合交易次数、胜负和净盈亏，并在回测页面“策略 / Bucket / 交易对统计”区展示。
- 2026-06-24 策略回测页面已新增“参数组合对比”表，复用最近回测归档并按账户权益从高到低排序，便于横向比较均线、ATR、DMI、Swing、手续费/风险、周期、净盈亏、胜率、盈亏比、最大回撤、Bucket 净盈亏和交易次数。
- 2026-06-24 实时 Paper Trading 已新增 `paper_runtime_events` 复盘事件表；`scripts/run_paper_realtime.py` 默认注入数据库 session factory，每根 K 线处理后写入 signal / snapshot，并在发生拒绝或成交时额外写入 rejected_signal / fill。
- 2026-06-23 已新增截图语义对应的 BTC fixture 回归用例，验证日线空头主仓和日线空头下 4h 反弹多仓方向；真实 Binance 历史窗口回放以截图日期 `2026-05-13` 为准，避免误按文字中的 2025 年验证。
- 2026-06-23 已新增 `scripts/validate_layered_btc_history.py`，复用真实 Binance K 线缓存和实时策略适配器验证默认 BTC probe：`SHORT_4H_HEDGE` 命中 `2026-05-13 23:59:59 UTC+8`，entry `78794.70`；`SHORT_DAY_CORE` 命中 `2026-06-01 07:59:59 UTC+8`，entry `73653.20`；`LONG_4H_HEDGE` 命中 `2026-06-13 10:59:59 UTC+8`，entry `63612.00`。

2026-06-20 Binance 连接修复：

- [x] 按 Binance USDⓈ-M Futures 官方文档将实时 K 线 WebSocket 主网入口迁移为 routed market endpoint：`wss://fstream.binance.com/market/stream?...`。
- [x] Ubuntu 生成的 `.env.ports.generated` 默认 `BINANCE_WEBSOCKET_BASE_URL` 已从测试网 `wss://fstream.binancefuture.com` 改为主网 `wss://fstream.binance.com/market`，避免主网 REST 与测试网 WebSocket 混跑。
- [x] WebSocket 默认连接参数已按官方 ping/pong 规则放宽：客户端 ping 间隔 180 秒，pong 超时 600 秒，并在断线、24 小时断开或 keepalive timeout 后自动指数退避重连。
- [x] Binance REST K 线拉取已增加短退避重试：连接超时/网络错误、HTTP 408/429/503 默认最多 3 次；HTTP 451 仍直接提示当前网络/地区受限。
- [x] 状态页顶部“永续实时价格”改为订阅 Binance USDⓈ-M Futures `<symbol>@ticker` WebSocket，使用 ticker 事件里的 last price，不再依赖成交、持仓或已收盘 K 线策略评估刷新。

2026-06-20 回测胜率与交易成本诊断：

- [x] 读取 Ubuntu PostgreSQL 回测归档，确认截图对应 run：`50/200` = run 2，`30/120` = run 3，`15/60` = run 4。
- [x] 确认低胜率本身不是唯一问题：`15/60` 与 `30/120` 胜率约 44% 但盈利；`50/200` 亏损主要来自慢参数下止损密集、手续费吞噬计划风险。
- [x] 新增入场成本过滤：下单前估算 `开仓 taker fee + 止损 taker fee`，若超过计划止损风险的 `max_fee_to_risk_ratio` 则拒绝入场；默认 `0.25`。
- [x] Web 回测页新增“手续费/风险上限”参数；回测归档 config snapshot 新增 `content` 字段保存完整 JSON 参数，避免以后只能靠 hash 反推参数。
- [x] `scripts/run_strategy_backtest_batch.py` 的固定参数已抽成批量配置：支持用户指定快/慢均线类型、快/慢周期起止与步进、回测周期、ATR/DMI/Swing 参数组、手续费/风险上限组、止盈模式组。
- [x] 策略回测页新增“批量参数回测”按钮，新标签页打开 `/backtest/batch`，页面可手动输入批量脚本参数并执行同一套批量回测与归档逻辑。
- [x] 批量回测脚本在执行每组参数前会先查 `backtest_runs + config_snapshots`，若数据库已有相同配置 hash 的策略回测结果，默认跳过该组合并复用已有指标进入分析；只有显式 `--rerun-completed` 才会重跑。
- [x] `/backtest/batch` 新增“停止回测”按钮和终端风格运行日志；页面轮询 `/api/backtest/batch/status` 展示 `[run]`、`[ARCHIVED]`、耗时、剩余预计和停止状态。倒计时日志动态更新同一行，不再每秒追加刷屏；停止请求会在当前组合结束后的安全点退出。
- [x] 最近回测结果表新增 ATR、DMI、Swing、手续费/风险 4 列，避免同一均线组合但不同精修参数的结果看起来重复。
- [x] 批量参数默认值已收敛：过滤快线>=慢线默认“是”，慢线结束默认 200 且实际包含 200，ATR/DMI 默认只测 12、14，Swing Lookback 默认只测 20、30，手续费/风险上限默认 `0.25,0`，其中 `0` 表示关闭该过滤。
- [x] 批量回测所有组合完成后后台任务自动进入空闲状态；页面完成后只刷新一次并显示结果，按钮改为一行排列，运行日志改为白底黑字。
- [x] `/backtest/batch` 新增“清空回测记录”按钮；批量任务运行中会拒绝清空，空闲时会删除策略回测归档的 `backtest_trades`、`backtest_runs` 和不再被引用的 `strategy_backtest` 配置快照。
- [x] 修复批量回测旧 checkpoint 导致的假 skip：checkpoint 中成功但数据库已无同配置 run 时会重新回测并归档；批量页面提交后会清理 `run/stop/clear` URL 参数，避免完成后刷新又重复启动任务。

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
- [x] 写入 BTCUSDT、ETHUSDT 真实 K 线。
- [x] 实现 K 线完整性验证。
- [x] 实现多周期已收盘数据对齐函数。
- [x] 实现 EMA、ATR、ADX、DI_PLUS、DI_MINUS、Bollinger Bands。
- [x] 用第三方库或固定样本校验指标误差。

说明：

- 当前已实现 EMA、ATR、ADX、DI_PLUS、DI_MINUS、Bollinger Bands。
- 当前已添加 `tests/fixtures/indicator_golden.json` 固定样本校验。
- Binance 主网 futures endpoint 当前本机可访问；`scripts/sync_klines.py` 默认同步分层策略所需 `1d / 4h / 1h / 15m`。
- 2026-06-23 已启动本地 PostgreSQL Docker Compose 并完成 migration；已用 Binance 主网 futures 写入 BTCUSDT、ETHUSDT 各 `1d / 4h / 1h / 15m` 最近已收盘 K 线。
- 2026-06-23 已修复 Binance REST 最新未收盘 K 线误标为 `is_closed=True` 的问题：`fetch_klines()` 现在只返回 `close_time <= now_ms` 的已收盘 K 线。本地库已清理未来 K 线，复查 `future_klines=0`。

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

- 历史实现已支持 `TREND_PULLBACK` 主趋势入场信号；下一阶段该名称仅作为兼容语义保留。
- 做多要求：主趋势允许做多、价格回踩到快线/ATR 区域、15m 看涨确认、RR 达标。
- 做空要求：主趋势允许做空、价格反弹到快线/ATR 区域、15m 看跌确认、RR 达标。
- 当前主趋势策略使用 2R 阶梯移动止盈：触达第一个 2R 后不立即全平，而是把该 2R 价设为移动止盈价；每继续完成一个新的 2R 阶梯，移动止盈价再推进到新阶梯价；止损使用最近 swing low / swing high。
- 历史实现已支持 `REVERSAL_PROBE` 趋势转换试仓信号；下一阶段如保留，应映射为更明确的 hedge/transition 策略。
- 趋势转换输出通用事件 `REVERSAL_LONG_ENTRY` / `REVERSAL_SHORT_ENTRY`，并通过 `signal_level = EARLY | CONFIRMED` 区分早期/确认。
- 趋势转换评分已执行 `min(raw_score, 100)` 封顶。
- 趋势转换做多/做空已实现距离快线过远的追涨追跌过滤。
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
- [x] 支持 3个月 / 6个月 / 1年 / 2年分页历史回测。

说明：

- 当前已实现最小事件驱动回测内核：按 K 线 open_time 顺序推进、单仓位、按风险预算开仓、止盈/止损退出、输出 trade 与 final_equity。下一阶段必须升级为多策略子仓回测。
- 当前已支持 `TREND_PULLBACK` 与 `REVERSAL_PROBE` 信号；趋势转换信号会使用自身 `risk_pct` 风险上限。
- 当前已实现永续合约默认成本：maker 挂单手续费 0.02%，taker 吃单手续费 0.05%；入场按 taker，止损按 taker，止盈按 maker。
- 当前已输出整体指标与按 `strategy_type` 拆分的交易次数、胜负、gross_pnl、fees、net_pnl。
- 当前已实现 8 小时资金费率模拟，资金费进入 trade 与整体指标；当前资金费率为可配置参数，默认 0，尚未自动接入 Binance 实时 funding rate。
- 当前已实现交易所 `quantity_step`、`min_qty`、`min_notional` 过滤；价格精度仍待进一步细化为不同订单类型的 tick 方向。
- 当前已实现止损专用滑点与跳空越过止损时的极端成交价。
- 当前已实现限价未触达不成交、限价部分成交比例和 partial_fills 统计。
- 当前已实现价格 tick 方向细化：买入向上取 tick，卖出向下取 tick。
- 当前已实现强平风险模拟，触发强平时优先于止损退出并计入 liquidations。
- 当前已实现 `backtest_runs`、`config_snapshots`、`backtest_trades` 归档，并提供 repository 写入入口。
- 当前 Web 状态页已新增“策略回测”按钮，点击后以新标签页打开 `/backtest`。回测页复用当前实时策略适配器和 PaperTradingEngine，用 Binance REST 历史 K 线回放 4h / 1h / 15m 多周期策略；旧默认曾是 EMA50 / EMA200，当前策略参数已迁移到 EMA15 / MA60，下一阶段要统一为分层策略参数。
- 当前策略回测已支持分页历史回测：用户可选择最近 3个月 / 6个月 / 1年 / 2年，后端按 Binance 单次 1500 根限制自动分页拉取 4h / 1h / 15m 历史 K 线。
- 当前 Web 策略回测已接入数据库归档：每次成功回测会写入 `backtest_runs`、`backtest_trades` 和 `config_snapshots`。2026-06-19 已确认 Ubuntu 服务器此前表存在但行数为 0，根因是 `/backtest` 页面只渲染结果、没有调用归档 repository；现已修复。
- 当前 Web 策略回测已增加页面级错误展示：Binance REST 超时、DNS/网络失败或其他回测执行异常会显示为“回测执行失败：...”，不再返回空白页或 empty reply。

## V0.4 Paper Trading

- [x] 实现实时行情订阅。
- [x] 实现 Paper 撮合。
- [x] 实现 Paper 持仓与账户权益。
- [x] 接入主趋势策略 Paper 验证。
- [x] 接入趋势转换策略 Paper 验证。
- [x] 实现状态页或 CLI 状态输出。
- [x] 实现基础报警。

说明：

- 当前已实现 Paper Trading 最小内核：接收策略信号、单仓位撮合、止盈/止损退出、权益更新、fills 记录和 rejected_signals 计数。下一阶段必须升级为多策略子仓撮合。
- 当前 Paper Trading 默认按永续合约模拟：初始资金 1000 USDT、默认 10X 杠杆、maker 0.02%、taker 0.05%、资金费每 8 小时结算一次；资金费率当前默认 0，可通过启动参数配置。
- 当前 Paper Trading 的 `TREND_PULLBACK` 默认使用 2R 阶梯移动止盈：价格触达 2R 目标后进入“移动止盈中”，把 2R 价作为移动止盈价；价格继续顺势每推进一个 2R 阶梯，移动止盈价同步推进；回撤触达当前移动止盈价才平仓。可通过 `--trend-pullback-take-profit-mode FIXED` 回退固定止盈。
- 当前已修复回测/Paper 出场撮合的关键未来函数问题：持仓会记录入场交易对和入场周期，只有同一交易对、同一周期的 K 线才能触发止盈/止损，避免 BTC 持仓被 ETH K 线平仓，或 15m 入场被同一时间的 1h/4h 高低点提前平仓。
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
- 当前历史实现约束为 ONE_WAY + ISOLATED。下一阶段 Paper/Backtest 必须先支持策略子仓和同一 symbol 多空共存；Live HEDGE 模式必须另行自检和确认后才能接入。
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
- 当前已实现小资金实盘专用配置校验：必须使用 `small_capital_live` profile，账户权益上限 <= 1000，单笔风险 <= 0.5%，每日亏损上限 <= 1.5%，最大杠杆 <= 10，仅允许 BTCUSDT / ETHUSDT，且必须 ONE_WAY + ISOLATED。
- 当前阶段没有 Binance API Key，不做真实或测试网下单；先用真实行情驱动 Paper Trading，验证策略、风控、状态机和连续运行稳定性。
- 当前已实现 Paper Trading 连续运行健康检查：检测 WebSocket 连接、行情延迟、Paper 回撤、拒单数量和运行时错误；该模块用于后续“连续 2 周无重大错误”的自动化验收。
- 当前已实现 Paper Trading 状态持久化/恢复入口：PaperSnapshot 可无损序列化为 JSON payload，并支持保存到本地状态文件和从状态文件恢复；Decimal 金额以字符串保存，避免浮点误差。
- 当前已实现持久化 Paper stream runner：启动时从状态文件恢复 PaperTradingEngine，每处理一根已收盘 K 线后写回 PaperSnapshot，避免真实行情模拟交易重启后丢失权益、持仓、成交和拒单计数。
- 当前已实现真实行情 Paper runner 与脚本入口：`scripts/run_paper_realtime.py` 会连接 Binance WebSocket 已收盘 K 线流，并使用持久化 Paper stream runner 保存状态。
- 当前真实行情 Paper runner 已支持多周期订阅，默认订阅 15m / 1h / 4h；已新增 MultiTimeframeKlineCache，用于按 symbol 聚合多周期已收盘 K 线。
- 当前已新增实时策略适配器：把 4h / 1h / 15m 已收盘 K 线历史转换为 EMA、ATR、ADX、DI、swing 与趋势转换结构输入，并复用现有趋势识别、`TREND_PULLBACK` 主趋势回踩策略和 `REVERSAL_PROBE` 趋势转换策略。下一阶段要改为调用独立分层策略系统，并加入 1d 历史。
- 当前 `scripts/run_paper_realtime.py` 默认路径已不再永久 WAIT；不注入自定义策略函数时，会通过多周期缓存生成实时主趋势或趋势转换 Paper 信号。有持仓时默认不加仓，避免重复入场噪音。
- 当前已修复 signal router 字段丢失问题：主趋势与趋势转换信号经路由后会保留 entry_price、stop_loss、take_profit、risk_reward、risk_pct、score、signal_level 等执行/统计字段。
- 当前趋势转换信号已补充可执行 entry_price、ATR 止损与 2R take_profit，Paper 不再依赖默认止损止盈模拟趋势转换策略。
- 当前已新增极简中文 Web 状态页：`scripts/run_paper_status_web.py` 读取 `runtime/paper-state.json`，展示账户权益、持仓情况、全部模拟交易记录、买入价、卖出价、使用策略和 rejected signals，并每 5 秒自动刷新。
- 当前真实行情模拟交易默认本金已改为 1000 USDT。
- 当前已修复实时 Paper 启动后长时间无信号的问题：默认策略需要 4h / 1h / 15m 多周期指标历史，尤其 EMA200；现在启动时会先用 Binance REST 默认拉取最近 250 根真实已收盘 K 线预热策略缓存，再接 WebSocket 实时 K 线推进。
- 当前 Web 状态页已增加系统运行时间，方便判断模拟交易服务是否中途断开或重启。
- 当前 Web 状态页仍保持 5 秒自动刷新，但已从浏览器级整页刷新改为后台软刷新，避免页面闪烁，并保留当前选中的交易对和 K 线周期。
- 当前 Web 状态页已增加错误日志框，用红色字体显示运行异常摘要；`Traceback`、`File ...`、`map_httpcore_exceptions` 等 Python 调用栈不直接展示，`ConnectTimeout` 会摘要为 Binance REST 连接超时提示。若超时来自历史预热，会保留交易对和周期，例如 `BTCUSDT 4h 历史数据预热失败`。
- 当前 Binance REST 历史预热失败不会再让实时 Paper runner 退出；单个交易对/周期预热失败会记录日志并继续进入 WebSocket 主流程。
- 当前 Web 状态页顶部已显示 BTCUSDT / ETHUSDT 永续实时价格；该价格来自 Binance USDⓈ-M Futures ticker WebSocket，状态文件暂时没有 ticker 时才回退到成交、持仓或策略评估价格。当状态文件暂时没有策略评估数据时，策略触发条件和 K 线图区会显示“等待实时策略评估更新”。
- 当前已修复“运行很久但页面没有任何输出”的可观察性问题：Paper 状态文件会记录最近 50 条策略评估结果。早期 Web 状态页曾显示“最近策略输出”调试表；现在主页面已隐藏该表，避免无意义的 `SYSTEM / no actionable signal` 干扰用户阅读，复盘数据仍保留在状态文件中。
- 当前已修复 5m 高频输出淹没策略视图的问题：状态文件按“交易对 + 周期”保留最新策略输出，页面会同时展示各周期最新状态，而不是只被 5m 刷屏。
- 当前 Web 状态页已增加“策略K线图”：使用内嵌 SVG 绘制 4h / 1h / 15m K 线图并叠加快慢线。下一阶段要加入 1d 图和动态均线名称，禁止继续写死 EMA50/EMA200。
- 当前 Web 状态页已增加精简版“策略触发条件”：只展示当前最接近触发的策略方向，例如主趋势做空时不再显示主趋势做多。下一阶段要改为展示 `SHORT_DAY_CORE` / `SHORT_4H_1H_ADDON` / `LONG_4H_HEDGE` 等明确策略候选。
- 当前 Web 状态页的“策略触发条件”已改为按交易对分别显示最新条件卡，避免 BTCUSDT / ETHUSDT 同时运行时只展示全局最新一条，导致用户拿 BTC 图对照 ETH 条件。
- 当前 Web 状态页已新增策略回测入口 `/backtest`，用于在等待长期 Paper Trading 之前，先用历史 K 线快速验证当前策略和不同 EMA 参数组合。
- 当前策略回测页已改为单交易对回测：默认 BTC，可切换 ETH，避免 BTC/ETH 成交记录混在同一张报表里造成误判；回测参数栏已压缩为一行展示。
- 当前策略回测已增加历史 K 线本地缓存：数据按交易对和周期保存到 `runtime/backtest-klines/`；同一交易对后续回测更短周期或不同 EMA 参数时复用缓存，只在所需时间段缺失时补拉 Binance REST 数据。
- 当前策略回测页新增批量参数回测入口 `/backtest/batch`：页面可输入 EMA/MA 类型、快慢周期范围与步进、回测周期、ATR/DMI/Swing、手续费/风险上限和止盈模式，执行逻辑仍复用 `scripts/run_strategy_backtest_batch.py` 与现有 `run_strategy_backtest()`。
- 当前批量回测会基于归档配置 hash 跳过数据库中已存在的同参数结果，并把已有 run 的 final_equity、net_pnl、胜负和胜率写入 checkpoint，保证全跳过时仍可选出 best primary。
- 当前批量回测 Web 入口使用后台任务执行，页面提供停止按钮和运行日志面板；日志内容由脚本显式回调输出。所有组合完成后后台任务会自动停止并进入空闲状态；页面在完成后只刷新一次展示结果。`本轮倒计时` 会在 Web 日志中替换上一条倒计时行，表现为读秒而不是按秒新增日志。批量默认过滤快线>=慢线，并把 ATR/DMI 精修默认收敛为 12、14，Swing Lookback 默认收敛为 20、30，手续费/风险上限默认只比较 0.25 与关闭过滤。
- 已完成：策略回测参数组合对比已补充最大回撤、盈亏比和按 strategy bucket 展开的净盈亏贡献。
