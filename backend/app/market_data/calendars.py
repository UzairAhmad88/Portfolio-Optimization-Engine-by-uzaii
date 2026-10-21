"""
Exchange calendars and session integrity module for US Equities (NYSE/NASDAQ) and PSX (Pakistan Stock Exchange).

Workstream 31.1:
- Distinct market-specific exchange calendars with explicit timezone and calendar versioning.
- Distinguishes regular trading sessions, weekends, statutory holidays, lunar/religious holidays, and historic closures.
- Detects missing market data observations on genuine trading days without false-positive flagging of holidays/weekends.
- Cross-market session alignment utilities.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta
from typing import Any, Iterable
import zoneinfo


CALENDAR_VERSION_US = "US-NYSE-2026.1"
CALENDAR_VERSION_PSX = "PSX-KHI-2026.1"


class ExchangeCalendar(ABC):
    """
    Abstract base class for financial market exchange trading calendars.
    """

    def __init__(self, market: str, calendar_id: str, version: str, tz_name: str) -> None:
        self.market = market.upper()
        self.calendar_id = calendar_id
        self.version = version
        self.tz_name = tz_name
        self.timezone = zoneinfo.ZoneInfo(tz_name)

    @abstractmethod
    def is_session(self, dt: date) -> bool:
        """Returns True if the given date is an active, open trading session."""
        pass

    @abstractmethod
    def holiday_reason(self, dt: date) -> str | None:
        """Returns the holiday or closure reason if closed, else None."""
        pass

    def get_sessions(self, start_date: date, end_date: date) -> list[date]:
        """
        Returns a sorted list of open trading sessions between start_date and end_date (inclusive).
        """
        if start_date > end_date:
            return []
        sessions: list[date] = []
        cur = start_date
        one_day = timedelta(days=1)
        while cur <= end_date:
            if self.is_session(cur):
                sessions.append(cur)
            cur += one_day
        return sessions

    def detect_missing_sessions(
        self,
        observed_dates: Iterable[date | str],
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """
        Detects missing observations on expected trading sessions.
        Does NOT flag weekends or legitimate holidays.

        Returns a list of records:
            {"date": "YYYY-MM-DD", "market": self.market, "severity": "error", "reason": "Missing expected session observation."}
        """
        expected = set(self.get_sessions(start_date, end_date))
        observed: set[date] = set()
        for d in observed_dates:
            if isinstance(d, str):
                observed.add(date.fromisoformat(d.strip()))
            elif isinstance(d, date):
                observed.add(d)

        missing = sorted(expected - observed)
        return [
            {
                "date": m.isoformat(),
                "market": self.market,
                "severity": "error",
                "rule_id": "DQ_MISSING_SESSION",
                "reason": f"Expected trading session on {m.isoformat()} has no recorded price observation.",
                "calendar_version": self.version,
            }
            for m in missing
        ]


class USCalendar(ExchangeCalendar):
    """
    US Equities (NYSE / NASDAQ) Trading Calendar.
    Conventions:
    - Normal trading days: Monday through Friday, 09:30 - 16:00 ET (America/New_York).
    - Standard US Federal & Exchange Holidays:
      * New Year's Day (Jan 1, observed on Dec 31 if Sat, Jan 2 if Sun).
      * Martin Luther King, Jr. Day (3rd Monday in Jan).
      * Washington's Birthday / Presidents' Day (3rd Monday in Feb).
      * Good Friday (Friday before Easter Sunday).
      * Memorial Day (Last Monday in May).
      * Juneteenth National Independence Day (June 19, observed June 18 if Sat, June 20 if Sun - official holiday since 2022).
      * Independence Day (July 4, observed July 3 if Sat, July 5 if Sun).
      * Labor Day (1st Monday in Sept).
      * Thanksgiving Day (4th Thursday in Nov).
      * Christmas Day (Dec 25, observed Dec 24 if Sat, Dec 26 if Sun).
    - Documented Historical Exceptional Closures:
      * 2001-09-11 through 2001-09-14: 9/11 Terrorist Attacks.
      * 2004-06-11: National Day of Mourning for President Ronald Reagan.
      * 2007-01-02: National Day of Mourning for President Gerald Ford.
      * 2012-10-29 and 2012-10-30: Hurricane Sandy severe weather closure.
      * 2018-12-05: National Day of Mourning for President George H.W. Bush.
    """

    EXCEPTIONAL_CLOSURES: dict[date, str] = {
        date(2001, 9, 11): "9/11 Terrorist Attacks closure",
        date(2001, 9, 12): "9/11 Terrorist Attacks closure",
        date(2001, 9, 13): "9/11 Terrorist Attacks closure",
        date(2001, 9, 14): "9/11 Terrorist Attacks closure",
        date(2004, 6, 11): "National Day of Mourning for President Ronald Reagan",
        date(2007, 1, 2): "National Day of Mourning for President Gerald Ford",
        date(2012, 10, 29): "Hurricane Sandy weather closure",
        date(2012, 10, 30): "Hurricane Sandy weather closure",
        date(2018, 12, 5): "National Day of Mourning for President George H.W. Bush",
    }

    def __init__(self, version: str = CALENDAR_VERSION_US) -> None:
        super().__init__(
            market="US",
            calendar_id="US_EQUITY",
            version=version,
            tz_name="America/New_York",
        )

    def is_session(self, dt: date) -> bool:
        if dt.weekday() >= 5:  # Saturday or Sunday
            return False
        if dt in self.EXCEPTIONAL_CLOSURES:
            return False
        return self._get_holiday_reason(dt) is None

    def holiday_reason(self, dt: date) -> str | None:
        if dt.weekday() == 5:
            return "Saturday"
        if dt.weekday() == 6:
            return "Sunday"
        if dt in self.EXCEPTIONAL_CLOSURES:
            return self.EXCEPTIONAL_CLOSURES[dt]
        return self._get_holiday_reason(dt)

    def _get_holiday_reason(self, dt: date) -> str | None:
        y = dt.year
        m = dt.month
        d = dt.day
        wd = dt.weekday()

        # 1. New Year's Day (Jan 1) with observation rule
        if m == 1 and d == 1 and wd < 5:
            return "New Year's Day"
        if m == 1 and d == 2 and wd == 0:  # Sunday Jan 1 observed Monday Jan 2
            return "New Year's Day (Observed)"
        if m == 12 and d == 31 and wd == 4:  # Saturday Jan 1 observed Friday Dec 31
            return "New Year's Day (Observed)"

        # 2. Martin Luther King Jr. Day (3rd Monday in January)
        if m == 1 and wd == 0 and 15 <= d <= 21:
            return "Martin Luther King, Jr. Day"

        # 3. Presidents' Day (3rd Monday in February)
        if m == 2 and wd == 0 and 15 <= d <= 21:
            return "Presidents' Day"

        # 4. Good Friday (computus algorithm for Easter)
        if self._is_good_friday(dt):
            return "Good Friday"

        # 5. Memorial Day (Last Monday in May)
        if m == 5 and wd == 0 and d >= 25:
            return "Memorial Day"

        # 6. Juneteenth (June 19, celebrated starting in 2022)
        if y >= 2022:
            if m == 6 and d == 19 and wd < 5:
                return "Juneteenth National Independence Day"
            if m == 6 and d == 18 and wd == 4:  # Sat June 19 -> Fri June 18
                return "Juneteenth National Independence Day (Observed)"
            if m == 6 and d == 20 and wd == 0:  # Sun June 19 -> Mon June 20
                return "Juneteenth National Independence Day (Observed)"

        # 7. Independence Day (July 4)
        if m == 7 and d == 4 and wd < 5:
            return "Independence Day"
        if m == 7 and d == 3 and wd == 4:  # Sat July 4 -> Fri July 3
            return "Independence Day (Observed)"
        if m == 7 and d == 5 and wd == 0:  # Sun July 4 -> Mon July 5
            return "Independence Day (Observed)"

        # 8. Labor Day (1st Monday in September)
        if m == 9 and wd == 0 and d <= 7:
            return "Labor Day"

        # 9. Thanksgiving Day (4th Thursday in November)
        if m == 11 and wd == 3 and 22 <= d <= 28:
            return "Thanksgiving Day"

        # 10. Christmas Day (Dec 25)
        if m == 12 and d == 25 and wd < 5:
            return "Christmas Day"
        if m == 12 and d == 24 and wd == 4:  # Sat Dec 25 -> Fri Dec 24
            return "Christmas Day (Observed)"
        if m == 12 and d == 26 and wd == 0:  # Sun Dec 25 -> Mon Dec 26
            return "Christmas Day (Observed)"

        return None

    @staticmethod
    def _is_good_friday(dt: date) -> bool:
        """Anonymous Gregorian algorithm to compute Good Friday (Easter Sunday - 2 days)."""
        year = dt.year
        a = year % 19
        b = year // 100
        c = year % 100
        d = b // 4
        e = b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i = c // 4
        k = c % 4
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        month = (h + l - 7 * m + 114) // 31
        day = ((h + l - 7 * m + 114) % 31) + 1
        easter_sunday = date(year, month, day)
        good_friday = easter_sunday - timedelta(days=2)
        return dt == good_friday


class PSXCalendar(ExchangeCalendar):
    """
    Pakistan Stock Exchange (PSX - Karachi / Lahore / Islamabad) Trading Calendar.
    Conventions:
    - Normal trading days: Monday through Friday (Asia/Karachi).
    - Fixed National & Public Holidays:
      * Jan 1: Bank Holiday (PSX closed for public transactions).
      * Feb 5: Kashmir Solidarity Day.
      * Mar 23: Pakistan Day.
      * May 1: Labour Day.
      * Jul 1: Bank Holiday (Mid-Year Financial Year Closing).
      * Aug 14: Independence Day.
      * Nov 9: Iqbal Day (observed as public holiday in recent years/notification).
      * Dec 25: Quaid-e-Azam Day / Christmas.
    - Verified Islamic Lunar Holidays (Authoritative official notification dates):
      * Eid-ul-Fitr (3 to 5 days).
      * Eid-ul-Adha (3 to 4 days).
      * Ashura (9th & 10th Muharram, 2 days).
      * Eid Milad-un-Nabi (12th Rabi-ul-Awal, 1 day).
      * Shab-e-Barat / Ramadan start (where gazetted by PSX notices).

    Coverage Boundary & Gazette Dependency (DEF-31-02):
      Islamic lunar calendar dates in Pakistan depend on authoritative physical
      moon-sighting determinations by the Central Ruet-e-Hilal Committee and official
      annual gazetted notifications by the Government of Pakistan / PSX.
      Authoritative gazetted holiday closures are provided for 2020 through 2026.
      For trading sessions outside 2020–2026, fixed statutory holidays and weekends are
      accurately enforced, while lunar holiday closures require annual gazette updates.
    """

    LUNAR_COVERAGE_START_YEAR: int = 2020
    LUNAR_COVERAGE_END_YEAR: int = 2026
    LUNAR_COVERAGE_RANGE: tuple[int, int] = (2020, 2026)

    FIXED_HOLIDAYS: dict[tuple[int, int], str] = {
        (1, 1): "Bank Holiday (New Year Closing)",
        (2, 5): "Kashmir Solidarity Day",
        (3, 23): "Pakistan Day",
        (5, 1): "Labour Day",
        (7, 1): "Bank Holiday (Mid-Year Closing)",
        (8, 14): "Independence Day",
        (11, 9): "Iqbal Day",
        (12, 25): "Quaid-e-Azam Day",
    }

    # Verified official PSX gazetted lunar and special closures (2020 through 2026)
    LUNAR_AND_SPECIAL_CLOSURES: dict[date, str] = {
        # 2020
        date(2020, 4, 24): "1st Ramadan Bank Holiday",
        date(2020, 5, 22): "Jumat-ul-Wida / Shab-e-Qadr",
        date(2020, 5, 25): "Eid-ul-Fitr Holiday",
        date(2020, 5, 26): "Eid-ul-Fitr Holiday",
        date(2020, 5, 27): "Eid-ul-Fitr Holiday",
        date(2020, 7, 31): "Eid-ul-Adha Holiday",
        date(2020, 8, 28): "Ashura (9th Muharram)",
        date(2020, 10, 30): "Eid Milad-un-Nabi",

        # 2021
        date(2021, 5, 10): "Eid-ul-Fitr Holiday",
        date(2021, 5, 11): "Eid-ul-Fitr Holiday",
        date(2021, 5, 12): "Eid-ul-Fitr Holiday",
        date(2021, 5, 13): "Eid-ul-Fitr Holiday",
        date(2021, 5, 14): "Eid-ul-Fitr Holiday",
        date(2021, 7, 20): "Eid-ul-Adha Holiday",
        date(2021, 7, 21): "Eid-ul-Adha Holiday",
        date(2021, 7, 22): "Eid-ul-Adha Holiday",
        date(2021, 8, 18): "Ashura (9th Muharram)",
        date(2021, 8, 19): "Ashura (10th Muharram)",
        date(2021, 10, 19): "Eid Milad-un-Nabi",

        # 2022
        date(2022, 5, 2): "Eid-ul-Fitr Holiday",
        date(2022, 5, 3): "Eid-ul-Fitr Holiday",
        date(2022, 5, 4): "Eid-ul-Fitr Holiday",
        date(2022, 5, 5): "Eid-ul-Fitr Holiday",
        date(2022, 7, 8): "Eid-ul-Adha Holiday",
        date(2022, 7, 11): "Eid-ul-Adha Holiday",
        date(2022, 7, 12): "Eid-ul-Adha Holiday",
        date(2022, 8, 8): "Ashura (9th Muharram)",
        date(2022, 8, 9): "Ashura (10th Muharram)",

        # 2023
        date(2023, 4, 21): "Eid-ul-Fitr Holiday",
        date(2023, 4, 24): "Eid-ul-Fitr Holiday",
        date(2023, 4, 25): "Eid-ul-Fitr Holiday",
        date(2023, 6, 28): "Eid-ul-Adha Holiday",
        date(2023, 6, 29): "Eid-ul-Adha Holiday",
        date(2023, 6, 30): "Eid-ul-Adha Holiday",
        date(2023, 7, 28): "Ashura (9th/10th Muharram)",
        date(2023, 9, 29): "Eid Milad-un-Nabi",

        # 2024
        date(2024, 2, 8): "General Elections Public Holiday",
        date(2024, 4, 10): "Eid-ul-Fitr Holiday",
        date(2024, 4, 11): "Eid-ul-Fitr Holiday",
        date(2024, 4, 12): "Eid-ul-Fitr Holiday",
        date(2024, 5, 28): "Youm-e-Takbeer Public Holiday",
        date(2024, 6, 17): "Eid-ul-Adha Holiday",
        date(2024, 6, 18): "Eid-ul-Adha Holiday",
        date(2024, 6, 19): "Eid-ul-Adha Holiday",
        date(2024, 7, 16): "Ashura (9th Muharram)",
        date(2024, 7, 17): "Ashura (10th Muharram)",
        date(2024, 9, 17): "Eid Milad-un-Nabi",

        # 2025
        date(2025, 3, 31): "Eid-ul-Fitr Holiday",
        date(2025, 4, 1): "Eid-ul-Fitr Holiday",
        date(2025, 4, 2): "Eid-ul-Fitr Holiday",
        date(2025, 6, 6): "Eid-ul-Adha Holiday",
        date(2025, 6, 9): "Eid-ul-Adha Holiday",
        date(2025, 7, 4): "Ashura (9th Muharram)",
        date(2025, 7, 7): "Ashura (10th Muharram)",
        date(2025, 9, 5): "Eid Milad-un-Nabi",

        # 2026
        date(2026, 3, 20): "Eid-ul-Fitr Holiday",
        date(2026, 3, 23): "Pakistan Day / Eid-ul-Fitr Holiday",
        date(2026, 3, 24): "Eid-ul-Fitr Holiday",
        date(2026, 5, 27): "Eid-ul-Adha Holiday",
        date(2026, 5, 28): "Eid-ul-Adha Holiday",
        date(2026, 6, 24): "Ashura (9th Muharram)",
        date(2026, 6, 25): "Ashura (10th Muharram)",
        date(2026, 8, 26): "Eid Milad-un-Nabi",
    }

    def __init__(self, version: str = CALENDAR_VERSION_PSX) -> None:
        super().__init__(
            market="PSX",
            calendar_id="PSX_EQUITY",
            version=version,
            tz_name="Asia/Karachi",
        )

    def is_session(self, dt: date) -> bool:
        if dt.weekday() >= 5:  # Saturday or Sunday
            return False
        if dt in self.LUNAR_AND_SPECIAL_CLOSURES:
            return False
        key = (dt.month, dt.day)
        if key in self.FIXED_HOLIDAYS:
            return False
        return True

    def holiday_reason(self, dt: date) -> str | None:
        if dt.weekday() == 5:
            return "Saturday"
        if dt.weekday() == 6:
            return "Sunday"
        if dt in self.LUNAR_AND_SPECIAL_CLOSURES:
            return self.LUNAR_AND_SPECIAL_CLOSURES[dt]
        key = (dt.month, dt.day)
        if key in self.FIXED_HOLIDAYS:
            return self.FIXED_HOLIDAYS[key]
        return None


def get_calendar(market: str) -> ExchangeCalendar:
    """
    Factory returning the authoritative exchange calendar for the given market.
    """
    m = market.strip().upper()
    if m == "US":
        return USCalendar()
    elif m == "PSX":
        return PSXCalendar()
    else:
        raise ValueError(f"Unsupported market '{market}'. Must be 'US' or 'PSX'.")


def align_cross_market_sessions(
    dates_us: Iterable[date],
    dates_psx: Iterable[date],
    method: str = "intersection",
) -> tuple[list[date], list[dict[str, Any]]]:
    """
    Aligns dates across US and PSX markets.
    method:
      - 'intersection': Only dates open in both markets (strictly synchronized, no forward-fill).
      - 'union': All dates open in at least one market, with documented warnings for holiday asymmetries.

    Returns:
      (aligned_dates, alignment_warnings)
    """
    set_us = set(dates_us)
    set_psx = set(dates_psx)
    warnings: list[dict[str, Any]] = []

    cal_us = USCalendar()
    cal_psx = PSXCalendar()

    if method == "intersection":
        common = sorted(set_us & set_psx)
        # Note dates dropped due to holiday asymmetry
        dropped_us = set_us - set_psx
        dropped_psx = set_psx - set_us
        if dropped_us:
            warnings.append({
                "type": "CROSS_MARKET_DROPPED_DATES",
                "market": "US",
                "count": len(dropped_us),
                "message": f"{len(dropped_us)} US dates dropped because PSX was closed (e.g. {sorted(dropped_us)[:3]}).",
            })
        if dropped_psx:
            warnings.append({
                "type": "CROSS_MARKET_DROPPED_DATES",
                "market": "PSX",
                "count": len(dropped_psx),
                "message": f"{len(dropped_psx)} PSX dates dropped because US was closed (e.g. {sorted(dropped_psx)[:3]}).",
            })
        return common, warnings
    elif method == "union":
        all_dates = sorted(set_us | set_psx)
        for d in all_dates:
            us_open = d in set_us
            psx_open = d in set_psx
            if us_open and not psx_open:
                reason = cal_psx.holiday_reason(d) or "Closed"
                warnings.append({
                    "date": d.isoformat(),
                    "market_closed": "PSX",
                    "reason": reason,
                    "message": f"US was open but PSX was closed on {d.isoformat()} ({reason}).",
                })
            elif psx_open and not us_open:
                reason = cal_us.holiday_reason(d) or "Closed"
                warnings.append({
                    "date": d.isoformat(),
                    "market_closed": "US",
                    "reason": reason,
                    "message": f"PSX was open but US was closed on {d.isoformat()} ({reason}).",
                })
        return all_dates, warnings
    else:
        raise ValueError(f"Unknown alignment method '{method}'. Must be 'intersection' or 'union'.")
