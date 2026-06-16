PRD 修复补丁 v1.1：趋势转换试仓与实盘风控修复

1. 修复目标

本补丁用于修复当前 PRD 中与以下模块相关的关键问题：

1. 趋势转换试仓仓位计算；
2. 趋势转换试仓止损公式；
3. 4H / 1H 趋势冲突与趋势转换模块的逻辑冲突；
4. 信号生成顺序；
5. ADX 趋势方向判断；
6. 止损订单存在性检查；
7. 强平价与保证金安全检查；
8. 合约持仓模式与保证金模式；
9. 多周期数据对齐；
10. 回测撮合与实盘一致性；
11. 文档编号、字段、工程目录修正。

本补丁优先级高于原 PRD 中存在冲突的旧规则。

⸻

2. P0 修复：趋势转换试仓仓位计算

2.1 问题说明

原 PRD 中趋势转换试仓同时存在两套仓位逻辑：

趋势转换试仓仓位 = 主策略标准仓位 * 30%

以及：

max_reversal_loss_per_trade_pct: 0.003

后续伪代码又使用：

risk_amount = account_equity * 0.003
base_qty = risk_amount / stop_distance
final_qty = base_qty * score_multiplier

这会导致实际风险被二次缩小。

例如：

评分	score_multiplier	实际账户风险
70 - 74	0.20	0.06%
75 - 84	0.30	0.09%
85 - 100	0.50	0.15%

这不符合“趋势转换试仓最大风险 0.3%”的原意。

⸻

2.2 修复原则

趋势转换试仓应同时满足两个限制：

1. 单笔最大亏损不得超过账户权益的 0.3%；
2. 仓位不得超过主策略标准仓位的 20% / 30% / 50%。

最终仓位应取两者中的较小值：

最终趋势转换仓位 = min(
    0.3% 风险上限仓位,
    主策略标准仓位 × 趋势转换评分系数
)

⸻

2.3 修复后的仓位计算公式

主策略标准风险金额：

standard_risk_amount = account_equity * risk_per_trade_pct

主策略标准仓位：

standard_qty = standard_risk_amount / stop_distance

趋势转换风险金额：

reversal_risk_amount = account_equity * max_reversal_loss_per_trade_pct

趋势转换风险上限仓位：

reversal_risk_qty = reversal_risk_amount / stop_distance

评分限制仓位：

score_limited_qty = standard_qty * reversal_score_multiplier

最终趋势转换仓位：

final_reversal_qty = min(
    reversal_risk_qty,
    score_limited_qty
)

⸻

2.4 修复后的仓位伪代码

def calculate_reversal_position_size(
    account_equity,
    risk_per_trade_pct,
    max_reversal_loss_per_trade_pct,
    entry_price,
    stop_loss,
    reversal_score,
    atr_state,
    ai_decision,
    liquidity_state,
    symbol_rules
):
    stop_distance = abs(entry_price - stop_loss)
    if stop_distance <= 0:
        return 0
    # 1. 主策略标准仓位
    standard_risk_amount = account_equity * risk_per_trade_pct
    standard_qty = standard_risk_amount / stop_distance
    # 2. 趋势转换最大风险仓位
    reversal_risk_amount = account_equity * max_reversal_loss_per_trade_pct
    reversal_risk_qty = reversal_risk_amount / stop_distance
    # 3. 趋势转换评分仓位系数
    if reversal_score < 70:
        score_multiplier = 0.0
    elif reversal_score < 75:
        score_multiplier = 0.20
    elif reversal_score < 85:
        score_multiplier = 0.30
    else:
        score_multiplier = 0.50
    score_limited_qty = standard_qty * score_multiplier
    # 4. 先取风险上限和评分上限中的较小值
    final_qty = min(reversal_risk_qty, score_limited_qty)
    # 5. AI 风险过滤调整
    if ai_decision == "BLOCK":
        ai_multiplier = 0.0
    elif ai_decision == "WARN":
        ai_multiplier = 0.5
    else:
        ai_multiplier = 1.0
    # 6. 波动率调整
    if atr_state == "EXTREME":
        volatility_multiplier = 0.0
    elif atr_state == "HIGH":
        volatility_multiplier = 0.5
    else:
        volatility_multiplier = 1.0
    # 7. 流动性调整
    if liquidity_state == "LOW":
        liquidity_multiplier = 0.5
    else:
        liquidity_multiplier = 1.0
    final_qty *= ai_multiplier
    final_qty *= volatility_multiplier
    final_qty *= liquidity_multiplier
    # 8. 按交易所规则修正精度
    final_qty = round_step_size(final_qty, symbol_rules.step_size)
    # 9. 检查最小数量和最小名义价值
    if final_qty < symbol_rules.min_qty:
        return 0
    if final_qty * entry_price < symbol_rules.min_notional:
        return 0
    return final_qty

⸻

2.5 配置修复

新增或确认以下配置：

reversal_strategy:
  position:
    min_multiplier: 0.20
    default_multiplier: 0.30
    max_multiplier: 0.50
    max_loss_per_trade_pct: 0.003

主策略配置保持：

risk:
  risk_per_trade_pct: 0.01

解释：

主策略单笔风险默认 1%；
趋势转换试仓单笔风险默认 0.3%；
趋势转换仓位最高不得超过主策略标准仓位的 50%。

⸻

3. P0 修复：趋势转换试仓止损公式

3.1 问题说明

原 PRD 中趋势转换做多止损为：

long_reversal_stop = min(
    recent_15m_swing_low - tick_size,
    ema200_15m - tick_size,
    entry_price - ATR * 1.2
)

对多单来说，min() 会选择最低的止损价，也就是最宽的止损。

原 PRD 中趋势转换做空止损为：

short_reversal_stop = max(
    recent_15m_swing_high + tick_size,
    ema200_15m + tick_size,
    entry_price + ATR * 1.2
)

对空单来说，max() 会选择最高的止损价，也就是最宽的止损。

趋势转换交易属于提前参与型交易，止损不应该默认取最宽位置。

⸻

3.2 修复原则

趋势转换试仓止损应满足：

1. 尊重结构位；
2. 不允许止损过宽；
3. 不允许靠近强平价；
4. 不允许亏损后扩大止损；
5. 如果止损距离超过最大限制，直接放弃交易。

⸻

3.3 修复后的多单止损

多单结构止损：

structural_stop = min(
    recent_15m_swing_low - tick_size,
    ema200_15m - tick_size
)

ATR 限制止损：

atr_stop = entry_price - ATR * reversal_atr_stop_multiplier

最终多单止损：

long_reversal_stop = max(
    structural_stop,
    atr_stop
)

含义：

多单止损选择更靠近入场价的有效止损，避免止损过宽。

⸻

3.4 修复后的空单止损

空单结构止损：

structural_stop = max(
    recent_15m_swing_high + tick_size,
    ema200_15m + tick_size
)

ATR 限制止损：

atr_stop = entry_price + ATR * reversal_atr_stop_multiplier

最终空单止损：

short_reversal_stop = min(
    structural_stop,
    atr_stop
)

含义：

空单止损选择更靠近入场价的有效止损，避免止损过宽。

⸻

3.5 最大止损距离限制

新增硬限制：

reversal_strategy:
  stop_loss:
    atr_multiplier: 1.2
    max_stop_distance_pct: 0.025

规则：

如果 abs(entry_price - stop_loss) / entry_price > max_reversal_stop_distance_pct：
    放弃交易

默认：

趋势转换试仓最大止损距离不得超过 2.5%。

⸻

4. P0 修复：趋势冲突处理

4.1 问题说明

原 PRD 中趋势冲突处理写法为：

如果 4H 看空，1H 看多：
trend_state = TRANSITION
action = WAIT

但新增趋势转换模块的目标正是处理：

4H 尚未完全反转，
但 1H 和 15M 已经出现明确反向结构。

如果趋势识别模块直接输出 WAIT 并终止后续策略，则趋势转换模块永远无法运行。

⸻

4.2 修复后的趋势冲突规则

将原规则：

TRANSITION => WAIT

修改为：

TRANSITION => 主策略 WAIT，但趋势转换模块继续评估

⸻

4.3 修复后的 4H / 1H 冲突处理

如果 4H 看空，1H 看多：

trend_state = TRANSITION
main_strategy_action = WAIT
reversal_strategy_action = EVALUATE_REVERSAL_LONG

如果 4H 看多，1H 看空：

trend_state = TRANSITION
main_strategy_action = WAIT
reversal_strategy_action = EVALUATE_REVERSAL_SHORT

如果 4H 和 1H 都看多：

trend_state = UPTREND
main_strategy_action = EVALUATE_LONG
reversal_strategy_action = DISABLED

如果 4H 和 1H 都看空：

trend_state = DOWNTREND
main_strategy_action = EVALUATE_SHORT
reversal_strategy_action = DISABLED

如果 EMA50 / EMA200 缠绕，且 1H / 15M 没有明确结构：

trend_state = RANGE
main_strategy_action = WAIT
reversal_strategy_action = WAIT

⸻

4.4 修复后的趋势识别输出结构

趋势识别模块输出应修改为：

{
  "symbol": "ETHUSDT",
  "trend_state": "TRANSITION",
  "main_strategy_action": "WAIT",
  "reversal_strategy_action": "EVALUATE_REVERSAL_LONG",
  "allow_long": false,
  "allow_short": false,
  "allow_reversal_long": true,
  "allow_reversal_short": false,
  "reason": [
    "4H remains below EMA200",
    "1H close > EMA200",
    "15M trend may be turning bullish"
  ]
}

⸻

5. P1 修复：信号生成顺序

5.1 问题说明

原 PRD 中信号生成顺序为：

7. 生成主趋势回踩信号
8. 生成趋势转换试仓信号
9. 生成突破确认信号
10. 生成退出信号

这在自动交易系统中不够安全。

正确原则：

先处理风险和退出，再考虑新开仓。

⸻

5.2 修复后的信号生成顺序

将信号生成顺序修改为：

1. 更新市场数据
2. 计算多周期指标
3. 同步账户、订单、持仓
4. 判断账户级风控状态
5. 判断已有持仓退出条件
6. 生成退出信号
7. 判断 AI 新闻过滤状态
8. 判断资金费率过滤状态
9. 判断已有持仓冲突
10. 生成主趋势回踩信号
11. 生成趋势转换试仓信号
12. 生成突破确认信号
13. 输出最终信号

⸻

5.3 修复后的最终执行优先级

最终执行优先级为：

账户级风控
>
止损 / 强平保护
>
已有持仓退出信号
>
AI 新闻过滤器
>
资金费率过滤器
>
已有持仓冲突检查
>
主趋势回踩信号
>
趋势转换试仓信号
>
突破确认信号
>
WAIT

规则：

1. 只要账户级风控触发，所有新开仓信号无效；
2. 只要持仓缺少止损，所有新开仓信号无效；
3. 只要已有持仓触发退出，必须先处理退出；
4. AI BLOCK 禁止新开仓；
5. Funding BLOCK 禁止新开仓；
6. 反向持仓存在时禁止直接反手；
7. 主趋势信号优先于趋势转换信号；
8. 趋势转换信号优先于突破信号。

⸻

6. P1 修复：ADX 增加 DI+ / DI- 方向判断

6.1 问题说明

ADX 只表示趋势强度，不表示趋势方向。

例如：

ADX 高，可能是强上涨；
ADX 高，也可能是强下跌。

因此只使用：

ADX >= 20

不足以判断趋势方向。

⸻

6.2 指标模块新增字段

ADX 指标模块必须同时输出：

ADX
DI_PLUS
DI_MINUS

数据库 indicator_snapshots 表建议新增字段：

ALTER TABLE indicator_snapshots
ADD COLUMN di_plus NUMERIC,
ADD COLUMN di_minus NUMERIC;

⸻

6.3 多头趋势确认

多头趋势强度确认：

ADX >= min_adx
AND DI_PLUS > DI_MINUS

强多头趋势确认：

ADX >= strong_adx
AND DI_PLUS > DI_MINUS
AND DI_PLUS 正在上升

⸻

6.4 空头趋势确认

空头趋势强度确认：

ADX >= min_adx
AND DI_MINUS > DI_PLUS

强空头趋势确认：

ADX >= strong_adx
AND DI_MINUS > DI_PLUS
AND DI_MINUS 正在上升

⸻

6.5 趋势转换做多 DI 条件

趋势转换做多加分条件：

DI_PLUS 上穿 DI_MINUS
或
DI_PLUS 连续 2 根 15M K 线高于 DI_MINUS

⸻

6.6 趋势转换做空 DI 条件

趋势转换做空加分条件：

DI_MINUS 上穿 DI_PLUS
或
DI_MINUS 连续 2 根 15M K 线高于 DI_PLUS

⸻

7. P0 修复：止损订单存在性检查

7.1 问题说明

自动交易系统不能只在开仓后尝试挂止损，还必须持续检查：

真实持仓是否存在；
对应止损订单是否存在；
止损订单数量是否正确；
止损方向是否正确；
止损是否 reduceOnly；
止损是否已经失效。

否则可能出现：

主订单成交，但止损失败；
止损单被取消；
止损单数量不匹配；
系统本地以为有止损，交易所实际没有止损。

⸻

7.2 新增 Stop Order Guard

新增模块：

stop_order_guard.py

模块职责：

1. 定时扫描所有交易所真实持仓；
2. 检查每个持仓是否存在有效止损单；
3. 检查止损单数量是否覆盖当前持仓；
4. 检查止损方向是否正确；
5. 检查止损单是否 reduceOnly；
6. 如果缺失止损，立即补挂；
7. 如果补挂失败，立即市价平仓；
8. 触发 CRITICAL 告警。

⸻

7.3 配置

stop_order_guard:
  enabled: true
  check_interval_seconds: 5
  max_repair_attempts: 3
  close_position_if_repair_failed: true

⸻

7.4 处理流程

扫描真实持仓
  ↓
是否有持仓？
  ↓
无持仓 => 跳过
  ↓
有持仓 => 查询当前止损单
  ↓
止损单存在且有效？
  ↓
是 => 继续监控
  ↓
否 => 补挂止损
  ↓
补挂成功？
  ↓
是 => 记录日志并告警
  ↓
否 => 市价平仓
  ↓
发送 CRITICAL 告警

⸻

7.5 止损单有效性标准

一个止损单必须同时满足：

1. symbol 与持仓一致；
2. side 与持仓退出方向一致；
3. quantity 覆盖当前持仓数量；
4. reduceOnly = true；
5. stopPrice 有效；
6. 订单状态为 NEW；
7. 触发价没有明显错误；
8. 不会增加反向仓位。

⸻

8. P0 修复：强平价与保证金检查

8.1 问题说明

USDT 永续合约存在强平风险。
系统不能只看 ATR 止损，还必须检查：

预估强平价；
止损价；
标记价格；
保证金率；
维持保证金；
杠杆倍数。

如果策略止损价距离强平价太近，极端行情下可能还没触发策略止损，交易所已经强平。

⸻

8.2 新增强平安全检查

新增配置：

liquidation_guard:
  enabled: true
  liquidation_buffer_pct: 0.01
  reject_if_stop_too_close_to_liquidation: true

默认要求：

止损价与强平价至少保持 1% 的价格距离。

⸻

8.3 多单强平检查

多单要求：

liquidation_price < stop_loss < entry_price

安全距离：

(stop_loss - liquidation_price) / entry_price >= liquidation_buffer_pct

如果不满足：

禁止开仓

⸻

8.4 空单强平检查

空单要求：

entry_price < stop_loss < liquidation_price

安全距离：

(liquidation_price - stop_loss) / entry_price >= liquidation_buffer_pct

如果不满足：

禁止开仓

⸻

8.5 下单前检查

每次下单前必须执行：

1. 获取账户权益；
2. 获取当前 symbol 杠杆限制；
3. 计算预估保证金；
4. 计算或查询预估强平价；
5. 检查止损价是否安全；
6. 检查账户保证金率；
7. 检查最大杠杆限制；
8. 检查最大名义价值限制；
9. 通过后才允许下单。

⸻

9. P1 修复：合约持仓模式与保证金模式

9.1 问题说明

币安合约支持：

单向持仓模式 One-way Mode
双向持仓模式 Hedge Mode

也支持：

逐仓 ISOLATED
全仓 CROSSED

原 PRD 中没有明确系统默认模式，这会导致执行模块实现不一致。

⸻

9.2 MVP 默认模式

MVP 推荐：

execution:
  position_mode: ONE_WAY
  margin_type: ISOLATED

原因：

ONE_WAY 更简单；
ISOLATED 更适合小资金测试；
避免单个策略错误影响整个账户权益；
避免同一 symbol 同时存在 long 和 short。

⸻

9.3 下单前必须确认

下单前必须确认：

1. 当前账户 position_mode；
2. 当前 symbol margin_type；
3. 当前 symbol leverage；
4. 当前 symbol 是否已有持仓；
5. 当前 symbol 是否已有反向挂单。

⸻

9.4 ONE_WAY 模式规则

在 ONE_WAY 模式下：

1. 同一 symbol 同一时间只能持有一个方向；
2. 有多单时，不允许直接开空；
3. 有空单时，不允许直接开多；
4. 反向信号只能先触发退出；
5. 退出完成后，等待下一根 K 线重新评估。

⸻

9.5 HEDGE 模式规则

如果未来启用 HEDGE 模式，必须单独配置：

execution:
  position_mode: HEDGE

并明确订单字段：

positionSide = LONG
positionSide = SHORT
reduceOnly
closePosition

HEDGE 模式不作为 MVP 默认实现。

⸻

10. P1 修复：多周期数据对齐规则

10.1 问题说明

多周期策略最容易出现未来函数。

尤其是：

15M 信号使用了尚未收盘的 1H K 线；
15M 信号使用了尚未收盘的 4H K 线；
回测和实盘使用了不同的数据对齐方式。

这会导致回测结果虚高。

⸻

10.2 数据对齐原则

新增规则：

所有周期指标必须只使用已收盘 K 线。

⸻

10.3 15M 信号生成时的数据要求

当系统在 15M 周期生成信号时：

1. 15M 使用最近一根已收盘 15M K 线；
2. 1H 使用最近一根已收盘 1H K 线；
3. 4H 使用最近一根已收盘 4H K 线；
4. 禁止使用正在形成中的 1H K 线；
5. 禁止使用正在形成中的 4H K 线。

⸻

10.4 示例

假设当前时间为：

2026-01-01 10:15:00

如果 15M K 线刚收盘，则可用于信号的周期为：

15M：10:00 - 10:15 已收盘 K 线
1H：09:00 - 10:00 已收盘 K 线
4H：04:00 - 08:00 已收盘 K 线

不可使用：

1H：10:00 - 11:00 正在形成中的 K 线
4H：08:00 - 12:00 正在形成中的 K 线

⸻

10.5 回测与实盘一致性

回测与实盘必须共用同一个数据对齐函数：

def get_closed_multi_timeframe_context(current_time, symbol):
    kline_15m = get_latest_closed_kline(symbol, "15m", current_time)
    kline_1h = get_latest_closed_kline(symbol, "1h", current_time)
    kline_4h = get_latest_closed_kline(symbol, "4h", current_time)
    return {
        "15m": kline_15m,
        "1h": kline_1h,
        "4h": kline_4h
    }

禁止回测使用一套逻辑、实盘使用另一套逻辑。

⸻

11. P1 修复：趋势转换信号分级

11.1 问题说明

原趋势转换策略要求：

1H close > EMA200
15M EMA50 > EMA200
15M 回踩 EMA50 或 EMA200

该规则较稳，但对于真正的 V 型反转，可能仍然偏晚。

⸻

11.2 修复方案：分为 A 类早期试仓与 B 类确认试仓

趋势转换做多分为：

REVERSAL_LONG_EARLY
REVERSAL_LONG_CONFIRMED

趋势转换做空分为：

REVERSAL_SHORT_EARLY
REVERSAL_SHORT_CONFIRMED

⸻

11.3 A 类趋势转换做多：早期试仓

适用场景：

4H 尚未转多；
1H 开始转强；
15M 已经率先突破；
但 15M EMA50 尚未完全上穿 EMA200。

条件：

4H 不再创新低
AND 1H close > EMA50
AND 1H close 接近或突破 EMA200
AND 15M close > EMA200
AND 15M EMA50 斜率向上
AND 15M 放量突破最近 20 根 K 线高点
AND 15M 第一次回踩 EMA20 或 EMA50 不破
AND ATR_PCT 不处于 EXTREME
AND AI_FILTER != BLOCK
AND funding_filter != BLOCK

仓位：

标准仓位的 20%

风险：

单笔最大亏损不得超过账户权益 0.2% - 0.3%

⸻

11.4 B 类趋势转换做多：确认试仓

条件：

4H 出现止跌结构
AND 1H close > EMA200
AND 1H EMA50 斜率向上
AND 15M EMA50 > EMA200
AND 15M 回踩 EMA50 不破
AND 15M 出现止跌确认 K 线
AND 成交量确认

仓位：

标准仓位的 30% - 50%

⸻

11.5 A 类趋势转换做空：早期试仓

条件：

4H 不再创新高
AND 1H close < EMA50
AND 1H close 接近或跌破 EMA200
AND 15M close < EMA200
AND 15M EMA50 斜率向下
AND 15M 放量跌破最近 20 根 K 线低点
AND 15M 第一次反抽 EMA20 或 EMA50 不过
AND ATR_PCT 不处于 EXTREME
AND AI_FILTER != BLOCK
AND funding_filter != BLOCK

仓位：

标准仓位的 20%

⸻

11.6 B 类趋势转换做空：确认试仓

条件：

4H 出现滞涨结构
AND 1H close < EMA200
AND 1H EMA50 斜率向下
AND 15M EMA50 < EMA200
AND 15M 反抽 EMA50 不过
AND 15M 出现滞涨确认 K 线
AND 成交量确认

仓位：

标准仓位的 30% - 50%

⸻

12. P1 修复：趋势转换禁止追涨追跌

12.1 问题说明

趋势转换模块用于捕捉 V 型反转，但不能在大阳线或大阴线之后盲目追单。

⸻

12.2 新增配置

reversal_strategy:
  entry_filter:
    max_entry_distance_from_ema50_atr: 1.0
    max_entry_distance_from_ema50_pct: 0.012

⸻

12.3 做多禁止追涨规则

如果满足以下任意条件，禁止趋势转换做多：

entry_price - EMA50_15M > 1.0 * ATR

或：

(entry_price - EMA50_15M) / entry_price > 0.012

即：

入场价距离 15M EMA50 超过 1 ATR 或 1.2%，禁止追多。

⸻

12.4 做空禁止追跌规则

如果满足以下任意条件，禁止趋势转换做空：

EMA50_15M - entry_price > 1.0 * ATR

或：

(EMA50_15M - entry_price) / entry_price > 0.012

即：

入场价距离 15M EMA50 超过 1 ATR 或 1.2%，禁止追空。

⸻

13. P1 修复：趋势转换 TP3 方向校验

13.1 问题说明

原 PRD 写：

做多 TP3 = 4H EMA200 或 3R
做空 TP3 = 4H EMA200 或 3R

但 4H EMA200 并不总是在正确方向上。

⸻

13.2 多单 TP3 方向校验

趋势转换做多：

只有当 EMA200_4H > entry_price 时，EMA200_4H 才可作为 TP3。

否则：

TP3 = max(previous_high, entry_price + 3R)

⸻

13.3 空单 TP3 方向校验

趋势转换做空：

只有当 EMA200_4H < entry_price 时，EMA200_4H 才可作为 TP3。

否则：

TP3 = min(previous_low, entry_price - 3R)

⸻

14. P1 修复：回测真实撮合补充

14.1 必须模拟的交易成本

回测必须加入：

1. Maker 手续费；
2. Taker 手续费；
3. 市价单滑点；
4. 限价单未成交；
5. 止损滑点；
6. 资金费率；
7. 最小下单数量；
8. 最小名义价值；
9. 价格精度；
10. 数量精度；
11. 强平风险；
12. 订单部分成交。

⸻

14.2 限价单成交规则

限价买单：

如果下一根 K 线 low <= limit_price，则认为可能成交。

限价卖单：

如果下一根 K 线 high >= limit_price，则认为可能成交。

保守规则：

如果触发价格只被影线轻微触碰，可按未成交或部分成交处理。

⸻

14.3 止损滑点规则

止损触发后，不应直接按 stop_price 成交。

建议：

long_stop_fill_price = stop_price * (1 - stop_slippage_pct)
short_stop_fill_price = stop_price * (1 + stop_slippage_pct)

默认：

backtest:
  stop_slippage_pct: 0.0005

极端波动时：

backtest:
  extreme_stop_slippage_pct: 0.002

⸻

14.4 同一根 K 线同时触发止损和止盈

保守处理：

同一根 K 线同时触发止损和止盈时，优先按止损处理。

此规则保持不变。

⸻

15. P2 修复：文档编号

15.1 问题说明

当前文档中同时存在：

20A. 趋势转换试仓策略
20B. 趋势转换做多策略
...
20N. 趋势转换交易单独统计指标

后面又出现：

20. AI 新闻过滤器

容易造成目录冲突。

⸻

15.2 建议修复

建议将新增模块正式编号为：

20. 趋势转换试仓策略
21. 趋势转换做多策略
22. 趋势转换做空策略
23. 趋势转换试仓风控规则
24. 趋势转换模块配置
25. 趋势转换信号结构
26. 趋势转换主流程伪代码
27. 趋势转换做多伪代码
28. 趋势转换做空伪代码
29. 趋势转换策略与主策略的关系
30. 趋势转换策略适配 ETH 示例
31. 趋势转换模块验收标准
32. 趋势转换交易单独统计指标
33. AI 新闻过滤器
34. 资金费率过滤

后续章节依次顺延。

如果不想大规模重排，至少将：

20. AI 新闻过滤器

改成：

21. AI 新闻过滤器

避免与 20A - 20N 冲突。

⸻

16. P2 修复：字段 typo

16.1 问题说明

趋势转换信号 JSON 示例中存在错误日期：

"created_at": "2020G-01-01T00:00:00Z"

⸻

16.2 修复

改为：

"created_at": "2026-01-01T00:00:00Z"

⸻

17. P2 修复：工程目录补充趋势转换模块

17.1 问题说明

原工程目录中策略模块包含：

pullback_strategy.py
breakout_confirm.py

但没有趋势转换模块文件。

⸻

17.2 修复后的目录

将策略目录修改为：

strategy/
├── trend_detector.py
├── volatility_detector.py
├── signal_engine.py
├── pullback_strategy.py
├── breakout_confirm.py
├── reversal_strategy.py
├── reversal_detector.py
└── reversal_score.py

说明：

文件	职责
reversal_strategy.py	趋势转换试仓主策略
reversal_detector.py	检测 4H / 1H / 15M 反转结构
reversal_score.py	计算趋势转换评分

⸻

18. 新增配置总览

建议统一新增以下配置：

execution:
  position_mode: ONE_WAY
  margin_type: ISOLATED
reversal_strategy:
  enabled: true
  position:
    min_multiplier: 0.20
    default_multiplier: 0.30
    max_multiplier: 0.50
    max_loss_per_trade_pct: 0.003
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
  take_profit:
    tp1_rr: 1.0
    tp1_close_pct: 0.30
    tp2_close_pct: 0.30
    tp3_rr: 3.0
    tp3_close_pct: 0.40
    require_tp3_direction_check: true
    move_to_break_even_after_tp1: true
  time_stop:
    max_bars_to_0_5r: 8
    max_bars_to_1r: 12
  cooldown:
    symbol_cooldown_after_loss_minutes: 180
    max_consecutive_reversal_losses: 2
    global_cooldown_minutes: 720
  filters:
    require_ai_not_block: true
    require_funding_not_block: true
    require_atr_not_extreme: true
    require_volume_confirm: true
stop_order_guard:
  enabled: true
  check_interval_seconds: 5
  max_repair_attempts: 3
  close_position_if_repair_failed: true
liquidation_guard:
  enabled: true
  liquidation_buffer_pct: 0.01
  reject_if_stop_too_close_to_liquidation: true
backtest:
  maker_fee_rate: 0.0002
  taker_fee_rate: 0.0005
  market_order_slippage_pct: 0.0005
  stop_slippage_pct: 0.0005
  extreme_stop_slippage_pct: 0.002
  conservative_same_bar_execution: true

⸻

19. 修复优先级

19.1 P0：必须立即修复

1. 趋势转换仓位计算；
2. 趋势转换止损公式；
3. TRANSITION 与趋势转换模块冲突；
4. 止损订单存在性检查；
5. 强平价与保证金检查。

这些问题如果不修，后续开发容易出现实盘风险。

⸻

19.2 P1：强烈建议修复

1. 信号生成顺序；
2. ADX 增加 DI+ / DI-；
3. 多周期数据对齐；
4. 持仓模式与保证金模式；
5. 趋势转换信号分级；
6. 禁止追涨追跌；
7. TP3 方向校验；
8. 回测真实撮合补充。

这些问题会影响回测可信度和策略稳定性。

⸻

19.3 P2：建议修复

1. 文档编号；
2. typo；
3. 工程目录补充 reversal 模块。

这些问题主要影响文档清晰度和开发一致性。

⸻

20. 最终验收标准

完成本补丁后，PRD 至少应满足：

1. 趋势转换仓位不会超过 0.3% 账户风险；
2. 趋势转换仓位不会超过主策略标准仓位 50%；
3. 趋势转换止损不会默认取最宽止损；
4. 4H / 1H 冲突时，主策略等待，但趋势转换模块可继续评估；
5. 已有持仓退出优先于新开仓；
6. ADX 必须配合 DI+ / DI- 判断趋势方向；
7. 实盘持仓必须持续检查止损订单；
8. 下单前必须检查强平价和保证金安全；
9. 系统默认使用 ONE_WAY + ISOLATED；
10. 多周期信号只能使用已收盘 K 线；
11. 回测必须包含手续费、滑点、资金费率和交易所规则；
12. 趋势转换模块必须单独统计回测表现。

⸻

21. 结论

本补丁不改变原 PRD 的核心策略方向。

原核心仍然是：

多周期趋势 + 回踩入场 + ATR 风控 + AI 新闻过滤

本补丁增强的是：

1. 趋势转换试仓的安全性；
2. V 型反转捕捉能力；
3. 实盘订单保护；
4. 回测可信度；
5. 风控一致性。

修复完成后，策略框架会更适合以下交易目标：

在大周期趋势框架下，
不盲目逆势，
但也不完全错过 1H / 15M 的明确 V 型反转，
通过小仓位、严格止损、分批止盈提升整体收益弹性。