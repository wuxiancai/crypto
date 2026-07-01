import html
import json
import os
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
import time
from typing import Any

_SYSTEM_METRICS_LAST_SAMPLE: dict[str, Any] | None = None
_LOG_TIMESTAMP_PATTERN = re.compile(
    r"^\[?(?P<timestamp>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})\]?\s+"
)


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
            "open_positions": [],
            "fills": [],
            "rejected_signals": 0,
            "runtime_seconds": 0,
            "runtime_started_at_ms": None,
            "current_time_ms": now_ms,
            "initial_equity": "1000",
            "last_update_at_ms": None,
            "error_logs": _read_error_logs(error_log_path),
            "signal_evaluations": [],
            "market_prices": {},
            "strategy_details": _default_strategy_details(),
            "system_metrics": _system_metrics_payload(state_path.parent, now_ms),
        }

    payload = _read_status_state_payload(state_path)
    if payload is None:
        return _corrupt_state_payload(
            state_path=state_path,
            now_ms=now_ms,
            error_log_path=error_log_path,
        )
    started_at = payload.get("runtime_started_at_ms")
    signal_evaluations = payload.get("signal_evaluations", [])
    fills = payload.get("fills", [])
    open_position = payload.get("open_position")
    open_positions = payload.get("open_positions")
    if not isinstance(open_positions, list):
        open_positions = [open_position] if isinstance(open_position, dict) else []
    if open_position is None and open_positions:
        open_position = open_positions[0]
    return {
        "status": "RUNNING",
        "state_path": str(state_path),
        "equity": payload.get("equity"),
        "open_position": open_position,
        "open_positions": open_positions,
        "fills": fills,
        "rejected_signals": payload.get("rejected_signals", 0),
        "runtime_seconds": _runtime_seconds(started_at, now_ms),
        "runtime_started_at_ms": started_at,
        "current_time_ms": now_ms,
        "initial_equity": payload.get("initial_equity") or payload.get("starting_equity") or "1000",
        "last_update_at_ms": payload.get("last_update_at_ms"),
        "error_logs": _read_error_logs(
            error_log_path,
            active_after_ms=_int_or_none(payload.get("last_update_at_ms")),
        ),
        "signal_evaluations": signal_evaluations,
        "market_prices": _stored_market_prices(_read_market_price_payload(state_path).get("market_prices"))
        or _stored_market_prices(payload.get("market_prices"))
        or _latest_market_prices(
            evaluations=signal_evaluations,
            open_position=open_position,
            open_positions=open_positions,
            fills=fills,
        ),
        "strategy_details": _strategy_details_from_payload(payload.get("strategy_details")),
        "system_metrics": _system_metrics_payload(state_path.parent, now_ms),
    }


def _read_status_state_payload(state_path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _corrupt_state_payload(
    *,
    state_path: Path,
    now_ms: int,
    error_log_path: Path | None,
) -> dict[str, Any]:
    return {
        "status": "STATE_CORRUPT",
        "state_path": str(state_path),
        "equity": None,
        "open_position": None,
        "open_positions": [],
        "fills": [],
        "rejected_signals": 0,
        "runtime_seconds": 0,
        "runtime_started_at_ms": None,
        "current_time_ms": now_ms,
        "initial_equity": "1000",
        "last_update_at_ms": None,
        "error_logs": [
            f"Paper 状态文件不可解析：{state_path}",
            *_read_error_logs(error_log_path),
        ],
        "signal_evaluations": [],
        "market_prices": _stored_market_prices(_read_market_price_payload(state_path).get("market_prices")),
        "strategy_details": _default_strategy_details(),
        "system_metrics": _system_metrics_payload(state_path.parent, now_ms),
    }


def _read_market_price_payload(state_path: Path) -> dict[str, Any]:
    price_path = state_path.with_name("paper-market-prices.json")
    if not price_path.exists():
        return {}
    try:
        payload = json.loads(price_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def render_paper_status_html(payload: dict[str, Any]) -> str:
    position = payload.get("open_position")
    positions = payload.get("open_positions") or ([position] if position is not None else [])
    fills = list(reversed(payload.get("fills", [])))
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
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
    .nav-button {{ color: #b42318; text-decoration: none; font-weight: 700; border-color: #ef4444; }}
    .ticker-strip {{ flex: 1; min-width: 420px; display: flex; align-items: center; justify-content: center; gap: 8px; flex-wrap: nowrap; }}
    .ticker-item {{ display: inline-flex; align-items: baseline; gap: 6px; padding: 7px 10px; border: 1px solid #d9e0ec; border-radius: 4px; background: #fff; white-space: nowrap; }}
    .ticker-symbol {{ color: #65748b; font-size: 12px; font-weight: 700; }}
    .ticker-price {{ color: #172033; font-size: 16px; font-weight: 700; }}
    .ticker-price-up {{ color: #0a7c52; }}
    .ticker-price-down {{ color: #b42318; }}
    .grid {{ display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }}
    .panel {{ background: #fff; border: 1px solid #d9e0ec; border-radius: 6px; padding: 14px; }}
    .return-panel {{ display: grid; gap: 5px; color: #b42318; font-size: 13px; line-height: 1.35; }}
    .return-title {{ font-weight: 700; }}
    .return-line {{ white-space: nowrap; }}
    .return-profit {{ color: #0a7c52; }}
    .return-loss {{ color: #b42318; }}
    .position-trade-panel {{ display: grid; gap: 12px; }}
    .position-trade-row {{ display: grid; gap: 4px; }}
    .system-metrics {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 5px 10px; font-size: 12px; line-height: 1.35; }}
    .metric-item {{ min-width: 0; }}
    .metric-key {{ color: #65748b; margin-right: 3px; }}
    .metric-value {{ color: #172033; font-weight: 700; white-space: nowrap; }}
    .metric-network {{ grid-column: 1 / -1; }}
    .strategy-detail-panel {{ grid-column: 1 / -1; display: flex; align-items: flex-start; gap: 10px; padding: 7px 10px; overflow: hidden; }}
    .strategy-detail-panel .label {{ flex: 0 0 auto; margin-bottom: 0; line-height: 1.45; }}
    .strategy-detail-grid {{ display: grid; grid-template-columns: 1fr; gap: 4px; flex: 1 1 auto; min-width: 0; }}
    .strategy-detail-block {{ display: flex; align-items: baseline; gap: 8px; flex-wrap: nowrap; white-space: nowrap; min-width: 0; overflow: hidden; font-family: Menlo, Consolas, monospace; font-size: 11px; line-height: 1.45; color: #344055; }}
    .strategy-detail-row {{ display: inline-flex; align-items: baseline; gap: 3px; flex: 0 0 auto; min-width: 0; }}
    .strategy-detail-key {{ color: #65748b; white-space: nowrap; }}
    .strategy-detail-value {{ color: #172033; white-space: nowrap; }}
    .form-grid {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; align-items: end; }}
    .form-field {{ display: grid; gap: 6px; }}
    .form-field label {{ color: #344055; font-size: 13px; font-weight: 700; }}
    .form-field input, .form-field select {{ border: 1px solid #b8c2d6; border-radius: 4px; padding: 8px 10px; font-size: 14px; background: #fff; }}
    .primary-button {{ border: 1px solid #172033; background: #172033; color: #fff; border-radius: 4px; padding: 9px 12px; cursor: pointer; font-weight: 700; }}
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
    .rule-list {{ display: flex; flex-wrap: wrap; gap: 8px 14px; margin: 0 0 12px; padding: 0; list-style: none; color: #344055; font-size: 13px; }}
    .rule-list li {{ white-space: nowrap; }}
    .condition-summary {{ display: grid; gap: 6px; margin-bottom: 12px; }}
    .condition-cards {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }}
    .condition-title {{ color: #172033; font-size: 17px; font-weight: 700; }}
    .condition-missing {{ color: #65748b; font-size: 13px; }}
    .condition-list {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }}
    .condition-row {{ padding: 10px; border: 1px solid #e6ebf2; border-radius: 4px; background: #fff; font-size: 13px; }}
    .condition-status {{ font-weight: 700; white-space: nowrap; }}
    .condition-pass {{ color: #0a7c52; }}
    .condition-fail {{ color: #b42318; }}
    .condition-info {{ color: #65748b; }}
    .condition-detail {{ color: #65748b; overflow-wrap: anywhere; margin-top: 6px; }}
    .condition-detail summary {{ cursor: pointer; color: #65748b; }}
    .chart-wrap {{ background: #fff; border: 1px solid #d9e0ec; border-radius: 6px; padding: 10px; overflow-x: auto; }}
    .interactive-chart {{ cursor: crosshair; touch-action: none; user-select: none; }}
    .chart-tooltip {{ position: fixed; display: none; pointer-events: none; z-index: 40; background: #172033; color: #fff; border: 1px solid rgba(255,255,255,0.14); border-radius: 4px; padding: 8px 10px; font-size: 12px; line-height: 1.55; box-shadow: 0 8px 24px rgba(23,32,51,0.18); white-space: nowrap; }}
    .chart-help {{ color: #65748b; font-size: 12px; margin-left: auto; }}
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
    .price-cell.price-stop {{ color: #b42318; font-weight: 700; }}
    .price-cell.price-target {{ color: #0a7c52; font-weight: 700; }}
    .money-cell {{ color: #175cd3; font-weight: 700; }}
    .trade-scroll {{ max-height: 252px; overflow-y: auto; border: 1px solid #d9e0ec; border-radius: 6px; }}
    .trade-scroll table {{ border: 0; border-radius: 0; }}
    .compact-position th, .compact-position td {{ white-space: normal; }}
    @media (max-width: 820px) {{
      main {{ padding: 14px; }}
      header {{ align-items: flex-start; flex-direction: column; }}
      .header-meta {{ justify-content: flex-start; }}
      .ticker-strip {{ justify-content: flex-start; width: 100%; min-width: 0; overflow-x: auto; }}
      .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .strategy-detail-panel {{ grid-column: 1 / -1; max-height: none; }}
      .strategy-detail-grid {{ grid-template-columns: 1fr; }}
      .condition-list {{ grid-template-columns: 1fr; }}
      .condition-cards {{ grid-template-columns: 1fr; }}
      .table-wrap {{ overflow-x: auto; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>模拟交易看板</h1>
      {_render_market_prices(payload.get("market_prices", {}))}
      <div class="header-meta">
        <a class="badge nav-button" href="/backtest" target="_blank" rel="noopener">策略回测</a>
        <a class="badge" href="/paper/events" target="_blank" rel="noopener">Paper复盘</a>
        <div class="badge">运行时间：{_format_duration(payload.get("runtime_seconds"))}</div>
        <div class="badge">{_status_label(payload.get("status"))}</div>
      </div>
    </header>
    <section class="grid">
      <div class="panel"><div class="label">账户权益 USDT</div><div class="value">{_format_decimal(payload.get("equity"), 2)}</div></div>
      {_render_runtime_return_panel(payload)}
      {_render_position_trade_summary_panel(positions, fills)}
      <div class="panel"><div class="label" id="rejected-signals">拒绝信号</div><div class="value">{_escape(payload.get("rejected_signals"))}</div></div>
      {_render_system_metrics(payload.get("system_metrics", {}))}
      {_render_strategy_details(payload.get("strategy_details", []))}
    </section>
    <section class="panel">
      <h2>持仓情况</h2>
      {_render_positions(positions)}
    </section>
    <section style="margin-top: 16px;">
      <h2>全部模拟交易记录</h2>
      {_render_fills(fills, positions)}
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
    const SVG_NS = "http://www.w3.org/2000/svg";
    const CHART_GEOMETRY = {{ width: 1080, height: 320, left: 48, right: 18, top: 18, bottom: 28 }};
    const chartItemsInGroup = (selector, group) => Array.from(document.querySelectorAll(selector)).filter((item) => (item.getAttribute("data-chart-group") || "default") === group);
    function bindChartTabs() {{
      document.querySelectorAll("[data-chart-target]").forEach((button) => {{
        if (button.dataset.boundChartTab === "1") {{
          return;
        }}
        button.dataset.boundChartTab = "1";
        button.addEventListener("click", () => {{
          activateChart(button);
        }});
      }});
    }}
    function activateChart(button) {{
        const target = button.getAttribute("data-chart-target");
        const group = button.getAttribute("data-chart-group") || "default";
        chartItemsInGroup("[data-chart-target]", group).forEach((item) => item.classList.remove("active"));
        chartItemsInGroup("[data-chart-panel]", group).forEach((item) => item.classList.remove("active"));
        button.classList.add("active");
        const panel = chartItemsInGroup("[data-chart-panel]", group).find((item) => item.getAttribute("data-chart-panel") === target);
        if (panel) {{
          panel.classList.add("active");
        }}
        bindInteractiveCharts();
    }}
    function snapshotActiveCharts() {{
      const active = {{}};
      document.querySelectorAll("[data-chart-target].active").forEach((button) => {{
        active[button.getAttribute("data-chart-group") || "default"] = button.getAttribute("data-chart-target");
      }});
      return active;
    }}
    function restoreActiveCharts(active) {{
      Object.entries(active).forEach(([group, target]) => {{
        const button = chartItemsInGroup("[data-chart-target]", group).find((item) => item.getAttribute("data-chart-target") === target);
        if (button) {{
          activateChart(button);
        }}
      }});
    }}
    function bindInteractiveCharts() {{
      document.querySelectorAll("[data-interactive-chart='1']").forEach((svg) => {{
        if (svg.dataset.boundInteractiveChart !== "1") {{
          svg.dataset.boundInteractiveChart = "1";
          svg.addEventListener("mousemove", (event) => updateChartHover(svg, event));
          svg.addEventListener("mouseleave", () => hideChartHover(svg));
          svg.addEventListener("wheel", (event) => {{
            event.preventDefault();
            if (event.shiftKey) {{
              shiftChartWindow(svg, event.deltaY);
            }} else {{
              zoomChartWindow(svg, event);
            }}
          }}, {{ passive: false }});
        }}
        renderInteractiveChart(svg);
      }});
    }}
    function chartPoints(svg) {{
      try {{
        const parsed = JSON.parse(svg.dataset.chartPoints || "[]");
        return Array.isArray(parsed) ? parsed : [];
      }} catch (_error) {{
        return [];
      }}
    }}
    function chartNumber(value) {{
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : null;
    }}
    function chartPrice(value) {{
      const parsed = chartNumber(value);
      return parsed === null ? "-" : parsed.toFixed(2);
    }}
    function chartTime(value) {{
      const parsed = Number(value);
      if (Number.isFinite(parsed) && parsed > 100000000000) {{
        return new Date(parsed).toLocaleString("zh-CN", {{ hour12: false, timeZone: "Asia/Shanghai" }});
      }}
      return value === undefined || value === null || value === "" ? "-" : String(value);
    }}
    function chartEscape(value) {{
      return String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
    }}
    function chartWindowSize(svg, points) {{
      const configured = Number(svg.dataset.chartWindowSize || svg.dataset.chartDefaultWindowSize || 80);
      const size = Number.isFinite(configured) ? configured : 80;
      return Math.min(points.length, Math.max(12, Math.floor(size)));
    }}
    function chartVisibleSlice(svg) {{
      const points = chartPoints(svg);
      const size = chartWindowSize(svg, points);
      const maxOffset = Math.max(0, points.length - size);
      const offset = Math.min(maxOffset, Math.max(0, Number(svg.dataset.chartOffset || 0)));
      const end = points.length - offset;
      const start = Math.max(0, end - size);
      svg.dataset.chartOffset = String(offset);
      svg.dataset.chartVisibleStart = String(start);
      return {{ all: points, visible: points.slice(start, end), start }};
    }}
    function svgNode(name, attrs) {{
      const node = document.createElementNS(SVG_NS, name);
      Object.entries(attrs || {{}}).forEach(([key, value]) => node.setAttribute(key, String(value)));
      return node;
    }}
    function chartScale(values, plotHeight, top) {{
      let minimum = Math.min(...values);
      let maximum = Math.max(...values);
      if (!Number.isFinite(minimum) || !Number.isFinite(maximum)) {{
        minimum = 0;
        maximum = 1;
      }}
      if (minimum === maximum) {{
        minimum -= 1;
        maximum += 1;
      }}
      const yAt = (value) => top + (maximum - value) * plotHeight / (maximum - minimum);
      return {{ minimum, maximum, yAt }};
    }}
    function renderInteractiveChart(svg) {{
      const slice = chartVisibleSlice(svg);
      const points = slice.visible;
      if (points.length < 2) {{
        return;
      }}
      const geometry = CHART_GEOMETRY;
      const plotWidth = geometry.width - geometry.left - geometry.right;
      const plotHeight = geometry.height - geometry.top - geometry.bottom;
      const values = [];
      points.forEach((point) => {{
        ["high", "low", "ma_fast", "ma_slow"].forEach((key) => {{
          const value = chartNumber(point[key]);
          if (value !== null) {{
            values.push(value);
          }}
        }});
      }});
      const scale = chartScale(values, plotHeight, geometry.top);
      const xAt = (index) => geometry.left + index * plotWidth / Math.max(points.length - 1, 1);
      const candleWidth = Math.max(3, Math.min(9, Math.floor(plotWidth / Math.max(points.length, 1) * 0.55)));
      svg.innerHTML = "";
      svg.appendChild(svgNode("rect", {{ x: 0, y: 0, width: geometry.width, height: geometry.height, fill: "#ffffff" }}));
      for (let index = 0; index < 5; index += 1) {{
        const y = geometry.top + index * plotHeight / 4;
        const value = scale.maximum - index * (scale.maximum - scale.minimum) / 4;
        svg.appendChild(svgNode("line", {{ x1: geometry.left, y1: y.toFixed(2), x2: geometry.left + plotWidth, y2: y.toFixed(2), stroke: "#eef3f9" }}));
        const text = svgNode("text", {{ x: 8, y: (y + 4).toFixed(2), "font-size": 11, fill: "#65748b" }});
        text.textContent = value.toFixed(2);
        svg.appendChild(text);
      }}
      svg.appendChild(svgNode("line", {{ x1: geometry.left, y1: geometry.top, x2: geometry.left, y2: geometry.top + plotHeight, stroke: "#d9e0ec" }}));
      svg.appendChild(svgNode("line", {{ x1: geometry.left, y1: geometry.top + plotHeight, x2: geometry.width - geometry.right, y2: geometry.top + plotHeight, stroke: "#d9e0ec" }}));
      points.forEach((point, index) => {{
        const open = chartNumber(point.open);
        const high = chartNumber(point.high);
        const low = chartNumber(point.low);
        const close = chartNumber(point.close);
        if (open === null || high === null || low === null || close === null) {{
          return;
        }}
        const x = xAt(index);
        const openY = scale.yAt(open);
        const closeY = scale.yAt(close);
        const color = close >= open ? "#0a7c52" : "#b42318";
        svg.appendChild(svgNode("line", {{ x1: x.toFixed(2), y1: scale.yAt(high).toFixed(2), x2: x.toFixed(2), y2: scale.yAt(low).toFixed(2), stroke: color, "stroke-width": 1 }}));
        svg.appendChild(svgNode("rect", {{ x: (x - candleWidth / 2).toFixed(2), y: Math.min(openY, closeY).toFixed(2), width: candleWidth, height: Math.max(Math.abs(closeY - openY), 1).toFixed(2), fill: color }}));
      }});
      [["ma_fast", "#2563eb"], ["ma_slow", "#9333ea"]].forEach(([key, color]) => {{
        const pairs = [];
        points.forEach((point, index) => {{
          const value = chartNumber(point[key]);
          if (value !== null) {{
            pairs.push(xAt(index).toFixed(2) + "," + scale.yAt(value).toFixed(2));
          }}
        }});
        if (pairs.length >= 2) {{
          svg.appendChild(svgNode("polyline", {{ points: pairs.join(" "), fill: "none", stroke: color, "stroke-width": 2 }}));
        }}
      }});
      svg.appendChild(svgNode("line", {{ "data-chart-crosshair-x": "1", x1: geometry.left, y1: geometry.top, x2: geometry.left, y2: geometry.top + plotHeight, stroke: "#172033", "stroke-width": 1, "stroke-dasharray": "4 4", visibility: "hidden", "pointer-events": "none" }}));
      svg.appendChild(svgNode("line", {{ "data-chart-crosshair-y": "1", x1: geometry.left, y1: geometry.top, x2: geometry.left + plotWidth, y2: geometry.top, stroke: "#172033", "stroke-width": 1, "stroke-dasharray": "4 4", visibility: "hidden", "pointer-events": "none" }}));
    }}
    function chartTooltip() {{
      let tooltip = document.querySelector(".chart-tooltip");
      if (!tooltip) {{
        tooltip = document.createElement("div");
        tooltip.className = "chart-tooltip";
        document.body.appendChild(tooltip);
      }}
      return tooltip;
    }}
    function updateChartHover(svg, event) {{
      const slice = chartVisibleSlice(svg);
      const points = slice.visible;
      if (points.length < 2) {{
        return;
      }}
      const geometry = CHART_GEOMETRY;
      const plotWidth = geometry.width - geometry.left - geometry.right;
      const plotHeight = geometry.height - geometry.top - geometry.bottom;
      const rect = svg.getBoundingClientRect();
      const viewX = (event.clientX - rect.left) * geometry.width / rect.width;
      const viewY = (event.clientY - rect.top) * geometry.height / rect.height;
      const nearest = Math.min(points.length - 1, Math.max(0, Math.round((viewX - geometry.left) * (points.length - 1) / plotWidth)));
      const point = points[nearest];
      const x = geometry.left + nearest * plotWidth / Math.max(points.length - 1, 1);
      const crossX = svg.querySelector("[data-chart-crosshair-x]");
      const crossY = svg.querySelector("[data-chart-crosshair-y]");
      if (crossX) {{
        crossX.setAttribute("x1", x.toFixed(2));
        crossX.setAttribute("x2", x.toFixed(2));
        crossX.setAttribute("visibility", "visible");
      }}
      if (crossY) {{
        const y = Math.min(geometry.top + plotHeight, Math.max(geometry.top, viewY));
        crossY.setAttribute("y1", y.toFixed(2));
        crossY.setAttribute("y2", y.toFixed(2));
        crossY.setAttribute("visibility", "visible");
      }}
      const tooltip = chartTooltip();
      const fastLabel = svg.dataset.chartFastLabel || "快线";
      const slowLabel = svg.dataset.chartSlowLabel || "慢线";
      tooltip.innerHTML = "<strong>" + chartEscape(svg.dataset.chartSymbol || "-") + " · " + chartEscape(svg.dataset.chartInterval || "-") + "</strong><br>时间 " + chartEscape(chartTime(point.open_time || point.close_time || point.time)) + "<br>开 " + chartPrice(point.open) + "　高 " + chartPrice(point.high) + "　低 " + chartPrice(point.low) + "　收 " + chartPrice(point.close) + "<br>" + chartEscape(fastLabel) + " " + chartPrice(point.ma_fast) + "　" + chartEscape(slowLabel) + " " + chartPrice(point.ma_slow);
      tooltip.style.display = "block";
      tooltip.style.left = Math.min(window.innerWidth - tooltip.offsetWidth - 12, event.clientX + 14) + "px";
      tooltip.style.top = Math.min(window.innerHeight - tooltip.offsetHeight - 12, event.clientY + 14) + "px";
    }}
    function hideChartHover(svg) {{
      const tooltip = chartTooltip();
      tooltip.style.display = "none";
      ["[data-chart-crosshair-x]", "[data-chart-crosshair-y]"].forEach((selector) => {{
        const line = svg.querySelector(selector);
        if (line) {{
          line.setAttribute("visibility", "hidden");
        }}
      }});
    }}
    function shiftChartWindow(svg, deltaY) {{
      const points = chartPoints(svg);
      const size = chartWindowSize(svg, points);
      const maxOffset = Math.max(0, points.length - size);
      const current = Math.min(maxOffset, Math.max(0, Number(svg.dataset.chartOffset || 0)));
      const next = deltaY > 0 ? current + 6 : current - 6;
      svg.dataset.chartOffset = String(Math.min(maxOffset, Math.max(0, next)));
      renderInteractiveChart(svg);
    }}
    function zoomChartWindow(svg, event) {{
      const points = chartPoints(svg);
      if (points.length < 2) {{
        return;
      }}
      const currentSize = chartWindowSize(svg, points);
      const rect = svg.getBoundingClientRect();
      const geometry = CHART_GEOMETRY;
      const plotWidth = geometry.width - geometry.left - geometry.right;
      const viewX = (event.clientX - rect.left) * geometry.width / rect.width;
      const ratio = Math.min(1, Math.max(0, (viewX - geometry.left) / plotWidth));
      const currentOffset = Math.min(Math.max(0, points.length - currentSize), Math.max(0, Number(svg.dataset.chartOffset || 0)));
      const currentEnd = points.length - currentOffset;
      const currentStart = Math.max(0, currentEnd - currentSize);
      const anchor = currentStart + Math.round(ratio * Math.max(currentSize - 1, 1));
      const nextSizeRaw = event.deltaY > 0 ? currentSize + 10 : currentSize - 10;
      const nextSize = Math.min(points.length, Math.max(12, Math.floor(nextSizeRaw)));
      const nextStart = Math.min(Math.max(0, points.length - nextSize), Math.max(0, anchor - Math.round(ratio * Math.max(nextSize - 1, 1))));
      const nextOffset = Math.max(0, points.length - (nextStart + nextSize));
      svg.dataset.chartWindowSize = String(nextSize);
      svg.dataset.chartOffset = String(nextOffset);
      renderInteractiveChart(svg);
    }}
    async function refreshDashboard() {{
      const activeCharts = snapshotActiveCharts();
      try {{
        const response = await fetch(window.location.href, {{ cache: "no-store" }});
        if (!response.ok) {{
          return;
        }}
        const html = await response.text();
        const nextDocument = new DOMParser().parseFromString(html, "text/html");
        const nextMain = nextDocument.querySelector("main");
        const currentMain = document.querySelector("main");
        if (!nextMain || !currentMain) {{
          return;
        }}
        currentMain.innerHTML = nextMain.innerHTML;
        bindChartTabs();
        restoreActiveCharts(activeCharts);
        bindInteractiveCharts();
        colorTickerPrices();
      }} catch (_error) {{
        return;
      }}
    }}
    const lastTickerPrices = window.__lastTickerPrices || (window.__lastTickerPrices = {{}});
    function colorTickerPrices() {{
      document.querySelectorAll("[data-ticker-symbol]").forEach((node) => {{
        const symbol = node.getAttribute("data-ticker-symbol") || "";
        const price = Number(node.getAttribute("data-ticker-price"));
        if (!symbol || !Number.isFinite(price)) {{
          return;
        }}
        node.classList.remove("ticker-price-up", "ticker-price-down");
        const previous = lastTickerPrices[symbol];
        if (Number.isFinite(previous)) {{
          if (price > previous) {{
            node.classList.add("ticker-price-up");
          }} else if (price < previous) {{
            node.classList.add("ticker-price-down");
          }}
        }}
        lastTickerPrices[symbol] = price;
      }});
    }}
    bindChartTabs();
    bindInteractiveCharts();
    colorTickerPrices();
    setInterval(refreshDashboard, 5000);
  </script>
</body>
</html>"""


def render_strategy_backtest_html(
    result: Any | None = None,
    recent_results: list[Any] | None = None,
    info: Any = None,
) -> str:
    from app.paper.strategy_backtest import StrategyBacktestConfig

    config = result.config if result is not None else StrategyBacktestConfig()
    trades = result.trades if result is not None else []
    error = result.error if result is not None else None
    recent = _sort_recent_backtest_results(recent_results or [])
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>策略回测</title>
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
    .badge {{ font-size: 13px; padding: 6px 10px; border: 1px solid #b8c2d6; border-radius: 4px; background: #fff; color: #344055; text-decoration: none; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }}
    .panel {{ background: #fff; border: 1px solid #d9e0ec; border-radius: 6px; padding: 14px; }}
    .label {{ color: #65748b; font-size: 12px; margin-bottom: 6px; }}
    .value {{ font-size: 20px; font-weight: 700; overflow-wrap: anywhere; }}
    h2 {{ font-size: 16px; margin: 0 0 10px; }}
    .form-grid {{ display: grid; grid-template-columns: 100px 95px 95px 95px 130px 145px 145px 130px; gap: 12px; align-items: end; }}
    .form-field {{ display: grid; gap: 6px; }}
    .form-field label {{ color: #344055; font-size: 13px; font-weight: 700; }}
    .form-field input, .form-field select {{ width: 100%; box-sizing: border-box; border: 1px solid #b8c2d6; border-radius: 4px; padding: 8px 10px; font-size: 14px; background: #fff; }}
    .primary-button {{ border: 1px solid #172033; background: #172033; color: #fff; border-radius: 4px; padding: 9px 12px; cursor: pointer; font-weight: 700; }}
    .secondary-button {{ border: 1px solid #b8c2d6; background: #fff; color: #344055; border-radius: 4px; padding: 9px 12px; cursor: pointer; font-weight: 700; text-decoration: none; }}
    .danger-button {{ border: 1px solid #b42318; background: #b42318; color: #fff; border-radius: 4px; padding: 9px 12px; cursor: pointer; font-weight: 700; text-decoration: none; }}
    .button-row {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-top: 12px; }}
    .info-box {{ color: #0a7c52; padding: 12px 14px; background: #f0fdf8; border: 1px solid #a7f3d0; border-radius: 6px; margin-top: 16px; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d9e0ec; border-radius: 6px; overflow: hidden; }}
    th, td {{ border-bottom: 1px solid #e6ebf2; padding: 9px 10px; text-align: left; font-size: 13px; white-space: nowrap; }}
    th {{ background: #eef3f9; color: #344055; }}
    tr:last-child td {{ border-bottom: 0; }}
    .empty {{ color: #65748b; padding: 14px; background: #fff; border: 1px solid #d9e0ec; border-radius: 6px; }}
    .error-log-line {{ color: #b42318; font-family: Menlo, Consolas, monospace; font-size: 12px; white-space: pre-wrap; overflow-wrap: anywhere; }}
    .profit {{ color: #0a7c52; }}
    .loss {{ color: #b42318; }}
    .trade-scroll {{ max-height: 252px; overflow-y: auto; border: 1px solid #d9e0ec; border-radius: 6px; }}
    .trade-scroll table {{ border: 0; border-radius: 0; }}
    .recent-results-scroll {{ max-height: 410px; overflow-y: auto; border: 1px solid #d9e0ec; border-radius: 6px; }}
    .recent-results-scroll table {{ border: 0; border-radius: 0; }}
    @media (max-width: 820px) {{
      main {{ padding: 14px; }}
      header {{ align-items: flex-start; flex-direction: column; }}
      .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .form-grid {{ grid-template-columns: 1fr; }}
      .table-wrap {{ overflow-x: auto; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>策略回测</h1>
      <div style="display: flex; gap: 8px; flex-wrap: wrap;">
        <a class="badge" href="/backtest/batch" target="_blank" rel="noopener">批量参数回测</a>
        <a class="badge" href="/">返回模拟交易看板</a>
      </div>
    </header>
    <section class="panel">
      <h2>回测参数</h2>
      <form class="form-grid" method="get" action="/backtest">
        <div class="form-field">
          <label for="symbol">交易对</label>
          <select id="symbol" name="symbol">
            {_render_symbol_options(getattr(config, "symbols", ("BTCUSDT",)))}
          </select>
        </div>
        <div class="form-field">
          <label for="fast_ma_type">快线类型</label>
          <select id="fast_ma_type" name="fast_ma_type">
            {_render_average_type_options(getattr(config, "fast_ma_type", "EMA"))}
          </select>
        </div>
        <div class="form-field">
          <label for="ema_fast">快线周期</label>
          <input id="ema_fast" name="ema_fast" type="number" min="2" max="500" value="{_escape(config.ema_fast_period)}">
        </div>
        <div class="form-field">
          <label for="slow_ma_type">慢线类型</label>
          <select id="slow_ma_type" name="slow_ma_type">
            {_render_average_type_options(getattr(config, "slow_ma_type", "EMA"))}
          </select>
        </div>
        <div class="form-field">
          <label for="ema_slow">慢线周期</label>
          <input id="ema_slow" name="ema_slow" type="number" min="3" max="1000" value="{_escape(config.ema_slow_period)}">
        </div>
        <div class="form-field">
          <label for="limit">历史K线根数</label>
          <input id="limit" name="limit" type="number" min="50" max="1500" value="{_escape(config.limit)}">
        </div>
        <div class="form-field">
          <label for="history_period">回测周期</label>
          <select id="history_period" name="history_period">
            {_render_history_period_options(getattr(config, "history_period", "3m"))}
          </select>
        </div>
        <div class="form-field">
          <label for="max_fee_to_risk_ratio">手续费占风险过滤</label>
          <input id="max_fee_to_risk_ratio" name="max_fee_to_risk_ratio" type="number" min="0" max="2" step="0.05" value="{_escape(config.max_fee_to_risk_ratio)}">
        </div>
        <div class="form-field">
          <label for="weekly_risk_pct">周线风险</label>
          <input id="weekly_risk_pct" name="weekly_risk_pct" type="number" min="0" max="0.05" step="0.001" value="{_escape(getattr(config, "weekly_risk_pct", "0.008"))}">
        </div>
        <div class="form-field">
          <label for="daily_risk_pct">日线风险</label>
          <input id="daily_risk_pct" name="daily_risk_pct" type="number" min="0" max="0.05" step="0.001" value="{_escape(getattr(config, "daily_risk_pct", "0.005"))}">
        </div>
        <div class="form-field">
          <label for="h4_risk_pct">4H风险</label>
          <input id="h4_risk_pct" name="h4_risk_pct" type="number" min="0" max="0.05" step="0.0005" value="{_escape(getattr(config, "h4_risk_pct", "0.002"))}">
        </div>
        <div class="form-field">
          <label for="weekly_leverage">周线杠杆</label>
          <input id="weekly_leverage" name="weekly_leverage" type="number" min="1" max="20" step="0.5" value="{_escape(getattr(config, "weekly_leverage", "2"))}">
        </div>
        <div class="form-field">
          <label for="daily_leverage">日线杠杆</label>
          <input id="daily_leverage" name="daily_leverage" type="number" min="1" max="20" step="0.5" value="{_escape(getattr(config, "daily_leverage", "5"))}">
        </div>
        <div class="form-field">
          <label for="h4_leverage">4H杠杆</label>
          <input id="h4_leverage" name="h4_leverage" type="number" min="1" max="20" step="0.5" value="{_escape(getattr(config, "h4_leverage", "10"))}">
        </div>
        <button class="primary-button" type="submit" name="run" value="1">开始回测</button>
      </form>
      <div class="button-row">
        <form method="get" action="/backtest">
          <button class="danger-button" type="submit" name="clear" value="1">清除回测结果</button>
        </form>
      </div>
    </section>
    {_render_info_box(info)}
    {_render_backtest_error(error)}
    <section class="grid" style="margin-top: 16px;">
      <div class="panel"><div class="label">初始权益 USDT</div><div class="value">{_format_decimal(getattr(result, "initial_equity", config.initial_equity), 2)}</div></div>
      <div class="panel"><div class="label">账户权益 USDT</div><div class="value">{_format_decimal(getattr(result, "final_equity", config.initial_equity), 2)}</div></div>
      <div class="panel"><div class="label">总交易次数</div><div class="value">{_escape(getattr(result, "total_trades", 0))}</div></div>
      <div class="panel"><div class="label">胜 / 负 / 胜率</div><div class="value">{_escape(getattr(result, "wins", 0))} / {_escape(getattr(result, "losses", 0))} / 胜率 {_format_win_rate(getattr(result, "wins", 0), getattr(result, "losses", 0))}</div></div>
      <div class="panel"><div class="label">最大回撤</div><div class="value">{_format_decimal(getattr(result, "max_drawdown", "0"), 2)} / {_format_decimal(getattr(result, "max_drawdown_pct", "0"), 2)}%</div></div>
      <div class="panel"><div class="label">盈亏比</div><div class="value">{_escape(getattr(result, "profit_loss_ratio", "0.00"))}</div></div>
    </section>
    <section style="margin-top: 16px;">
      <h2>最近回测结果</h2>
      {_render_recent_backtest_results(recent)}
    </section>
    <section style="margin-top: 16px;">
      <h2>参数组合对比</h2>
      {_render_parameter_comparison_table(recent)}
    </section>
    <section style="margin-top: 16px;">
      <h2>策略 / 层级 / 交易对统计</h2>
      {_render_backtest_metric_tables(result)}
    </section>
    <section style="margin-top: 16px;">
      <h2>全部回测交易记录</h2>
      {_render_backtest_trades(trades)}
    </section>
  </main>
  <script>
    const cleanBacktestUrl = () => {{
      const url = new URL(window.location.href);
      ["run", "clear"].forEach((key) => url.searchParams.delete(key));
      return `${{url.pathname}}${{url.search}}`;
    }};
    if (["run", "clear"].some((key) => new URL(window.location.href).searchParams.has(key))) {{
      window.history.replaceState(null, "", cleanBacktestUrl());
    }}
  </script>
</body>
</html>"""


def render_strategy_backtest_batch_html(
    config: Any | None = None,
    analysis: dict[str, Any] | None = None,
    error: str | None = None,
    info: str | None = None,
    job_status: dict[str, Any] | None = None,
) -> str:
    if config is None:
        from scripts.run_strategy_backtest_batch import StrategyBacktestBatchConfig

        config = StrategyBacktestBatchConfig()
    job = job_status or {}
    effective_analysis = analysis if analysis is not None else job.get("analysis")
    effective_error = error or job.get("error")
    fast_start, fast_end, fast_step = _series_bounds(getattr(config, "fast_periods", (15, 50)))
    slow_start, slow_end, slow_step = _series_bounds(getattr(config, "slow_periods", (30, 200)))
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>批量参数回测</title>
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
    h2 {{ font-size: 16px; margin: 0 0 10px; }}
    .badge {{ font-size: 13px; padding: 6px 10px; border: 1px solid #b8c2d6; border-radius: 4px; background: #fff; color: #344055; text-decoration: none; }}
    .panel {{ background: #fff; border: 1px solid #d9e0ec; border-radius: 6px; padding: 14px; }}
    .batch-summary {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-bottom: 14px; }}
    .summary-item {{ border: 1px solid #d9e0ec; border-radius: 6px; padding: 10px; background: #f8fafc; }}
    .summary-label {{ color: #65748b; font-size: 12px; margin-bottom: 4px; }}
    .summary-value {{ color: #172033; font-size: 14px; font-weight: 700; overflow-wrap: anywhere; }}
    .batch-form {{ display: grid; gap: 14px; }}
    .form-section {{ border: 1px solid #e6ebf2; border-radius: 6px; padding: 12px; margin: 0; min-width: 0; }}
    .form-section legend {{ color: #172033; font-size: 14px; font-weight: 700; padding: 0 6px; }}
    .section-note {{ color: #65748b; font-size: 12px; margin: 0 0 10px; line-height: 1.5; }}
    .form-grid {{ display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; align-items: end; }}
    .form-grid.compact {{ grid-template-columns: repeat(5, minmax(0, 1fr)); }}
    .form-field {{ display: grid; gap: 6px; }}
    .form-field label {{ color: #344055; font-size: 13px; font-weight: 700; display: inline-flex; align-items: center; gap: 5px; position: relative; width: fit-content; }}
    .param-help {{ display: inline-flex; align-items: center; justify-content: center; width: 15px; height: 15px; border-radius: 50%; border: 1px solid #b8c2d6; color: #65748b; background: #fff; font-size: 11px; line-height: 1; cursor: help; }}
    .param-help::after {{ content: attr(data-tooltip); display: none; position: absolute; left: 0; top: 22px; z-index: 20; width: min(320px, 78vw); padding: 10px 12px; border: 1px solid #b8c2d6; border-radius: 6px; background: #172033; color: #fff; font-size: 12px; font-weight: 400; line-height: 1.5; white-space: pre-line; box-shadow: 0 8px 24px rgba(23, 32, 51, 0.18); }}
    .param-help:hover::after, .param-help:focus::after {{ display: block; }}
    .form-field input, .form-field select {{ width: 100%; box-sizing: border-box; border: 1px solid #b8c2d6; border-radius: 4px; padding: 8px 10px; font-size: 14px; background: #fff; }}
    .primary-button {{ border: 1px solid #172033; background: #172033; color: #fff; border-radius: 4px; padding: 9px 12px; cursor: pointer; font-weight: 700; }}
    .danger-button {{ border: 1px solid #b42318; background: #b42318; color: #fff; border-radius: 4px; padding: 9px 12px; cursor: pointer; font-weight: 700; text-decoration: none; }}
    .secondary-button {{ border: 1px solid #b8c2d6; background: #fff; color: #344055; border-radius: 4px; padding: 9px 12px; cursor: pointer; font-weight: 700; text-decoration: none; }}
    .button-row {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
    .batch-actions {{ justify-content: flex-start; }}
    .job-badge {{ font-size: 13px; padding: 7px 10px; border: 1px solid #b8c2d6; border-radius: 4px; background: #fff; color: #344055; }}
    .empty {{ color: #65748b; padding: 14px; background: #fff; border: 1px solid #d9e0ec; border-radius: 6px; }}
    .info-box {{ color: #0a7c52; padding: 12px 14px; background: #f0fdf8; border: 1px solid #a7f3d0; border-radius: 6px; margin-top: 16px; }}
    .error-log-line {{ color: #b42318; font-family: Menlo, Consolas, monospace; font-size: 12px; white-space: pre-wrap; overflow-wrap: anywhere; }}
    .terminal {{ min-height: 360px; max-height: 540px; overflow-y: auto; background: #fff; color: #172033; border: 1px solid #d9e0ec; border-radius: 6px; padding: 12px; font-family: Menlo, Consolas, "Courier New", monospace; font-size: 13px; line-height: 1.45; white-space: pre-wrap; overflow-wrap: anywhere; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d9e0ec; border-radius: 6px; overflow: hidden; }}
    th, td {{ border-bottom: 1px solid #e6ebf2; padding: 9px 10px; text-align: left; font-size: 13px; white-space: nowrap; }}
    th {{ background: #eef3f9; color: #344055; }}
    tr:last-child td {{ border-bottom: 0; }}
    .table-wrap {{ overflow-x: auto; }}
    @media (max-width: 900px) {{
      main {{ padding: 14px; }}
      header {{ align-items: flex-start; flex-direction: column; }}
      .batch-summary {{ grid-template-columns: 1fr; }}
      .form-grid, .form-grid.compact {{ grid-template-columns: 1fr; }}
      .batch-actions {{ grid-column: auto; }}
      .button-row {{ flex-wrap: wrap; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>批量参数回测</h1>
      <a class="badge" href="/backtest">返回策略回测</a>
    </header>
    <section class="panel">
      <h2>批量回测参数</h2>
      <div class="batch-summary">
        <div class="summary-item"><div class="summary-label">策略内核</div><div class="summary-value">WEEKLY_DAILY_H4_V1</div></div>
        <div class="summary-item"><div class="summary-label">策略框架</div><div class="summary-value">1w 周线 + 1d 日线 + 4h 执行</div></div>
        <div class="summary-item"><div class="summary-label">默认均线</div><div class="summary-value">EMA15 / MA60</div></div>
        <div class="summary-item"><div class="summary-label">输出统计</div><div class="summary-value">按策略、层级、交易对聚合</div></div>
      </div>
      <form class="batch-form" method="get" action="/backtest/batch">
        <fieldset class="form-section">
          <legend>基础范围</legend>
          <p class="section-note">先控制交易对、周期和均线搜索空间；2c2g 服务器建议保持较小网格，避免长时间占满资源。</p>
          <div class="form-grid">
            <div class="form-field">
              {_render_batch_field_label("symbol", "交易对")}
              <select id="symbol" name="symbol">{_render_batch_symbol_options(getattr(config, "symbol", "BTCUSDT"))}</select>
            </div>
            <div class="form-field">
              {_render_batch_field_label("history_period", "回测周期")}
              <select id="history_period" name="history_period">{_render_history_period_options(getattr(config, "history_period", "1y"))}</select>
            </div>
            <div class="form-field">
              {_render_batch_field_label("fast_ma_type", "快线类型")}
              <select id="fast_ma_type" name="fast_ma_type">{_render_average_type_options(getattr(config, "fast_ma_type", "EMA"))}</select>
            </div>
            <div class="form-field">{_render_batch_field_label("fast_start", "快线起始")}<input id="fast_start" name="fast_start" type="number" min="2" max="500" value="{_escape(fast_start)}"></div>
            <div class="form-field">{_render_batch_field_label("fast_end", "快线结束")}<input id="fast_end" name="fast_end" type="number" min="2" max="500" value="{_escape(fast_end)}"></div>
            <div class="form-field">{_render_batch_field_label("fast_step", "快线步进")}<input id="fast_step" name="fast_step" type="number" min="1" max="100" value="{_escape(fast_step)}"></div>
            <div class="form-field">
              {_render_batch_field_label("slow_ma_type", "慢线类型")}
              <select id="slow_ma_type" name="slow_ma_type">{_render_average_type_options(getattr(config, "slow_ma_type", "MA"))}</select>
            </div>
            <div class="form-field">{_render_batch_field_label("slow_start", "慢线起始")}<input id="slow_start" name="slow_start" type="number" min="3" max="1000" value="{_escape(slow_start)}"></div>
            <div class="form-field">{_render_batch_field_label("slow_end", "慢线结束")}<input id="slow_end" name="slow_end" type="number" min="3" max="1000" value="{_escape(slow_end)}"></div>
            <div class="form-field">{_render_batch_field_label("slow_step", "慢线步进")}<input id="slow_step" name="slow_step" type="number" min="1" max="200" value="{_escape(slow_step)}"></div>
            <div class="form-field">
              {_render_batch_field_label("skip_fast_gte_slow", "过滤快线>=慢线")}
              <select id="skip_fast_gte_slow" name="skip_fast_gte_slow">{_render_bool_options(getattr(config, "skip_fast_gte_slow", True))}</select>
            </div>
          </div>
        </fieldset>
        <fieldset class="form-section">
          <legend>WEEKLY_DAILY_H4_V1 参数</legend>
          <p class="section-note">这些参数进入周线、日线、4H 三层策略内核；多个值用英文逗号分隔。</p>
          <div class="form-grid compact">
            <div class="form-field">{_render_batch_field_label("atr_periods", "ATR 周期")}<input id="atr_periods" name="atr_periods" value="{_escape(_join_values(getattr(config, "atr_periods", (12, 14))))}"></div>
            <div class="form-field">{_render_batch_field_label("dmi_periods", "DMI 周期")}<input id="dmi_periods" name="dmi_periods" value="{_escape(_join_values(getattr(config, "dmi_periods", (12, 14))))}"></div>
            <div class="form-field">{_render_batch_field_label("swing_lookbacks", "Swing Lookback")}<input id="swing_lookbacks" name="swing_lookbacks" value="{_escape(_join_values(getattr(config, "swing_lookbacks", (20, 30))))}"></div>
            <div class="form-field">{_render_batch_field_label("max_fee_to_risk_ratios", "手续费占风险过滤")}<input id="max_fee_to_risk_ratios" name="max_fee_to_risk_ratios" value="{_escape(_join_values(getattr(config, "max_fee_to_risk_ratios", ("0.25", "0"))))}"></div>
            <div class="form-field">
              {_render_batch_field_label("take_profit_modes", "止盈模式")}
              <select id="take_profit_modes" name="take_profit_modes">{_render_take_profit_mode_options(getattr(config, "take_profit_modes", ("TRAILING", "FIXED")))}</select>
            </div>
          </div>
        </fieldset>
        <fieldset class="form-section">
          <legend>执行控制</legend>
          <p class="section-note">批量任务会复用已有归档，已有相同配置默认跳过；停止会在当前组合结束后的安全点退出。</p>
          <div class="button-row batch-actions">
            <button class="primary-button" type="submit" name="run" value="1">开始批量回测</button>
            <button class="danger-button" type="submit" name="stop" value="1">停止回测</button>
            <button class="secondary-button" type="submit" name="clear" value="1">清除回测结果</button>
            <span class="job-badge" id="batch-job-status">{_escape(_batch_job_status_label(job))}</span>
          </div>
        </fieldset>
      </form>
    </section>
    {_render_backtest_error(effective_error)}
    {_render_info_box(info)}
    <section style="margin-top: 16px;">
      <h2>运行日志</h2>
      <div id="backtest-log-terminal" class="terminal">{_escape(_batch_log_text(job))}</div>
    </section>
    <section style="margin-top: 16px;">
      <h2>批量回测结果</h2>
      <div id="batch-analysis">{_render_batch_analysis(effective_analysis)}</div>
    </section>
  </main>
  <script>
    const pageFinishedAt = {json.dumps(job.get("finished_at_ms"))};
    const cleanBatchUrl = () => {{
      const url = new URL(window.location.href);
      ["run", "stop", "clear"].forEach((key) => url.searchParams.delete(key));
      return url.pathname + (url.search ? url.search : "");
    }};
    if (["run", "stop", "clear"].some((key) => new URL(window.location.href).searchParams.has(key))) {{
      window.history.replaceState(null, "", cleanBatchUrl());
    }}
    async function refreshBatchStatus() {{
      try {{
        const response = await fetch("/api/backtest/batch/status", {{ cache: "no-store" }});
        if (!response.ok) return;
        const payload = await response.json();
        const terminal = document.getElementById("backtest-log-terminal");
        if (terminal) {{
          terminal.textContent = (payload.logs || []).join("\\n") || "等待批量回测启动";
          terminal.scrollTop = terminal.scrollHeight;
        }}
        const status = document.getElementById("batch-job-status");
        if (status) {{
          status.textContent = payload.running ? (payload.stop_requested ? "停止中" : "运行中") : "空闲";
        }}
        if (!payload.running && payload.analysis && payload.finished_at_ms !== pageFinishedAt) {{
          window.location.href = cleanBatchUrl();
        }}
      }} catch (_error) {{
        return;
      }}
    }}
    refreshBatchStatus();
    setInterval(refreshBatchStatus, 2000);
  </script>
</body>
</html>"""


def render_paper_runtime_events_html(
    events: list[Any] | None = None,
    filters: dict[str, str] | None = None,
    error: str | None = None,
) -> str:
    event_rows = events or []
    active_filters = filters or {}
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Paper 复盘</title>
  <style>
    :root {{ color-scheme: light; font-family: Arial, "PingFang SC", "Microsoft YaHei", sans-serif; background: #f5f7fb; color: #172033; }}
    body {{ margin: 0; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
    header {{ display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 18px; }}
    h1 {{ font-size: 24px; margin: 0; }}
    .badge {{ font-size: 13px; padding: 6px 10px; border: 1px solid #b8c2d6; border-radius: 4px; background: #fff; color: #172033; text-decoration: none; }}
    .panel {{ background: #fff; border: 1px solid #d9e0ec; border-radius: 6px; padding: 14px; margin-bottom: 16px; }}
    .form-grid {{ display: grid; grid-template-columns: 90px repeat(6, minmax(0, 1fr)) 100px; gap: 10px; align-items: end; }}
    .form-field {{ display: grid; gap: 6px; }}
    .form-field label {{ color: #344055; font-size: 13px; font-weight: 700; }}
    .form-field input, .form-field select {{ border: 1px solid #b8c2d6; border-radius: 4px; padding: 8px 10px; font-size: 14px; background: #fff; }}
    .primary-button {{ border: 1px solid #172033; background: #172033; color: #fff; border-radius: 4px; padding: 9px 12px; cursor: pointer; font-weight: 700; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d9e0ec; border-radius: 6px; overflow: hidden; }}
    th, td {{ border-bottom: 1px solid #e6ebf2; padding: 9px 10px; text-align: left; font-size: 13px; white-space: nowrap; }}
    th {{ background: #eef3f9; color: #344055; }}
    tr:last-child td {{ border-bottom: 0; }}
    details summary {{ cursor: pointer; color: #65748b; }}
    pre {{ margin: 8px 0 0; white-space: pre-wrap; overflow-wrap: anywhere; font-family: Menlo, Consolas, monospace; font-size: 12px; color: #344055; }}
    .table-wrap {{ overflow-x: auto; }}
    .empty {{ color: #65748b; padding: 14px; background: #fff; border: 1px solid #d9e0ec; border-radius: 6px; }}
    .error {{ color: #b42318; margin-bottom: 12px; }}
    @media (max-width: 820px) {{ main {{ padding: 14px; }} header {{ align-items: flex-start; flex-direction: column; }} .form-grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Paper 复盘</h1>
      <div><a class="badge" href="/">返回看板</a></div>
    </header>
    {_render_paper_runtime_event_help()}
    {_render_paper_runtime_event_shortcuts()}
    {_render_paper_runtime_event_filters(active_filters)}
    {_render_backtest_error(error)}
    {_render_paper_runtime_event_counts(event_rows)}
    {_render_paper_runtime_timelines(event_rows)}
    {_render_paper_runtime_event_table(event_rows)}
  </main>
</body>
</html>"""


def _render_paper_runtime_event_help() -> str:
    return """<section class="panel">
  <h2 style="font-size:16px;margin:0 0 8px;">怎么看复盘</h2>
  <p style="margin:0;color:#344055;line-height:1.7;">这页按时间记录模拟交易系统每根 K 线的处理过程：<strong>策略信号</strong>表示系统判断是否要开仓，<strong>账户快照</strong>表示当时权益和持仓状态，<strong>被拒绝信号</strong>表示出现了信号但风控或仓位规则没有允许开仓，<strong>成交</strong>表示实际模拟开仓或平仓。优先看“摘要”，需要排查细节时再展开“完整原始数据”。</p>
</section>"""


def _render_paper_runtime_event_filters(filters: dict[str, str]) -> str:
    return f"""<section class="panel">
  <form class="form-grid" action="/paper/events" method="get">
    <div class="form-field">
      <label>数量</label>
      <input name="limit" value="{_escape(filters.get("limit", "50"))}">
    </div>
    <div class="form-field">
      <label>事件类型</label>
      <select name="event_type">
        {_event_type_options(filters.get("event_type", ""))}
      </select>
    </div>
    <div class="form-field">
      <label>交易对</label>
      <input name="symbol" value="{_escape(filters.get("symbol", ""))}" placeholder="BTCUSDT">
    </div>
    <div class="form-field">
      <label>策略代码</label>
      <input name="strategy_type" value="{_escape(filters.get("strategy_type", ""))}" placeholder="WEEKLY_SHORT_TREND">
    </div>
    <div class="form-field">
      <label>策略分组</label>
      <input name="bucket" value="{_escape(filters.get("bucket", ""))}" placeholder="WEEKLY">
    </div>
    <div class="form-field">
      <label>开始 UTC+8</label>
      <input name="start_time" value="{_escape(filters.get("start_time", ""))}" placeholder="2026-06-24 08:00">
    </div>
    <div class="form-field">
      <label>结束 UTC+8</label>
      <input name="end_time" value="{_escape(filters.get("end_time", ""))}" placeholder="2026-06-24 23:59">
    </div>
    <button class="primary-button" type="submit">查询</button>
  </form>
</section>"""


def _render_paper_runtime_event_shortcuts() -> str:
    links = [
        ("/paper/events", "全部"),
        ("/paper/events?event_type=fill", "只看成交"),
        ("/paper/events?event_type=blocked_signal", "只看风控阻断"),
        ("/paper/events?event_type=rejected_signal", "只看被拒绝信号"),
        ("/paper/events?event_type=signal", "只看策略信号"),
        ("/paper/events?event_type=snapshot", "只看账户快照"),
    ]
    rendered = "".join(
        f'<a class="badge" href="{_escape(href)}">{_escape(label)}</a>'
        for href, label in links
    )
    return f'<section class="panel" style="display:flex;gap:8px;flex-wrap:wrap;">{rendered}</section>'


def _event_type_options(selected: str) -> str:
    options = [
        ("", "全部"),
        ("signal", "策略信号"),
        ("blocked_signal", "被风控阻断信号"),
        ("rejected_signal", "被拒绝信号"),
        ("fill", "成交"),
        ("snapshot", "账户快照"),
    ]
    return "\n".join(
        f'<option value="{_escape(value)}"{" selected" if value == selected else ""}>{_escape(label)}</option>'
        for value, label in options
    )


def _render_paper_runtime_event_table(events: list[Any]) -> str:
    if not events:
        return '<div class="empty">暂无 Paper 复盘事件</div>'
    rows = "\n".join(_render_paper_runtime_event_row(event) for event in events)
    return f"""<div class="table-wrap">
<table>
  <thead>
    <tr>
      <th>时间 UTC+8</th><th>类型</th><th>交易对</th><th>周期</th><th>策略</th><th>动作</th><th>策略分组</th><th>摘要</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
</div>"""


def _render_paper_runtime_event_counts(events: list[Any]) -> str:
    counts = {event_type: 0 for event_type in ("signal", "blocked_signal", "rejected_signal", "fill", "snapshot")}
    for event in events:
        event_type = str(getattr(event, "event_type", ""))
        if event_type in counts:
            counts[event_type] += 1
    items = "".join(
        f'<span class="badge">{_escape(_event_type_label(event_type))}：{_escape(count)}</span>'
        for event_type, count in counts.items()
    )
    return f'<section class="panel" style="display:flex;gap:8px;flex-wrap:wrap;">{items}</section>'


def _render_paper_runtime_timelines(events: list[Any]) -> str:
    fill_events = [event for event in events if getattr(event, "event_type", "") == "fill"]
    if not fill_events:
        return ""
    sorted_events = sorted(events, key=lambda event: int(getattr(event, "event_time", 0) or 0))
    rows = []
    for fill in fill_events[:20]:
        signal = _nearest_prior_event(sorted_events, fill, "signal")
        snapshot = _nearest_prior_event(sorted_events, fill, "snapshot")
        rows.append(
            "<tr>"
            f"<td>{_escape(_timeline_title(fill))}</td>"
            f"<td>{_escape(_format_event_time_ms(getattr(fill, 'event_time', None)))}</td>"
            f"<td>{_escape(_timeline_signal_summary(signal))}</td>"
            f"<td>{_escape(_timeline_snapshot_summary(snapshot))}</td>"
            f"<td>{_escape('退出成交：' + _paper_runtime_event_summary('fill', getattr(fill, 'payload', '')))}</td>"
            "</tr>"
        )
    return (
        '<section class="panel"><h2 style="font-size:16px;margin:0 0 10px;">交易时间线</h2>'
        '<div class="table-wrap"><table><thead><tr>'
        '<th>交易</th><th>退出时间 UTC+8</th><th>开仓信号</th><th>持仓快照</th><th>退出成交</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div></section>'
    )


def _nearest_prior_event(events: list[Any], fill: Any, event_type: str) -> Any | None:
    fill_time = int(getattr(fill, "event_time", 0) or 0)
    fill_symbol = getattr(fill, "symbol", None)
    fill_strategy = getattr(fill, "strategy_type", None)
    fill_bucket = getattr(fill, "bucket", None)
    candidates = []
    for event in events:
        event_time = int(getattr(event, "event_time", 0) or 0)
        if event_time > fill_time or getattr(event, "event_type", "") != event_type:
            continue
        if getattr(event, "symbol", None) != fill_symbol:
            continue
        if event_type == "signal":
            if getattr(event, "strategy_type", None) != fill_strategy:
                continue
            if getattr(event, "bucket", None) != fill_bucket:
                continue
        candidates.append(event)
    return candidates[-1] if candidates else None


def _timeline_title(fill: Any) -> str:
    return " ".join(
        part
        for part in (
            str(getattr(fill, "symbol", "") or ""),
            str(getattr(fill, "strategy_type", "") or ""),
            str(getattr(fill, "bucket", "") or "-"),
        )
        if part
    )


def _timeline_signal_summary(event: Any | None) -> str:
    if event is None:
        return "开仓信号：-"
    return "开仓信号：" + _paper_runtime_event_summary("signal", getattr(event, "payload", ""))


def _timeline_snapshot_summary(event: Any | None) -> str:
    if event is None:
        return "持仓快照：-"
    return "持仓快照：" + _paper_runtime_event_summary("snapshot", getattr(event, "payload", ""))


def _render_paper_runtime_event_row(event: Any) -> str:
    return f"""<tr>
  <td>{_escape(_format_event_time_ms(getattr(event, "event_time", None)))}</td>
  <td>{_escape(_event_type_label(getattr(event, "event_type", "-")))}</td>
  <td>{_escape(getattr(event, "symbol", "-"))}</td>
  <td>{_escape(getattr(event, "interval", "-"))}</td>
  <td>{_escape(_strategy_type_label(getattr(event, "strategy_type", "-")))}</td>
  <td>{_escape(_action_label(getattr(event, "action", "-")))}</td>
  <td>{_escape(_bucket_label(getattr(event, "bucket", None)))}</td>
  <td>{_render_paper_runtime_event_summary_cell(getattr(event, "event_type", ""), getattr(event, "payload", ""))}</td>
</tr>"""


def _render_paper_runtime_event_summary_cell(event_type: str, payload: str) -> str:
    summary = _paper_runtime_event_summary(event_type, payload)
    pretty_payload = _pretty_event_payload(payload)
    return (
        f"{_escape(summary)}"
        f"<details><summary>完整原始数据</summary><pre>{_escape(pretty_payload)}</pre></details>"
    )


def _paper_runtime_event_summary(event_type: str, payload: str) -> str:
    decoded = _decode_event_payload(payload)
    if event_type == "fill":
        return (
            f"净盈亏={_format_decimal(decoded.get('net_pnl'), 2)}, "
            f"退出原因={_exit_reason_label(decoded.get('exit_reason'))}, "
            f"数量={_format_decimal(decoded.get('quantity'), 4)}"
        )
    if event_type == "blocked_signal":
        nearest = decoded.get("nearest_strategy") or {}
        original_action = nearest.get("original_action", "-") if isinstance(nearest, dict) else "-"
        return f"风控阻断，原始动作={original_action}，原因={_format_reason_list(decoded.get('reason'))}"
    if event_type == "rejected_signal":
        return f"拒绝原因={_format_reason_list(decoded.get('reason'))}"
    if event_type == "snapshot":
        return (
            f"账户权益={_format_decimal(decoded.get('equity'), 2)}, "
            f"持仓数={len(decoded.get('open_positions', []) or [])}, "
            f"累计拒绝={decoded.get('rejected_signals', 0)}"
        )
    if event_type == "signal":
        opened = decoded.get("opened_position")
        opened_label = "是" if opened else "否"
        return f"是否开仓={opened_label}, 原因={_format_reason_list(decoded.get('reason'))}"
    return "-"


def _event_type_label(event_type: Any) -> str:
    labels = {
        "signal": "策略信号",
        "blocked_signal": "被风控阻断信号",
        "rejected_signal": "被拒绝信号",
        "fill": "成交",
        "snapshot": "账户快照",
    }
    key = str(event_type or "")
    return labels.get(key, key or "-")


def _strategy_type_label(strategy_type: Any) -> str:
    labels = {
        "SYSTEM": "系统",
        "WEEKLY_SHORT_TREND": "周线趋势做空",
        "WEEKLY_LONG_TREND": "周线趋势做多",
        "DAILY_SHORT_TREND": "日线顺势做空",
        "DAILY_LONG_TREND": "日线顺势做多",
        "DAILY_LONG_REBOUND": "日线反弹做多",
        "DAILY_SHORT_REBOUND": "日线反弹做空",
        "H4_SHORT_BREAKOUT": "4H突破做空",
        "H4_LONG_BREAKOUT": "4H突破做多",
        "H4_SHORT_CONTINUATION": "4H延续做空",
        "H4_LONG_CONTINUATION": "4H延续做多",
    }
    key = str(strategy_type or "")
    label = labels.get(key)
    if label is None:
        return key or "-"
    return f"{label} ({key})"


def _bucket_label(bucket: Any) -> str:
    labels = {
        "WEEKLY": "周线仓",
        "DAILY": "日线仓",
        "H4": "4H仓",
    }
    key = str(bucket or "")
    if not key:
        return "-"
    label = labels.get(key)
    return f"{label} ({key})" if label else key


def _position_level_label(level: Any) -> str:
    labels = {
        "WEEKLY": "周线",
        "DAILY": "日线",
        "H4": "4H",
    }
    key = str(level or "")
    return labels.get(key, key or "-")


def _trade_mode_label(mode: Any) -> str:
    labels = {
        "TREND": "顺势",
        "REBOUND": "反弹",
        "BREAKOUT": "突破",
        "PULLBACK": "回踩",
        "CONTINUATION": "延续",
    }
    key = str(mode or "")
    return labels.get(key, key or "-")


def _trade_policy_budget_label(mode: Any) -> str:
    key = str(mode or "").upper()
    if key == "REBOUND":
        return "反弹单：结构风险较高 / 风险预算较低"
    if key in {"TREND", "BREAKOUT", "PULLBACK", "CONTINUATION"}:
        return "主方向单：结构风险较低 / 风险预算较高"
    return "-"


def _format_reason_list(reasons: Any) -> str:
    if isinstance(reasons, list):
        values = [str(reason) for reason in reasons if str(reason)]
    elif reasons:
        values = [str(reasons)]
    else:
        values = []
    if not values:
        return "-"
    return "、".join(_reason_label(value) for value in values)


def _reason_label(reason: str) -> str:
    labels = {
        "no actionable signal": "暂无可执行信号",
        "non-entry interval observed": "当前不是入场周期，仅记录状态",
        "waiting for required realtime timeframes": "等待所需周期 K 线齐全",
        "position closed on current kline": "当前 K 线已经平仓，本根不再重新开仓",
        "daily bearish": "日线空头",
        "daily bullish": "日线多头",
        "daily bearish core": "日线核心做空条件成立",
        "daily bullish core": "日线核心做多条件成立",
        "15m bearish entry": "15分钟做空入场条件成立",
        "15m bullish entry": "15分钟做多入场条件成立",
        "4h/1h bearish": "4小时/1小时空头一致",
        "4h/1h bullish": "4小时/1小时多头一致",
        "4h/1h bearish hedge": "4小时/1小时出现空头对冲机会",
        "4h/1h bullish hedge": "4小时/1小时出现多头对冲机会",
        "missing bearish 15m confirmation": "缺少15分钟看跌确认",
        "missing bullish 15m confirmation": "缺少15分钟看涨确认",
        "price not in ema50 pullback zone": "价格不在快线回踩区域",
    }
    return labels.get(reason, reason)


def _decode_event_payload(payload: str) -> dict[str, Any]:
    try:
        decoded = json.loads(payload)
    except (TypeError, json.JSONDecodeError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _pretty_event_payload(payload: str) -> str:
    decoded = _decode_event_payload(payload)
    if not decoded:
        return str(payload or "")
    return json.dumps(decoded, ensure_ascii=False, indent=2, sort_keys=True)


def _format_event_time_ms(value: Any) -> str:
    try:
        timestamp = int(value) / 1000
    except (TypeError, ValueError):
        return "-"
    return datetime.fromtimestamp(timestamp, tz=timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")


def _render_positions(positions: list[dict[str, Any]]) -> str:
    valid_positions = [position for position in positions if isinstance(position, dict)]
    if not valid_positions:
        return '<div class="empty">当前无持仓</div>'
    rows = []
    for position in valid_positions:
        rows.append(
            "<tr>"
            f"<td>{_escape(position.get('symbol'))}</td>"
            f"<td>{_side_label(position.get('side'))}</td>"
            f"<td>{_escape(position.get('strategy_type'))}</td>"
            f"<td>{_escape(position.get('strategy_kernel') or '-')}</td>"
            f"<td>{_position_level_label(position.get('position_level') or position.get('bucket'))}</td>"
            f"<td>{_trade_mode_label(position.get('trade_mode'))}</td>"
            f"<td>{_trade_policy_budget_label(position.get('trade_mode'))}</td>"
            f"<td>{_format_decimal(position.get('entry_price'), 2)}</td>"
            f"<td class=\"price-cell price-stop\">{_format_decimal(_initial_stop_loss_value(position), 2)}</td>"
            f"<td>{_format_decimal(position.get('stop_loss'), 2)}</td>"
            f"<td class=\"price-cell price-target\">{_format_decimal(position.get('take_profit'), 2)}</td>"
            f"<td>{'移动止盈中' if position.get('trailing_active') else '等待激活'}</td>"
            f"<td>{_leverage_label(position.get('leverage'))}</td>"
            f"<td class=\"money-cell\">{_format_notional_usdt(position)}</td>"
            "</tr>"
        )
    return (
        '<div class="table-wrap"><table class="compact-position">'
        "<thead><tr><th>交易对</th><th>方向</th><th>使用策略</th><th>内核</th><th>层级</th><th>模式</th>"
        "<th>结构/预算</th><th>入场</th><th class=\"price-cell price-stop\">初始止损</th><th>当前保护线</th><th class=\"price-cell price-target\">止盈激活价</th><th>止盈逻辑</th><th>杠杆</th><th class=\"money-cell\">USDT</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def _initial_stop_loss_value(position: dict[str, Any]) -> Any:
    return position.get("initial_stop_loss") or position.get("stop_loss")


def _format_notional_usdt(item: dict[str, Any]) -> str:
    price = _decimal_or_none(item.get("entry_price"))
    quantity = _decimal_or_none(item.get("quantity"))
    if price is None or quantity is None:
        return "-"
    return _format_decimal(price * quantity, 2)


def _leverage_label(value: Any) -> str:
    leverage = _decimal_or_none(value) or Decimal("10")
    if leverage == leverage.to_integral_value():
        return f"{format(leverage.quantize(Decimal('1')), 'f')}X"
    return f"{format(leverage.normalize(), 'f')}X"


def _decimal_or_none(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _render_history_period_options(selected: Any) -> str:
    options = [
        ("3m", "最近3个月"),
        ("6m", "最近6个月"),
        ("1y", "1年"),
        ("2y", "最近2年"),
    ]
    selected_value = str(selected or "3m")
    return "".join(
        f'<option value="{_escape(value)}"{_selected_attr(value == selected_value)}>{_escape(label)}</option>'
        for value, label in options
    )


def _render_average_type_options(selected: Any) -> str:
    selected_value = str(selected or "EMA").upper()
    options = ("EMA", "MA")
    return "".join(
        f'<option value="{_escape(value)}"{_selected_attr(value == selected_value)}>{_escape(value)}</option>'
        for value in options
    )


def _render_symbol_options(symbols: Any) -> str:
    selected = "BTCUSDT"
    if isinstance(symbols, (list, tuple)) and symbols:
        selected = str(symbols[0])
    options = [
        ("BTCUSDT", "BTC"),
        ("ETHUSDT", "ETH"),
    ]
    return "".join(
        f'<option value="{_escape(value)}"{_selected_attr(value == selected)}>{_escape(label)}</option>'
        for value, label in options
    )


_BATCH_PARAMETER_HELP = {
    "symbol": "选择参与批量回测的交易对。\n影响：不同币种波动结构不同，同一参数在 BTC/ETH 上可能表现完全不同。\n建议：先用 BTC 验证主策略，再用 ETH 做泛化验证。",
    "history_period": "选择回测使用的历史长度。\n影响：周期越长越能覆盖多种行情，但运行更慢；周期太短容易过拟合最近行情。\n建议：初筛用最近 6 个月或 1 年，最终确认至少看 1 年。",
    "fast_ma_type": "快线均线类型。EMA 对最新价格更敏感，MA 更平滑。\n影响：EMA 更容易提前入场也更容易误触发；MA 更稳但可能错过早段行情。\n建议：当前主线优先 EMA。",
    "fast_start": "快线周期搜索起点。\n影响：数值越小越敏感，交易次数可能更多；数值越大信号更慢。\n建议：围绕 12-20，当前默认 15。",
    "fast_end": "快线周期搜索终点。\n影响：范围越大组合越多、回测越慢，也更容易挑出过拟合参数。\n建议：精调时保持 15-30 内的小范围。",
    "fast_step": "快线周期递增步长。\n影响：步长越小搜索更细但更慢；步长越大可能跳过好参数。\n建议：粗筛用 5，精调用 1-3。",
    "slow_ma_type": "慢线均线类型，用来判断大趋势基准。\n影响：MA 更适合做趋势基准，EMA 会让趋势边界更贴近价格。\n建议：当前主线优先 MA。",
    "slow_start": "慢线周期搜索起点。\n影响：数值越小趋势判断越敏感；数值越大越偏中长期趋势。\n建议：围绕 50-80，当前默认 60。",
    "slow_end": "慢线周期搜索终点。\n影响：范围过大会显著增加组合数量，也可能选出只适合历史的慢线。\n建议：精调时保持 60-120，必要时再扩到 200。",
    "slow_step": "慢线周期递增步长。\n影响：步长越小越细但更慢；步长越大适合快速粗筛。\n建议：粗筛 20-30，精调 5-10。",
    "skip_fast_gte_slow": "是否过滤快线周期大于等于慢线周期的组合。\n影响：开启后避免快慢线逻辑倒置，减少无意义组合。\n建议：保持开启。",
    "atr_periods": "ATR 波动率周期，用于止损距离和回踩区域判断。\n影响：周期小更贴近近期波动但更抖；周期大更稳但止损可能偏宽。\n建议：12-14，当前优先 14。",
    "dmi_periods": "DMI 趋势强度周期，用于过滤趋势质量。\n影响：周期小更敏感，周期大更保守；过大可能错过趋势启动。\n建议：12-14，当前优先 12。",
    "swing_lookbacks": "Swing 高低点回看窗口，用于结构止损和关键高低点判断。\n影响：数值小止损更近、交易更多；数值大止损更宽、胜率可能更稳但盈亏比受影响。\n建议：20-30，当前优先 20。",
    "max_fee_to_risk_ratios": "这是手续费占单笔风险比例的过滤阈值，不是手续费开关。固定手续费始终按 maker 0.02%、taker 0.05% 计入回测。\n影响：数值越低越严格，会过滤掉止损过近、手续费占风险过高的交易；0 只表示不启用这道过滤。\n建议：默认 0.25，并保留 0 作为关闭过滤的对照组。",
    "take_profit_modes": "止盈方式。TRAILING 是移动止盈，FIXED 是固定目标止盈。\n影响：TRAILING 更适合趋势延伸，FIXED 更容易落袋但可能放弃大行情。\n建议：批量对比 TRAILING + FIXED，最终按净盈亏、回撤和盈亏比选择。",
}


def _render_batch_field_label(field_id: str, text: str) -> str:
    help_text = _BATCH_PARAMETER_HELP.get(field_id)
    if not help_text:
        return f'<label for="{_escape(field_id)}">{_escape(text)}</label>'
    escaped_help = _escape(help_text)
    return (
        f'<label for="{_escape(field_id)}">{_escape(text)}'
        f'<span class="param-help" tabindex="0" aria-label="{escaped_help}" '
        f'data-tooltip="{escaped_help}">?</span></label>'
    )


def _render_batch_symbol_options(selected: Any) -> str:
    selected_value = str(selected or "BTCUSDT")
    options = [
        ("BTCUSDT", "BTC"),
        ("ETHUSDT", "ETH"),
    ]
    return "".join(
        f'<option value="{_escape(value)}"{_selected_attr(value == selected_value)}>{_escape(label)}</option>'
        for value, label in options
    )


def _render_bool_options(selected: Any) -> str:
    selected_bool = bool(selected)
    options = [(False, "否"), (True, "是")]
    return "".join(
        f'<option value="{1 if value else 0}"{_selected_attr(value == selected_bool)}>{_escape(label)}</option>'
        for value, label in options
    )


def _render_bool_series_options(selected: Any) -> str:
    selected_value = _bool_series_value(selected)
    options = [
        ("false", "否"),
        ("true", "是"),
        ("false,true", "否 + 是"),
    ]
    return "".join(
        f'<option value="{_escape(value)}"{_selected_attr(value == selected_value)}>{_escape(label)}</option>'
        for value, label in options
    )


def _bool_series_value(selected: Any) -> str:
    values = selected if isinstance(selected, (list, tuple)) else (selected,)
    bools: list[bool] = []
    for value in values:
        if isinstance(value, bool):
            bools.append(value)
            continue
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "是"}:
            bools.append(True)
        elif text in {"0", "false", "no", "否"}:
            bools.append(False)
    unique_values = set(bools)
    if unique_values == {False, True}:
        return "false,true"
    if unique_values == {True}:
        return "true"
    return "false"


def _render_take_profit_mode_options(selected: Any) -> str:
    selected_value = _join_values(selected) or "TRAILING,FIXED"
    options = [
        ("TRAILING", "TRAILING"),
        ("FIXED", "FIXED"),
        ("TRAILING,FIXED", "TRAILING + FIXED"),
    ]
    return "".join(
        f'<option value="{_escape(value)}"{_selected_attr(value == selected_value)}>{_escape(label)}</option>'
        for value, label in options
    )


def _series_bounds(values: Any) -> tuple[int, int, int]:
    numbers = [int(value) for value in values] if isinstance(values, (list, tuple)) else []
    if not numbers:
        return (0, 0, 1)
    if len(numbers) == 1:
        return (numbers[0], numbers[0], 1)
    steps = [right - left for left, right in zip(numbers, numbers[1:]) if right > left]
    step = steps[0] if steps else 1
    return (numbers[0], numbers[-1], step)


def _join_values(values: Any) -> str:
    if not isinstance(values, (list, tuple)):
        return _join_value(values)
    return ",".join(_join_value(value) for value in values)


def _join_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value or "")


def _render_batch_analysis(analysis: dict[str, Any] | None) -> str:
    if not analysis:
        return '<div class="empty">尚未执行批量回测</div>'
    primary = analysis.get("primary") or {}
    refinement = analysis.get("refinement") or {}
    rows = [
        ("主搜索成功/总数", f"{primary.get('success_runs', 0)} / {primary.get('total_runs', 0)}"),
        ("主搜索最佳", _batch_record_line(primary.get("best"))),
        ("精修成功/总数", f"{refinement.get('success_runs', 0)} / {refinement.get('total_runs', 0)}"),
        ("精修最佳", _batch_record_line(refinement.get("best"))),
        ("收益和胜率同时改善", _batch_record_line(refinement.get("best_joint_improvement"))),
    ]
    body = "".join(f"<tr><th>{_escape(label)}</th><td>{_escape(value)}</td></tr>" for label, value in rows)
    return f'<div class="table-wrap"><table><tbody>{body}</tbody></table></div>'


def _batch_job_status_label(job_status: dict[str, Any]) -> str:
    if job_status.get("running"):
        return "停止中" if job_status.get("stop_requested") else "运行中"
    return "空闲"


def _batch_log_text(job_status: dict[str, Any]) -> str:
    logs = job_status.get("logs")
    if isinstance(logs, list) and logs:
        return "\n".join(str(line) for line in logs)
    return "等待批量回测启动"


def _batch_record_line(record: Any) -> str:
    if not isinstance(record, dict):
        return "无"
    params = record.get("params") or {}
    combo = (
        f"{params.get('fast_ma_type', 'EMA')}{params.get('fast_period', '-')}/"
        f"{params.get('slow_ma_type', 'MA')}{params.get('slow_period', '-')}"
    )
    return (
        f"{combo} | final={record.get('final_equity', '-')} | "
        f"pnl={record.get('net_pnl', '-')} | win_rate={record.get('win_rate', '-')}"
    )


def _selected_attr(selected: bool) -> str:
    return " selected" if selected else ""


def _render_fills(fills: list[dict[str, Any]], positions: list[dict[str, Any]] | None = None) -> str:
    open_trades = _open_position_trade_rows(positions or [])
    trade_rows = [*open_trades, *fills]
    if not trade_rows:
        return '<div class="empty">暂无模拟交易记录</div>'
    rows = "\n".join(_render_fill_row(fill) for fill in trade_rows)
    return f"""<div class="table-wrap trade-scroll">
<table>
  <thead>
    <tr>
      <th>交易对</th><th>方向</th><th>使用策略</th><th>开仓时间 UTC+8</th><th>平仓时间 UTC+8</th>
      <th class="price-cell price-stop">开仓价</th><th class="price-cell price-target">平仓价</th><th>杠杆</th><th class="money-cell">USDT</th><th>手续费</th><th>资金费</th><th>净盈亏</th><th>退出原因</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
</div>"""


def _render_backtest_trades(trades: list[dict[str, Any]]) -> str:
    if not trades:
        return '<div class="empty">暂无回测成交</div>'
    rows = "\n".join(_render_fill_row(trade) for trade in trades)
    return f"""<div class="table-wrap trade-scroll">
<table>
  <thead>
    <tr>
      <th>交易对</th><th>方向</th><th>使用策略</th><th>开仓时间 UTC+8</th><th>平仓时间 UTC+8</th>
      <th class="price-cell price-stop">开仓价</th><th class="price-cell price-target">平仓价</th><th>杠杆</th><th class="money-cell">USDT</th><th>手续费</th><th>资金费</th><th>净盈亏</th><th>退出原因</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
</div>"""


def _render_recent_backtest_results(results: list[Any]) -> str:
    if not results:
        return '<div class="empty">暂无历史回测结果</div>'
    rows = "\n".join(_render_recent_backtest_result_row(result) for result in results)
    return f"""<div class="table-wrap recent-results-scroll">
<table>
  <thead>
    <tr>
      <th>回测时间 UTC+8</th><th>交易对</th><th>策略内核</th><th>时间层级</th><th>均线组合</th><th>ATR</th><th>DMI</th><th>Swing</th><th>手续费过滤</th><th>层级风险</th><th>层级杠杆</th><th>止盈</th><th>周期</th>
      <th>初始权益</th><th>账户权益</th><th>总交易次数</th><th>胜 / 负 / 胜率</th><th>净盈亏</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
</div>"""


def _render_parameter_comparison_table(results: list[Any]) -> str:
    if not results:
        return '<div class="empty">暂无参数组合对比</div>'
    rows = "\n".join(
        _render_parameter_comparison_row(index, result)
        for index, result in enumerate(_sort_backtest_results_by_equity(results), start=1)
    )
    return f"""<div class="table-wrap recent-results-scroll">
<table>
  <thead>
    <tr>
      <th>排名</th><th>交易对</th><th>策略内核</th><th>时间层级</th><th>均线组合</th><th>ATR</th><th>DMI</th><th>Swing</th><th>手续费过滤</th><th>层级风险</th><th>层级杠杆</th><th>止盈</th><th>周期</th>
      <th>账户权益</th><th>净盈亏</th><th>胜率</th><th>盈亏比</th><th>最大回撤</th><th>层级净盈亏</th><th>交易次数</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
</div>"""


def _render_parameter_comparison_row(index: int, result: Any) -> str:
    net_pnl = getattr(result, "net_pnl", "0")
    return f"""<tr>
  <td>{_escape(index)}</td>
  <td>{_escape(getattr(result, "symbol", "-"))}</td>
  <td>{_escape(getattr(result, "strategy_kernel", "WEEKLY_DAILY_H4_V1"))}</td>
  <td>{_escape(getattr(result, "timeframes", "1w,1d,4h"))}</td>
  <td>{_escape(_average_combo_label(result))}</td>
  <td>{_escape(getattr(result, "atr_period", "-"))}</td>
  <td>{_escape(getattr(result, "dmi_period", "-"))}</td>
  <td>{_escape(getattr(result, "swing_lookback", "-"))}</td>
  <td>{_escape(_fee_to_risk_label(getattr(result, "max_fee_to_risk_ratio", "-")))}</td>
  <td>{_escape(_level_risk_label(result))}</td>
  <td>{_escape(_level_leverage_label(result))}</td>
  <td>{_escape(getattr(result, "trend_pullback_take_profit_mode", "TRAILING"))}</td>
  <td>{_escape(_history_period_label(getattr(result, "history_period", "")))}</td>
  <td>{_format_decimal(getattr(result, "final_equity", "0"), 2)}</td>
  <td class="{_pnl_class(net_pnl)}">{_format_decimal(net_pnl, 2)}</td>
  <td>{_format_win_rate(getattr(result, "wins", 0), getattr(result, "losses", 0))}</td>
  <td>{_escape(getattr(result, "profit_loss_ratio", "0.00"))}</td>
  <td>{_format_decimal(getattr(result, "max_drawdown", "0"), 2)} / {_format_decimal(getattr(result, "max_drawdown_pct", "0"), 2)}%</td>
  <td>{_render_bucket_comparison_cell(getattr(result, "bucket_metrics", {}) or {})}</td>
  <td>{_escape(getattr(result, "total_trades", 0))}</td>
</tr>"""


def _render_bucket_comparison_cell(metrics: dict[str, dict[str, Any]]) -> str:
    label = _bucket_comparison_label(metrics)
    if not metrics:
        return _escape(label)
    details = "<br>".join(_escape(line) for line in _bucket_comparison_details(metrics))
    return f"{_escape(label)}<details><summary>层级明细</summary>{details}</details>"


def _bucket_comparison_label(metrics: dict[str, dict[str, Any]]) -> str:
    if not metrics:
        return "-"
    parts = []
    for bucket, values in sorted(metrics.items()):
        parts.append(
            f"{bucket} {_format_decimal(values.get('net_pnl'), 2)} ({values.get('trade_count', 0)})"
        )
    return "；".join(parts)


def _bucket_comparison_details(metrics: dict[str, dict[str, Any]]) -> list[str]:
    return [
        (
            f"{bucket}：交易 {values.get('trade_count', 0)}，"
            f"胜/负 {values.get('wins', 0)}/{values.get('losses', 0)}，"
            f"净盈亏 {_format_decimal(values.get('net_pnl'), 2)}"
        )
        for bucket, values in sorted(metrics.items())
    ]


def _render_backtest_metric_tables(result: Any | None) -> str:
    if result is None:
        return '<div class="empty">暂无统计</div>'
    strategy_metrics = getattr(result, "strategy_metrics", {}) or {}
    bucket_metrics = getattr(result, "bucket_metrics", {}) or {}
    symbol_metrics = getattr(result, "symbol_metrics", {}) or {}
    if not strategy_metrics and not bucket_metrics and not symbol_metrics:
        return '<div class="empty">暂无统计</div>'
    return (
        '<div class="table-wrap" style="display: grid; gap: 12px;">'
        f"{_render_metric_table('按策略统计', strategy_metrics, '策略')}"
        f"{_render_metric_table('按层级统计', bucket_metrics, '层级')}"
        f"{_render_metric_table('按交易对统计', symbol_metrics, '交易对')}"
        "</div>"
    )


def _render_metric_table(title: str, metrics: dict[str, dict[str, Any]], first_column: str) -> str:
    if not metrics:
        return f'<div class="empty">{_escape(title)}暂无数据</div>'
    rows = []
    for name, values in sorted(metrics.items()):
        rows.append(
            "<tr>"
            f"<td>{_escape(name)}</td>"
            f"<td>{_escape(values.get('trade_count', 0))}</td>"
            f"<td>{_escape(values.get('wins', 0))}</td>"
            f"<td>{_escape(values.get('losses', 0))}</td>"
            f"<td>{_format_decimal(values.get('net_pnl'), 2)}</td>"
            "</tr>"
        )
    return (
        f'<div><h3 style="font-size:14px;margin:0 0 8px;">{_escape(title)}</h3>'
        "<table><thead><tr>"
        f"<th>{_escape(first_column)}</th><th>交易次数</th><th>胜</th><th>负</th><th>净盈亏</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )


def _render_recent_backtest_result_row(result: Any) -> str:
    net_pnl = getattr(result, "net_pnl", "0")
    pnl_class = _pnl_class(net_pnl)
    wins = getattr(result, "wins", 0)
    losses = getattr(result, "losses", 0)
    return f"""<tr>
  <td>{_escape(_format_datetime(getattr(result, "created_at", None)))}</td>
  <td>{_escape(getattr(result, "symbol", "-"))}</td>
  <td>{_escape(getattr(result, "strategy_kernel", "WEEKLY_DAILY_H4_V1"))}</td>
  <td>{_escape(getattr(result, "timeframes", "1w,1d,4h"))}</td>
  <td>{_escape(_average_combo_label(result))}</td>
  <td>{_escape(getattr(result, "atr_period", "-"))}</td>
  <td>{_escape(getattr(result, "dmi_period", "-"))}</td>
  <td>{_escape(getattr(result, "swing_lookback", "-"))}</td>
  <td>{_escape(_fee_to_risk_label(getattr(result, "max_fee_to_risk_ratio", "-")))}</td>
  <td>{_escape(_level_risk_label(result))}</td>
  <td>{_escape(_level_leverage_label(result))}</td>
  <td>{_escape(getattr(result, "trend_pullback_take_profit_mode", "TRAILING"))}</td>
  <td>{_escape(_history_period_label(getattr(result, "history_period", "")))}</td>
  <td>{_format_decimal(getattr(result, "initial_equity", "0"), 2)}</td>
  <td>{_format_decimal(getattr(result, "final_equity", "0"), 2)}</td>
  <td>{_escape(getattr(result, "total_trades", 0))}</td>
  <td>{_escape(wins)} / {_escape(losses)} / 胜率 {_format_win_rate(wins, losses)}</td>
  <td class="{pnl_class}">{_format_decimal(net_pnl, 2)}</td>
</tr>"""


def _average_combo_label(result: Any) -> str:
    fast_type = str(getattr(result, "fast_ma_type", "EMA") or "EMA").upper()
    slow_type = str(getattr(result, "slow_ma_type", "EMA") or "EMA").upper()
    fast_period = getattr(result, "fast_period", 50)
    slow_period = getattr(result, "slow_period", 200)
    return f"{fast_type}{fast_period} / {slow_type}{slow_period}"


def _fee_to_risk_label(value: Any) -> str:
    text = str(value)
    return "关闭" if text in {"0", "0.0", "0.00"} else text


def _level_risk_label(result: Any) -> str:
    weekly = getattr(result, "weekly_risk_pct", "0.008")
    daily = getattr(result, "daily_risk_pct", "0.005")
    h4 = getattr(result, "h4_risk_pct", "0.002")
    return f"W {weekly} / D {daily} / H4 {h4}"


def _level_leverage_label(result: Any) -> str:
    weekly = getattr(result, "weekly_leverage", "2")
    daily = getattr(result, "daily_leverage", "5")
    h4 = getattr(result, "h4_leverage", "10")
    return f"W {weekly} / D {daily} / H4 {h4}"


def _bool_config_label(value: Any) -> str:
    if isinstance(value, bool):
        return "是" if value else "否"
    text = str(value).strip().lower()
    return "是" if text in {"1", "true", "yes", "是"} else "否"


def _sort_recent_backtest_results(results: list[Any]) -> list[Any]:
    return sorted(
        results,
        key=lambda item: _datetime_sort_key(getattr(item, "created_at", None)),
        reverse=True,
    )


def _sort_backtest_results_by_equity(results: list[Any]) -> list[Any]:
    return sorted(
        results,
        key=lambda item: _decimal_sort_key(getattr(item, "final_equity", "0")),
        reverse=True,
    )


def _decimal_sort_key(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _datetime_sort_key(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return datetime.min.replace(tzinfo=timezone.utc)


def _history_period_label(value: Any) -> str:
    labels = {
        "3m": "最近3个月",
        "6m": "最近6个月",
        "1y": "1年",
        "2y": "最近2年",
    }
    return labels.get(str(value), str(value or "-"))


def _render_backtest_error(error: Any) -> str:
    if not error:
        return ""
    return f"""<section class="panel" style="margin-top: 16px;">
  <h2>错误日志</h2>
  <div class="error-log-line">{_escape(error)}</div>
</section>"""


def _render_info_box(message: Any) -> str:
    if not message:
        return ""
    return f'<div class="info-box">{_escape(message)}</div>'


def _render_error_logs(lines: list[str]) -> str:
    if not lines:
        return '<div class="empty">暂无错误日志</div>'
    rendered = "".join(f'<div class="error-log-line">{_escape(line)}</div>' for line in lines)
    return f'<div class="error-log-box">{rendered}</div>'


def _render_market_prices(prices: dict[str, Any]) -> str:
    symbols = ("BTCUSDT", "ETHUSDT")
    items = "".join(_render_market_price_item(symbol, prices.get(symbol)) for symbol in symbols)
    return f'<div class="ticker-strip">{items}</div>'


def _render_market_price_item(symbol: str, price: Any) -> str:
    formatted = _format_decimal(price, 2)
    decimal_value = _to_decimal(price)
    data_price = f' data-ticker-price="{_escape(decimal_value)}"' if decimal_value is not None else ""
    return f"""<div class="ticker-item">
  <span class="ticker-symbol">{symbol} 永续</span>
  <span class="ticker-price" data-ticker-symbol="{symbol}"{data_price}>{formatted}</span>
</div>"""


def _render_runtime_return_panel(payload: dict[str, Any]) -> str:
    initial_equity = _to_decimal(payload.get("initial_equity")) or Decimal("1000")
    current_equity = _to_decimal(payload.get("equity"))
    started_at_ms = payload.get("runtime_started_at_ms")
    current_time_ms = payload.get("current_time_ms")
    if current_equity is None:
        amount_text = "-"
        rate_text = "-"
        class_name = "return-line"
    else:
        profit = current_equity - initial_equity
        rate = Decimal("0") if initial_equity == 0 else profit * Decimal("100") / initial_equity
        amount_text = f"{_format_decimal(profit, 2)}USDT"
        rate_text = f"{_format_decimal(rate, 2)}%"
        class_name = "return-line return-profit" if profit >= 0 else "return-line return-loss"
    days = _runtime_calendar_days(started_at_ms, current_time_ms)
    return f"""<div class="panel return-panel">
  <div class="return-title">第{days}天收益</div>
  <div class="{class_name}">收益：{amount_text}</div>
  <div class="{class_name}">收益率：{rate_text}</div>
</div>"""


def _render_position_trade_summary_panel(positions: list[dict[str, Any]], fills: list[dict[str, Any]]) -> str:
    return f"""<div class="panel position-trade-panel">
  <div class="position-trade-row"><div class="label">持仓情况</div><div class="value">{_position_title(positions)}</div></div>
  <div class="position-trade-row"><div class="label">模拟交易记录</div><div class="value">{len(fills) + len(positions)}</div></div>
</div>"""


def _runtime_calendar_days(started_at_ms: Any, current_time_ms: Any) -> int:
    try:
        start_ms = int(started_at_ms)
        now_ms = int(current_time_ms)
    except (TypeError, ValueError):
        return 0
    utc_plus_8 = timezone(timedelta(hours=8))
    start_date = datetime.fromtimestamp(start_ms / 1000, tz=utc_plus_8).date()
    now_date = datetime.fromtimestamp(now_ms / 1000, tz=utc_plus_8).date()
    return max(1, (now_date - start_date).days + 1)


def _render_system_metrics(metrics: Any) -> str:
    payload = metrics if isinstance(metrics, dict) else {}
    rows = [
        ("CPU", payload.get("cpu_percent", "-"), ""),
        ("内存", payload.get("memory_available", "-"), ""),
        ("Swap", payload.get("swap_free", "-"), ""),
        ("硬盘", payload.get("disk_free", "-"), ""),
        ("网速", payload.get("network_speed", "-"), " metric-network"),
    ]
    items = "".join(
        f'<div class="metric-item{extra_class}"><span class="metric-key">{_escape(label)}</span><span class="metric-value">{_escape(value)}</span></div>'
        for label, value, extra_class in rows
    )
    return f'<div class="panel"><div class="label">系统性能</div><div class="system-metrics">{items}</div></div>'


def _render_strategy_details(details: list[dict[str, Any]]) -> str:
    effective_details = details or _default_strategy_details()
    blocks = "".join(
        f'<div class="strategy-detail-block">{_render_strategy_detail_rows(detail)}</div>'
        for detail in effective_details
    )
    return f"""<div class="panel strategy-detail-panel">
  <div class="label">当前策略详情</div>
  <div class="strategy-detail-grid">{blocks}</div>
</div>"""


def _render_strategy_detail_rows(detail: dict[str, Any]) -> str:
    labels = (
        ("币种", "symbol"),
        ("快线", "fast_ma"),
        ("慢线", "slow_ma"),
        ("ATR", "atr_period"),
        ("DMI", "dmi_period"),
        ("Swing", "swing_lookback"),
        ("费险", "max_fee_to_risk_ratio"),
        ("止盈", "trend_pullback_take_profit_mode"),
        ("策略内核", "strategy_kernel"),
        ("时间层级", "timeframes"),
    )
    return "".join(
        f'<div class="strategy-detail-row"><span class="strategy-detail-key">{_escape(label)}</span><span class="strategy-detail-value">{_escape(_strategy_detail_value(detail.get(key)))}</span></div>'
        for label, key in labels
    )


def _strategy_detail_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "-"
    return str(value)


def _strategy_details_from_payload(raw_details: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_details, list):
        return _default_strategy_details()
    details = [
        detail
        for detail in raw_details
        if isinstance(detail, dict)
    ]
    return details or _default_strategy_details()


def _default_strategy_details() -> list[dict[str, Any]]:
    return [
        {
            "symbol": symbol,
            "fast_ma": "EMA15",
            "slow_ma": "MA60",
            "atr_period": "14",
            "dmi_period": "12",
            "swing_lookback": "20",
            "max_fee_to_risk_ratio": "0.25",
            "trend_pullback_take_profit_mode": "TRAILING",
            "strategy_kernel": "WEEKLY_DAILY_H4_V1",
            "timeframes": "1w,1d,4h",
        }
        for symbol in ("BTCUSDT", "ETHUSDT")
    ]


def _stored_market_prices(raw_prices: Any) -> dict[str, Any]:
    if not isinstance(raw_prices, dict):
        return {}
    prices: dict[str, Any] = {}
    for symbol, raw_value in raw_prices.items():
        if isinstance(raw_value, dict):
            price = raw_value.get("price")
        else:
            price = raw_value
        if price is not None:
            prices[str(symbol)] = price
    return prices


def _latest_market_prices(
    evaluations: Any,
    open_position: Any,
    open_positions: Any,
    fills: Any,
) -> dict[str, Any]:
    prices: dict[str, Any] = {}
    timestamps: dict[str, int] = {}
    for fill in fills if isinstance(fills, list) else []:
        if not isinstance(fill, dict):
            continue
        symbol = str(fill.get("symbol") or "")
        if not symbol:
            continue
        exit_time = int(fill.get("exit_time") or 0)
        if exit_time >= timestamps.get(symbol, -1):
            prices[symbol] = fill.get("exit_price")
            timestamps[symbol] = exit_time
    if isinstance(open_position, dict):
        symbol = str(open_position.get("symbol") or "")
        if symbol:
            prices[symbol] = open_position.get("entry_price")
            timestamps[symbol] = int(open_position.get("entry_time") or 0)
    for position in open_positions if isinstance(open_positions, list) else []:
        if not isinstance(position, dict):
            continue
        symbol = str(position.get("symbol") or "")
        if not symbol:
            continue
        entry_time = int(position.get("entry_time") or 0)
        if entry_time >= timestamps.get(symbol, -1):
            prices[symbol] = position.get("entry_price")
            timestamps[symbol] = entry_time
    for evaluation in evaluations if isinstance(evaluations, list) else []:
        if not isinstance(evaluation, dict):
            continue
        symbol = str(evaluation.get("symbol") or "")
        if not symbol:
            continue
        evaluated_at = int(evaluation.get("evaluated_at_ms") or 0)
        price = _evaluation_latest_price(evaluation)
        if price is not None and evaluated_at >= timestamps.get(symbol, -1):
            prices[symbol] = price
            timestamps[symbol] = evaluated_at
    return prices


def _evaluation_latest_price(evaluation: dict[str, Any]) -> Any:
    if evaluation.get("close") is not None:
        return evaluation.get("close")
    raw_timeframes = evaluation.get("chart_timeframes")
    if isinstance(raw_timeframes, dict):
        for interval in ("15m", "1h", "4h"):
            raw_points = raw_timeframes.get(interval)
            if isinstance(raw_points, list) and raw_points:
                last_point = raw_points[-1]
                if isinstance(last_point, dict) and last_point.get("close") is not None:
                    return last_point.get("close")
    raw_points = evaluation.get("chart_points")
    if isinstance(raw_points, list) and raw_points:
        last_point = raw_points[-1]
        if isinstance(last_point, dict):
            return last_point.get("close")
    return None


def _render_strategy_conditions(evaluations: list[dict[str, Any]]) -> str:
    latest = _latest_condition_evaluations_by_symbol(evaluations)
    if not latest:
        return '<div class="empty">暂无策略触发条件：等待实时策略评估更新</div>'
    rendered = [
        _render_strategy_condition_card(evaluation)
        for evaluation in latest
    ]
    rendered = [card for card in rendered if card]
    if not rendered:
        return '<div class="empty">暂无策略触发条件：等待实时策略评估更新</div>'
    return f'<div class="condition-cards">{"".join(rendered)}</div>'


def _render_strategy_condition_card(evaluation: dict[str, Any]) -> str:
    nearest = evaluation.get("nearest_strategy", {})
    strategy_name = _nearest_strategy_name(nearest)
    conditions = _conditions_for_strategy(evaluation.get("condition_statuses", []), strategy_name)
    if not conditions:
        return ""
    display_nearest = _nearest_strategy_for_conditions(nearest, conditions)
    rows = "".join(_render_condition_row(condition) for condition in conditions)
    return f"""<div class="panel">
  <div class="condition-summary">
    <div class="condition-title">{_escape(_nearest_strategy_summary(display_nearest, evaluation.get("symbol")))}</div>
    <div class="condition-missing">{_escape(_missing_conditions_summary(conditions))}</div>
  </div>
  <div class="condition-list">{rows}</div>
</div>"""


def _latest_condition_evaluations_by_symbol(evaluations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for evaluation in evaluations:
        if not evaluation.get("condition_statuses"):
            continue
        symbol = str(evaluation.get("symbol") or "-")
        current = latest.get(symbol)
        if current is None or int(evaluation.get("evaluated_at_ms") or 0) >= int(current.get("evaluated_at_ms") or 0):
            latest[symbol] = evaluation
    return sorted(
        latest.values(),
        key=lambda item: str(item.get("symbol") or ""),
    )


def _render_condition_row(condition: dict[str, Any]) -> str:
    passed = bool(condition.get("passed"))
    required = bool(condition.get("required", True))
    status_class = "condition-pass" if passed else ("condition-fail" if required else "condition-info")
    return f"""<div class="condition-row">
  <div><span class="condition-status {status_class}">{_condition_status_label(passed, required)}</span> {_escape(condition.get("text"))}</div>
  <details class="condition-detail"><summary>计算明细</summary>{_escape(condition.get("detail"))}</details>
</div>"""


def _condition_status_label(passed: bool, required: bool = True) -> str:
    if passed:
        return "满足"
    return "未满足" if required else "观察"


def _nearest_strategy_summary(nearest: Any, symbol: Any = None) -> str:
    if not isinstance(nearest, dict) or not nearest:
        return "当前趋势：暂无"
    name = _strategy_condition_group_label(nearest.get("name")) or "-"
    matched = nearest.get("matched", 0)
    total = nearest.get("total", 0)
    prefix = f"{symbol} " if symbol else ""
    return f"当前趋势：{prefix}{name} · 已满足 {matched}/{total}"


def _nearest_strategy_name(nearest: Any) -> str | None:
    if not isinstance(nearest, dict):
        return None
    name = nearest.get("name")
    return str(name) if name else None


def _conditions_for_strategy(raw_conditions: Any, strategy_name: str | None) -> list[dict[str, Any]]:
    conditions = [
        normalized
        for condition in raw_conditions
        if isinstance(condition, dict)
        for normalized in [_normalize_condition(condition)]
        if normalized is not None and normalized.get("required", True)
    ]
    if strategy_name is None:
        return conditions
    selected = [
        condition
        for condition in conditions
        if condition.get("strategy") == strategy_name
    ]
    return selected or conditions


def _nearest_strategy_for_conditions(nearest: Any, conditions: list[dict[str, Any]]) -> Any:
    if not conditions:
        return nearest
    if not isinstance(nearest, dict):
        return nearest
    condition_strategy = conditions[0].get("strategy")
    if not condition_strategy:
        return nearest
    required = [condition for condition in conditions if condition.get("required", True)]
    rendered_matched = sum(1 for condition in required if condition.get("passed"))
    rendered_total = len(required)
    name = str(nearest.get("name") or "")
    matched = int(nearest.get("matched") or 0)
    total = int(nearest.get("total") or 0)
    if name == "SYSTEM" and matched == 0 and total == 0:
        return {
            **nearest,
            "name": condition_strategy,
            "matched": rendered_matched,
            "total": rendered_total,
        }
    if name == condition_strategy and (matched != rendered_matched or total != rendered_total):
        return {
            **nearest,
            "matched": rendered_matched,
            "total": rendered_total,
        }
    return nearest


def _normalize_condition(condition: dict[str, Any]) -> dict[str, Any] | None:
    strategy = condition.get("strategy") or condition.get("strategy_type")
    text = condition.get("text") or _strategy_condition_text(strategy)
    if not text:
        return None
    detail = condition.get("detail")
    if isinstance(detail, (list, tuple)):
        detail = "; ".join(str(item) for item in detail)
    elif detail is None:
        detail = "-"
    normalized = dict(condition)
    normalized["strategy"] = str(strategy) if strategy else "-"
    normalized["text"] = _normalize_condition_text(str(text))
    normalized["detail"] = str(detail)
    return normalized


def _normalize_condition_text(text: str) -> str:
    return text


def _append_condition_detail(detail: str, addition: str) -> str:
    if not detail or detail == "-":
        return addition
    if addition in detail:
        return detail
    return f"{detail}; {addition}"


def _strategy_condition_text(strategy: Any) -> str:
    labels = {
        "WEEKLY": "周线大环境",
        "DAILY": "日线战术层",
        "H4": "4H执行层",
    }
    return labels.get(str(strategy or ""), "")


def _strategy_condition_group_label(strategy: Any) -> str:
    labels = {
        "WEEKLY": "周线仓",
        "DAILY": "日线仓",
        "H4": "4H仓",
        "SYSTEM": "系统",
    }
    key = str(strategy or "")
    return labels.get(key, key)


def _missing_conditions_summary(conditions: list[dict[str, Any]]) -> str:
    missing = [
        str(condition.get("text"))
        for condition in conditions
        if condition.get("required", True) and not condition.get("passed") and condition.get("text")
    ]
    if not missing:
        return "所有关键条件已满足，等待下一根已收盘 K 线确认或执行。"
    return "还差：" + "、".join(missing)


def _render_strategy_chart(evaluations: list[dict[str, Any]]) -> str:
    evaluations_by_symbol = _latest_chart_evaluations_by_symbol(evaluations)
    if not evaluations_by_symbol:
        return '<div class="empty">暂无K线图数据：等待实时策略评估更新</div>'
    if len(evaluations_by_symbol) == 1:
        evaluation = evaluations_by_symbol[0]
        rules = _render_core_rules(evaluation.get("core_rules", []))
        chart_timeframes = _chart_timeframes_from_evaluation(evaluation)
        if not chart_timeframes:
            return f'{rules}<div class="empty">K线图数据不足</div>'
        return f"""{rules}
<div class="chart-wrap">
  {_render_chart_controls_and_panels(evaluation=evaluation, chart_timeframes=chart_timeframes, symbol_scoped=False)}
</div>"""

    symbol_tabs = "".join(
        _render_chart_symbol_tab(symbol=str(evaluation.get("symbol") or "UNKNOWN"), active=index == 0)
        for index, evaluation in enumerate(evaluations_by_symbol)
    )
    symbol_panels = "".join(
        _render_chart_symbol_panel(evaluation=evaluation, active=index == 0)
        for index, evaluation in enumerate(evaluations_by_symbol)
    )
    return f"""<div class="chart-wrap">
  <div class="chart-tabs">{symbol_tabs}</div>
  {symbol_panels}
</div>"""


def _render_chart_symbol_panel(evaluation: dict[str, Any], active: bool) -> str:
    rules = _render_core_rules(evaluation.get("core_rules", []))
    chart_timeframes = _chart_timeframes_from_evaluation(evaluation)
    if not chart_timeframes:
        return f'{rules}<div class="empty">K线图数据不足</div>'
    active_class = " active" if active else ""
    symbol = str(evaluation.get("symbol") or "UNKNOWN")
    group = f"chart-{_safe_chart_key(symbol)}"
    return f"""<div class="chart-panel{active_class}" data-chart-panel="{_symbol_panel_id(symbol)}" data-chart-group="chart-symbols">
  {rules}
  {_render_chart_controls_and_panels(evaluation=evaluation, chart_timeframes=chart_timeframes, symbol_scoped=True, group=group)}
</div>"""


def _render_chart_controls_and_panels(
    evaluation: dict[str, Any],
    chart_timeframes: dict[str, list[dict[str, Any]]],
    symbol_scoped: bool,
    group: str = "default",
) -> str:
    preferred_order = ("1d", "4h", "1h", "15m")
    intervals = [
        interval
        for interval in preferred_order
        if interval in chart_timeframes
    ] + [
        interval
        for interval in chart_timeframes
        if interval not in preferred_order
    ]
    active_interval = "15m" if "15m" in intervals else (intervals[0] if intervals else "")
    symbol = str(evaluation.get("symbol") or "UNKNOWN")
    tabs = "".join(
        _render_chart_tab(interval=interval, active=interval == active_interval, symbol=symbol if symbol_scoped else None, group=group)
        for interval in intervals
    )
    panels = "".join(
        _render_chart_panel(
            interval=interval,
            points=chart_timeframes[interval],
            symbol=symbol,
            active=interval == active_interval,
            symbol_scoped=symbol_scoped,
            group=group,
        )
        for interval in intervals
    )
    return f"""<div class="chart-tabs">{tabs}</div>
  {panels}"""


def _chart_timeframes_from_evaluation(evaluation: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
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


def _render_chart_tab(interval: str, active: bool, symbol: str | None = None, group: str = "default") -> str:
    active_class = " active" if active else ""
    chart_id = _chart_id(interval, symbol=symbol)
    return f'<button class="chart-tab{active_class}" type="button" data-chart-target="{chart_id}" data-chart-group="{_escape(group)}">{_escape(interval)}</button>'


def _render_chart_symbol_tab(symbol: str, active: bool) -> str:
    active_class = " active" if active else ""
    return f'<button class="chart-tab{active_class}" type="button" data-chart-target="{_symbol_panel_id(symbol)}" data-chart-group="chart-symbols">{_escape(symbol)}</button>'


def _render_chart_panel(
    interval: str,
    points: list[dict[str, Any]],
    symbol: Any,
    active: bool,
    symbol_scoped: bool = False,
    group: str = "default",
) -> str:
    active_class = " active" if active else ""
    chart_id = _chart_id(interval, symbol=str(symbol) if symbol_scoped else None)
    fast_label, slow_label = _chart_average_labels(points)
    return f"""<div class="chart-panel{active_class}" data-chart-panel="{chart_id}" data-chart-group="{_escape(group)}">
  <div class="legend">
    <span class="legend-item"><span class="legend-swatch" style="background:#0a7c52"></span>K线</span>
    <span class="legend-item"><span class="legend-swatch" style="background:#2563eb"></span>{_escape(fast_label)}</span>
    <span class="legend-item"><span class="legend-swatch" style="background:#9333ea"></span>{_escape(slow_label)}</span>
    <span>{_escape(symbol)} · {_escape(interval)}</span>
    <span class="chart-help">悬停查看详情，滚轮缩放K线，Shift+滚轮平移</span>
  </div>
  {_render_chart_svg(points, fast_label=fast_label, slow_label=slow_label, symbol=str(symbol), interval=interval)}
</div>"""


def _chart_id(interval: str, symbol: str | None = None) -> str:
    interval_key = _safe_chart_key(interval)
    if symbol is None:
        return f"chart-{interval_key}"
    return f"chart-{_safe_chart_key(symbol)}-{interval_key}"


def _symbol_panel_id(symbol: str) -> str:
    return f"symbol-{_safe_chart_key(symbol)}"


def _safe_chart_key(value: str) -> str:
    return "".join(char for char in value if char.isalnum())


def _latest_chart_evaluations_by_symbol(evaluations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for evaluation in evaluations:
        if not (evaluation.get("chart_timeframes") or evaluation.get("chart_points")):
            continue
        symbol = str(evaluation.get("symbol") or "UNKNOWN")
        current = latest.get(symbol)
        if current is None or int(evaluation.get("evaluated_at_ms") or 0) >= int(current.get("evaluated_at_ms") or 0):
            latest[symbol] = evaluation
    return [latest[symbol] for symbol in sorted(latest)]


def _render_core_rules(rules: Any) -> str:
    if not rules:
        return ""
    items = "".join(f"<li>{_escape(rule)}</li>" for rule in rules)
    return f'<ul class="rule-list">{items}</ul>'


def _normalise_chart_points(raw_points: Any) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    if not isinstance(raw_points, list):
        return points
    for raw in raw_points:
        if not isinstance(raw, dict):
            continue
        point: dict[str, Any] = {}
        for key in ("open", "high", "low", "close"):
            value = _to_decimal(raw.get(key))
            if value is not None:
                point[key] = value
        fast_value = _to_decimal(raw.get("ma_fast", raw.get("ema50")))
        slow_value = _to_decimal(raw.get("ma_slow", raw.get("ema200")))
        if fast_value is not None:
            point["ma_fast"] = fast_value
        if slow_value is not None:
            point["ma_slow"] = slow_value
        for time_key in ("open_time", "close_time", "time"):
            if raw.get(time_key) is not None:
                point[time_key] = raw.get(time_key)
        point["fast_ma_label"] = str(raw.get("fast_ma_label") or "EMA15")
        point["slow_ma_label"] = str(raw.get("slow_ma_label") or "MA60")
        if {"open", "high", "low", "close"}.issubset(point):
            points.append(point)
    return points


def _chart_average_labels(points: list[dict[str, Any]]) -> tuple[str, str]:
    for point in points:
        fast_label = str(point.get("fast_ma_label") or "").strip()
        slow_label = str(point.get("slow_ma_label") or "").strip()
        if fast_label or slow_label:
            return fast_label or "EMA15", slow_label or "MA60"
    return "EMA15", "MA60"


def _render_chart_svg(points: list[dict[str, Any]], fast_label: str, slow_label: str, symbol: str, interval: str) -> str:
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
        values.extend(value for key, value in point.items() if key in {"ma_fast", "ma_slow"})
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
    fast_path = _line_path(points, "ma_fast", x_at, y_at)
    slow_path = _line_path(points, "ma_slow", x_at, y_at)
    fast_line = f'<polyline points="{fast_path}" fill="none" stroke="#2563eb" stroke-width="2" />' if fast_path else ""
    slow_line = f'<polyline points="{slow_path}" fill="none" stroke="#9333ea" stroke-width="2" />' if slow_path else ""
    grid = _chart_grid(width, padding_left, padding_top, plot_width, plot_height, minimum, maximum)
    chart_points = _chart_points_json(points)
    return f"""<svg class="interactive-chart" viewBox="0 0 {width} {height}" width="100%" height="320" role="img" aria-label="K线图 {_escape(fast_label)} {_escape(slow_label)}" data-interactive-chart="1" data-chart-points="{chart_points}" data-chart-default-window-size="80" data-chart-window-size="80" data-chart-offset="0" data-chart-symbol="{_escape(symbol)}" data-chart-interval="{_escape(interval)}" data-chart-fast-label="{_escape(fast_label)}" data-chart-slow-label="{_escape(slow_label)}">
  <rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff" />
  {grid}
  {''.join(candles)}
  {fast_line}
  {slow_line}
  <line data-chart-crosshair-x="1" x1="{padding_left}" y1="{padding_top}" x2="{padding_left}" y2="{padding_top + plot_height}" stroke="#172033" stroke-width="1" stroke-dasharray="4 4" visibility="hidden" pointer-events="none" />
  <line data-chart-crosshair-y="1" x1="{padding_left}" y1="{padding_top}" x2="{padding_left + plot_width}" y2="{padding_top}" stroke="#172033" stroke-width="1" stroke-dasharray="4 4" visibility="hidden" pointer-events="none" />
</svg>"""


def _chart_points_json(points: list[dict[str, Any]]) -> str:
    payload: list[dict[str, Any]] = []
    for point in points:
        item: dict[str, Any] = {}
        for key in ("open_time", "close_time", "time"):
            if point.get(key) is not None:
                item[key] = point.get(key)
        for key in ("open", "high", "low", "close", "ma_fast", "ma_slow"):
            if key in point:
                item[key] = _fmt(point[key])
        item["fast_ma_label"] = str(point.get("fast_ma_label") or "EMA15")
        item["slow_ma_label"] = str(point.get("slow_ma_label") or "MA60")
        payload.append(item)
    return _escape(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


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
    points: list[dict[str, Any]],
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


def _open_position_trade_rows(positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for position in positions:
        if not isinstance(position, dict):
            continue
        rows.append(
            {
                "symbol": position.get("symbol"),
                "side": position.get("side"),
                "strategy_type": position.get("strategy_type"),
                "strategy_kernel": position.get("strategy_kernel"),
                "position_level": position.get("position_level"),
                "trade_mode": position.get("trade_mode"),
                "market_regime": position.get("market_regime"),
                "lifecycle_state": position.get("lifecycle_state"),
                "entry_time": position.get("entry_time"),
                "exit_time": None,
                "entry_price": position.get("entry_price"),
                "exit_price": None,
                "quantity": position.get("quantity"),
                "leverage": position.get("leverage"),
                "fees": position.get("entry_fee"),
                "funding_fee": None,
                "net_pnl": None,
                "exit_reason": "OPEN",
            }
        )
    return rows


def _render_fill_row(fill: dict[str, Any]) -> str:
    pnl = str(fill.get("net_pnl", "0"))
    pnl_class = "loss" if pnl.startswith("-") else "profit"
    strategy_cell = _trade_identity_label(fill)
    return f"""<tr>
  <td>{_escape(fill.get("symbol"))}</td>
  <td>{_side_label(fill.get("side"))}</td>
  <td>{strategy_cell}</td>
  <td>{_format_time_ms(fill.get("entry_time"))}</td>
  <td>{_format_time_ms(fill.get("exit_time"))}</td>
  <td class="price-cell price-stop">{_format_decimal(fill.get("entry_price"), 2)}</td>
  <td class="price-cell price-target">{_format_decimal(fill.get("exit_price"), 2)}</td>
  <td>{_leverage_label(fill.get("leverage"))}</td>
  <td class="money-cell">{_format_notional_usdt(fill)}</td>
  <td>{_format_decimal(fill.get("fees"), 2)}</td>
  <td>{_format_decimal(fill.get("funding_fee"), 2)}</td>
  <td class="{pnl_class}">{_format_decimal(fill.get("net_pnl"), 2)}</td>
  <td>{_exit_reason_label(fill.get("exit_reason"), fill.get("exit_detail"))}</td>
</tr>"""


def _trade_identity_label(item: dict[str, Any]) -> str:
    strategy = _strategy_type_label(item.get("strategy_type"))
    kernel = item.get("strategy_kernel")
    level = _position_level_label(item.get("position_level") or item.get("bucket"))
    mode = _trade_mode_label(item.get("trade_mode"))
    budget = _trade_policy_budget_label(item.get("trade_mode"))
    details = " / ".join(part for part in (kernel, level, mode, budget) if part and part != "-")
    if not details:
        return _escape(strategy)
    return f"{_escape(strategy)}<br><span class=\"muted\">{_escape(details)}</span>"


def _position_title(positions: Any) -> str:
    valid_positions = [position for position in positions if isinstance(position, dict)] if isinstance(positions, list) else []
    if not valid_positions:
        return "无"
    if len(valid_positions) == 1:
        position = valid_positions[0]
        return f"{_escape(position.get('symbol'))} {_side_label(position.get('side'))}"
    return f"{len(valid_positions)} 个策略子仓"


def _side_label(side: Any) -> str:
    if side == "LONG":
        return "做多"
    if side == "SHORT":
        return "做空"
    return _escape(side)


def _exit_reason_label(reason: Any, detail: Any = None) -> str:
    detail_text = _format_exit_detail(detail)
    if reason == "TAKE_PROFIT":
        return detail_text or "止盈"
    if reason == "STOP_LOSS":
        return detail_text or "止损"
    if reason == "TRAILING_TAKE_PROFIT":
        return detail_text or "移动止盈"
    if reason == "LIQUIDATION":
        return "强平"
    if reason == "OPEN":
        return "持仓中"
    return _escape(reason)


def _format_exit_detail(detail: Any) -> str:
    if not detail:
        return ""
    return _format_numbers_in_text(str(detail))


def _format_numbers_in_text(value: str) -> str:
    parts = value.split(" ")
    return " ".join(_format_decimal(part, 2) if _to_decimal(part) is not None else _escape(part) for part in parts)


def _format_decimal(value: Any, places: int = 2) -> str:
    decimal_value = _to_decimal(value)
    if decimal_value is None:
        return _escape(value if value is not None else "-")
    quant = Decimal("1").scaleb(-places)
    return format(decimal_value.quantize(quant), "f")


def _system_metrics_payload(disk_path: Path, now_ms: int) -> dict[str, str]:
    return {
        "cpu_percent": _system_cpu_percent(now_ms),
        "memory_available": _system_memory_value("MemAvailable"),
        "swap_free": _system_memory_value("SwapFree"),
        "disk_free": _system_disk_free(disk_path),
        "network_speed": _system_network_speed(now_ms),
    }


def _system_cpu_percent(now_ms: int) -> str:
    sample = _read_cpu_sample()
    if sample is None:
        return "-"
    global _SYSTEM_METRICS_LAST_SAMPLE
    previous = _SYSTEM_METRICS_LAST_SAMPLE or {}
    _SYSTEM_METRICS_LAST_SAMPLE = {**previous, "cpu": sample, "cpu_time_ms": now_ms}
    previous_sample = previous.get("cpu")
    if not isinstance(previous_sample, tuple):
        return "-"
    previous_idle, previous_total = previous_sample
    idle, total = sample
    total_delta = total - previous_total
    idle_delta = idle - previous_idle
    if total_delta <= 0:
        return "-"
    usage = max(Decimal("0"), min(Decimal("100"), Decimal(total_delta - idle_delta) * Decimal("100") / Decimal(total_delta)))
    return f"{_format_decimal(usage, 1)}%"


def _read_cpu_sample() -> tuple[int, int] | None:
    try:
        first_line = Path("/proc/stat").read_text(encoding="utf-8").splitlines()[0]
    except (OSError, IndexError):
        return None
    parts = first_line.split()
    if not parts or parts[0] != "cpu":
        return None
    try:
        values = [int(value) for value in parts[1:]]
    except ValueError:
        return None
    if len(values) < 4:
        return None
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    return idle, sum(values)


def _system_memory_value(field_name: str) -> str:
    values = _read_meminfo_kb()
    value_kb = values.get(field_name)
    if value_kb is None:
        return "-"
    return _format_bytes(value_kb * 1024)


def _read_meminfo_kb() -> dict[str, int]:
    try:
        lines = Path("/proc/meminfo").read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    values: dict[str, int] = {}
    for line in lines:
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        parts = raw_value.strip().split()
        if not parts:
            continue
        try:
            values[key] = int(parts[0])
        except ValueError:
            continue
    return values


def _system_disk_free(path: Path) -> str:
    try:
        stat = os.statvfs(path if path.exists() else Path("."))
    except OSError:
        return "-"
    return _format_bytes(stat.f_bavail * stat.f_frsize)


def _system_network_speed(now_ms: int) -> str:
    sample = _read_network_sample()
    if sample is None:
        return "-"
    global _SYSTEM_METRICS_LAST_SAMPLE
    previous = _SYSTEM_METRICS_LAST_SAMPLE or {}
    _SYSTEM_METRICS_LAST_SAMPLE = {**previous, "network": sample, "network_time_ms": now_ms}
    previous_sample = previous.get("network")
    previous_time_ms = previous.get("network_time_ms")
    if not isinstance(previous_sample, tuple) or not isinstance(previous_time_ms, int):
        return "-"
    seconds = Decimal(max(1, now_ms - previous_time_ms)) / Decimal("1000")
    rx_delta = max(0, sample[0] - previous_sample[0])
    tx_delta = max(0, sample[1] - previous_sample[1])
    return f"↓ {_format_bytes_per_second(Decimal(rx_delta) / seconds)} ↑ {_format_bytes_per_second(Decimal(tx_delta) / seconds)}"


def _read_network_sample() -> tuple[int, int] | None:
    try:
        lines = Path("/proc/net/dev").read_text(encoding="utf-8").splitlines()[2:]
    except OSError:
        return None
    rx_total = 0
    tx_total = 0
    for line in lines:
        if ":" not in line:
            continue
        interface, raw_values = line.split(":", 1)
        if interface.strip() == "lo":
            continue
        parts = raw_values.split()
        if len(parts) < 16:
            continue
        try:
            rx_total += int(parts[0])
            tx_total += int(parts[8])
        except ValueError:
            continue
    return rx_total, tx_total


def _format_bytes(value: int) -> str:
    amount = Decimal(value)
    units = ("B", "KB", "MB", "GB", "TB")
    unit_index = 0
    while amount >= Decimal("1024") and unit_index < len(units) - 1:
        amount /= Decimal("1024")
        unit_index += 1
    places = 0 if unit_index == 0 else 2
    return f"{_format_decimal(amount, places)} {units[unit_index]}"


def _format_bytes_per_second(value: Decimal) -> str:
    amount = value
    units = ("B/s", "KB/s", "MB/s", "GB/s")
    unit_index = 0
    while amount >= Decimal("1024") and unit_index < len(units) - 1:
        amount /= Decimal("1024")
        unit_index += 1
    places = 0 if unit_index == 0 else 2
    return f"{_format_decimal(amount, places)} {units[unit_index]}"


def _format_win_rate(wins: Any, losses: Any) -> str:
    try:
        win_count = int(wins)
        loss_count = int(losses)
    except (TypeError, ValueError):
        return "0%"
    total = win_count + loss_count
    if total <= 0:
        return "0%"
    return f"{round(win_count * 100 / total)}%"


def _format_datetime(value: Any) -> str:
    if not isinstance(value, datetime):
        return "-"
    utc_plus_8 = timezone(timedelta(hours=8))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(utc_plus_8).strftime("%Y-%m-%d %H:%M")


def _pnl_class(value: Any) -> str:
    decimal_value = _to_decimal(value)
    if decimal_value is not None and decimal_value < 0:
        return "loss"
    return "profit"


def _format_time_ms(value: Any) -> str:
    try:
        milliseconds = int(value)
    except (TypeError, ValueError):
        return "-"
    utc_plus_8 = timezone(timedelta(hours=8))
    formatted = datetime.fromtimestamp(milliseconds / 1000, tz=utc_plus_8).strftime("%Y-%m-%d %H:%M")
    return f'<span title="{milliseconds:,}">{formatted}</span>'


def _action_label(action: Any) -> str:
    labels = {
        "WAIT": "等待",
        "SNAPSHOT": "快照",
        "LONG_ENTRY": "做多入场",
        "REVERSAL_LONG_ENTRY": "趋势转换做多入场",
        "SHORT_ENTRY": "做空入场",
        "REVERSAL_SHORT_ENTRY": "趋势转换做空入场",
        "EXIT": "平仓",
    }
    key = str(action or "")
    label = labels.get(key)
    if label is None:
        return _escape(key or "-")
    return f"{label} ({key})"


def _status_label(status: Any) -> str:
    if status == "RUNNING":
        return "运行中"
    if status == "WAITING_FOR_STATE":
        return "等待状态文件"
    if status == "STATE_CORRUPT":
        return "状态文件损坏"
    return _escape(status)


def _runtime_seconds(started_at_ms: Any, now_ms: int) -> int:
    if started_at_ms is None:
        return 0
    return max(0, int((now_ms - int(started_at_ms)) / 1000))


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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


def _read_error_logs(
    path: Path | None,
    max_lines: int = 50,
    active_after_ms: int | None = None,
) -> list[str]:
    if path is None or not path.exists():
        return []
    stat = path.stat()
    if active_after_ms is not None and int(stat.st_mtime * 1000) <= active_after_ms:
        return []
    fallback_timestamp = _format_event_time_ms(int(stat.st_mtime * 1000))
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    matched = []
    for line in lines:
        timestamp, message = _split_log_timestamp(line, fallback_timestamp)
        if _is_error_recovery_log_line(message):
            matched.clear()
            continue
        summary = _summarize_error_log_line(message)
        rendered = f"{timestamp} {summary}" if summary else None
        if rendered and rendered not in matched:
            matched.append(rendered)
    return matched[-max_lines:]


def _split_log_timestamp(line: str, fallback_timestamp: str) -> tuple[str, str]:
    match = _LOG_TIMESTAMP_PATTERN.match(line)
    if match is None:
        return fallback_timestamp, line
    return match.group("timestamp").replace("T", " "), line[match.end():]


def _summarize_error_log_line(line: str) -> str | None:
    lowered = line.lower()
    if "historical warmup skipped" in lowered:
        return _summarize_historical_warmup_error(line, lowered)
    if "connecttimeout" in lowered or "connect timeout" in lowered or "timed out" in lowered:
        return "Binance REST 连接超时：历史数据预热或回测可能无法完成，请检查服务器网络是否能访问 Binance。"
    if (
        "traceback" in lowered
        or "the above exception" in lowered
        or "map_exception" in lowered
        or line.lstrip().startswith("File ")
        or line.lstrip().startswith("with ")
    ):
        return None
    if "websocket" in lowered and ("error" in lowered or "failed" in lowered or "disconnected" in lowered):
        return f"WebSocket 连接异常：{line}"
    if _is_error_log_line(line):
        return line
    return None


def _is_error_recovery_log_line(line: str) -> bool:
    lowered = line.lower()
    return (
        "websocket reconnected successfully" in lowered
        or "ticker websocket reconnected successfully" in lowered
    )


def _summarize_historical_warmup_error(line: str, lowered: str) -> str:
    prefix = "Historical warmup skipped for "
    target = ""
    detail = line
    if line.startswith(prefix):
        rest = line[len(prefix):]
        target, _, detail = rest.partition(": ")
    if "connecttimeout" in lowered or "connect timeout" in lowered or "timed out" in lowered:
        target_text = f"{target} " if target else ""
        return f"Binance REST 连接超时：{target_text}历史数据预热失败，{detail}"
    target_text = f"{target} " if target else ""
    return f"历史数据预热失败：{target_text}{detail}"


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
