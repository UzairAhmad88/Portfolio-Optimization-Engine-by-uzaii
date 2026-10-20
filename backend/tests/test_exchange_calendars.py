"""
Unit tests for Exchange Calendars and Session Integrity (Workstream 31.1).
"""

from datetime import date
import pytest

from app.market_data.calendars import (
    CALENDAR_VERSION_PSX,
    CALENDAR_VERSION_US,
    PSXCalendar,
    USCalendar,
    align_cross_market_sessions,
    get_calendar,
)


def test_us_calendar_ordinary_sessions_and_weekends():
    cal = USCalendar()
    assert cal.calendar_id == "US_EQUITY"
    assert cal.version == CALENDAR_VERSION_US
    assert cal.tz_name == "America/New_York"

    # Ordinary Wednesday
    wed = date(2024, 6, 12)
    assert cal.is_session(wed) is True
    assert cal.holiday_reason(wed) is None

    # Weekend Saturday and Sunday
    sat = date(2024, 6, 15)
    sun = date(2024, 6, 16)
    assert cal.is_session(sat) is False
    assert cal.holiday_reason(sat) == "Saturday"
    assert cal.is_session(sun) is False
    assert cal.holiday_reason(sun) == "Sunday"


def test_us_calendar_statutory_holidays():
    cal = USCalendar()

    # New Year's Day 2024 (Monday Jan 1)
    assert cal.is_session(date(2024, 1, 1)) is False
    assert "New Year" in (cal.holiday_reason(date(2024, 1, 1)) or "")

    # MLK Day 2024 (Monday Jan 15)
    assert cal.is_session(date(2024, 1, 15)) is False
    assert "King" in (cal.holiday_reason(date(2024, 1, 15)) or "")

    # Presidents' Day 2024 (Monday Feb 19)
    assert cal.is_session(date(2024, 2, 19)) is False

    # Good Friday 2024 (March 29)
    assert cal.is_session(date(2024, 3, 29)) is False
    assert cal.holiday_reason(date(2024, 3, 29)) == "Good Friday"

    # Juneteenth 2024 (Wednesday June 19)
    assert cal.is_session(date(2024, 6, 19)) is False
    assert "Juneteenth" in (cal.holiday_reason(date(2024, 6, 19)) or "")

    # Independence Day 2024 (Thursday July 4)
    assert cal.is_session(date(2024, 7, 4)) is False

    # Labor Day 2024 (Monday Sept 2)
    assert cal.is_session(date(2024, 9, 2)) is False

    # Thanksgiving 2024 (Thursday Nov 28)
    assert cal.is_session(date(2024, 11, 28)) is False

    # Christmas 2024 (Wednesday Dec 25)
    assert cal.is_session(date(2024, 12, 25)) is False


def test_us_calendar_exceptional_historical_closures():
    cal = USCalendar()

    # 9/11 Closure
    d_911 = date(2001, 9, 11)
    assert cal.is_session(d_911) is False
    assert "9/11" in (cal.holiday_reason(d_911) or "")

    # Hurricane Sandy Closure (Oct 29 & 30, 2012)
    sandy1 = date(2012, 10, 29)
    sandy2 = date(2012, 10, 30)
    assert cal.is_session(sandy1) is False
    assert "Hurricane Sandy" in (cal.holiday_reason(sandy1) or "")
    assert cal.is_session(sandy2) is False

    # Bush National Day of Mourning (Dec 5, 2018)
    bush_mourning = date(2018, 12, 5)
    assert cal.is_session(bush_mourning) is False
    assert "Bush" in (cal.holiday_reason(bush_mourning) or "")


def test_psx_calendar_fixed_and_lunar_holidays():
    cal = PSXCalendar()
    assert cal.calendar_id == "PSX_EQUITY"
    assert cal.version == CALENDAR_VERSION_PSX
    assert cal.tz_name == "Asia/Karachi"

    # Normal Tuesday
    tue = date(2024, 5, 14)
    assert cal.is_session(tue) is True

    # Kashmir Solidarity Day (Feb 5)
    kashmir_day = date(2024, 2, 5)
    assert cal.is_session(kashmir_day) is False
    assert "Kashmir" in (cal.holiday_reason(kashmir_day) or "")

    # Pakistan Day (March 23, 2024 was Saturday, check 2023 Friday March 23)
    pak_day_2023 = date(2023, 3, 23)
    assert cal.is_session(pak_day_2023) is False
    assert "Pakistan Day" in (cal.holiday_reason(pak_day_2023) or "")

    # Labour Day (May 1)
    assert cal.is_session(date(2024, 5, 1)) is False

    # Independence Day (Aug 14)
    assert cal.is_session(date(2024, 8, 14)) is False

    # Quaid-e-Azam Day (Dec 25)
    assert cal.is_session(date(2024, 12, 25)) is False

    # Lunar closures: Eid-ul-Fitr 2024 (April 10, 11, 12)
    assert cal.is_session(date(2024, 4, 10)) is False
    assert cal.is_session(date(2024, 4, 11)) is False
    assert cal.is_session(date(2024, 4, 12)) is False

    # Ashura 2024 (July 16, 17)
    assert cal.is_session(date(2024, 7, 16)) is False
    assert cal.is_session(date(2024, 7, 17)) is False


def test_missing_session_detection():
    cal = USCalendar()
    start = date(2024, 6, 10)  # Mon
    end = date(2024, 6, 21)    # Fri

    # June 10 (Mon), 11 (Tue), 12 (Wed), 13 (Thu), 14 (Fri)
    # June 17 (Mon), 18 (Tue), 19 (Wed - Juneteenth Holiday!), 20 (Thu), 21 (Fri)
    # Total expected sessions: 9 (June 19 is holiday, weekends excluded)
    expected_sessions = cal.get_sessions(start, end)
    assert len(expected_sessions) == 9
    assert date(2024, 6, 19) not in expected_sessions

    # Suppose June 13 observation is missing
    observed = [d for d in expected_sessions if d != date(2024, 6, 13)]
    missing = cal.detect_missing_sessions(observed, start, end)

    assert len(missing) == 1
    assert missing[0]["date"] == "2024-06-13"
    assert missing[0]["rule_id"] == "DQ_MISSING_SESSION"
    assert missing[0]["severity"] == "error"

    # Weekends and Juneteenth (June 19) must NOT be flagged as missing
    flagged_dates = [m["date"] for m in missing]
    assert "2024-06-15" not in flagged_dates
    assert "2024-06-16" not in flagged_dates
    assert "2024-06-19" not in flagged_dates


def test_cross_market_session_alignment():
    # 2024-07-04: US closed (Independence Day), PSX open
    # 2024-08-14: PSX closed (Independence Day), US open
    # 2024-07-03: Both open
    dates_us = [date(2024, 7, 3), date(2024, 8, 14)]
    dates_psx = [date(2024, 7, 3), date(2024, 7, 4)]

    # Intersection
    common, warnings_inter = align_cross_market_sessions(dates_us, dates_psx, method="intersection")
    assert common == [date(2024, 7, 3)]
    assert len(warnings_inter) == 2

    # Union
    all_dates, warnings_union = align_cross_market_sessions(dates_us, dates_psx, method="union")
    assert all_dates == [date(2024, 7, 3), date(2024, 7, 4), date(2024, 8, 14)]
    assert len(warnings_union) == 2


def test_calendar_factory():
    us_cal = get_calendar("US")
    assert isinstance(us_cal, USCalendar)

    psx_cal = get_calendar("PSX")
    assert isinstance(psx_cal, PSXCalendar)

    with pytest.raises(ValueError, match="Unsupported market"):
        get_calendar("LSE")
