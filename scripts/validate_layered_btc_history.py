from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from decimal import Decimal
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from app.data.binance import BinanceDataError
from app.data.quality import INTERVAL_MS, Kline
from app.paper.multitimeframe import MultiTimeframeFrame
from app.paper.strategy_adapter import RealtimeStrategyConfig, build_realtime_strategy_signal
from app.paper.strategy_backtest import _fetch_interval_pages
from app.strategy.signal_router import StrategySignal


LOCAL_TZ = ZoneInfo("Asia/Shanghai")
VALIDATION_INTERVALS = ("1d", "4h", "1h", "15m")


@dataclass(frozen=True)
class LayeredHistoryProbe:
    name: str
    start_time: str
    end_time: str
    expected_strategy: str
    expected_action: str

    @property
    def start_time_ms(self) -> int:
        return _local_time_ms(self.start_time)

    @property
    def end_time_ms(self) -> int:
        return _local_time_ms(self.end_time)


@dataclass(frozen=True)
class LayeredHistoryProbeResult:
    name: str
    expected_strategy: str
    expected_action: str
    matched: bool
    checked_15m_bars: int
    matched_time: str | None = None
    matched_strategy: str | None = None
    matched_action: str | None = None
    matched_bucket: str | None = None
    matched_entry_price: str | None = None
    last_strategy: str | None = None
    last_action: str | None = None
    last_bucket: str | None = None
    last_reason: list[str] | None = None


DEFAULT_BTC_PROBES = (
    LayeredHistoryProbe(
        name="btc_2026_4h_short_transition",
        start_time="2026-05-13 20:00",
        end_time="2026-05-16 00:00",
        expected_strategy="SHORT_4H_HEDGE",
        expected_action="SHORT_ENTRY",
    ),
    LayeredHistoryProbe(
        name="btc_2026_daily_short_core",
        start_time="2026-05-13 20:00",
        end_time="2026-06-05 00:00",
        expected_strategy="SHORT_DAY_CORE",
        expected_action="SHORT_ENTRY",
    ),
    LayeredHistoryProbe(
        name="btc_2026_4h_rebound_hedge",
        start_time="2026-06-12 20:00",
        end_time="2026-06-18 00:00",
        expected_strategy="LONG_4H_HEDGE",
        expected_action="LONG_ENTRY",
    ),
)


async def fetch_layered_validation_klines(
    *,
    symbol: str,
    start_time_ms: int,
    end_time_ms: int,
    cache_dir: Path | None,
    limit: int = 1500,
) -> list[Kline]:
    rows: list[Kline] = []
    for interval in VALIDATION_INTERVALS:
        rows.extend(
            await _fetch_interval_pages(
                symbol=symbol,
                interval=interval,
                limit=limit,
                start_time=start_time_ms,
                end_time=end_time_ms,
                cache_dir=cache_dir,
            )
        )
    return sorted(rows, key=lambda item: (item.open_time, item.interval))


def evaluate_layered_history_probe(
    *,
    klines: list[Kline],
    probe: LayeredHistoryProbe,
    strategy_config: RealtimeStrategyConfig | None = None,
) -> LayeredHistoryProbeResult:
    config = strategy_config or _default_layered_strategy_config()
    by_interval = _group_klines(klines)
    entry_klines = [
        kline
        for kline in by_interval.get("15m", ())
        if probe.start_time_ms <= kline.close_time <= probe.end_time_ms
    ]
    checked = 0
    last_signal: StrategySignal | None = None
    for entry_kline in entry_klines:
        frame = _frame_at(
            symbol=entry_kline.symbol,
            by_interval=by_interval,
            closed_at_ms=entry_kline.close_time,
        )
        if frame is None:
            continue
        checked += 1
        signal = build_realtime_strategy_signal(frame, config)
        last_signal = signal
        if signal.strategy_type == probe.expected_strategy and _action_matches(signal.action, probe.expected_action):
            return LayeredHistoryProbeResult(
                name=probe.name,
                expected_strategy=probe.expected_strategy,
                expected_action=probe.expected_action,
                matched=True,
                checked_15m_bars=checked,
                matched_time=_format_local_time(entry_kline.close_time),
                matched_strategy=signal.strategy_type,
                matched_action=signal.action,
                matched_bucket=signal.bucket,
                matched_entry_price=_decimal_text(signal.entry_price),
                last_strategy=signal.strategy_type,
                last_action=signal.action,
                last_bucket=signal.bucket,
                last_reason=list(signal.reason),
            )
    return LayeredHistoryProbeResult(
        name=probe.name,
        expected_strategy=probe.expected_strategy,
        expected_action=probe.expected_action,
        matched=False,
        checked_15m_bars=checked,
        last_strategy=last_signal.strategy_type if last_signal else None,
        last_action=last_signal.action if last_signal else None,
        last_bucket=last_signal.bucket if last_signal else None,
        last_reason=list(last_signal.reason) if last_signal else None,
    )


def evaluate_layered_history_probes(
    *,
    klines: list[Kline],
    probes: tuple[LayeredHistoryProbe, ...] = DEFAULT_BTC_PROBES,
    strategy_config: RealtimeStrategyConfig | None = None,
) -> list[LayeredHistoryProbeResult]:
    return [
        evaluate_layered_history_probe(
            klines=klines,
            probe=probe,
            strategy_config=strategy_config,
        )
        for probe in probes
    ]


def _default_layered_strategy_config() -> RealtimeStrategyConfig:
    return RealtimeStrategyConfig(
        fast_ma_type="EMA",
        slow_ma_type="MA",
        ema_fast_period=15,
        ema_slow_period=60,
        atr_period=14,
        dmi_period=12,
        swing_lookback=20,
        pullback_zone_atr_multiplier=Decimal("1"),
        require_pullback_close_beyond_fast_ma=False,
        enable_reversal_probe=False,
        enable_layered_strategy=True,
    )


def _group_klines(klines: list[Kline]) -> dict[str, tuple[Kline, ...]]:
    grouped: dict[str, list[Kline]] = {}
    for kline in sorted(klines, key=lambda item: item.open_time):
        grouped.setdefault(kline.interval, []).append(kline)
    return {interval: tuple(rows) for interval, rows in grouped.items()}


def _frame_at(
    *,
    symbol: str,
    by_interval: dict[str, tuple[Kline, ...]],
    closed_at_ms: int,
    max_history: int = 250,
) -> MultiTimeframeFrame | None:
    histories: dict[str, tuple[Kline, ...]] = {}
    for interval in VALIDATION_INTERVALS:
        rows = tuple(
            kline
            for kline in by_interval.get(interval, ())
            if kline.symbol == symbol and kline.close_time <= closed_at_ms
        )
        if not rows:
            return None
        histories[interval] = rows[-max_history:]
    return MultiTimeframeFrame(symbol=symbol, klines_by_interval=histories)


def _local_time_ms(value: str) -> int:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=LOCAL_TZ)
    return int(parsed.timestamp() * 1000)


def _format_local_time(value_ms: int) -> str:
    return datetime.fromtimestamp(value_ms / 1000, tz=LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S UTC+8")


def _decimal_text(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _action_matches(actual: str, expected: str) -> bool:
    aliases = {
        "BUY": "LONG_ENTRY",
        "SELL": "SHORT_ENTRY",
    }
    return aliases.get(actual, actual) == aliases.get(expected, expected)


def _result_payload(result: LayeredHistoryProbeResult) -> dict[str, object]:
    return asdict(result)


async def _run(args: argparse.Namespace) -> int:
    probes = DEFAULT_BTC_PROBES
    start_time_ms = min(probe.start_time_ms for probe in probes)
    end_time_ms = max(probe.end_time_ms for probe in probes)
    warmup_start = datetime.fromtimestamp(start_time_ms / 1000, tz=LOCAL_TZ) - timedelta(days=args.warmup_days)
    fetch_start_ms = int(warmup_start.timestamp() * 1000)
    try:
        klines = await fetch_layered_validation_klines(
            symbol=args.symbol,
            start_time_ms=fetch_start_ms,
            end_time_ms=end_time_ms,
            cache_dir=args.cache_dir,
            limit=args.limit,
        )
    except BinanceDataError as exc:
        print(f"历史 K 线拉取失败：{exc}")
        return 2

    results = evaluate_layered_history_probes(klines=klines, probes=probes)
    if args.json:
        print(json.dumps([_result_payload(result) for result in results], ensure_ascii=False, indent=2))
    else:
        _print_results(args.symbol, results)
    return 0 if all(result.matched for result in results) else 1


def _print_results(symbol: str, results: list[LayeredHistoryProbeResult]) -> None:
    print(f"{symbol} 分层策略历史验证")
    for result in results:
        status = "PASS" if result.matched else "FAIL"
        print(f"- {status} {result.name}: expected={result.expected_strategy}/{result.expected_action}")
        print(f"  checked_15m_bars={result.checked_15m_bars}")
        if result.matched:
            print(
                "  matched="
                f"{result.matched_time} {result.matched_strategy}/{result.matched_action} "
                f"bucket={result.matched_bucket} entry={result.matched_entry_price}"
            )
        else:
            print(
                "  last="
                f"{result.last_strategy}/{result.last_action} bucket={result.last_bucket} "
                f"reason={'; '.join(result.last_reason or [])}"
            )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate layered BTC strategy probes with Binance history.")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--cache-dir", type=Path, default=Path("runtime/layered-validation-klines"))
    parser.add_argument("--limit", type=int, default=1500)
    parser.add_argument("--warmup-days", type=int, default=180)
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    return asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
