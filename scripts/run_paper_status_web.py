from __future__ import annotations

import argparse
import asyncio
from dataclasses import replace
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.paper.strategy_backtest import StrategyBacktestConfig, run_strategy_backtest
from app.paper.web_status import (
    build_paper_status_payload,
    render_paper_status_html,
    render_strategy_backtest_html,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the Paper Trading status page.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--state-path", type=Path, default=Path("runtime/paper-state.json"))
    parser.add_argument("--error-log-path", type=Path, default=Path("runtime/logs/paper-realtime.log"))
    return parser.parse_args()


def make_handler(state_path: Path, error_log_path: Path):
    class PaperStatusHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            payload = build_paper_status_payload(state_path, error_log_path=error_log_path)
            if parsed.path == "/api/status":
                self._send_json(payload)
                return
            if parsed.path in {"/", "/index.html"}:
                self._send_html(render_paper_status_html(payload))
                return
            if parsed.path == "/backtest":
                result = None
                query = parse_qs(parsed.query)
                if query.get("run") == ["1"]:
                    result = _run_strategy_backtest_from_query(query)
                    result = _archive_strategy_backtest_result(result)
                else:
                    result = run_strategy_backtest_default_result()
                self._send_html(render_strategy_backtest_html(result=result))
                return
            self.send_error(404)

        def log_message(self, format: str, *args) -> None:
            return

        def _send_html(self, body: str) -> None:
            encoded = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_json(self, payload: dict) -> None:
            encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return PaperStatusHandler


def run_strategy_backtest_default_result():
    config = StrategyBacktestConfig()
    from app.paper.strategy_backtest import StrategyBacktestResult

    return StrategyBacktestResult(
        config=config,
        initial_equity="1000.00",
        final_equity="1000.00",
        total_trades=0,
        wins=0,
        losses=0,
        net_pnl="0.00",
        trades=[],
        error=None,
    )


def _backtest_config_from_query(query: dict[str, list[str]]) -> StrategyBacktestConfig:
    symbol = _query_choice(query, "symbol", "BTCUSDT", {"BTCUSDT", "ETHUSDT"})
    return StrategyBacktestConfig(
        symbols=(symbol,),
        ema_fast_period=_query_int(query, "ema_fast", 50, minimum=2, maximum=500),
        ema_slow_period=_query_int(query, "ema_slow", 200, minimum=3, maximum=1000),
        limit=_query_int(query, "limit", 1500, minimum=50, maximum=1500),
        history_period=_query_choice(query, "history_period", "3m", {"3m", "6m", "1y", "2y"}),
    )


def _run_strategy_backtest_from_query(query: dict[str, list[str]]):
    config = _backtest_config_from_query(query)
    try:
        return asyncio.run(run_strategy_backtest(config))
    except Exception as exc:
        return replace(run_strategy_backtest_default_result(), config=config, error=f"回测执行失败：{exc}")


def _archive_strategy_backtest_result(result, session_factory=None):
    if result.error:
        return result
    try:
        from app.config.settings import Settings
        from app.database.db import build_session_factory
        from app.database.repositories import archive_strategy_backtest_result

        factory = session_factory or build_session_factory(Settings())
        with factory() as session:
            archive_strategy_backtest_result(session, result)
    except Exception as exc:
        return replace(result, error=f"回测结果写入数据库失败：{exc}")
    return result


def _query_int(
    query: dict[str, list[str]],
    key: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    try:
        value = int(query.get(key, [str(default)])[0])
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))


def _query_choice(
    query: dict[str, list[str]],
    key: str,
    default: str,
    allowed: set[str],
) -> str:
    value = query.get(key, [default])[0]
    return value if value in allowed else default


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(args.state_path, args.error_log_path))
    print(f"Paper status page: http://{args.host}:{args.port}")
    print(f"Reading state: {args.state_path}")
    print(f"Reading error log: {args.error_log_path}")
    server.serve_forever()


if __name__ == "__main__":
    main()
