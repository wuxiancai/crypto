#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SNAPSHOT_NAME="${1:-2026-06-23-pre-trigger-filter}"
SNAPSHOT_DIR="$ROOT_DIR/docs/strategy_snapshots/$SNAPSHOT_NAME"

if [[ ! -d "$SNAPSHOT_DIR" ]]; then
  echo "Strategy snapshot not found: $SNAPSHOT_DIR" >&2
  exit 1
fi

restore_file() {
  local relative_path="$1"
  if [[ ! -f "$SNAPSHOT_DIR/$relative_path" ]]; then
    echo "Snapshot file missing: $relative_path" >&2
    exit 1
  fi
  mkdir -p "$(dirname "$ROOT_DIR/$relative_path")"
  cp "$SNAPSHOT_DIR/$relative_path" "$ROOT_DIR/$relative_path"
}

restore_file "app/strategy/pullback_strategy.py"
restore_file "app/strategy/trend_detector.py"
restore_file "app/strategy/reversal_strategy.py"
restore_file "app/strategy/signal_router.py"
restore_file "app/paper/strategy_adapter.py"
restore_file "app/paper/strategy_backtest.py"
restore_file "app/paper/live_runner.py"
restore_file "app/paper/trading.py"
restore_file "app/database/repositories.py"
restore_file "scripts/run_strategy_backtest_batch.py"
restore_file "scripts/run_paper_status_web.py"

echo "Restored strategy snapshot: $SNAPSHOT_NAME"
