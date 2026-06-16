from decimal import Decimal


def test_formats_paper_status_for_cli():
    from app.paper.status import format_paper_status
    from app.paper.trading import PaperSnapshot

    output = format_paper_status(
        PaperSnapshot(
            equity=Decimal("10200"),
            open_position=None,
            fills=[],
            rejected_signals=2,
        )
    )

    assert "equity=10200" in output
    assert "open_position=NONE" in output
    assert "fills=0" in output
    assert "rejected_signals=2" in output
