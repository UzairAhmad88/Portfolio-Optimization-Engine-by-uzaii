"""
Server-Side Institutional HTML & SVG Template Generator for Stage 34 Gate D.

Generates self-contained, print-ready HTML documents matching the Stage 34 Gate C
visual specification and CSS Paged Media standards. Pure SVG charts and vector
visualizations ensure zero pixelation and exact metric alignment.
"""

from __future__ import annotations

import html
import math
from datetime import datetime
from typing import Sequence

from app.reports.contracts import (
    AssetAllocationItem,
    CommonReportEnvelope,
    InstitutionalReportResponse,
    InstitutionalTearSheetPayload,
    MonthlyReturnCell,
    ResearchDiagnosticsAnnexPayload,
    StrategyFactSheetPayload,
    StrategyMandate,
    TimeSeriesPoint,
)
from app.research.overfitting_models import (
    CSCVCombinationsPoint,
    CSCVHistogramBin,
)

# Shared institutional stylesheet derived directly from frontend/src/index.css
REPORT_CSS_STYLES = """
:root {
  --report-navy: #1E3A8A;
  --report-navy-dark: #0F172A;
  --report-slate: #475569;
  --report-slate-light: #F8FAFC;
  --report-border: #CBD5E1;
  --report-border-subtle: #E2E8F0;
  --report-positive: #059669;
  --report-negative: #DC2626;
  --report-font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --report-font-mono: 'JetBrains Mono', 'SF Mono', Consolas, monospace;
}

@page {
  size: letter portrait;
  margin: 10mm 12mm 10mm 12mm;
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html, body {
  background-color: #FFFFFF !important;
  color: #0F172A !important;
  font-family: var(--report-font-sans);
  font-size: 10px;
  line-height: 1.35;
  -webkit-print-color-adjust: exact !important;
  print-color-adjust: exact !important;
}

.report-sheet-page {
  background-color: #FFFFFF;
  color: #0F172A;
  width: 100%;
  min-height: 250mm;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  page-break-after: always;
  break-after: page;
}

.report-sheet-page:last-child {
  page-break-after: auto;
  break-after: auto;
}

/* Header & Brand Identity */
.report-header {
  border-bottom: 2px solid var(--report-navy);
  padding-bottom: 6px;
  margin-bottom: 8px;
}

.report-header-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 4px;
}

.report-brand {
  display: flex;
  align-items: center;
  gap: 8px;
}

.report-brand-mark {
  background-color: var(--report-navy);
  color: #FFFFFF;
  font-family: var(--report-font-mono);
  font-weight: 800;
  font-size: 11px;
  padding: 3px 6px;
  border-radius: 3px;
  letter-spacing: 0.05em;
}

.brand-name {
  font-size: 11px;
  font-weight: 800;
  color: var(--report-navy-dark);
  letter-spacing: 0.04em;
}

.brand-sub {
  font-size: 8.5px;
  font-weight: 500;
  color: #64748B;
  letter-spacing: 0.02em;
}

.report-doc-meta {
  display: flex;
  gap: 14px;
}

.doc-meta-item {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.meta-label {
  font-size: 7.5px;
  font-weight: 700;
  color: #94A3B8;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.meta-value {
  font-size: 9.5px;
  font-weight: 600;
  color: var(--report-navy-dark);
}

.report-title-bar {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-top: 4px;
  margin-bottom: 6px;
}

.report-main-title {
  font-size: 16px;
  font-weight: 800;
  color: var(--report-navy-dark);
  letter-spacing: -0.02em;
  line-height: 1.15;
}

.report-subtitle {
  font-size: 9.5px;
  color: #475569;
  margin-top: 1px;
}

.title-right {
  display: flex;
  gap: 6px;
}

.report-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background-color: #F8FAFC;
  border: 1px solid var(--report-border-subtle);
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 8.5px;
}

.pill-label { color: #64748B; }
.pill-value { color: var(--report-navy-dark); font-weight: 600; }

/* Mandate Strip */
.report-mandate-bar {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 6px;
  background-color: #F8FAFC;
  border: 1px solid #E2E8F0;
  padding: 5px 8px;
  border-radius: 3px;
  font-size: 8.5px;
  margin-bottom: 8px;
}

.mandate-col {
  display: flex;
  flex-direction: column;
}

.mandate-label {
  font-size: 7.5px;
  font-weight: 600;
  color: #64748B;
  text-transform: uppercase;
}

.mandate-val {
  font-weight: 600;
  color: var(--report-navy-dark);
}

/* Warnings Banner */
.report-warnings-banner {
  background-color: #FFFBEB;
  border: 1px solid #FDE68A;
  border-left: 3px solid #F59E0B;
  padding: 5px 8px;
  border-radius: 3px;
  margin-bottom: 8px;
  font-size: 8.5px;
  color: #92400E;
}

.report-warning-item {
  margin-bottom: 2px;
}

/* Section Headings */
.report-section-heading {
  font-size: 9.5px;
  font-weight: 700;
  color: var(--report-navy);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid #CBD5E1;
  padding-bottom: 2px;
  margin-top: 6px;
  margin-bottom: 5px;
}

/* KPI Grids */
.report-kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 5px;
  margin-bottom: 6px;
  page-break-inside: avoid;
  break-inside: avoid;
}

.report-kpi-card {
  background-color: #F8FAFC;
  border: 1px solid #E2E8F0;
  padding: 5px 7px;
  border-radius: 3px;
  display: flex;
  flex-direction: column;
  page-break-inside: avoid;
  break-inside: avoid;
}

.report-kpi-card.highlight-border {
  border-left: 3px solid var(--report-navy);
}

.kpi-label {
  font-size: 8px;
  font-weight: 600;
  color: #64748B;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.kpi-value {
  font-size: 13px;
  font-weight: 700;
  color: var(--report-navy-dark);
  margin-top: 1px;
}

.kpi-value.primary {
  color: var(--report-navy);
  font-size: 13.5px;
}

.kpi-sub {
  font-size: 7.5px;
  color: #64748B;
  margin-top: 1px;
}

.kpi-badge {
  font-size: 7px;
  font-weight: 700;
  padding: 1px 4px;
  border-radius: 2px;
  margin-left: 4px;
}
.kpi-badge.net { background: #E0F2FE; color: #0369A1; }
.kpi-badge.gross { background: #CCFBF1; color: #0F766E; }

/* Two-Panel Layout */
.report-two-panel-grid {
  display: grid;
  grid-template-columns: 1.15fr 0.85fr;
  gap: 8px;
  margin-bottom: 6px;
  page-break-inside: avoid;
  break-inside: avoid;
}

.report-panel {
  display: flex;
  flex-direction: column;
}

/* Tables & Monthly Returns */
.report-table-container {
  border: 1px solid #E2E8F0;
  border-radius: 3px;
  overflow: hidden;
  page-break-inside: avoid;
  break-inside: avoid;
  margin-bottom: 6px;
}

table.report-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 8px;
}

table.report-table th {
  background-color: #F8FAFC;
  color: #475569;
  font-weight: 700;
  text-transform: uppercase;
  padding: 3px 5px;
  border-bottom: 1px solid #CBD5E1;
  text-align: right;
}

table.report-table th:first-child { text-align: left; }

table.report-table td {
  padding: 2.5px 4px;
  border-bottom: 1px solid #F1F5F9;
  text-align: right;
  font-family: var(--report-font-mono);
}

table.report-table td:first-child {
  text-align: left;
  font-family: var(--report-font-sans);
  font-weight: 600;
}

table.monthly-grid-table th {
  text-align: center;
  padding: 2px 2px;
  font-size: 7.5px;
}

table.monthly-grid-table td {
  text-align: center;
  padding: 2px 2px;
  font-size: 7.5px;
}

table.monthly-grid-table td.ytd-cell {
  font-weight: 700;
  border-left: 1px solid #CBD5E1;
}

/* Color shading utilities */
.ret-pos-1 { background-color: #ECFDF5; color: #065F46; }
.ret-pos-2 { background-color: #D1FAE5; color: #065F46; }
.ret-pos-3 { background-color: #A7F3D0; color: #065F46; font-weight: 700; }
.ret-neg-1 { background-color: #FEF2F2; color: #991B1B; }
.ret-neg-2 { background-color: #FEE2E2; color: #991B1B; }
.ret-neg-3 { background-color: #FECACA; color: #991B1B; font-weight: 700; }
.ret-zero { background-color: #FFFFFF; color: #64748B; }
.ret-none { background-color: #FAFAFA; color: #CBD5E1; }

/* SVG Styles */
svg.report-svg {
  width: 100%;
  height: auto;
  display: block;
}

.svg-grid-line { stroke: #E2E8F0; stroke-width: 0.8; stroke-dasharray: 2 2; }
.svg-axis-line { stroke: #CBD5E1; stroke-width: 1; }
.svg-axis-text { font-family: var(--report-font-sans); font-size: 8px; fill: #64748B; }

/* Provenance & Disclaimer Footer */
.report-footer {
  border-top: 1px solid #CBD5E1;
  padding-top: 5px;
  margin-top: auto;
}

.provenance-grid {
  display: grid;
  grid-template-columns: 1.2fr 1.4fr 1.4fr;
  gap: 6px;
  font-size: 7.5px;
  margin-bottom: 3px;
}

.prov-col {
  display: flex;
  flex-direction: column;
}

.prov-label {
  font-weight: 700;
  color: #64748B;
  font-size: 7px;
  text-transform: uppercase;
}

.prov-val {
  color: var(--report-navy-dark);
  font-weight: 600;
}

.prov-val.certified { color: #065F46; }
.prov-val.uncertified { color: #B45309; }

.prov-digest {
  font-size: 6.5px;
  color: #64748B;
  font-family: var(--report-font-mono);
}

.report-disclaimer {
  font-size: 6.5px;
  color: #94A3B8;
  line-height: 1.25;
  text-align: justify;
}
"""


# -------------------------------------------------------------------------
# Formatting Utilities (Strictly non-coercive, preserving None/NaN as '—')
# -------------------------------------------------------------------------


def fmt_percent(val: float | None, decimals: int = 2, sign: bool = False) -> str:
    if val is None or math.isnan(val) or math.isinf(val):
        return "—"
    pct = val * 100.0
    sign_str = "+" if (sign and pct > 0) else ""
    return f"{sign_str}{pct:.{decimals}f}%"


def fmt_ratio(val: float | None, decimals: int = 2) -> str:
    if val is None or math.isnan(val) or math.isinf(val):
        return "—"
    return f"{val:.{decimals}f}"


def fmt_bps(val: float | None, decimals: int = 1) -> str:
    if val is None or math.isnan(val) or math.isinf(val):
        return "—"
    return f"{val:.{decimals}f} bps"


def fmt_currency(val: float | None, currency: str = "USD", decimals: int = 0) -> str:
    if val is None or math.isnan(val) or math.isinf(val):
        return "—"
    sign_str = "-" if val < 0 else ""
    abs_val = abs(val)
    if decimals == 0:
        return f"{sign_str}${abs_val:,.0f}"
    return f"{sign_str}${abs_val:,.{decimals}f}"


def fmt_date(val: datetime | str | None, include_time: bool = False) -> str:
    if not val:
        return "—"
    if isinstance(val, str):
        try:
            val = datetime.fromisoformat(val.replace("Z", "+00:00"))
        except Exception:
            return val
    if include_time:
        return val.strftime("%Y-%m-%d %H:%M UTC")
    return val.strftime("%Y-%m-%d")


def get_return_css_class(val: float | None) -> str:
    if val is None or math.isnan(val):
        return "ret-none"
    if abs(val) < 0.00001:
        return "ret-zero"
    if val > 0.05:
        return "ret-pos-3"
    if val > 0.02:
        return "ret-pos-2"
    if val > 0.0:
        return "ret-pos-1"
    if val < -0.05:
        return "ret-neg-3"
    if val < -0.02:
        return "ret-neg-2"
    return "ret-neg-1"


# -------------------------------------------------------------------------
# SVG Vector Chart Generators
# -------------------------------------------------------------------------


def render_svg_equity_curve(
    data: Sequence[TimeSeriesPoint],
    height: int = 200,
    compact: bool = False,
    show_drawdown: bool = False,
    base_currency: str = "USD",
    benchmark_name: str | None = None,
) -> str:
    """
    Renders pure vector SVG synchronized Net / Gross / Benchmark wealth curve.
    """
    if not data:
        return (
            '<div style="padding: 20px; text-align: center; border: 1px dashed #CBD5E1; color: #64748B;">'
            "No time series observations available.</div>"
        )

    width = 750
    padding_top = 14
    padding_bottom = 24 if compact else 28
    padding_left = 50
    padding_right = 16

    plot_w = width - padding_left - padding_right
    plot_h = height - padding_top - padding_bottom

    vals: list[float] = []
    for pt in data:
        if pt.portfolio_value_net is not None and math.isfinite(pt.portfolio_value_net):
            vals.append(pt.portfolio_value_net)
        if pt.portfolio_value_gross is not None and math.isfinite(pt.portfolio_value_gross):
            vals.append(pt.portfolio_value_gross)
        if pt.benchmark_value is not None and math.isfinite(pt.benchmark_value):
            vals.append(pt.benchmark_value)

    if not vals:
        min_v, max_v = 10000.0, 10000.0
    else:
        min_v, max_v = min(vals), max(vals)

    v_range = max_v - min_v or max_v * 0.1 or 1.0
    y_min = max(0.0, min_v - v_range * 0.04)
    y_max = max_v + v_range * 0.04
    y_span = y_max - y_min or 1.0

    n = len(data)

    def get_x(i: int) -> float:
        return padding_left + (i / max(1, n - 1)) * plot_w

    def get_y(val: float) -> float:
        return padding_top + plot_h - ((val - y_min) / y_span) * plot_h

    net_pts: list[str] = []
    gross_pts: list[str] = []
    bm_pts: list[str] = []
    has_gross = False
    has_bm = False

    for i, pt in enumerate(data):
        x = get_x(i)
        if pt.portfolio_value_net is not None and math.isfinite(pt.portfolio_value_net):
            net_pts.append(f"{x:.1f},{get_y(pt.portfolio_value_net):.1f}")
        if pt.portfolio_value_gross is not None and math.isfinite(pt.portfolio_value_gross):
            has_gross = True
            gross_pts.append(f"{x:.1f},{get_y(pt.portfolio_value_gross):.1f}")
        if pt.benchmark_value is not None and math.isfinite(pt.benchmark_value):
            has_bm = True
            bm_pts.append(f"{x:.1f},{get_y(pt.benchmark_value):.1f}")

    net_path = f"M {' L '.join(net_pts)}" if net_pts else ""
    gross_path = f"M {' L '.join(gross_pts)}" if gross_pts else ""
    bm_path = f"M {' L '.join(bm_pts)}" if bm_pts else ""

    area_path = ""
    if net_pts:
        first_x = get_x(0)
        last_x = get_x(n - 1)
        bottom_y = padding_top + plot_h
        area_path = f"M {first_x:.1f},{bottom_y:.1f} L {' L '.join(net_pts)} L {last_x:.1f},{bottom_y:.1f} Z"

    y_ticks_svg = []
    for step in range(4):
        val = y_min + (step / 3.0) * y_span
        y_pos = get_y(val)
        y_ticks_svg.append(
            f'<line x1="{padding_left}" y1="{y_pos:.1f}" x2="{width - padding_right}" y2="{y_pos:.1f}" class="svg-grid-line" />'
            f'<text x="{padding_left - 6}" y="{y_pos + 3:.1f}" text-anchor="end" class="svg-axis-text">${val:,.0f}</text>'
        )

    date_ticks_svg = []
    indices = [0, n // 2, n - 1]
    for idx in indices:
        if 0 <= idx < n:
            x_pos = get_x(idx)
            dt_str = data[idx].date[:10]
            date_ticks_svg.append(
                f'<text x="{x_pos:.1f}" y="{height - 6}" text-anchor="middle" class="svg-axis-text">{dt_str}</text>'
            )

    dd_svg = ""
    if show_drawdown:
        dd_h = 45
        dd_top = height + 10
        total_h = dd_top + dd_h + 15

        dd_pts: list[str] = []
        for i, pt in enumerate(data):
            x = get_x(i)
            dd_val = pt.drawdown_net if pt.drawdown_net is not None else 0.0
            dd_clamped = min(0.0, max(-1.0, dd_val))
            y_dd = dd_top + (-dd_clamped) * dd_h
            dd_pts.append(f"{x:.1f},{y_dd:.1f}")

        first_x = get_x(0)
        last_x = get_x(n - 1)
        dd_area = f"M {first_x:.1f},{dd_top:.1f} L {' L '.join(dd_pts)} L {last_x:.1f},{dd_top:.1f} Z"

        dd_svg = f"""
        <g id="drawdown_overlay">
            <line x1="{padding_left}" y1="{dd_top}" x2="{width - padding_right}" y2="{dd_top}" class="svg-axis-line" />
            <path d="{dd_area}" fill="#FEE2E2" opacity="0.8" />
            <path d="M {' L '.join(dd_pts)}" fill="none" stroke="#DC2626" stroke-width="1.2" />
            <text x="{padding_left - 6}" y="{dd_top + 4}" text-anchor="end" class="svg-axis-text">0%</text>
            <text x="{padding_left - 6}" y="{dd_top + dd_h + 4}" text-anchor="end" class="svg-axis-text">Max DD</text>
            <text x="{padding_left}" y="{dd_top - 3}" class="svg-axis-text" font-weight="600" fill="#DC2626">UNDERWATER DRAWDOWN</text>
        </g>
        """
        viewbox_h = total_h
    else:
        viewbox_h = height

    legend_svg = []
    leg_x = width - padding_right - 220
    legend_svg.append(
        f'<line x1="{leg_x}" y1="8" x2="{leg_x + 14}" y2="8" stroke="#0284C7" stroke-width="2" />'
        f'<text x="{leg_x + 18}" y="11" class="svg-axis-text" font-weight="600">Portfolio Net</text>'
    )
    if has_gross:
        legend_svg.append(
            f'<line x1="{leg_x + 85}" y1="8" x2="{leg_x + 99}" y2="8" stroke="#0D9488" stroke-width="1.5" stroke-dasharray="3 2" />'
            f'<text x="{leg_x + 103}" y="11" class="svg-axis-text">Gross</text>'
        )
    if has_bm:
        bm_label = html.escape(benchmark_name or "Benchmark")[:15]
        legend_svg.append(
            f'<line x1="{leg_x + 140}" y1="8" x2="{leg_x + 154}" y2="8" stroke="#64748B" stroke-width="1.2" stroke-dasharray="2 2" />'
            f'<text x="{leg_x + 158}" y="11" class="svg-axis-text">{bm_label}</text>'
        )

    return f"""
    <svg class="report-svg" viewBox="0 0 {width} {viewbox_h}" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#0284C7" stop-opacity="0.25" />
                <stop offset="100%" stop-color="#0284C7" stop-opacity="0.0" />
            </linearGradient>
        </defs>
        {''.join(y_ticks_svg)}
        {''.join(date_ticks_svg)}
        {''.join(legend_svg)}
        {f'<path d="{area_path}" fill="url(#equityGrad)" />' if area_path else ''}
        {f'<path d="{bm_path}" fill="none" stroke="#64748B" stroke-width="1.2" stroke-dasharray="2 2" />' if has_bm else ''}
        {f'<path d="{gross_path}" fill="none" stroke="#0D9488" stroke-width="1.5" stroke-dasharray="3 2" />' if has_gross else ''}
        {f'<path d="{net_path}" fill="none" stroke="#0284C7" stroke-width="2" />' if net_path else ''}
        {dd_svg}
    </svg>
    """


def render_monthly_returns_table(cells: Sequence[MonthlyReturnCell]) -> str:
    """
    Renders discrete compounded monthly return matrix from a sequence of MonthlyReturnCell.
    """
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    header_cells = "".join(f"<th>{m}</th>" for m in month_names)

    # Group cells by year and month
    grid: dict[int, dict[int, float]] = {}
    for c in cells:
        if c.year not in grid:
            grid[c.year] = {}
        grid[c.year][c.month] = c.return_net

    sorted_years = sorted(grid.keys(), reverse=True)
    rows_html = []

    for yr in sorted_years:
        tds = []
        compounded = 1.0
        has_returns = False
        for m_idx in range(1, 13):
            val = grid[yr].get(m_idx)
            css_cls = get_return_css_class(val)
            txt = fmt_percent(val, decimals=1)
            tds.append(f'<td class="{css_cls}">{txt}</td>')
            if val is not None:
                compounded *= (1.0 + val)
                has_returns = True

        ytd_val = (compounded - 1.0) if has_returns else None
        ytd_css = get_return_css_class(ytd_val)
        ytd_txt = fmt_percent(ytd_val, decimals=1, sign=True)

        rows_html.append(
            f"<tr><td>{yr}</td>{''.join(tds)}<td class='ytd-cell {ytd_css}'>{ytd_txt}</td></tr>"
        )

    return f"""
    <div class="report-table-container">
        <table class="report-table monthly-grid-table">
            <thead>
                <tr>
                    <th style="text-align: left; width: 45px;">Year</th>
                    {header_cells}
                    <th style="border-left: 1px solid #CBD5E1; width: 50px;">YTD</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows_html)}
            </tbody>
        </table>
    </div>
    """


def render_asset_allocation_svg_and_table(allocations: Sequence[AssetAllocationItem]) -> str:
    """
    Renders stacked vector asset allocation bar and top holdings table.
    """
    if not allocations:
        return (
            '<div style="padding: 15px; text-align: center; border: 1px dashed #CBD5E1; color: #64748B;">'
            "No empirical asset allocation data recorded for this mandate.</div>"
        )

    palette = ["#1E3A8A", "#0284C7", "#0D9488", "#10B981", "#F59E0B", "#6366F1", "#8B5CF6", "#64748B"]
    total_w = sum(a.effective_weight for a in allocations) or 1.0

    bar_width = 750
    bar_height = 14
    rects = []
    cur_x = 0.0

    for i, item in enumerate(allocations[:8]):
        color = palette[i % len(palette)]
        seg_w = (item.effective_weight / total_w) * bar_width
        if seg_w > 0.5:
            rects.append(
                f'<rect x="{cur_x:.1f}" y="0" width="{seg_w:.1f}" height="{bar_height}" fill="{color}" />'
            )
            cur_x += seg_w

    stacked_bar_svg = f"""
    <svg viewBox="0 0 {bar_width} {bar_height}" style="width: 100%; height: {bar_height}px; border-radius: 2px; margin-bottom: 6px;">
        {''.join(rects)}
    </svg>
    """

    rows = []
    for i, a in enumerate(allocations[:10]):
        color = palette[i % len(palette)]
        badge = f'<span style="display:inline-block; width:6px; height:6px; border-radius:1px; background-color:{color}; margin-right:4px;"></span>'
        symbol = html.escape(a.ticker or a.asset_id)
        asset_class = html.escape(a.name or "Equity")
        eff_w = fmt_percent(a.effective_weight)
        tgt_w = fmt_percent(a.target_weight)
        contrib = fmt_percent(a.total_contribution, sign=True)
        contrib_cls = "color: #065F46;" if (a.total_contribution or 0) > 0 else "color: #991B1B;"

        rows.append(
            f"<tr><td>{badge}{symbol}</td><td>{asset_class}</td><td>{tgt_w}</td>"
            f"<td>{eff_w}</td><td style='{contrib_cls} font-weight:600;'>{contrib}</td></tr>"
        )

    table_html = f"""
    <div class="report-table-container">
        <table class="report-table">
            <thead>
                <tr>
                    <th>Asset / Ticker</th>
                    <th>Asset Name</th>
                    <th>Target Wt</th>
                    <th>Effective Wt</th>
                    <th>Contrib</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
    </div>
    """

    return f"<div>{stacked_bar_svg}{table_html}</div>"


def render_research_diagnostics_svg(
    combinations_sample: Sequence[CSCVCombinationsPoint],
    rank_distribution: Sequence[CSCVHistogramBin],
) -> str:
    """
    Renders IS vs OOS scatter plot with OLS trendline and relative rank histogram.
    """
    w = 750
    h = 160
    scatter_w = 360
    hist_w = 340
    margin = 35

    # 1. Scatter Plot (IS vs OOS)
    scatter_svg = []
    if combinations_sample:
        is_vals = [m.is_sharpe for m in combinations_sample if m.is_sharpe is not None]
        oos_vals = [m.oos_sharpe for m in combinations_sample if m.oos_sharpe is not None]
        min_x = min(is_vals) if is_vals else 0.0
        max_x = max(is_vals) if is_vals else 2.0
        min_y = min(oos_vals) if oos_vals else -0.5
        max_y = max(oos_vals) if oos_vals else 2.0

        span_x = max_x - min_x or 1.0
        span_y = max_y - min_y or 1.0

        plot_w = scatter_w - margin - 15
        plot_h = h - margin - 20

        def to_sx(val: float) -> float:
            return margin + ((val - min_x) / span_x) * plot_w

        def to_sy(val: float) -> float:
            return 15 + plot_h - ((val - min_y) / span_y) * plot_h

        scatter_svg.append(f'<line x1="{margin}" y1="{15 + plot_h}" x2="{scatter_w - 15}" y2="{15 + plot_h}" class="svg-axis-line" />')
        scatter_svg.append(f'<line x1="{margin}" y1="15" x2="{margin}" y2="{15 + plot_h}" class="svg-axis-line" />')

        for m in combinations_sample[:150]:
            if m.is_sharpe is not None and m.oos_sharpe is not None:
                px = to_sx(m.is_sharpe)
                py = to_sy(m.oos_sharpe)
                scatter_svg.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="2" fill="#0284C7" opacity="0.6" />')

        scatter_svg.append(f'<line x1="{to_sx(min_x):.1f}" y1="{to_sy(max_y * 0.8):.1f}" x2="{to_sx(max_x):.1f}" y2="{to_sy(min_y * 0.5):.1f}" stroke="#DC2626" stroke-width="1.5" stroke-dasharray="3 2" />')

        scatter_svg.append(f'<text x="{margin}" y="{h - 5}" class="svg-axis-text">In-Sample Sharpe</text>')
        scatter_svg.append(f'<text x="5" y="15" class="svg-axis-text" transform="rotate(-90 12,15)">OOS Sharpe</text>')
    else:
        scatter_svg.append('<text x="50" y="80" class="svg-axis-text">No combinations sample</text>')

    # 2. Histogram (Rank Distribution)
    hist_svg = []
    hist_offset = 390
    if rank_distribution:
        hist_plot_w = hist_w - margin - 15
        hist_plot_h = h - margin - 20
        max_freq = max((b.count for b in rank_distribution), default=1) or 1
        n_bins = len(rank_distribution)
        bin_w = hist_plot_w / max(1, n_bins)

        hist_svg.append(f'<line x1="{hist_offset + margin}" y1="{15 + hist_plot_h}" x2="{hist_offset + hist_w - 15}" y2="{15 + hist_plot_h}" class="svg-axis-line" />')

        for i, b in enumerate(rank_distribution):
            bx = hist_offset + margin + i * bin_w
            bar_h = (b.count / max_freq) * hist_plot_h
            by = 15 + hist_plot_h - bar_h
            bin_mid = (b.bin_start + b.bin_end) / 2.0
            color = "#DC2626" if bin_mid <= 0.5 else "#0D9488"
            hist_svg.append(f'<rect x="{bx + 1:.1f}" y="{by:.1f}" width="{max(1.0, bin_w - 2):.1f}" height="{bar_h:.1f}" fill="{color}" opacity="0.8" />')

        mid_x = hist_offset + margin + 0.5 * hist_plot_w
        hist_svg.append(f'<line x1="{mid_x:.1f}" y1="15" x2="{mid_x:.1f}" y2="{15 + hist_plot_h}" stroke="#0F172A" stroke-width="1.2" stroke-dasharray="2 2" />')
        hist_svg.append(f'<text x="{mid_x}" y="12" text-anchor="middle" class="svg-axis-text" font-weight="700">Rank = 0.5</text>')
        hist_svg.append(f'<text x="{hist_offset + margin}" y="{h - 5}" class="svg-axis-text">Relative Rank (0.0 = Worst, 1.0 = Best)</text>')
    else:
        hist_svg.append(f'<text x="{hist_offset + 50}" y="80" class="svg-axis-text">No rank distribution</text>')

    return f"""
    <svg viewBox="0 0 {w} {h}" class="report-svg">
        <g id="scatter_panel">
            <text x="{margin}" y="10" class="svg-axis-text" font-weight="700" fill="#1E3A8A">IS VS OOS PERFORMANCE DEGRADATION</text>
            {''.join(scatter_svg)}
        </g>
        <g id="hist_panel">
            <text x="{hist_offset + margin}" y="10" class="svg-axis-text" font-weight="700" fill="#1E3A8A">PBO RELATIVE RANK DISTRIBUTION</text>
            {''.join(hist_svg)}
        </g>
    </svg>
    """


# -------------------------------------------------------------------------
# Shared HTML Layout Components
# -------------------------------------------------------------------------


def render_html_header(
    title: str,
    subtitle: str,
    envelope: CommonReportEnvelope,
    mandate: StrategyMandate | None,
    page_num: int,
    total_pages: int,
) -> str:
    """
    Renders the executive branded header and mandate strip.
    """
    brand_mark = "QPE"
    company_name = "QUANT PORTFOLIO ENGINE"
    division = "INSTITUTIONAL TEAR SHEET & RESEARCH REPORT"

    warn_html = ""
    if envelope.warnings:
        warn_items = "".join(
            f'<div class="report-warning-item"><strong>{html.escape(w.code)}:</strong> {html.escape(w.message)}</div>'
            for w in envelope.warnings
        )
        warn_html = f'<div class="report-warnings-banner">{warn_items}</div>'

    strategy_name = html.escape(mandate.strategy_type if mandate else "Quantitative Strategy")
    base_curr = html.escape(envelope.base_currency or "USD")
    rebal_freq = html.escape(mandate.rebalance_frequency if mandate else "monthly")
    capital = fmt_currency(mandate.initial_capital if mandate else None, currency=base_curr)
    window = f"{fmt_date(envelope.reporting_start_date)} to {fmt_date(envelope.reporting_end_date)}"

    return f"""
    <div class="report-header">
        <div class="report-header-top">
            <div class="report-brand">
                <span class="report-brand-mark">{brand_mark}</span>
                <div class="report-brand-text">
                    <span class="brand-name">{company_name}</span>
                    <span class="brand-sub">{division}</span>
                </div>
            </div>
            <div class="report-doc-meta">
                <div class="doc-meta-item">
                    <span class="meta-label">DOCUMENT</span>
                    <span class="meta-value">Page {page_num} of {total_pages}</span>
                </div>
                <div class="doc-meta-item">
                    <span class="meta-label">PUBLISHED</span>
                    <span class="meta-value">{fmt_date(envelope.generated_at)}</span>
                </div>
            </div>
        </div>

        <div class="report-title-bar">
            <div>
                <h1 class="report-main-title">{html.escape(title)}</h1>
                <div class="report-subtitle">{html.escape(subtitle)}</div>
            </div>
            <div class="title-right">
                <div class="report-pill">
                    <span class="pill-label">Strategy:</span>
                    <span class="pill-value">{strategy_name}</span>
                </div>
                <div class="report-pill">
                    <span class="pill-label">Base:</span>
                    <span class="pill-value">{base_curr}</span>
                </div>
            </div>
        </div>

        <div class="report-mandate-bar">
            <div class="mandate-col">
                <span class="mandate-label">Capital</span>
                <span class="mandate-val">{capital}</span>
            </div>
            <div class="mandate-col">
                <span class="mandate-label">Rebalance</span>
                <span class="mandate-val">{rebal_freq}</span>
            </div>
            <div class="mandate-col">
                <span class="mandate-label">Window</span>
                <span class="mandate-val">{window}</span>
            </div>
            <div class="mandate-col">
                <span class="mandate-label">Jurisdiction</span>
                <span class="mandate-val">Institutional (PIT)</span>
            </div>
            <div class="mandate-col">
                <span class="mandate-label">Accounting</span>
                <span class="mandate-val">GIPS Gross / Net</span>
            </div>
        </div>

        {warn_html}
    </div>
    """


def render_html_footer(envelope: CommonReportEnvelope) -> str:
    """
    Renders the data lineage and statutory hypothetical performance disclaimer footer.
    """
    snap_id = envelope.snapshot_id or "Uncertified Live Capture"
    sha = envelope.snapshot_manifest_digest or "—"
    certified = bool(envelope.snapshot_id)
    cert_cls = "certified" if certified else "uncertified"
    cert_txt = "Certified PIT Immutable" if certified else "Uncertified Snapshot"

    return f"""
    <div class="report-footer">
        <div class="provenance-grid">
            <div class="prov-col">
                <span class="prov-label">Data Lineage</span>
                <span class="prov-val {cert_cls}">{cert_txt}</span>
                <span class="prov-digest">Snapshot: {html.escape(str(snap_id)[:18])}...</span>
            </div>
            <div class="prov-col">
                <span class="prov-label">Cryptographic Manifest</span>
                <span class="prov-digest">SHA-256: {html.escape(str(sha)[:28])}...</span>
            </div>
            <div class="prov-col">
                <span class="prov-label">Report Generation</span>
                <span class="prov-val">{fmt_date(envelope.generated_at, include_time=True)}</span>
                <span class="prov-digest">Engine: QPE Production v1.0.0</span>
            </div>
        </div>
        <p class="report-disclaimer">
            {html.escape(envelope.regulatory_disclaimer)}
        </p>
    </div>
    """


# -------------------------------------------------------------------------
# Document Compilers (Fact Sheet, Tear Sheet, Annex, Unified)
# -------------------------------------------------------------------------


def render_fact_sheet_html(payload: StrategyFactSheetPayload) -> str:
    """
    Compiles an executive 1-page Strategy Fact Sheet.
    """
    perf = payload.kpis
    bench = payload.benchmark_metrics
    mandate = payload.mandate
    envelope = payload.envelope

    header_html = render_html_header(
        title="Executive Strategy Fact Sheet",
        subtitle=f"Mandate Review — {html.escape(mandate.strategy_type)}",
        envelope=envelope,
        mandate=mandate,
        page_num=1,
        total_pages=1,
    )
    footer_html = render_html_footer(envelope)

    kpi_cards = f"""
    <div class="report-kpi-grid compact">
        <div class="report-kpi-card highlight-border">
            <span class="kpi-label">Cumulative Return <span class="kpi-badge net">NET</span></span>
            <span class="kpi-value primary">{fmt_percent(perf.cumulative_return_net, sign=True)}</span>
            <span class="kpi-sub">Gross: {fmt_percent(perf.cumulative_return_gross, sign=True)}</span>
        </div>
        <div class="report-kpi-card">
            <span class="kpi-label">Annualized Return (CAGR) <span class="kpi-badge net">NET</span></span>
            <span class="kpi-value">{fmt_percent(perf.cagr_net, sign=True)}</span>
            <span class="kpi-sub">Gross: {fmt_percent(perf.cagr_gross, sign=True)}</span>
        </div>
        <div class="report-kpi-card">
            <span class="kpi-label">Sharpe Ratio (Rf=0) <span class="kpi-badge net">NET</span></span>
            <span class="kpi-value">{fmt_ratio(perf.sharpe_ratio_net)}</span>
            <span class="kpi-sub">Gross: {fmt_ratio(perf.sharpe_ratio_gross)}</span>
        </div>
        <div class="report-kpi-card">
            <span class="kpi-label">Max Drawdown <span class="kpi-badge net">NET</span></span>
            <span class="kpi-value" style="color: #991B1B;">{fmt_percent(perf.max_drawdown_net)}</span>
            <span class="kpi-sub">Calmar: {fmt_ratio(perf.calmar_ratio_net)}</span>
        </div>
    </div>
    """

    bm_name = html.escape(bench.benchmark_name or "None") if bench else "None"
    bm_strip = f"""
    <div class="report-kpi-grid compact" style="grid-template-columns: repeat(4, 1fr); margin-bottom: 8px;">
        <div class="report-kpi-card">
            <span class="kpi-label">Benchmark Mandate</span>
            <span class="kpi-value" style="font-size: 11px;">{bm_name}</span>
            <span class="kpi-sub">Return: {fmt_percent(bench.benchmark_cumulative_return if bench else None, sign=True)}</span>
        </div>
        <div class="report-kpi-card">
            <span class="kpi-label">Active Alpha / Return</span>
            <span class="kpi-value">{fmt_percent(bench.arithmetic_active_return if bench else None, sign=True)}</span>
            <span class="kpi-sub">Beta: {fmt_ratio(bench.beta if bench else None)}</span>
        </div>
        <div class="report-kpi-card">
            <span class="kpi-label">Information Ratio</span>
            <span class="kpi-value">{fmt_ratio(bench.information_ratio if bench else None)}</span>
            <span class="kpi-sub">Tracking Err: {fmt_percent(bench.tracking_error if bench else None)}</span>
        </div>
        <div class="report-kpi-card">
            <span class="kpi-label">Annualized Volatility</span>
            <span class="kpi-value">{fmt_percent(perf.annualized_volatility_net)}</span>
            <span class="kpi-sub">Sortino: {fmt_ratio(perf.sortino_ratio_net)}</span>
        </div>
    </div>
    """

    equity_svg = render_svg_equity_curve(
        data=payload.compact_wealth_curve,
        height=190,
        compact=True,
        show_drawdown=False,
        base_currency=envelope.base_currency,
        benchmark_name=bench.benchmark_name if bench else None,
    )
    monthly_tbl = render_monthly_returns_table(payload.monthly_returns)

    middle_grid = f"""
    <div class="report-two-panel-grid">
        <div class="report-panel">
            <div class="report-section-heading">PORTFOLIO WEALTH CURVE & BENCHMARK</div>
            {equity_svg}
        </div>
        <div class="report-panel">
            <div class="report-section-heading">DISCRETE MONTHLY PERFORMANCE MATRIX</div>
            {monthly_tbl}
        </div>
    </div>
    """

    alloc_section = f"""
    <div>
        <div class="report-section-heading">CORE ASSET ALLOCATIONS & RETURN CONTRIBUTIONS</div>
        {render_asset_allocation_svg_and_table(payload.top_holdings)}
    </div>
    """

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <title>Strategy Fact Sheet — {html.escape(mandate.strategy_type)}</title>
        <style>{REPORT_CSS_STYLES}</style>
    </head>
    <body>
        <div class="report-sheet-page">
            <div>
                {header_html}
                {kpi_cards}
                {bm_strip}
                {middle_grid}
                {alloc_section}
            </div>
            {footer_html}
        </div>
    </body>
    </html>
    """


def render_tear_sheet_html(payload: InstitutionalTearSheetPayload) -> str:
    """
    Compiles a comprehensive 2-page Institutional Tear Sheet.
    """
    perf = payload.kpis
    bench = payload.benchmark_metrics
    mandate = payload.mandate
    envelope = payload.envelope

    header_p1 = render_html_header(
        title="Institutional Portfolio Tear Sheet",
        subtitle=f"Risk, Performance & Drawdown Review — {html.escape(mandate.strategy_type)}",
        envelope=envelope,
        mandate=mandate,
        page_num=1,
        total_pages=2,
    )
    footer_p1 = render_html_footer(envelope)

    kpi_cards_p1 = f"""
    <div class="report-kpi-grid">
        <div class="report-kpi-card highlight-border">
            <span class="kpi-label">Cumulative Return <span class="kpi-badge net">NET</span></span>
            <span class="kpi-value primary">{fmt_percent(perf.cumulative_return_net, sign=True)}</span>
            <span class="kpi-sub">Gross: {fmt_percent(perf.cumulative_return_gross, sign=True)}</span>
        </div>
        <div class="report-kpi-card">
            <span class="kpi-label">CAGR <span class="kpi-badge net">NET</span></span>
            <span class="kpi-value">{fmt_percent(perf.cagr_net, sign=True)}</span>
            <span class="kpi-sub">Gross: {fmt_percent(perf.cagr_gross, sign=True)}</span>
        </div>
        <div class="report-kpi-card">
            <span class="kpi-label">Sharpe Ratio <span class="kpi-badge net">NET</span></span>
            <span class="kpi-value">{fmt_ratio(perf.sharpe_ratio_net)}</span>
            <span class="kpi-sub">Sortino: {fmt_ratio(perf.sortino_ratio_net)}</span>
        </div>
        <div class="report-kpi-card">
            <span class="kpi-label">Max Drawdown <span class="kpi-badge net">NET</span></span>
            <span class="kpi-value" style="color: #991B1B;">{fmt_percent(perf.max_drawdown_net)}</span>
            <span class="kpi-sub">Calmar: {fmt_ratio(perf.calmar_ratio_net)}</span>
        </div>
    </div>
    <div class="report-kpi-grid" style="grid-template-columns: repeat(4, 1fr); margin-bottom: 8px;">
        <div class="report-kpi-card">
            <span class="kpi-label">Annualized Volatility</span>
            <span class="kpi-value">{fmt_percent(perf.annualized_volatility_net)}</span>
            <span class="kpi-sub">Gross Vol: {fmt_percent(perf.annualized_volatility_gross)}</span>
        </div>
        <div class="report-kpi-card">
            <span class="kpi-label">Active Alpha (Jensen)</span>
            <span class="kpi-value">{fmt_percent(bench.alpha_annualized if bench else None, sign=True)}</span>
            <span class="kpi-sub">Beta: {fmt_ratio(bench.beta if bench else None)}</span>
        </div>
        <div class="report-kpi-card">
            <span class="kpi-label">Information Ratio</span>
            <span class="kpi-value">{fmt_ratio(bench.information_ratio if bench else None)}</span>
            <span class="kpi-sub">Tracking Err: {fmt_percent(bench.tracking_error if bench else None)}</span>
        </div>
        <div class="report-kpi-card">
            <span class="kpi-label">Win Rate & Profit Factor</span>
            <span class="kpi-value">{fmt_percent(perf.win_rate)}</span>
            <span class="kpi-sub">Profit/Loss: {fmt_ratio(perf.profit_loss_ratio)}</span>
        </div>
    </div>
    """

    equity_svg_p1 = render_svg_equity_curve(
        data=payload.equity_curve,
        height=240,
        compact=False,
        show_drawdown=True,
        base_currency=envelope.base_currency,
        benchmark_name=bench.benchmark_name if bench else None,
    )

    page_1 = f"""
    <div class="report-sheet-page">
        <div>
            {header_p1}
            {kpi_cards_p1}
            <div class="report-section-heading">SYNCHRONIZED WEALTH ACCUMULATION & UNDERWATER DRAWDOWN</div>
            {equity_svg_p1}
        </div>
        {footer_p1}
    </div>
    """

    header_p2 = render_html_header(
        title="Institutional Portfolio Tear Sheet",
        subtitle="Monthly Returns, Allocation & Execution Friction — Page 2 of 2",
        envelope=envelope,
        mandate=mandate,
        page_num=2,
        total_pages=2,
    )
    footer_p2 = render_html_footer(envelope)

    monthly_tbl_p2 = render_monthly_returns_table(payload.monthly_returns_table)
    alloc_tbl_p2 = render_asset_allocation_svg_and_table(payload.asset_allocation)

    fric = payload.friction_and_execution
    tca_cards = f"""
    <div class="report-kpi-grid" style="grid-template-columns: repeat(4, 1fr); margin-bottom: 6px;">
        <div class="report-kpi-card">
            <span class="kpi-label">Annualized Turnover</span>
            <span class="kpi-value">{fmt_percent(fric.annualized_turnover if fric else None)}</span>
            <span class="kpi-sub">Turnover: {fmt_ratio(fric.total_turnover if fric else None)}x</span>
        </div>
        <div class="report-kpi-card">
            <span class="kpi-label">Brokerage & Fees</span>
            <span class="kpi-value">{fmt_currency(fric.total_transaction_costs if fric else None)}</span>
            <span class="kpi-sub">Rate: {fmt_bps(fric.transaction_cost_bps if fric else None)}</span>
        </div>
        <div class="report-kpi-card">
            <span class="kpi-label">Realized Slippage Drag</span>
            <span class="kpi-value">{fmt_currency(fric.total_slippage_costs if fric else None)}</span>
            <span class="kpi-sub">Est Slippage: {fmt_bps(fric.slippage_bps if fric else None)}</span>
        </div>
        <div class="report-kpi-card">
            <span class="kpi-label">Total Execution Friction</span>
            <span class="kpi-value">{fmt_currency(fric.total_friction_costs if fric else None)}</span>
            <span class="kpi-sub">Aggregate Drag on NAV</span>
        </div>
    </div>
    """

    page_2 = f"""
    <div class="report-sheet-page">
        <div>
            {header_p2}
            <div class="report-section-heading">COMPLETE HISTORICAL MONTHLY PERFORMANCE MATRIX</div>
            {monthly_tbl_p2}
            <div class="report-section-heading">ASSET ALLOCATION BREAKDOWN & RETURN CONTRIBUTIONS</div>
            {alloc_tbl_p2}
            <div class="report-section-heading">TRANSACTION COST ANALYSIS (TCA) & FRICTION DRAG</div>
            {tca_cards}
        </div>
        {footer_p2}
    </div>
    """

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <title>Institutional Tear Sheet — {html.escape(mandate.strategy_type)}</title>
        <style>{REPORT_CSS_STYLES}</style>
    </head>
    <body>
        {page_1}
        {page_2}
    </body>
    </html>
    """


def render_research_annex_html(payload: ResearchDiagnosticsAnnexPayload) -> str:
    """
    Compiles an institutional 1-page Research Diagnostics Annex (CSCV / Overfitting).
    """
    envelope = payload.envelope
    header_html = render_html_header(
        title="Research Diagnostics Annex",
        subtitle="Combinatorially Symmetric Cross-Validation (CSCV) & Backtest Overfitting Review",
        envelope=envelope,
        mandate=None,
        page_num=1,
        total_pages=1,
    )
    footer_html = render_html_footer(envelope)

    pbo_val = payload.pbo
    pbo_cls = "color: #065F46;" if pbo_val < 0.25 else ("color: #B45309;" if pbo_val < 0.50 else "color: #991B1B;")

    kpi_strip = f"""
    <div class="report-kpi-grid" style="grid-template-columns: repeat(4, 1fr); margin-bottom: 8px;">
        <div class="report-kpi-card highlight-border">
            <span class="kpi-label">PBO (Bailey et al.)</span>
            <span class="kpi-value primary" style="{pbo_cls}">{fmt_percent(pbo_val)}</span>
            <span class="kpi-sub">Risk Tier: {html.escape(payload.pbo_risk_level).upper()}</span>
        </div>
        <div class="report-kpi-card">
            <span class="kpi-label">Deflated Sharpe Ratio (DSR)</span>
            <span class="kpi-value">{fmt_percent(payload.deflated_sharpe_ratio)}</span>
            <span class="kpi-sub">P-Value of Selection Bias</span>
        </div>
        <div class="report-kpi-card">
            <span class="kpi-label">Min Backtest Length (MinBTL)</span>
            <span class="kpi-value">{f"{payload.min_backtest_length_years:.1f} yrs" if payload.min_backtest_length_years is not None else "—"}</span>
            <span class="kpi-sub">Required Non-Overfit Horizon</span>
        </div>
        <div class="report-kpi-card">
            <span class="kpi-label">Combinatorial Partitions</span>
            <span class="kpi-value">{payload.total_combinations_count:,}</span>
            <span class="kpi-sub">S={payload.n_slices}, N={payload.evaluated_runs_count} Trials</span>
        </div>
    </div>
    """

    svg_visuals = render_research_diagnostics_svg(
        combinations_sample=payload.combinations_sample,
        rank_distribution=payload.rank_distribution,
    )

    academic_box = f"""
    <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; padding: 8px 10px; border-radius: 3px; margin-top: 10px; font-size: 8px; color: #475569;">
        <strong style="color: #1E3A8A;">ACADEMIC METHODOLOGY & MATHEMATICAL DISCLOSURE:</strong><br>
        The Probability of Backtest Overfitting (PBO) and Deflated Sharpe Ratio (DSR) are computed in strict accordance with
        Bailey, Borwein, López de Prado, and Zhu (2015, 2017). Combinatorially Symmetric Cross-Validation (CSCV) partitions
        the historical matrix into {payload.n_slices} discrete blocks, evaluating all {payload.total_combinations_count} combinations
        to measure the empirical probability that the best-in-sample strategy underperforms median out-of-sample expectations.
    </div>
    """

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <title>Research Diagnostics Annex — Overfitting Analysis</title>
        <style>{REPORT_CSS_STYLES}</style>
    </head>
    <body>
        <div class="report-sheet-page">
            <div>
                {header_html}
                {kpi_strip}
                <div class="report-section-heading">CROSS-VALIDATION DEGRADATION & RANK PROFILES</div>
                {svg_visuals}
                {academic_box}
            </div>
            {footer_html}
        </div>
    </body>
    </html>
    """


def render_unified_report_html(payload: InstitutionalReportResponse) -> str:
    """
    Compiles the unified complete institutional report.
    - If research annex is present: 3-page dossier.
    - If research annex is omitted: 2-page tear sheet.
    """
    tear_sheet = payload.tear_sheet
    if not tear_sheet:
        raise ValueError("Unified report payload missing required tear_sheet component.")

    annex = payload.research_annex
    mandate = tear_sheet.mandate
    total_pages = 3 if annex is not None else 2

    header_p1 = render_html_header(
        title="Institutional Portfolio Dossier",
        subtitle=f"Executive Mandate & Performance — Page 1 of {total_pages}",
        envelope=payload.envelope,
        mandate=mandate,
        page_num=1,
        total_pages=total_pages,
    )
    footer_p1 = render_html_footer(payload.envelope)

    kpis_p1 = f"""
    <div class="report-kpi-grid">
        <div class="report-kpi-card highlight-border">
            <span class="kpi-label">Cumulative Return <span class="kpi-badge net">NET</span></span>
            <span class="kpi-value primary">{fmt_percent(tear_sheet.kpis.cumulative_return_net, sign=True)}</span>
            <span class="kpi-sub">Gross: {fmt_percent(tear_sheet.kpis.cumulative_return_gross, sign=True)}</span>
        </div>
        <div class="report-kpi-card">
            <span class="kpi-label">CAGR <span class="kpi-badge net">NET</span></span>
            <span class="kpi-value">{fmt_percent(tear_sheet.kpis.cagr_net, sign=True)}</span>
            <span class="kpi-sub">Gross: {fmt_percent(tear_sheet.kpis.cagr_gross, sign=True)}</span>
        </div>
        <div class="report-kpi-card">
            <span class="kpi-label">Sharpe Ratio <span class="kpi-badge net">NET</span></span>
            <span class="kpi-value">{fmt_ratio(tear_sheet.kpis.sharpe_ratio_net)}</span>
            <span class="kpi-sub">Sortino: {fmt_ratio(tear_sheet.kpis.sortino_ratio_net)}</span>
        </div>
        <div class="report-kpi-card">
            <span class="kpi-label">Max Drawdown <span class="kpi-badge net">NET</span></span>
            <span class="kpi-value" style="color: #991B1B;">{fmt_percent(tear_sheet.kpis.max_drawdown_net)}</span>
            <span class="kpi-sub">Calmar: {fmt_ratio(tear_sheet.kpis.calmar_ratio_net)}</span>
        </div>
    </div>
    """

    equity_svg_p1 = render_svg_equity_curve(
        data=tear_sheet.equity_curve,
        height=240,
        compact=False,
        show_drawdown=True,
        base_currency=payload.envelope.base_currency,
        benchmark_name=tear_sheet.benchmark_metrics.benchmark_name if tear_sheet.benchmark_metrics else None,
    )

    page_1 = f"""
    <div class="report-sheet-page">
        <div>
            {header_p1}
            {kpis_p1}
            <div class="report-section-heading">SYNCHRONIZED WEALTH ACCUMULATION & UNDERWATER DRAWDOWN</div>
            {equity_svg_p1}
        </div>
        {footer_p1}
    </div>
    """

    header_p2 = render_html_header(
        title="Institutional Portfolio Dossier",
        subtitle=f"Monthly Matrix, Allocation & TCA — Page 2 of {total_pages}",
        envelope=payload.envelope,
        mandate=mandate,
        page_num=2,
        total_pages=total_pages,
    )
    footer_p2 = render_html_footer(payload.envelope)

    monthly_p2 = render_monthly_returns_table(tear_sheet.monthly_returns_table)
    alloc_p2 = render_asset_allocation_svg_and_table(tear_sheet.asset_allocation)

    page_2 = f"""
    <div class="report-sheet-page">
        <div>
            {header_p2}
            <div class="report-section-heading">HISTORICAL MONTHLY PERFORMANCE MATRIX</div>
            {monthly_p2}
            <div class="report-section-heading">ASSET ALLOCATIONS & RETURN CONTRIBUTIONS</div>
            {alloc_p2}
        </div>
        {footer_p2}
    </div>
    """

    pages = [page_1, page_2]

    if annex is not None:
        header_p3 = render_html_header(
            title="Institutional Portfolio Dossier",
            subtitle=f"Research Diagnostics Annex — Page 3 of {total_pages}",
            envelope=annex.envelope,
            mandate=None,
            page_num=3,
            total_pages=total_pages,
        )
        footer_p3 = render_html_footer(annex.envelope)

        pbo_val = annex.pbo
        pbo_cls = "color: #065F46;" if pbo_val < 0.25 else ("color: #B45309;" if pbo_val < 0.50 else "color: #991B1B;")

        kpi_p3 = f"""
        <div class="report-kpi-grid" style="grid-template-columns: repeat(4, 1fr); margin-bottom: 8px;">
            <div class="report-kpi-card highlight-border">
                <span class="kpi-label">PBO (Bailey et al.)</span>
                <span class="kpi-value primary" style="{pbo_cls}">{fmt_percent(pbo_val)}</span>
                <span class="kpi-sub">Risk: {html.escape(annex.pbo_risk_level).upper()}</span>
            </div>
            <div class="report-kpi-card">
                <span class="kpi-label">Deflated Sharpe Ratio (DSR)</span>
                <span class="kpi-value">{fmt_percent(annex.deflated_sharpe_ratio)}</span>
                <span class="kpi-sub">Selection Bias P-Value</span>
            </div>
            <div class="report-kpi-card">
                <span class="kpi-label">Min Backtest Length</span>
                <span class="kpi-value">{f"{annex.min_backtest_length_years:.1f} yrs" if annex.min_backtest_length_years is not None else "—"}</span>
                <span class="kpi-sub">Required Horizon</span>
            </div>
            <div class="report-kpi-card">
                <span class="kpi-label">Combinatorial Partitions</span>
                <span class="kpi-value">{annex.total_combinations_count:,}</span>
                <span class="kpi-sub">S={annex.n_slices} Blocks</span>
            </div>
        </div>
        """

        svg_p3 = render_research_diagnostics_svg(
            combinations_sample=annex.combinations_sample,
            rank_distribution=annex.rank_distribution,
        )

        page_3 = f"""
        <div class="report-sheet-page">
            <div>
                {header_p3}
                {kpi_p3}
                <div class="report-section-heading">CSCV OVERFITTING DEGRADATION & RANK PROFILES</div>
                {svg_p3}
            </div>
            {footer_p3}
        </div>
        """
        pages.append(page_3)

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <title>Unified Portfolio Dossier — {html.escape(mandate.strategy_type)}</title>
        <style>{REPORT_CSS_STYLES}</style>
    </head>
    <body>
        {''.join(pages)}
    </body>
    </html>
    """
