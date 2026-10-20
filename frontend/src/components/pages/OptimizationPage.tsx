import React, { useState } from 'react';
import {
  Target,
  XCircle,
  RefreshCw,
  Info,
  Cpu,
  BarChart2,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { useDataset } from '../../context/DatasetContext';
import type {
  OptimizationObjective,
  OptimizationRequest,
  OptimizationResponse,
  PortfolioDefinition,
} from '../../types/api';

interface OptimizationPageProps {
  initialPortfolio?: PortfolioDefinition | null;
  onAnalysisComplete?: (response: OptimizationResponse) => void;
}

export const OptimizationPage: React.FC<OptimizationPageProps> = ({
  initialPortfolio,
  onAnalysisComplete,
}) => {
  const { currentDataset, availableAssets } = useDataset();

  const [objective, setObjective] = useState<OptimizationObjective>('min_variance');
  const [targetReturn, setTargetReturn] = useState<string>('0.15');
  const [riskFreeRate, setRiskFreeRate] = useState<number>(0.02);
  const [annualized, setAnnualized] = useState<boolean>(true);
  const [periodsPerYear, setPeriodsPerYear] = useState<number>(252);

  const [isSolving, setIsSolving] = useState<boolean>(false);
  const [optimizationResult, setOptimizationResult] = useState<OptimizationResponse | null>(null);
  const [solverError, setSolverError] = useState<string | null>(null);

  const handleRunOptimization = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentDataset) {
      setSolverError('No active dataset found. Please upload or register a dataset first.');
      return;
    }

    const assetsToOptimize =
      initialPortfolio?.assets && initialPortfolio.assets.length > 0
        ? initialPortfolio.assets
        : availableAssets.map((a) => a.ticker);

    if (assetsToOptimize.length === 0) {
      setSolverError('No assets available to optimize. Please register market data or configure a portfolio.');
      return;
    }

    setIsSolving(true);
    setSolverError(null);

    const portfolioDef: PortfolioDefinition = initialPortfolio || {
      name: 'Standard Mean-Variance Universe',
      dataset_id: currentDataset.dataset_id,
      assets: assetsToOptimize,
      constraints: {
        default_min_weight: 0.0,
        default_max_weight: 1.0,
        target_total_weight: 1.0,
        allow_short: false,
      },
    };

    const request: OptimizationRequest = {
      portfolio: portfolioDef,
      objective,
      target_return: objective === 'target_return' ? parseFloat(targetReturn) || null : null,
      risk_free_rate: Number(riskFreeRate),
      annualized,
      periods_per_year: Number(periodsPerYear),
    };

    try {
      const result = await apiClient.optimizePortfolio(request);
      setOptimizationResult(result);
      if (onAnalysisComplete) {
        onAnalysisComplete(result);
      }
    } catch (err: any) {
      setSolverError(err.message || 'Numerical solver failed to find feasible allocation.');
      setOptimizationResult(null);
    } finally {
      setIsSolving(false);
    }
  };

  if (!currentDataset) {
    return (
      <div className="workspace-container">
        <div className="alert alert-info">
          <Info size={18} style={{ flexShrink: 0 }} />
          <div>
            <strong>No Dataset Registered</strong>
            <p style={{ marginTop: '4px', fontSize: '13px' }}>
              Upload and register a dataset in the <strong>Market Data</strong> workspace before executing portfolio optimization.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="workspace-container">
      {/* Solver Configuration Form */}
      <form onSubmit={handleRunOptimization}>
        <div className="card" style={{ marginBottom: '24px' }}>
          <div className="card-header">
            <div className="card-title">
              <Target size={18} style={{ color: 'var(--accent)' }} />
              <span>SciPy SLSQP Numerical Optimizer</span>
            </div>
            <span className="badge badge-neutral font-mono">
              Assets: {initialPortfolio?.assets?.length || availableAssets.length} | {availableAssets[0]?.currency || 'USD'}
            </span>
          </div>

          {solverError && (
            <div className="alert alert-danger">
              <XCircle size={18} style={{ flexShrink: 0 }} />
              <div>
                <strong>Optimization Failed:</strong> {solverError}
              </div>
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '20px' }}>
            <div className="form-group">
              <label className="form-label">Optimization Objective</label>
              <select
                className="input"
                value={objective}
                onChange={(e) => setObjective(e.target.value as OptimizationObjective)}
              >
                <option value="min_variance">Global Minimum Variance (Min Risk)</option>
                <option value="max_sharpe">Maximum Sharpe Ratio (Tangent)</option>
                <option value="equal_weight">Equal-Weight (1/N Benchmark)</option>
                <option value="target_return">Target Expected Return</option>
              </select>
            </div>

            {objective === 'target_return' && (
              <div className="form-group">
                <label className="form-label">Target Return (e.g. 0.15 for 15%)</label>
                <input
                  type="number"
                  step="0.005"
                  className="input font-mono"
                  value={targetReturn}
                  onChange={(e) => setTargetReturn(e.target.value)}
                  required
                />
              </div>
            )}

            <div className="form-group">
              <label className="form-label">
                <span>Annual Risk-Free Rate (r_f)</span>
                <span className="font-mono">{(riskFreeRate * 100).toFixed(1)}%</span>
              </label>
              <input
                type="number"
                step="0.005"
                className="input font-mono"
                value={riskFreeRate}
                onChange={(e) => setRiskFreeRate(parseFloat(e.target.value) || 0)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Periods Per Year</label>
              <input
                type="number"
                className="input font-mono"
                value={periodsPerYear}
                onChange={(e) => setPeriodsPerYear(parseInt(e.target.value, 10) || 252)}
              />
            </div>

            <div className="form-group" style={{ justifyContent: 'center' }}>
              <label className="form-label">Annualization Mode</label>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', height: '36px' }}>
                <input
                  type="checkbox"
                  id="annualized-checkbox"
                  checked={annualized}
                  onChange={(e) => setAnnualized(e.target.checked)}
                  style={{ cursor: 'pointer' }}
                />
                <label htmlFor="annualized-checkbox" style={{ fontSize: '13px', cursor: 'pointer', color: 'var(--text-secondary)' }}>
                  Annualize Returns & Volatility
                </label>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button
              type="submit"
              disabled={isSolving}
              className="btn btn-primary"
            >
              {isSolving ? <RefreshCw size={15} className="spin" /> : <Target size={15} />}
              <span>{isSolving ? 'Solving Quadratic Program...' : 'Solve Optimal Allocation'}</span>
            </button>
          </div>
        </div>
      </form>

      {/* Optimization Results */}
      {optimizationResult && (
        <div>
          {/* Performance & Risk Metric Cards */}
          <div className="metric-grid">
            <div className="metric-card">
              <div className="metric-label">Expected Return E[R_p]</div>
              <div className="metric-value font-mono" style={{ color: (optimizationResult.metrics?.expected_return || 0) >= 0 ? 'var(--success)' : 'var(--danger)' }}>
                {optimizationResult.metrics ? `${(optimizationResult.metrics.expected_return * 100).toFixed(2)}%` : '—'}
              </div>
              <div className="metric-sub">
                <span>{annualized ? 'Annualized expected return' : 'Periodic mean return'}</span>
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-label">Volatility σ_p</div>
              <div className="metric-value font-mono">
                {optimizationResult.metrics ? `${(optimizationResult.metrics.volatility * 100).toFixed(2)}%` : '—'}
              </div>
              <div className="metric-sub">
                <span>{annualized ? 'Annualized standard dev' : 'Periodic standard dev'}</span>
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-label">Sharpe Ratio</div>
              <div className="metric-value font-mono" style={{ color: 'var(--accent)' }}>
                {optimizationResult.metrics?.sharpe_ratio != null
                  ? optimizationResult.metrics.sharpe_ratio.toFixed(3)
                  : 'N/A'}
              </div>
              <div className="metric-sub">
                <span>r_f = {(riskFreeRate * 100).toFixed(1)}%</span>
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-label">Total / Gross Weight</div>
              <div className="metric-value font-mono">
                {optimizationResult.metrics ? `${(optimizationResult.metrics.total_weight * 100).toFixed(1)}%` : '—'}
              </div>
              <div className="metric-sub">
                <span>Gross: {((optimizationResult.metrics?.gross_exposure ?? 0) * 100).toFixed(1)}%</span>
              </div>
            </div>
          </div>

          {/* Solver Diagnostics Card */}
          <div className="card" style={{ marginBottom: '24px' }}>
            <div className="card-header">
              <div className="card-title">
                <Cpu size={18} style={{ color: 'var(--accent)' }} />
                <span>Solver Diagnostics & Convergence Audit</span>
              </div>
              <span className={`badge ${optimizationResult.solver_diagnostics.converged ? 'badge-success' : 'badge-danger'}`}>
                {optimizationResult.solver_diagnostics.status}
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px', marginBottom: '14px' }}>
              <div style={{ fontSize: '12px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Algorithm:</span>{' '}
                <strong style={{ color: 'var(--text-primary)' }}>{optimizationResult.solver_diagnostics.solver_name}</strong>
              </div>
              <div style={{ fontSize: '12px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Iterations:</span>{' '}
                <span className="font-mono">{optimizationResult.solver_diagnostics.iterations ?? '—'}</span>
              </div>
              <div style={{ fontSize: '12px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Objective Value:</span>{' '}
                <span className="font-mono">{optimizationResult.solver_diagnostics.objective_value?.toFixed(6) ?? '—'}</span>
              </div>
              <div style={{ fontSize: '12px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Feasible:</span>{' '}
                <span style={{ color: optimizationResult.is_feasible ? 'var(--success)' : 'var(--danger)', fontWeight: 600 }}>
                  {optimizationResult.is_feasible ? 'Strictly Satisfied' : 'Violations Detected'}
                </span>
              </div>
            </div>

            <div style={{ fontSize: '12px', color: 'var(--text-secondary)', padding: '8px 12px', backgroundColor: 'var(--bg-input)', borderRadius: 'var(--radius-sm)' }}>
              <strong>Solver Message:</strong> {optimizationResult.solver_diagnostics.message}
            </div>
          </div>

          {/* Asset Allocation Weights Table */}
          <div className="card" style={{ marginBottom: '24px' }}>
            <div className="card-header">
              <div className="card-title">
                <BarChart2 size={18} style={{ color: 'var(--accent)' }} />
                <span>Optimal Asset Allocation Weights</span>
              </div>
              <span className="badge badge-info">
                Currency: {optimizationResult.currency}
              </span>
            </div>

            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th>Asset Ticker</th>
                    <th className="num-cell">Optimal Weight (%)</th>
                    <th>Allocation Bar</th>
                    <th className="num-cell">Decimal Weight</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(optimizationResult.weights).map(([ticker, weight]) => {
                    const pct = weight * 100;
                    return (
                      <tr key={ticker}>
                        <td className="font-mono" style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                          {ticker}
                        </td>
                        <td className="num-cell" style={{ fontWeight: 600, color: pct > 0 ? 'var(--accent)' : 'var(--text-dim)' }}>
                          {pct.toFixed(2)}%
                        </td>
                        <td style={{ minWidth: '180px' }}>
                          <div
                            style={{
                              width: '100%',
                              height: '8px',
                              borderRadius: '4px',
                              backgroundColor: 'var(--bg-elevated)',
                              overflow: 'hidden',
                            }}
                          >
                            <div
                              style={{
                                width: `${Math.min(100, Math.max(0, pct))}%`,
                                height: '100%',
                                backgroundColor: pct > 0 ? 'var(--accent)' : 'transparent',
                                transition: 'width 0.3s ease',
                              }}
                            />
                          </div>
                        </td>
                        <td className="num-cell font-mono">{weight.toFixed(5)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Academic & Regulatory Notice */}
          <div className="alert alert-info" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            <Info size={14} style={{ flexShrink: 0 }} />
            <div>
              Portfolio optimization results reflect historical statistical estimates (Bessel-corrected sample covariance and sample mean return).
              Historical performance does not guarantee future returns. This research output is for quantitative evaluation purposes only and does not constitute financial advice.
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
