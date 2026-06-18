import html
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
import time
from typing import Any


def build_paper_status_payload(
    state_path: Path,
    current_time_ms: int | None = None,
    error_log_path: Path | None = None,
) -> dict[str, Any]:
    now_ms = current_time_ms if current_time_ms is not None else int(time.time() * 1000)
    if not state_path.exists():
        return {
            "status": "WAITING_FOR_STATE",
            "state_path": str(state_path),
            "equity": None,
            "open_position": None,
            "fills": [],
            "rejected_signals": 0,
            "runtime_seconds": 0,
            "last_update_at_ms": None,
            "error_logs": _read_error_logs(error_log_path),
            "signal_evaluations": [],
        }

    payload = json.loads(state_path.read_text(encoding="utf-8"))
    started_at = payload.get("runtime_started_at_ms")
    return {
        "status": "RUNNING",
        "state_path": str(state_path),
        "equity": payload.get("equity"),
        "open_position": payload.get("open_position"),
        "fills": payload.get("fills", []),
        "rejected_signals": payload.get("rejected_signals", 0),
        "runtime_seconds": _runtime_seconds(started_at, now_ms),
        "last_update_at_ms": payload.get("last_update_at_ms"),
        "error_logs": _read_error_logs(error_log_path),
        "signal_evaluations": payload.get("signal_evaluations", []),
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
    .header-meta {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }}
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
    .error-log-box {{ display: grid; gap: 8px; }}
    .error-log-line {{ color: #b42318; font-family: Menlo, Consolas, monospace; font-size: 12px; white-space: pre-wrap; overflow-wrap: anywhere; }}
    .rule-list {{ display: grid; gap: 6px; margin: 0 0 12px; padding: 0; list-style: none; color: #344055; font-size: 13px; }}
    .condition-summary {{ display: grid; gap: 6px; margin-bottom: 12px; }}
    .condition-title {{ color: #172033; font-size: 17px; font-weight: 700; }}
    .condition-missing {{ color: #65748b; font-size: 13px; }}
    .condition-list {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }}
    .condition-row {{ padding: 10px; border: 1px solid #e6ebf2; border-radius: 4px; background: #fff; font-size: 13px; }}
    .condition-status {{ font-weight: 700; white-space: nowrap; }}
    .condition-pass {{ color: #0a7c52; }}
    .condition-fail {{ color: #b42318; }}
    .condition-detail {{ color: #65748b; overflow-wrap: anywhere; margin-top: 6px; }}
    .condition-detail summary {{ cursor: pointer; color: #65748b; }}
    .chart-wrap {{ background: #fff; border: 1px solid #d9e0ec; border-radius: 6px; padding: 10px; overflow-x: auto; }}
    .chart-tabs {{ display: flex; gap: 6px; flex-wrap: wrap; margin: 0 0 10px; }}
    .chart-tab {{ border: 1px solid #b8c2d6; background: #fff; color: #344055; border-radius: 4px; padding: 6px 10px; cursor: pointer; font-size: 13px; }}
    .chart-tab.active {{ background: #172033; color: #fff; border-color: #172033; }}
    .chart-panel {{ display: none; }}
    .chart-panel.active {{ display: block; }}
    .legend {{ display: flex; gap: 14px; align-items: center; flex-wrap: wrap; color: #65748b; font-size: 12px; margin-bottom: 8px; }}
    .legend-item {{ display: inline-flex; align-items: center; gap: 5px; }}
    .legend-swatch {{ width: 16px; height: 3px; display: inline-block; border-radius: 2px; }}
    .candle-up {{ color: #0a7c52; }}
    .candle-down {{ color: #b42318; }}
    .profit {{ color: #0a7c52; }}
    .loss {{ color: #b42318; }}
    @media (max-width: 820px) {{
      main {{ padding: 14px; }}
      header {{ align-items: flex-start; flex-direction: column; }}
      .header-meta {{ justify-content: flex-start; }}
      .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .condition-list {{ grid-template-columns: 1fr; }}
      .table-wrap {{ overflow-x: auto; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>模拟交易看板</h1>
      <div class="header-meta">
        <div class="badge">系统运行时间：{_format_duration(payload.get("runtime_seconds"))}</div>
        <div class="badge">{_status_label(payload.get("status"))} · 5 秒自动刷新</div>
      </div>
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
    <section style="margin-top: 16px;">
      <h2>最近策略输出</h2>
      {_render_signal_evaluations(payload.get("signal_evaluations", []))}
    </section>
    <section style="margin-top: 16px;">
      <h2>策略触发条件</h2>
      {_render_strategy_conditions(payload.get("signal_evaluations", []))}
    </section>
    <section style="margin-top: 16px;">
      <h2>策略K线图</h2>
      {_render_strategy_chart(payload.get("signal_evaluations", []))}
    </section>
    <section class="panel" style="margin-top: 16px;">
      <h2>错误日志</h2>
      {_render_error_logs(payload.get("error_logs", []))}
    </section>
  </main>
  <script>
    document.querySelectorAll("[data-chart-target]").forEach((button) => {{
      button.addEventListener("click", () => {{
        const target = button.getAttribute("data-chart-target");
        document.querySelectorAll("[data-chart-target]").forEach((item) => item.classList.remove("active"));
        document.querySelectorAll("[data-chart-panel]").forEach((item) => item.classList.remove("active"));
        button.classList.add("active");
        const panel = document.querySelector(`[data-chart-panel="${{target}}"]`);
        if (panel) {{
          panel.classList.add("active");
        }}
      }});
    }});
  </script>
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


def _render_error_logs(lines: list[str]) -> str:
    if not lines:
        return '<div class="empty">暂无错误日志</div>'
    rendered = "".join(f'<div class="error-log-line">{_escape(line)}</div>' for line in lines)
    return f'<div class="error-log-box">{rendered}</div>'


def _render_signal_evaluations(evaluations: list[dict[str, Any]]) -> str:
    latest = _latest_evaluations_by_symbol_interval(evaluations)
    if not latest:
        return '<div class="empty">暂无策略输出</div>'
    rows = "\n".join(_render_signal_evaluation_row(evaluation) for evaluation in reversed(latest))
    return f"""<div class="table-wrap">
<table>
  <thead>
    <tr>
      <th>交易对</th><th>周期</th><th>收盘价</th><th>动作</th><th>使用策略</th><th>原因</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
</div>"""


def _latest_evaluations_by_symbol_interval(evaluations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for evaluation in evaluations:
        key = (str(evaluation.get("symbol")), str(evaluation.get("interval")))
        latest[key] = evaluation
    return sorted(
        latest.values(),
        key=lambda item: int(item.get("evaluated_at_ms") or 0),
    )


def _render_signal_evaluation_row(evaluation: dict[str, Any]) -> str:
    return f"""<tr>
  <td>{_escape(evaluation.get("symbol"))}</td>
  <td>{_escape(evaluation.get("interval"))}</td>
  <td>{_escape(evaluation.get("close"))}</td>
  <td>{_action_label(evaluation.get("action"))}</td>
  <td>{_escape(evaluation.get("strategy_type"))}</td>
  <td>{_escape(_format_reasons(evaluation.get("reason")))}</td>
</tr>"""


def _render_strategy_conditions(evaluations: list[dict[str, Any]]) -> str:
    evaluation = _latest_condition_evaluation(evaluations)
    if evaluation is None:
        return '<div class="empty">暂无策略触发条件</div>'
    nearest = evaluation.get("nearest_strategy", {})
    strategy_name = _nearest_strategy_name(nearest)
    conditions = _conditions_for_strategy(evaluation.get("condition_statuses", []), strategy_name)
    if not conditions:
        return '<div class="empty">暂无策略触发条件</div>'
    rows = "".join(_render_condition_row(condition) for condition in conditions)
    return f"""<div class="panel">
  <div class="condition-summary">
    <div class="condition-title">{_escape(_nearest_strategy_summary(nearest))}</div>
    <div class="condition-missing">{_escape(_missing_conditions_summary(conditions))}</div>
  </div>
  <div class="condition-list">{rows}</div>
</div>"""


def _latest_condition_evaluation(evaluations: list[dict[str, Any]]) -> dict[str, Any] | None:
    conditionable = [
        evaluation
        for evaluation in evaluations
        if evaluation.get("condition_statuses")
    ]
    if not conditionable:
        return None
    return max(conditionable, key=lambda item: int(item.get("evaluated_at_ms") or 0))


def _render_condition_row(condition: dict[str, Any]) -> str:
    passed = bool(condition.get("passed"))
    status_class = "condition-pass" if passed else "condition-fail"
    return f"""<div class="condition-row">
  <div><span class="condition-status {status_class}">{_condition_status_label(passed)}</span> {_escape(condition.get("text"))}</div>
  <details class="condition-detail"><summary>计算明细</summary>{_escape(condition.get("detail"))}</details>
</div>"""


def _condition_status_label(passed: bool) -> str:
    return "满足" if passed else "未满足"


def _nearest_strategy_summary(nearest: Any) -> str:
    if not isinstance(nearest, dict) or not nearest:
        return "当前趋势：暂无"
    name = nearest.get("name") or "-"
    matched = nearest.get("matched", 0)
    total = nearest.get("total", 0)
    return f"当前趋势：{name} · 已满足 {matched}/{total}"


def _nearest_strategy_name(nearest: Any) -> str | None:
    if not isinstance(nearest, dict):
        return None
    name = nearest.get("name")
    return str(name) if name else None


def _conditions_for_strategy(raw_conditions: Any, strategy_name: str | None) -> list[dict[str, Any]]:
    conditions = [
        condition
        for condition in raw_conditions
        if isinstance(condition, dict)
    ]
    if strategy_name is None:
        return conditions
    selected = [
        condition
        for condition in conditions
        if condition.get("strategy") == strategy_name
    ]
    return selected or conditions


def _missing_conditions_summary(conditions: list[dict[str, Any]]) -> str:
    missing = [
        str(condition.get("text"))
        for condition in conditions
        if not condition.get("passed")
    ]
    if not missing:
        return "所有关键条件已满足，等待下一根已收盘 K 线确认或执行。"
    return "还差：" + "、".join(missing)


def _render_strategy_chart(evaluations: list[dict[str, Any]]) -> str:
    evaluation = _latest_chart_evaluation(evaluations)
    if evaluation is None:
        return '<div class="empty">暂无K线图数据</div>'
    rules = _render_core_rules(evaluation.get("core_rules", []))
    chart_timeframes = _chart_timeframes_from_evaluation(evaluation)
    if not chart_timeframes:
        return f'{rules}<div class="empty">K线图数据不足</div>'
    preferred_order = ("4h", "1h", "15m")
    intervals = [
        interval
        for interval in preferred_order
        if interval in chart_timeframes
    ] + [
        interval
        for interval in chart_timeframes
        if interval not in preferred_order
    ]
    tabs = "".join(
        _render_chart_tab(interval=interval, active=index == 0)
        for index, interval in enumerate(intervals)
    )
    panels = "".join(
        _render_chart_panel(
            interval=interval,
            points=chart_timeframes[interval],
            symbol=evaluation.get("symbol"),
            active=index == 0,
        )
        for index, interval in enumerate(intervals)
    )
    return f"""{rules}
<div class="chart-wrap">
  <div class="chart-tabs">{tabs}</div>
  {panels}
</div>"""


def _chart_timeframes_from_evaluation(evaluation: dict[str, Any]) -> dict[str, list[dict[str, Decimal]]]:
    raw_timeframes = evaluation.get("chart_timeframes")
    if isinstance(raw_timeframes, dict):
        chart_timeframes = {
            str(interval): points
            for interval, raw_points in raw_timeframes.items()
            if len(points := _normalise_chart_points(raw_points)) >= 2
        }
        if chart_timeframes:
            return chart_timeframes
    fallback_points = _normalise_chart_points(evaluation.get("chart_points", []))
    if len(fallback_points) < 2:
        return {}
    return {str(evaluation.get("interval") or "15m"): fallback_points}


def _render_chart_tab(interval: str, active: bool) -> str:
    active_class = " active" if active else ""
    chart_id = _chart_id(interval)
    return f'<button class="chart-tab{active_class}" type="button" data-chart-target="{chart_id}">{_escape(interval)}</button>'


def _render_chart_panel(
    interval: str,
    points: list[dict[str, Decimal]],
    symbol: Any,
    active: bool,
) -> str:
    active_class = " active" if active else ""
    chart_id = _chart_id(interval)
    return f"""<div class="chart-panel{active_class}" data-chart-panel="{chart_id}">
  <div class="legend">
    <span class="legend-item"><span class="legend-swatch" style="background:#0a7c52"></span>K线</span>
    <span class="legend-item"><span class="legend-swatch" style="background:#2563eb"></span>EMA50</span>
    <span class="legend-item"><span class="legend-swatch" style="background:#9333ea"></span>EMA200</span>
    <span>{_escape(symbol)} · {_escape(interval)}</span>
  </div>
  {_render_chart_svg(points)}
</div>"""


def _chart_id(interval: str) -> str:
    return f"chart-{''.join(char for char in interval if char.isalnum())}"


def _latest_chart_evaluation(evaluations: list[dict[str, Any]]) -> dict[str, Any] | None:
    chartable = [
        evaluation
        for evaluation in evaluations
        if evaluation.get("chart_timeframes") or evaluation.get("chart_points")
    ]
    if not chartable:
        return None
    return max(chartable, key=lambda item: int(item.get("evaluated_at_ms") or 0))


def _render_core_rules(rules: Any) -> str:
    if not rules:
        return ""
    items = "".join(f"<li>{_escape(rule)}</li>" for rule in rules)
    return f'<ul class="rule-list">{items}</ul>'


def _normalise_chart_points(raw_points: Any) -> list[dict[str, Decimal]]:
    points: list[dict[str, Decimal]] = []
    if not isinstance(raw_points, list):
        return points
    for raw in raw_points:
        if not isinstance(raw, dict):
            continue
        point: dict[str, Decimal] = {}
        for key in ("open", "high", "low", "close", "ema50", "ema200"):
            value = _to_decimal(raw.get(key))
            if value is not None:
                point[key] = value
        if {"open", "high", "low", "close"}.issubset(point):
            points.append(point)
    return points


def _render_chart_svg(points: list[dict[str, Decimal]]) -> str:
    width = 1080
    height = 320
    padding_left = 48
    padding_right = 18
    padding_top = 18
    padding_bottom = 28
    plot_width = width - padding_left - padding_right
    plot_height = height - padding_top - padding_bottom
    values: list[Decimal] = []
    for point in points:
        values.extend([point["high"], point["low"]])
        values.extend(value for key, value in point.items() if key in {"ema50", "ema200"})
    minimum = min(values)
    maximum = max(values)
    if maximum == minimum:
        maximum += Decimal("1")
        minimum -= Decimal("1")

    def x_at(index: int) -> Decimal:
        if len(points) == 1:
            return Decimal(padding_left) + Decimal(plot_width) / Decimal("2")
        return Decimal(padding_left) + Decimal(index) * Decimal(plot_width) / Decimal(len(points) - 1)

    def y_at(value: Decimal) -> Decimal:
        return Decimal(padding_top) + (maximum - value) * Decimal(plot_height) / (maximum - minimum)

    candle_width = max(3, min(9, int(plot_width / max(len(points), 1) * 0.55)))
    candles = []
    for index, point in enumerate(points):
        x = x_at(index)
        open_y = y_at(point["open"])
        close_y = y_at(point["close"])
        high_y = y_at(point["high"])
        low_y = y_at(point["low"])
        color = "#0a7c52" if point["close"] >= point["open"] else "#b42318"
        body_top = min(open_y, close_y)
        body_height = max(abs(close_y - open_y), Decimal("1"))
        candles.append(
            f'<line x1="{_fmt(x)}" y1="{_fmt(high_y)}" x2="{_fmt(x)}" y2="{_fmt(low_y)}" stroke="{color}" stroke-width="1" />'
            f'<rect x="{_fmt(x - Decimal(candle_width) / 2)}" y="{_fmt(body_top)}" width="{candle_width}" height="{_fmt(body_height)}" fill="{color}" />'
        )
    ema50_path = _line_path(points, "ema50", x_at, y_at)
    ema200_path = _line_path(points, "ema200", x_at, y_at)
    grid = _chart_grid(width, padding_left, padding_top, plot_width, plot_height, minimum, maximum)
    return f"""<svg viewBox="0 0 {width} {height}" width="100%" height="320" role="img" aria-label="K线图 EMA50 EMA200">
  <rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff" />
  {grid}
  {''.join(candles)}
  <polyline points="{ema50_path}" fill="none" stroke="#2563eb" stroke-width="2" />
  <polyline points="{ema200_path}" fill="none" stroke="#9333ea" stroke-width="2" />
</svg>"""


def _chart_grid(
    width: int,
    padding_left: int,
    padding_top: int,
    plot_width: int,
    plot_height: int,
    minimum: Decimal,
    maximum: Decimal,
) -> str:
    rows = []
    for index in range(5):
        y = Decimal(padding_top) + Decimal(index) * Decimal(plot_height) / Decimal("4")
        value = maximum - Decimal(index) * (maximum - minimum) / Decimal("4")
        rows.append(
            f'<line x1="{padding_left}" y1="{_fmt(y)}" x2="{padding_left + plot_width}" y2="{_fmt(y)}" stroke="#eef3f9" />'
            f'<text x="8" y="{_fmt(y + Decimal("4"))}" font-size="11" fill="#65748b">{_escape(_fmt(value))}</text>'
        )
    rows.append(f'<line x1="{padding_left}" y1="{padding_top}" x2="{padding_left}" y2="{padding_top + plot_height}" stroke="#d9e0ec" />')
    rows.append(f'<line x1="{padding_left}" y1="{padding_top + plot_height}" x2="{width - 18}" y2="{padding_top + plot_height}" stroke="#d9e0ec" />')
    return "".join(rows)


def _line_path(
    points: list[dict[str, Decimal]],
    key: str,
    x_at: Any,
    y_at: Any,
) -> str:
    pairs = [
        f"{_fmt(x_at(index))},{_fmt(y_at(point[key]))}"
        for index, point in enumerate(points)
        if key in point
    ]
    return " ".join(pairs)


def _to_decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _fmt(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


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


def _action_label(action: Any) -> str:
    if action == "WAIT":
        return "等待"
    if action in {"LONG_ENTRY", "REVERSAL_LONG_ENTRY"}:
        return "做多入场"
    if action in {"SHORT_ENTRY", "REVERSAL_SHORT_ENTRY"}:
        return "做空入场"
    return _escape(action)


def _format_reasons(reasons: Any) -> str:
    if not reasons:
        return "-"
    if isinstance(reasons, list):
        return "；".join(str(reason) for reason in reasons)
    return str(reasons)


def _status_label(status: Any) -> str:
    if status == "RUNNING":
        return "运行中"
    if status == "WAITING_FOR_STATE":
        return "等待状态文件"
    return _escape(status)


def _runtime_seconds(started_at_ms: Any, now_ms: int) -> int:
    if started_at_ms is None:
        return 0
    return max(0, int((now_ms - int(started_at_ms)) / 1000))


def _format_duration(seconds: Any) -> str:
    total_seconds = max(0, int(seconds or 0))
    days, remainder = divmod(total_seconds, 24 * 60 * 60)
    hours, remainder = divmod(remainder, 60 * 60)
    minutes, seconds = divmod(remainder, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days} 天")
    if hours or parts:
        parts.append(f"{hours} 小时")
    if minutes or parts:
        parts.append(f"{minutes} 分钟")
    if not parts:
        parts.append(f"{seconds} 秒")
    return " ".join(parts)


def _read_error_logs(path: Path | None, max_lines: int = 50) -> list[str]:
    if path is None or not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    matched = [line for line in lines if _is_error_log_line(line)]
    return matched[-max_lines:]


def _is_error_log_line(line: str) -> bool:
    lowered = line.lower()
    return (
        "error" in lowered
        or "exception" in lowered
        or "traceback" in lowered
        or "failed" in lowered
        or "historical warmup skipped" in lowered
    )


def _escape(value: Any) -> str:
    return html.escape(str(value))
