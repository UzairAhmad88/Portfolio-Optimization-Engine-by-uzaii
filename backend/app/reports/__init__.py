"""
Institutional reporting module for Stage 34.
Provides domain contracts, metric registries, and reporting schemas for
Strategy Fact Sheets, Institutional Tear Sheets, and Research Diagnostics Annexes.
"""

from app.reports.contracts import (
    CommonReportEnvelope,
    ExecutiveKPIs,
    BenchmarkRelativeMetrics,
    AssetAllocationItem,
    TimeSeriesPoint,
    MonthlyReturnCell,
    FrictionAndExecutionMetrics,
    StrategyMandate,
    ReportWarning,
    StrategyFactSheetPayload,
    InstitutionalTearSheetPayload,
    ResearchDiagnosticsAnnexPayload,
    InstitutionalReportResponse,
)
from app.reports.assembler import ReportAssemblerService
from app.reports.renderer import count_pdf_pages, get_chromium_executable, render_html_to_pdf
from app.reports.pdf_templates import (
    render_fact_sheet_html,
    render_research_annex_html,
    render_tear_sheet_html,
    render_unified_report_html,
)

__all__ = [
    "CommonReportEnvelope",
    "ExecutiveKPIs",
    "BenchmarkRelativeMetrics",
    "AssetAllocationItem",
    "TimeSeriesPoint",
    "MonthlyReturnCell",
    "FrictionAndExecutionMetrics",
    "StrategyMandate",
    "ReportWarning",
    "StrategyFactSheetPayload",
    "InstitutionalTearSheetPayload",
    "ResearchDiagnosticsAnnexPayload",
    "InstitutionalReportResponse",
    "ReportAssemblerService",
    "count_pdf_pages",
    "get_chromium_executable",
    "render_html_to_pdf",
    "render_fact_sheet_html",
    "render_tear_sheet_html",
    "render_research_annex_html",
    "render_unified_report_html",
]
