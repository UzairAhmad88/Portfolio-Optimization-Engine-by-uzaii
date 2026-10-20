import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  AlertTriangle,
  Sliders,
  Play,
  RotateCcw,
  GitBranch,
  TrendingUp,
  Activity,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { useDataset } from '../../context/DatasetContext';
import type {
  RiskParityOptimizeRequest,
  RiskParityOptimizeResponse,
  RiskParityBacktestRequest,
  RiskParityBacktestResponse,
} from '../../types/api';

type ActiveTab = 'optimization' | 'backtest';

export const RiskParityPage: React.FC = () => {
  const { currentDataset, availableAssets } = useDataset();

  // Tab State
  const [activeTab, setActiveTab] = useState<ActiveTab>('optimization');

  // Optimization Parameters
  const [method, setMethod] = useState<'erc' | 'hrp' | 'inverse_variance' | 'equal_weight'>('erc');
  const [linkageMethod, setLinkageMethod] = useState<'single' | 'complete' | 'average'>('single');
  const [minWeight, setMinWeight] = useState<number>(0.0);
  const [maxWeight, setMaxWeight] = useState<number>(1.0);
  const [useCustomBudgets, setUseCustomBudgets] = useState<boolean>(false);
  const [riskBudgets, setRiskBudgets] = useState<Record<string, number>>({});

  // Backtest Parameters
  const [splitDate, setSplitDate] = useState<string>('');
  const [rebalanceFrequency, setRebalanceFrequency] = useState<'daily' | 'weekly' | 'monthly' | 'quarterly'>('monthly');
  const [costBps, setCostBps] = useState<number>(10.0);
  const [slippageBps, setSlippageBps] = useState<number>(5.0);
  const [initialCash, setInitialCash] = useState<number>(100000);
  const [backtestChartMode, setBacktestChartMode] = useState<'equity' | 'drawdown'>('equity');

  // Execution States
  const [isOptimizing, setIsOptimizing] = useState<boolean>(false);
  const [optError, setOptError] = useState<string | null>(null);
  const [optResult, setOptResult] = useState<RiskParityOptimizeResponse | null>(null);

  const [isBacktesting, setIsBacktesting] = useState<boolean>(false);
  const [backtestError, setBacktestError] = useState<string | null>(null);
  const [backtestResult, setBacktestResult] = useState<RiskParityBacktestResponse | null>(null);

  // Initialize budgets when assets change
  useEffect(() => {
    if (availableAssets.length > 0) {
      const n = availableAssets.length;
      const initial: Record<string, number> = {};
      availableAssets.forEach((a) => {
        initial[a.asset_id] = Number((1.0 / n).toFixed(4));
      });
      setRiskBudgets(initial);
    }
  }, [availableAssets]);

  // Set default split date from dataset assets if available
  useEffect(() => {
    if (availableAssets.length > 0 && availableAssets[0]?.end_date) {
      // Set split date roughly 6 months before end date or midpoint
      const d = new Date(availableAssets[0].end_date);
      d.setMonth(d.getMonth() - 6);
      setSplitDate(d.toISOString().slice(0, 10));
    }
  }, [availableAssets]);

  const handleBudgetChange = (asset: string, val: number) => {
    setRiskBudgets((prev) => ({
      ...prev,
      [asset]: Math.max(0, val),
    }));
  };

  const normalizeBudgets = () => {
    const sum = Object.values(riskBudgets).reduce((a, b) => a + b, 0);
    if (sum > 0) {
      const normalized: Record<string, number> = {};
      Object.entries(riskBudgets).forEach(([k, v]) => {
        normalized[k] = Number((v / sum).toFixed(4));
      });
      setRiskBudgets(normalized);
    }
  };

  const handleRunOptimization = async () => {
    if (!currentDataset) {
      setOptError('Please select a dataset first.');
      return;
    }

    setIsOptimizing(true);
    setOptError(null);

    try {
      const req: RiskParityOptimizeRequest = {
        dataset_id: currentDataset.dataset_id,
        method,
        linkage_method: method === 'hrp' ? linkageMethod : undefined,
        constraints: {
          default_min_weight: minWeight,
          default_max_weight: maxWeight,
        },
        risk_budgets: useCustomBudgets ? riskBudgets : undefined,
      };

      const res = await apiClient.optimizeRiskParity(req);
      setOptResult(res);
    } catch (err: any) {
      setOptError(err?.message || 'Failed to solve risk parity portfolio.');
    } finally {
      setIsOptimizing(false);
    }
  };

  const handleRunBacktest = async () => {
    if (!currentDataset) {
      setBacktestError('Please select a dataset first.');
      return;
    }
    if (!splitDate) {
      setBacktestError('Please provide an in-sample training split date.');
      return;
    }

    setIsBacktesting(true);
    setBacktestError(null);

    try {
      const req: RiskParityBacktestRequest = {
        dataset_id: currentDataset.dataset_id,
        method,
        linkage_method: method === 'hrp' ? linkageMethod : undefined,
        split_date: splitDate,
        rebalance_frequency: rebalanceFrequency,
        transaction_cost_bps: costBps,
        slippage_bps: slippageBps,
        initial_cash: initialCash,
      };

      const res = await apiClient.backtestRiskParity(req);
      setBacktestResult(res);
    } catch (err: any) {
      setBacktestError(err?.message || 'Failed to execute out-of-sample backtest.');
    } finally {
      setIsBacktesting(false);
    }
  };

  if (!currentDataset) {
    return (
      <div className="workspace-container">
        <div className="card" style={{ textAlign: 'center', padding: '48px 24px' }}>
          <ShieldCheck size={48} style={{ color: 'var(--text-secondary)', marginBottom: '16px' }} />
          <h2 style={{ fontSize: '20px', fontWeight: 600, marginBottom: '8px' }}>
            No Active Dataset Selected
          </h2>
          <p style={{ color: 'var(--text-secondary)', maxWidth: '480px', margin: '0 auto 24px' }}>
            Equal Risk Contribution (ERC) and Hierarchical Risk Parity (HRP) require historical returns to construct covariance and correlation distance matrices.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="workspace-container">
      {/* Tab Navigation Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: '1px solid var(--border-subtle)',
          marginBottom: '24px',
          paddingBottom: '12px',
        }}
      >
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={() => setActiveTab('optimization')}
            className={`btn ${activeTab === 'optimization' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            <ShieldCheck size={16} />
            <span>Risk Parity Optimization</span>
          </button>
          <button
            onClick={() => setActiveTab('backtest')}
            className={`btn ${activeTab === 'backtest' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            <TrendingUp size={16} />
            <span>Out-of-Sample Backtesting</span>
          </button>
        </div>

        <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
          Active Dataset: <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{currentDataset.filename}</span> ({availableAssets.length} assets)
        </div>
      </div>

      {activeTab === 'optimization' ? (
        <div style={{ display: 'grid', gridTemplateColumns: '360px 1fr', gap: '24px' }}>
          {/* Controls Sidebar */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div className="card">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
                <Sliders size={18} style={{ color: 'var(--primary)' }} />
                <h3 style={{ fontSize: '16px', fontWeight: 600 }}>Algorithm Formulation</h3>
              </div>

              {/* Method Selection */}
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, marginBottom: '6px' }}>
                  Allocation Method
                </label>
                <select
                  value={method}
                  onChange={(e) => setMethod(e.target.value as any)}
                  className="input-field"
                  style={{ width: '100%' }}
                >
                  <option value="erc">Equal Risk Contribution (ERC / Spinu)</option>
                  <option value="hrp">Hierarchical Risk Parity (HRP / Lopez de Prado)</option>
                  <option value="inverse_variance">Inverse Volatility / Variance (Analytical)</option>
                  <option value="equal_weight">Equal Weight Benchmark (1/N)</option>
                </select>
                <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  {method === 'erc' && 'Convex log-barrier SLSQP optimization equalizing marginal risk contributions.'}
                  {method === 'hrp' && 'Clustering & recursive bisection on correlation distance; immune to covariance inversion.'}
                  {method === 'inverse_variance' && 'Weights inversely proportional to asset variance w_i ∝ 1/σ_i².'}
                  {method === 'equal_weight' && 'Naive equal capital distribution w_i = 1/N.'}
                </p>
              </div>

              {/* HRP Linkage Method */}
              {method === 'hrp' && (
                <div style={{ marginBottom: '16px', padding: '12px', backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)' }}>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, marginBottom: '6px' }}>
                    Tree Linkage Metric
                  </label>
                  <select
                    value={linkageMethod}
                    onChange={(e) => setLinkageMethod(e.target.value as any)}
                    className="input-field"
                    style={{ width: '100%' }}
                  >
                    <option value="single">Single Linkage (Nearest neighbor d_min)</option>
                    <option value="complete">Complete Linkage (Farthest neighbor d_max)</option>
                    <option value="average">Average Linkage (Mean pairwise distance UPGMA)</option>
                  </select>
                </div>
              )}

              {/* Weights Bounds */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    Min Weight (w_min)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={minWeight}
                    onChange={(e) => setMinWeight(parseFloat(e.target.value) || 0)}
                    className="input-field"
                    style={{ width: '100%' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    Max Weight (w_max)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={maxWeight}
                    onChange={(e) => setMaxWeight(parseFloat(e.target.value) || 1)}
                    className="input-field"
                    style={{ width: '100%' }}
                  />
                </div>
              </div>

              {/* Custom Budgets (ERC Only) */}
              {method === 'erc' && (
                <div style={{ marginBottom: '16px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={useCustomBudgets}
                        onChange={(e) => setUseCustomBudgets(e.target.checked)}
                      />
                      <span>Custom Risk Budgets (b_i)</span>
                    </label>
                    {useCustomBudgets && (
                      <button
                        onClick={normalizeBudgets}
                        className="btn btn-secondary"
                        style={{ fontSize: '11px', padding: '2px 8px' }}
                      >
                        <RotateCcw size={10} style={{ marginRight: '4px' }} />
                        Normalize
                      </button>
                    )}
                  </div>

                  {useCustomBudgets && (
                    <div style={{ maxHeight: '180px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      {availableAssets.map((a) => (
                        <div key={a.asset_id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '12px' }}>
                          <span>{a.asset_id}</span>
                          <input
                            type="number"
                            step="0.01"
                            min="0"
                            max="1"
                            value={riskBudgets[a.asset_id] ?? 0}
                            onChange={(e) => handleBudgetChange(a.asset_id, parseFloat(e.target.value) || 0)}
                            className="input-field"
                            style={{ width: '80px', padding: '2px 6px', textAlign: 'right' }}
                          />
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Execute Button */}
              <button
                onClick={handleRunOptimization}
                disabled={isOptimizing}
                className="btn btn-primary"
                style={{ width: '100%', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px' }}
              >
                <Play size={16} />
                <span>{isOptimizing ? 'Computing Parity Solution...' : 'Optimize Risk Parity'}</span>
              </button>

              {optError && (
                <div className="alert alert-danger" style={{ marginTop: '16px', fontSize: '12px' }}>
                  <AlertTriangle size={14} style={{ flexShrink: 0 }} />
                  <span>{optError}</span>
                </div>
              )}
            </div>
          </div>

          {/* Results Display */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {optResult ? (
              <>
                {/* Diagnostics Header Cards */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
                  <div className="card" style={{ padding: '16px' }}>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                      Annualized Volatility
                    </div>
                    <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)' }}>
                      {(optResult.portfolio_volatility * 100).toFixed(2)}%
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      σ_p = √(wᵀΣw)
                    </div>
                  </div>

                  <div className="card" style={{ padding: '16px' }}>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                      Effective Bets (N_ent)
                    </div>
                    <div style={{ fontSize: '20px', fontWeight: 700, color: '#38BDF8' }}>
                      {optResult.diagnostics.effective_bets.toFixed(2)} / {optResult.assets.length}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      Entropy of Risk (exp(-Σ p ln p))
                    </div>
                  </div>

                  <div className="card" style={{ padding: '16px' }}>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                      Risk Gini Coefficient
                    </div>
                    <div style={{ fontSize: '20px', fontWeight: 700, color: optResult.diagnostics.risk_gini < 0.1 ? '#10B981' : '#F59E0B' }}>
                      {optResult.diagnostics.risk_gini.toFixed(4)}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      0 = Perfect Parity, 1 = Monopolized
                    </div>
                  </div>

                  <div className="card" style={{ padding: '16px' }}>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                      Diversification Ratio
                    </div>
                    <div style={{ fontSize: '20px', fontWeight: 700, color: '#818CF8' }}>
                      {optResult.diagnostics.diversification_ratio.toFixed(2)}x
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      DR = (wᵀσ) / σ_p
                    </div>
                  </div>
                </div>

                {/* Status Badge */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
                  {optResult.is_feasible ? (
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: '#10B981', fontWeight: 600 }}>
                      <CheckCircle2 size={16} /> Feasible ({optResult.solver_status})
                    </span>
                  ) : (
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: '#EF4444', fontWeight: 600 }}>
                      <XCircle size={16} /> Infeasible ({optResult.solver_status})
                    </span>
                  )}
                  <span style={{ color: 'var(--text-secondary)' }}>— {optResult.solver_message}</span>
                </div>

                {/* Capital Allocation vs Risk Contribution Comparative Chart */}
                <div className="card">
                  <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '16px' }}>
                    Capital Allocation (w_i) vs Risk Contribution (%RC_i)
                  </h3>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {optResult.assets.map((asset) => {
                      const weightPct = (optResult.weights[asset] ?? 0) * 100;
                      const rcPct = (optResult.percentage_risk_contributions[asset] ?? 0) * 100;
                      const targetPct = (optResult.target_risk_budgets[asset] ?? 0) * 100;

                      return (
                        <div key={asset} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                            <span style={{ fontWeight: 600 }}>{asset}</span>
                            <span style={{ color: 'var(--text-secondary)' }}>
                              Weight: <strong style={{ color: '#38BDF8' }}>{weightPct.toFixed(1)}%</strong> |
                              Risk: <strong style={{ color: '#10B981' }}>{rcPct.toFixed(1)}%</strong> |
                              Budget: {targetPct.toFixed(1)}%
                            </span>
                          </div>

                          <div style={{ position: 'relative', height: '14px', backgroundColor: 'var(--bg-secondary)', borderRadius: '4px', overflow: 'hidden' }}>
                            {/* Weight Bar */}
                            <div
                              style={{
                                position: 'absolute',
                                left: 0,
                                top: 0,
                                height: '50%',
                                width: `${Math.min(100, Math.max(0, weightPct))}%`,
                                backgroundColor: '#38BDF8',
                              }}
                              title={`Weight: ${weightPct.toFixed(2)}%`}
                            />
                            {/* Risk Contribution Bar */}
                            <div
                              style={{
                                position: 'absolute',
                                left: 0,
                                bottom: 0,
                                height: '50%',
                                width: `${Math.min(100, Math.max(0, rcPct))}%`,
                                backgroundColor: '#10B981',
                              }}
                              title={`%RC: ${rcPct.toFixed(2)}%`}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  <div style={{ display: 'flex', gap: '20px', marginTop: '16px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <div style={{ width: '12px', height: '8px', backgroundColor: '#38BDF8', borderRadius: '2px' }} />
                      <span>Capital Weight (w_i)</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <div style={{ width: '12px', height: '8px', backgroundColor: '#10B981', borderRadius: '2px' }} />
                      <span>Percentage Risk Contribution (%RC_i)</span>
                    </div>
                  </div>
                </div>

                {/* Analytical Risk Decomposition Table */}
                <div className="card">
                  <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '16px' }}>
                    Euler Risk Decomposition Details
                  </h3>

                  <div style={{ overflowX: 'auto' }}>
                    <table className="table" style={{ width: '100%', fontSize: '12px' }}>
                      <thead>
                        <tr>
                          <th>Asset</th>
                          <th style={{ textAlign: 'right' }}>Weight (w_i)</th>
                          <th style={{ textAlign: 'right' }}>MRC_i (∂σ/∂w_i)</th>
                          <th style={{ textAlign: 'right' }}>TRC_i (w_i·MRC_i)</th>
                          <th style={{ textAlign: 'right' }}>%RC_i</th>
                          <th style={{ textAlign: 'right' }}>Target Budget (b_i)</th>
                          <th style={{ textAlign: 'right' }}>Risk Drift</th>
                        </tr>
                      </thead>
                      <tbody>
                        {optResult.assets.map((asset) => {
                          const w = optResult.weights[asset] ?? 0;
                          const mrc = optResult.marginal_risk_contributions[asset] ?? 0;
                          const trc = optResult.total_risk_contributions[asset] ?? 0;
                          const prc = optResult.percentage_risk_contributions[asset] ?? 0;
                          const target = optResult.target_risk_budgets[asset] ?? 0;
                          const drift = Math.abs(prc - target);

                          return (
                            <tr key={asset}>
                              <td style={{ fontWeight: 600 }}>{asset}</td>
                              <td style={{ textAlign: 'right', color: '#38BDF8' }}>{(w * 100).toFixed(2)}%</td>
                              <td style={{ textAlign: 'right' }}>{(mrc * 100).toFixed(2)}%</td>
                              <td style={{ textAlign: 'right' }}>{(trc * 100).toFixed(3)}%</td>
                              <td style={{ textAlign: 'right', fontWeight: 600, color: '#10B981' }}>{(prc * 100).toFixed(2)}%</td>
                              <td style={{ textAlign: 'right', color: 'var(--text-secondary)' }}>{(target * 100).toFixed(2)}%</td>
                              <td style={{ textAlign: 'right', color: drift < 0.01 ? '#10B981' : '#F59E0B' }}>
                                {(drift * 100).toFixed(2)}%
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* HRP Cluster Ordering Badge */}
                {optResult.reordered_indices && optResult.method === 'hrp' && (
                  <div className="card">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                      <GitBranch size={16} style={{ color: '#818CF8' }} />
                      <h4 style={{ fontSize: '14px', fontWeight: 600 }}>HRP Quasi-Diagonalization Tree Leaf Order</h4>
                    </div>
                    <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '12px' }}>
                      Hierarchical clustering reorders assets so that highly correlated assets are adjacent:
                    </p>
                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                      {optResult.reordered_indices.map((idx, pos) => (
                        <div
                          key={pos}
                          style={{
                            padding: '4px 10px',
                            backgroundColor: 'var(--bg-secondary)',
                            border: '1px solid var(--border-subtle)',
                            borderRadius: '4px',
                            fontSize: '12px',
                          }}
                        >
                          <span style={{ color: 'var(--text-secondary)', marginRight: '6px' }}>#{pos + 1}</span>
                          <strong>{optResult.assets[idx]}</strong>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="card" style={{ textAlign: 'center', padding: '64px 24px' }}>
                <Activity size={40} style={{ color: 'var(--text-secondary)', margin: '0 auto 12px' }} />
                <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '6px' }}>
                  No Parity Solution Computed Yet
                </h3>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', maxWidth: '420px', margin: '0 auto' }}>
                  Configure your desired method (ERC, HRP, or Inverse Variance) in the sidebar and click "Optimize Risk Parity" to solve.
                </p>
              </div>
            )}
          </div>
        </div>
      ) : (
        /* Out-of-Sample Backtesting Tab */
        <div style={{ display: 'grid', gridTemplateColumns: '360px 1fr', gap: '24px' }}>
          {/* Backtest Config Sidebar */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div className="card">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
                <TrendingUp size={18} style={{ color: 'var(--primary)' }} />
                <h3 style={{ fontSize: '16px', fontWeight: 600 }}>Backtest Configuration</h3>
              </div>

              {/* Method Selector */}
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, marginBottom: '6px' }}>
                  Strategy Parity Method
                </label>
                <select
                  value={method}
                  onChange={(e) => setMethod(e.target.value as any)}
                  className="input-field"
                  style={{ width: '100%' }}
                >
                  <option value="erc">Equal Risk Contribution (ERC)</option>
                  <option value="hrp">Hierarchical Risk Parity (HRP)</option>
                  <option value="inverse_variance">Inverse Volatility / Variance</option>
                  <option value="equal_weight">Equal Weight Benchmark</option>
                </select>
              </div>

              {/* In-Sample Training Split Date */}
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, marginBottom: '6px' }}>
                  In-Sample Cut-Off (Split Date)
                </label>
                <input
                  type="date"
                  value={splitDate}
                  onChange={(e) => setSplitDate(e.target.value)}
                  className="input-field"
                  style={{ width: '100%' }}
                />
                <p style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  Covariance estimated strictly on observations ≤ split_date. Simulation runs on observations &gt; split_date.
                </p>
              </div>

              {/* Rebalance Frequency */}
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, marginBottom: '6px' }}>
                  Rebalance Frequency
                </label>
                <select
                  value={rebalanceFrequency}
                  onChange={(e) => setRebalanceFrequency(e.target.value as any)}
                  className="input-field"
                  style={{ width: '100%' }}
                >
                  <option value="monthly">Monthly</option>
                  <option value="quarterly">Quarterly</option>
                  <option value="weekly">Weekly</option>
                  <option value="daily">Daily</option>
                </select>
              </div>

              {/* Transaction Cost & Slippage */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    Fee (bps)
                  </label>
                  <input
                    type="number"
                    step="1"
                    min="0"
                    max="500"
                    value={costBps}
                    onChange={(e) => setCostBps(parseFloat(e.target.value) || 0)}
                    className="input-field"
                    style={{ width: '100%' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    Slippage (bps)
                  </label>
                  <input
                    type="number"
                    step="1"
                    min="0"
                    max="500"
                    value={slippageBps}
                    onChange={(e) => setSlippageBps(parseFloat(e.target.value) || 0)}
                    className="input-field"
                    style={{ width: '100%' }}
                  />
                </div>
              </div>

              {/* Initial Capital */}
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                  Initial Capital ($)
                </label>
                <input
                  type="number"
                  step="1000"
                  min="1000"
                  value={initialCash}
                  onChange={(e) => setInitialCash(parseFloat(e.target.value) || 100000)}
                  className="input-field"
                  style={{ width: '100%' }}
                />
              </div>

              {/* Execute Backtest */}
              <button
                onClick={handleRunBacktest}
                disabled={isBacktesting}
                className="btn btn-primary"
                style={{ width: '100%', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px' }}
              >
                <Play size={16} />
                <span>{isBacktesting ? 'Simulating Backtest...' : 'Run Out-of-Sample Backtest'}</span>
              </button>

              {backtestError && (
                <div className="alert alert-danger" style={{ marginTop: '16px', fontSize: '12px' }}>
                  <AlertTriangle size={14} style={{ flexShrink: 0 }} />
                  <span>{backtestError}</span>
                </div>
              )}
            </div>
          </div>

          {/* Backtest Results */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {backtestResult ? (
              <>
                {/* Temporal Split Summary */}
                <div className="card" style={{ padding: '16px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
                    <div>
                      <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>In-Sample Training</div>
                      <div style={{ fontWeight: 600 }}>Ends {backtestResult.in_sample_end}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Out-of-Sample Testing</div>
                      <div style={{ fontWeight: 600 }}>{backtestResult.out_of_sample_start} → {backtestResult.out_of_sample_end}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Rebalances Executed</div>
                      <div style={{ fontWeight: 600 }}>{backtestResult.strategy_metrics.rebalance_count} rebalances</div>
                    </div>
                  </div>
                </div>

                {/* Head-to-Head KPI Comparison Table */}
                <div className="card">
                  <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '16px' }}>
                    Strategy Performance vs Equal Weight Benchmark
                  </h3>

                  <div style={{ overflowX: 'auto' }}>
                    <table className="table" style={{ width: '100%', fontSize: '13px' }}>
                      <thead>
                        <tr>
                          <th>Metric</th>
                          <th style={{ textAlign: 'right', color: '#10B981' }}>
                            {backtestResult.method.toUpperCase()} Strategy (Net)
                          </th>
                          <th style={{ textAlign: 'right', color: '#94A3B8' }}>Equal Weight 1/N Benchmark</th>
                          <th style={{ textAlign: 'right' }}>Spread (Active)</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td>Annualized Return</td>
                          <td style={{ textAlign: 'right', fontWeight: 600, color: '#10B981' }}>
                            {(backtestResult.strategy_metrics.annualized_return * 100).toFixed(2)}%
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            {(backtestResult.equal_weight_benchmark_metrics.annualized_return * 100).toFixed(2)}%
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            {((backtestResult.strategy_metrics.annualized_return - backtestResult.equal_weight_benchmark_metrics.annualized_return) * 100).toFixed(2)}%
                          </td>
                        </tr>
                        <tr>
                          <td>Annualized Volatility</td>
                          <td style={{ textAlign: 'right', fontWeight: 600, color: '#38BDF8' }}>
                            {(backtestResult.strategy_metrics.annualized_volatility * 100).toFixed(2)}%
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            {(backtestResult.equal_weight_benchmark_metrics.annualized_volatility * 100).toFixed(2)}%
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            {((backtestResult.strategy_metrics.annualized_volatility - backtestResult.equal_weight_benchmark_metrics.annualized_volatility) * 100).toFixed(2)}%
                          </td>
                        </tr>
                        <tr>
                          <td>Sharpe Ratio</td>
                          <td style={{ textAlign: 'right', fontWeight: 600 }}>
                            {backtestResult.strategy_metrics.sharpe_ratio?.toFixed(2) ?? 'N/A'}
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            {backtestResult.equal_weight_benchmark_metrics.sharpe_ratio?.toFixed(2) ?? 'N/A'}
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            {backtestResult.strategy_metrics.sharpe_ratio != null && backtestResult.equal_weight_benchmark_metrics.sharpe_ratio != null
                              ? (backtestResult.strategy_metrics.sharpe_ratio - backtestResult.equal_weight_benchmark_metrics.sharpe_ratio).toFixed(2)
                              : 'N/A'}
                          </td>
                        </tr>
                        <tr>
                          <td>Sortino Ratio</td>
                          <td style={{ textAlign: 'right' }}>
                            {backtestResult.strategy_metrics.sortino_ratio?.toFixed(2) ?? 'N/A'}
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            {backtestResult.equal_weight_benchmark_metrics.sortino_ratio?.toFixed(2) ?? 'N/A'}
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            {backtestResult.strategy_metrics.sortino_ratio != null && backtestResult.equal_weight_benchmark_metrics.sortino_ratio != null
                              ? (backtestResult.strategy_metrics.sortino_ratio - backtestResult.equal_weight_benchmark_metrics.sortino_ratio).toFixed(2)
                              : 'N/A'}
                          </td>
                        </tr>
                        <tr>
                          <td>Max Drawdown</td>
                          <td style={{ textAlign: 'right', color: '#EF4444', fontWeight: 600 }}>
                            {(backtestResult.strategy_metrics.max_drawdown * 100).toFixed(2)}%
                          </td>
                          <td style={{ textAlign: 'right', color: '#EF4444' }}>
                            {(backtestResult.equal_weight_benchmark_metrics.max_drawdown * 100).toFixed(2)}%
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            {((backtestResult.strategy_metrics.max_drawdown - backtestResult.equal_weight_benchmark_metrics.max_drawdown) * 100).toFixed(2)}%
                          </td>
                        </tr>
                        <tr>
                          <td>Total Friction Costs (Fees + Slippage)</td>
                          <td style={{ textAlign: 'right' }}>
                            ${(backtestResult.strategy_metrics.total_transaction_costs + backtestResult.strategy_metrics.total_slippage_costs).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            ${(backtestResult.equal_weight_benchmark_metrics.total_transaction_costs + backtestResult.equal_weight_benchmark_metrics.total_slippage_costs).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </td>
                          <td style={{ textAlign: 'right' }}>—</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Backtest Curves (Equity & Drawdown) */}
                <div className="card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                    <h3 style={{ fontSize: '16px', fontWeight: 600 }}>
                      {backtestChartMode === 'equity' ? 'Out-of-Sample Portfolio Wealth Trajectory' : 'Out-of-Sample Drawdown Profile (%)'}
                    </h3>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button
                        onClick={() => setBacktestChartMode('equity')}
                        className={`btn ${backtestChartMode === 'equity' ? 'btn-primary' : 'btn-secondary'}`}
                        style={{ fontSize: '12px', padding: '4px 10px' }}
                      >
                        Equity Curve ($)
                      </button>
                      <button
                        onClick={() => setBacktestChartMode('drawdown')}
                        className={`btn ${backtestChartMode === 'drawdown' ? 'btn-primary' : 'btn-secondary'}`}
                        style={{ fontSize: '12px', padding: '4px 10px' }}
                      >
                        Drawdown (%)
                      </button>
                    </div>
                  </div>

                  {/* Visual Timeseries Representation */}
                  <div style={{ height: '260px', width: '100%', position: 'relative' }}>
                    {backtestChartMode === 'equity' ? (
                      <svg viewBox="0 0 600 240" style={{ width: '100%', height: '100%', overflow: 'visible' }}>
                        {(() => {
                          const points = backtestResult.equity_curve;
                          if (points.length < 2) return null;

                          const allVals = points.flatMap((p) => [p.strategy, p.benchmark]);
                          const minVal = Math.min(...allVals) * 0.98;
                          const maxVal = Math.max(...allVals) * 1.02;
                          const valRange = maxVal - minVal || 1;

                          const toX = (i: number) => (i / (points.length - 1)) * 580 + 10;
                          const toY = (val: number) => 220 - ((val - minVal) / valRange) * 200;

                          const stratPath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${toX(i)} ${toY(p.strategy)}`).join(' ');
                          const benchPath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${toX(i)} ${toY(p.benchmark)}`).join(' ');

                          return (
                            <>
                              {/* Grid lines */}
                              <line x1="10" y1="20" x2="590" y2="20" stroke="var(--border-subtle)" strokeDasharray="3 3" />
                              <line x1="10" y1="120" x2="590" y2="120" stroke="var(--border-subtle)" strokeDasharray="3 3" />
                              <line x1="10" y1="220" x2="590" y2="220" stroke="var(--border-subtle)" />

                              {/* Benchmark Path */}
                              <path d={benchPath} fill="none" stroke="#64748B" strokeWidth="2" strokeDasharray="4 4" />
                              {/* Strategy Path */}
                              <path d={stratPath} fill="none" stroke="#10B981" strokeWidth="2.5" />

                              {/* Labels */}
                              <text x="12" y="18" fill="var(--text-secondary)" fontSize="10">${maxVal.toFixed(0)}</text>
                              <text x="12" y="215" fill="var(--text-secondary)" fontSize="10">${minVal.toFixed(0)}</text>
                            </>
                          );
                        })()}
                      </svg>
                    ) : (
                      <svg viewBox="0 0 600 240" style={{ width: '100%', height: '100%', overflow: 'visible' }}>
                        {(() => {
                          const points = backtestResult.drawdown_curve;
                          if (points.length < 2) return null;

                          const allVals = points.flatMap((p) => [p.strategy, p.benchmark]);
                          const minVal = Math.min(-1, Math.min(...allVals) * 1.05);
                          const maxVal = 0;
                          const valRange = maxVal - minVal || 1;

                          const toX = (i: number) => (i / (points.length - 1)) * 580 + 10;
                          const toY = (val: number) => 30 + ((maxVal - val) / valRange) * 190;

                          const stratPath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${toX(i)} ${toY(p.strategy)}`).join(' ');
                          const benchPath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${toX(i)} ${toY(p.benchmark)}`).join(' ');

                          return (
                            <>
                              {/* 0% baseline */}
                              <line x1="10" y1="30" x2="590" y2="30" stroke="var(--border-subtle)" strokeWidth="1.5" />
                              <line x1="10" y1="125" x2="590" y2="125" stroke="var(--border-subtle)" strokeDasharray="3 3" />
                              <line x1="10" y1="220" x2="590" y2="220" stroke="var(--border-subtle)" strokeDasharray="3 3" />

                              {/* Benchmark Path */}
                              <path d={benchPath} fill="none" stroke="#64748B" strokeWidth="2" strokeDasharray="4 4" />
                              {/* Strategy Path */}
                              <path d={stratPath} fill="none" stroke="#EF4444" strokeWidth="2.5" />

                              {/* Labels */}
                              <text x="12" y="26" fill="var(--text-secondary)" fontSize="10">0%</text>
                              <text x="12" y="216" fill="var(--text-secondary)" fontSize="10">{minVal.toFixed(1)}%</text>
                            </>
                          );
                        })()}
                      </svg>
                    )}
                  </div>

                  <div style={{ display: 'flex', gap: '20px', marginTop: '12px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <div style={{ width: '12px', height: '3px', backgroundColor: backtestChartMode === 'equity' ? '#10B981' : '#EF4444' }} />
                      <span>{backtestResult.method.toUpperCase()} Strategy</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <div style={{ width: '12px', height: '3px', backgroundColor: '#64748B' }} />
                      <span>Equal Weight Benchmark (1/N)</span>
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div className="card" style={{ textAlign: 'center', padding: '64px 24px' }}>
                <TrendingUp size={40} style={{ color: 'var(--text-secondary)', margin: '0 auto 12px' }} />
                <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '6px' }}>
                  No Out-of-Sample Simulation Executed
                </h3>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', maxWidth: '420px', margin: '0 auto' }}>
                  Select an in-sample training split date and rebalancing frequency, then click "Run Out-of-Sample Backtest".
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
