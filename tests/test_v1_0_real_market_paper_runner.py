import asyncio
from decimal import Decimal


def _kline(
    symbol: str,
    interval: str,
    index: int,
    close: str,
    open_price: str | None = None,
    high: str | None = None,
    low: str | None = None,
):
    from app.data.quality import INTERVAL_MS, Kline

    open_time = index * INTERVAL_MS[interval]
    price = Decimal(close)
    return Kline(
        symbol=symbol,
        interval=interval,
        open_time=open_time,
        close_time=open_time + INTERVAL_MS[interval] - 1,
        open=Decimal(open_price) if open_price is not None else price,
        high=Decimal(high) if high is not None else price + Decimal("2"),
        low=Decimal(low) if low is not None else price - Decimal("2"),
        close=price,
        volume=Decimal("10"),
    )


def test_real_market_paper_runner_wires_source_to_persistent_stream(tmp_path):
    from app.data.quality import Kline
    from app.paper.live_runner import RealMarketPaperConfig, run_real_market_paper
    from app.paper.persistence import load_paper_snapshot

    state_path = tmp_path / "paper-state.json"

    async def source():
        yield Kline(
            symbol="BTCUSDT",
            interval="15m",
            open_time=0,
            close_time=899_999,
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            volume=Decimal("10"),
        )

    snapshot = asyncio.run(
        run_real_market_paper(
            RealMarketPaperConfig(
                symbols=("BTCUSDT", "ETHUSDT"),
                intervals=("15m", "1h", "4h"),
                websocket_base_url="wss://fstream.binance.com",
                state_path=state_path,
                initial_equity=Decimal("10000"),
                risk_per_trade_pct=Decimal("0.005"),
            ),
            source=source(),
        )
    )

    persisted = load_paper_snapshot(state_path)

    assert snapshot.equity == Decimal("10000")
    assert snapshot.open_position is None
    assert snapshot.rejected_signals == 0
    assert persisted == snapshot


def test_real_market_paper_config_defaults_to_perpetual_costs_and_10x_leverage(tmp_path):
    from app.paper.live_runner import RealMarketPaperConfig

    config = RealMarketPaperConfig(
        symbols=("BTCUSDT",),
        intervals=("15m", "1h", "4h"),
        websocket_base_url="wss://fstream.binance.com",
        state_path=tmp_path / "paper-state.json",
        initial_equity=Decimal("1000"),
        risk_per_trade_pct=Decimal("0.005"),
    )

    assert config.maker_fee_rate == Decimal("0.0002")
    assert config.taker_fee_rate == Decimal("0.0005")
    assert config.leverage == Decimal("10")
    assert config.funding_interval_ms == 8 * 60 * 60 * 1000
    assert config.trend_pullback_take_profit_mode == "TRAILING"


def test_real_market_paper_runner_uses_injected_strategy_signal(tmp_path):
    from app.data.quality import Kline
    from app.paper.live_runner import RealMarketPaperConfig, run_real_market_paper
    from app.strategy.pullback_strategy import TradeSignal

    state_path = tmp_path / "paper-state.json"
    klines = [
        Kline(
            symbol="BTCUSDT",
            interval="15m",
            open_time=0,
            close_time=899_999,
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            volume=Decimal("10"),
        ),
        Kline(
            symbol="BTCUSDT",
            interval="15m",
            open_time=900_000,
            close_time=1_799_999,
            open=Decimal("100"),
            high=Decimal("111"),
            low=Decimal("99"),
            close=Decimal("110"),
            volume=Decimal("10"),
        ),
    ]

    async def source():
        for kline in klines:
            yield kline

    def signal_fn(kline: Kline, has_position: bool) -> TradeSignal:
        if kline.open_time == 0 and not has_position:
            return TradeSignal(
                action="LONG_ENTRY",
                strategy_type="TREND_PULLBACK",
                entry_price=Decimal("100"),
                stop_loss=Decimal("95"),
                take_profit=Decimal("110"),
                risk_reward=Decimal("2"),
                reason=["injected strategy"],
            )
        return TradeSignal(
            action="WAIT",
            strategy_type="TREND_PULLBACK",
            entry_price=None,
            stop_loss=None,
            take_profit=None,
            risk_reward=None,
            reason=[],
        )

    snapshot = asyncio.run(
        run_real_market_paper(
            RealMarketPaperConfig(
                symbols=("BTCUSDT",),
                intervals=("15m", "1h", "4h"),
                websocket_base_url="wss://fstream.binance.com",
                state_path=state_path,
                initial_equity=Decimal("10000"),
                risk_per_trade_pct=Decimal("0.005"),
                maker_fee_rate=Decimal("0"),
                taker_fee_rate=Decimal("0"),
                slippage_pct=Decimal("0"),
                trend_pullback_take_profit_mode="FIXED",
            ),
            source=source(),
            signal_fn=signal_fn,
        )
    )

    assert snapshot.equity == Decimal("10100")
    assert snapshot.open_position is None
    assert len(snapshot.fills) == 1


def test_real_market_paper_runner_uses_default_realtime_strategy(tmp_path):
    from app.data.quality import INTERVAL_MS, Kline
    from app.paper.live_runner import RealMarketPaperConfig, run_real_market_paper
    from app.paper.strategy_adapter import RealtimeStrategyConfig

    state_path = tmp_path / "paper-state.json"
    klines = [
        *[
            _kline("BTCUSDT", "4h", index, close)
            for index, close in enumerate(["100", "104", "108", "112", "116", "120"])
        ],
        *[
            _kline("BTCUSDT", "1h", index, close)
            for index, close in enumerate(["108", "112", "116", "120", "124", "128"])
        ],
        *[
            _kline("BTCUSDT", "15m", index, close)
            for index, close in enumerate(["120", "124", "128", "124"])
        ],
        _kline("BTCUSDT", "15m", 4, "126", open_price="125"),
        Kline(
            symbol="BTCUSDT",
            interval="15m",
            open_time=5 * INTERVAL_MS["15m"],
            close_time=6 * INTERVAL_MS["15m"] - 1,
            open=Decimal("160"),
            high=Decimal("160"),
            low=Decimal("125"),
            close=Decimal("130"),
            volume=Decimal("10"),
        ),
    ]

    async def source():
        for kline in klines:
            yield kline

    snapshot = asyncio.run(
        run_real_market_paper(
            RealMarketPaperConfig(
                symbols=("BTCUSDT",),
                intervals=("15m", "1h", "4h"),
                websocket_base_url="wss://fstream.binance.com",
                state_path=state_path,
                initial_equity=Decimal("10000"),
                risk_per_trade_pct=Decimal("0.005"),
                maker_fee_rate=Decimal("0"),
                taker_fee_rate=Decimal("0"),
                slippage_pct=Decimal("0"),
                trend_pullback_take_profit_mode="FIXED",
                strategy_config=RealtimeStrategyConfig(
                    ema_fast_period=3,
                    ema_slow_period=5,
                    atr_period=3,
                    dmi_period=3,
                    swing_lookback=5,
                ),
            ),
            source=source(),
        )
    )

    assert snapshot.equity == Decimal("10100.00")
    assert snapshot.open_position is None
    assert len(snapshot.fills) == 1
    assert snapshot.fills[0].strategy_type == "TREND_PULLBACK"


def test_default_realtime_strategy_does_not_reuse_latest_15m_signal_on_non_entry_interval():
    from app.paper.live_runner import build_default_realtime_signal_fn
    from app.paper.strategy_adapter import RealtimeStrategyConfig

    warmup_klines = [
        *[
            _kline("BTCUSDT", "4h", index, close)
            for index, close in enumerate(["100", "104", "108", "112", "116", "120"])
        ],
        *[
            _kline("BTCUSDT", "1h", index, close)
            for index, close in enumerate(["108", "112", "116", "120", "124", "128"])
        ],
        *[
            _kline("BTCUSDT", "15m", index, close)
            for index, close in enumerate(["120", "124", "128", "124"])
        ],
        _kline("BTCUSDT", "15m", 4, "126", open_price="125"),
    ]
    signal_fn = build_default_realtime_signal_fn(
        RealtimeStrategyConfig(
            ema_fast_period=3,
            ema_slow_period=5,
            atr_period=3,
            dmi_period=3,
            swing_lookback=5,
        ),
        warmup_klines=warmup_klines,
    )

    signal = signal_fn(_kline("BTCUSDT", "5m", 99, "126"), has_position=False)

    assert signal.action == "WAIT"
    assert signal.reason == ["non-entry interval observed"]


def test_real_market_paper_runner_uses_default_reversal_strategy(tmp_path):
    from app.data.quality import INTERVAL_MS, Kline
    from app.paper.live_runner import RealMarketPaperConfig, run_real_market_paper
    from app.paper.strategy_adapter import RealtimeStrategyConfig

    state_path = tmp_path / "paper-state.json"
    klines = [
        *[
            _kline("BTCUSDT", "4h", index, close)
            for index, close in enumerate(["120", "110", "100", "90", "80", "81"])
        ],
        *[
            _kline("BTCUSDT", "1h", index, close)
            for index, close in enumerate(["80", "84", "88", "92", "96", "100"])
        ],
        *[
            _kline("BTCUSDT", "15m", index, close)
            for index, close in enumerate(["90", "94", "98", "96", "97", "98"])
        ],
        Kline(
            symbol="BTCUSDT",
            interval="15m",
            open_time=6 * INTERVAL_MS["15m"],
            close_time=7 * INTERVAL_MS["15m"] - 1,
            open=Decimal("98"),
            high=Decimal("120"),
            low=Decimal("97"),
            close=Decimal("120"),
            volume=Decimal("10"),
        ),
    ]

    async def source():
        for kline in klines:
            yield kline

    snapshot = asyncio.run(
        run_real_market_paper(
            RealMarketPaperConfig(
                symbols=("BTCUSDT",),
                intervals=("15m", "1h", "4h"),
                websocket_base_url="wss://fstream.binance.com",
                state_path=state_path,
                initial_equity=Decimal("10000"),
                risk_per_trade_pct=Decimal("0.005"),
                maker_fee_rate=Decimal("0"),
                taker_fee_rate=Decimal("0"),
                slippage_pct=Decimal("0"),
                trend_pullback_take_profit_mode="FIXED",
                strategy_config=RealtimeStrategyConfig(
                    ema_fast_period=3,
                    ema_slow_period=5,
                    atr_period=3,
                    dmi_period=3,
                    swing_lookback=5,
                ),
            ),
            source=source(),
        )
    )

    assert snapshot.open_position is None
    assert len(snapshot.fills) == 1
    assert snapshot.fills[0].strategy_type == "REVERSAL_PROBE"
    assert snapshot.fills[0].net_pnl.quantize(Decimal("0.001")) == Decimal("40.000")


def test_default_realtime_strategy_can_be_warmed_with_historical_klines(tmp_path):
    from app.data.quality import INTERVAL_MS, Kline
    from app.paper.live_runner import RealMarketPaperConfig, run_real_market_paper
    from app.paper.strategy_adapter import RealtimeStrategyConfig

    state_path = tmp_path / "paper-state.json"
    warmup_klines = [
        *[
            _kline("BTCUSDT", "4h", index, close)
            for index, close in enumerate(["100", "104", "108", "112", "116", "120"])
        ],
        *[
            _kline("BTCUSDT", "1h", index, close)
            for index, close in enumerate(["108", "112", "116", "120", "124", "128"])
        ],
        *[
            _kline("BTCUSDT", "15m", index, close)
            for index, close in enumerate(["120", "124", "128", "124"])
        ],
    ]
    entry_kline = _kline("BTCUSDT", "15m", 4, "126", open_price="125")
    exit_kline = Kline(
        symbol="BTCUSDT",
        interval="15m",
        open_time=5 * INTERVAL_MS["15m"],
        close_time=6 * INTERVAL_MS["15m"] - 1,
        open=Decimal("160"),
        high=Decimal("160"),
        low=Decimal("125"),
        close=Decimal("130"),
        volume=Decimal("10"),
    )

    async def source():
        yield entry_kline
        yield exit_kline

    snapshot = asyncio.run(
        run_real_market_paper(
            RealMarketPaperConfig(
                symbols=("BTCUSDT",),
                intervals=("15m", "1h", "4h"),
                websocket_base_url="wss://fstream.binance.com",
                state_path=state_path,
                initial_equity=Decimal("10000"),
                risk_per_trade_pct=Decimal("0.005"),
                maker_fee_rate=Decimal("0"),
                taker_fee_rate=Decimal("0"),
                slippage_pct=Decimal("0"),
                trend_pullback_take_profit_mode="FIXED",
                strategy_config=RealtimeStrategyConfig(
                    ema_fast_period=3,
                    ema_slow_period=5,
                    atr_period=3,
                    dmi_period=3,
                    swing_lookback=5,
                ),
            ),
            source=source(),
            warmup_klines=warmup_klines,
        )
    )

    assert snapshot.open_position is None
    assert len(snapshot.fills) == 1
    assert snapshot.fills[0].strategy_type == "TREND_PULLBACK"


def test_realtime_warmup_fetches_250_closed_klines_by_default(monkeypatch, tmp_path):
    from app.paper import live_runner
    from app.paper.live_runner import RealMarketPaperConfig, fetch_realtime_warmup_klines

    requested_limits: list[int] = []

    async def fake_fetch_klines(symbol: str, interval: str, limit: int, settings=None):
        requested_limits.append(limit)
        return []

    monkeypatch.setattr(live_runner, "fetch_klines", fake_fetch_klines)

    asyncio.run(
        fetch_realtime_warmup_klines(
            RealMarketPaperConfig(
                symbols=("BTCUSDT", "ETHUSDT"),
                intervals=("15m", "1h", "4h"),
                websocket_base_url="wss://fstream.binance.com",
                state_path=tmp_path / "paper-state.json",
                initial_equity=Decimal("10000"),
                risk_per_trade_pct=Decimal("0.005"),
                maker_fee_rate=Decimal("0"),
                taker_fee_rate=Decimal("0"),
                slippage_pct=Decimal("0"),
                trend_pullback_take_profit_mode="FIXED",
            )
        )
    )

    assert requested_limits
    assert set(requested_limits) == {250}


def test_real_market_paper_runner_replays_missing_historical_klines_after_restart(monkeypatch, tmp_path):
    from app.data.quality import INTERVAL_MS, Kline
    from app.paper import live_runner
    from app.paper.live_runner import RealMarketPaperConfig, run_real_market_paper
    from app.paper.persistence import save_paper_snapshot
    from app.paper.trading import PaperPosition, PaperSnapshot

    state_path = tmp_path / "paper-state.json"
    save_paper_snapshot(
        PaperSnapshot(
            equity=Decimal("10000"),
            open_position=PaperPosition(
                symbol="BTCUSDT",
                side="LONG",
                strategy_type="TREND_PULLBACK",
                entry_time=0,
                entry_price=Decimal("100"),
                stop_loss=Decimal("95"),
                take_profit=Decimal("110"),
                quantity=Decimal("20"),
                entry_fee=Decimal("0"),
            ),
            fills=[],
            rejected_signals=0,
            runtime_started_at_ms=1_000,
            last_update_at_ms=1_799_999,
        ),
        state_path,
    )

    async def fake_fetch_klines(symbol: str, interval: str, limit: int, settings=None):
        if symbol == "BTCUSDT" and interval == "15m":
            return [
                Kline(
                    symbol="BTCUSDT",
                    interval="15m",
                    open_time=2 * INTERVAL_MS["15m"],
                    close_time=3 * INTERVAL_MS["15m"] - 1,
                    open=Decimal("105"),
                    high=Decimal("111"),
                    low=Decimal("104"),
                    close=Decimal("110"),
                    volume=Decimal("10"),
                )
            ]
        return []

    async def empty_websocket_source(*args, **kwargs):
        if False:
            yield None

    monkeypatch.setattr(live_runner, "fetch_klines", fake_fetch_klines)
    monkeypatch.setattr(live_runner, "iter_binance_multi_interval_websocket_klines", empty_websocket_source)

    snapshot = asyncio.run(
        run_real_market_paper(
            RealMarketPaperConfig(
                symbols=("BTCUSDT",),
                intervals=("15m", "1h", "4h"),
                websocket_base_url="wss://fstream.binance.com",
                state_path=state_path,
                initial_equity=Decimal("10000"),
                risk_per_trade_pct=Decimal("0.005"),
                maker_fee_rate=Decimal("0"),
                taker_fee_rate=Decimal("0"),
                slippage_pct=Decimal("0"),
                trend_pullback_take_profit_mode="FIXED",
            )
        )
    )

    assert snapshot.equity == Decimal("10200")
    assert snapshot.open_position is None
    assert len(snapshot.fills) == 1
    assert snapshot.fills[0].exit_reason == "TAKE_PROFIT"
