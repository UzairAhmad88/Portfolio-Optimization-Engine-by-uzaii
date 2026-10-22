/**
 * Institutional Research Diagnostics Annex (Optional Third Page)
 *
 * Provides Stage 33 multiple-testing corrections, Probability of Backtest Overfitting (PBO),
 * Deflated Sharpe Ratio (DSR), Minimum Backtest Length (MinBTL), CSCV distributions,
 * and academic methodology disclaimers (Bailey, Borwein, López de Prado, Zhu 2014).
 */

import React from 'react';
import type { ResearchDiagnosticsAnnexPayload } from '../../types/reporting';
import {
  ReportHeaderAndProvenance,
  ReportWarningsBanner,
  ReportProvenanceFooter,
} from './ReportHeaderAndProvenance';
import { ResearchDiagnosticsVisuals } from './ResearchDiagnosticsVisuals';
import { formatPercent, formatRatio } from './formatters';

interface ResearchDiagnosticsAnnexViewProps {
  payload: ResearchDiagnosticsAnnexPayload;
  pageNumber?: number;
  totalPages?: number;
}

export const ResearchDiagnosticsAnnexView: React.FC<ResearchDiagnosticsAnnexViewProps> = ({
  payload,
  pageNumber = 3,
  totalPages = 3,
}) => {
  const {
    envelope,
    evaluated_runs_count,
    aligned_observations_count,
    n_slices,
    total_combinations_count,
    pbo,
    pbo_risk_level,
    best_run_id,
    best_run_number,
    best_nominal_sharpe,
    expected_max_sharpe,
    deflated_sharpe_ratio,
    is_statistically_significant,
    min_backtest_length_years,
    actual_backtest_length_years,
    skewness,
    kurtosis,
    degradation_regression,
    combinations_sample,
    rank_distribution,
  } = payload;


  return (
    <article className="report-sheet-page research-annex-page" role="document" aria-label="Research Diagnostics Annex">
      <ReportHeaderAndProvenance
        envelope={envelope}
        pageNumber={pageNumber}
        totalPages={totalPages}
        subtitle="Stage 33 Research Diagnostics Annex — Combinatorially Symmetric Cross-Validation (CSCV)"
      />

      <ReportWarningsBanner warnings={envelope.warnings} />

      {/* Multiple-Testing & Overfitting KPI Cards */}
      <div className="report-section-heading">Multiple-Testing Correction &amp; Overfitting Indicators</div>
      <div className="report-kpi-grid">
        {/* PBO */}
        <div className="report-kpi-card highlight-border">
          <div className="kpi-label">Prob. of Backtest Overfitting (PBO)</div>
          <div className={`kpi-value font-mono ${pbo > 0.5 ? 'negative' : 'positive'}`}>
            {formatPercent(pbo, 1)}
          </div>
          <div className={`kpi-sub uppercase font-bold pbo-risk-text ${pbo_risk_level}`}>
            {pbo_risk_level} Risk Level
          </div>
        </div>

        {/* Deflated Sharpe Ratio */}
        <div className="report-kpi-card">
          <div className="kpi-label">Deflated Sharpe Ratio (DSR)</div>
          <div className={`kpi-value font-mono ${is_statistically_significant ? 'positive' : 'negative'}`}>
            {formatPercent(deflated_sharpe_ratio, 1)}
          </div>
          <div className="kpi-sub font-mono">
            {is_statistically_significant ? '✓ Statistically Significant' : '✗ Insufficient Track Record'}
          </div>
        </div>

        {/* Minimum Backtest Length (MinBTL) */}
        <div className="report-kpi-card">
          <div className="kpi-label">Min. Backtest Length (MinBTL)</div>
          <div className="kpi-value font-mono">
            {min_backtest_length_years != null ? `${formatRatio(min_backtest_length_years, 2)} yrs` : 'Undefined (SR ≤ SR*)'}
          </div>
          <div className="kpi-sub font-mono">
            Actual Track: {formatRatio(actual_backtest_length_years, 2)} yrs
          </div>
        </div>

        {/* Best Nominal vs Expected Max Sharpe */}
        <div className="report-kpi-card">
          <div className="kpi-label">Best Nominal vs Expected Max SR</div>
          <div className="kpi-value font-mono">
            {formatRatio(best_nominal_sharpe, 2)} / {formatRatio(expected_max_sharpe, 2)}
          </div>
          <div className="kpi-sub font-mono">
            Best Run #{best_run_number} ({best_run_id})
          </div>
        </div>
      </div>

      {/* CSCV Combinatorial Setup Strip */}
      <div className="annex-setup-strip">
        <span className="setup-item">
          <strong>Evaluated Trials (N):</strong> <span className="font-mono">{evaluated_runs_count}</span>
        </span>
        <span className="setup-item">
          <strong>Synchronized Days (T):</strong> <span className="font-mono">{aligned_observations_count}</span>
        </span>
        <span className="setup-item">
          <strong>CSCV Slices (S):</strong> <span className="font-mono">{n_slices}</span>
        </span>
        <span className="setup-item">
          <strong>Sub-Matrices C(S, S/2):</strong> <span className="font-mono">{total_combinations_count.toLocaleString()}</span>
        </span>
        <span className="setup-item">
          <strong>Higher Moments:</strong> Skew: <span className="font-mono">{formatRatio(skewness, 2)}</span> | Kurt:{' '}
          <span className="font-mono">{formatRatio(kurtosis, 2)}</span>
        </span>
      </div>

      {/* Visual Analytics: Scatter Plot & Rank Histogram */}
      <ResearchDiagnosticsVisuals
        combinationsSample={combinations_sample}
        rankDistribution={rank_distribution}
        degradationRegression={degradation_regression}
        pbo={pbo}
        pboRiskLevel={pbo_risk_level}
      />

      {/* Academic Methodology Qualification Notice */}
      <div className="annex-methodology-notice" role="note">
        <strong>METHODOLOGY DISCLOSURE (Bailey, Borwein, López de Prado, Zhu):</strong> Combinatorially Symmetric
        Cross-Validation (CSCV) evaluates the distribution of relative rank degradation across combinatorial partitions
        of backtest history. A low PBO or high DSR does not constitute a guarantee of future real-world profitability,
        nor does it eliminate regime shift, liquidity friction, or model specification risks.
      </div>

      <ReportProvenanceFooter envelope={envelope} />
    </article>
  );
};
