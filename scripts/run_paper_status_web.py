from __future__ import annotations

import argparse
import asyncio
import os
from collections import deque
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.paper.strategy_backtest import StrategyBacktestConfig, run_strategy_backtest
from app.paper.web_status import (
    build_paper_status_payload,
    render_paper_status_html,
    render_paper_runtime_events_html,
    render_strategy_backtest_batch_html,
    render_strategy_backtest_html,
)
from scripts.run_strategy_backtest_batch import run_strategy_backtest_batch


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the Paper Trading status page.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--state-path", type=Path, default=Path("runtime/paper-state.json"))
    parser.add_argument("--error-log-path", type=Path, default=Path("runtime/logs/paper-realtime.log"))
    parser.add_argument(
        "--enable-batch-backtest",
        action="store_true",
        default=os.getenv("PAPER_ENABLE_BATCH_BACKTEST") == "1",
        help="Enable heavy batch backtest actions on this web process.",
    )
    return parser.parse_args()


class BatchBacktestJobManager:
    def __init__(self, max_logs: int = 800) -> None:
        self._lock = threading.Lock()
        self._logs: deque[str] = deque(maxlen=max_logs)
        self._running = False
        self._stop_requested = False
        self._analysis = None
        self._error = None
        self._started_at_ms = None
        self._finished_at_ms = None
        self._stop_event: threading.Event | None = None
        self._thread: threading.Thread | None = None

    def start(self, config) -> bool:
        with self._lock:
            if self._running:
                return False
            self._logs.clear()
            self._running = True
            self._stop_requested = False
            self._analysis = None
            self._error = None
            self._started_at_ms = int(time.time() * 1000)
            self._finished_at_ms = None
            self._stop_event = threading.Event()
            self._append_log_locked("批量回测后台任务已启动。")
            thread = threading.Thread(target=self._run, args=(config, self._stop_event), daemon=True)
            self._thread = thread
            thread.start()
            return True

    def stop(self) -> bool:
        with self._lock:
            if not self._running or self._stop_event is None:
                return False
            self._stop_requested = True
            self._stop_event.set()
            self._append_log_locked("停止请求已收到，当前回测组合完成后会退出。")
            return True

    def status(self) -> dict:
        with self._lock:
            return {
                "running": self._running,
                "stop_requested": self._stop_requested,
                "started_at_ms": self._started_at_ms,
                "finished_at_ms": self._finished_at_ms,
                "logs": list(self._logs),
                "analysis": self._analysis,
                "error": self._error,
            }

    def _run(self, config, stop_event: threading.Event) -> None:
        try:
            analysis = run_strategy_backtest_batch(config, log_callback=self._append_log, stop_event=stop_event)
            with self._lock:
                self._analysis = analysis
                self._append_log_locked("批量回测后台任务已结束。")
        except Exception as exc:
            with self._lock:
                self._error = f"批量回测执行失败：{exc}"
                self._append_log_locked(self._error)
        finally:
            with self._lock:
                self._running = False
                self._finished_at_ms = int(time.time() * 1000)

    def _append_log(self, line: str) -> None:
        with self._lock:
            self._append_log_locked(line)

    def _append_log_locked(self, line: str) -> None:
        text = str(line)
        if _is_countdown_log_line(text) and self._logs and _is_countdown_log_line(self._logs[-1]):
            self._logs[-1] = text
            return
        self._logs.append(text)


def _is_countdown_log_line(line: str) -> bool:
    return "本轮倒计时:" in line


_BATCH_BACKTEST_JOBS = BatchBacktestJobManager()
LOCAL_TZ = ZoneInfo("Asia/Shanghai")


def make_handler(state_path: Path, error_log_path: Path, enable_batch_backtest: bool = False):
    class PaperStatusHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            payload = build_paper_status_payload(state_path, error_log_path=error_log_path)
            if parsed.path == "/api/status":
                self._send_json(payload)
                return
            if parsed.path == "/api/backtest/batch/status":
                status = _BATCH_BACKTEST_JOBS.status()
                status["enabled"] = enable_batch_backtest
                self._send_json(status)
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
                recent_results = _load_recent_strategy_backtest_results()
                self._send_html(render_strategy_backtest_html(result=result, recent_results=recent_results))
                return
            if parsed.path == "/backtest/batch":
                query = parse_qs(parsed.query)
                config = _batch_config_from_query(query)
                error = None
                info = None
                if not enable_batch_backtest:
                    error = (
                        "批量回测在 Web 进程中默认禁用，避免云服务器被公网请求触发重计算或清空记录。"
                        "如需本机临时研究，请设置 PAPER_ENABLE_BATCH_BACKTEST=1 后重启状态页。"
                    )
                else:
                    if query.get("run") == ["1"]:
                        if not _BATCH_BACKTEST_JOBS.start(config):
                            error = "已有批量回测正在运行，请先停止或等待完成。"
                    if query.get("stop") == ["1"]:
                        if not _BATCH_BACKTEST_JOBS.stop():
                            error = "当前没有正在运行的批量回测。"
                    if query.get("clear") == ["1"]:
                        if _BATCH_BACKTEST_JOBS.status().get("running"):
                            error = "批量回测正在运行，请先停止或等待完成后再清空记录。"
                        else:
                            clear_message = _clear_strategy_backtest_records()
                            if clear_message.startswith("清空回测记录失败"):
                                error = clear_message
                            else:
                                info = clear_message
                self._send_html(
                    render_strategy_backtest_batch_html(
                        config=config,
                        job_status=_BATCH_BACKTEST_JOBS.status(),
                        error=error,
                        info=info,
                    )
                )
                return
            if parsed.path == "/paper/events":
                query = parse_qs(parsed.query)
                events = _load_paper_runtime_events_for_web(query)
                self._send_html(
                    render_paper_runtime_events_html(
                        events=events,
                        filters=_paper_runtime_event_filters_from_query(query),
                    )
                )
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
        fast_ma_type=_query_choice(query, "fast_ma_type", "EMA", {"EMA", "MA"}),
        slow_ma_type=_query_choice(query, "slow_ma_type", "MA", {"EMA", "MA"}),
        ema_fast_period=_query_int(query, "ema_fast", 15, minimum=2, maximum=500),
        ema_slow_period=_query_int(query, "ema_slow", 60, minimum=3, maximum=1000),
        limit=_query_int(query, "limit", 1500, minimum=50, maximum=1500),
        history_period=_query_choice(query, "history_period", "3m", {"3m", "6m", "1y", "2y"}),
        max_fee_to_risk_ratio=_query_decimal(
            query,
            "max_fee_to_risk_ratio",
            Decimal("0.25"),
            minimum=Decimal("0"),
            maximum=Decimal("2"),
        ),
    )


def _batch_config_from_query(query: dict[str, list[str]]):
    from scripts.run_strategy_backtest_batch import HISTORY_WINDOWS_MS, StrategyBacktestBatchConfig

    history_period = _query_choice(query, "history_period", "1y", set(HISTORY_WINDOWS_MS))
    return StrategyBacktestBatchConfig(
        symbol=_query_choice(query, "symbol", "BTCUSDT", {"BTCUSDT", "ETHUSDT"}),
        fast_ma_type=_query_choice(query, "fast_ma_type", "EMA", {"EMA", "MA"}),
        slow_ma_type=_query_choice(query, "slow_ma_type", "MA", {"EMA", "MA"}),
        fast_periods=_query_range(query, "fast", default_start=15, default_end=50, default_step=5, minimum=2, maximum=500),
        slow_periods=_query_range(query, "slow", default_start=30, default_end=200, default_step=30, minimum=3, maximum=1000),
        atr_periods=_query_int_list(query, "atr_periods", (12, 14), minimum=2, maximum=200),
        dmi_periods=_query_int_list(query, "dmi_periods", (12, 14), minimum=2, maximum=200),
        swing_lookbacks=_query_int_list(query, "swing_lookbacks", (20, 30), minimum=2, maximum=500),
        max_fee_to_risk_ratios=_query_decimal_list(
            query,
            "max_fee_to_risk_ratios",
            ("0.25", "0"),
            minimum=Decimal("0"),
            maximum=Decimal("2"),
        ),
        take_profit_modes=_query_choice_list(query, "take_profit_modes", ("TRAILING", "FIXED"), {"TRAILING", "FIXED"}),
        pullback_zone_atr_multipliers=_query_decimal_list(
            query,
            "pullback_zone_atr_multipliers",
            ("1",),
            minimum=Decimal("0"),
            maximum=Decimal("3"),
        ),
        require_pullback_close_beyond_fast_ma_options=_query_bool_list(
            query,
            "require_pullback_close_beyond_fast_ma_options",
            (False,),
        ),
        enable_reversal_probe_options=_query_bool_list(
            query,
            "enable_reversal_probe_options",
            (False,),
        ),
        history_period=history_period,
        history_window_ms=HISTORY_WINDOWS_MS[history_period],
        skip_fast_gte_slow=_query_bool(query, "skip_fast_gte_slow", True),
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


def _load_recent_strategy_backtest_results(session_factory=None):
    try:
        from app.config.settings import Settings
        from app.database.db import build_session_factory
        from app.database.repositories import list_strategy_backtest_summaries

        factory = session_factory or build_session_factory(Settings())
        with factory() as session:
            return list_strategy_backtest_summaries(session, limit=100)
    except Exception:
        return []


def _load_paper_runtime_events_for_web(query: dict[str, list[str]], session_factory=None):
    try:
        from app.config.settings import Settings
        from app.database.db import build_session_factory
        from scripts.show_paper_runtime_events import load_paper_runtime_events

        factory = session_factory or build_session_factory(Settings())
        with factory() as session:
            return load_paper_runtime_events(
                session,
                limit=_query_int(query, "limit", 50, minimum=1, maximum=500),
                event_type=_optional_query_choice(
                    query,
                    "event_type",
                    {"signal", "blocked_signal", "rejected_signal", "fill", "snapshot"},
                ),
                symbol=_optional_query_text(query, "symbol"),
                strategy_type=_optional_query_text(query, "strategy_type"),
                bucket=_optional_query_text(query, "bucket"),
                start_time_ms=_query_local_time_ms(query, "start_time"),
                end_time_ms=_query_local_time_ms(query, "end_time"),
            )
    except Exception:
        return []


def _paper_runtime_event_filters_from_query(query: dict[str, list[str]]) -> dict[str, str]:
    return {
        "limit": str(_query_int(query, "limit", 50, minimum=1, maximum=500)),
        "event_type": _optional_query_choice(
            query,
            "event_type",
            {"signal", "blocked_signal", "rejected_signal", "fill", "snapshot"},
        )
        or "",
        "symbol": _optional_query_text(query, "symbol") or "",
        "strategy_type": _optional_query_text(query, "strategy_type") or "",
        "bucket": _optional_query_text(query, "bucket") or "",
        "start_time": _optional_query_text(query, "start_time") or "",
        "end_time": _optional_query_text(query, "end_time") or "",
    }


def _optional_query_choice(query: dict[str, list[str]], key: str, allowed: set[str]) -> str | None:
    value = _optional_query_text(query, key)
    if value is None:
        return None
    return value if value in allowed else None


def _optional_query_text(query: dict[str, list[str]], key: str) -> str | None:
    value = str(query.get(key, [""])[0]).strip()
    return value or None


def _query_local_time_ms(query: dict[str, list[str]], key: str) -> int | None:
    value = _optional_query_text(query, key)
    if value is None:
        return None
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            parsed = datetime.strptime(value, pattern)
        except ValueError:
            continue
        return int(parsed.replace(tzinfo=LOCAL_TZ).timestamp() * 1000)
    return None


def _clear_strategy_backtest_records(session_factory=None) -> str:
    try:
        from app.config.settings import Settings
        from app.database.db import build_session_factory
        from app.database.repositories import clear_strategy_backtest_history

        factory = session_factory or build_session_factory(Settings())
        with factory() as session:
            counts = clear_strategy_backtest_history(session)
    except Exception as exc:
        return f"清空回测记录失败：{exc}"
    return (
        "已清空回测记录："
        f"回测 {counts.get('runs', 0)} 条，"
        f"交易 {counts.get('trades', 0)} 条，"
        f"配置 {counts.get('config_snapshots', 0)} 条。"
    )


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


def _query_decimal(
    query: dict[str, list[str]],
    key: str,
    default: Decimal,
    minimum: Decimal,
    maximum: Decimal,
) -> Decimal:
    try:
        value = Decimal(query.get(key, [str(default)])[0])
    except Exception:
        return default
    return max(minimum, min(maximum, value))


def _query_range(
    query: dict[str, list[str]],
    prefix: str,
    default_start: int,
    default_end: int,
    default_step: int,
    minimum: int,
    maximum: int,
) -> tuple[int, ...]:
    start = _query_int(query, f"{prefix}_start", default_start, minimum=minimum, maximum=maximum)
    end = _query_int(query, f"{prefix}_end", default_end, minimum=minimum, maximum=maximum)
    step = _query_int(query, f"{prefix}_step", default_step, minimum=1, maximum=maximum)
    if end < start:
        end = start
    values = list(range(start, end + 1, step))
    if values and values[-1] != end:
        values.append(end)
    return tuple(values)


def _query_int_list(
    query: dict[str, list[str]],
    key: str,
    default: tuple[int, ...],
    minimum: int,
    maximum: int,
) -> tuple[int, ...]:
    values: list[int] = []
    for part in query.get(key, [",".join(str(value) for value in default)])[0].split(","):
        text = part.strip()
        if not text:
            continue
        try:
            value = int(text)
        except ValueError:
            continue
        values.append(max(minimum, min(maximum, value)))
    return tuple(values) or default


def _query_decimal_list(
    query: dict[str, list[str]],
    key: str,
    default: tuple[str, ...],
    minimum: Decimal,
    maximum: Decimal,
) -> tuple[str, ...]:
    values: list[str] = []
    for part in query.get(key, [",".join(default)])[0].split(","):
        text = part.strip()
        if not text:
            continue
        try:
            value = Decimal(text)
        except Exception:
            continue
        values.append(str(max(minimum, min(maximum, value))))
    return tuple(values) or default


def _query_choice_list(
    query: dict[str, list[str]],
    key: str,
    default: tuple[str, ...],
    allowed: set[str],
) -> tuple[str, ...]:
    values = tuple(
        part.strip().upper()
        for part in query.get(key, [",".join(default)])[0].split(",")
        if part.strip().upper() in allowed
    )
    return values or default


def _query_bool(query: dict[str, list[str]], key: str, default: bool) -> bool:
    value = str(query.get(key, ["1" if default else "0"])[0]).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _query_bool_list(
    query: dict[str, list[str]],
    key: str,
    default: tuple[bool, ...],
) -> tuple[bool, ...]:
    mapping = {
        "1": True,
        "true": True,
        "yes": True,
        "on": True,
        "0": False,
        "false": False,
        "no": False,
        "off": False,
    }
    values: list[bool] = []
    default_text = ",".join("true" if value else "false" for value in default)
    for part in query.get(key, [default_text])[0].split(","):
        text = part.strip().lower()
        if text in mapping:
            values.append(mapping[text])
    return tuple(values) or default


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer(
        (args.host, args.port),
        make_handler(
            args.state_path,
            args.error_log_path,
            enable_batch_backtest=args.enable_batch_backtest,
        ),
    )
    print(f"Paper status page: http://{args.host}:{args.port}")
    print(f"Reading state: {args.state_path}")
    print(f"Reading error log: {args.error_log_path}")
    server.serve_forever()


if __name__ == "__main__":
    main()
