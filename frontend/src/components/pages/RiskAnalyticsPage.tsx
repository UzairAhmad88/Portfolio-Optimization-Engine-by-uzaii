import React, { useState, useEffect } from 'react';
import {
  ShieldAlert,
  TrendingDown,
  RefreshCw,
  Info,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { useDataset } from '../../context/DatasetContext';
import type {
  PortfolioComparisonRequest,
  PortfolioComparisonResponse,
  PortfolioDefinition,
  PortfolioRiskSummaryModel,
} from '../../types/api';

interface RiskAnalyticsPageProps {
  initialPortfolio?: PortfolioDefinition | null;
}

export const RiskAnalyticsPage: React.FC<RiskAnalyticsPageProps> = ({ initialPortfolio }) => {
  const { currentDataset, availableAssets } = useDataset();

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [comparisonData, setComparisonData] = useState<PortfolioComparisonResponse | null>(null);
  const [selectedStrategyIndex, setSelectedStrategyIndex] = useState<number>(0);
  const [riskError, setRiskError] = useState<string | null>(null);

  const fetchRiskProfile = async () => {
    if (!currentDataset) return;
    const assetsToUse =
      initialPortfolio?.assets && initialPortfolio.assets.length > 0
        ? initialPortfolio.assets
        : availableAssets.map((a) => a.ticker);

    if (assetsToUse.length === 0) return;

    setIsLoading(true);
    setRiskError(null);

    const portfolioDef: PortfolioDefinition = initialPortfolio || {
      name: 'Risk Evaluation Portfolio',
      dataset_id: currentDataset.dataset_id,
      assets: assetsToUse,
      constraints: {
        default_min_weight: 0.0,
        default_max_weight: 1.0,
        target_total_weight: 1.0,
        allow_short: false,
      },
    };

    const request: PortfolioComparisonRequest = {
      portfolio: portfolioDef,
      include_gmv: true,
      include_max_sharpe: true,
      include_equal_weight: true,
      annualized: true,
      periods_per_year: 252,
      risk_free_rate: 0.02,
    };

    try {
      const res = await apiClient.comparePortfolios(request);
      setComparisonData(res);
    } catch (err: any) {
      setRiskError(err.message || 'Failed to compute risk analytics tear-sheet.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (currentDataset && availableAssets.length > 0) {
      fetchRiskProfile();
    }
  }, [currentDataset?.dataset_id, availableAssets.length]);

  if (!currentDataset) {
    return (
      <div className="workspace-container">
        <div className="alert alert-info">
          <Info size={18} style={{ flexShrink: 0 }} />
          <div>
            <strong>No Dataset Selected</strong>
            <p style={{ marginTop: '4px', fontSize: '13px' }}>
              Upload and register market data in <strong>Market Data</strong> to evaluate portfolio risk tear-sheets.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const selectedPortfolio = comparisonData?.portfolios[selectedStrategyIndex];
  const riskSummary: PortfolioRiskSummaryModel | undefined | null = selectedPortfolio?.risk_summary;

  return (
    <div className="workspace-container">
      <div className="card" style={{ marginBottom: '24px' }}>
        <div className="card-header">
          <div className="card-title">
            <ShieldAlert size={18} style={{ color: 'var(--accent)' }} />
            <span>Institutional Portfolio Risk Tear-Sheet</span>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            {comparisonData?.portfolios.map((p, idx) => (
              <button
                key={p.name}
                onClick={() => setSelectedStrategyIndex(idx)}
                className={`btn ${selectedStrategyIndex === idx ? 'btn-primary' : 'btn-outline'}`}
                style={{ fontSize: '12px', padding: '4px 10px' }}
              >
                {p.name}
              </button>
            ))}
            <button
              onClick={fetchRiskProfile}
              disabled={isLoading}
              className="btn btn-outline"
              style={{ padding: '4px 8px' }}
              title="Recalculate risk profile"
            >
              <RefreshCw size={14} className={isLoading ? 'spin' : ''} />
            </button>
          </div>
        </div>

        {riskError && (
          <div className="alert alert-danger">
            <TrendingDown size={18} />
            <span>{riskError}</span>
          </div>
        )}

        {isLoading ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
            Calculating downside deviations, drawdowns, and Sharpe/Sortino ratios...
          </div>
        ) : riskSummary ? (
          <div>
            {/* Headline Metrics Grid */}
            <div className="metric-grid">
              <div className="metric-card">
                <div className="metric-label">Annualized Return</div>
                <div className="metric-value font-mono" style={{ color: riskSummary.annualized_return >= 0 ? 'var(--success)' : 'var(--danger)' }}>
                  {(riskSummary.annualized_return * 100).toFixed(2)}%
                </div>
                <div className="metric-sub">
                  <span>Periodic: {(riskSummary.arithmetic_mean_return * 100).toFixed(4)}%</span>
                </div>
              </div>

              <div className="metric-card">
                <div className="metric-label">Annualized Volatility (σ)</div>
                <div className="metric-value font-mono">
                  {(riskSummary.annualized_volatility * 100).toFixed(2)}%
                </div>
                <div className="metric-sub">
                  <span>Periodic σ: {(riskSummary.periodic_volatility * 100).toFixed(3)}%</span>
                </div>
              </div>

              <div className="metric-card">
                <div className="metric-label">Maximum Drawdown</div>
                <div className="metric-value font-mono" style={{ color: 'var(--danger)' }}>
                  -{(riskSummary.maximum_drawdown * 100).toFixed(2)}%
                </div>
                <div className="metric-sub">
                  <span>Peak-to-trough drop</span>
                </div>
              </div>

              <div className="metric-card">
                <div className="metric-label">Sortino Ratio</div>
                <div className="metric-value font-mono" style={{ color: 'var(--accent)' }}>
                  {riskSummary.sortino_ratio != null ? riskSummary.sortino_ratio.toFixed(3) : 'N/A'}
                </div>
                <div className="metric-sub">
                  <span>Sharpe: {riskSummary.sharpe_ratio != null ? riskSummary.sharpe_ratio.toFixed(3) : 'N/A'}</span>
                </div>
              </div>
            </div>

            {/* Detailed Risk Breakdown Table */}
            <div className="table-container" style={{ marginBottom: '24px' }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Risk Metric Name</th>
                    <th>Metric Interpretation</th>
                    <th className="num-cell">Reported Value</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td style={{ fontWeight: 600 }}>Cumulative Compounding Return</td>
                    <td style={{ color: 'var(--text-secondary)' }}>Total geometric compounded wealth growth over observation span</td>
                    <td className="num-cell font-mono" style={{ color: riskSummary.geometric_cumulative_return >= 0 ? 'var(--success)' : 'var(--danger)', fontWeight: 600 }}>
                      {(riskSummary.geometric_cumulative_return * 100).toFixed(2)}%
                    </td>
                  </tr>
                  <tr>
                    <td style={{ fontWeight: 600 }}>Downside Semi-Deviation</td>
                    <td style={{ color: 'var(--text-secondary)' }}>Volatility of returns falling below MAR (Minimum Acceptable Return = {(riskSummary.mar_annualized * 100).toFixed(1)}%)</td>
                    <td className="num-cell font-mono">{(riskSummary.downside_deviation * 100).toFixed(3)}%</td>
                  </tr>
                  <tr>
                    <td style={{ fontWeight: 600 }}>Periodic Return Variance</td>
                    <td style={{ color: 'var(--text-secondary)' }}>Unadjusted periodic return sample variance (s^2)</td>
                    <td className="num-cell font-mono">{riskSummary.variance.toExponential(4)}</td>
                  </tr>
                  <tr>
                    <td style={{ fontWeight: 600 }}>Clean Observation Count</td>
                    <td style={{ color: 'var(--text-secondary)' }}>Synchronized historical daily price bars evaluated</td>
                    <td className="num-cell font-mono">{riskSummary.observation_count.toLocaleString()}</td>
                  </tr>
                  <tr>
                    <td style={{ fontWeight: 600 }}>Historical Window</td>
                    <td style={{ color: 'var(--text-secondary)' }}>Effective synchronous time range</td>
                    <td className="num-cell font-mono">{riskSummary.start_date} to {riskSummary.end_date}</td>
                  </tr>
                  <tr>
                    <td style={{ fontWeight: 600 }}>Annualization Factor (P)</td>
                    <td style={{ color: 'var(--text-secondary)' }}>Compounding periods per year assumed</td>
                    <td className="num-cell font-mono">{riskSummary.periods_per_year}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Strategy Allocation Weights */}
            {selectedPortfolio && (
              <div className="card" style={{ backgroundColor: 'var(--bg-elevated)', marginBottom: '16px' }}>
                <h4 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '10px' }}>
                  Allocations for {selectedPortfolio.name}
                </h4>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                  {Object.entries(selectedPortfolio.weights).map(([ticker, w]) => (
                    <div
                      key={ticker}
                      style={{
                        padding: '6px 10px',
                        borderRadius: 'var(--radius-sm)',
                        backgroundColor: 'var(--bg-card)',
                        border: '1px solid var(--border-medium)',
                        fontSize: '12px',
                      }}
                    >
                      <span className="font-mono" style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{ticker}: </span>
                      <span className="font-mono" style={{ color: w > 0 ? 'var(--accent)' : 'var(--text-dim)' }}>
                        {(w * 100).toFixed(2)}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>
            No risk summary available for this portfolio definition.
          </div>
        )}
      </div>
    </div>
  );
};
