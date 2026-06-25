# Layered Strategy System Design

更新时间：2026-06-23
状态：等待用户复核确认后进入实现

## 目标

把当前单一 `TREND_PULLBACK` / `REVERSAL_PROBE` 策略，升级为独立、参数化、可复用的分层策略系统。策略系统负责根据日线、4h、1h、15m 已收盘 K 线生成明确的策略信号；Paper、Backtest、Web 状态页和未来 Live 执行只消费策略系统输出，不再把策略规则散落在各模块中。

本设计覆盖多头和空头对称逻辑。

## 核心原则

1. 日线决定主趋势。
2. 4h 决定主趋势启动、子趋势和 hedge 反弹/回调。
3. 1h 决定执行确认。
4. 15m 决定具体入场、止损和执行触发。
5. 所有策略参数必须集中配置，不能写死在 Paper、Backtest 或 Web 展示层。
6. 同一 symbol 必须支持多策略子仓共存，尤其是主趋势仓与 hedge 仓共存。
7. Backtest、Paper、未来 Live 必须调用同一套策略系统。
8. 所有信号必须带明确 `strategy_type`，不能再用模糊的主趋势/趋势转换名称表达不同交易目的。

## 策略命名

空头主趋势场景：

- `SHORT_DAY_CORE`：日线空头主仓。用于捕捉日线级别 EMA15 跌破 MA60 后的主趋势下跌。
- `SHORT_4H_1H_ADDON`：日线空头下的 4h/1h 顺势空头加仓。用于主空趋势中，4h/1h 再次转弱或反弹失败后的加仓。
- `LONG_4H_HEDGE`：日线空头下的 4h 反弹多仓。用于保留日线空头主仓的同时，捕捉 4h 级别反弹。

多头主趋势场景：

- `LONG_DAY_CORE`：日线多头主仓。用于捕捉日线级别 EMA15 上穿 MA60 后的主趋势上涨。
- `LONG_4H_1H_ADDON`：日线多头下的 4h/1h 顺势多头加仓。用于主多趋势中，4h/1h 再次转强或回调结束后的加仓。
- `SHORT_4H_HEDGE`：日线多头下的 4h 回调空仓。用于保留日线多头主仓的同时，捕捉 4h 级别回调。

旧名称处理：

- `TREND_PULLBACK` 保留为历史兼容名称，不再作为新增策略系统的主语义。
- `REVERSAL_PROBE` 保留为历史兼容名称，后续如需保留，应映射为更明确的 hedge 或 transition 策略，不再作为默认核心策略名。

## 默认参数

默认均线参数：

```yaml
fast_ma_type: EMA
fast_period: 15
slow_ma_type: MA
slow_period: 60
atr_period: 14
dmi_period: 12
swing_lookback: 20
min_adx: 20
```

时间框架参数：

```yaml
core_timeframe: 1d
child_timeframe: 4h
confirm_timeframe: 1h
entry_timeframe: 15m
optional_runtime_timeframes: [5m]
```

风险参数初始建议：

```yaml
core_risk_pct: 0.005
addon_risk_pct: 0.003
hedge_risk_pct: 0.002
max_core_positions_per_symbol: 1
max_addon_positions_per_symbol: 2
max_hedge_positions_per_symbol: 1
allow_core_and_hedge_coexist: true
allow_long_and_short_same_symbol: true
trend_pullback_take_profit_mode: TRAILING
max_fee_to_risk_ratio: 0.25
```

以上数值必须作为配置进入策略系统，回测页面、批量回测、Paper runner 只能传参，不能复制规则。

## 趋势状态定义

### 日线主趋势

日线多头：

- `daily_fast_ma > daily_slow_ma`
- 日线快线斜率向上，或价格收盘站上慢线后快线持续靠近慢线
- 可选动能确认：`ADX >= min_adx` 且 `DI+ > DI-`

日线空头：

- `daily_fast_ma < daily_slow_ma`
- 日线快线斜率向下，或价格收盘跌破慢线后快线持续靠近慢线
- 可选动能确认：`ADX >= min_adx` 且 `DI- > DI+`

日线转换期：

- 日线尚未完成快慢线交叉，但 4h 已经完成反向交叉。
- 允许小风险试仓，但不能直接按主仓风险开满。
- 例如 2025-05-13 20:00 附近，4h 已死叉而日线仍 `EMA15 > MA60`，应允许 `SHORT_DAY_CORE` 的 early/core-probe 版本或独立 `SHORT_DAY_CORE` 初始试仓。

### 4h 子趋势

4h 多头：

- 4h 快线高于慢线，或 4h 快线上穿慢线后持续向上。
- 1h 同向确认时，允许顺势加仓或 hedge 多仓。

4h 空头：

- 4h 快线低于慢线，或 4h 快线下穿慢线后持续向下。
- 1h 同向确认时，允许顺势加仓或 hedge 空仓。

## 信号规则

### SHORT_DAY_CORE

触发场景：

- 日线已确认空头，或日线转换期但 4h 已率先死叉并转弱。
- 4h 不要求等待回抽到快线，允许捕捉趋势启动。
- 1h 空头确认优先；如果 4h 死叉刚发生且 1h 已提前空头，也可开初始试仓。
- 15m 用于入场确认，可是跌破、反抽失败或连续弱势收盘。

入场类型：

- `CORE_CROSS_ENTRY`：日线或 4h 快慢线交叉后的主趋势启动。
- `CORE_BREAKDOWN_ENTRY`：价格跌破关键 swing low 后，15m/1h 确认延续。
- `CORE_PULLBACK_ENTRY`：反抽快线或前低压力失败后的入场。

退出/减仓：

- 触及主趋势 trailing stop。
- 日线重新转多或 4h 强反转并持续确认。
- 到达阶段目标后部分止盈，剩余仓位跟随日线趋势。

### SHORT_4H_1H_ADDON

触发场景：

- 已存在或允许 `SHORT_DAY_CORE`。
- 日线仍为空头。
- 4h/1h 再次从反弹转弱，或反抽快线/慢线失败。
- 15m 出现顺势确认。

限制：

- 每个 symbol 的 addon 数量受 `max_addon_positions_per_symbol` 限制。
- addon 风险小于 core。
- addon 的止损更贴近 4h/1h swing high。

### LONG_4H_HEDGE

触发场景：

- 日线仍为空头。
- 4h 转为多头或从极端下跌后出现明确反弹结构。
- 1h 多头确认。
- 15m 回踩不破或突破确认。

用途：

- 不是日线反转主仓。
- 是对日线空头主仓的反弹保护和收益增强。
- 允许与 `SHORT_DAY_CORE` 同时存在。

退出：

- 4h 多头失败。
- 1h 重新死叉。
- 触及预设反弹目标，例如 4h 慢线、前高、固定 R 倍数或 trailing stop。

### 多头对称规则

`LONG_DAY_CORE` 对称 `SHORT_DAY_CORE`。

`LONG_4H_1H_ADDON` 对称 `SHORT_4H_1H_ADDON`。

`SHORT_4H_HEDGE` 对称 `LONG_4H_HEDGE`。

所有参数必须复用同一套配置，不允许多头和空头规则手工复制后发散。

## 持仓模型

当前单仓位模型必须升级为策略子仓模型。

最小目标：

- 同一 symbol 下可同时存在一个主趋势 core 仓和一个反向 hedge 仓。
- 同一 symbol 下可存在多个 addon 仓，但数量受配置限制。
- 每个子仓必须记录：`symbol`、`side`、`strategy_type`、`strategy_bucket`、`entry_timeframe`、`entry_time`、`entry_price`、`stop_loss`、`take_profit`、`risk_pct`、`parent_strategy_type`。

推荐 bucket：

- `DAY_CORE`
- `FOUR_HOUR_ADDON`
- `FOUR_HOUR_HEDGE`

共存矩阵：

| 已有仓位 | 新信号 | 允许 | 说明 |
| --- | --- | --- | --- |
| `SHORT_DAY_CORE` | `LONG_4H_HEDGE` | 是 | 日线空头下 4h 反弹多仓 |
| `SHORT_DAY_CORE` | `SHORT_4H_1H_ADDON` | 是 | 顺势加仓，受数量限制 |
| `SHORT_DAY_CORE` | `LONG_DAY_CORE` | 否 | 日线主趋势反转前不能直接反向 core |
| `LONG_DAY_CORE` | `SHORT_4H_HEDGE` | 是 | 日线多头下 4h 回调空仓 |
| `LONG_DAY_CORE` | `LONG_4H_1H_ADDON` | 是 | 顺势加仓，受数量限制 |
| `LONG_DAY_CORE` | `SHORT_DAY_CORE` | 否 | 日线主趋势反转前不能直接反向 core |

未来 Live 若使用 Binance Futures，必须使用 HEDGE position mode 才能真实支持同一 symbol 多空共存。Paper/Backtest 先实现策略子仓模型，Live 仍需独立自检和风险门槛。

## 策略系统接口

建议新增独立策略系统模块，供 Paper/Backtest/Web 调用。

输入：

```python
StrategySystemInput(
    symbol="BTCUSDT",
    histories={
        "1d": tuple[Kline, ...],
        "4h": tuple[Kline, ...],
        "1h": tuple[Kline, ...],
        "15m": tuple[Kline, ...],
    },
    open_positions=tuple[StrategyPositionView, ...],
    config=LayeredStrategyConfig(...),
)
```

输出：

```python
StrategyDecision(
    signals=tuple[StrategySignal, ...],
    diagnostics=StrategyDiagnostics(...),
)
```

每个信号必须包含：

```python
StrategySignal(
    action="OPEN" | "CLOSE" | "REDUCE" | "WAIT",
    side="LONG" | "SHORT",
    strategy_type="SHORT_DAY_CORE",
    strategy_bucket="DAY_CORE",
    entry_price=Decimal(...),
    stop_loss=Decimal(...),
    take_profit=Decimal(...),
    risk_pct=Decimal(...),
    reason=(...),
    config_snapshot={...},
)
```

## Web 展示要求

状态页必须显示：

- 当前日线主趋势：日线多头 / 日线空头 / 转换期 / 震荡。
- 4h 子趋势：多头 / 空头 / 反弹 / 回调 / 震荡。
- 当前已满足的策略候选：`SHORT_DAY_CORE`、`SHORT_4H_1H_ADDON`、`LONG_4H_HEDGE` 等。
- 每个策略候选的参数和未满足条件。
- 当前持仓按 strategy bucket 分组展示，而不是只显示一个“持仓情况”。

页面文案禁止继续写死 `EMA50/EMA200`。必须动态显示当前配置，例如 `EMA15 / MA60`、`快线`、`慢线`。

## Backtest 要求

回测系统必须支持：

- 多策略子仓并行。
- 同一 symbol 多空共存。
- 按 strategy_type 分别统计：交易次数、胜率、净盈亏、最大回撤、平均持仓时间、利润因子。
- 按 bucket 统计：core、addon、hedge 对整体收益和回撤的贡献。
- 参数快照必须保存完整 `LayeredStrategyConfig`。

验收用例必须覆盖：

1. 2025-05-13 附近 4h 率先死叉时，系统能产生空头初始信号，而不是等日线完全死叉后才反应。
2. 日线空头确认后，系统能持有或补充 `SHORT_DAY_CORE`。
3. 2026-06-12 20:00 后，日线仍为空头但 4h 转多时，系统能产生 `LONG_4H_HEDGE`，且不强制关闭 `SHORT_DAY_CORE`。
4. 多头趋势下，以上逻辑完全对称。

## 分阶段实现建议

阶段 1：文档与测试框架

- 完成本设计文档、README、PRD、PROJECT_CONTEXT、DECISIONS、TASKS、HANDOFF 同步。
- 新增策略系统测试 fixture，先用人工 K 线路径验证信号语义。

阶段 2：独立策略系统

- 新增 `LayeredStrategyConfig`。
- 新增日线/4h/1h/15m 趋势状态计算。
- 新增六类策略信号生成。
- 暂时通过适配器把新信号转成旧 Paper 可消费格式，先不改全部执行层。

阶段 3：多策略子仓 Paper/Backtest

- PaperTradingEngine 从单仓位改为多子仓。
- Backtest engine 支持多子仓并行撮合。
- 按 strategy_type 和 bucket 输出指标。

阶段 4：状态页和回测页升级

- 状态页展示策略系统诊断和多子仓。
- 回测页支持 LayeredStrategyConfig 参数输入。
- 批量回测支持 core/addon/hedge 参数组。

阶段 5：真实运行验证

- 用历史 BTCUSDT 数据回放 2025-05-13 至今。
- 检查是否捕捉日线空头主趋势。
- 检查是否捕捉 2026-06-12 20:00 后的 4h 反弹多头 hedge。
- 对比旧策略与新策略的收益、回撤、胜率和换手。

## 明确不在本轮实现的内容

- 不开启真实 Live 下单。
- 不修改 Binance 账户真实 position mode。
- 不直接承诺 HEDGE Live 可用；Live 需要独立自检、API 权限和小资金实盘配置通过。
- 不把历史回测报告改写为新结论，历史报告保留原始上下文。
