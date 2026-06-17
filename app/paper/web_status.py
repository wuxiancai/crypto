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
  <title>模拟交易看板</title>
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
      <h1>模拟交易看板</h1>
      <div class="badge">{_status_label(payload.get("status"))} · 5 秒自动刷新</div>
    </header>
    <section class="grid">
      <div class="panel"><div class="label">账户权益 USDT</div><div class="value">{_escape(payload.get("equity") or "-")}</div></div>
      <div class="panel"><div class="label">持仓情况</div><div class="value">{_position_title(position)}</div></div>
      <div class="panel"><div class="label">模拟成交次数</div><div class="value">{len(fills)}</div></div>
      <div class="panel"><div class="label" id="rejected-signals">拒绝信号</div><div class="value">{_escape(payload.get("rejected_signals"))}</div></div>
    </section>
    <section class="panel">
      <h2>持仓情况</h2>
      {_render_position(position)}
    </section>
    <section style="margin-top: 16px;">
      <h2>全部模拟交易记录</h2>
      {_render_fills(fills)}
    </section>
  </main>
</body>
</html>"""


def _render_position(position: dict[str, Any] | None) -> str:
    if position is None:
        return '<div class="empty">当前无持仓</div>'
    rows = [
        ("交易对", position.get("symbol")),
        ("方向", _side_label(position.get("side"))),
        ("使用策略", position.get("strategy_type")),
        ("入场价", position.get("entry_price")),
        ("止损价", position.get("stop_loss")),
        ("止盈价", position.get("take_profit")),
        ("持仓数量", position.get("quantity")),
    ]
    cells = "".join(f"<tr><th>{_escape(label)}</th><td>{_escape(value)}</td></tr>" for label, value in rows)
    return f'<div class="table-wrap"><table>{cells}</table></div>'


def _render_fills(fills: list[dict[str, Any]]) -> str:
    if not fills:
        return '<div class="empty">暂无模拟成交</div>'
    rows = "\n".join(_render_fill_row(fill) for fill in fills)
    return f"""<div class="table-wrap">
<table>
  <thead>
    <tr>
      <th>交易对</th><th>方向</th><th>使用策略</th><th>买入价</th><th>卖出价</th>
      <th>数量</th><th>毛盈亏</th><th>手续费</th><th>净盈亏</th><th>退出原因</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
</div>"""


def _render_fill_row(fill: dict[str, Any]) -> str:
    pnl = str(fill.get("net_pnl", "0"))
    pnl_class = "loss" if pnl.startswith("-") else "profit"
    buy_price, sell_price = _buy_sell_prices(fill)
    return f"""<tr>
  <td>{_escape(fill.get("symbol"))}</td>
  <td>{_side_label(fill.get("side"))}</td>
  <td>{_escape(fill.get("strategy_type"))}</td>
  <td>{_escape(buy_price)}</td>
  <td>{_escape(sell_price)}</td>
  <td>{_escape(fill.get("quantity"))}</td>
  <td>{_escape(fill.get("gross_pnl"))}</td>
  <td>{_escape(fill.get("fees"))}</td>
  <td class="{pnl_class}">{_escape(fill.get("net_pnl"))}</td>
  <td>{_exit_reason_label(fill.get("exit_reason"))}</td>
</tr>"""


def _position_title(position: dict[str, Any] | None) -> str:
    if position is None:
        return "无"
    return f"{_escape(position.get('symbol'))} {_side_label(position.get('side'))}"


def _buy_sell_prices(fill: dict[str, Any]) -> tuple[Any, Any]:
    if fill.get("side") == "SHORT":
        return fill.get("exit_price"), fill.get("entry_price")
    return fill.get("entry_price"), fill.get("exit_price")


def _side_label(side: Any) -> str:
    if side == "LONG":
        return "做多"
    if side == "SHORT":
        return "做空"
    return _escape(side)


def _exit_reason_label(reason: Any) -> str:
    if reason == "TAKE_PROFIT":
        return "止盈"
    if reason == "STOP_LOSS":
        return "止损"
    if reason == "LIQUIDATION":
        return "强平"
    return _escape(reason)


def _status_label(status: Any) -> str:
    if status == "RUNNING":
        return "运行中"
    if status == "WAITING_FOR_STATE":
        return "等待状态文件"
    return _escape(status)


def _escape(value: Any) -> str:
    return html.escape(str(value))
