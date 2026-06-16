import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from app.indicators.core import atr, bollinger_bands, directional_movement_index, ema


@dataclass(frozen=True)
class GoldenValidationResult:
    checked: list[str]
    errors: list[str]


def validate_golden_fixture(path: Path) -> GoldenValidationResult:
    payload = json.loads(path.read_text(encoding="utf-8"))
    closes = [Decimal(value) for value in payload["close_values"]]
    highs = [Decimal(value) for value in payload["high_values"]]
    lows = [Decimal(value) for value in payload["low_values"]]
    expected = {key: Decimal(value) for key, value in payload["expected"].items()}

    bands = bollinger_bands(closes, period=5, stddev=Decimal("2"))
    dmi = directional_movement_index(highs, lows, closes, period=3)
    actual = {
        "ema_3_last": ema(closes, period=3)[-1],
        "atr_3_last": atr(highs, lows, closes, period=3)[-1],
        "bb_5_middle_last": bands[-1].middle if bands[-1] is not None else None,
        "di_plus_3_last": dmi[-1].di_plus if dmi[-1] is not None else None,
        "di_minus_3_last": dmi[-1].di_minus if dmi[-1] is not None else None,
        "adx_3_last": dmi[-1].adx if dmi[-1] is not None else None,
    }

    errors: list[str] = []
    checked: list[str] = []
    for key, expected_value in expected.items():
        checked.append(key)
        actual_value = actual[key]
        if actual_value != expected_value:
            errors.append(f"{key}: expected {expected_value}, got {actual_value}")
    return GoldenValidationResult(checked=checked, errors=errors)

