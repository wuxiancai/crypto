import os
from io import StringIO


def test_read_error_logs_preserves_log_timestamp(tmp_path):
    from app.paper.web_status import _read_error_logs

    log_path = tmp_path / "paper-realtime.log"
    log_path.write_text(
        "2026-07-01 12:34:56 Funding snapshot fetch skipped: Binance premium index request failed\n",
        encoding="utf-8",
    )

    lines = _read_error_logs(log_path)

    assert lines == [
        "2026-07-01 12:34:56 Funding snapshot fetch skipped: Binance premium index request failed"
    ]


def test_read_error_logs_adds_file_time_when_log_line_has_no_timestamp(tmp_path):
    from app.paper.web_status import _read_error_logs

    log_path = tmp_path / "paper-realtime.log"
    log_path.write_text(
        "Funding snapshot fetch skipped: Binance premium index request failed\n",
        encoding="utf-8",
    )
    os.utime(log_path, (1_782_880_496, 1_782_880_496))

    lines = _read_error_logs(log_path)

    assert lines == [
        "2026-07-01 12:34:56 Funding snapshot fetch skipped: Binance premium index request failed"
    ]


def test_timestamped_line_writer_prefixes_complete_log_lines():
    from scripts.run_paper_realtime import _TimestampedLineWriter

    output = StringIO()
    writer = _TimestampedLineWriter(output, now=lambda: "2026-07-01 12:34:56")

    writer.write("Funding snapshot fetch skipped")
    writer.write(": Binance premium index request failed\n")

    assert output.getvalue() == (
        "2026-07-01 12:34:56 Funding snapshot fetch skipped: "
        "Binance premium index request failed\n"
    )
