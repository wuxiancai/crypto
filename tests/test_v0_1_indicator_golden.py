from pathlib import Path


def test_indicator_golden_fixture_matches_expected_values():
    from app.indicators.validation import validate_golden_fixture

    result = validate_golden_fixture(Path("tests/fixtures/indicator_golden.json"))

    assert result.errors == []
    assert result.checked == [
        "ema_3_last",
        "atr_3_last",
        "bb_5_middle_last",
        "di_plus_3_last",
        "di_minus_3_last",
        "adx_3_last",
    ]

