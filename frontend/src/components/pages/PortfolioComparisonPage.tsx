import React, { useState, useEffect } from 'react';
import {
  GitCompare,
  RefreshCw,
  Plus,
  Trash2,
  XCircle,
  Info,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { useDataset } from '../../context/DatasetContext';
import type {
  PortfolioComparisonRequest,
  PortfolioComparisonResponse,
  PortfolioDefinition,
} from '../../types/api';

interface PortfolioComparisonPageProps {
  initialPortfolio?: PortfolioDefinition | null;
}

export const PortfolioComparisonPage: React.FC<PortfolioComparisonPageProps> = ({ initialPortfolio }) => {
  const { currentDataset, availableAssets } = useDataset();

  const [includeGmv, setIncludeGmv] = useState<boolean>(true);
  const [includeMaxSharpe, setIncludeMaxSharpe] = useState<boolean>(true);
  const [includeEqualWeight, setIncludeEqualWeight] = useState<boolean>(true);

  // Custom portfolio inputs
  const [customName, setCustomName] = useState<string>('Aggressive Tilt');
  const [customWeights, setCustomWeights] = useState<Record<string, number>>({});
  const [customPortfoliosList, setCustomPortfoliosList] = useState<Record<string, Record<string, number>>>({});

  const [isComparing, setIsComparing] = useState<boolean>(false);
  const [comparisonResponse, setComparisonResponse] = useState<PortfolioComparisonResponse | null>(null);
  const [comparisonError, setComparisonError] = useState<string | null>(null);

  // Initialize custom weights when assets load
  useEffect(() => {
    if (availableAssets.length > 0) {
      const initial: Record<string, number> = {};
      const equalShare = Number((1 / availableAssets.length).toFixed(4));
      availableAssets.forEach((a) => {
        initial[a.ticker] = equalShare;
      });
      setCustomWeights(initial);
    }
  }, [availableAssets]);

  const handleWeightChange = (ticker: string, val: number) => {
    setCustomWeights((prev) => ({
      ...prev,
      [ticker]: val,
    }));
  };

  const handleAddCustomPortfolio = () => {
    if (!customName.trim()) return;
    setCustomPortfoliosList((prev) => ({
      ...prev,
      [customName.trim()]: { ...customWeights },
    }));
    setCustomName('Defensive Allocation');
  };

  const handleRemoveCustomPortfolio = (name: string) => {
    setCustomPortfoliosList((prev) => {
      const next = { ...prev };
      delete next[name];
      return next;
    });
  };

  const handleExecuteComparison = async () => {
    if (!currentDataset) return;
    const assetsToUse =
      initialPortfolio?.assets && initialPortfolio.assets.length > 0
        ? initialPortfolio.assets
        : availableAssets.map((a) => a.ticker);

    if (assetsToUse.length === 0) return;

    setIsComparing(true);
    setComparisonError(null);

    const portfolioDef: PortfolioDefinition = initialPortfolio || {
      name: 'Strategy Comparison Base',
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
      include_gmv: includeGmv,
      include_max_sharpe: includeMaxSharpe,
      include_equal_weight: includeEqualWeight,
      custom_portfolios: Object.keys(customPortfoliosList).length > 0 ? customPortfoliosList : undefined,
      annualized: true,
      periods_per_year: 252,
      risk_free_rate: 0.02,
    };

    try {
      const res = await apiClient.comparePortfolios(request);
      setComparisonResponse(res);
    } catch (err: any) {
      setComparisonError(err.message || 'Comparison calculation failed.');
      setComparisonResponse(null);
    } finally {
      setIsComparing(false);
    }
  };

  useEffect(() => {
    if (currentDataset && availableAssets.length > 0) {
      handleExecuteComparison();
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
              Upload and register market data in <strong>Market Data</strong> to run multi-strategy portfolio comparisons.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const customSum = Object.values(customWeights).reduce((a, b) => a + (Number(b) || 0), 0);

  return (
    <div className="workspace-container">
      {/* Configuration & Controls */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <div className="card-header">
          <div className="card-title">
            <GitCompare size={18} style={{ color: 'var(--accent)' }} />
            <span>Multi-Strategy Allocation & Risk Comparison</span>
          </div>
          <button
            onClick={handleExecuteComparison}
            disabled={isComparing}
            className="btn btn-primary"
            style={{ fontSize: '12px' }}
          >
            {isComparing ? <RefreshCw size={14} className="spin" /> : <RefreshCw size={14} />}
            <span>{isComparing ? 'Running Comparison...' : 'Run Comparative Matrix'}</span>
          </button>
        </div>

        {comparisonError && (
          <div className="alert alert-danger">
            <XCircle size={18} />
            <span>{comparisonError}</span>
          </div>
        )}

        <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap', marginBottom: '20px' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={includeGmv}
              onChange={(e) => setIncludeGmv(e.target.checked)}
            />
            <span>Global Minimum-Variance (GMV)</span>
          </label>

          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={includeMaxSharpe}
              onChange={(e) => setIncludeMaxSharpe(e.target.checked)}
            />
            <span>Maximum Sharpe Ratio (Tangent)</span>
          </label>

          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={includeEqualWeight}
              onChange={(e) => setIncludeEqualWeight(e.target.checked)}
            />
            <span>Equal-Weight (1/N Benchmark)</span>
          </label>
        </div>

        {/* Custom Portfolios Creator */}
        <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '16px' }}>
          <h4 style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '12px' }}>
            Add Custom Portfolio Allocation (Optional)
          </h4>

          <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-end', flexWrap: 'wrap', marginBottom: '12px' }}>
            <div className="form-group" style={{ marginBottom: 0, minWidth: '200px' }}>
              <label className="form-label">Strategy Name</label>
              <input
                type="text"
                className="input"
                value={customName}
                onChange={(e) => setCustomName(e.target.value)}
              />
            </div>

            <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
              {availableAssets.slice(0, 6).map((asset) => (
                <div key={asset.ticker} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <span className="font-mono" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{asset.ticker}</span>
                  <input
                    type="number"
                    step="0.05"
                    className="input font-mono"
                    style={{ width: '80px', padding: '6px' }}
                    value={customWeights[asset.ticker] ?? 0}
                    onChange={(e) => handleWeightChange(asset.ticker, parseFloat(e.target.value) || 0)}
                  />
                </div>
              ))}
            </div>

            <button
              type="button"
              onClick={handleAddCustomPortfolio}
              disabled={Math.abs(customSum - 1.0) > 0.05}
              className="btn btn-secondary"
              style={{ height: '36px' }}
              title={Math.abs(customSum - 1.0) > 0.05 ? 'Weights must sum to approx 1.0 (100%)' : ''}
            >
              <Plus size={14} />
              <span>Add Custom Portfolio (Sum: {(customSum * 100).toFixed(1)}%)</span>
            </button>
          </div>

          {/* List of custom portfolios added */}
          {Object.keys(customPortfoliosList).length > 0 && (
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '10px' }}>
              {Object.keys(customPortfoliosList).map((name) => (
                <div
                  key={name}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '4px 10px',
                    borderRadius: 'var(--radius-sm)',
                    backgroundColor: 'var(--bg-elevated)',
                    border: '1px solid var(--border-medium)',
                    fontSize: '12px',
                  }}
                >
                  <span style={{ fontWeight: 600 }}>{name}</span>
                  <Trash2
                    size={13}
                    style={{ color: 'var(--danger)', cursor: 'pointer' }}
                    onClick={() => handleRemoveCustomPortfolio(name)}
                  />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Comparison Results Table */}
      {comparisonResponse && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <span>Strategy Comparison Matrix</span>
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              Window: <span className="font-mono">{comparisonResponse.date_coverage?.start_date} to {comparisonResponse.date_coverage?.end_date}</span> ({comparisonResponse.date_coverage?.common_bar_count} bars)
            </div>
          </div>

          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th>Strategy Name</th>
                  <th className="num-cell">Expected Return</th>
                  <th className="num-cell">Volatility (σ)</th>
                  <th className="num-cell">Sharpe Ratio</th>
                  <th className="num-cell">Sortino Ratio</th>
                  <th className="num-cell">Max Drawdown</th>
                  <th className="num-cell">Gross Exposure</th>
                  <th>Feasible</th>
                </tr>
              </thead>
              <tbody>
                {comparisonResponse.portfolios.map((item) => {
                  const ret = item.metrics.expected_return;
                  const vol = item.metrics.volatility;
                  const sharpe = item.metrics.sharpe_ratio;
                  const sortino = item.risk_summary?.sortino_ratio;
                  const mdd = item.risk_summary?.maximum_drawdown;

                  return (
                    <tr key={item.name}>
                      <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{item.name}</td>
                      <td className="num-cell font-mono" style={{ color: ret >= 0 ? 'var(--success)' : 'var(--danger)', fontWeight: 600 }}>
                        {(ret * 100).toFixed(2)}%
                      </td>
                      <td className="num-cell font-mono">{(vol * 100).toFixed(2)}%</td>
                      <td className="num-cell font-mono" style={{ color: 'var(--accent)' }}>
                        {sharpe != null ? sharpe.toFixed(3) : 'N/A'}
                      </td>
                      <td className="num-cell font-mono">
                        {sortino != null ? sortino.toFixed(3) : 'N/A'}
                      </td>
                      <td className="num-cell font-mono" style={{ color: mdd != null ? 'var(--danger)' : 'inherit' }}>
                        {mdd != null ? `-${(mdd * 100).toFixed(2)}%` : '—'}
                      </td>
                      <td className="num-cell font-mono">{(item.metrics.gross_exposure * 100).toFixed(1)}%</td>
                      <td>
                        <span className={`badge ${item.is_feasible ? 'badge-success' : 'badge-danger'}`}>
                          {item.is_feasible ? 'FEASIBLE' : 'INFEASIBLE'}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
