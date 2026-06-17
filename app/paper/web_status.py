import html
import json
from pathlib import Path
from typing import Any


def build_paper_status_payload(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {
            "status": "WAITING_FOR_STATE",
            "state_path": str(state_path),
            "equity": None,
            "open_position": None,
            "fills": [],
            "rejected_signals": 0,
        }

    payload = json.loads(state_path.read_text(encoding="utf-8"))
    return {
        "status": "RUNNING",
        "state_path": str(state_path),
        "equity": payload.get("equity"),
        "open_position": payload.get("open_position"),
        "fills": payload.get("fills", []),
        "rejected_signals": payload.get("rejected_signals", 0),
    }


def render_paper_status_html(payload: dict[str, Any]) -> str:
    position = payload.get("open_position")
    fills = list(reversed(payload.get("fills", [])))
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="5">
  <title>Paper Trading</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: Arial, "PingFang SC", "Microsoft YaHei", sans-serif;
      background: #f5f7fb;
      color: #172033;
    }}
    body {{ margin: 0; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
    header {{ display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 18px; }}
    h1 {{ font-size: 24px; margin: 0; }}
    .badge {{ font-size: 13px; padding: 6px 10px; border: 1px solid #b8c2d6; border-radius: 4px; background: #fff; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }}
    .panel {{ background: #fff; border: 1px solid #d9e0ec; border-radius: 6px; padding: 14px; }}
    .label {{ color: #65748b; font-size: 12px; margin-bottom: 6px; }}
    .value {{ font-size: 20px; font-weight: 700; overflow-wrap: anywhere; }}
    h2 {{ font-size: 16px; margin: 0 0 10px; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d9e0ec; border-radius: 6px; overflow: hidden; }}
    th, td {{ border-bottom: 1px solid #e6ebf2; padding: 9px 10px; text-align: left; font-size: 13px; white-space: nowrap; }}
    th {{ background: #eef3f9; color: #344055; }}
    tr:last-child td {{ border-bottom: 0; }}
    .empty {{ color: #65748b; padding: 14px; background: #fff; border: 1px solid #d9e0ec; border-radius: 6px; }}
    .profit {{ color: #0a7c52; }}
    .loss {{ color: #b42318; }}
    @media (max-width: 820px) {{
      main {{ padding: 14px; }}
      header {{ align-items: flex-start; flex-direction: column; }}
      .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .table-wrap {{ overflow-x: auto; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Paper Trading</h1>
      <div class="badge">{_escape(payload.get("status"))} · refresh 5s</div>
    </header>
    <section class="grid">
      <div class="panel"><div class="label">equity</div><div class="value">{_escape(payload.get("equity") or "-")}</div></div>
      <div class="panel"><div class="label">open position</div><div class="value">{_position_title(position)}</div></div>
      <div class="panel"><div class="label">fills</div><div class="value">{len(fills)}</div></div>
      <div class="panel"><div class="label" id="rejected-signals">rejected signals</div><div class="value">{_escape(payload.get("rejected_signals"))}</div></div>
    </section>
    <section class="panel">
      <h2>Open Position</h2>
      {_render_position(position)}
    </section>
    <section style="margin-top: 16px;">
      <h2>All Fills</h2>
      {_render_fills(fills)}
    </section>
  </main>
</body>
</html>"""


def _render_position(position: dict[str, Any] | None) -> str:
    if position is None:
        return '<div class="empty">No open position</div>'
    rows = [
        ("symbol", position.get("symbol")),
        ("side", position.get("side")),
        ("strategy", position.get("strategy_type")),
        ("entry_price", position.get("entry_price")),
        ("stop_loss", position.get("stop_loss")),
        ("take_profit", position.get("take_profit")),
        ("quantity", position.get("quantity")),
    ]
    cells = "".join(f"<tr><th>{_escape(label)}</th><td>{_escape(value)}</td></tr>" for label, value in rows)
    return f'<div class="table-wrap"><table>{cells}</table></div>'


def _render_fills(fills: list[dict[str, Any]]) -> str:
    if not fills:
        return '<div class="empty">No fills yet</div>'
    rows = "\n".join(_render_fill_row(fill) for fill in fills)
    return f"""<div class="table-wrap">
<table>
  <thead>
    <tr>
      <th>symbol</th><th>side</th><th>strategy</th><th>entry</th><th>exit</th>
      <th>qty</th><th>gross pnl</th><th>fees</th><th>net pnl</th><th>reason</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
</div>"""


def _render_fill_row(fill: dict[str, Any]) -> str:
    pnl = str(fill.get("net_pnl", "0"))
    pnl_class = "loss" if pnl.startswith("-") else "profit"
    return f"""<tr>
  <td>{_escape(fill.get("symbol"))}</td>
  <td>{_escape(fill.get("side"))}</td>
  <td>{_escape(fill.get("strategy_type"))}</td>
  <td>{_escape(fill.get("entry_price"))}</td>
  <td>{_escape(fill.get("exit_price"))}</td>
  <td>{_escape(fill.get("quantity"))}</td>
  <td>{_escape(fill.get("gross_pnl"))}</td>
  <td>{_escape(fill.get("fees"))}</td>
  <td class="{pnl_class}">{_escape(fill.get("net_pnl"))}</td>
  <td>{_escape(fill.get("exit_reason"))}</td>
</tr>"""


def _position_title(position: dict[str, Any] | None) -> str:
    if position is None:
        return "NONE"
    return f"{_escape(position.get('symbol'))} {_escape(position.get('side'))}"


def _escape(value: Any) -> str:
    return html.escape(str(value))
