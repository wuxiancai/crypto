from dataclasses import dataclass
from typing import Iterable

from app.data.quality import Kline


@dataclass(frozen=True)
class MultiTimeframeFrame:
    symbol: str
    klines_by_interval: dict[str, tuple[Kline, ...]]

    def latest(self, interval: str) -> Kline:
        return self.klines_by_interval[interval][-1]

    def history(self, interval: str) -> tuple[Kline, ...]:
        return self.klines_by_interval[interval]


class MultiTimeframeKlineCache:
    def __init__(
        self,
        required_intervals: Iterable[str],
        max_klines_per_interval: int = 200,
    ) -> None:
        self._required_intervals = tuple(required_intervals)
        self._max_klines_per_interval = max_klines_per_interval
        self._klines: dict[str, dict[str, list[Kline]]] = {}

    def update(self, kline: Kline) -> MultiTimeframeFrame | None:
        symbol_klines = self._klines.setdefault(kline.symbol, {})
        interval_klines = symbol_klines.setdefault(kline.interval, [])
        interval_klines.append(kline)
        if len(interval_klines) > self._max_klines_per_interval:
            del interval_klines[: len(interval_klines) - self._max_klines_per_interval]
        if not all(symbol_klines.get(interval) for interval in self._required_intervals):
            return None
        return MultiTimeframeFrame(
            symbol=kline.symbol,
            klines_by_interval={
                interval: tuple(symbol_klines[interval])
                for interval in self._required_intervals
            },
        )
