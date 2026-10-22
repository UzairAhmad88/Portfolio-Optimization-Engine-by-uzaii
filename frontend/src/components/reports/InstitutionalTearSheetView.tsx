/**
 * Institutional Tear Sheet (Exactly Two Intended Pages)
 *
 * Page 1: Performance & Risk
 * - Header & Strategy Mandate
 * - Executive KPIs & Gross vs Net Comparative Breakdown
 * - Benchmark Attribution Matrix
 * - Full High-Resolution Vector Equity & Drawdown Curve
 * - Peak/Trough Drawdown Analysis
 *
 * Page 2: Return, Portfolio, TCA & Provenance
 * - Header Page 2 Counter
 * - Monthly Returns Compounded Matrix
 * - Comprehensive Asset Allocation & Return Contributions
 * - Transaction Cost Analysis (TCA), Turnover & Execution Drag
 * - Data Snapshot Provenance & Certified Manifest Lineage
 * - Regulatory Warnings & Disclaimers
 */

import React from 'react';
import type { InstitutionalTearSheetPayload } from '../../types/reporting';
import {
  ReportHeaderAndProvenance,
  ReportWarningsBanner,
  ReportProvenanceFooter,
} from './ReportHeaderAndProvenance';
import { ExecutiveKPISummary } from './ExecutiveKPISummary';
import { VectorEquityCurve } from './VectorEquityCurve';
import { MonthlyReturnsGrid } from './MonthlyReturnsGrid';
import { AssetAllocationChart } from './AssetAllocationChart';
import { formatBps, formatCurrency, formatPercent, formatRatio } from './formatters';

interface InstitutionalTearSheetViewProps {
  payload: InstitutionalTearSheetPayload;
}

export const InstitutionalTearSheetView: React.FC<InstitutionalTearSheetViewProps> = ({ payload }) => {
  const {
    envelope,
    mandate,
    kpis,
    benchmark_metrics,
    equity_curve,
    monthly_returns_table,
    asset_allocation,
    friction_and_execution,
  } = payload;

  return (
    <div className="report-multi-page-container" role="document" aria-label="Institutional Tear Sheet">
      {/* ================= PAGE 1 ================= */}
      <article className="report-sheet-page tear-sheet-page-1">
        <ReportHeaderAndProvenance
          envelope={envelope}
          mandate={mandate}
          pageNumber={1}
          totalPages={2}
          subtitle="Institutional Performance, Benchmark Attribution & Tail Risk Profile"
        />

        <ReportWarningsBanner warnings={envelope.warnings} />

        <ExecutiveKPISummary kpis={kpis} benchmarkMetrics={benchmark_metrics} compact={false} />

        {/* Full-width High-Resolution Equity & Drawdown Curve */}
        <VectorEquityCurve
          data={equity_curve}
          baseCurrency={envelope.base_currency}
          height={240}
          showDrawdown={true}
          benchmarkName={benchmark_metrics?.benchmark_name}
          compact={false}
        />

        {/* Peak-to-Trough Drawdown Details Strip */}
        <div className="report-drawdown-details-strip" role="region" aria-label="Drawdown Profile">
          <div className="dd-item">
            <span className="dd-label">Peak Date:</span>
            <span className="dd-val font-mono">{kpis.drawdown_peak_date || '—'}</span>
          </div>
          <div className="dd-item">
            <span className="dd-label">Trough Date:</span>
            <span className="dd-val font-mono">{kpis.drawdown_trough_date || '—'}</span>
          </div>
          <div className="dd-item">
            <span className="dd-label">Recovery Date:</span>
            <span className="dd-val font-mono">{kpis.drawdown_recovery_date || 'Unrecovered'}</span>
          </div>
          <div className="dd-item">
            <span className="dd-label">Drawdown Duration:</span>
            <span className="dd-val font-mono">
              {kpis.drawdown_duration_days != null ? `${kpis.drawdown_duration_days} days` : '—'}
            </span>
          </div>
          <div className="dd-item">
            <span className="dd-label">Profit / Loss Ratio:</span>
            <span className="dd-val font-mono font-bold">{formatRatio(kpis.profit_loss_ratio, 2)}</span>
          </div>
        </div>

        <div className="page-break-hint">Page 1 of 2 — Turn over for Allocations, TCA &amp; Lineage</div>
      </article>

      {/* ================= PAGE 2 ================= */}
      <article className="report-sheet-page tear-sheet-page-2">
        <div className="report-page-2-header">
          <div className="page-2-title">
            <span className="font-bold">{envelope.report_title}</span> — Portfolio Composition, TCA &amp; Provenance
          </div>
          <div className="page-2-counter font-mono">Page 2 / 2</div>
        </div>

        {/* Monthly Compounded Return Matrix */}
        <MonthlyReturnsGrid cells={monthly_returns_table} showGross={true} />

        {/* Complete Asset Allocation & Risk Breakdown */}
        <AssetAllocationChart allocations={asset_allocation} compact={false} />

        {/* Transaction Cost Analysis (TCA) & Execution Drag Grid */}
        {friction_and_execution && (
          <div className="report-tca-section" role="region" aria-label="Transaction Cost Analysis">
            <div className="report-section-heading">Transaction Cost Analysis (TCA) &amp; Execution Drag</div>
            <div className="tca-grid">
              <div className="tca-card">
                <span className="tca-label">Cumulative Turnover</span>
                <span className="tca-val font-mono">{formatPercent(friction_and_execution.total_turnover, 1)}</span>
                <span className="tca-sub font-mono">
                  Ann: {formatPercent(friction_and_execution.annualized_turnover, 1)}
                </span>
              </div>
              <div className="tca-card">
                <span className="tca-label">Model Friction Drag</span>
                <span className="tca-val font-mono highlight">
                  {formatBps(friction_and_execution.friction_drag_bps, 1)}
                </span>
                <span className="tca-sub font-mono">
                  Cost: {formatBps(friction_and_execution.transaction_cost_bps, 1)} | Slip:{' '}
                  {formatBps(friction_and_execution.slippage_bps, 1)}
                </span>
              </div>
              <div className="tca-card">
                <span className="tca-label">Total Execution Friction</span>
                <span className="tca-val font-mono">
                  {formatCurrency(friction_and_execution.total_friction_costs, envelope.base_currency, 2)}
                </span>
                <span className="tca-sub font-mono">
                  TC: {formatCurrency(friction_and_execution.total_transaction_costs, envelope.base_currency, 1)} | Slip:{' '}
                  {formatCurrency(friction_and_execution.total_slippage_costs, envelope.base_currency, 1)}
                </span>
              </div>
              <div className="tca-card">
                <span className="tca-label">Rebalance Executions</span>
                <span className="tca-val font-mono">{friction_and_execution.number_of_rebalances}</span>
                <span className="tca-sub">scheduled portfolio rebalances</span>
              </div>
            </div>
          </div>
        )}

        {/* Full Provenance & Legal Disclaimers */}
        <ReportProvenanceFooter envelope={envelope} />
      </article>
    </div>
  );
};
