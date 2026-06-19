# Backtest History And MA Types

## Goal

Make the strategy backtest page keep recent run summaries on the page, show win rate with wins/losses, and allow mixed moving-average types such as EMA50 / MA200.

## Scope

- Add fast/slow moving-average type fields to the backtest config and web query parsing.
- Compute selected EMA or MA in the realtime strategy adapter instead of always using EMA.
- Archive the selected average types in `config_snapshots.content`.
- Load recent web strategy backtest runs from existing `backtest_runs` and `config_snapshots`.
- Render a scrollable recent-results table above the full trade table, newest first.
- Update tests and handoff documentation.

## Verification

- Run focused tests for indicators, strategy adapter, backtest runner, and backtest page.
- Run the full test suite before committing.
