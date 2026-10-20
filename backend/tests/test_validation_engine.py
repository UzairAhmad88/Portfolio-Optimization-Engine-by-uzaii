import pytest

from app.market_data.service import validate_csv


def test_valid_minimal_csv():
    csv_bytes = (
        b"date,ticker,market,close,currency\n"
        b"2025-01-02,AAPL,US,150.25,USD\n"
        b"2025-01-03,AAPL,US,152.50,USD\n"
    )
    report = validate_csv(csv_bytes)
    assert report["rows_examined"] == 2
    assert report["valid_rows"] == 2
    assert report["rejected_rows"] == 0
    assert len(report["errors"]) == 0
    assert len(report["warnings"]) > 0  # optional columns missing warnings


def test_valid_complete_ohlc_csv():
    csv_bytes = (
        b"date,ticker,market,close,currency,open,high,low,adjusted_close,volume\n"
        b"2025-01-02,AAPL,US,150.00,USD,148.00,152.00,147.50,150.00,1500000\n"
        b"2025-01-02,OGDC,PSX,120.00,PKR,118.00,121.50,117.00,120.00,450000\n"
    )
    report = validate_csv(csv_bytes)
    assert report["rows_examined"] == 2
    assert report["valid_rows"] == 2
    assert report["rejected_rows"] == 0
    assert len(report["errors"]) == 0
    assert len(report["warnings"]) == 0
    assert report["valid_data"][0]["open"] == 148.00
    assert report["valid_data"][0]["high"] == 152.00
    assert report["valid_data"][0]["low"] == 147.50


def test_invalid_high_lower_than_low():
    csv_bytes = (
        b"date,ticker,market,close,currency,high,low\n"
        b"2025-01-02,AAPL,US,100,USD,90,110\n"
    )
    report = validate_csv(csv_bytes)
    assert report["valid_rows"] == 0
    assert report["rejected_rows"] == 1
    reasons = report["errors"][0]["reasons"]
    assert "High cannot be lower than low." in reasons


def test_invalid_high_lower_than_close():
    csv_bytes = (
        b"date,ticker,market,close,currency,high,low\n"
        b"2025-01-02,AAPL,US,120,USD,110,90\n"
    )
    report = validate_csv(csv_bytes)
    assert report["valid_rows"] == 0
    reasons = report["errors"][0]["reasons"]
    assert "High cannot be lower than close." in reasons


def test_invalid_high_lower_than_open():
    csv_bytes = (
        b"date,ticker,market,close,currency,open,high,low\n"
        b"2025-01-02,AAPL,US,100,USD,115,105,90\n"
    )
    report = validate_csv(csv_bytes)
    assert report["valid_rows"] == 0
    reasons = report["errors"][0]["reasons"]
    assert "High cannot be lower than open." in reasons


def test_invalid_low_higher_than_close():
    csv_bytes = (
        b"date,ticker,market,close,currency,high,low\n"
        b"2025-01-02,AAPL,US,85,USD,105,90\n"
    )
    report = validate_csv(csv_bytes)
    assert report["valid_rows"] == 0
    reasons = report["errors"][0]["reasons"]
    assert "Low cannot be higher than close." in reasons


def test_invalid_low_higher_than_open():
    csv_bytes = (
        b"date,ticker,market,close,currency,open,high,low\n"
        b"2025-01-02,AAPL,US,100,USD,85,105,90\n"
    )
    report = validate_csv(csv_bytes)
    assert report["valid_rows"] == 0
    reasons = report["errors"][0]["reasons"]
    assert "Low cannot be higher than open." in reasons


def test_non_numeric_in_required_field():
    csv_bytes = (
        b"date,ticker,market,close,currency\n2025-01-02,AAPL,US,corrupt_price,USD\n"
    )
    report = validate_csv(csv_bytes)
    assert report["valid_rows"] == 0
    reasons = report["errors"][0]["reasons"]
    assert any("positive" in r for r in reasons)


def test_non_numeric_in_optional_field():
    csv_bytes = (
        b"date,ticker,market,close,currency,open\n"
        b"2025-01-02,AAPL,US,100,USD,corrupt_open\n"
    )
    report = validate_csv(csv_bytes)
    assert report["valid_rows"] == 0
    reasons = report["errors"][0]["reasons"]
    assert "open must be a valid number when provided." in reasons


def test_non_numeric_in_volume():
    csv_bytes = (
        b"date,ticker,market,close,currency,volume\n"
        b"2025-01-02,AAPL,US,100,USD,bad_volume\n"
    )
    report = validate_csv(csv_bytes)
    assert report["valid_rows"] == 0
    reasons = report["errors"][0]["reasons"]
    assert "volume must be a valid number when provided." in reasons


def test_non_finite_price_infinity():
    csv_bytes = (
        b"date,ticker,market,close,currency,open\n2025-01-02,AAPL,US,100,USD,inf\n"
    )
    report = validate_csv(csv_bytes)
    assert report["valid_rows"] == 0
    reasons = report["errors"][0]["reasons"]
    assert "open must be a finite number." in reasons


def test_non_finite_volume_infinity():
    csv_bytes = (
        b"date,ticker,market,close,currency,volume\n2025-01-02,AAPL,US,100,USD,inf\n"
    )
    report = validate_csv(csv_bytes)
    assert report["valid_rows"] == 0
    reasons = report["errors"][0]["reasons"]
    assert "Volume must be a finite number." in reasons


def test_negative_and_zero_price_no_duplicate_error():
    csv_bytes = (
        b"date,ticker,market,close,currency\n"
        b"2025-01-02,AAPL,US,0,USD\n"
        b"2025-01-03,AAPL,US,-10,USD\n"
    )
    report = validate_csv(csv_bytes)
    assert report["valid_rows"] == 0
    assert report["rejected_rows"] == 2
    for err in report["errors"]:
        # Verify exactly one reason per row for close <= 0, no duplicate
        assert err["reasons"] == ["Close must be a positive number."]


def test_negative_volume():
    csv_bytes = (
        b"date,ticker,market,close,currency,volume\n2025-01-02,AAPL,US,100,USD,-500\n"
    )
    report = validate_csv(csv_bytes)
    assert report["valid_rows"] == 0
    reasons = report["errors"][0]["reasons"]
    assert "Volume must be non-negative." in reasons


def test_legitimate_missing_optional_values_allowed():
    csv_bytes = (
        b"date,ticker,market,close,currency,open,volume\n"
        b"2025-01-02,AAPL,US,100,USD,,1000\n"
        b"2025-01-03,AAPL,US,102,USD,101,\n"
    )
    report = validate_csv(csv_bytes)
    assert report["valid_rows"] == 2
    assert report["rejected_rows"] == 0
    assert report["valid_data"][0]["open"] is None
    assert report["valid_data"][0]["volume"] == 1000.0
    assert report["valid_data"][1]["open"] == 101.0
    assert report["valid_data"][1]["volume"] is None


def test_duplicate_observations_excluded_with_sorted_row_numbers():
    csv_bytes = (
        b"date,ticker,market,close,currency\n"
        b"2025-01-02,AAPL,US,100,USD\n"
        b"2025-01-02,AAPL,US,105,USD\n"
        b"2025-01-03,AAPL,US,-1,USD\n"
    )
    report = validate_csv(csv_bytes)
    assert report["valid_rows"] == 0
    assert report["rejected_rows"] == 3
    # Check that error rows are sorted in ascending order
    row_numbers = [err["row"] for err in report["errors"]]
    assert row_numbers == sorted(row_numbers)


def test_invalid_date_format():
    csv_bytes = b"date,ticker,market,close,currency\nnot_a_date,AAPL,US,100,USD\n"
    report = validate_csv(csv_bytes)
    assert report["valid_rows"] == 0
    reasons = report["errors"][0]["reasons"]
    assert "Invalid or missing date." in reasons


def test_unsupported_market_identifier():
    csv_bytes = b"date,ticker,market,close,currency\n2025-01-02,BTC,CRYPTO,50000,USD\n"
    report = validate_csv(csv_bytes)
    assert report["valid_rows"] == 0
    reasons = report["errors"][0]["reasons"]
    assert "Market must be US or PSX." in reasons


def test_missing_required_column_raises_value_error():
    csv_bytes = b"date,market,close,currency\n2025-01-02,US,100,USD\n"
    with pytest.raises(ValueError, match="CSV is missing required columns: ticker"):
        validate_csv(csv_bytes)


def test_empty_and_whitespace_csv_raises_value_error():
    with pytest.raises(ValueError, match="Uploaded file is empty"):
        validate_csv(b"")
    with pytest.raises(ValueError, match="Uploaded file is empty"):
        validate_csv(b"   \n\n  \t ")
