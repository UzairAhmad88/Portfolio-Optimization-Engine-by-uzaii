/**
 * Institutional Executive Performance & Risk KPI Summary Grid
 * Rigorously segregates Standalone Net vs Gross Performance.
 * Preserves null/undefined values without zero coercion.
 * Displays Benchmark Relative Alpha, Beta, Tracking Error, and Information Ratio.
 */

import React from 'react';
import type { ExecutiveKPIs, BenchmarkRelativeMetrics } from '../../types/reporting';
import { formatPercent, formatRatio } from './formatters';

interface ExecutiveKPISummaryProps {
  kpis: ExecutiveKPIs;
  benchmarkMetrics?: BenchmarkRelativeMetrics | null;
  compact?: boolean;
}

export const ExecutiveKPISummary: React.FC<ExecutiveKPISummaryProps> = ({
  kpis,
  benchmarkMetrics,
  compact = false,
}) => {
  const hasGross = kpis.cumulative_return_gross != null;
  const hasBenchmark = benchmarkMetrics != null;

  return (
    <div className="report-kpi-section" role="region" aria-label="Executive Performance Summary">
      <div className="report-section-heading">Executive Return &amp; Risk Metrics</div>

      <div className={`report-kpi-grid ${compact ? 'compact' : ''}`}>
        {/* Cumulative Return */}
        <div className="report-kpi-card">
          <div className="kpi-label">Cumulative Return (Net)</div>
          <div className="kpi-value primary font-mono">
            {formatPercent(kpis.cumulative_return_net, 2, true)}
          </div>
          {hasGross && (
            <div className="kpi-sub font-mono">
              Gross: {formatPercent(kpis.cumulative_return_gross, 2, true)}
            </div>
          )}
        </div>

        {/* CAGR / Annualized Return */}
        <div className="report-kpi-card">
          <div className="kpi-label">Compound Annual Growth (CAGR)</div>
          <div className="kpi-value font-mono">
            {formatPercent(kpis.cagr_net, 2, true)}
          </div>
          <div className="kpi-sub font-mono">
            Ann. Ret: {formatPercent(kpis.annualized_return_net, 2, true)}
          </div>
        </div>

        {/* Annualized Volatility */}
        <div className="report-kpi-card">
          <div className="kpi-label">Annualized Volatility (Net)</div>
          <div className="kpi-value font-mono">
            {formatPercent(kpis.annualized_volatility_net, 2)}
          </div>
          {hasGross && (
            <div className="kpi-sub font-mono">
              Gross: {formatPercent(kpis.annualized_volatility_gross, 2)}
            </div>
          )}
        </div>

        {/* Sharpe Ratio */}
        <div className="report-kpi-card">
          <div className="kpi-label">Sharpe Ratio (Net)</div>
          <div className="kpi-value font-mono highlight">
            {formatRatio(kpis.sharpe_ratio_net, 2)}
          </div>
          {hasGross && (
            <div className="kpi-sub font-mono">
              Gross: {formatRatio(kpis.sharpe_ratio_gross, 2)}
            </div>
          )}
        </div>

        {/* Sortino Ratio */}
        <div className="report-kpi-card">
          <div className="kpi-label">Sortino Ratio (Net)</div>
          <div className="kpi-value font-mono">
            {formatRatio(kpis.sortino_ratio_net, 2)}
          </div>
          {hasGross && (
            <div className="kpi-sub font-mono">
              Gross: {formatRatio(kpis.sortino_ratio_gross, 2)}
            </div>
          )}
        </div>

        {/* Maximum Drawdown */}
        <div className="report-kpi-card">
          <div className="kpi-label">Maximum Drawdown (Net)</div>
          <div className="kpi-value font-mono negative">
            {formatPercent(kpis.max_drawdown_net, 2)}
          </div>
          {kpis.drawdown_duration_days != null && (
            <div className="kpi-sub font-mono">
              Duration: {kpis.drawdown_duration_days} days
            </div>
          )}
        </div>

        {/* Calmar Ratio */}
        <div className="report-kpi-card">
          <div className="kpi-label">Calmar Ratio (Net)</div>
          <div className="kpi-value font-mono">
            {formatRatio(kpis.calmar_ratio_net, 2)}
          </div>
          {hasGross && (
            <div className="kpi-sub font-mono">
              Gross: {formatRatio(kpis.calmar_ratio_gross, 2)}
            </div>
          )}
        </div>

        {/* Win Rate / Observations */}
        <div className="report-kpi-card">
          <div className="kpi-label">Daily Win Rate</div>
          <div className="kpi-value font-mono">
            {formatPercent(kpis.win_rate, 1)}
          </div>
          <div className="kpi-sub font-mono">
            {kpis.observation_count} obs ({kpis.positive_periods_count || 0}W / {kpis.negative_periods_count || 0}L)
          </div>
        </div>
      </div>

      {/* Benchmark-Relative Performance Strip */}
      <div className="report-benchmark-strip">
        <div className="bm-strip-header">
          <span className="bm-strip-title">Benchmark Attribution</span>
          {hasBenchmark ? (
            <span className="bm-strip-name font-mono">
              {benchmarkMetrics.benchmark_name} ({benchmarkMetrics.benchmark_id})
            </span>
          ) : (
            <span className="bm-strip-unavailable font-mono">No benchmark active comparison</span>
          )}
        </div>

        {hasBenchmark ? (
          <div className="bm-metrics-grid">
            <div className="bm-metric-item">
              <span className="bm-label">Benchmark Return:</span>
              <span className="bm-val font-mono">{formatPercent(benchmarkMetrics.benchmark_cumulative_return, 2, true)}</span>
            </div>
            <div className="bm-metric-item">
              <span className="bm-label">Active Return:</span>
              <span className="bm-val font-mono font-bold">{formatPercent(benchmarkMetrics.arithmetic_active_return, 2, true)}</span>
            </div>
            <div className="bm-metric-item">
              <span className="bm-label">Beta:</span>
              <span className="bm-val font-mono">{formatRatio(benchmarkMetrics.beta, 2)}</span>
            </div>
            <div className="bm-metric-item">
              <span className="bm-label">Jensen's Alpha:</span>
              <span className="bm-val font-mono">{formatPercent(benchmarkMetrics.alpha_annualized, 2, true)}</span>
            </div>
            <div className="bm-metric-item">
              <span className="bm-label">Tracking Error:</span>
              <span className="bm-val font-mono">{formatPercent(benchmarkMetrics.tracking_error, 2)}</span>
            </div>
            <div className="bm-metric-item">
              <span className="bm-label">Information Ratio:</span>
              <span className="bm-val font-mono highlight">{formatRatio(benchmarkMetrics.information_ratio, 2)}</span>
            </div>
          </div>
        ) : (
          <div className="bm-empty-notice">
            Comparative benchmark metrics are not configured or data bars were empty. Relative metrics remain omitted.
          </div>
        )}
      </div>
    </div>
  );
};
