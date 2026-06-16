from decimal import Decimal


def test_generates_alerts_for_paper_drawdown_and_rejected_signals():
    from app.paper.alerts import AlertConfig, evaluate_paper_alerts
    from app.paper.trading import PaperSnapshot

    alerts = evaluate_paper_alerts(
        PaperSnapshot(
            equity=Decimal("9400"),
            open_position=None,
            fills=[],
            rejected_signals=3,
        ),
        AlertConfig(
            initial_equity=Decimal("10000"),
            max_drawdown_pct=Decimal("0.05"),
            max_rejected_signals=2,
        ),
    )

    assert [alert.level for alert in alerts] == ["WARN", "WARN"]
    assert [alert.code for alert in alerts] == ["PAPER_DRAWDOWN", "PAPER_REJECTED_SIGNALS"]
