from decimal import Decimal


def test_serializes_and_restores_paper_snapshot_with_open_position_and_fills():
    from app.paper.persistence import paper_snapshot_from_payload, paper_snapshot_to_payload
    from app.paper.trading import PaperFill, PaperPosition, PaperSnapshot

    snapshot = PaperSnapshot(
        equity=Decimal("10025.50"),
        open_position=PaperPosition(
            symbol="BTCUSDT",
            side="LONG",
            strategy_type="TREND_PULLBACK",
            entry_time=1_000,
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
            take_profit=Decimal("110"),
            quantity=Decimal("0.5"),
            entry_fee=Decimal("0.02"),
        ),
        fills=[
            PaperFill(
                symbol="ETHUSDT",
                side="SHORT",
                strategy_type="REVERSAL_PROBE",
                entry_time=2_000,
                exit_time=3_000,
                entry_price=Decimal("200"),
                exit_price=Decimal("190"),
                quantity=Decimal("0.2"),
                gross_pnl=Decimal("2"),
                fees=Decimal("0.03"),
                net_pnl=Decimal("1.97"),
                exit_reason="TAKE_PROFIT",
                exit_detail="做空止盈：最低价触达止盈价 190",
            )
        ],
        rejected_signals=2,
    )

    payload = paper_snapshot_to_payload(snapshot)
    restored = paper_snapshot_from_payload(payload)

    assert payload["equity"] == "10025.50"
    assert payload["open_position"]["entry_price"] == "100"
    assert payload["fills"][0]["net_pnl"] == "1.97"
    assert payload["fills"][0]["exit_detail"] == "做空止盈：最低价触达止盈价 190"
    assert restored == snapshot


def test_serializes_and_restores_paper_snapshot_without_open_position():
    from app.paper.persistence import paper_snapshot_from_payload, paper_snapshot_to_payload
    from app.paper.trading import PaperSnapshot

    snapshot = PaperSnapshot(
        equity=Decimal("10000"),
        open_position=None,
        fills=[],
        rejected_signals=0,
    )

    payload = paper_snapshot_to_payload(snapshot)
    restored = paper_snapshot_from_payload(payload)

    assert payload["open_position"] is None
    assert restored == snapshot


def test_serializes_and_restores_paper_runtime_metadata():
    from app.paper.persistence import paper_snapshot_from_payload, paper_snapshot_to_payload
    from app.paper.trading import PaperSnapshot

    snapshot = PaperSnapshot(
        equity=Decimal("1000"),
        open_position=None,
        fills=[],
        rejected_signals=0,
        runtime_started_at_ms=1_000,
        last_update_at_ms=2_000,
    )

    payload = paper_snapshot_to_payload(snapshot)
    restored = paper_snapshot_from_payload(payload)

    assert payload["runtime_started_at_ms"] == 1_000
    assert payload["last_update_at_ms"] == 2_000
    assert restored == snapshot


def test_saving_paper_snapshot_preserves_existing_realtime_market_prices(tmp_path):
    import json

    from app.paper.persistence import save_paper_snapshot
    from app.paper.trading import PaperSnapshot

    state_path = tmp_path / "paper-state.json"
    state_path.write_text(
        json.dumps(
            {
                "equity": "1000",
                "open_position": None,
                "fills": [],
                "rejected_signals": 0,
                "market_prices": {
                    "BTCUSDT": {
                        "price": "63424.90",
                        "event_time_ms": 1_710_000_000_000,
                        "source": "binance_ticker_ws",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    save_paper_snapshot(
        PaperSnapshot(
            equity=Decimal("1005"),
            open_position=None,
            fills=[],
            rejected_signals=0,
        ),
        state_path,
    )

    payload = json.loads(state_path.read_text(encoding="utf-8"))

    assert payload["equity"] == "1005"
    assert payload["market_prices"]["BTCUSDT"]["price"] == "63424.90"
