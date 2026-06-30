# Weekly Daily H4 Strategy Core Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the existing strategy core strictly according to `交易逻辑优化.md`, replacing the old daily/4h/1h/15m strategy semantics with a clean `WEEKLY / DAILY / H4` position hierarchy without mixing old and new kernel meanings.

**Architecture:** Keep the existing data, Paper, Backtest, persistence, risk, event, and Web foundations. Add a new versioned strategy kernel `WEEKLY_DAILY_H4_V1` beside the current layered kernel, route Paper/Backtest/Web through an explicit kernel selector, validate the new kernel in parallel, then switch defaults only after evidence passes.

**Tech Stack:** Python dataclasses, Decimal, PostgreSQL/Alembic, pytest, Binance USD-M Futures closed Klines, existing PaperTradingEngine, existing strategy backtest runner, existing Web status renderer.

---

## 0. Non-Negotiable Migration Rules

This section is the safety rail for the whole upgrade. Do not start code changes before these rules are reflected in tests and docs.

1. `交易逻辑优化.md` is the source of truth for new strategy semantics.
2. Do not rewrite the whole system. Reuse the existing Paper, Backtest, data sync, risk, persistence, runtime events, and Web status foundations.
3. Do not treat old buckets as new levels:
   - `DAY_CORE` is not `WEEKLY`.
   - `FOUR_HOUR_ADDON` is not `DAILY`.
   - `FOUR_HOUR_HEDGE` is not `H4`.
4. New canonical fields must exist before behavior migration:
   - `strategy_kernel`
   - `position_level`
   - `trade_mode`
   - `market_regime`
   - `lifecycle_state`
5. Old fields may remain only for compatibility:
   - `strategy_type`
   - `bucket`
   - `open_position`
6. A single Paper or Backtest run must use one kernel only:
   - `LAYERED_DAILY_V1`
   - or `WEEKLY_DAILY_H4_V1`
   - never both in the same run.
7. New kernel default stays disabled until the parallel validation gate passes.
8. First version scope remains Paper + Backtest + Web status. Do not start Live/testnet/real order work.
9. Every implementation task must include tests before default behavior is changed.
10. Any uncertain state must produce `WAIT` / reject new entries, not a best-effort trade.

## 1. Target Semantics From `交易逻辑优化.md`

The new kernel has exactly three position levels:

```text
WEEKLY = 周线仓
DAILY  = 日线仓
H4     = 4H 仓
```

The new kernel has trade modes as attributes, not extra position classes:

```text
TREND
REBOUND
BREAKOUT
PULLBACK
CONTINUATION
```

The new control layers do not create positions:

```text
Regime Tagging
Throttle
Signal Score
Lifecycle
Equity Guard
```

The priority chain must be implemented in this order:

```text
account risk
> liquidation risk
> hard stop
> equity guard
> weekly forced exit
> weekly staged reduction
> lifecycle progression
> throttle
> daily exits
> daily rebound/trend mutual exclusion
> H4 no-trade filter
> new entries
```

## 2. File Structure

Create:

- `app/strategy/position_hierarchy.py`
  Canonical enums and dataclasses for the new kernel. This file owns level, mode, regime, lifecycle, score, throttle, and kernel version names.
- `app/strategy/weekly_daily_h4_strategy.py`
  Pure strategy decision engine for `WEEKLY_DAILY_H4_V1`. It must not call PaperTradingEngine and must not write files or database rows.
- `app/strategy/trade_controls.py`
  Regime Tagging, Throttle, Signal Score, Lifecycle, and Equity Guard pure functions used by the new kernel.
- `tests/test_v2_0_position_hierarchy_contract.py`
  Contract tests proving old and new semantics are not mixed.
- `tests/test_v2_0_weekly_daily_h4_strategy.py`
  Unit tests for weekly, daily, and H4 decisions.
- `tests/test_v2_0_trade_controls.py`
  Unit tests for Regime, Throttle, Signal Score, Lifecycle, and Equity Guard.
- `tests/test_v2_0_weekly_daily_h4_adapter.py`
  Adapter tests proving Paper/Backtest select exactly one kernel.

Modify:

- `app/data/quality.py`
  Ensure `INTERVAL_MS` supports `1w` if not already present.
- `scripts/sync_klines.py`
  Include `1w` in sync defaults only after tests prove Binance fetch and persistence support it.
- `scripts/start.sh`
  Include `1w` in startup sync and realtime warmup only after new kernel can run in diagnostic mode.
- `app/paper/multitimeframe.py`
  Allow required intervals to include `1w`.
- `app/paper/strategy_adapter.py`
  Add explicit kernel selector. Do not reuse `enable_layered_strategy` as the new switch.
- `app/paper/live_runner.py`
  Keep current default until cutover gate; add config plumbing for the new kernel.
- `app/paper/strategy_backtest.py`
  Add backtest config field `strategy_kernel` and fetch intervals `1w / 1d / 4h / 15m` for the new kernel.
- `app/paper/trading.py`
  Add position identity fields and partial reduction support. Preserve old state loading.
- `app/paper/persistence.py`
  Serialize and deserialize new fields with old-state defaults.
- `app/database/models.py`
  Add queryable metadata columns only if event payload is not enough for status/backtest comparison.
- `app/database/repositories.py`
  Persist new metadata if columns are added.
- `app/paper/web_status.py`
  Display kernel, level, mode, lifecycle, score, and controls without using old bucket labels as new truth.
- `docs/PROJECT_CONTEXT.md`
  Mark old daily layered kernel as legacy and new `WEEKLY_DAILY_H4_V1` as next strategy mainline after cutover.
- `docs/DECISIONS.md`
  Add a new decision that supersedes old D2/D5 only for `WEEKLY_DAILY_H4_V1`.
- `docs/TASKS.md`
  Track implementation phases and validation gates.
- `docs/HANDOFF.md`
  Record current migration status after each task.

Do not modify:

- Live trading adapters, testnet adapters, or real order execution. They remain out of first-version scope.

## 3. Task 0: Freeze The Upgrade Contract

**Files:**

- Modify: `docs/DECISIONS.md`
- Modify: `docs/PROJECT_CONTEXT.md`
- Modify: `docs/TASKS.md`
- Modify: `docs/HANDOFF.md`

- [ ] Step 1: Add a decision named `D15. WEEKLY_DAILY_H4_V1 supersedes old layered strategy after validation`.

Decision content must say:

```markdown
### D15. WEEKLY_DAILY_H4_V1 是下一代策略内核

`交易逻辑优化.md` 是新版策略内核的需求源。新版内核命名为 `WEEKLY_DAILY_H4_V1`，仓位层级只允许 `WEEKLY / DAILY / H4`。

旧 `LAYERED_DAILY_V1` 继续作为兼容内核保留，直到新版内核通过并行回测与 Paper 诊断验证。禁止把 `DAY_CORE / FOUR_HOUR_ADDON / FOUR_HOUR_HEDGE` 直接解释为新版 `WEEKLY / DAILY / H4`。

同一次 Paper 或 Backtest 运行只能启用一个策略内核。新版内核切为默认前，必须完成文档、单测、回测对照、状态页展示和 Handoff 更新。
```

- [ ] Step 2: Update project context.

Add this sentence to `docs/PROJECT_CONTEXT.md`:

```markdown
下一代策略内核为 `WEEKLY_DAILY_H4_V1`：周线决定大环境和周线仓，日线在周线环境下做互斥的反弹或顺势仓，4H 只做严格执行与 breakout/pullback/continuation。
```

- [ ] Step 3: Run docs-only checks.

Run:

```bash
git diff --check
```

Expected: no trailing whitespace errors.

- [ ] Step 4: Commit.

```bash
git add docs/DECISIONS.md docs/PROJECT_CONTEXT.md docs/TASKS.md docs/HANDOFF.md
git commit -m "docs: freeze weekly daily h4 strategy upgrade contract"
```

## 4. Task 1: Add Canonical Position Hierarchy Contracts

**Files:**

- Create: `app/strategy/position_hierarchy.py`
- Create: `tests/test_v2_0_position_hierarchy_contract.py`

- [ ] Step 1: Write failing tests for canonical names.

Required assertions:

```python
def test_position_levels_are_only_weekly_daily_h4():
    from app.strategy.position_hierarchy import PositionLevel

    assert [item.value for item in PositionLevel] == ["WEEKLY", "DAILY", "H4"]


def test_trade_modes_are_attributes_not_position_levels():
    from app.strategy.position_hierarchy import PositionLevel, TradeMode

    assert "BREAKOUT" not in [item.value for item in PositionLevel]
    assert TradeMode.BREAKOUT.value == "BREAKOUT"


def test_legacy_buckets_are_not_canonical_levels():
    from app.strategy.position_hierarchy import legacy_bucket_to_position_level

    assert legacy_bucket_to_position_level("DAY_CORE") is None
    assert legacy_bucket_to_position_level("FOUR_HOUR_ADDON") is None
    assert legacy_bucket_to_position_level("FOUR_HOUR_HEDGE") is None
```

- [ ] Step 2: Run tests to verify failure.

```bash
.venv/bin/python -m pytest tests/test_v2_0_position_hierarchy_contract.py -q
```

Expected: fail because module does not exist.

- [ ] Step 3: Implement `position_hierarchy.py`.

Minimum required objects:

```python
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum


class StrategyKernel(str, Enum):
    LAYERED_DAILY_V1 = "LAYERED_DAILY_V1"
    WEEKLY_DAILY_H4_V1 = "WEEKLY_DAILY_H4_V1"


class PositionLevel(str, Enum):
    WEEKLY = "WEEKLY"
    DAILY = "DAILY"
    H4 = "H4"


class TradeMode(str, Enum):
    TREND = "TREND"
    REBOUND = "REBOUND"
    BREAKOUT = "BREAKOUT"
    PULLBACK = "PULLBACK"
    CONTINUATION = "CONTINUATION"


class MarketRegime(str, Enum):
    TREND = "TREND"
    RANGE = "RANGE"
    TRANSITION = "TRANSITION"
    BREAKOUT = "BREAKOUT"
    EXHAUSTION = "EXHAUSTION"
    UNKNOWN = "UNKNOWN"


class LifecycleState(str, Enum):
    OPENED = "OPENED"
    CONFIRMED = "CONFIRMED"
    PROTECTED = "PROTECTED"
    PROFIT_LOCKED = "PROFIT_LOCKED"
    REDUCED = "REDUCED"
    EXITED = "EXITED"


@dataclass(frozen=True)
class HierarchySignalMeta:
    strategy_kernel: StrategyKernel
    position_level: PositionLevel
    trade_mode: TradeMode
    market_regime: MarketRegime = MarketRegime.UNKNOWN
    lifecycle_state: LifecycleState = LifecycleState.OPENED
    signal_score: Decimal | None = None
    controls: tuple[str, ...] = field(default_factory=tuple)


def legacy_bucket_to_position_level(bucket: str | None) -> PositionLevel | None:
    if bucket in {PositionLevel.WEEKLY.value, PositionLevel.DAILY.value, PositionLevel.H4.value}:
        return PositionLevel(bucket)
    return None
```

- [ ] Step 4: Run tests.

```bash
.venv/bin/python -m pytest tests/test_v2_0_position_hierarchy_contract.py -q
```

Expected: pass.

- [ ] Step 5: Commit.

```bash
git add app/strategy/position_hierarchy.py tests/test_v2_0_position_hierarchy_contract.py
git commit -m "feat: add weekly daily h4 hierarchy contracts"
```

## 5. Task 2: Add Weekly Closed-Kline Support Without Changing Strategy Behavior

**Files:**

- Modify: `app/data/quality.py`
- Modify: `scripts/sync_klines.py`
- Modify: `scripts/start.sh`
- Modify: `app/paper/multitimeframe.py`
- Modify: `tests/test_v1_1_sync_klines.py`
- Modify: `tests/test_v1_0_multitimeframe_cache.py`
- Modify: `tests/test_deploy_ports.py`

- [ ] Step 1: Write tests proving `1w` is supported.

Required expectations:

```python
assert INTERVAL_MS["1w"] == 7 * 24 * 60 * 60 * 1000
assert DEFAULT_SYNC_INTERVALS == ("1w", "1d", "4h", "15m")
assert "--intervals 5m 15m 4h 1d 1w" in start_script_content
```

- [ ] Step 2: Implement `1w` support.

Rules:

- `1w` must be treated as a closed Kline interval.
- Backtest replay order for same `close_time` must be `1w`, then `1d`, then `4h`, then `15m`.
- Do not add `1h` to the new kernel path unless a later requirement explicitly reintroduces it.
- Existing old-kernel tests may continue to expect `1h`; update only the tests that refer to default startup sync for the new kernel.

- [ ] Step 3: Run interval tests.

```bash
.venv/bin/python -m pytest tests/test_v1_1_sync_klines.py tests/test_v1_0_multitimeframe_cache.py tests/test_deploy_ports.py -q
```

Expected: pass.

- [ ] Step 4: Commit.

```bash
git add app/data/quality.py scripts/sync_klines.py scripts/start.sh app/paper/multitimeframe.py tests/test_v1_1_sync_klines.py tests/test_v1_0_multitimeframe_cache.py tests/test_deploy_ports.py
git commit -m "feat: support weekly closed kline data"
```

## 6. Task 3: Build Weekly Regime And Weekly Position Rules

**Files:**

- Create: `app/strategy/weekly_daily_h4_strategy.py`
- Create: `tests/test_v2_0_weekly_daily_h4_strategy.py`

- [ ] Step 1: Write tests for weekly short entry.

Required behavior:

- Weekly `EMA15 < MA60`.
- Daily `EMA15 < MA60`.
- Output opens `WEEKLY` short trend position.
- Risk budget level is at least 60% of strategy budget.
- Signal metadata includes `strategy_kernel=WEEKLY_DAILY_H4_V1`.

- [ ] Step 2: Write tests for weekly long entry.

Mirror the short test:

- Weekly `EMA15 > MA60`.
- Daily `EMA15 > MA60`.
- Output opens `WEEKLY` long trend position.

- [ ] Step 3: Write tests for weekly staged reductions.

Required behavior:

```text
weekly close above MA60 under weekly short:
    REDUCE WEEKLY 30%-50%

weekly structure high close-break under weekly short:
    REDUCE WEEKLY 30%-50%

weekly bearish momentum decay:
    stop adding WEEKLY
    REDUCE WEEKLY 20%-30%

weekly golden cross under weekly short:
    CLOSE WEEKLY remainder
```

Long side must be symmetric.

- [ ] Step 4: Implement minimum pure decision engine.

Required public API:

```python
@dataclass(frozen=True)
class WeeklyDailyH4Config:
    fast_period: int = 15
    slow_period: int = 60
    weekly_budget_floor_pct: Decimal = Decimal("0.60")
    daily_budget_floor_pct: Decimal = Decimal("0.30")
    h4_budget_cap_pct: Decimal = Decimal("0.10")
    weekly_trend_break_reduce_pct: Decimal = Decimal("0.40")
    weekly_structure_break_reduce_pct: Decimal = Decimal("0.40")
    weekly_momentum_break_reduce_pct: Decimal = Decimal("0.25")


def build_weekly_daily_h4_decision(
    strategy_input: WeeklyDailyH4Input,
    config: WeeklyDailyH4Config | None = None,
) -> WeeklyDailyH4Decision:
    raise NotImplementedError("Task 3 must replace this with the pure decision engine")
```

The implementation must return `WAIT` when data is missing or state is uncertain.

- [ ] Step 5: Run tests.

```bash
.venv/bin/python -m pytest tests/test_v2_0_weekly_daily_h4_strategy.py -q
```

Expected: pass.

- [ ] Step 6: Commit.

```bash
git add app/strategy/weekly_daily_h4_strategy.py tests/test_v2_0_weekly_daily_h4_strategy.py
git commit -m "feat: add weekly regime and weekly position rules"
```

## 7. Task 4: Add Position Lifecycle And Partial Reduction Support

**Files:**

- Modify: `app/paper/trading.py`
- Modify: `app/paper/persistence.py`
- Modify: `tests/test_v1_1_paper_strategy_buckets.py`
- Create: `tests/test_v2_0_weekly_position_lifecycle.py`

- [ ] Step 1: Add tests proving old state still loads.

Required behavior:

- A persisted old position without `strategy_kernel`, `position_level`, `trade_mode`, or `lifecycle_state` loads successfully.
- Loaded old position has `strategy_kernel=LAYERED_DAILY_V1`.
- Loaded old position does not pretend to be `WEEKLY`, `DAILY`, or `H4`.

- [ ] Step 2: Add tests for partial reduction.

Required behavior:

- `REDUCE_POSITION` reduces quantity by a requested fraction.
- Reduction creates a fill with `exit_reason=WEEKLY_TREND_BREAK_REDUCE`, `WEEKLY_STRUCTURE_BREAK_REDUCE`, or `WEEKLY_MOMENTUM_BREAK_REDUCE`.
- Remaining position keeps original `position_level=WEEKLY`.
- Full close creates `exit_reason=WEEKLY_FORCED_EXIT`.

- [ ] Step 3: Modify `PaperPosition`.

Add fields with compatibility defaults:

```python
strategy_kernel: str = "LAYERED_DAILY_V1"
position_level: str | None = None
trade_mode: str | None = None
lifecycle_state: str = "OPENED"
signal_score: Decimal | None = None
```

- [ ] Step 4: Add reduce handling in `PaperTradingEngine.on_signal`.

Rules:

- Reductions are allowed only for matching symbol and matching position identity.
- Reduction cannot increase risk.
- Reduction cannot produce negative or zero remaining quantity unless action is a full close.
- Existing hard stop, liquidation, kill switch, and max drawdown behavior must remain higher priority.

- [ ] Step 5: Run tests.

```bash
.venv/bin/python -m pytest tests/test_v1_1_paper_strategy_buckets.py tests/test_v2_0_weekly_position_lifecycle.py -q
```

Expected: pass.

- [ ] Step 6: Commit.

```bash
git add app/paper/trading.py app/paper/persistence.py tests/test_v1_1_paper_strategy_buckets.py tests/test_v2_0_weekly_position_lifecycle.py
git commit -m "feat: add hierarchy position lifecycle support"
```

## 8. Task 5: Implement Daily Rebound/Trend Mutual Exclusion

**Files:**

- Modify: `app/strategy/weekly_daily_h4_strategy.py`
- Modify: `app/paper/trading.py`
- Modify: `tests/test_v2_0_weekly_daily_h4_strategy.py`
- Create: `tests/test_v2_0_daily_mutual_exclusion.py`

- [ ] Step 1: Write tests for weekly short + daily rebound long.

Required behavior:

- Weekly short remains open.
- Daily golden cross or clear rebound structure allows one `DAILY LONG REBOUND`.
- The signal is not allowed when a `DAILY SHORT TREND` already exists.
- The signal must not close or convert the `WEEKLY SHORT`.

- [ ] Step 2: Write tests for daily rebound failure to daily trend.

Required behavior:

- If `DAILY LONG REBOUND` is open, no `DAILY SHORT TREND` can open.
- Rebound failure first exits `DAILY LONG REBOUND`.
- Only after that exit may the next eligible decision open `DAILY SHORT TREND`.

- [ ] Step 3: Mirror all tests for weekly long.

Required behavior:

- Weekly long + daily callback short is allowed as a daily rebound/counter-trend tactical position.
- Daily callback short and daily trend long are mutually exclusive.

- [ ] Step 4: Implement conflict policy.

Do not rely on old bucket conflict rules. The rule must inspect:

```text
strategy_kernel
symbol
position_level == DAILY
trade_mode in {REBOUND, TREND}
weekly_context
```

- [ ] Step 5: Run tests.

```bash
.venv/bin/python -m pytest tests/test_v2_0_weekly_daily_h4_strategy.py tests/test_v2_0_daily_mutual_exclusion.py -q
```

Expected: pass.

- [ ] Step 6: Commit.

```bash
git add app/strategy/weekly_daily_h4_strategy.py app/paper/trading.py tests/test_v2_0_weekly_daily_h4_strategy.py tests/test_v2_0_daily_mutual_exclusion.py
git commit -m "feat: enforce daily rebound trend mutual exclusion"
```

## 9. Task 6: Implement Strict H4 Breakout, Pullback, And Continuation

**Files:**

- Modify: `app/strategy/weekly_daily_h4_strategy.py`
- Modify: `tests/test_v2_0_weekly_daily_h4_strategy.py`
- Create: `tests/test_v2_0_h4_breakout_modes.py`

- [ ] Step 1: Write tests for H4 no-trade when BOLL is closed.

Required behavior:

- `H4` signal is rejected when BOLL width is contracting.
- Rejection reason contains `H4_BOLL_NOT_OPEN`.
- Weekly and Daily positions are not modified by H4 no-trade state.

- [ ] Step 2: Write tests for H4 breakout.

Required behavior:

- BOLL width expands.
- H4 close breaks recent structure high/low.
- Direction aligns with weekly or daily allowed bias.
- Entry is not overextended from structure by more than configured ATR.
- Output is `position_level=H4`, `trade_mode=BREAKOUT`, budget cap `<= 0.10`.

- [ ] Step 3: Write tests for H4 pullback.

Required behavior:

- A prior breakout has been confirmed.
- Retest holds the breakout zone.
- Output is `position_level=H4`, `trade_mode=PULLBACK`.

- [ ] Step 4: Write tests for H4 continuation.

Required behavior:

- BOLL remains open.
- Trend structure continues.
- Entry is not overextended.
- Output is `position_level=H4`, `trade_mode=CONTINUATION`.

- [ ] Step 5: Implement BOLL and structure logic.

Use existing Bollinger indicator outputs where possible. Do not implement new indicator math if `app/indicators/core.py` already provides the value.

- [ ] Step 6: Run tests.

```bash
.venv/bin/python -m pytest tests/test_v2_0_h4_breakout_modes.py tests/test_v2_0_weekly_daily_h4_strategy.py -q
```

Expected: pass.

- [ ] Step 7: Commit.

```bash
git add app/strategy/weekly_daily_h4_strategy.py tests/test_v2_0_weekly_daily_h4_strategy.py tests/test_v2_0_h4_breakout_modes.py
git commit -m "feat: add h4 breakout pullback continuation modes"
```

## 10. Task 7: Add Regime, Throttle, Signal Score, Lifecycle, Equity Guard

**Files:**

- Create: `app/strategy/trade_controls.py`
- Create: `tests/test_v2_0_trade_controls.py`
- Modify: `app/strategy/weekly_daily_h4_strategy.py`
- Modify: `app/paper/trading.py`

- [ ] Step 1: Write Regime Tagging tests.

Required states:

```text
TREND
RANGE
TRANSITION
BREAKOUT
EXHAUSTION
UNKNOWN
```

Required behavior:

- `UNKNOWN` blocks new entries.
- `RANGE` blocks chasing entries and H4 weak signals.
- `BREAKOUT` allows only qualified H4 breakout.
- `EXHAUSTION` blocks add-on risk and moves profitable positions toward protection.

- [ ] Step 2: Write Throttle tests.

Required behavior:

- Same symbol and level enters cooldown after close.
- Same direction pauses after N consecutive losses.
- Failed H4 breakout requires a new BOLL opening or new structure.
- Weekly reduction blocks immediate re-add.

- [ ] Step 3: Write Signal Score tests.

Required bands:

```text
score >= 80: standard budget
60 <= score < 80: allowed, no add
40 <= score < 60: reduced or wait
score < 40: reject
```

Score must never override hard stops, equity guard, throttle, or mutual exclusion.

- [ ] Step 4: Write Lifecycle tests.

Required transitions:

```text
OPENED -> CONFIRMED -> PROTECTED -> PROFIT_LOCKED -> REDUCED -> EXITED
```

Weekly, Daily, and H4 must use different progression rules.

- [ ] Step 5: Write Equity Guard tests.

Required behavior:

- Daily loss threshold blocks new entries.
- Weekly loss threshold blocks new entries and allows reductions.
- Drawdown from equity high lowers or blocks risk.
- Max drawdown allows only reduce/close.

- [ ] Step 6: Implement controls as pure functions.

No function in `trade_controls.py` may call database, Web, Paper persistence, or Binance.

- [ ] Step 7: Integrate controls into new strategy kernel and trading engine priority.

Priority must match `交易逻辑优化.md` section 12.

- [ ] Step 8: Run tests.

```bash
.venv/bin/python -m pytest tests/test_v2_0_trade_controls.py tests/test_v2_0_weekly_daily_h4_strategy.py -q
```

Expected: pass.

- [ ] Step 9: Commit.

```bash
git add app/strategy/trade_controls.py app/strategy/weekly_daily_h4_strategy.py app/paper/trading.py tests/test_v2_0_trade_controls.py tests/test_v2_0_weekly_daily_h4_strategy.py
git commit -m "feat: add trading control layers"
```

## 11. Task 8: Wire The New Kernel Through Adapter, Backtest, And Paper In Diagnostic Mode

**Files:**

- Modify: `app/paper/strategy_adapter.py`
- Modify: `app/paper/live_runner.py`
- Modify: `app/paper/strategy_backtest.py`
- Modify: `scripts/run_paper_realtime.py`
- Modify: `tests/test_v2_0_weekly_daily_h4_adapter.py`
- Modify: `tests/test_v1_0_strategy_backtest_runner.py`
- Modify: `tests/test_v1_0_real_market_paper_runner.py`

- [ ] Step 1: Add config selector.

Required API:

```python
strategy_kernel: str = "LAYERED_DAILY_V1"
```

Do not use `enable_layered_strategy` for the new kernel.

- [ ] Step 2: Add tests proving only one kernel runs.

Required behavior:

- `strategy_kernel=LAYERED_DAILY_V1` calls old `build_layered_strategy_decision`.
- `strategy_kernel=WEEKLY_DAILY_H4_V1` calls new `build_weekly_daily_h4_decision`.
- An unknown kernel returns `WAIT` with a clear reason.
- A single signal contains exactly one kernel identity.

- [ ] Step 3: Add diagnostic mode.

Diagnostic mode means:

- New kernel can compute diagnostics.
- It does not open positions by default in live Paper until cutover.
- Backtest may run new kernel explicitly by config.

- [ ] Step 4: Update backtest interval fetch.

For `WEEKLY_DAILY_H4_V1`, fetch:

```text
1w / 1d / 4h / 15m
```

For `LAYERED_DAILY_V1`, keep:

```text
1d / 4h / 1h / 15m
```

- [ ] Step 5: Run tests.

```bash
.venv/bin/python -m pytest tests/test_v2_0_weekly_daily_h4_adapter.py tests/test_v1_0_strategy_backtest_runner.py tests/test_v1_0_real_market_paper_runner.py -q
```

Expected: pass.

- [ ] Step 6: Commit.

```bash
git add app/paper/strategy_adapter.py app/paper/live_runner.py app/paper/strategy_backtest.py scripts/run_paper_realtime.py tests/test_v2_0_weekly_daily_h4_adapter.py tests/test_v1_0_strategy_backtest_runner.py tests/test_v1_0_real_market_paper_runner.py
git commit -m "feat: wire weekly daily h4 kernel in diagnostic mode"
```

## 12. Task 9: Update Persistence, Runtime Events, And Web Status

**Files:**

- Modify: `app/paper/persistence.py`
- Modify: `app/database/models.py`
- Modify: `app/database/repositories.py`
- Modify: `app/paper/web_status.py`
- Modify: `scripts/show_paper_runtime_events.py`
- Modify: `tests/test_v1_0_paper_persistence.py`
- Modify: `tests/test_v1_2_paper_runtime_events_cli.py`
- Modify: `tests/test_v1_2_paper_runtime_events_web.py`
- Modify: `tests/test_v1_0_paper_status_web.py`

- [ ] Step 1: Add tests for JSON persistence fields.

Required fields:

```json
{
  "strategy_kernel": "WEEKLY_DAILY_H4_V1",
  "position_level": "WEEKLY",
  "trade_mode": "TREND",
  "market_regime": "TREND",
  "lifecycle_state": "PROTECTED",
  "signal_score": "82"
}
```

Old JSON without these fields must load.

- [ ] Step 2: Add event display tests.

Web and CLI must show:

```text
Kernel
Level
Mode
Lifecycle
Score
Control blockers
```

They may still show old `strategy_type` and `bucket`, but not as the canonical new identity.

- [ ] Step 3: Add database columns only if needed.

If filtering by level/mode is needed, add nullable columns:

```text
strategy_kernel
position_level
trade_mode
lifecycle_state
signal_score
```

If payload-only is enough for this phase, do not add a migration.

- [ ] Step 4: Run tests.

```bash
.venv/bin/python -m pytest tests/test_v1_0_paper_persistence.py tests/test_v1_2_paper_runtime_events_cli.py tests/test_v1_2_paper_runtime_events_web.py tests/test_v1_0_paper_status_web.py -q
```

Expected: pass.

- [ ] Step 5: Commit.

```bash
git add app/paper/persistence.py app/database/models.py app/database/repositories.py app/paper/web_status.py scripts/show_paper_runtime_events.py tests/test_v1_0_paper_persistence.py tests/test_v1_2_paper_runtime_events_cli.py tests/test_v1_2_paper_runtime_events_web.py tests/test_v1_0_paper_status_web.py
git commit -m "feat: expose weekly daily h4 runtime metadata"
```

## 13. Task 10: Parallel Backtest Validation Before Default Cutover

**Files:**

- Modify: `app/paper/strategy_backtest.py`
- Modify: `scripts/run_strategy_backtest_batch.py`
- Create: `scripts/compare_strategy_kernels.py`
- Create: `tests/test_v2_0_strategy_kernel_comparison.py`
- Modify: `docs/TASKS.md`
- Modify: `docs/HANDOFF.md`

- [ ] Step 1: Add comparison script tests.

The script must compare the same symbol, date range, cost model, and initial equity across:

```text
LAYERED_DAILY_V1
WEEKLY_DAILY_H4_V1
```

Required output fields:

```text
kernel
symbol
history_period
final_equity
net_pnl
max_drawdown_pct
total_trades
win_rate
profit_loss_ratio
weekly_trades
daily_trades
h4_trades
```

- [ ] Step 2: Implement script.

Required command:

```bash
.venv/bin/python scripts/compare_strategy_kernels.py --symbols BTCUSDT ETHUSDT --history-period 2y
```

- [ ] Step 3: Run comparison locally or on the intended research machine.

Do not run heavy 2-year grid search on the 2c2g server. Single comparison is allowed if resource usage is acceptable; otherwise run locally.

- [ ] Step 4: Acceptance gate.

Do not cut over if any of these fail:

- New kernel cannot complete a backtest.
- New kernel has unbounded trade frequency.
- H4 trades dominate total risk beyond the 10% cap.
- Daily rebound and daily trend coexist in the same weekly context.
- Weekly forced exit does not close the remaining weekly position.
- Drawdown is materially worse without an understood reason.
- Runtime events cannot explain why signals were accepted or rejected.

- [ ] Step 5: Commit.

```bash
git add app/paper/strategy_backtest.py scripts/run_strategy_backtest_batch.py scripts/compare_strategy_kernels.py tests/test_v2_0_strategy_kernel_comparison.py docs/TASKS.md docs/HANDOFF.md
git commit -m "feat: add strategy kernel comparison validation"
```

## 14. Task 11: Paper Cutover With Rollback

**Files:**

- Modify: `app/paper/live_runner.py`
- Modify: `scripts/run_paper_realtime.py`
- Modify: `scripts/start.sh`
- Modify: `docs/PROJECT_CONTEXT.md`
- Modify: `docs/DECISIONS.md`
- Modify: `docs/TASKS.md`
- Modify: `docs/HANDOFF.md`
- Modify: `tests/test_v1_0_real_market_paper_runner.py`
- Modify: `tests/test_deploy_script.py`

- [ ] Step 1: Add explicit runtime switch.

Supported values:

```text
PAPER_STRATEGY_KERNEL=LAYERED_DAILY_V1
PAPER_STRATEGY_KERNEL=WEEKLY_DAILY_H4_V1
```

Default remains old until this task's final step.

- [ ] Step 2: Add rollback tests.

Required behavior:

- If env var is old kernel, old intervals and old strategy path run.
- If env var is new kernel, `1w / 1d / 4h / 15m` path runs.
- If env var is invalid, service fails fast with clear message and does not trade.

- [ ] Step 3: Switch default only after Task 10 gate passes.

Change default:

```text
PAPER_STRATEGY_KERNEL=WEEKLY_DAILY_H4_V1
```

Keep rollback documented:

```bash
PAPER_STRATEGY_KERNEL=LAYERED_DAILY_V1 bash scripts/start.sh
```

- [ ] Step 4: Run focused verification.

```bash
.venv/bin/python -m pytest tests/test_v1_0_real_market_paper_runner.py tests/test_deploy_script.py tests/test_v2_0_weekly_daily_h4_adapter.py -q
git diff --check
```

Expected: pass.

- [ ] Step 5: Commit.

```bash
git add app/paper/live_runner.py scripts/run_paper_realtime.py scripts/start.sh docs/PROJECT_CONTEXT.md docs/DECISIONS.md docs/TASKS.md docs/HANDOFF.md tests/test_v1_0_real_market_paper_runner.py tests/test_deploy_script.py
git commit -m "feat: switch paper default to weekly daily h4 kernel"
```

## 15. Task 12: Quarantine Or Remove Legacy Kernel Only After Stable Operation

**Files:**

- Modify: `app/strategy/layered_strategy.py`
- Modify: `app/paper/strategy_adapter.py`
- Modify: `docs/PROJECT_CONTEXT.md`
- Modify: `docs/DECISIONS.md`
- Modify: `docs/TASKS.md`
- Modify: `docs/HANDOFF.md`

- [ ] Step 1: Wait for stable Paper evidence.

Required evidence:

- At least one continuous Paper run survives restart.
- State JSON reloads without losing new fields.
- Web status explains current weekly/daily/H4 state.
- Backtest and Paper both use the same new kernel path.

- [ ] Step 2: Decide legacy fate.

Allowed outcomes:

- Keep old kernel behind explicit rollback flag.
- Move old kernel to `app/strategy/legacy_layered_strategy.py`.
- Remove old kernel only after user explicitly approves.

- [ ] Step 3: Do not delete old tests until replacement coverage exists.

Every removed old behavior test must have a corresponding new-kernel test or documented deletion reason.

- [ ] Step 4: Commit.

```bash
git add app/strategy/layered_strategy.py app/paper/strategy_adapter.py docs/PROJECT_CONTEXT.md docs/DECISIONS.md docs/TASKS.md docs/HANDOFF.md
git commit -m "chore: quarantine legacy layered strategy kernel"
```

## 16. Final Verification Matrix

Run before claiming the upgrade is complete:

```bash
.venv/bin/python -m pytest tests/test_v2_0_position_hierarchy_contract.py -q
.venv/bin/python -m pytest tests/test_v2_0_weekly_daily_h4_strategy.py -q
.venv/bin/python -m pytest tests/test_v2_0_daily_mutual_exclusion.py -q
.venv/bin/python -m pytest tests/test_v2_0_h4_breakout_modes.py -q
.venv/bin/python -m pytest tests/test_v2_0_trade_controls.py -q
.venv/bin/python -m pytest tests/test_v2_0_weekly_daily_h4_adapter.py -q
.venv/bin/python -m pytest tests/test_v1_0_strategy_backtest_runner.py tests/test_v1_0_real_market_paper_runner.py tests/test_v1_0_paper_persistence.py tests/test_v1_0_paper_status_web.py -q
.venv/bin/python -m py_compile app/strategy/position_hierarchy.py app/strategy/weekly_daily_h4_strategy.py app/strategy/trade_controls.py app/paper/strategy_adapter.py app/paper/trading.py app/paper/strategy_backtest.py
git diff --check
```

Manual validation:

```bash
.venv/bin/python scripts/compare_strategy_kernels.py --symbols BTCUSDT ETHUSDT --history-period 2y
```

Paper validation after cutover:

```bash
PAPER_STRATEGY_KERNEL=WEEKLY_DAILY_H4_V1 bash scripts/start.sh
```

Rollback validation:

```bash
PAPER_STRATEGY_KERNEL=LAYERED_DAILY_V1 bash scripts/start.sh
```

## 17. Completion Criteria

The upgrade is complete only when all of these are true:

- `交易逻辑优化.md` requirements are traceable to tests or explicit docs.
- `WEEKLY / DAILY / H4` are the only canonical new position levels.
- Daily rebound and daily trend positions cannot coexist in the same weekly context.
- Weekly positions support staged trend, structure, and momentum reductions.
- Weekly golden/death cross forced exits close the remaining weekly position.
- H4 supports breakout, pullback, and continuation, with BOLL no-trade filtering.
- Regime, Throttle, Signal Score, Lifecycle, and Equity Guard are active in the new kernel.
- Paper and Backtest select exactly one strategy kernel per run.
- Old kernel remains rollback-only or is explicitly quarantined.
- Web status and runtime events show the new kernel identity clearly.
- Handoff docs say whether the new kernel is diagnostic, default, or rollback-only.

## 18. Stop Conditions

Stop implementation and report status if any of these happen:

- New and old kernel fields become ambiguous in persisted state.
- A Paper/Backtest run can open both old bucket positions and new level positions at the same time.
- A weekly forced exit closes Daily or H4 positions accidentally.
- A daily mutual exclusion rule closes Weekly positions.
- H4 no-trade state blocks Weekly staged exits or hard stops.
- Equity Guard can be bypassed by Signal Score.
- Backtest uses an unfinished high-timeframe Kline.
- The system starts Live/testnet/real order work without explicit user instruction.
