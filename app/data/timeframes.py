from datetime import datetime, timezone


INTERVAL_SECONDS = {
    "5m": 5 * 60,
    "15m": 15 * 60,
    "1h": 60 * 60,
    "4h": 4 * 60 * 60,
}


def closed_window_open_time(current_time: datetime, interval: str) -> datetime:
    if interval not in INTERVAL_SECONDS:
        raise ValueError(f"unsupported interval: {interval}")
    if current_time.tzinfo is None:
        raise ValueError("current_time must be timezone-aware")

    utc_time = current_time.astimezone(timezone.utc)
    interval_seconds = INTERVAL_SECONDS[interval]
    timestamp = int(utc_time.timestamp())
    current_window_open = timestamp - (timestamp % interval_seconds)
    closed_open = current_window_open - interval_seconds
    return datetime.fromtimestamp(closed_open, tz=timezone.utc)
