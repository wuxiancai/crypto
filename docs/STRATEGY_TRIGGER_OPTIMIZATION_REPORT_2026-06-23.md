# 策略触发条件优化回测报告（2026-06-23）

## 结论

本次只比较同一数据窗口，不再混用 1 年和 2 年收益。窗口为 `2025-06-22 15:59:59 UTC+8` 到 `2026-06-22 15:59:59 UTC+8`，数据来自 Ubuntu PostgreSQL `crypto_quant`，回测结果已归档到远端库。

当前最优组合是：

- `BTCUSDT EMA18 / MA40, ATR12, DMI12, Swing20, fee/risk=0, TRAILING`
- 触发条件：`ZoneATR=1`，`CloseBeyondMA=False`，`Reversal=False`
- Ubuntu DB run_id：`312` / 复测 run_id：`323`
- 最终权益：`1473.15`
- 净收益：`473.15`
- 胜率：`44.67%`
- 平均盈利 / 平均亏损：`13.4267 / 6.4992`
- 盈亏比：`2.07`
- Profit Factor：`1.67`

关键结论：当前策略族不是高胜率策略，而是低于 50% 胜率、依赖约 2 倍盈亏比赚钱。全库 1 年、交易数不少于 50 的回测里，最高胜率为 `46.72%`，没有达到 60%。如果目标必须是胜率超过 60%，不能只调均线/ATR/DMI 或红框的 EMA 区域，需要新增更强的趋势质量过滤或改变出场逻辑。

## 已保存原策略

已保存修改前策略快照：

- `docs/strategy_snapshots/2026-06-23-pre-trigger-filter/`
- 校验文件：`docs/strategy_snapshots/2026-06-23-pre-trigger-filter/SHA256SUMS`
- 恢复脚本：`scripts/restore_strategy_snapshot.sh`

恢复命令：

```bash
scripts/restore_strategy_snapshot.sh
```

也可以指定快照名：

```bash
scripts/restore_strategy_snapshot.sh 2026-06-23-pre-trigger-filter
```

## 本次策略修改

新增三个可回测触发参数：

- `pullback_zone_atr_multiplier`：快线区域 ATR 倍数，默认 `1`，用于控制“回踩/反弹到快线区域”的宽度。
- `require_pullback_close_beyond_fast_ma`：是否要求收盘重新回到快线方向侧。做多要求 `close >= fast_ma`，做空要求 `close <= fast_ma`。
- `enable_reversal_probe`：是否启用趋势转换试仓 `REVERSAL_PROBE`。

这些参数已经接入：

- 实时策略适配器
- 策略回测配置
- 批量回测脚本
- `/backtest/batch` 页面表单
- 数据库配置归档 payload

## 红框触发条件判断

截图红框中的“15m 反弹到 EMA50 区域”本质上是避免追空：价格必须反弹触达快线附近，再出现 15m 看跌确认，才允许主趋势做空。

原逻辑并不是严格的“收盘在 EMA50 下方”，而是：

- 做多：`low <= fast_ma + ATR` 且 `close >= fast_ma - ATR`
- 做空：`high >= fast_ma - ATR` 且 `close <= fast_ma + ATR`

它允许 K 线只要进入快线附近的 ATR 区域就触发，因此覆盖面偏宽。但本次回测显示，简单收紧成 `close` 必须回到快线方向侧并没有改善结果，反而降低收益。

## 触发条件网格回测

基准组合固定为 `EMA18/MA40 ATR12 DMI12 Swing20 Fee/Risk=0 TRAILING`，只改变触发条件。

| run_id | ZoneATR | CloseBeyondMA | Reversal | 最终权益 | 胜率 | 盈亏比 | PF | 交易数 |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 312 | 1 | False | False | 1473.15 | 44.67% | 2.07 | 1.67 | 197 |
| 316 | 0.75 | False | False | 1422.34 | 44.23% | 2.00 | 1.58 | 208 |
| 311 | 1 | False | True | 1420.19 | 42.79% | 2.09 | 1.56 | 208 |
| 315 | 0.75 | False | True | 1374.75 | 42.66% | 2.01 | 1.49 | 218 |
| 320 | 0.5 | False | False | 1354.88 | 43.61% | 1.86 | 1.44 | 227 |
| 314 | 1 | True | False | 1347.83 | 43.33% | 2.02 | 1.54 | 180 |
| 322 | 0.5 | True | False | 1317.16 | 43.14% | 1.89 | 1.44 | 204 |
| 319 | 0.5 | False | True | 1309.55 | 42.19% | 1.88 | 1.37 | 237 |
| 318 | 0.75 | True | False | 1303.21 | 42.63% | 1.95 | 1.45 | 190 |
| 313 | 1 | True | True | 1299.38 | 41.36% | 2.05 | 1.44 | 191 |
| 321 | 0.5 | True | True | 1273.09 | 41.59% | 1.91 | 1.36 | 214 |
| 317 | 0.75 | True | True | 1259.61 | 41.00% | 1.97 | 1.37 | 200 |

判断：

- `REVERSAL_PROBE` 明显拖累结果。关闭后，基准从 `1420.19` 提升到 `1473.15`，胜率从 `42.79%` 提升到 `44.67%`。
- `CloseBeyondMA=True` 不是有效优化。它减少交易数，但收益、胜率、PF 都下降。
- `ZoneATR` 缩小到 `0.75` 或 `0.5` 没有改善。`0.5` 反而交易数增加、平均盈利下降，说明当前穿刺快线后的确认逻辑不是越窄越好。

## 均线组合复测

使用最佳触发条件 `ZoneATR=1, CloseBeyondMA=False, Reversal=False` 复测前几名组合，并对比 `TRAILING/FIXED`。

| run_id | 组合 | TP | 最终权益 | 胜率 | 盈亏比 | PF | 交易数 |
|---:|---|---|---:|---:|---:|---:|---:|
| 323 | EMA18/MA40 ATR12 DMI12 Swing20 | TRAILING | 1473.15 | 44.67% | 2.07 | 1.67 | 197 |
| 327 | EMA15/MA60 ATR12 DMI14 Swing20 | TRAILING | 1326.68 | 45.95% | 1.94 | 1.65 | 148 |
| 325 | EMA15/MA90 ATR12 DMI14 Swing20 | TRAILING | 1312.64 | 46.06% | 1.80 | 1.54 | 165 |
| 329 | EMA15/MA90 ATR12 DMI12 Swing30 | TRAILING | 1223.69 | 44.44% | 1.93 | 1.54 | 126 |
| 324 | EMA18/MA40 ATR12 DMI12 Swing20 | FIXED | 1219.14 | 44.28% | 1.67 | 1.33 | 201 |
| 328 | EMA15/MA60 ATR12 DMI14 Swing20 | FIXED | 1211.29 | 46.31% | 1.66 | 1.43 | 149 |
| 326 | EMA15/MA90 ATR12 DMI14 Swing20 | FIXED | 1182.43 | 44.51% | 1.65 | 1.33 | 164 |
| 330 | EMA15/MA90 ATR12 DMI12 Swing30 | FIXED | 1176.27 | 44.72% | 1.79 | 1.45 | 123 |

判断：

- `TRAILING` 明显优于 `FIXED`，固定止盈没有提升胜率，也显著压低盈亏比。
- `EMA15/MA90` 和 `EMA15/MA60` 胜率略高，但收益低于 `EMA18/MA40`。
- 当前最优不是最高胜率组合，而是收益、盈亏比、PF 更均衡的 `EMA18/MA40`。

## 不合理点

1. `REVERSAL_PROBE` 和主趋势回踩混在一个交易系统里，质量差异很大。趋势转换试仓胜率低、净收益差，会拖累主趋势策略。
2. 红框 EMA 区域条件过宽的问题存在，但简单缩窄 ATR 区域或强制收盘站回快线，并没有提升结果。
3. 固定止盈没有把胜率推高，反而压低盈亏比，说明当前策略收益主要来自让盈利单继续跑。
4. 页面文案仍应继续修正：“EMA50 区域”应该动态显示为当前快线，例如 `EMA18 区域`，否则容易误解。
5. 当前策略族最高胜率离 60% 很远，说明入场过滤还不够强，不能靠参数微调承诺 60% 胜率。

## 推荐后续优化组合

优先级从高到低：

1. 默认关闭 `REVERSAL_PROBE`，只回测/运行 `TREND_PULLBACK only`。
2. 保留 `ZoneATR=1` 和 `CloseBeyondMA=False`，不要把本次失败的 strict close 作为默认。
3. 新增趋势强度过滤：例如 `ADX >= 25` 或 `DI gap >= 8/10`，目标是减少横盘假回踩。
4. 新增 15m 拒绝 K 线质量过滤：做空要求上影线占比、实体方向、收盘位置更靠近低点；做多对称处理。
5. 分 LONG/SHORT 单独回测。之前拆分显示 SHORT 对 BTCUSDT 更强，应允许只做优势方向。
6. 若必须追求 60% 胜率，另开一组“高胜率模式”：更近止盈、更宽止损、更严格趋势过滤。但这可能牺牲盈亏比和最终收益，必须单独和收益最优模式比较。

## 建议默认参数

短期建议上线/继续回测的默认组合：

```text
symbol = BTCUSDT
fast_ma = EMA18
slow_ma = MA40
atr_period = 12
dmi_period = 12
swing_lookback = 20
max_fee_to_risk_ratio = 0
trend_pullback_take_profit_mode = TRAILING
pullback_zone_atr_multiplier = 1
require_pullback_close_beyond_fast_ma = false
enable_reversal_probe = false
```

下一轮待验证组合：

```text
EMA18/MA40 + TREND_PULLBACK only + ADX >= 25
EMA18/MA40 + TREND_PULLBACK only + DI gap >= 8
EMA18/MA40 + TREND_PULLBACK only + 15m rejection candle quality
EMA18/MA40 + SHORT only
EMA15/MA60 + TREND_PULLBACK only + ADX/DI gap
```

## 验证命令

已通过：

```bash
.venv/bin/python -m pytest tests/test_v0_2_pullback_strategy.py \
  tests/test_v1_0_strategy_backtest_runner.py::test_strategy_backtest_defaults_to_perpetual_contract_costs \
  tests/test_v1_0_strategy_backtest_runner.py::test_strategy_backtest_config_passes_trigger_options_to_realtime_config \
  tests/test_v1_0_strategy_backtest_runner.py::test_archives_strategy_backtest_result_to_database \
  tests/test_v1_0_strategy_backtest_runner.py::test_strategy_backtest_batch_config_builds_user_selected_parameter_sets \
  tests/test_v1_0_strategy_backtest_runner.py::test_strategy_backtest_batch_primary_candidates_honor_single_dmi_input \
  tests/test_v1_0_strategy_backtest_runner.py::test_strategy_backtest_batch_query_defaults_match_page_defaults \
  tests/test_v1_0_strategy_backtest_page.py::test_strategy_backtest_batch_page_shows_all_script_parameters \
  tests/test_v1_0_strategy_backtest_page.py::test_strategy_backtest_batch_page_defaults_to_smaller_refinement_grid -q
```

结果：`14 passed`

备注：本机访问 Binance REST 返回 HTTP 451，因此本次真实回测没有依赖 Binance 外部接口，而是直接从 Ubuntu PostgreSQL 抽取 K 线到本地 cache 后执行同一回测引擎。
