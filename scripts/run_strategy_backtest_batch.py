from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
from typing import Any, Iterable

from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config.settings import Settings
from app.data.binance import BinanceDataError, fetch_klines
from app.data.quality import INTERVAL_MS, Kline, validate_kline_sequence
from app.database.db import build_session_factory
from app.database.models import KlineRecord
from app.database.repositories import archive_strategy_backtest_result, find_archived_strategy_backtest_run, upsert_klines
from app.paper.strategy_backtest import StrategyBacktestConfig, run_strategy_backtest

SUPPORTED_INTERVALS = ("1w", "1d", "4h")
HISTORY_PERIOD = "1y"
HISTORY_WINDOW_MS = 365 * 24 * 60 * 60 * 1000
HISTORY_WINDOWS_MS = {
    "3m": 90 * 24 * 60 * 60 * 1000,
    "6m": 180 * 24 * 60 * 60 * 1000,
    "1y": 365 * 24 * 60 * 60 * 1000,
    "2y": 2 * 365 * 24 * 60 * 60 * 1000,
}
DEFAULT_WORKSPACE = ROOT / "runtime" / "strategy-backtest-batch"
DEFAULT_ESTIMATED_RUN_SECONDS = 90


@dataclass(frozen=True)
class BacktestWindow:
    start_time_ms: int
    end_time_ms: int
    latest_close_time_by_interval: dict[str, int]


@dataclass(frozen=True)
class ParameterSet:
    fast_period: int
    slow_period: int
    fast_ma_type: str = "EMA"
    slow_ma_type: str = "MA"
    atr_period: int = 14
    dmi_period: int = 14
    swing_lookback: int = 20
    max_fee_to_risk_ratio: str = "0.25"
    trend_pullback_take_profit_mode: str = "TRAILING"

    def key(self) -> str:
        return (
            f"{self.fast_ma_type.lower()}{self.fast_period}"
            f"-{self.slow_ma_type.lower()}{self.slow_period}"
            f"-atr{self.atr_period}"
            f"-dmi{self.dmi_period}"
            f"-swing{self.swing_lookback}"
            f"-feerisk{self.max_fee_to_risk_ratio}"
            f"-tp{self.trend_pullback_take_profit_mode.lower()}"
        )

    def label(self) -> str:
        return (
            "WEEKLY_DAILY_H4_V1"
            f" | 1w/1d/4h | "
            f"{self.fast_ma_type}{self.fast_period}/{self.slow_ma_type}{self.slow_period}"
            f" | ATR {self.atr_period}"
            f" | DMI {self.dmi_period}"
            f" | Swing {self.swing_lookback}"
            f" | Fee/Risk {self.max_fee_to_risk_ratio}"
            f" | TP {self.trend_pullback_take_profit_mode}"
        )

    def to_config(
        self,
        symbol: str,
        cache_dir: Path,
        window: BacktestWindow,
        history_period: str = HISTORY_PERIOD,
    ) -> StrategyBacktestConfig:
        return StrategyBacktestConfig(
            symbols=(symbol,),
            fast_ma_type=self.fast_ma_type,
            slow_ma_type=self.slow_ma_type,
            ema_fast_period=self.fast_period,
            ema_slow_period=self.slow_period,
            atr_period=self.atr_period,
            dmi_period=self.dmi_period,
            swing_lookback=self.swing_lookback,
            limit=1500,
            history_period=history_period,
            history_start_time_ms=window.start_time_ms,
            history_end_time_ms=window.end_time_ms,
            history_cache_dir=cache_dir,
            max_fee_to_risk_ratio=Decimal(self.max_fee_to_risk_ratio),
            trend_pullback_take_profit_mode=self.trend_pullback_take_profit_mode,
        )


@dataclass(frozen=True)
class StrategyBacktestBatchConfig:
    symbol: str = "BTCUSDT"
    workspace: Path | None = None
    fast_ma_type: str = "EMA"
    slow_ma_type: str = "MA"
    fast_periods: tuple[int, ...] = tuple(range(15, 51, 5))
    slow_periods: tuple[int, ...] = (30, 60, 90, 120, 150, 180, 200)
    atr_periods: tuple[int, ...] = (12, 14)
    dmi_periods: tuple[int, ...] = (12, 14)
    swing_lookbacks: tuple[int, ...] = (20, 30)
    max_fee_to_risk_ratios: tuple[str, ...] = ("0.25", "0")
    take_profit_modes: tuple[str, ...] = ("TRAILING", "FIXED")
    history_period: str = HISTORY_PERIOD
    history_window_ms: int = HISTORY_WINDOW_MS
    skip_fast_gte_slow: bool = True
    rerun_completed: bool = False
    retry_failed: bool = False
    refresh_cache: bool = False
    reset_workspace: bool = False

    def workspace_path(self) -> Path:
        if self.workspace is not None:
            return self.workspace.expanduser().resolve()
        return (DEFAULT_WORKSPACE / f"{self.symbol.lower()}-{self.history_period}").resolve()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Batch-run the existing web strategy backtest, archive every successful run "
            "to the database, and analyse the best parameter set."
        )
    )
    parser.add_argument("--symbol", default="BTCUSDT", choices=("BTCUSDT", "ETHUSDT"))
    parser.add_argument("--fast-ma-type", default="EMA", choices=("EMA", "MA"))
    parser.add_argument("--slow-ma-type", default="MA", choices=("EMA", "MA"))
    parser.add_argument("--fast-periods", default="15:50:5", help="Fast MA periods, e.g. 15:50:5 or 15,20,25.")
    parser.add_argument("--slow-periods", default="30,60,90,120,150,180,200", help="Slow MA periods, e.g. 30,60,90,120,150,180,200.")
    parser.add_argument("--atr-periods", default="12,14")
    parser.add_argument("--dmi-periods", default="12,14")
    parser.add_argument("--swing-lookbacks", default="20,30")
    parser.add_argument("--max-fee-to-risk-ratios", default="0.25,0")
    parser.add_argument("--take-profit-modes", default="TRAILING,FIXED")
    parser.add_argument("--history-period", default=HISTORY_PERIOD, choices=tuple(HISTORY_WINDOWS_MS))
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="Directory used for checkpoint, cache and analysis reports.",
    )
    parser.add_argument(
        "--skip-fast-gte-slow",
        action="store_true",
        default=True,
        help="Skip combinations where EMA period is greater than or equal to MA period.",
    )
    parser.add_argument(
        "--include-fast-gte-slow",
        action="store_false",
        dest="skip_fast_gte_slow",
        help="Include combinations where the fast period is greater than or equal to the slow period.",
    )
    parser.add_argument(
        "--rerun-completed",
        action="store_true",
        help="Re-run successful parameter sets even if they already exist in the checkpoint.",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry parameter sets that previously failed.",
    )
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Rebuild the local cache from database K-lines before running.",
    )
    parser.add_argument(
        "--reset-workspace",
        action="store_true",
        help="Delete the existing workspace before starting a new batch.",
    )
    return parser.parse_args()


def main() -> None:
    _prepare_runtime_env()
    config = _batch_config_from_args(parse_args())
    run_strategy_backtest_batch(config)


def _batch_config_from_args(args: argparse.Namespace) -> StrategyBacktestBatchConfig:
    return StrategyBacktestBatchConfig(
        symbol=args.symbol,
        workspace=args.workspace,
        fast_ma_type=args.fast_ma_type,
        slow_ma_type=args.slow_ma_type,
        fast_periods=_parse_int_series(args.fast_periods),
        slow_periods=_parse_int_series(args.slow_periods),
        atr_periods=_parse_int_series(args.atr_periods),
        dmi_periods=_parse_int_series(args.dmi_periods),
        swing_lookbacks=_parse_int_series(args.swing_lookbacks),
        max_fee_to_risk_ratios=_parse_decimal_series(args.max_fee_to_risk_ratios),
        take_profit_modes=_parse_take_profit_modes(args.take_profit_modes),
        history_period=args.history_period,
        history_window_ms=HISTORY_WINDOWS_MS[args.history_period],
        skip_fast_gte_slow=args.skip_fast_gte_slow,
        rerun_completed=args.rerun_completed,
        retry_failed=args.retry_failed,
        refresh_cache=args.refresh_cache,
        reset_workspace=args.reset_workspace,
    )


def run_strategy_backtest_batch(
    config: StrategyBacktestBatchConfig,
    log_callback: Any | None = None,
    stop_event: Any | None = None,
) -> dict[str, Any]:
    workspace = config.workspace_path()
    if config.reset_workspace and workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)

    settings = Settings()
    session_factory = build_session_factory(settings)
    checkpoint = _load_checkpoint(workspace)
    requested_window: BacktestWindow | None = None
    if checkpoint is not None:
        _validate_checkpoint_symbol(checkpoint, config.symbol)
        requested_window = _window_from_checkpoint(checkpoint)

    _ensure_database_history(
        session_factory=session_factory,
        settings=settings,
        symbol=config.symbol,
        requested_window=requested_window,
        history_window_ms=config.history_window_ms,
        log_callback=log_callback,
    )

    if checkpoint is None:
        with session_factory() as session:
            window = _resolve_backtest_window(session, config.symbol, config.history_window_ms)
        checkpoint = _initial_checkpoint(symbol=config.symbol, workspace=workspace, window=window)
        _save_checkpoint(workspace, checkpoint)
    else:
        window = requested_window

    cache_dir = workspace / "cache"
    if config.refresh_cache or not _cache_complete(cache_dir, config.symbol):
        with session_factory() as session:
            _hydrate_cache_from_database(
                session=session,
                symbol=config.symbol,
                cache_dir=cache_dir,
                window=window,
            )

    primary_phase = "primary"
    primary_candidates = list(_build_primary_candidates(config))
    primary_records = _run_phase(
        phase=primary_phase,
        candidates=primary_candidates,
        checkpoint=checkpoint,
        workspace=workspace,
        cache_dir=cache_dir,
        session_factory=session_factory,
        symbol=config.symbol,
        window=window,
        history_period=config.history_period,
        rerun_completed=config.rerun_completed,
        retry_failed=config.retry_failed,
        future_runs_estimate=0,
        log_callback=log_callback,
        stop_event=stop_event,
    )
    best_primary = _best_record(primary_records)
    if best_primary is None:
        raise SystemExit("No successful primary backtest result was produced.")

    best_primary_params = _params_from_record(best_primary)
    refinement_phase = f"refinement:{best_primary['run_key']}"
    refinement_candidates = list(_build_refinement_candidates(best_primary_params, config))
    refinement_records = (
        _run_phase(
            phase=refinement_phase,
            candidates=refinement_candidates,
            checkpoint=checkpoint,
            workspace=workspace,
            cache_dir=cache_dir,
            session_factory=session_factory,
            symbol=config.symbol,
            window=window,
            history_period=config.history_period,
            rerun_completed=config.rerun_completed,
            retry_failed=config.retry_failed,
            future_runs_estimate=0,
            log_callback=log_callback,
            stop_event=stop_event,
        )
        if refinement_candidates
        else []
    )

    analysis = _build_analysis(
        symbol=config.symbol,
        window=window,
        primary_records=primary_records,
        refinement_records=refinement_records,
    )
    _write_analysis_outputs(workspace, analysis)
    _print_summary(analysis, workspace, log_callback=log_callback)
    return analysis


def _prepare_runtime_env() -> None:
    if os.environ.get("DATABASE_URL"):
        return
    _load_env_file(ROOT / ".env.ports.generated")
    _load_env_file(ROOT / ".env")


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = _strip_env_value(value.strip())


def _strip_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _parse_int_series(raw: str) -> tuple[int, ...]:
    text = str(raw or "").strip()
    if ":" in text:
        parts = [part.strip() for part in text.split(":")]
        if len(parts) not in {2, 3}:
            raise SystemExit(f"Invalid integer range: {raw}")
        start = int(parts[0])
        end = int(parts[1])
        step = int(parts[2]) if len(parts) == 3 else 1
        if step <= 0:
            raise SystemExit(f"Range step must be positive: {raw}")
        if end < start:
            raise SystemExit(f"Range end must be >= start: {raw}")
        return tuple(range(start, end + 1, step))
    values = tuple(int(part.strip()) for part in text.split(",") if part.strip())
    if not values:
        raise SystemExit(f"At least one integer value is required: {raw}")
    return values


def _parse_decimal_series(raw: str) -> tuple[str, ...]:
    values: list[str] = []
    for part in str(raw or "").split(","):
        text = part.strip()
        if not text:
            continue
        try:
            Decimal(text)
        except InvalidOperation as exc:
            raise SystemExit(f"Invalid decimal value: {text}") from exc
        values.append(text)
    if not values:
        raise SystemExit("At least one fee/risk value is required.")
    return tuple(values)


def _parse_take_profit_modes(raw: str) -> tuple[str, ...]:
    allowed = {"TRAILING", "FIXED"}
    values = tuple(part.strip().upper() for part in str(raw or "").split(",") if part.strip())
    if not values:
        raise SystemExit("At least one take-profit mode is required.")
    invalid = [value for value in values if value not in allowed]
    if invalid:
        raise SystemExit(f"Invalid take-profit mode: {', '.join(invalid)}")
    return values


def _parse_bool_series(raw: str) -> tuple[bool, ...]:
    mapping = {
        "1": True,
        "true": True,
        "yes": True,
        "on": True,
        "0": False,
        "false": False,
        "no": False,
        "off": False,
    }
    values: list[bool] = []
    for part in str(raw or "").split(","):
        text = part.strip().lower()
        if not text:
            continue
        if text not in mapping:
            raise SystemExit(f"Invalid boolean value: {part.strip()}")
        values.append(mapping[text])
    if not values:
        raise SystemExit("At least one boolean value is required.")
    return tuple(values)


def _ensure_database_history(
    session_factory: Any,
    settings: Settings,
    symbol: str,
    requested_window: BacktestWindow | None,
    history_window_ms: int,
    log_callback: Any | None = None,
) -> None:
    if requested_window is None:
        target_end_time_ms = _latest_closed_end_time(int(time.time() * 1000))
        target_start_time_ms = target_end_time_ms - history_window_ms
    else:
        target_start_time_ms = requested_window.start_time_ms
        target_end_time_ms = requested_window.end_time_ms

    _emit(
        log_callback,
        f"Checking database K-lines for {symbol} "
        f"({target_start_time_ms} -> {target_end_time_ms})"
    )
    for interval in SUPPORTED_INTERVALS:
        written = asyncio.run(
            _ensure_interval_history(
                session_factory=session_factory,
                settings=settings,
                symbol=symbol,
                interval=interval,
                start_time_ms=target_start_time_ms,
                end_time_ms=target_end_time_ms,
            )
        )
        if written > 0:
            _emit(log_callback, f"  synced {symbol} {interval}: wrote {written} klines")
        else:
            _emit(log_callback, f"  ready  {symbol} {interval}: database already has full window")


async def _ensure_interval_history(
    session_factory: Any,
    settings: Settings,
    symbol: str,
    interval: str,
    start_time_ms: int,
    end_time_ms: int,
) -> int:
    interval_ms = INTERVAL_MS[interval]
    first_open = _ceil_to_interval(start_time_ms, interval_ms)
    last_open = (end_time_ms // interval_ms) * interval_ms
    if first_open > last_open:
        return 0

    with session_factory() as session:
        existing_open_times = {
            int(value)
            for value in session.execute(
                select(KlineRecord.open_time).where(
                    KlineRecord.symbol == symbol,
                    KlineRecord.interval == interval,
                    KlineRecord.is_closed.is_(True),
                    KlineRecord.open_time >= first_open,
                    KlineRecord.open_time <= last_open,
                )
            ).scalars()
        }

    missing_ranges = _missing_open_ranges(
        existing_open_times=existing_open_times,
        first_open=first_open,
        last_open=last_open,
        interval_ms=interval_ms,
    )
    if not missing_ranges:
        return 0

    written = 0
    for missing_start, missing_end in missing_ranges:
        fetched = await _fetch_interval_pages_from_binance(
            symbol=symbol,
            interval=interval,
            start_time_ms=missing_start,
            end_time_ms=missing_end,
            settings=settings,
        )
        if not fetched:
            continue
        errors = validate_kline_sequence(fetched)
        if errors:
            preview = "; ".join(errors[:5])
            raise SystemExit(f"Fetched invalid {symbol} {interval} klines: {preview}")
        with session_factory() as session:
            upsert_klines(session, fetched)
        written += len(fetched)
    return written


async def _fetch_interval_pages_from_binance(
    symbol: str,
    interval: str,
    start_time_ms: int,
    end_time_ms: int,
    settings: Settings,
) -> list[Kline]:
    page_limit = 1500
    interval_ms = INTERVAL_MS[interval]
    cursor = start_time_ms
    pages: list[Kline] = []
    while cursor <= end_time_ms:
        page_end = min(end_time_ms, cursor + interval_ms * page_limit - 1)
        try:
            page = await fetch_klines(
                symbol=symbol,
                interval=interval,
                limit=page_limit,
                settings=settings,
                start_time=cursor,
                end_time=page_end,
            )
        except BinanceDataError as exc:
            raise SystemExit(f"Failed to sync {symbol} {interval} klines from Binance: {exc}") from exc
        if not page:
            cursor = page_end + 1
            continue
        pages.extend(page)
        next_cursor = max(kline.open_time for kline in page) + interval_ms
        cursor = max(next_cursor, page_end + 1)
    return [
        row
        for row in sorted({kline.open_time: kline for kline in pages}.values(), key=lambda item: item.open_time)
        if start_time_ms <= row.open_time <= end_time_ms
    ]


def _missing_open_ranges(
    existing_open_times: set[int],
    first_open: int,
    last_open: int,
    interval_ms: int,
) -> list[tuple[int, int]]:
    missing_ranges: list[tuple[int, int]] = []
    missing_start: int | None = None
    cursor = first_open
    while cursor <= last_open:
        if cursor not in existing_open_times and missing_start is None:
            missing_start = cursor
        if cursor in existing_open_times and missing_start is not None:
            missing_ranges.append((missing_start, cursor - 1))
            missing_start = None
        cursor += interval_ms
    if missing_start is not None:
        missing_ranges.append((missing_start, last_open + interval_ms - 1))
    return missing_ranges


def _latest_closed_end_time(now_ms: int) -> int:
    return min(((now_ms // INTERVAL_MS[interval]) * INTERVAL_MS[interval]) - 1 for interval in SUPPORTED_INTERVALS)


def _validate_checkpoint_symbol(checkpoint: dict[str, Any], symbol: str) -> None:
    saved_symbol = str(checkpoint.get("symbol") or "")
    if saved_symbol != symbol:
        raise SystemExit(
            f"Workspace checkpoint belongs to {saved_symbol or 'UNKNOWN'}, "
            f"but current run uses {symbol}. Use a different --workspace."
        )


def _initial_checkpoint(symbol: str, workspace: Path, window: BacktestWindow) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "created_at_ms": int(time.time() * 1000),
        "symbol": symbol,
        "workspace": str(workspace),
        "window": {
            "start_time_ms": window.start_time_ms,
            "end_time_ms": window.end_time_ms,
            "latest_close_time_by_interval": window.latest_close_time_by_interval,
        },
        "records": {},
    }


def _load_checkpoint(workspace: Path) -> dict[str, Any] | None:
    path = _checkpoint_path(workspace)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Checkpoint is not valid JSON: {path} ({exc})") from exc
    return payload if isinstance(payload, dict) else None


def _save_checkpoint(workspace: Path, checkpoint: dict[str, Any]) -> None:
    _atomic_write_json(_checkpoint_path(workspace), checkpoint)


def _checkpoint_path(workspace: Path) -> Path:
    return workspace / "checkpoint.json"


def _window_from_checkpoint(checkpoint: dict[str, Any]) -> BacktestWindow:
    payload = checkpoint.get("window") or {}
    return BacktestWindow(
        start_time_ms=int(payload["start_time_ms"]),
        end_time_ms=int(payload["end_time_ms"]),
        latest_close_time_by_interval={
            str(key): int(value)
            for key, value in dict(payload.get("latest_close_time_by_interval") or {}).items()
        },
    )


def _cache_complete(cache_dir: Path, symbol: str) -> bool:
    return all((cache_dir / f"{symbol}-{interval}.jsonl").exists() for interval in SUPPORTED_INTERVALS)


def _resolve_backtest_window(session: Any, symbol: str, history_window_ms: int = HISTORY_WINDOW_MS) -> BacktestWindow:
    latest_close_time_by_interval: dict[str, int] = {}
    for interval in SUPPORTED_INTERVALS:
        latest_close = session.execute(
            select(func.max(KlineRecord.close_time)).where(
                KlineRecord.symbol == symbol,
                KlineRecord.interval == interval,
                KlineRecord.is_closed.is_(True),
            )
        ).scalar_one()
        if latest_close is None:
            raise SystemExit(f"No closed {interval} K-line data found in database for {symbol}.")
        latest_close_time_by_interval[interval] = int(latest_close)

    end_time_ms = min(latest_close_time_by_interval.values())
    start_time_ms = end_time_ms - history_window_ms
    for interval in SUPPORTED_INTERVALS:
        interval_ms = INTERVAL_MS[interval]
        first_open = _ceil_to_interval(start_time_ms, interval_ms)
        last_open = (end_time_ms // interval_ms) * interval_ms
        expected_count = max(0, ((last_open - first_open) // interval_ms) + 1)
        row_count = session.execute(
            select(func.count()).select_from(KlineRecord).where(
                KlineRecord.symbol == symbol,
                KlineRecord.interval == interval,
                KlineRecord.is_closed.is_(True),
                KlineRecord.open_time >= first_open,
                KlineRecord.open_time <= end_time_ms,
            )
        ).scalar_one()
        if int(row_count or 0) < expected_count:
            raise SystemExit(f"Database does not contain a complete requested window for {symbol} {interval}.")
    return BacktestWindow(
        start_time_ms=start_time_ms,
        end_time_ms=end_time_ms,
        latest_close_time_by_interval=latest_close_time_by_interval,
    )


def _hydrate_cache_from_database(
    session: Any,
    symbol: str,
    cache_dir: Path,
    window: BacktestWindow,
) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "symbol": symbol,
        "start_time_ms": window.start_time_ms,
        "end_time_ms": window.end_time_ms,
        "intervals": {},
    }
    for interval in SUPPORTED_INTERVALS:
        rows = session.execute(
            select(KlineRecord).where(
                KlineRecord.symbol == symbol,
                KlineRecord.interval == interval,
                KlineRecord.is_closed.is_(True),
                KlineRecord.open_time >= _ceil_to_interval(window.start_time_ms, INTERVAL_MS[interval]),
                KlineRecord.open_time <= window.end_time_ms,
            ).order_by(KlineRecord.open_time.asc())
        ).scalars().all()
        klines = [_kline_from_record(row) for row in rows]
        errors = validate_kline_sequence(klines)
        if errors:
            preview = "; ".join(errors[:5])
            raise SystemExit(f"Invalid K-line sequence for {symbol} {interval}: {preview}")
        _write_cache_file(cache_dir / f"{symbol}-{interval}.jsonl", klines)
        metadata["intervals"][interval] = {
            "count": len(klines),
            "first_open_time": klines[0].open_time if klines else None,
            "last_open_time": klines[-1].open_time if klines else None,
        }
    _atomic_write_json(cache_dir / "metadata.json", metadata)


def _kline_from_record(row: KlineRecord) -> Kline:
    return Kline(
        symbol=row.symbol,
        interval=row.interval,
        open_time=int(row.open_time),
        close_time=int(row.close_time),
        open=Decimal(str(row.open)),
        high=Decimal(str(row.high)),
        low=Decimal(str(row.low)),
        close=Decimal(str(row.close)),
        volume=Decimal(str(row.volume)),
        is_closed=bool(row.is_closed),
    )


def _write_cache_file(path: Path, rows: list[Kline]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(json.dumps(row.model_dump(mode="json"), sort_keys=True) for row in rows)
    path.write_text(f"{payload}\n" if payload else "", encoding="utf-8")


def _build_primary_candidates(config: StrategyBacktestBatchConfig | bool) -> Iterable[ParameterSet]:
    if isinstance(config, bool):
        config = StrategyBacktestBatchConfig(skip_fast_gte_slow=config)
    for fast_period in config.fast_periods:
        for slow_period in config.slow_periods:
            if config.skip_fast_gte_slow and fast_period >= slow_period:
                continue
            for atr_period in config.atr_periods:
                for dmi_period in config.dmi_periods:
                    for swing_lookback in config.swing_lookbacks:
                        for max_fee_to_risk_ratio in config.max_fee_to_risk_ratios:
                            for take_profit_mode in config.take_profit_modes:
                                yield ParameterSet(
                                    fast_period=fast_period,
                                    slow_period=slow_period,
                                    fast_ma_type=config.fast_ma_type,
                                    slow_ma_type=config.slow_ma_type,
                                    atr_period=atr_period,
                                    dmi_period=dmi_period,
                                    swing_lookback=swing_lookback,
                                    max_fee_to_risk_ratio=max_fee_to_risk_ratio,
                                    trend_pullback_take_profit_mode=take_profit_mode,
                                )


def _build_refinement_candidates(
    base: ParameterSet,
    config: StrategyBacktestBatchConfig | None = None,
) -> Iterable[ParameterSet]:
    return []


def _run_phase(
    phase: str,
    candidates: list[ParameterSet],
    checkpoint: dict[str, Any],
    workspace: Path,
    cache_dir: Path,
    session_factory: Any,
    symbol: str,
    window: BacktestWindow,
    history_period: str,
    rerun_completed: bool,
    retry_failed: bool,
    future_runs_estimate: int = 0,
    log_callback: Any | None = None,
    stop_event: Any | None = None,
) -> list[dict[str, Any]]:
    records = checkpoint.setdefault("records", {})
    initial_phase_pending = _pending_run_count(
        candidates=candidates,
        records=records,
        phase=phase,
        rerun_completed=rerun_completed,
        retry_failed=retry_failed,
    )
    if initial_phase_pending > 0:
        phase_estimate_seconds = _estimate_run_seconds(records, phase=phase)
        total_estimated_runs = initial_phase_pending + future_runs_estimate
        _emit(
            log_callback,
            f"[phase] {phase} 待执行 {initial_phase_pending} 组 | "
            f"当前阶段预计总用时 {_format_duration_clock(phase_estimate_seconds * initial_phase_pending)} | "
            f"整个脚本预计总用时 {_format_duration_clock(phase_estimate_seconds * total_estimated_runs)}"
        )
    for index, params in enumerate(candidates, start=1):
        if _stop_requested(stop_event):
            _emit(log_callback, f"[stopped] 停止请求已收到，{phase} 在第 {index}/{len(candidates)} 组前退出。")
            break
        run_key = _run_key(phase, params)
        existing = records.get(run_key)
        config = params.to_config(symbol=symbol, cache_dir=cache_dir, window=window, history_period=history_period)
        if existing is not None and not _should_run_existing(
            existing=existing,
            rerun_completed=rerun_completed,
            retry_failed=retry_failed,
        ):
            if str(existing.get("status") or "") == "success":
                with session_factory() as session:
                    archived_run = find_archived_strategy_backtest_run(session, config)
                if archived_run is not None:
                    records[run_key] = _record_from_archived_run(
                        phase=phase,
                        run_key=run_key,
                        params=params,
                        archived_run=archived_run,
                    )
                    _save_checkpoint(workspace, checkpoint)
                    _emit(
                        log_callback,
                        f"[skip {index}/{len(candidates)}] {phase} {params.label()} "
                        f"| existing database run_id={archived_run.id}"
                    )
                    continue
                _emit(
                    log_callback,
                    f"[rerun {index}/{len(candidates)}] {phase} {params.label()} "
                    "| checkpoint success missing from database"
                )
            else:
                _emit(log_callback, f"[skip {index}/{len(candidates)}] {phase} {params.label()}")
                continue

        if not rerun_completed:
            with session_factory() as session:
                archived_run = find_archived_strategy_backtest_run(session, config)
            if archived_run is not None:
                record = _record_from_archived_run(
                    phase=phase,
                    run_key=run_key,
                    params=params,
                    archived_run=archived_run,
                )
                records[run_key] = record
                _save_checkpoint(workspace, checkpoint)
                _emit(
                    log_callback,
                    f"[skip {index}/{len(candidates)}] {phase} {params.label()} "
                    f"| existing database run_id={archived_run.id}"
                )
                continue

        _emit(log_callback, f"[run  {index}/{len(candidates)}] {phase} {params.label()}")
        current_estimated_seconds = _estimate_run_seconds(records, phase=phase)
        remaining_runs = _pending_run_count(
            candidates=candidates[index - 1 :],
            records=records,
            phase=phase,
            rerun_completed=rerun_completed,
            retry_failed=retry_failed,
        )
        total_remaining_runs = remaining_runs + future_runs_estimate
        _emit(
            log_callback,
            "         "
            f"本轮预计用时={_format_duration_clock(current_estimated_seconds)} | "
            f"当前阶段剩余总预计={_format_duration_clock(current_estimated_seconds * remaining_runs)} | "
            f"整个脚本剩余总预计={_format_duration_clock(current_estimated_seconds * total_remaining_runs)}"
        )
        started_at_ms = int(time.time() * 1000)
        with _countdown_printer(
            label="         本轮倒计时",
            estimated_seconds=current_estimated_seconds,
            log_callback=log_callback,
        ):
            result = asyncio.run(run_strategy_backtest(config))
        actual_elapsed_seconds = max(1, int((int(time.time() * 1000) - started_at_ms) / 1000))
        record: dict[str, Any] = {
            "phase": phase,
            "run_key": run_key,
            "status": "error" if result.error else "success",
            "params": _params_payload(params),
            "started_at_ms": started_at_ms,
            "finished_at_ms": int(time.time() * 1000),
            "elapsed_seconds": actual_elapsed_seconds,
            "error": result.error,
        }
        _emit(
            log_callback,
            "         "
            f"本轮实际用时={_format_duration_clock(actual_elapsed_seconds)}"
        )
        if result.error:
            _emit(log_callback, f"         error: {result.error}")
        else:
            with session_factory() as session:
                archived_run_id = archive_strategy_backtest_result(session, result)
            _emit(
                log_callback,
                "         "
                f"[ARCHIVED] run_id={archived_run_id} | "
                f"combo={params.fast_ma_type}{params.fast_period}/{params.slow_ma_type}{params.slow_period}"
            )
            record.update(
                {
                    "archived_run_id": archived_run_id,
                    "initial_equity": result.initial_equity,
                    "final_equity": result.final_equity,
                    "net_pnl": result.net_pnl,
                    "total_trades": result.total_trades,
                    "wins": result.wins,
                    "losses": result.losses,
                    "win_rate": _format_ratio(result.wins, result.losses),
                }
            )
            _emit(
                log_callback,
                "         "
                f"final={result.final_equity} | pnl={result.net_pnl} | "
                f"trades={result.total_trades} | win_rate={record['win_rate']}"
            )
        records[run_key] = record
        _save_checkpoint(workspace, checkpoint)
    return [record for record in records.values() if record.get("phase") == phase]


def _record_from_archived_run(
    phase: str,
    run_key: str,
    params: ParameterSet,
    archived_run: Any,
) -> dict[str, Any]:
    now_ms = int(time.time() * 1000)
    return {
        "phase": phase,
        "run_key": run_key,
        "status": "success",
        "source": "existing_database",
        "params": _params_payload(params),
        "started_at_ms": now_ms,
        "finished_at_ms": now_ms,
        "elapsed_seconds": 0,
        "error": None,
        "archived_run_id": int(archived_run.id),
        "initial_equity": _money_record_value(archived_run.initial_equity),
        "final_equity": _money_record_value(archived_run.final_equity),
        "net_pnl": _money_record_value(archived_run.net_pnl),
        "total_trades": int(archived_run.total_trades),
        "wins": int(archived_run.wins),
        "losses": int(archived_run.losses),
        "win_rate": _format_ratio(int(archived_run.wins), int(archived_run.losses)),
    }


def _should_run_existing(
    existing: dict[str, Any],
    rerun_completed: bool,
    retry_failed: bool,
) -> bool:
    status = str(existing.get("status") or "")
    if status == "success":
        return rerun_completed
    if status == "error":
        return retry_failed
    return True


def _pending_run_count(
    candidates: Iterable[ParameterSet],
    records: dict[str, Any],
    phase: str,
    rerun_completed: bool,
    retry_failed: bool,
) -> int:
    total = 0
    for params in candidates:
        run_key = _run_key(phase, params)
        existing = records.get(run_key)
        if existing is None or _should_run_existing(existing, rerun_completed=rerun_completed, retry_failed=retry_failed):
            total += 1
    return total


def _estimate_run_seconds(records: dict[str, Any], phase: str) -> int:
    phase_durations = [
        _record_elapsed_seconds(record)
        for record in records.values()
        if record.get("phase") == phase and _record_elapsed_seconds(record) is not None
    ]
    all_durations = [
        _record_elapsed_seconds(record)
        for record in records.values()
        if _record_elapsed_seconds(record) is not None
    ]
    source = phase_durations or all_durations
    if not source:
        return DEFAULT_ESTIMATED_RUN_SECONDS
    average = int(sum(source) / len(source))
    return max(5, average)


def _record_elapsed_seconds(record: dict[str, Any]) -> int | None:
    raw_elapsed = record.get("elapsed_seconds")
    if raw_elapsed is not None:
        try:
            return max(1, int(raw_elapsed))
        except (TypeError, ValueError):
            return None
    started_at_ms = record.get("started_at_ms")
    finished_at_ms = record.get("finished_at_ms")
    if started_at_ms is None or finished_at_ms is None:
        return None
    try:
        return max(1, int((int(finished_at_ms) - int(started_at_ms)) / 1000))
    except (TypeError, ValueError):
        return None


def _run_key(phase: str, params: ParameterSet) -> str:
    return f"{phase}|{params.key()}"


def _params_payload(params: ParameterSet) -> dict[str, Any]:
    return asdict(params)


def _best_record(records: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    successful = [record for record in records if record.get("status") == "success"]
    if not successful:
        return None
    return max(successful, key=_record_sort_key)


def _top_records(records: Iterable[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    successful = [record for record in records if record.get("status") == "success"]
    return sorted(successful, key=_record_sort_key, reverse=True)[:limit]


def _record_sort_key(record: dict[str, Any]) -> tuple[Decimal, Decimal, Decimal, int, int]:
    return (
        _decimal_from_record(record, "final_equity"),
        _decimal_from_record(record, "win_rate"),
        _decimal_from_record(record, "net_pnl"),
        int(record.get("wins") or 0),
        -int(record.get("losses") or 0),
    )


def _decimal_from_record(record: dict[str, Any], key: str) -> Decimal:
    value = record.get(key)
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _params_from_record(record: dict[str, Any]) -> ParameterSet:
    params = dict(record.get("params") or {})
    return ParameterSet(
        fast_period=int(params["fast_period"]),
        slow_period=int(params["slow_period"]),
        fast_ma_type=str(params.get("fast_ma_type") or "EMA"),
        slow_ma_type=str(params.get("slow_ma_type") or "MA"),
        atr_period=int(params["atr_period"]),
        dmi_period=int(params["dmi_period"]),
        swing_lookback=int(params["swing_lookback"]),
        max_fee_to_risk_ratio=str(params["max_fee_to_risk_ratio"]),
        trend_pullback_take_profit_mode=str(params["trend_pullback_take_profit_mode"]),
    )


def _record_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _build_analysis(
    symbol: str,
    window: BacktestWindow,
    primary_records: list[dict[str, Any]],
    refinement_records: list[dict[str, Any]],
) -> dict[str, Any]:
    best_primary = _best_record(primary_records)
    best_refinement = _best_record(refinement_records)
    top_primary = _top_records(primary_records)
    top_refinement = _top_records(refinement_records)

    joint_improvements: list[dict[str, Any]] = []
    better_return: list[dict[str, Any]] = []
    better_win_rate: list[dict[str, Any]] = []
    if best_primary is not None:
        baseline_equity = _decimal_from_record(best_primary, "final_equity")
        baseline_win_rate = _decimal_from_record(best_primary, "win_rate")
        for record in refinement_records:
            if record.get("status") != "success":
                continue
            equity = _decimal_from_record(record, "final_equity")
            win_rate = _decimal_from_record(record, "win_rate")
            if equity > baseline_equity:
                better_return.append(record)
            if win_rate > baseline_win_rate:
                better_win_rate.append(record)
            if equity > baseline_equity and win_rate > baseline_win_rate:
                joint_improvements.append(record)

    analysis = {
        "generated_at_ms": int(time.time() * 1000),
        "symbol": symbol,
        "window": {
            "start_time_ms": window.start_time_ms,
            "end_time_ms": window.end_time_ms,
            "latest_close_time_by_interval": window.latest_close_time_by_interval,
        },
        "primary": {
            "total_runs": len(primary_records),
            "success_runs": sum(1 for record in primary_records if record.get("status") == "success"),
            "failed_runs": sum(1 for record in primary_records if record.get("status") == "error"),
            "best": best_primary,
            "top5": top_primary,
        },
        "refinement": {
            "total_runs": len(refinement_records),
            "success_runs": sum(1 for record in refinement_records if record.get("status") == "success"),
            "failed_runs": sum(1 for record in refinement_records if record.get("status") == "error"),
            "best": best_refinement,
            "top5": top_refinement,
            "best_return_improvement": _best_record(better_return),
            "best_win_rate_improvement": _best_record(better_win_rate),
            "best_joint_improvement": _best_record(joint_improvements),
        },
    }
    return analysis


def _write_analysis_outputs(workspace: Path, analysis: dict[str, Any]) -> None:
    _atomic_write_json(workspace / "analysis.json", analysis)
    (workspace / "analysis.md").write_text(_analysis_markdown(analysis), encoding="utf-8")


def _analysis_markdown(analysis: dict[str, Any]) -> str:
    primary = analysis.get("primary") or {}
    refinement = analysis.get("refinement") or {}
    lines = [
        f"# Strategy Backtest Batch Report ({analysis.get('symbol', '-')})",
        "",
        f"- Window start: `{analysis['window']['start_time_ms']}`",
        f"- Window end: `{analysis['window']['end_time_ms']}`",
        f"- Primary successful runs: `{primary.get('success_runs', 0)}` / `{primary.get('total_runs', 0)}`",
        f"- Refinement successful runs: `{refinement.get('success_runs', 0)}` / `{refinement.get('total_runs', 0)}`",
        "",
        "## Best Primary",
        "",
        _record_markdown(primary.get("best")),
        "",
        "## Top Primary 5",
        "",
    ]
    for item in primary.get("top5") or []:
        lines.append(f"- {_record_short_line(item)}")
    lines.extend(["", "## Refinement", "", f"- Best refinement: {_record_short_line(refinement.get('best'))}"])
    lines.append(f"- Better return: {_record_short_line(refinement.get('best_return_improvement'))}")
    lines.append(f"- Better win rate: {_record_short_line(refinement.get('best_win_rate_improvement'))}")
    lines.append(f"- Better return and win rate: {_record_short_line(refinement.get('best_joint_improvement'))}")
    return "\n".join(lines) + "\n"


def _record_markdown(record: dict[str, Any] | None) -> str:
    if record is None:
        return "- None"
    return "\n".join(
        [
            f"- Params: `{_record_params_label(record)}`",
            f"- Final equity: `{record.get('final_equity', '-')}`",
            f"- Net pnl: `{record.get('net_pnl', '-')}`",
            f"- Win rate: `{record.get('win_rate', '-')}`",
            f"- Trades: `{record.get('total_trades', '-')}`",
            f"- Archived run id: `{record.get('archived_run_id', '-')}`",
        ]
    )


def _record_short_line(record: dict[str, Any] | None) -> str:
    if record is None:
        return "none"
    if record.get("status") != "success":
        return f"{record.get('run_key', '-')}: error={record.get('error', '-')}"
    return (
        f"{_record_params_label(record)} | final={record.get('final_equity', '-')}"
        f" | pnl={record.get('net_pnl', '-')}"
        f" | win_rate={record.get('win_rate', '-')}"
        f" | trades={record.get('total_trades', '-')}"
    )


def _record_params_label(record: dict[str, Any]) -> str:
    params = record.get("params") or {}
    return (
        f"{params.get('fast_ma_type', 'EMA')}{params.get('fast_period', '-')}/"
        f"{params.get('slow_ma_type', 'MA')}{params.get('slow_period', '-')}"
        f", ATR {params.get('atr_period', '-')}"
        f", DMI {params.get('dmi_period', '-')}"
        f", Swing {params.get('swing_lookback', '-')}"
        f", Fee/Risk {params.get('max_fee_to_risk_ratio', '-')}"
        f", TP {params.get('trend_pullback_take_profit_mode', '-')}"
    )


def _print_summary(analysis: dict[str, Any], workspace: Path, log_callback: Any | None = None) -> None:
    primary_best = (analysis.get("primary") or {}).get("best")
    refinement = analysis.get("refinement") or {}
    _emit(log_callback, "")
    _emit(log_callback, "Batch backtest completed.")
    _emit(log_callback, f"Workspace: {workspace}")
    _emit(log_callback, f"Analysis JSON: {workspace / 'analysis.json'}")
    _emit(log_callback, f"Analysis Markdown: {workspace / 'analysis.md'}")
    _emit(log_callback, f"Best primary: {_record_short_line(primary_best)}")
    _emit(log_callback, f"Best refinement: {_record_short_line(refinement.get('best'))}")
    _emit(log_callback, f"Joint improvement: {_record_short_line(refinement.get('best_joint_improvement'))}")


class _countdown_printer:
    def __init__(self, label: str, estimated_seconds: int, log_callback: Any | None = None) -> None:
        self._label = label
        self._estimated_seconds = max(1, estimated_seconds)
        self._log_callback = log_callback
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._started_at = 0.0

    def __enter__(self) -> "_countdown_printer":
        self._started_at = time.time()
        self._thread.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self._stop.set()
        self._thread.join(timeout=1.5)
        if self._log_callback is None:
            sys.stdout.write("\r" + " " * 120 + "\r")
            sys.stdout.flush()

    def _run(self) -> None:
        while not self._stop.wait(1):
            elapsed = int(time.time() - self._started_at)
            remaining = self._estimated_seconds - elapsed
            if remaining >= 0:
                status = f"剩余 {_format_duration_clock(remaining)}"
            else:
                status = f"已超时 {_format_duration_clock(abs(remaining))}"
            line = f"{self._label}: {status} / 预计 {_format_duration_clock(self._estimated_seconds)}"
            if self._log_callback is None:
                sys.stdout.write("\r" + line)
                sys.stdout.flush()
            else:
                self._log_callback(line)


def _emit(log_callback: Any | None, line: str) -> None:
    if log_callback is None:
        print(line)
        return
    log_callback(line)


def _stop_requested(stop_event: Any | None) -> bool:
    return bool(stop_event is not None and stop_event.is_set())


def _format_ratio(wins: int, losses: int) -> str:
    total = wins + losses
    if total <= 0:
        return "0"
    value = Decimal(wins) * Decimal("100") / Decimal(total)
    return format(value.quantize(Decimal("0.01")), "f")


def _money_record_value(value: Any) -> str:
    try:
        return format(Decimal(str(value)).quantize(Decimal("0.01")), "f")
    except (InvalidOperation, TypeError, ValueError):
        return "0.00"


def _format_duration_clock(total_seconds: int) -> str:
    seconds = max(0, int(total_seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(path)


def _ceil_to_interval(value: int, interval_ms: int) -> int:
    return ((value + interval_ms - 1) // interval_ms) * interval_ms


if __name__ == "__main__":
    main()
