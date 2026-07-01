# Independent Timeline Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `WEEKLY / DAILY / H4` 改为三条独立时间线策略，并让 Paper、Backtest、Web 状态页和复盘按 `trade_policy.md` 执行。

**Architecture:** 保留 `WEEKLY_DAILY_H4_V1` 内核名，但拆分周线、日线、4H 独立评估函数。交易层允许不同时间线反向共存，同一时间线只禁止反向仓，允许同方向追加仓位。

**Tech Stack:** Python 3.11、pytest、现有 `app.strategy`、`app.paper`、PostgreSQL 归档模型。

---

## Files

- Create / maintain: `trade_policy.md`
- Modify: `app/strategy/weekly_daily_h4_strategy.py`
- Modify: `app/paper/strategy_adapter.py`
- Modify: `app/paper/trading.py`
- Modify: `app/paper/live_runner.py`
- Modify: `app/paper/strategy_backtest.py`
- Modify: `app/paper/web_status.py`
- Modify tests under `tests/test_v2_0_*.py`
- Modify docs: `docs/TASKS.md`, `docs/HANDOFF.md`, `docs/DECISIONS.md`

## Task 1: Lock Policy Document

**Files:**
- Verify: `trade_policy.md`
- Modify: `docs/DECISIONS.md`
- Modify: `docs/TASKS.md`

- [ ] Confirm `trade_policy.md` states:
  - Three timelines only: `WEEKLY / DAILY / H4`.
  - Different timelines may hold opposite directions.
  - Same timeline rejects opposite direction.
  - Same timeline same direction may add positions.
  - Upper timeline direction affects classification and risk budget, not entry permission.

- [ ] Add a decision to `docs/DECISIONS.md` that `trade_policy.md` is the source of truth for current timeline policy.

- [ ] Commit:

```bash
git add trade_policy.md docs/DECISIONS.md docs/TASKS.md
git commit -m "Document independent timeline trade policy"
```

## Task 2: Refactor Strategy Decisions Into Independent Timeline Evaluators

**Files:**
- Modify: `app/strategy/weekly_daily_h4_strategy.py`
- Test: `tests/test_v2_0_weekly_daily_h4_strategy.py`

- [ ] Add failing tests:
  - `test_weekly_signal_uses_weekly_only_without_daily_confirmation`
  - `test_daily_short_under_weekly_bull_is_rebound_short_not_blocked`
  - `test_h4_long_under_daily_bear_is_rebound_long_not_blocked`

- [ ] Implement:
  - `evaluate_weekly_strategy(strategy_input, config, control_state)`
  - `evaluate_daily_strategy(strategy_input, config, weekly_regime, control_state)`
  - `evaluate_h4_strategy(strategy_input, config, daily_regime, control_state)`

- [ ] Ensure weekly entry only checks weekly bullish / bearish conditions.

- [ ] Ensure daily entry only checks daily bullish / bearish conditions and uses weekly regime only to classify `TREND / REBOUND / NEUTRAL`.

- [ ] Ensure h4 entry only checks h4 bullish / bearish plus 4H BOLL / breakout / continuation conditions and uses daily regime only to classify `TREND / REBOUND / NEUTRAL`.

- [ ] Run:

```bash
.venv/bin/python -m pytest tests/test_v2_0_weekly_daily_h4_strategy.py -q
```

- [ ] Commit:

```bash
git add app/strategy/weekly_daily_h4_strategy.py tests/test_v2_0_weekly_daily_h4_strategy.py
git commit -m "Make weekly daily h4 strategies independent"
```

## Task 3: Allow Same Timeline Same Direction Adds

**Files:**
- Modify: `app/paper/trading.py`
- Test: `tests/test_v2_0_paper_weekly_daily_h4_kernel.py`

- [ ] Add failing tests:
  - `test_same_level_opposite_direction_is_rejected`
  - `test_same_level_same_direction_adds_position`
  - `test_different_levels_opposite_directions_can_coexist`

- [ ] Update `_has_conflicting_position()`:
  - Same symbol + same kernel + same position_level + opposite side returns `True`.
  - Same symbol + same kernel + same position_level + same side returns `False`.
  - Different position_level returns `False`.

- [ ] Keep legacy bucket conflict behavior unchanged for signals without `position_level`.

- [ ] Run:

```bash
.venv/bin/python -m pytest tests/test_v2_0_paper_weekly_daily_h4_kernel.py -q
```

- [ ] Commit:

```bash
git add app/paper/trading.py tests/test_v2_0_paper_weekly_daily_h4_kernel.py
git commit -m "Allow same timeline same direction adds"
```

## Task 4: Gate Execution By Event Timeframe

**Files:**
- Modify: `app/paper/live_runner.py`
- Modify: `app/paper/strategy_backtest.py`
- Test: `tests/test_v2_0_weekly_daily_h4_adapter.py`
- Test: `tests/test_v2_0_backtest_weekly_daily_h4_adaptation.py`

- [ ] Ensure weekly actions only execute on `1w` closed K line events.

- [ ] Ensure daily actions only execute on `1d` closed K line events.

- [ ] Ensure H4 actions only execute on `4h` closed K line events.

- [ ] Keep all timelines available as context for classification.

- [ ] Run:

```bash
.venv/bin/python -m pytest tests/test_v2_0_weekly_daily_h4_adapter.py tests/test_v2_0_backtest_weekly_daily_h4_adaptation.py -q
```

- [ ] Commit:

```bash
git add app/paper/live_runner.py app/paper/strategy_backtest.py tests/test_v2_0_weekly_daily_h4_adapter.py tests/test_v2_0_backtest_weekly_daily_h4_adaptation.py
git commit -m "Execute timeline signals only on matching kline events"
```

## Task 5: Update Web Status And Replay Labels

**Files:**
- Modify: `app/paper/web_status.py`
- Test: current Web status tests or create focused tests if archived.

- [ ] Show timeline, direction, trade mode, and risk-budget class for each open position.

- [ ] Rename ambiguous text:
  - Use “结构风险较低 / 风险预算较高” for aligned trades.
  - Use “结构风险较高 / 风险预算较低” for rebound trades.

- [ ] Ensure replay events retain `position_level`, `trade_mode`, `market_regime`, and risk budget.

- [ ] Run relevant Web tests and focused render tests.

- [ ] Commit:

```bash
git add app/paper/web_status.py tests
git commit -m "Show independent timeline policy in paper status"
```

## Task 6: Full Verification

**Files:**
- Modify: `docs/HANDOFF.md`
- Modify: `docs/TASKS.md`

- [ ] Run:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m py_compile app/strategy/weekly_daily_h4_strategy.py app/paper/strategy_adapter.py app/paper/trading.py app/paper/live_runner.py app/paper/strategy_backtest.py app/paper/web_status.py
git diff --check
```

- [ ] Run at least one real-data smoke if Binance is reachable:

```bash
.venv/bin/python scripts/sync_klines.py --symbols BTCUSDT --intervals 1w 1d 4h --limit 120
```

- [ ] Update `docs/HANDOFF.md` with actual verification results.

- [ ] Update `docs/TASKS.md` with completed checklist items.

- [ ] Commit:

```bash
git add docs/HANDOFF.md docs/TASKS.md
git commit -m "Record independent timeline strategy verification"
```
