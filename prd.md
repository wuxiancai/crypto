# 币安 USDT 永续合约量化交易系统 PRD

版本：v0.4-layered-strategy-draft
日期：2026-06-24
状态：分层策略系统设计修订版；等待用户确认后进入实现

## 0.1 版本边界

- 第一版只开发 Backtest、Paper Trading、Web 状态页、回测复盘、模拟风控和策略验证。
- 第一版不开发测试网下单、真实下单、API 下单适配器、小资金实盘或任何真金白银实盘交易。
- 第二版才允许开发 Live Trading、测试网下单、真实下单、API 下单适配器和小资金实盘。
- 第二版开发永久暂停，除非用户明确发出“开始开发第二版实盘交易”的指令。
- API Key 可用、Paper 连续稳定、Live 自检代码存在、Guard 代码存在或文档检查项完成，都不能自动触发第二版。

## 0. 2026-06-23 分层策略系统修订

本次修订覆盖早期 `EMA50 / EMA200`、`TREND_PULLBACK`、`REVERSAL_PROBE`、单仓位 `ONE_WAY` 作为默认策略主线的旧描述。历史章节可作为背景保留，但后续实现以本节、`docs/DECISIONS.md` 和 `docs/superpowers/specs/2026-06-23-layered-strategy-system-design.md` 为准。

新的策略主线是独立、参数化、可复用的分层策略系统：

- 日线负责主趋势判断。
- 4h 负责子趋势与主趋势下的反弹/回调。
- 1h 负责方向确认。
- 15m 负责入场触发。
- 5m 只作为执行和监控周期，不用于高周期方向确认。

必须支持的策略名：

- `SHORT_DAY_CORE`：日线空头主仓。
- `SHORT_4H_1H_ADDON`：日线空头下 4h/1h 顺势加仓。
- `LONG_4H_HEDGE`：日线空头中的 4h 反弹多仓。
- `LONG_DAY_CORE`：日线多头主仓。
- `LONG_4H_1H_ADDON`：日线多头下 4h/1h 顺势加仓。
- `SHORT_4H_HEDGE`：日线多头中的 4h 回调空仓。

默认策略参数：

```yaml
strategy_defaults:
  fast_ma: EMA15
  slow_ma: MA60
  atr_period: 14
  dmi_period: 12
  swing_lookback: 20
  max_fee_to_risk_ratio: 0
  take_profit_mode: TRAILING
```

Paper Trading 和 Backtest 必须支持同一 symbol 下按策略 bucket 管理的多策略子仓，至少允许：

- `SHORT_DAY_CORE` 与 `LONG_4H_HEDGE` 共存。
- `LONG_DAY_CORE` 与 `SHORT_4H_HEDGE` 共存。

Live 真实下单属于第二版，不属于第一版。未来第二版若被用户明确启动，且 Live 要支持同一 symbol 多空共存，必须单独启用 Binance Futures `HEDGE` position mode，并通过独立自检、小资金配置和用户确认。

## 1. 项目定位

本项目是一个面向币安 USDⓈ-M Futures 的自动交易研发系统，核心策略框架为：

- 分层趋势识别：日线主趋势、4h 子趋势、1h 确认、15m 入场
- 日线核心仓、4h/1h 顺势加仓、4h hedge 仓
- ATR 动态止损止盈
- 账户级与交易级风控优先
- AI 新闻过滤器只做风险过滤，不直接决定买卖方向

系统目标不是追求高频或复杂预测模型，而是构建一个可回测、可模拟、可监控、可复盘、可安全停止的自动交易闭环。

## 2. 非目标与实盘声明

本系统不构成投资建议。USDT 永续合约具备高杠杆、高波动、爆仓和 API 执行风险。

第一版明确不做：

- 高频订单簿策略
- 网格、套利、马丁、亏损补仓
- AI 预测价格方向
- 多交易所路由
- 测试网下单、真实下单、API 下单适配器
- 小资金实盘
- 全自动无人工审查的大资金实盘

任何实盘都属于第二版。除非用户明确发出开始第二版实盘交易的指令，否则以下验收项只能作为第二版候选清单，不允许推动开发：

- 指标计算测试
- 无未来函数回测
- 样本外回测
- Paper Trading 连续运行
- 测试网完整下单闭环
- Kill Switch 演练
- 小资金实盘验证

## 3. 核心原则

1. 风控优先于信号。
2. 数据质量优先于策略判断。
3. 第一版所有 Paper 订单必须有可恢复的订单状态机；第二版如被明确启动，所有实盘订单也必须满足同一要求。
4. 任何不确定状态默认禁止新开仓。
5. AI 只能输出 `ALLOW`、`WARN`、`BLOCK`，不能下单、不能改参数、不能覆盖硬风控。
6. 回测、Paper Trading 必须共享同一套策略与风控规则；第二版 Live 如被明确启动，也必须共享同一套规则。
7. 每笔交易必须能从数据库中复盘：当时的数据、指标、信号、风控、订单、成交、持仓和配置版本。
8. 时间、价格、数量、资金和风险计算必须可确定、可复现，不允许依赖隐式本地时区或 float 精度。

## 4. 运行模式

系统必须支持三种运行模式：

### 4.1 Backtest

使用历史数据回放策略，验证信号、风控、撮合、费用、滑点和资金费率影响。

### 4.2 Paper Trading

实时接收币安行情，但不发送真实订单。Paper 模式必须使用真实下单前同级别的风控、订单计划和持仓状态机，但第一版只接入模拟执行适配器。

### 4.3 Live Trading

真实连接币安 API。Live Trading 属于第二版，永久暂停。除非用户明确发出“开始开发第二版实盘交易”的指令，否则不得开发测试网下单、真实下单、API 下单适配器或小资金实盘。

第二版如被明确启动，Live 至少必须重新设计并启用：

- API Key 权限限制
- IP 白名单
- 测试网/实盘环境隔离
- 最大杠杆限制
- 最大日亏损限制
- Kill Switch
- 订单状态回查
- 持仓同步
- 严重异常报警

## 5. MVP 范围

MVP / 第一版目标是先实现“数据 -> 指标 -> 信号 -> 风控 -> Paper/回测 -> 可复盘”的闭环，不开发实盘。

### 5.1 MVP 必须实现

- BTCUSDT、ETHUSDT 两个交易对
- 1d / 4h / 1h / 15m / 5m K 线数据
- PostgreSQL 存储行情、指标、信号、订单计划、Paper 成交、持仓、账户快照
- EMA15、MA60、ADX、DI_PLUS、DI_MINUS、ATR、Bollinger Bands
- 分层策略系统：日线 core、4h/1h addon、4h hedge
- 策略子仓识别、回测统计与 Paper 验证
- 单笔风险仓位计算
- ATR 止损、固定 RR 止盈、保本止损
- 事件驱动回测
- Paper Trading
- Kill Switch
- Telegram 或日志型报警
- 基础 Dashboard 或 CLI 状态页

### 5.2 MVP 暂不实现

- AI 新闻过滤器真实 LLM 调用
- 分层策略 Live 实盘执行
- 突破策略实盘执行
- 多币种大规模扫描
- 复杂链上数据
- 多交易所

MVP 可保留 AI 过滤器接口，但默认使用 deterministic stub：

- 无风险：`ALLOW`
- 配置为新闻不可用：`BLOCK`
- 明确模拟风险事件：`BLOCK`

## 6. 技术栈

推荐技术栈：

```yaml
language: Python 3.11+
api: FastAPI
async_runtime: asyncio
validation: pydantic
database: PostgreSQL
cache: Redis optional
migration: Alembic
exchange: Binance Futures REST + WebSocket
backtest: 自研事件驱动回测
dashboard: Streamlit 或 FastAPI Admin
monitoring: Prometheus optional
deployment: Docker Compose
notification: Telegram first
```

异步任务建议优先使用单进程 `asyncio` + 明确的后台任务，等 MVP 稳定后再引入 Celery/arq，避免早期复杂度过高。

## 7. 系统模块

```text
quant_system/
  app/
    config/
    data/
    indicators/
    strategy/
    risk/
    execution/
    backtest/
    database/
    monitoring/
    notifications/
    utils/
  tests/
  scripts/
  docs/
```

核心模块职责：

- `data`：行情订阅、REST 补数、数据质量检测。
- `indicators`：只负责指标计算，不决定交易。
- `strategy`：根据已收盘 K 线和指标生成候选信号，下一阶段必须提供独立分层策略系统、集中策略参数和统一诊断输出；旧 `pullback_strategy` / `reversal_strategy` 只作为兼容适配或迁移参考。
- `risk`：账户、交易对、单笔交易、强平安全、止损订单守护、风控优先级和 Kill Switch。
- `execution`：订单计划、交易所适配、订单状态机、持仓同步。
- `backtest`：历史回放、撮合、费用、滑点、资金费率、报告。
- `database`：schema、migration、repository、配置快照。
- `monitoring`：状态页、指标、报警。

## 8. 市场与数据

### 8.1 默认市场

币安 USDⓈ-M Futures，即 USDT 本位永续合约。

MVP 默认交易对：

```yaml
symbols:
  - BTCUSDT
  - ETHUSDT
```

后续扩展交易对必须通过筛选：

- 合约状态为 `TRADING`
- 报价资产为 `USDT`
- 24h 成交额高于阈值
- 点差低于阈值
- 深度足够
- 非新上市极端波动币
- 非黑名单币种
- 满足最小下单数量、最小名义价值、价格精度、数量精度

### 8.2 K 线周期

```yaml
timeframes:
  main_trend: 1d
  child_trend: 4h
  confirm: 1h
  entry: 15m
  execution: 5m
```

策略确认只能使用已收盘 K 线。未收盘 K 线只可用于监控，不可用于确认入场。

### 8.3 数据质量

每根 K 线必须满足：

- `open_time`、`close_time` 不为空
- OHLC 不为空
- `high >= max(open, close, low)`
- `low <= min(open, close, high)`
- `volume >= 0`
- 同一 symbol + interval 时间序列连续
- 已收盘 K 线才可用于信号确认

数据延迟阈值：

```yaml
max_kline_delay_seconds:
  5m: 20
  15m: 60
  1h: 180
  4h: 300
  1d: 900
```

超过阈值时：

1. 暂停对应 symbol 新开仓。
2. 触发告警。
3. WebSocket 重连。
4. REST 补齐缺失 K 线。
5. 重算受影响指标。
6. 恢复前不得开新仓。

### 8.4 多周期数据对齐

多周期策略最容易出现未来函数。系统必须保证回测和实盘使用同一个多周期已收盘数据对齐函数。

规则：

- 所有周期指标必须只使用已收盘 K 线。
- 15m 信号使用最近一根已收盘 15m K 线。
- 1h 趋势确认使用最近一根已收盘 1h K 线。
- 4h 趋势确认使用最近一根已收盘 4h K 线。
- 日线主趋势使用最近一根已收盘 1d K 线。
- 禁止 15m 信号使用正在形成中的 1h、4h 或 1d K 线。
- 禁止回测和实盘使用不同的数据对齐逻辑。

示例：

当前时间为 `2026-01-01 10:15:00`，如果 15m K 线刚收盘，则可用于信号的周期为：

- 15m：10:00 - 10:15 已收盘 K 线。
- 1h：09:00 - 10:00 已收盘 K 线。
- 4h：04:00 - 08:00 已收盘 K 线。
- 1d：前一日已收盘 K 线。

不可使用：

- 1h：10:00 - 11:00 正在形成中的 K 线。
- 4h：08:00 - 12:00 正在形成中的 K 线。
- 1d：当日正在形成中的 K 线。

接口契约：

```python
def get_closed_multi_timeframe_context(current_time, symbol):
    kline_15m = get_latest_closed_kline(symbol, "15m", current_time)
    kline_1h = get_latest_closed_kline(symbol, "1h", current_time)
    kline_4h = get_latest_closed_kline(symbol, "4h", current_time)
    kline_1d = get_latest_closed_kline(symbol, "1d", current_time)
    return {"15m": kline_15m, "1h": kline_1h, "4h": kline_4h, "1d": kline_1d}
```

## 9. 指标与策略

### 9.1 指标

默认指标：

```yaml
indicators:
  fast_ma_type: EMA
  fast_ma_period: 15
  slow_ma_type: MA
  slow_ma_period: 60
  dmi_period: 12
  min_adx: 20
  strong_adx: 25
  di_plus: required
  di_minus: required
  atr_period: 14
  min_atr_pct: 0.003
  max_atr_pct: 0.08
  bb_period: 20
  bb_std: 2.0
  min_bb_width_pct: 0.005
  max_bb_width_pct: 0.12
```

`ATR_PCT = ATR / close`  
`BB_WIDTH_PCT = (bb_upper - bb_lower) / bb_middle`

### 9.2 分层趋势识别

日线多头主趋势候选：

- 1d close > MA60
- 1d EMA15 > MA60
- 1d EMA15 slope > 0
- ADX >= min_adx
- DI_PLUS > DI_MINUS

日线空头主趋势候选：

- 1d close < MA60
- 1d EMA15 < MA60
- 1d EMA15 slope < 0
- ADX >= min_adx
- DI_MINUS > DI_PLUS

4h/1h 子趋势候选使用相同快慢线规则，但不能覆盖日线主趋势。4h/1h 与日线方向一致时评估 addon；4h/1h 与日线方向相反时评估 hedge。

趋势状态：

- `DAY_UPTREND`
- `DAY_DOWNTREND`
- `FOUR_HOUR_UPTREND`
- `FOUR_HOUR_DOWNTREND`
- `RANGE`
- `TRANSITION`
- `EXTREME`
- `UNKNOWN`

ADX 只表示趋势强度，不表示趋势方向。所有趋势方向判断必须结合 DI_PLUS / DI_MINUS：

- 多头强度确认：`ADX >= min_adx AND DI_PLUS > DI_MINUS`
- 空头强度确认：`ADX >= min_adx AND DI_MINUS > DI_PLUS`
- 强多头确认：`ADX >= strong_adx AND DI_PLUS > DI_MINUS AND DI_PLUS 正在上升`
- 强空头确认：`ADX >= strong_adx AND DI_MINUS > DI_PLUS AND DI_MINUS 正在上升`

4h 与 1h 冲突时，策略系统不能简单 `WAIT`，必须输出具体未满足条件和可继续观察的策略候选：

- 日线空头，4h/1h 同向看空：评估 `SHORT_4H_1H_ADDON`。
- 日线空头，4h/1h 同向看多：评估 `LONG_4H_HEDGE`。
- 日线多头，4h/1h 同向看多：评估 `LONG_4H_1H_ADDON`。
- 日线多头，4h/1h 同向看空：评估 `SHORT_4H_HEDGE`。
- 4h 与 1h 不一致：仅输出候选诊断，不开新子仓。
- EMA15 / MA60 缠绕且 1h / 15m 无明确结构：对应策略候选等待。

趋势识别输出必须包含：

```json
{
  "symbol": "ETHUSDT",
  "day_trend": "DAY_DOWNTREND",
  "four_hour_trend": "FOUR_HOUR_UPTREND",
  "one_hour_confirm": "BULLISH_CONFIRM",
  "candidates": ["LONG_4H_HEDGE"],
  "blocked_candidates": [
    {"strategy_type": "SHORT_4H_1H_ADDON", "missing": ["4h downtrend", "1h bearish confirm"]}
  ],
  "reason": ["daily remains bearish", "4h/1h rebound is active"]
}
```

### 9.3 波动率识别

波动率状态：

- `LOW_VOLATILITY`
- `NORMAL`
- `HIGH_VOLATILITY`
- `EXTREME_VOLATILITY`
- `SQUEEZE`
- `EXPANSION`
- `UNKNOWN`

过滤规则：

- `ATR_PCT < min_atr_pct`：不交易，等待突破。
- `ATR_PCT > max_atr_pct`：禁止新开仓。
- `BB_WIDTH_PCT < min_bb_width_pct`：不交易。
- `BB_WIDTH_PCT > max_bb_width_pct`：禁止新开仓。
- 单根 K 线实体 > `2.5 * ATR`：禁止追单。

## 10. 信号规则

### 10.1 信号类型

执行信号：

- `LONG_ENTRY`
- `SHORT_ENTRY`
- `LONG_EXIT`
- `SHORT_EXIT`
- `HOLD`
- `WAIT`
- `PAUSE`
- `FORCE_EXIT`
- `RISK_BLOCK`
- `FUNDING_BLOCK`
- `AI_BLOCK`

策略类型必须使用明确策略名：

- `SHORT_DAY_CORE`
- `SHORT_4H_1H_ADDON`
- `LONG_4H_HEDGE`
- `LONG_DAY_CORE`
- `LONG_4H_1H_ADDON`
- `SHORT_4H_HEDGE`

旧 `TREND_PULLBACK` / `REVERSAL_PROBE` 只作为历史兼容名称，不再作为新增策略系统的主策略类型。

后续扩展信号：

- `BREAKOUT_LONG_ENTRY`
- `BREAKOUT_SHORT_ENTRY`

### 10.2 分层策略入场总则

所有入场必须由策略系统生成 `StrategySignal`，其他模块不得复制策略条件。每个候选信号至少包含：

- `strategy_type`
- `bucket`
- `symbol`
- `side`
- `timeframe`
- `entry_price`
- `stop_loss`
- `take_profit_plan`
- `risk_pct`
- `config_snapshot`
- `matched_conditions`
- `missing_conditions`

### 10.3 多头策略族

前置条件：

- `LONG_DAY_CORE`：日线 `EMA15 > MA60` 且日线结构转强。
- `LONG_4H_1H_ADDON`：日线多头中，4h/1h 同向看多。
- `LONG_4H_HEDGE`：日线空头中，4h/1h 同向看多，作为反弹 hedge 仓。
- ADX >= `min_adx`
- DI_PLUS > DI_MINUS
- ATR_PCT 在允许范围内
- AI/Funding/账户风控未 BLOCK
- 对应 strategy bucket 当前无同方向未处理仓位

回踩区域满足任一：

- 15m low <= EMA15 + ATR * `pullback_zone_atr_multiplier`
- 15m close 接近 EMA15
- 15m low 接近 BB_MIDDLE
- 15m low 回踩前高支撑位

止跌确认至少满足两个：

- 当前 K 线 close > open
- 当前 K 线 close > 前一根 high
- 下影线长度 > 实体长度
- 成交量 > volume_ma20
- 价格重新站上 EMA20

### 10.4 空头策略族

前置条件：

- `SHORT_DAY_CORE`：日线 `EMA15 < MA60` 且日线结构转弱。
- `SHORT_4H_1H_ADDON`：日线空头中，4h/1h 同向看空。
- `SHORT_4H_HEDGE`：日线多头中，4h/1h 同向看空，作为回调 hedge 仓。
- ADX >= `min_adx`
- DI_MINUS > DI_PLUS
- ATR_PCT 在允许范围内
- AI/Funding/账户风控未 BLOCK
- 对应 strategy bucket 当前无同方向未处理仓位

反弹区域满足任一：

- 15m high >= EMA15 - ATR * `pullback_zone_atr_multiplier`
- 15m close 接近 EMA15
- 15m high 接近 BB_MIDDLE
- 15m high 反弹至前低压力位

滞涨确认至少满足两个：

- 当前 K 线 close < open
- 当前 K 线 close < 前一根 low
- 上影线长度 > 实体长度
- 成交量 > volume_ma20
- 价格重新跌破 EMA20

### 10.5 最终信号结构

```json
{
  "signal_id": "uuid",
  "strategy_type": "SHORT_DAY_CORE",
  "symbol": "BTCUSDT",
  "side": "SHORT",
  "signal_type": "SHORT_ENTRY",
  "bucket": "DAY_CORE",
  "entry_type": "CORE_OR_BREAKDOWN",
  "entry_price": "65000.00",
  "stop_loss": "64025.00",
  "take_profit": "66950.00",
  "timeframe": "15m",
  "confidence": 78,
  "risk_reward_ratio": "2.00",
  "reason": ["1d downtrend", "4h bearish impulse", "15m bearish confirmation"],
  "created_at": "2026-01-01T00:00:00Z"
}
```

所有价格、数量、金额在代码中必须使用 decimal 类型，不得使用 float 做下单精度计算。

### 10.6 信号生成顺序

系统必须先处理风险、同步和退出，再考虑新开仓。

信号生成顺序：

1. 更新市场数据。
2. 获取多周期已收盘上下文。
3. 计算多周期指标。
4. 同步账户、订单、持仓。
5. 判断账户级风控状态。
6. 判断已有持仓退出条件。
7. 生成退出信号。
8. 判断 AI 新闻过滤状态。
9. 判断资金费率过滤状态。
10. 判断已有持仓冲突。
11. 调用分层策略系统生成候选信号。
12. 按 strategy bucket 判断是否允许新增、加仓、hedge 或等待。
13. 输出最终信号与未满足条件诊断。

最终执行优先级：

1. 账户级风控。
2. 止损订单缺失、强平保护、保证金安全。
3. 已有持仓退出信号。
4. AI 新闻过滤器。
5. 资金费率过滤器。
6. 已有持仓冲突检查。
7. 分层策略系统候选信号。
8. strategy bucket 冲突检查与风险排序。
9. 可选突破确认信号。
10. WAIT。

规则：

- 账户级风控触发时，所有新开仓信号无效。
- 已有持仓缺少有效止损时，所有新开仓信号无效。
- 已有持仓触发退出时，必须先处理退出。
- AI BLOCK 或 Funding BLOCK 禁止新开仓。
- Paper/Backtest 中同一 symbol 可存在不同 strategy bucket 的反向 hedge 仓。
- 同一 bucket 内禁止重复开同方向未处理仓位。
- 日线 core 仓优先级高于 addon，addon 优先级高于 hedge；hedge 不能反向平掉 core，除非退出规则显式触发。

## 11. 风控优先级

最终执行前必须按以下顺序评估：

1. 手动 Kill Switch
2. 账户权益异常
3. 止损挂单失败或已有持仓无止损
4. 强平价或保证金安全检查失败
5. 交易所真实持仓无法确认
6. 已有持仓退出信号
7. 当日最大亏损
8. 连续亏损限制
9. 数据中断或数据延迟
10. API 异常
11. Funding BLOCK
12. AI BLOCK
13. 极端波动
14. 已有持仓冲突
15. 趋势不明确
16. 信号置信度不足

任何 BLOCK 均禁止新开仓。退出、减仓、补挂止损、Kill Switch 操作不受“禁止新开仓”限制。

## 12. 账户与仓位风控

默认参数：

```yaml
risk:
  risk_per_trade_pct: 0.01
  max_daily_loss_pct: 0.03
  max_account_risk_pct: 0.10
  max_open_positions: 3
  max_symbol_exposure_pct: 0.20
  max_total_notional_pct: 1.0
  max_consecutive_losses: 3
  cooldown_after_losses_minutes: 240
leverage:
  default: 3
  max: 5
execution:
  paper_position_model: STRATEGY_BUCKETS
  live_position_mode_default: ONE_WAY
  margin_type: ISOLATED
liquidation_guard:
  enabled: true
  liquidation_buffer_pct: 0.01
  reject_if_stop_too_close_to_liquidation: true
```

仓位计算必须先计算理论数量，再经过交易所规则和全局限制修正：

```text
risk_amount = account_equity * risk_per_trade_pct
effective_stop_distance = abs(entry_price - stop_loss)
base_quantity = risk_amount / effective_stop_distance
scaled_quantity = base_quantity
  * volatility_multiplier
  * ai_filter_multiplier
  * drawdown_multiplier
  * liquidity_multiplier
```

修正后必须检查：

- `step_size`
- `tick_size`
- `min_qty`
- `max_qty`
- `min_notional`
- 单币名义仓位上限
- 总名义仓位上限
- 可用保证金
- 杠杆上限
- 预估强平价
- 止损价与强平价安全距离
- 预估手续费和滑点后的最大亏损仍不超过风险预算

如果精度修正后风险超过预算，必须缩小数量或放弃交易。

### 12.1 持仓模式、策略子仓与保证金模式

Paper/Backtest 默认：

```yaml
execution:
  position_model: STRATEGY_BUCKETS
  buckets:
    - DAY_CORE
    - FOUR_HOUR_ADDON
    - FOUR_HOUR_HEDGE
```

规则：

- 同一 symbol 可同时存在不同 bucket 的主仓和 hedge 仓。
- `SHORT_DAY_CORE` 可以与 `LONG_4H_HEDGE` 共存。
- `LONG_DAY_CORE` 可以与 `SHORT_4H_HEDGE` 共存。
- 同一 bucket 内默认只能有一个活跃子仓；加仓必须通过 addon bucket 或显式加仓规则。
- hedge 仓不能自动平掉 core 仓，必须由各自退出规则管理。
- 账户级风险、symbol 总敞口和总名义价值仍按所有子仓合并计算。

Live 默认：

```yaml
execution:
  position_mode: ONE_WAY
  margin_type: ISOLATED
```

Live 默认保持 ONE_WAY 的原因：

- ONE_WAY 更简单，避免同一 symbol 同时存在 long 和 short。
- ISOLATED 更适合小资金测试，避免单个 symbol 错误影响全账户权益。

Live ONE_WAY 模式规则：

- 同一 symbol 同一时间只能持有一个方向。
- 有多单时，不允许直接开空。
- 有空单时，不允许直接开多。
- 反向信号只能先触发退出。
- 退出完成后，等待下一根 K 线重新评估。

下单前必须确认：

- 当前账户 position_mode。
- 当前 symbol margin_type。
- 当前 symbol leverage。
- 当前 symbol 是否已有持仓。
- 当前 symbol 是否已有反向挂单。

Live HEDGE 模式不作为默认实现。未来启用 HEDGE 必须单独配置并验证 `positionSide`、`reduceOnly`、`closePosition` 的行为，并通过独立用户确认。

### 12.2 强平价与保证金安全

每次下单前必须检查：

1. 获取账户权益。
2. 获取当前 symbol 杠杆限制。
3. 计算预估保证金。
4. 计算或查询预估强平价。
5. 检查止损价是否安全。
6. 检查账户保证金率。
7. 检查最大杠杆限制。
8. 检查最大名义价值限制。

多单要求：

```text
liquidation_price < stop_loss < entry_price
(stop_loss - liquidation_price) / entry_price >= liquidation_buffer_pct
```

空单要求：

```text
entry_price < stop_loss < liquidation_price
(liquidation_price - stop_loss) / entry_price >= liquidation_buffer_pct
```

默认要求止损价与强平价至少保持 1% 的价格距离。不满足则禁止开仓。

## 13. 止损与止盈

### 13.1 止损候选

多头候选：

- `atr_stop = entry_price - ATR * atr_stop_multiplier`
- `structure_stop = recent_swing_low - tick_size`

空头候选：

- `atr_stop = entry_price + ATR * atr_stop_multiplier`
- `structure_stop = recent_swing_high + tick_size`

### 13.2 止损选择规则

不能简单使用 `min()` 或 `max()` 作为“更保守止损”，因为这会经常扩大止损距离。

正确规则：

1. 生成 ATR 止损和结构止损候选。
2. 剔除方向错误或距离为 0 的候选。
3. 计算每个候选的止损距离。
4. 若候选止损距离超过 `max_stop_distance_pct`，该候选无效。
5. 若候选止损距离低于 `min_stop_distance_pct`，可调整到最小距离或放弃交易。
6. 在有效候选中，选择满足结构保护且风险最小的止损。
7. 若无有效候选，放弃交易。

默认：

```yaml
stop_loss:
  atr_multiplier: 1.5
  max_stop_distance_pct: 0.03
  min_stop_distance_pct: 0.002
```

### 13.3 止盈

默认使用分批止盈：

```yaml
take_profit_levels:
  - rr: 1.0
    close_pct: 0.30
  - rr: 2.0
    close_pct: 0.30
  - rr: 3.0
    close_pct: 0.40
```

浮盈达到 1R 后，剩余仓位止损移动到开仓价或扣除手续费后的保本价。

### 13.4 移动止盈

多头：

```text
trailing_stop = highest_price_since_entry - ATR * atr_trailing_multiplier
```

空头：

```text
trailing_stop = lowest_price_since_entry + ATR * atr_trailing_multiplier
```

## 14. Funding 与 AI 过滤

### 14.1 Funding 过滤

```yaml
funding_rate:
  warn_abs: 0.0005
  block_abs: 0.0015
  settlement_avoid_minutes: 15
```

规则：

- 距离资金费率结算 <= 15 分钟：禁止新开仓。
- `abs(funding_rate) >= block_abs`：禁止新开仓。
- `abs(funding_rate) >= warn_abs`：仓位乘数 0.5。

### 14.2 AI 过滤器定位

AI 新闻过滤器不是信号生成器，只是风险过滤器。

AI 输出：

- `ALLOW`：允许交易。
- `WARN`：允许交易但降仓。
- `BLOCK`：禁止新开仓。

AI 不得：

- 直接下单
- 修改策略参数
- 跳过硬风控
- 生成多空方向
- 覆盖 Kill Switch

### 14.3 AI 失败策略

为了实盘安全，失败策略必须确定：

```yaml
ai_filter:
  enabled: false
  timeout_seconds: 10
  cache_minutes: 15
  fallback_decision: BLOCK
```

异常处理：

- LLM 超时：`BLOCK`
- 新闻源失败：`BLOCK`
- JSON 解析失败：`BLOCK`
- confidence 低于阈值：`BLOCK`
- 明确重大风险：`BLOCK`

MVP 阶段 AI 默认关闭，保留接口、日志和 deterministic stub。

## 15. 订单执行状态机

### 15.1 订单计划

策略层不得直接下单。策略只生成信号，风控通过后生成 `OrderPlan`。

`OrderPlan` 必须包含：

- symbol
- side
- position_side
- order_type
- entry_price
- quantity
- stop_loss
- take_profit levels
- leverage
- margin_type
- position_mode
- estimated_liquidation_price
- liquidation_buffer_pct
- reduce_only
- client_order_id
- strategy_version
- config_snapshot_id

### 15.2 下单流程

```text
signal
  -> risk evaluation
  -> order plan
  -> exchange rule validation
  -> set leverage/margin mode
  -> submit entry order
  -> query entry order status
  -> if filled: submit stop loss
  -> if stop loss confirmed: submit take profit
  -> persist state
  -> notify
```

### 15.3 高危异常

主订单已成交但止损失败时：

1. 立即重试止损订单。
2. 重试仍失败则市价平仓。
3. 触发 CRITICAL 告警。
4. 写入 `risk_events`。
5. 暂停新开仓，直到人工确认。

网络超时时不得盲目重复下单，必须先用 `client_order_id` 和交易所订单查询确认状态。

### 15.4 持仓同步

```yaml
position_sync_interval_seconds: 10
account_sync_interval_seconds: 10
```

本地持仓与交易所不一致时：

- 暂停新开仓
- 同步真实仓位
- 检查止损是否存在
- 必要时补挂止损或平仓
- 触发告警

### 15.5 Stop Order Guard

自动交易系统不能只在开仓后尝试挂止损，还必须持续检查交易所真实持仓是否有有效止损单。

配置：

```yaml
stop_order_guard:
  enabled: true
  check_interval_seconds: 5
  max_repair_attempts: 3
  close_position_if_repair_failed: true
```

Stop Order Guard 职责：

- 定时扫描所有交易所真实持仓。
- 检查每个持仓是否存在有效止损单。
- 检查止损单数量是否覆盖当前持仓。
- 检查止损方向是否正确。
- 检查止损单是否 reduceOnly。
- 如果缺失止损，立即补挂。
- 如果补挂失败，立即市价平仓。
- 触发 CRITICAL 告警。

有效止损单必须同时满足：

- symbol 与持仓一致。
- side 与持仓退出方向一致。
- quantity 覆盖当前持仓数量。
- reduceOnly = true。
- stopPrice 有效。
- 订单状态为 NEW。
- 触发价没有明显错误。
- 不会增加反向仓位。

## 16. 数据库契约

数据库必须支持复盘、恢复、审计和回测归档。

### 16.1 必须表

- `symbols`
- `klines`
- `indicator_snapshots`
- `signals`
- `order_plans`
- `orders`
- `order_events`
- `fills`
- `positions`
- `position_events`
- `account_snapshots`
- `funding_rates`
- `ai_filter_logs`
- `risk_events`
- `safety_checks`
- `stop_order_checks`
- `liquidation_checks`
- `strategy_runs`
- `config_snapshots`
- `backtest_runs`
- `backtest_trades`

### 16.2 关键要求

- 所有交易相关表必须记录 `strategy_version` 和 `config_snapshot_id`。
- 所有订单必须记录 `client_order_id`，并保证幂等。
- `orders` 保存当前状态，`order_events` 保存状态流转。
- `fills` 保存逐笔成交，不得只存平均价格。
- `positions` 保存当前视图，`position_events` 保存变化历史。
- `indicator_snapshots` 必须保存 `di_plus`、`di_minus`，因为 ADX 不提供趋势方向。
- AI 输入、输出、解析结果和 fallback 原因必须完整保存。
- Stop Order Guard 每次修复、失败、市价平仓都必须保存检查记录。
- 强平价与保证金安全检查必须保存输入、输出、拒绝原因和使用的交易所规则版本。
- 回测结果不可覆盖，必须按 `backtest_run_id` 归档。

### 16.3 时间与精度

- 数据库时间统一 UTC。
- 行情 open_time / close_time 保存交易所毫秒时间戳，同时可附加 UTC timestamp。
- 金额、价格、数量使用 `NUMERIC`。
- 代码下单计算使用 Decimal。

## 17. 回测系统

### 17.1 回测原则

回测必须避免未来函数，并尽量复用实盘策略和风控代码。

### 17.2 撮合规则

1. 使用已收盘 K 线生成信号。
2. 下一根 K 线开盘价或限价触发价成交。
3. 同一根 K 线同时触发止损和止盈时，优先按止损处理。
4. 加入 Maker 手续费和 Taker 手续费。
5. 加入市价单滑点。
6. 加入限价单未成交和部分成交。
7. 加入止损滑点。
8. 加入资金费率。
9. 模拟最小下单数量、最小名义价值、价格精度、数量精度。
10. 模拟强平风险。
11. 每笔回测交易必须能追溯到信号和配置快照。

默认回测成本配置：

```yaml
backtest:
  maker_fee_rate: 0.0002
  taker_fee_rate: 0.0005
  market_order_slippage_pct: 0.0005
  stop_slippage_pct: 0.0005
  extreme_stop_slippage_pct: 0.002
  conservative_same_bar_execution: true
```

限价单成交规则：

- 限价买单：下一根 K 线 low <= limit_price 时，认为可能成交。
- 限价卖单：下一根 K 线 high >= limit_price 时，认为可能成交。
- 如果触发价格只被影线轻微触碰，按未成交或部分成交处理。

止损成交规则：

```text
long_stop_fill_price = stop_price * (1 - stop_slippage_pct)
short_stop_fill_price = stop_price * (1 + stop_slippage_pct)
```

极端波动时使用 `extreme_stop_slippage_pct`。

### 17.3 样本划分

每次策略参数变更后必须记录：

- 样本内区间
- 样本外区间
- 参数集
- 数据版本
- 交易对范围

不得用同一段数据无限调参后直接声明策略有效。

### 17.4 指标

必须输出：

- total_return
- annual_return
- max_drawdown
- sharpe_ratio
- sortino_ratio
- win_rate
- profit_factor
- average_win
- average_loss
- payoff_ratio
- expectancy
- max_consecutive_losses
- trade_count
- long_trade_count
- short_trade_count
- average_holding_time
- calmar_ratio

必须按 `strategy_type` 单独统计，至少拆分：

- `SHORT_DAY_CORE`
- `SHORT_4H_1H_ADDON`
- `LONG_4H_HEDGE`
- `LONG_DAY_CORE`
- `LONG_4H_1H_ADDON`
- `SHORT_4H_HEDGE`
- `OVERALL_PORTFOLIO`

## 18. 历史策略说明：趋势转换试仓

本章是早期 `REVERSAL_PROBE` 方案的历史设计背景。2026-06-23 之后，新增实现不得继续把 `REVERSAL_PROBE` 作为默认核心策略名；相关思想应映射到更明确的 `LONG_4H_HEDGE`、`SHORT_4H_HEDGE` 或后续独立 transition 策略配置。

趋势转换试仓用于捕捉 4h 大周期尚未完全反转，但 1h 和 15m 已经率先完成结构切换的行情。

它与主趋势回踩策略的关系：

- 主趋势回踩：吃已经确认的大周期趋势。
- 趋势转换试仓：吃大周期反转初期，但必须轻仓、快进快出。
- 突破确认：吃趋势中的波动率扩张，优先级低于前两者。
- 风控模块：决定最终能不能交易。

历史 `REVERSAL_PROBE` 不再作为新增 MVP 默认入口；分层策略系统中的 hedge 策略必须纳入回测统计和 Paper Trading 验证。Live 实盘属于第二版，永久暂停，除非用户明确发令启动第二版。

### 18.1 适用场景

趋势转换试仓适用于：

- 4h 原趋势仍未完全反转，但已经出现止跌或滞涨。
- 1h 已经突破关键均线并出现反向结构。
- 15m 已经形成新的短周期多空结构。
- 成交量有确认。
- 短周期回踩或反抽后确认有效。

典型场景：

- 大跌后的 V 型反弹。
- 大涨后的 V 型反转下跌。
- 4h 空头趋势末期，1h 率先转多。
- 4h 多头趋势末期，1h 率先转空。
- 短周期放量突破长期压制后的第一次回踩。
- 短周期放量跌破长期支撑后的第一次反抽。

### 18.2 禁止场景

以下情况禁止趋势转换试仓：

- 4h 仍在单边加速下跌，且没有止跌结构。
- 4h 仍在单边加速上涨，且没有滞涨结构。
- 1h 没有突破或跌破 EMA200。
- 15m 没有完成 EMA50 与 EMA200 的方向切换。
- 价格距离 15m EMA50 过远。
- 单根 K 线涨跌幅过大，已经透支。
- ATR_PCT 超过极端波动阈值。
- 资金费率异常。
- AI 新闻过滤器输出 `BLOCK`。
- 当日亏损或连续亏损达到限制。
- 当前已有同方向满仓趋势单。
- 当前处于重大宏观数据公布前后窗口。

### 18.3 状态定义

趋势转换模块状态：

- `REVERSAL_LONG_WATCH`
- `REVERSAL_LONG_READY`
- `REVERSAL_LONG_ENTRY`
- `REVERSAL_SHORT_WATCH`
- `REVERSAL_SHORT_READY`
- `REVERSAL_SHORT_ENTRY`
- `REVERSAL_FAILED`
- `REVERSAL_CONFIRMED`

状态含义：

- `REVERSAL_LONG_WATCH`：观察潜在多头反转。
- `REVERSAL_LONG_READY`：多头反转条件基本成熟，等待入场。
- `REVERSAL_LONG_ENTRY`：通用多头试仓事件，必须带 `signal_level` 区分 `EARLY` 或 `CONFIRMED`。
- `REVERSAL_SHORT_WATCH`：观察潜在空头反转。
- `REVERSAL_SHORT_READY`：空头反转条件基本成熟，等待入场。
- `REVERSAL_SHORT_ENTRY`：通用空头试仓事件，必须带 `signal_level` 区分 `EARLY` 或 `CONFIRMED`。
- `REVERSAL_FAILED`：反转失败，退出或禁止继续试仓。
- `REVERSAL_CONFIRMED`：反转成功，可切换为主趋势策略。

### 18.4 信号分级

趋势转换信号分为 A 类早期试仓与 B 类确认试仓。

做多：

- `REVERSAL_LONG_EARLY`
- `REVERSAL_LONG_CONFIRMED`

做空：

- `REVERSAL_SHORT_EARLY`
- `REVERSAL_SHORT_CONFIRMED`

A 类早期试仓用于更早捕捉 V 型反转，但只能使用标准仓位的 20%，且单笔最大亏损不得超过账户权益 0.2%。

B 类确认试仓用于结构更明确后的参与，仓位范围为标准仓位的 30% - 50%，但仍不得超过账户权益 0.3% 风险上限。

### 18.5 趋势转换做多

趋势转换做多用于捕捉 4h 空头趋势尚未完全结束，但 1h 和 15m 已经率先转强的潜在底部反转。

4h 观察条件满足任意 2 个即可进入 `REVERSAL_LONG_WATCH`：

- 4h close 重新站上 EMA50。
- 4h close 虽未站上 EMA50，但已经连续 2 根 K 线不创新低。
- 4h 出现长下影线。
- 4h 最近一轮下跌后，成交量放大但价格不再继续破低。
- 4h close 距离 EMA200 小于 8%。
- 4h 最近低点形成 higher low。
- 4h ATR 开始下降，说明恐慌波动减弱。
- 4h 大阴线之后没有继续放量下跌。

1h 必须满足：

- 1h close > EMA50
- 1h close > EMA200
- 1h EMA50 斜率向上
- 1h 最近结构出现 higher high
- 1h 最近结构出现 higher low

15m 必须满足：

- 15m EMA50 > EMA200
- 15m close > EMA50
- 15m 已经放量突破前高
- 15m 回踩 EMA50 或 EMA200 后不破

A 类早期试仓条件：

- 4h 不再创新低。
- 1h close > EMA50。
- 1h close 接近或突破 EMA200。
- 15m close > EMA200。
- 15m EMA50 斜率向上。
- 15m 放量突破最近 20 根 K 线高点。
- 15m 第一次回踩 EMA20 或 EMA50 不破。
- ATR_PCT 不处于 EXTREME。
- AI/Funding/账户风控未 BLOCK。

B 类确认试仓条件：

- 4h 出现止跌结构。
- 1h close > EMA200。
- 1h EMA50 斜率向上。
- 15m EMA50 > EMA200。
- 15m 回踩 EMA50 不破。
- 15m 出现止跌确认 K 线。
- 成交量确认。

做多入场条件：

- 4h 进入 `REVERSAL_LONG_WATCH`
- 1h close > EMA200
- 15m EMA50 > EMA200
- 15m price 回踩 EMA50 或 EMA200
- 15m 回踩不跌破最近 swing low
- 15m 出现止跌确认 K 线
- volume >= volume_ma20
- ATR_PCT 在允许范围内
- AI/Funding/账户风控未 BLOCK

止跌确认 K 线至少满足 2 个：

- 当前 K 线 close > open。
- 当前 K 线 close > 前一根 K 线 high。
- 当前 K 线下影线长度 > 实体长度。
- 当前 K 线收盘重新站上 EMA20。
- 当前 K 线成交量 > volume_ma20。
- 当前 K 线没有跌破上一轮 swing low。
- 5m 出现底分型或连续阳线确认。

### 18.6 趋势转换做空

趋势转换做空用于捕捉 4h 多头趋势尚未完全结束，但 1h 和 15m 已经率先转弱的潜在顶部反转。

4h 观察条件满足任意 2 个即可进入 `REVERSAL_SHORT_WATCH`：

- 4h close 跌破 EMA50。
- 4h close 虽未跌破 EMA50，但已经连续 2 根 K 线不创新高。
- 4h 出现长上影线。
- 4h 最近一轮上涨后，成交量放大但价格不再继续创新高。
- 4h close 距离 EMA200 小于 8%。
- 4h 最近高点形成 lower high。
- 4h ATR 开始下降，说明上攻动能减弱。
- 4h 大阳线之后没有继续放量上涨。

1h 必须满足：

- 1h close < EMA50
- 1h close < EMA200
- 1h EMA50 斜率向下
- 1h 最近结构出现 lower high
- 1h 最近结构出现 lower low

15m 必须满足：

- 15m EMA50 < EMA200
- 15m close < EMA50
- 15m 已经放量跌破前低
- 15m 反抽 EMA50 或 EMA200 后不过

A 类早期试仓条件：

- 4h 不再创新高。
- 1h close < EMA50。
- 1h close 接近或跌破 EMA200。
- 15m close < EMA200。
- 15m EMA50 斜率向下。
- 15m 放量跌破最近 20 根 K 线低点。
- 15m 第一次反抽 EMA20 或 EMA50 不过。
- ATR_PCT 不处于 EXTREME。
- AI/Funding/账户风控未 BLOCK。

B 类确认试仓条件：

- 4h 出现滞涨结构。
- 1h close < EMA200。
- 1h EMA50 斜率向下。
- 15m EMA50 < EMA200。
- 15m 反抽 EMA50 不过。
- 15m 出现滞涨确认 K 线。
- 成交量确认。

做空入场条件：

- 4h 进入 `REVERSAL_SHORT_WATCH`
- 1h close < EMA200
- 15m EMA50 < EMA200
- 15m price 反抽 EMA50 或 EMA200
- 15m 反抽未突破最近 swing high
- 15m 出现滞涨确认 K 线
- volume >= volume_ma20
- ATR_PCT 在允许范围内
- AI/Funding/账户风控未 BLOCK

滞涨确认 K 线至少满足 2 个：

- 当前 K 线 close < open。
- 当前 K 线 close < 前一根 K 线 low。
- 当前 K 线上影线长度 > 实体长度。
- 当前 K 线收盘重新跌破 EMA20。
- 当前 K 线成交量 > volume_ma20。
- 当前 K 线没有突破上一轮 swing high。
- 5m 出现顶分型或连续阴线确认。

### 18.7 评分规则

趋势转换做多评分：

| 条件 | 分数 |
| --- | ---: |
| 4h 出现止跌结构 | +15 |
| 4h close 接近或站上 EMA50 | +10 |
| 1h close > EMA50 | +10 |
| 1h close > EMA200 | +15 |
| 1h 出现 higher high | +10 |
| 1h 出现 higher low | +10 |
| 15m EMA50 > EMA200 | +10 |
| 15m 回踩 EMA50 不破 | +10 |
| 15m 止跌确认 K 线 | +5 |
| 成交量确认 | +5 |
| DI_PLUS 上穿 DI_MINUS 或连续 2 根 15m 高于 DI_MINUS | +5 |

趋势转换做空评分：

| 条件 | 分数 |
| --- | ---: |
| 4h 出现滞涨结构 | +15 |
| 4h close 接近或跌破 EMA50 | +10 |
| 1h close < EMA50 | +10 |
| 1h close < EMA200 | +15 |
| 1h 出现 lower low | +10 |
| 1h 出现 lower high | +10 |
| 15m EMA50 < EMA200 | +10 |
| 15m 反抽 EMA50 不过 | +10 |
| 15m 滞涨确认 K 线 | +5 |
| 成交量确认 | +5 |
| DI_MINUS 上穿 DI_PLUS 或连续 2 根 15m 高于 DI_PLUS | +5 |

入场要求：

- 分数 < 60：禁止交易。
- 60 到 69：只允许观察，不允许开仓。
- >= 70：允许生成趋势转换试仓信号。

评分计算必须在所有加分项完成后执行 `score = min(raw_score, 100)`，避免 DI 加分导致分数超过 100。

### 18.8 仓位控制

趋势转换交易属于提前参与，确定性低于主趋势回踩，因此必须独立限制风险。

硬限制：

- A 类早期试仓单笔最大亏损 <= 账户权益 0.2%。
- B 类确认试仓单笔最大亏损 <= 账户权益 0.3%。
- 最大仓位 <= 主策略标准仓位 50%。
- 同一时间最多 1 个趋势转换试仓。
- 亏损时严禁补仓摊平。

评分仓位：

| 评分 | 仓位 |
| --- | ---: |
| 60 - 69 | 0，只观察 |
| 70 - 74 | 标准仓位的 20% |
| 75 - 84 | 标准仓位的 30% |
| 85 - 100 | 标准仓位的 50% |

最终趋势转换仓位必须同时满足“风险上限”和“评分仓位上限”，取两者较小值：

```text
standard_risk_amount = account_equity * risk_per_trade_pct
standard_qty = standard_risk_amount / stop_distance

reversal_risk_pct = 0.002 if signal_level == "EARLY" else 0.003
reversal_risk_amount = account_equity * reversal_risk_pct
reversal_risk_qty = reversal_risk_amount / stop_distance

score_limited_qty = standard_qty * reversal_score_multiplier

final_reversal_qty = min(reversal_risk_qty, score_limited_qty)
```

随后再乘以 AI、波动率、流动性等降仓因子，并按交易所精度修正。精度修正后如果风险超过对应信号级别的风险预算，必须缩小数量或放弃交易。

### 18.9 趋势转换止损

趋势转换止损必须比主趋势策略更严格。

多头止损候选：

- 最近 15m swing low 下方。
- 15m EMA200 下方。
- 1h EMA50 下方。
- `entry_price - ATR * 1.2`。

空头止损候选：

- 最近 15m swing high 上方。
- 15m EMA200 上方。
- 1h EMA50 上方。
- `entry_price + ATR * 1.2`。

止损选择仍遵循第 13 节的候选止损规则，不能简单用 `min()` 或 `max()` 扩大止损距离。

趋势转换多单推荐：

```text
structural_stop = min(recent_15m_swing_low - tick_size, ema200_15m - tick_size)
atr_stop = entry_price - ATR * reversal_atr_stop_multiplier
long_reversal_stop = max(structural_stop, atr_stop)
```

趋势转换空单推荐：

```text
structural_stop = max(recent_15m_swing_high + tick_size, ema200_15m + tick_size)
atr_stop = entry_price + ATR * reversal_atr_stop_multiplier
short_reversal_stop = min(structural_stop, atr_stop)
```

含义：选择更靠近入场价的有效止损，避免趋势转换交易默认使用最宽止损。

默认最大止损距离：

```yaml
max_reversal_stop_distance_pct: 0.025
```

如果止损距离超过 2.5%，放弃交易。

### 18.10 趋势转换止盈与时间止损

趋势转换采用分批止盈：

- TP1 = 1R，平仓 30%。
- TP2 = 前高/前低结构位，平仓 30%。
- TP3 = 4h EMA200 或 3R，平仓 40%。

TP3 必须做方向校验：

- 做多时，只有 `EMA200_4h > entry_price`，EMA200_4h 才可作为 TP3；否则 `TP3 = max(previous_high, entry_price + 3R)`。
- 做空时，只有 `EMA200_4h < entry_price`，EMA200_4h 才可作为 TP3；否则 `TP3 = min(previous_low, entry_price - 3R)`。

到达 TP1 后，止损移动到开仓价或扣除手续费后的保本价。

时间止损：

- 入场后 8 根 15m K 线内没有达到 0.5R：减仓 50% 或退出。
- 入场后 12 根 15m K 线内没有达到 1R：强制平仓。

### 18.11 禁止追涨追跌

趋势转换用于捕捉 V 型反转，但不能在大阳线或大阴线之后盲目追单。

做多禁止追涨：

```text
entry_price - EMA50_15m > 1.0 * ATR
OR (entry_price - EMA50_15m) / entry_price > 0.012
```

做空禁止追跌：

```text
EMA50_15m - entry_price > 1.0 * ATR
OR (EMA50_15m - entry_price) / entry_price > 0.012
```

触发任一条件，禁止趋势转换开仓。

### 18.12 失败条件

趋势转换做多出现以下任意条件，立即退出或禁止继续试仓：

- 15m close 跌破 EMA200。
- 15m 跌破最近 swing low。
- 1h close 跌回 EMA50 下方。
- 1h 突破后重新跌回 EMA200 下方。
- 做多后 8 根 15m K 线内没有达到 0.5R。
- 价格反弹缩量，随后放量下跌。
- AI/Funding 从允许状态变为 BLOCK。
- BTC 或 ETH 出现同步急跌。

趋势转换做空出现以下任意条件，立即退出或禁止继续试仓：

- 15m close 重新站上 EMA200。
- 15m 突破最近 swing high。
- 1h close 重新站上 EMA50。
- 1h 跌破后重新站回 EMA200 上方。
- 做空后 8 根 15m K 线内没有达到 0.5R。
- 价格下跌缩量，随后放量上涨。
- AI/Funding 从允许状态变为 BLOCK。
- BTC 或 ETH 出现同步急涨。

### 18.13 升级为主趋势仓位

趋势转换试仓后，如果 4h 进一步确认反转，可将该交易状态升级为主趋势跟随。

做多升级条件：

- 4h close > EMA200
- 4h EMA50 开始上行
- 1h EMA50 > EMA200
- 价格回踩 1h EMA50 不破

做空升级条件：

- 4h close < EMA200
- 4h EMA50 开始下行
- 1h EMA50 < EMA200
- 价格反抽 1h EMA50 不过

升级后处理：

- 不直接加满仓。
- 等下一次 15m 或 1h 回踩/反抽信号。
- 新增仓位仍必须通过标准主策略风控。
- 原试仓单可继续用移动止盈管理。
- 总仓位不得超过 `max_symbol_exposure_pct`。

### 18.14 配置

默认配置：

```yaml
reversal_strategy:
  enabled: true
  live_enabled: false
  score:
    min_watch_score: 60
    min_entry_score: 70
  position:
    min_multiplier: 0.20
    default_multiplier: 0.30
    max_multiplier: 0.50
    early_max_loss_per_trade_pct: 0.002
    confirmed_max_loss_per_trade_pct: 0.003
    max_reversal_positions: 1
  stop_loss:
    atr_multiplier: 1.2
    max_stop_distance_pct: 0.025
  entry_filter:
    max_entry_distance_from_ema50_atr: 1.0
    max_entry_distance_from_ema50_pct: 0.012
  signal_level:
    enable_early_probe: true
    early_probe_multiplier: 0.20
    confirmed_probe_min_multiplier: 0.30
    confirmed_probe_max_multiplier: 0.50
  cooldown:
    symbol_cooldown_after_loss_minutes: 180
    max_consecutive_reversal_losses: 2
    global_cooldown_minutes: 720
  time_stop:
    max_bars_to_0_5r: 8
    max_bars_to_1r: 12
  take_profit:
    tp1_rr: 1.0
    tp1_close_pct: 0.30
    tp2_close_pct: 0.30
    tp3_rr: 3.0
    tp3_close_pct: 0.40
    require_tp3_direction_check: true
    move_to_break_even_after_tp1: true
```

### 18.15 验收指标

以下是历史 `REVERSAL_PROBE` 的专项统计要求，不作为下一阶段分层策略系统的默认验收口径。下一阶段应按六类明确 `strategy_type` 与 bucket 统计：

- reversal_trade_count
- reversal_win_rate
- reversal_profit_factor
- reversal_average_win
- reversal_average_loss
- reversal_expectancy
- reversal_max_drawdown
- reversal_consecutive_losses
- reversal_avg_holding_time
- reversal_tp1_hit_rate
- reversal_break_even_rate
- reversal_failed_rate
- reversal_upgrade_to_trend_rate

历史 `REVERSAL_PROBE` 进入 Paper 的最低要求：

- 能正确生成 `REVERSAL_LONG_EARLY`、`REVERSAL_LONG_CONFIRMED`、`REVERSAL_SHORT_EARLY`、`REVERSAL_SHORT_CONFIRMED`。
- 试仓仓位不得超过标准仓位 50%。
- 早期试仓单笔最大风险不得超过账户权益 0.2%，确认试仓不得超过账户权益 0.3%。
- 回测报告必须单独统计趋势转换交易表现。

历史 `REVERSAL_PROBE` 若在第二版被重新评估，最低要求：

- `reversal_profit_factor > 1.1`
- `reversal_consecutive_losses <= 3`
- `reversal_failed_rate` 不得持续高于 65%
- `reversal_max_drawdown <= 主趋势策略最大回撤的 50%`

## 19. API 与控制面

MVP API：

- `GET /api/status`
- `GET /api/positions`
- `GET /api/signals?symbol=BTCUSDT&limit=50`
- `POST /api/control/pause`
- `POST /api/control/resume`
- `POST /api/control/kill-switch`
- `POST /api/backtest/run`

控制类接口必须有认证和审计日志。Kill Switch 请求必须记录操作者、原因、是否平仓、触发时间。

## 20. 监控与报警

Dashboard 或 CLI 至少展示：

- 当前模式：backtest / paper / live
- 策略版本
- WebSocket 状态
- 数据延迟
- 当前账户权益
- 当前可用余额
- 当前持仓
- 当日 PnL
- 当前回撤
- 最近信号
- 最近订单
- 风控状态
- Kill Switch 状态

报警等级：

- `INFO`
- `WARNING`
- `ERROR`
- `CRITICAL`

CRITICAL 场景：

- 主订单成交但止损挂单失败
- 当日亏损达到阈值
- 数据长时间中断
- 账户权益异常下降
- 持仓状态无法确认
- Kill Switch 触发

## 21. 安全与部署

### 21.1 API Key

- 不允许写死 API Key。
- API Key 只通过环境变量读取。
- `.env` 必须加入 `.gitignore`。
- 生产环境必须启用 IP 白名单。
- API Key 不得开放提现权限。
- 日志不得打印 API Secret。

### 21.2 启动前自检

以下是第二版 Live 启动前候选自检清单。第二版永久暂停，除非用户明确发令启动第二版：

- 当前环境确认为 live
- `BINANCE_API_KEY` / `BINANCE_API_SECRET` 存在
- API 权限不含提现
- IP 白名单已配置
- 当前地区、账户状态和交易所规则允许使用 USDⓈ-M Futures API
- 系统时间与交易所服务器时间偏差在允许范围内
- 数据库 migration 已执行
- Redis 可用或缓存降级已确认
- 交易对规则已同步
- position_mode = ONE_WAY
- Paper/Backtest 使用 `STRATEGY_BUCKETS` 管理子仓；第二版 Live 默认仍需重新评估 `ONE_WAY` / `HEDGE`。
- margin_type = ISOLATED
- leverage <= max_leverage
- 当前无未知持仓
- 当前无缺失止损的真实持仓
- Stop Order Guard 已启用且最近一次检查通过
- Liquidation Guard 已启用且最近一次检查通过
- 多周期数据延迟未超过阈值
- Kill Switch 可用
- 通知通道可用
- 小资金实盘专用配置已加载
- `LIVE_TRADING_CONFIRM=I_UNDERSTAND_THE_RISK`

任一失败则禁止启动 Live；但这些检查通过也不能自动启动第二版。

## 22. 测试计划

### 22.1 单元测试

必须覆盖：

- EMA / ATR / ADX / Bollinger
- DI_PLUS / DI_MINUS 方向判断
- 数据质量检查
- 多周期已收盘数据对齐
- 趋势评分
- 波动率过滤
- 回踩/反弹识别
- 止损候选选择
- 仓位计算
- 资金费率过滤
- AI JSON 校验与 fallback
- 交易所精度修正
- 强平价安全检查
- Stop Order Guard 有效止损判断

### 22.2 集成测试

必须覆盖：

- 数据获取到指标计算
- 指标到信号生成
- 信号到风控
- 风控到订单计划
- 订单计划到 Paper 撮合
- 订单状态同步
- 持仓同步
- 止损止盈同步
- Stop Order Guard 补挂与失败平仓
- 强平价/保证金拒单
- Kill Switch

### 22.3 压力与异常测试

必须覆盖：

- WebSocket 断线
- REST API 限频
- 数据库短暂不可用
- LLM 接口超时
- 行情剧烈波动
- 多订单同时触发止损
- 主订单成交但止损失败
- 网络超时后订单状态未知

## 23. 阶段规划

### V0.1 数据与指标

- 获取币安 K 线
- 存储 K 线
- 数据质量检测
- 计算指标
- 输出指标快照

### V0.2 策略信号

- 分层趋势识别
- 波动率识别
- 日线 core 策略
- 4h/1h addon 策略
- 4h hedge 策略
- 信号评分

### V0.3 回测系统

- 事件驱动回测
- 多策略子仓撮合
- 保守撮合
- 手续费、滑点、限价未成交、部分成交、资金费率、强平风险
- 回测报告
- 配置快照归档
- 按 strategy_type 单独统计

### V0.4 Paper Trading

- 实时行情
- Paper 撮合
- Paper 策略子仓
- Paper 账户权益
- 分层策略 Paper 验证
- 状态页和报警

### V0.5 风控与订单计划

- 仓位计算
- 止损止盈
- Stop Order Guard
- 强平价与保证金安全检查
- Paper/Backtest 策略子仓约束
- Live 默认 ONE_WAY + ISOLATED 执行约束
- Kill Switch
- 订单计划
- 持仓同步状态机

### V0.6 AI/Funding 过滤

- Funding 过滤
- AI filter 接口
- deterministic stub
- AI 日志
- 真实 LLM 可选启用

### V2.0 实盘交易候选事项（永久暂停）

- 测试网完整下单闭环
- Live 启动前自检
- 小资金实盘配置
- 完整监控报警
- 日报/周报

以上事项不属于第一版。除非用户明确发出“开始开发第二版实盘交易”的指令，否则不得推进。

## 24. 验收标准

### 24.1 MVP 验收

- 能拉取并存储 BTCUSDT、ETHUSDT K 线。
- 能正确计算指标，且与第三方库误差在可接受范围内。
- 能基于已收盘 K 线生成信号。
- 能通过风控过滤信号。
- 能完成无未来函数回测。
- 能完成 Paper Trading。
- 能在回测和 Paper 中生成并统计六类分层策略信号。
- 能在 Paper/Backtest 中支持日线 core 仓与 4h hedge 仓共存。
- 能记录信号、订单计划、成交、持仓和账户快照。
- Kill Switch 能暂停新开仓。
- 异常状态不会重复盲目下单。

### 24.2 第二版实盘前候选验收（永久暂停）

第二版永久暂停，除非用户明确发令启动第二版。未来进入 Live 前至少必须满足：

- Paper Trading 连续 2 周无重大错误。
- 测试网下单流程完整通过。
- 所有持仓均能自动挂止损。
- 主订单成交但止损失败的应急流程测试通过。
- Kill Switch 测试通过。
- 当日亏损限制测试通过。
- API Key 权限检查通过。
- 日志和报警完整。
- 小资金实盘参数单独配置。

## 25. 开发优先级

建议按以下顺序开发：

1. 数据库 migration 与配置系统
2. 行情采集与数据质量
3. 指标计算
4. 趋势与波动率识别
5. 主策略信号生成
6. 风控与止损/仓位计算
7. 回测系统
8. Paper Trading
9. 监控报警
10. Funding 与 AI filter stub
11. 第二版候选：测试网执行（永久暂停，需用户明确发令）
12. 第二版候选：小资金实盘（永久暂停，需用户明确发令）

理由：

- 没有数据库契约，无法复盘。
- 没有真实行情和数据质量，策略不可验证。
- 没有回测，不能进入 Paper。
- 第一版只做到 Paper，不进入 Live。
- 没有风控和 Kill Switch，不能自动下单；即使具备这些条件，也不能自动启动第二版。

## 26. 当前必须冻结的开发决策

1. MVP / 第一版默认不实盘，只做 Backtest + Paper。
2. AI 默认关闭，只保留接口和 deterministic stub。
3. 分层策略系统是下一阶段策略主线，必须进入 MVP 的回测与 Paper 验证；Live 实盘属于第二版，永久暂停，除非用户明确发令启动第二版。
4. 所有交易计算使用 Decimal。
5. 风控、订单、持仓必须建状态机。
6. 数据库必须先支持配置快照、订单事件、成交明细和回测归档。
7. 任何数据、AI、订单、持仓不确定状态默认禁止新开仓。
8. 趋势识别必须用 ADX + DI_PLUS / DI_MINUS，不能用 ADX 单独判断方向。
9. 回测和实盘必须共享多周期已收盘数据对齐函数。
10. Paper/Backtest 默认使用策略子仓模型；Live 默认使用 ONE_WAY + ISOLATED。
11. Stop Order Guard 与强平价/保证金检查属于实盘前硬门槛。

## 27. 下一步任务

下一步不应直接写交易执行代码，应先完成分层策略系统文档确认：

- `docs/superpowers/specs/2026-06-23-layered-strategy-system-design.md`：策略系统设计。
- `docs/PROJECT_CONTEXT.md`：项目目标、原则、术语。
- `docs/DECISIONS.md`：已冻结的架构与风控决策。
- `docs/TASKS.md`：下一阶段任务清单。
- `docs/HANDOFF.md`：当前进度、下一步、风险。

用户确认文档后，进入实现：

1. 新增独立策略系统模块与参数配置。
2. 为六类策略写测试 fixture。
3. Paper/Backtest 已从单仓位升级为策略子仓；后续只在第一版范围内继续优化复盘、筛选和参数验证。
4. Web 状态页展示日线主趋势、4h 子趋势、策略候选和子仓。
5. 用真实 BTCUSDT 区间验证 2025-05-13 空头主线与 2026-06-12 4h 反弹 hedge。
