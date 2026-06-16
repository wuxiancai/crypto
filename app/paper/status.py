from app.paper.trading import PaperSnapshot


def format_paper_status(snapshot: PaperSnapshot) -> str:
    open_position = snapshot.open_position
    if open_position is None:
        position_text = "NONE"
    else:
        position_text = (
            f"{open_position.symbol}:{open_position.side}:"
            f"{open_position.strategy_type}:qty={open_position.quantity}"
        )
    return "\n".join(
        [
            f"equity={snapshot.equity}",
            f"open_position={position_text}",
            f"fills={len(snapshot.fills)}",
            f"rejected_signals={snapshot.rejected_signals}",
        ]
    )
