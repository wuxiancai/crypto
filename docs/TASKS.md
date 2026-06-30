# Tasks

更新时间：2026-06-24

## 当前阶段

当前 V0.6 AI/Funding 过滤纯风控层已完成，真实行情驱动 Paper Trading 已跑通基础闭环。2026-06-30 用户要求按 `交易逻辑优化.md` 执行策略内核升级：新版内核为 `WEEKLY_DAILY_H4_V1`，只保留 `WEEKLY / DAILY / H4` 三类仓位，并删除旧内核运行入口，确保 Paper/Backtest/Web 状态页按新内核执行。

版本边界：第一版只开发 Backtest、Paper Trading、Web 状态/复盘和模拟风控闭环，不开发测试网下单、真实下单、API 下单适配器或小资金实盘。第二版才允许开发 Live Trading；第二版开发永久暂停，除非用户明确发出“开始开发第二版实盘交易”的指令。

## 当前阶段：WEEKLY_DAILY_H4_V1 策略内核升级

- [ ] 冻结升级决策：`交易逻辑优化.md` 是新版策略需求源，旧 `DAY_CORE / FOUR_HOUR_ADDON / FOUR_HOUR_HEDGE` 不得映射为新 `WEEKLY / DAILY / H4`。
- [ ] 新增独立策略内核模块：`app.strategy.weekly_daily_h4_strategy`。
- [ ] 新增 canonical 仓位层级、交易模式、生命周期和控制层合同。
- [ ] Paper/Backtest/Web 状态页切换到 `WEEKLY_DAILY_H4_V1`，删除旧 `enable_layered_strategy` 运行开关。
- [ ] 旧 `LAYERED_DAILY_V1` 只能作为历史代码或测试背景存在，不允许成为默认或 fallback 策略内核。
- [ ] 新内核验证完成后更新 Handoff 并提交 git。

2026-06-30 实施进度：

- [x] 新增 `app/strategy/position_hierarchy.py`、`app/strategy/trade_controls.py`、`app/strategy/weekly_daily_h4_strategy.py`。
- [x] Paper/Backtest/Realtime adapter 切换为 `WEEKLY_DAILY_H4_V1`。
- [x] 删除旧 `enable_layered_strategy` 运行开关、旧 `app/strategy/layered_strategy.py`、旧 pullback/reversal/trend detector 策略模块和旧 layered 验证/恢复脚本。
- [x] 启动同步、实时订阅、历史 warmup、策略回测改为当前内核周期 `1w / 1d / 4h`。
- [x] 新增 v2 合同、策略、Paper、adapter 测试。
- [ ] 旧 v0/v1 策略测试仍需后续归档或改写为 v2 口径；本次不再以旧内核断言作为验收标准。

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
- [x] 新增 `scripts/show_paper_runtime_events.py`，可按 limit、event_type、symbol、strategy_type、bucket 查询最近 Paper 复盘事件。
- [x] Web 状态页新增 `/paper/events` 只读复盘页，可按事件类型、交易对、策略和 bucket 查询 Paper Runtime 事件。

说明：

- 2026-06-23 已新增 `app.strategy.layered_strategy`，实时 Paper 默认开启分层策略；旧 4h/1h/15m 测试路径在没有 1d 数据时保持兼容。
- 2026-06-23 Paper snapshot 新增 `open_positions`，同时保留旧 `open_position` 兼容字段；状态页可展示多个 strategy bucket 子仓。
- 2026-06-23 回测页当前已通过 PaperTradingEngine 获得多子仓撮合能力，并默认拉取 1d/4h/1h/15m；`StrategyBacktestResult` 已提供 `strategy_metrics` 和 `bucket_metrics` 聚合结果。2026-06-24 上线体检后，默认参数统一为 `EMA15 / MA60, ATR14, DMI12, Swing20, fee/risk=0.25, TRAILING, enable_reversal_probe=false`，批量回测默认同时保留 `0` 作为关闭成本过滤的对照组。
- 2026-06-23 策略回测结果已新增最大回撤指标，按已平仓权益曲线计算 `max_drawdown` 和 `max_drawdown_pct`，并在回测页面顶部展示。
- 2026-06-23 策略回测结果已新增盈亏比 `profit_loss_ratio`，按平均盈利单净利润 / 平均亏损单绝对净亏损计算，并在回测页面顶部展示。
- 2026-06-23 策略回测结果已新增 `symbol_metrics`，按交易对聚合交易次数、胜负和净盈亏，并在回测页面“策略 / Bucket / 交易对统计”区展示。
- 2026-06-24 策略回测页面已新增“参数组合对比”表，复用最近回测归档并按账户权益从高到低排序，便于横向比较均线、ATR、DMI、Swing、手续费/风险、周期、净盈亏、胜率、盈亏比、最大回撤、Bucket 净盈亏和交易次数。
- 2026-06-24 策略回测“参数组合对比”的 Bucket 净盈亏列已支持展开明细，可查看每个 bucket 的交易次数、胜负和净盈亏。
- 2026-06-24 实时 Paper Trading 已新增 `paper_runtime_events` 复盘事件表；`scripts/run_paper_realtime.py` 默认注入数据库 session factory，每根 K 线处理后写入 signal / snapshot，并在发生拒绝或成交时额外写入 rejected_signal / fill。
- 2026-06-24 已新增 `scripts/show_paper_runtime_events.py` 最小复盘 CLI，用于直接查看 `paper_runtime_events` 里的 signal / rejected_signal / fill / snapshot 摘要。
- 2026-06-24 已新增 Web 只读复盘页 `/paper/events`，模拟交易看板顶部提供“Paper复盘”入口，页面可按 `event_type`、`symbol`、`strategy_type`、`bucket` 和 UTC+8 时间范围过滤事件，并支持快捷过滤、展开完整 payload、查看事件类型统计，以及把 fill 与前序 signal/snapshot 串成交易时间线。
- 2026-06-24 日线核心仓触发条件已改为完整链路：`SHORT_DAY_CORE` / `LONG_DAY_CORE` 必须同时满足日线主趋势、4h 子趋势、1h 确认和 15m 入场条件才输出开仓信号；状态页同一策略卡片会完整展示 1d / 4h / 1h / 15m 条件。
- 2026-06-24 实时 Paper Trading 已将 Binance WebSocket 已收盘 K 线写入 `klines` 表；下次启动时 `scripts/sync_klines.py` 仍会兜底校验，但正常运行期间产生的 15m / 1h K 线不应再只靠重启补齐。
- 2026-06-24 分层策略状态页不再显示已确认 regime 下的 `required=false` 当前动能观察项；15m 入场条件支持“快线区域或顺势延续”，避免强趋势深跌时因反弹不到快线附近而长期无法开仓。2026-06-27 新开 DAY_CORE / FOUR_HOUR_ADDON 已新增防追单与当前顺势过滤：空头要求 4h 当前斜率向下、4h 收盘未站上快线、1h 当前斜率向下、15m 不低于快线 `1.5 * ATR` 以外；多头完全对称。价格站上/跌破 4h 快线期间暂停同向新开仓或加仓，重新收回/站回快线后才恢复资格。
- 2026-06-24 状态页兼容旧 15m 快线区域条件文案并按顺势延续显示为满足；策略 K 线图支持滚轮缩放可见 K 线数量，Shift+滚轮平移历史窗口。
- 2026-06-24 模拟交易看板顶部实时价格支持按上次刷新涨跌变色，账户权益右侧新增按 UTC+8 自然日计算的累计收益卡，策略 K 线图默认展示 15m 周期。
- 2026-06-23 已新增截图语义对应的 BTC fixture 回归用例，验证日线空头主仓和日线空头下 4h 反弹多仓方向；真实 Binance 历史窗口回放以截图日期 `2026-05-13` 为准，避免误按文字中的 2025 年验证。
- 2026-06-23 已新增 `scripts/validate_layered_btc_history.py`，复用真实 Binance K 线缓存和实时策略适配器验证默认 BTC probe：`SHORT_4H_HEDGE` 命中 `2026-05-13 23:59:59 UTC+8`，entry `78794.70`；`SHORT_DAY_CORE` 命中 `2026-06-01 07:59:59 UTC+8`，entry `73653.20`；`LONG_4H_HEDGE` 命中 `2026-06-13 10:59:59 UTC+8`，entry `63612.00`。

2026-06-20 Binance 连接修复：

- [x] 按 Binance USDⓈ-M Futures 官方文档将实时 K 线 WebSocket 主网入口迁移为 routed market endpoint：`wss://fstream.binance.com/market/stream?...`。
- [x] Ubuntu 生成的 `.env.ports.generated` 默认 `BINANCE_WEBSOCKET_BASE_URL` 已从测试网 `wss://fstream.binancefuture.com` 改为主网 `wss://fstream.binance.com/market`，避免主网 REST 与测试网 WebSocket 混跑。
- [x] WebSocket 默认连接参数已按官方 ping/pong 规则放宽：客户端 ping 间隔 180 秒，pong 超时 600 秒，并在断线、24 小时断开或 keepalive timeout 后自动指数退避重连。
- [x] Binance REST K 线拉取已增加短退避重试：连接超时/网络错误、HTTP 408/429/503 默认最多 3 次；HTTP 451 仍直接提示当前网络/地区受限。
- [x] 状态页顶部“永续实时价格”改为订阅 Binance USDⓈ-M Futures `<symbol>@ticker` WebSocket，使用 ticker 事件里的 last price，不再依赖成交、持仓或已收盘 K 线策略评估刷新。
- [x] 2026-06-27 `scripts/start.sh` 在启动实时 Paper/WebSocket 前默认执行 Binance Futures REST 连通性硬检查：GET `/fapi/v1/ping` 和 `BTCUSDT 1d limit=1` K 线接口，任一失败立即退出并打印 curl 复查命令；如只想离线打开状态页，可设置 `BINANCE_CONNECTIVITY_CHECK_ON_START=0`。

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
- [x] 提供 systemd 服务安装脚本，部署后随系统启动，不依赖 SSH 终端。
- [x] 实现 PostgreSQL / Web 页面端口冲突自动顺延。
- [x] 生成 `.env.ports.generated` 记录最终端口和 DATABASE_URL。

说明：

- `scripts/deploy_ubuntu.sh` 用于首次部署，会安装依赖、启动 Docker、安装并启用 `crypto-paper.service` systemd 服务；真实行情 Paper Trading 和中文 Web 状态页由 systemd 托管，关闭 SSH 终端后仍会继续运行，服务器重启后自动启动。
- `scripts/install_systemd_service.sh` 可单独重装 systemd 服务；默认服务名为 `crypto-paper.service`。
- `scripts/start.sh` 是服务内部启动入口，也可在无 systemd 环境下手动启动；默认会自动检测端口冲突并顺延，systemd 模式下使用 `START_MODE=foreground` 让 systemd 监控进程生命周期。
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

- 当前已实现 EMA、ATR、ADX、DI_PLUS、DI_MINUS、Bollinger Bands；ATR、ADX、DI 使用 Wilder 平滑口径，避免和 TradingView/主流技术指标解释偏离。
- 当前已添加 `tests/fixtures/indicator_golden.json` 固定样本校验，并覆盖 Wilder ATR / DMI 初始化窗口。
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
- 当前主趋势策略使用 R + ATR 双层移动止盈：价格触达 2R 止盈激活价后不立即全平，先至少锁定 1R 已实现利润；剩余仓位按 Wilder ATR 动态保护线推进止损，禁止再回撤到保本出场。若历史兼容信号缺少 ATR，则退回 2R 阶梯兜底，但同样至少锁 1R。
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

- 当前事件驱动回测已复用 PaperTradingEngine 的策略子仓撮合能力，支持同一 symbol 下日线 core、4h/1h addon 和 4h hedge bucket 共存，并输出 strategy / bucket 聚合指标。早期单仓位内核只作为历史实现背景保留。
- 当前已支持 `TREND_PULLBACK` 与 `REVERSAL_PROBE` 信号；趋势转换信号会使用自身 `risk_pct` 风险上限。
- 当前已实现永续合约默认成本：maker 挂单手续费 0.02%，taker 吃单手续费 0.05%；入场按 taker，止损按 taker，止盈按 maker。
- 当前已输出整体指标与按 `strategy_type` 拆分的交易次数、胜负、gross_pnl、fees、net_pnl。
- 当前已实现 8 小时资金费率模拟，资金费进入 trade 与整体指标；实时 Paper 启动时会从 Binance USDⓈ-M Futures Mark Price / Premium Index 拉取 `lastFundingRate` 和 `nextFundingTime`，用于 Funding 入场过滤。拉取失败时会记录并降级为不启用自动 funding 阻断，避免打断 Paper runner。
- 当前已实现交易所 `quantity_step`、`min_qty`、`min_notional` 过滤，并已按订单方向细化价格 tick：买入向上取 tick，卖出向下取 tick。实时多周期 K 线缓存按 `open_time` 去重、排序和裁剪，避免重复 bar 污染指标。
- 当前已实现止损专用滑点与跳空越过止损时的极端成交价。
- 当前已实现限价未触达不成交、限价部分成交比例和 partial_fills 统计。
- 当前已实现价格 tick 方向细化：买入向上取 tick，卖出向下取 tick。
- 当前已实现强平风险模拟，触发强平时优先于止损退出并计入 liquidations。
- 当前已实现 `backtest_runs`、`config_snapshots`、`backtest_trades` 归档，并提供 repository 写入入口。
- 当前 Web 状态页已新增“策略回测”按钮，点击后以新标签页打开 `/backtest`。回测页复用当前实时策略适配器和 PaperTradingEngine，用 Binance REST 历史 K 线回放 1d / 4h / 1h / 15m 分层策略；默认参数已统一为 EMA15 / MA60、ATR14、DMI12、Swing20、fee/risk=0.25、TRAILING。
- 当前策略回测已支持分页历史回测：用户可选择最近 3个月 / 6个月 / 1年 / 2年，后端按 Binance 单次 1500 根限制自动分页拉取 4h / 1h / 15m 历史 K 线。
- 当前 Web 策略回测已接入数据库归档：每次成功回测会写入 `backtest_runs`、`backtest_trades` 和 `config_snapshots`。2026-06-19 已确认 Ubuntu 服务器此前表存在但行数为 0，根因是 `/backtest` 页面只渲染结果、没有调用归档 repository；现已修复。
- 当前 Web 策略回测已增加页面级错误展示：Binance REST 超时、DNS/网络失败或其他回测执行异常会显示为“回测执行失败：...”，不再返回空白页或 empty reply。

仿真限制：

- 强平价、资金费、滑点、限价部分成交和止损跳空成交均为第一版近似模型，用于策略压力测试和风险筛查，不等同 Binance 撮合引擎、标记价格、资金费结算和真实订单簿的逐笔复刻。
- Bollinger Bands、ATR、ADX/DMI 等指标采用项目固定口径计算；当前 ATR、ADX、DI 已固定为 Wilder 平滑，跨平台对比时仍可能因数据源、时区、未收盘 K 线过滤和初始化窗口不同产生轻微差异。
- Paper/Backtest 的多空同 symbol 共存是 strategy bucket 级模拟，不代表第一版已经支持真实 Binance HEDGE position mode；真实 HEDGE 和真实下单属于第二版暂停范围。

## V0.4 Paper Trading

- [x] 实现实时行情订阅。
- [x] 实现 Paper 撮合。
- [x] 实现 Paper 持仓与账户权益。
- [x] 接入主趋势策略 Paper 验证。
- [x] 接入趋势转换策略 Paper 验证。
- [x] 实现状态页或 CLI 状态输出。
- [x] 实现基础报警。

说明：

- 当前 PaperTradingEngine 已从单仓位升级为 strategy bucket 多子仓撮合，支持同一 symbol 下 core / addon / hedge 子仓共存；ADDON 由分层策略层根据当前 open bucket 显式输出，交易层不再把重复 DAY_CORE 隐式转换为 ADDON；旧 `open_position` 字段继续保留兼容。
- 当前 Paper Trading 默认按永续合约模拟：初始资金 1000 USDT、默认 10X 杠杆、maker 0.02%、taker 0.05%、资金费每 8 小时结算一次；资金费率当前默认 0，可通过启动参数配置。
- 当前 Paper Trading 的 `TREND_PULLBACK` 和分层策略默认使用 R + ATR 双层移动止盈：价格触达 2R 激活价后进入“移动止盈中”，先至少锁定 1R；之后按持仓 ATR 的 Wilder 更新值和 `trailing_atr_multiplier` 推进保护线，回撤触达当前移动保护线才平仓。可通过 `--trend-pullback-take-profit-mode FIXED` 回退固定止盈。
- 当前已修复回测/Paper 出场撮合的关键未来函数问题：持仓会记录入场交易对和入场周期，只有同一交易对、同一周期的 K 线才能触发止盈/止损，避免 BTC 持仓被 ETH K 线平仓，或 15m 入场被同一时间的 1h/4h 高低点提前平仓。
- Paper 主链路已接入模拟风控：Kill Switch 激活时禁止新开仓，可选择按当前已收盘 K 线平仓；`max_drawdown_pct` 触发后拒绝新开仓；入场前执行 Liquidation Guard 和 Stop Order Guard 判定。
- Paper 状态 JSON 默认只保留最近 1000 条 fills，避免长期运行写放大；完整复盘事件写入 `paper_runtime_events`。
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

- 当前 Paper/Backtest 主链路已按账户风险预算、止损距离、手续费/风险过滤、单仓名义上限和组合总名义/总计划风险上限计算仓位；单仓默认最多 `5x equity`，组合总名义默认最多 `10x equity`。
- 当前已实现趋势转换仓位计算：最终数量取风险上限和评分仓位上限的较小值；EARLY 使用 0.2% 风险，CONFIRMED 使用 0.3% 风险。
- 当前已实现止损候选选择：LONG 只接受低于入场价的止损，SHORT 只接受高于入场价的止损，并在最大止损距离内选择距离入场价最近的候选。
- 当前已实现趋势转换分批止盈计划：TP1 = 1R 平 30%，TP2 = 前高/前低平 30%，TP3 = 4h EMA200 或方向校验后的 3R/结构位平 40%，TP1 后移动止损到保本。
- 当前已实现 OrderPlan 合约：包含 symbol、side、strategy_type、order_type、entry_price、quantity、stop_loss、take_profit_levels、leverage、margin_type、position_mode、estimated_liquidation_price、liquidation_buffer_pct、reduce_only、client_order_id、strategy_version、config_snapshot_id。第一版 Paper/Backtest 目前只消费其中可模拟的仓位、止损、止盈、强平保护和止损保护语义，不引入真实订单状态编排。
- 当前历史实现约束为 ONE_WAY + ISOLATED。第一版 Paper/Backtest 必须支持策略子仓和同一 symbol 多空共存；Live HEDGE 模式属于第二版，永久暂停，除非用户明确发令启动第二版。
- 当前已实现 Stop Order Guard 判定层：校验真实持仓是否存在 symbol 匹配、退出方向正确、数量覆盖、reduceOnly、状态 NEW、触发价方向正确的有效止损单；Paper 主链路会用模拟止损单快照执行入场前保护校验，真实补挂止损动作保留到第二版。
- 当前已实现 Liquidation Guard 判定层：多单要求 liquidation_price < stop_loss < entry_price，空单要求 entry_price < stop_loss < liquidation_price，且止损价与强平价安全距离不低于 liquidation_buffer_pct；Paper 主链路已在入场前消费该判定。
- 当前已实现 Kill Switch 状态转移：触发后禁止新开仓，可标记是否平仓，并记录操作者、原因、触发时间和解除操作者；Paper 主链路已实际消费该状态。
- 当前已实现订单、成交、持仓状态机：覆盖订单提交、部分成交、完全成交、止损提交/确认/失败、止盈提交、退出成交；第一版作为 Paper/Backtest 复盘与第二版 Live 的边界模型保留，暂不接入真实下单编排。

## V0.6 AI/Funding 过滤

- [x] 实现资金费率过滤。
- [x] 实现 AI filter 接口。
- [x] 实现 deterministic stub。
- [x] 记录 AI 输入、输出、fallback 原因。
- [x] 保持真实 LLM 默认关闭。

说明：

- 当前已实现 Funding 过滤器：距离结算时间 <= 15 分钟禁止新开仓，abs(funding_rate) >= 0.0015 禁止新开仓，abs(funding_rate) >= 0.0005 输出 WARN 并将仓位乘数降为 0.5。
- 2026-06-24 实时 Paper 默认接入 Binance funding snapshot：启动时按 symbol 拉取 `lastFundingRate` 和 `nextFundingTime`，默认信号函数会在新开仓前执行 Funding filter；命中结算窗口或高费率时转为 WAIT，并在原因中记录 funding rate 与距离结算分钟数。
- 当前已实现 AI filter 接口与 deterministic stub：默认 `enabled = false` 时输出 ALLOW；新闻不可用时 fallback BLOCK；显式模拟重大风险事件时 BLOCK。
- 当前已实现 AI filter 日志 entry：记录输入 payload、输出 payload、fallback_reason、provider 和 evaluated_at，真实 LLM 仍未接入且默认关闭。

## V2.0 实盘交易候选事项（永久暂停）

> 以下事项不属于第一版。除非用户明确发出“开始开发第二版实盘交易”的指令，否则不得继续开发测试网、真实下单、API 下单适配器或小资金实盘。

- [ ] （第二版暂停）测试网完整下单闭环。
- [x] （第二版预留校验层）Live 启动前自检。
- [x] （第二版预留校验层）API 权限和 IP 白名单检查。
- [x] （第二版预留校验层）小资金实盘专用配置。
- [ ] （第二版暂停）Paper Trading 连续 2 周无重大错误后，重新评估是否允许规划第二版。
- [ ] （第二版暂停）Stop Order Guard 和 Liquidation Guard 演练通过。
- [ ] （第二版暂停）主订单成交但止损失败的应急流程演练通过。

说明：

- 当前已实现 Live 启动前自检纯校验层，但只作为第二版预留能力：任一失败项都会禁止启动 Live，并一次性返回所有 failed_checks。
- 自检已覆盖：API 不允许提现、IP 白名单、USDⓈ-M Futures API 可用性、服务器时间偏差、database migration、缓存可用或降级、交易所规则同步、ONE_WAY、ISOLATED、leverage <= max_leverage、未知持仓、缺失止损持仓、Stop Order Guard、Liquidation Guard、数据延迟、Kill Switch、通知通道、小资金配置、`LIVE_TRADING_CONFIRM=I_UNDERSTAND_THE_RISK`。
- 当前已实现小资金实盘专用配置校验，但只作为第二版预留能力：必须使用 `small_capital_live` profile，账户权益上限 <= 1000，单笔风险 <= 0.5%，每日亏损上限 <= 1.5%，最大杠杆 <= 10，仅允许 BTCUSDT / ETHUSDT，且必须 ONE_WAY + ISOLATED。
- 当前阶段不做真实或测试网下单；先用真实行情驱动 Paper Trading，验证策略、风控、状态机和连续运行稳定性。API Key 可用也不能自动启动第二版。
- 当前已实现 Paper Trading 连续运行健康检查：检测 WebSocket 连接、行情延迟、Paper 回撤、拒单数量和运行时错误；该模块用于后续“连续 2 周无重大错误”的自动化验收。
- 当前已实现 Paper Trading 状态持久化/恢复入口：PaperSnapshot 可无损序列化为 JSON payload，并支持保存到本地状态文件和从状态文件恢复；Decimal 金额以字符串保存，避免浮点误差。
- 当前已实现持久化 Paper stream runner：启动时从状态文件恢复 PaperTradingEngine，每处理一根已收盘 K 线后写回 PaperSnapshot，避免真实行情模拟交易重启后丢失权益、持仓和拒单计数；状态文件默认裁剪 fills，完整成交历史以数据库复盘事件为准。
- 当前已实现真实行情 Paper runner 与脚本入口：`scripts/run_paper_realtime.py` 会连接 Binance WebSocket 已收盘 K 线流，并使用持久化 Paper stream runner 保存状态。
- 当前真实行情 Paper runner 已支持多周期订阅，默认订阅 15m / 1h / 4h；已新增 MultiTimeframeKlineCache，用于按 symbol 聚合多周期已收盘 K 线。
- 当前实时策略适配器默认调用独立分层策略系统，并使用 1d / 4h / 1h / 15m 已收盘 K 线；旧 4h / 1h / 15m `TREND_PULLBACK` / `REVERSAL_PROBE` 与 `signal_router` 路径只在缺少 1d 历史时作为兼容回退。
- 当前 `scripts/run_paper_realtime.py` 默认路径已不再永久 WAIT；不注入自定义策略函数时，会通过多周期缓存生成实时分层 Paper 信号。ADDON 已由策略层根据 open bucket 显式输出，不再靠交易层重复 `DAY_CORE` 隐式转换。
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
- 当前 Web 状态页已增加“策略K线图”：使用内嵌 SVG 绘制 1d / 4h / 1h / 15m K 线图并叠加当前配置的快慢线，动态显示 EMA15 / MA60 等均线名称。
- 当前 Web 状态页已按交易对展示分层策略触发条件、策略候选和最近信号，覆盖 `SHORT_DAY_CORE` / `SHORT_4H_1H_ADDON` / `LONG_4H_HEDGE` 等明确策略名。
- 当前 Web 状态页的“策略触发条件”已改为按交易对分别显示最新条件卡，避免 BTCUSDT / ETHUSDT 同时运行时只展示全局最新一条，导致用户拿 BTC 图对照 ETH 条件。
- 当前 Web 状态页已新增策略回测入口 `/backtest`，用于在等待长期 Paper Trading 之前，先用历史 K 线快速验证当前策略和不同 EMA 参数组合。
- 当前策略回测页已改为单交易对回测：默认 BTC，可切换 ETH，避免 BTC/ETH 成交记录混在同一张报表里造成误判；回测参数栏已压缩为一行展示。
- 当前策略回测已增加历史 K 线本地缓存：数据按交易对和周期保存到 `runtime/backtest-klines/`；同一交易对后续回测更短周期或不同 EMA 参数时复用缓存，只在所需时间段缺失时补拉 Binance REST 数据。
- 当前策略回测页新增批量参数回测入口 `/backtest/batch`：页面可输入 EMA/MA 类型、快慢周期范围与步进、回测周期、ATR/DMI/Swing、手续费/风险上限和止盈模式，执行逻辑仍复用 `scripts/run_strategy_backtest_batch.py` 与现有 `run_strategy_backtest()`。
- 当前批量回测会基于归档配置 hash 跳过数据库中已存在的同参数结果，并把已有 run 的 final_equity、net_pnl、胜负和胜率写入 checkpoint，保证全跳过时仍可选出 best primary。
- 当前批量回测 Web 入口使用后台任务执行，页面提供停止按钮和运行日志面板；日志内容由脚本显式回调输出。所有组合完成后后台任务会自动停止并进入空闲状态；页面在完成后只刷新一次展示结果。`本轮倒计时` 会在 Web 日志中替换上一条倒计时行，表现为读秒而不是按秒新增日志。批量默认过滤快线>=慢线，并把 ATR/DMI 精修默认收敛为 12、14，Swing Lookback 默认收敛为 20、30，手续费/风险上限默认只比较 0.25 与关闭过滤。
- 已完成：策略回测参数组合对比已补充最大回撤、盈亏比和按 strategy bucket 展开的净盈亏贡献。
