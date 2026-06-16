from decimal import Decimal


def test_exit_signal_takes_priority_over_new_entries():
    from app.strategy.pullback_strategy import TradeSignal
    from app.strategy.reversal_strategy import ReversalSignal
    from app.strategy.signal_router import SignalInputs, StrategySignal, select_signal

    decision = select_signal(
        SignalInputs(
            exit_signal=StrategySignal(
                action="EXIT_LONG",
                strategy_type="RISK_EXIT",
                reason=["stop loss touched"],
            ),
            main_signal=TradeSignal(
                action="LONG_ENTRY",
                strategy_type="TREND_PULLBACK",
                entry_price=Decimal("100"),
                stop_loss=Decimal("95"),
                take_profit=Decimal("110"),
                risk_reward=Decimal("2"),
                reason=["main entry"],
            ),
            reversal_signal=ReversalSignal(
                action="REVERSAL_LONG_ENTRY",
                strategy_type="REVERSAL_PROBE",
                signal_level="EARLY",
                score=Decimal("80"),
                risk_pct=Decimal("0.002"),
                max_standard_position_pct=Decimal("0.2"),
                reason=["reversal entry"],
            ),
        )
    )

    assert decision.action == "EXIT_LONG"
    assert decision.strategy_type == "RISK_EXIT"


def test_risk_block_prevents_new_entries_after_exit_check():
    from app.strategy.pullback_strategy import TradeSignal
    from app.strategy.signal_router import SignalInputs, select_signal

    decision = select_signal(
        SignalInputs(
            risk_allows_new_entries=False,
            main_signal=TradeSignal(
                action="LONG_ENTRY",
                strategy_type="TREND_PULLBACK",
                entry_price=Decimal("100"),
                stop_loss=Decimal("95"),
                take_profit=Decimal("110"),
                risk_reward=Decimal("2"),
                reason=["main entry"],
            ),
        )
    )

    assert decision.action == "WAIT"
    assert decision.reason == ["risk blocked before new entries"]


def test_main_signal_takes_priority_over_reversal_signal():
    from app.strategy.pullback_strategy import TradeSignal
    from app.strategy.reversal_strategy import ReversalSignal
    from app.strategy.signal_router import SignalInputs, select_signal

    decision = select_signal(
        SignalInputs(
            main_signal=TradeSignal(
                action="SHORT_ENTRY",
                strategy_type="TREND_PULLBACK",
                entry_price=Decimal("100"),
                stop_loss=Decimal("105"),
                take_profit=Decimal("90"),
                risk_reward=Decimal("2"),
                reason=["main entry"],
            ),
            reversal_signal=ReversalSignal(
                action="REVERSAL_SHORT_ENTRY",
                strategy_type="REVERSAL_PROBE",
                signal_level="CONFIRMED",
                score=Decimal("90"),
                risk_pct=Decimal("0.003"),
                max_standard_position_pct=Decimal("0.5"),
                reason=["reversal entry"],
            ),
        )
    )

    assert decision.action == "SHORT_ENTRY"
    assert decision.strategy_type == "TREND_PULLBACK"


def test_data_sync_block_runs_before_all_signals():
    from app.strategy.signal_router import SignalInputs, StrategySignal, select_signal

    decision = select_signal(
        SignalInputs(
            data_ready=False,
            exit_signal=StrategySignal(
                action="EXIT_LONG",
                strategy_type="RISK_EXIT",
                reason=["stop loss touched"],
            ),
        )
    )

    assert decision.action == "WAIT"
    assert decision.reason == ["data not ready"]
