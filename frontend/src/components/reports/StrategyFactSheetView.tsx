/**
 * Institutional Strategy Fact Sheet (Exactly One Intended Page)
 * High-information-density executive layout containing:
 * - Report Header & Metadata
 * - Mandate & Constraints Summary
 * - Executive KPIs (Dual Gross/Net)
 * - Benchmark Attribution Strip
 * - Compact Vector Equity Curve (Preserving 250 downsampled observations)
 * - Monthly Net Returns Compounded Matrix
 * - Top Asset Holdings
 * - Provenance & Regulatory Disclaimers
 */

import React from 'react';
import type { StrategyFactSheetPayload } from '../../types/reporting';
import {
  ReportHeaderAndProvenance,
  ReportWarningsBanner,
  ReportProvenanceFooter,
} from './ReportHeaderAndProvenance';
import { ExecutiveKPISummary } from './ExecutiveKPISummary';
import { VectorEquityCurve } from './VectorEquityCurve';
import { MonthlyReturnsGrid } from './MonthlyReturnsGrid';
import { AssetAllocationChart } from './AssetAllocationChart';

interface StrategyFactSheetViewProps {
  payload: StrategyFactSheetPayload;
}

export const StrategyFactSheetView: React.FC<StrategyFactSheetViewProps> = ({ payload }) => {
  const { envelope, mandate, kpis, benchmark_metrics, compact_wealth_curve, monthly_returns, top_holdings } =
    payload;

  return (
    <article className="report-sheet-page fact-sheet-page" role="document" aria-label="Strategy Fact Sheet">
      {/* Page Header */}
      <ReportHeaderAndProvenance
        envelope={envelope}
        mandate={mandate}
        pageNumber={1}
        totalPages={1}
        subtitle="Executive Strategy Fact Sheet — Quantitative Investment Performance & Holdings Profile"
      />

      {/* Warnings if present */}
      <ReportWarningsBanner warnings={envelope.warnings} />

      {/* Executive KPIs & Benchmark Strip */}
      <ExecutiveKPISummary kpis={kpis} benchmarkMetrics={benchmark_metrics} compact={true} />

      {/* Main Analytical Section: Compact Equity Curve & Monthly Returns */}
      <div className="report-two-panel-grid">
        <div className="panel-left">
          <VectorEquityCurve
            data={compact_wealth_curve}
            baseCurrency={envelope.base_currency}
            height={190}
            benchmarkName={benchmark_metrics?.benchmark_name}
            compact={true}
          />
        </div>
        <div className="panel-right">
          <MonthlyReturnsGrid cells={monthly_returns} showGross={false} />
        </div>
      </div>

      {/* Top Holdings Breakdown */}
      <AssetAllocationChart allocations={top_holdings} compact={true} />

      {/* Provenance Footer */}
      <ReportProvenanceFooter envelope={envelope} />
    </article>
  );
};
