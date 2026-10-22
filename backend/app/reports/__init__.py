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
]
