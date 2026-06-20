import html
import json
from datetime import datetime, timedelta, timezone
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
            "market_prices": {},
        }

    payload = json.loads(state_path.read_text(encoding="utf-8"))
    started_at = payload.get("runtime_started_at_ms")
    signal_evaluations = payload.get("signal_evaluations", [])
    fills = payload.get("fills", [])
    open_position = payload.get("open_position")
    return {
        "status": "RUNNING",
        "state_path": str(state_path),
        "equity": payload.get("equity"),
        "open_position": open_position,
        "fills": fills,
        "rejected_signals": payload.get("rejected_signals", 0),
        "runtime_seconds": _runtime_seconds(started_at, now_ms),
        "last_update_at_ms": payload.get("last_update_at_ms"),
        "error_logs": _read_error_logs(error_log_path),
        "signal_evaluations": signal_evaluations,
        "market_prices": _latest_market_prices(
            evaluations=signal_evaluations,
            open_position=open_position,
            fills=fills,
        ),
    }


def render_paper_status_html(payload: dict[str, Any]) -> str:
    position = payload.get("open_position")
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
    .ticker-strip {{ flex: 1; min-width: 280px; display: flex; align-items: center; justify-content: center; gap: 10px; flex-wrap: wrap; }}
    .ticker-item {{ display: inline-flex; align-items: baseline; gap: 6px; padding: 7px 10px; border: 1px solid #d9e0ec; border-radius: 4px; background: #fff; }}
    .ticker-symbol {{ color: #65748b; font-size: 12px; font-weight: 700; }}
    .ticker-price {{ color: #172033; font-size: 16px; font-weight: 700; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }}
    .panel {{ background: #fff; border: 1px solid #d9e0ec; border-radius: 6px; padding: 14px; }}
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
    .trade-scroll {{ max-height: 252px; overflow-y: auto; border: 1px solid #d9e0ec; border-radius: 6px; }}
    .trade-scroll table {{ border: 0; border-radius: 0; }}
    .compact-position th, .compact-position td {{ white-space: normal; }}
    @media (max-width: 820px) {{
      main {{ padding: 14px; }}
      header {{ align-items: flex-start; flex-direction: column; }}
      .header-meta {{ justify-content: flex-start; }}
      .ticker-strip {{ justify-content: flex-start; width: 100%; }}
      .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
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
        <div class="badge">系统运行时间：{_format_duration(payload.get("runtime_seconds"))}</div>
        <div class="badge">{_status_label(payload.get("status"))} · 5 秒自动刷新</div>
      </div>
    </header>
    <section class="grid">
      <div class="panel"><div class="label">账户权益 USDT</div><div class="value">{_format_decimal(payload.get("equity"), 2)}</div></div>
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
    const chartItemsInGroup = (selector, group) => Array.from(document.querySelectorAll(selector)).filter((item) => (item.getAttribute("data-chart-group") || "default") === group);
    function bindChartTabs() {{
      document.querySelectorAll("[data-chart-target]").forEach((button) => {{
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
      }} catch (_error) {{
        return;
      }}
    }}
    bindChartTabs();
    setInterval(refreshDashboard, 5000);
  </script>
</body>
</html>"""


def render_strategy_backtest_html(result: Any | None = None, recent_results: list[Any] | None = None) -> str:
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
          <label for="max_fee_to_risk_ratio">手续费/风险上限</label>
          <input id="max_fee_to_risk_ratio" name="max_fee_to_risk_ratio" type="number" min="0" max="2" step="0.05" value="{_escape(config.max_fee_to_risk_ratio)}">
        </div>
        <button class="primary-button" type="submit" name="run" value="1">开始回测</button>
      </form>
    </section>
    {_render_backtest_error(error)}
    <section class="grid" style="margin-top: 16px;">
      <div class="panel"><div class="label">初始权益 USDT</div><div class="value">{_format_decimal(getattr(result, "initial_equity", config.initial_equity), 2)}</div></div>
      <div class="panel"><div class="label">账户权益 USDT</div><div class="value">{_format_decimal(getattr(result, "final_equity", config.initial_equity), 2)}</div></div>
      <div class="panel"><div class="label">总交易次数</div><div class="value">{_escape(getattr(result, "total_trades", 0))}</div></div>
      <div class="panel"><div class="label">胜 / 负 / 胜率</div><div class="value">{_escape(getattr(result, "wins", 0))} / {_escape(getattr(result, "losses", 0))} / 胜率 {_format_win_rate(getattr(result, "wins", 0), getattr(result, "losses", 0))}</div></div>
    </section>
    <section style="margin-top: 16px;">
      <h2>最近回测结果</h2>
      {_render_recent_backtest_results(recent)}
    </section>
    <section style="margin-top: 16px;">
      <h2>全部回测交易记录</h2>
      {_render_backtest_trades(trades)}
    </section>
  </main>
</body>
</html>"""


def render_strategy_backtest_batch_html(config: Any | None = None, analysis: dict[str, Any] | None = None, error: str | None = None) -> str:
    if config is None:
        from scripts.run_strategy_backtest_batch import StrategyBacktestBatchConfig

        config = StrategyBacktestBatchConfig()
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
    .form-grid {{ display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; align-items: end; }}
    .form-field {{ display: grid; gap: 6px; }}
    .form-field label {{ color: #344055; font-size: 13px; font-weight: 700; }}
    .form-field input, .form-field select {{ width: 100%; box-sizing: border-box; border: 1px solid #b8c2d6; border-radius: 4px; padding: 8px 10px; font-size: 14px; background: #fff; }}
    .primary-button {{ border: 1px solid #172033; background: #172033; color: #fff; border-radius: 4px; padding: 9px 12px; cursor: pointer; font-weight: 700; }}
    .empty {{ color: #65748b; padding: 14px; background: #fff; border: 1px solid #d9e0ec; border-radius: 6px; }}
    .error-log-line {{ color: #b42318; font-family: Menlo, Consolas, monospace; font-size: 12px; white-space: pre-wrap; overflow-wrap: anywhere; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d9e0ec; border-radius: 6px; overflow: hidden; }}
    th, td {{ border-bottom: 1px solid #e6ebf2; padding: 9px 10px; text-align: left; font-size: 13px; white-space: nowrap; }}
    th {{ background: #eef3f9; color: #344055; }}
    tr:last-child td {{ border-bottom: 0; }}
    .table-wrap {{ overflow-x: auto; }}
    @media (max-width: 900px) {{
      main {{ padding: 14px; }}
      header {{ align-items: flex-start; flex-direction: column; }}
      .form-grid {{ grid-template-columns: 1fr; }}
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
      <form class="form-grid" method="get" action="/backtest/batch">
        <div class="form-field">
          <label for="symbol">交易对</label>
          <select id="symbol" name="symbol">{_render_batch_symbol_options(getattr(config, "symbol", "BTCUSDT"))}</select>
        </div>
        <div class="form-field">
          <label for="fast_ma_type">快线类型</label>
          <select id="fast_ma_type" name="fast_ma_type">{_render_average_type_options(getattr(config, "fast_ma_type", "EMA"))}</select>
        </div>
        <div class="form-field"><label for="fast_start">快线起始</label><input id="fast_start" name="fast_start" type="number" min="2" max="500" value="{_escape(fast_start)}"></div>
        <div class="form-field"><label for="fast_end">快线结束</label><input id="fast_end" name="fast_end" type="number" min="2" max="500" value="{_escape(fast_end)}"></div>
        <div class="form-field"><label for="fast_step">快线步进</label><input id="fast_step" name="fast_step" type="number" min="1" max="100" value="{_escape(fast_step)}"></div>
        <div class="form-field">
          <label for="slow_ma_type">慢线类型</label>
          <select id="slow_ma_type" name="slow_ma_type">{_render_average_type_options(getattr(config, "slow_ma_type", "MA"))}</select>
        </div>
        <div class="form-field"><label for="slow_start">慢线起始</label><input id="slow_start" name="slow_start" type="number" min="3" max="1000" value="{_escape(slow_start)}"></div>
        <div class="form-field"><label for="slow_end">慢线结束</label><input id="slow_end" name="slow_end" type="number" min="3" max="1000" value="{_escape(slow_end)}"></div>
        <div class="form-field"><label for="slow_step">慢线步进</label><input id="slow_step" name="slow_step" type="number" min="1" max="200" value="{_escape(slow_step)}"></div>
        <div class="form-field">
          <label for="history_period">回测周期</label>
          <select id="history_period" name="history_period">{_render_history_period_options(getattr(config, "history_period", "1y"))}</select>
        </div>
        <div class="form-field"><label for="atr_periods">ATR 周期</label><input id="atr_periods" name="atr_periods" value="{_escape(_join_values(getattr(config, "atr_periods", (10, 12, 14, 16, 18))))}"></div>
        <div class="form-field"><label for="dmi_periods">DMI 周期</label><input id="dmi_periods" name="dmi_periods" value="{_escape(_join_values(getattr(config, "dmi_periods", (10, 12, 14, 16, 18))))}"></div>
        <div class="form-field"><label for="swing_lookbacks">Swing Lookback</label><input id="swing_lookbacks" name="swing_lookbacks" value="{_escape(_join_values(getattr(config, "swing_lookbacks", (10, 15, 20, 25, 30))))}"></div>
        <div class="form-field"><label for="max_fee_to_risk_ratios">手续费/风险上限</label><input id="max_fee_to_risk_ratios" name="max_fee_to_risk_ratios" value="{_escape(_join_values(getattr(config, "max_fee_to_risk_ratios", ("0.15", "0.20", "0.25", "0.30", "0.35", "0.50"))))}"></div>
        <div class="form-field"><label for="take_profit_modes">止盈模式</label><input id="take_profit_modes" name="take_profit_modes" value="{_escape(_join_values(getattr(config, "take_profit_modes", ("TRAILING", "FIXED"))))}"></div>
        <div class="form-field">
          <label for="skip_fast_gte_slow">过滤快线>=慢线</label>
          <select id="skip_fast_gte_slow" name="skip_fast_gte_slow">{_render_bool_options(getattr(config, "skip_fast_gte_slow", False))}</select>
        </div>
        <button class="primary-button" type="submit" name="run" value="1">开始批量回测</button>
      </form>
    </section>
    {_render_backtest_error(error)}
    <section style="margin-top: 16px;">
      <h2>批量回测结果</h2>
      {_render_batch_analysis(analysis)}
    </section>
  </main>
</body>
</html>"""


def _render_position(position: dict[str, Any] | None) -> str:
    if position is None:
        return '<div class="empty">当前无持仓</div>'
    rows = [
        ("交易对", _escape(position.get("symbol"))),
        ("方向", _side_label(position.get("side"))),
        ("使用策略", _escape(position.get("strategy_type"))),
        ("入场 / 止损 / 止盈", " / ".join([
            _format_decimal(position.get("entry_price"), 2),
            _format_decimal(position.get("stop_loss"), 2),
            _format_decimal(position.get("take_profit"), 2),
        ])),
        ("止盈状态", "移动止盈中" if position.get("trailing_active") else "等待触发"),
        ("数量", _format_decimal(position.get("quantity"), 4)),
    ]
    headers = "".join(f"<th>{_escape(label)}</th>" for label, _value in rows)
    values = "".join(f"<td>{value}</td>" for _label, value in rows)
    return f'<div class="table-wrap"><table class="compact-position"><thead><tr>{headers}</tr></thead><tbody><tr>{values}</tr></tbody></table></div>'


def _render_history_period_options(selected: Any) -> str:
    options = [
        ("3m", "最近3个月"),
        ("6m", "最近6个月"),
        ("1y", "最近1年"),
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
        return str(values or "")
    return ",".join(str(value) for value in values)


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


def _render_fills(fills: list[dict[str, Any]]) -> str:
    if not fills:
        return '<div class="empty">暂无模拟成交</div>'
    rows = "\n".join(_render_fill_row(fill) for fill in fills)
    return f"""<div class="table-wrap trade-scroll">
<table>
  <thead>
    <tr>
      <th>交易对</th><th>方向</th><th>使用策略</th><th>开仓时间 UTC+8</th><th>平仓时间 UTC+8</th>
      <th>开仓价</th><th>平仓价</th><th>数量</th><th>手续费</th><th>资金费</th><th>净盈亏</th><th>退出原因</th>
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
      <th>开仓价</th><th>平仓价</th><th>数量</th><th>手续费</th><th>资金费</th><th>净盈亏</th><th>退出原因</th>
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
      <th>回测时间 UTC+8</th><th>交易对</th><th>均线组合</th><th>周期</th>
      <th>初始权益</th><th>账户权益</th><th>总交易次数</th><th>胜 / 负 / 胜率</th><th>净盈亏</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
</div>"""


def _render_recent_backtest_result_row(result: Any) -> str:
    net_pnl = getattr(result, "net_pnl", "0")
    pnl_class = _pnl_class(net_pnl)
    wins = getattr(result, "wins", 0)
    losses = getattr(result, "losses", 0)
    return f"""<tr>
  <td>{_escape(_format_datetime(getattr(result, "created_at", None)))}</td>
  <td>{_escape(getattr(result, "symbol", "-"))}</td>
  <td>{_escape(_average_combo_label(result))}</td>
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


def _sort_recent_backtest_results(results: list[Any]) -> list[Any]:
    return sorted(
        results,
        key=lambda item: _datetime_sort_key(getattr(item, "created_at", None)),
        reverse=True,
    )


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
        "1y": "最近1年",
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


def _render_error_logs(lines: list[str]) -> str:
    if not lines:
        return '<div class="empty">暂无错误日志</div>'
    rendered = "".join(f'<div class="error-log-line">{_escape(line)}</div>' for line in lines)
    return f'<div class="error-log-box">{rendered}</div>'


def _render_market_prices(prices: dict[str, Any]) -> str:
    symbols = ("BTCUSDT", "ETHUSDT")
    items = "".join(
        f"""<div class="ticker-item">
  <span class="ticker-symbol">{symbol} 永续最新价</span>
  <span class="ticker-price">{_format_decimal(prices.get(symbol), 2)}</span>
</div>"""
        for symbol in symbols
    )
    return f'<div class="ticker-strip">{items}</div>'


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


def _latest_market_prices(
    evaluations: Any,
    open_position: Any,
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
    rows = "".join(_render_condition_row(condition) for condition in conditions)
    return f"""<div class="panel">
  <div class="condition-summary">
    <div class="condition-title">{_escape(_nearest_strategy_summary(nearest, evaluation.get("symbol")))}</div>
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
    status_class = "condition-pass" if passed else "condition-fail"
    return f"""<div class="condition-row">
  <div><span class="condition-status {status_class}">{_condition_status_label(passed)}</span> {_escape(condition.get("text"))}</div>
  <details class="condition-detail"><summary>计算明细</summary>{_escape(condition.get("detail"))}</details>
</div>"""


def _condition_status_label(passed: bool) -> str:
    return "满足" if passed else "未满足"


def _nearest_strategy_summary(nearest: Any, symbol: Any = None) -> str:
    if not isinstance(nearest, dict) or not nearest:
        return "当前趋势：暂无"
    name = nearest.get("name") or "-"
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
    chart_timeframes: dict[str, list[dict[str, Decimal]]],
    symbol_scoped: bool,
    group: str = "default",
) -> str:
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
    symbol = str(evaluation.get("symbol") or "UNKNOWN")
    tabs = "".join(
        _render_chart_tab(interval=interval, active=index == 0, symbol=symbol if symbol_scoped else None, group=group)
        for index, interval in enumerate(intervals)
    )
    panels = "".join(
        _render_chart_panel(
            interval=interval,
            points=chart_timeframes[interval],
            symbol=symbol,
            active=index == 0,
            symbol_scoped=symbol_scoped,
            group=group,
        )
        for index, interval in enumerate(intervals)
    )
    return f"""<div class="chart-tabs">{tabs}</div>
  {panels}"""


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


def _render_chart_tab(interval: str, active: bool, symbol: str | None = None, group: str = "default") -> str:
    active_class = " active" if active else ""
    chart_id = _chart_id(interval, symbol=symbol)
    return f'<button class="chart-tab{active_class}" type="button" data-chart-target="{chart_id}" data-chart-group="{_escape(group)}">{_escape(interval)}</button>'


def _render_chart_symbol_tab(symbol: str, active: bool) -> str:
    active_class = " active" if active else ""
    return f'<button class="chart-tab{active_class}" type="button" data-chart-target="{_symbol_panel_id(symbol)}" data-chart-group="chart-symbols">{_escape(symbol)}</button>'


def _render_chart_panel(
    interval: str,
    points: list[dict[str, Decimal]],
    symbol: Any,
    active: bool,
    symbol_scoped: bool = False,
    group: str = "default",
) -> str:
    active_class = " active" if active else ""
    chart_id = _chart_id(interval, symbol=str(symbol) if symbol_scoped else None)
    return f"""<div class="chart-panel{active_class}" data-chart-panel="{chart_id}" data-chart-group="{_escape(group)}">
  <div class="legend">
    <span class="legend-item"><span class="legend-swatch" style="background:#0a7c52"></span>K线</span>
    <span class="legend-item"><span class="legend-swatch" style="background:#2563eb"></span>EMA50</span>
    <span class="legend-item"><span class="legend-swatch" style="background:#9333ea"></span>EMA200</span>
    <span>{_escape(symbol)} · {_escape(interval)}</span>
  </div>
  {_render_chart_svg(points)}
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


def _latest_chart_evaluation(evaluations: list[dict[str, Any]]) -> dict[str, Any] | None:
    chartable = [
        evaluation
        for evaluation in evaluations
        if evaluation.get("chart_timeframes") or evaluation.get("chart_points")
    ]
    if not chartable:
        return None
    return max(chartable, key=lambda item: int(item.get("evaluated_at_ms") or 0))


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
    return f"""<tr>
  <td>{_escape(fill.get("symbol"))}</td>
  <td>{_side_label(fill.get("side"))}</td>
  <td>{_escape(fill.get("strategy_type"))}</td>
  <td>{_format_time_ms(fill.get("entry_time"))}</td>
  <td>{_format_time_ms(fill.get("exit_time"))}</td>
  <td>{_format_decimal(fill.get("entry_price"), 2)}</td>
  <td>{_format_decimal(fill.get("exit_price"), 2)}</td>
  <td>{_format_decimal(fill.get("quantity"), 4)}</td>
  <td>{_format_decimal(fill.get("fees"), 2)}</td>
  <td>{_format_decimal(fill.get("funding_fee"), 2)}</td>
  <td class="{pnl_class}">{_format_decimal(fill.get("net_pnl"), 2)}</td>
  <td>{_exit_reason_label(fill.get("exit_reason"), fill.get("exit_detail"))}</td>
</tr>"""


def _position_title(position: dict[str, Any] | None) -> str:
    if position is None:
        return "无"
    return f"{_escape(position.get('symbol'))} {_side_label(position.get('side'))}"


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
    matched = []
    for line in lines:
        summary = _summarize_error_log_line(line)
        if summary and summary not in matched:
            matched.append(summary)
    return matched[-max_lines:]


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
