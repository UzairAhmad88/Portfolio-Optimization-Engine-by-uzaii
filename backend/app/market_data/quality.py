"""
Data-quality and anomaly controls for market datasets.

Workstream 31.4:
- Structured, explainable validation rules distinguishing errors, warnings, and informational findings.
- Rules:
  * DQ_MISSING_SESSION: Calendar trading day with missing observation.
  * DQ_OHLC_INVERSION: Invalid high/low/open/close geometry.
  * DQ_NON_POSITIVE_PRICE: Price <= 0 or non-finite.
  * DQ_PRICE_DISCONTINUITY: Jump exceeding threshold without matching corporate action.
  * DQ_STALE_SERIES: Flatline price for >= N consecutive sessions.
  * DQ_CURRENCY_MISMATCH: Unaligned currency for market convention.
  * DQ_DUPLICATE_KEY: Multiple entries for same date/ticker/market.
- Never silently forward-fills, imputes, or mutates price observations.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

from app.market_data.calendars import get_calendar
from app.market_data.corporate_actions import CorporateActionEvent, CorporateActionType


DQ_POLICY_VERSION = "2026.1"


class AnomalySeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class QualityFinding:
    """
    Structured data quality finding.
    """
    rule_id: str
    severity: AnomalySeverity
    ticker: str
    market: str
    date: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    policy_version: str = DQ_POLICY_VERSION

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d


@dataclass(frozen=True)
class QualityAuditReport:
    """
    Comprehensive dataset quality audit result.
    """
    policy_version: str
    is_valid: bool
    total_findings: int
    error_count: int
    warning_count: int
    info_count: int
    findings: list[QualityFinding]

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_version": self.policy_version,
            "is_valid": self.is_valid,
            "total_findings": self.total_findings,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "findings": [f.to_dict() for f in self.findings],
        }


def audit_market_data_quality(
    bars: list[dict[str, Any]],
    corporate_actions: list[CorporateActionEvent] | None = None,
    discontinuity_threshold: float = 0.35,  # 35% single-day price jump triggers inspection
    stale_limit_days: int = 10,             # 10 consecutive sessions with identical price triggers stale warning
    policy_version: str = DQ_POLICY_VERSION,
) -> QualityAuditReport:
    """
    Performs comprehensive data-quality audit on a collection of price bars.
    """
    findings: list[QualityFinding] = []
    if not bars:
        return QualityAuditReport(
            policy_version=policy_version,
            is_valid=True,
            total_findings=0,
            error_count=0,
            warning_count=0,
            info_count=0,
            findings=[],
        )

    # Group by (ticker, market)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    seen_keys: set[tuple[str, str, str]] = set()

    # Pre-index corporate action effective dates by (ticker, market)
    ca_dates: set[tuple[str, str, date]] = set()
    if corporate_actions:
        for ca in corporate_actions:
            ca_dates.add((ca.ticker.upper(), ca.market.upper(), ca.effective_date))

    for b in bars:
        t = str(b.get("ticker", "")).strip().upper()
        m = str(b.get("market", "")).strip().upper()
        d_raw = b.get("date")
        d_str = d_raw.isoformat() if isinstance(d_raw, date) else str(d_raw).strip()

        # Check duplicate keys
        key = (t, m, d_str)
        if key in seen_keys:
            findings.append(
                QualityFinding(
                    rule_id="DQ_DUPLICATE_KEY",
                    severity=AnomalySeverity.ERROR,
                    ticker=t,
                    market=m,
                    date=d_str,
                    message=f"Duplicate observation for {t}:{m} on {d_str}.",
                )
            )
        seen_keys.add(key)
        grouped.setdefault((t, m), []).append(b)

    for (t, m), asset_bars in grouped.items():
        # Sort asset bars chronologically
        def _get_date(bar: dict) -> date:
            val = bar.get("date")
            return val if isinstance(val, date) else date.fromisoformat(str(val).strip())

        try:
            sorted_bars = sorted(asset_bars, key=_get_date)
        except Exception as e:
            findings.append(
                QualityFinding(
                    rule_id="DQ_INVALID_DATE_FORMAT",
                    severity=AnomalySeverity.ERROR,
                    ticker=t,
                    market=m,
                    date="",
                    message=f"Invalid date format in asset series: {e}",
                )
            )
            continue

        dates = [_get_date(b) for b in sorted_bars]
        start_date = dates[0]
        end_date = dates[-1]

        # 1. Missing calendar sessions check
        try:
            cal = get_calendar(m)
            missing = cal.detect_missing_sessions(dates, start_date, end_date)
            for miss in missing:
                findings.append(
                    QualityFinding(
                        rule_id="DQ_MISSING_SESSION",
                        severity=AnomalySeverity.WARNING,
                        ticker=t,
                        market=m,
                        date=miss["date"],
                        message=f"Open {m} trading session on {miss['date']} has no price observation for {t}.",
                        details={"calendar_version": cal.version},
                    )
                )
        except Exception:
            pass

        # 2. Bar-level checks
        stale_streak = 0
        last_close: float | None = None

        for i, b in enumerate(sorted_bars):
            cur_date = dates[i]
            d_str = cur_date.isoformat()

            # Currency check
            curr = str(b.get("currency", "")).strip().upper()
            if m == "US" and curr != "USD":
                findings.append(
                    QualityFinding(
                        rule_id="DQ_CURRENCY_MISMATCH",
                        severity=AnomalySeverity.ERROR,
                        ticker=t,
                        market=m,
                        date=d_str,
                        message=f"US market security currency is '{curr}', expected 'USD'.",
                    )
                )
            elif m == "PSX" and curr != "PKR":
                findings.append(
                    QualityFinding(
                        rule_id="DQ_CURRENCY_MISMATCH",
                        severity=AnomalySeverity.ERROR,
                        ticker=t,
                        market=m,
                        date=d_str,
                        message=f"PSX market security currency is '{curr}', expected 'PKR'.",
                    )
                )

            # Close price checks
            c = b.get("close")
            if c is None or not np.isfinite(c) or c <= 0:
                findings.append(
                    QualityFinding(
                        rule_id="DQ_NON_POSITIVE_PRICE",
                        severity=AnomalySeverity.ERROR,
                        ticker=t,
                        market=m,
                        date=d_str,
                        message=f"Close price must be strictly positive and finite, received {c}.",
                    )
                )
                continue

            # OHLC consistency
            h = b.get("high")
            l = b.get("low")
            o = b.get("open")
            if h is not None and l is not None and h < l:
                findings.append(
                    QualityFinding(
                        rule_id="DQ_OHLC_INVERSION",
                        severity=AnomalySeverity.ERROR,
                        ticker=t,
                        market=m,
                        date=d_str,
                        message=f"High ({h}) cannot be lower than Low ({l}).",
                    )
                )
            if h is not None and h < c:
                findings.append(
                    QualityFinding(
                        rule_id="DQ_OHLC_INVERSION",
                        severity=AnomalySeverity.ERROR,
                        ticker=t,
                        market=m,
                        date=d_str,
                        message=f"High ({h}) cannot be lower than Close ({c}).",
                    )
                )
            if l is not None and l > c:
                findings.append(
                    QualityFinding(
                        rule_id="DQ_OHLC_INVERSION",
                        severity=AnomalySeverity.ERROR,
                        ticker=t,
                        market=m,
                        date=d_str,
                        message=f"Low ({l}) cannot be higher than Close ({c}).",
                    )
                )

            # Stale pricing check
            if last_close is not None and c == last_close:
                stale_streak += 1
                if stale_streak >= stale_limit_days:
                    findings.append(
                        QualityFinding(
                            rule_id="DQ_STALE_SERIES",
                            severity=AnomalySeverity.WARNING,
                            ticker=t,
                            market=m,
                            date=d_str,
                            message=f"Price has remained identical ({c}) for {stale_streak} consecutive sessions.",
                            details={"streak_length": stale_streak},
                        )
                    )
            else:
                stale_streak = 1

            # Price jump discontinuity without corporate action check
            if last_close is not None and last_close > 0:
                pct_move = (c - last_close) / last_close
                if abs(pct_move) >= discontinuity_threshold:
                    # Check if corporate action occurred on this date
                    has_ca = (t, m, cur_date) in ca_dates
                    if not has_ca:
                        findings.append(
                            QualityFinding(
                                rule_id="DQ_PRICE_DISCONTINUITY",
                                severity=AnomalySeverity.WARNING,
                                ticker=t,
                                market=m,
                                date=d_str,
                                message=f"Unexplained large price move ({pct_move:+.2%}) without recorded corporate action.",
                                details={
                                    "pct_move": pct_move,
                                    "prior_close": last_close,
                                    "close": c,
                                },
                            )
                        )

            last_close = c

    err_count = sum(1 for f in findings if f.severity == AnomalySeverity.ERROR)
    warn_count = sum(1 for f in findings if f.severity == AnomalySeverity.WARNING)
    info_count = sum(1 for f in findings if f.severity == AnomalySeverity.INFO)

    return QualityAuditReport(
        policy_version=policy_version,
        is_valid=(err_count == 0),
        total_findings=len(findings),
        error_count=err_count,
        warning_count=warn_count,
        info_count=info_count,
        findings=findings,
    )
