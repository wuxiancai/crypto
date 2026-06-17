from decimal import Decimal


def test_saves_and_loads_paper_snapshot_file(tmp_path):
    from app.paper.persistence import load_paper_snapshot, save_paper_snapshot
    from app.paper.trading import PaperSnapshot

    snapshot = PaperSnapshot(
        equity=Decimal("10000"),
        open_position=None,
        fills=[],
        rejected_signals=1,
    )
    state_file = tmp_path / "paper-state.json"

    save_paper_snapshot(snapshot, state_file)
    restored = load_paper_snapshot(state_file)

    assert restored == snapshot
    assert state_file.read_text().startswith("{\n")


def test_load_paper_snapshot_returns_none_when_state_file_missing(tmp_path):
    from app.paper.persistence import load_paper_snapshot

    restored = load_paper_snapshot(tmp_path / "missing-paper-state.json")

    assert restored is None
