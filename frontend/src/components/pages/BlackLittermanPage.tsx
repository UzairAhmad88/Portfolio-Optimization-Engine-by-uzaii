import React, { useState, useEffect } from 'react';
import {
  Layers,
  AlertTriangle,
  Sliders,
  Plus,
  Trash2,
  Calendar,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { useDataset } from '../../context/DatasetContext';
import type {
  BlackLittermanViewItem,
  BlackLittermanOptimizeRequest,
  BlackLittermanOptimizeResponse,
  BlackLittermanBacktestRequest,
  BlackLittermanBacktestResponse,
} from '../../types/api';

type ActiveTab = 'optimization' | 'backtest';

export const BlackLittermanPage: React.FC = () => {
  const { currentDataset, availableAssets } = useDataset();

  // Tab state
  const [activeTab, setActiveTab] = useState<ActiveTab>('optimization');

  // Universe & Core Parameters
  const [selectedAssets, setSelectedAssets] = useState<string[]>([]);
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [riskFreeRate, setRiskFreeRate] = useState<number>(0.02);
  const [tau, setTau] = useState<number>(0.05);
  const [riskAversion, setRiskAversion] = useState<number>(2.50);

  // Views State
  const [views, setViews] = useState<BlackLittermanViewItem[]>([
    {
      view_type: 'relative',
      assets: [],
      weights: [1.0, -1.0],
      target_return: 0.03,
      confidence: 0.65,
      description: 'Asset 1 will outperform Asset 2 by 3.0%',
    },
  ]);

  // Constraints & Objective
  const [objective, setObjective] = useState<'max_sharpe' | 'min_variance' | 'mean_variance_utility'>('max_sharpe');
  const [minWeight, setMinWeight] = useState<number>(0.0);
  const [maxWeight, setMaxWeight] = useState<number>(0.60);

  // Backtest Options
  const [trainEndDate, setTrainEndDate] = useState<string>('');
  const [rebalanceFrequency, setRebalanceFrequency] = useState<'monthly' | 'quarterly' | 'daily'>('monthly');
  const [costBps, setCostBps] = useState<number>(10.0);
  const [slippageBps, setSlippageBps] = useState<number>(5.0);

  // Execution states
  const [isOptimizing, setIsOptimizing] = useState<boolean>(false);
  const [optimizationError, setOptimizationError] = useState<string | null>(null);
  const [optResult, setOptResult] = useState<BlackLittermanOptimizeResponse | null>(null);

  const [isBacktesting, setIsBacktesting] = useState<boolean>(false);
  const [backtestError, setBacktestError] = useState<string | null>(null);
  const [backtestResult, setBacktestResult] = useState<BlackLittermanBacktestResponse | null>(null);

  // Initialize selected assets and views when dataset loads
  useEffect(() => {
    if (availableAssets.length > 0 && selectedAssets.length === 0) {
      const initial = availableAssets.slice(0, Math.min(4, availableAssets.length)).map((a) => a.asset_id);
      setSelectedAssets(initial);

      if (initial.length >= 2) {
        setViews([
          {
            view_type: 'relative',
            assets: [initial[0], initial[1]],
            weights: [1.0, -1.0],
            target_return: 0.035,
            confidence: 0.70,
            description: `${initial[0]} outperforms ${initial[1]} by 3.5%`,
          },
        ]);
      }
    }
  }, [availableAssets]);

  const toggleAsset = (assetId: string) => {
    if (selectedAssets.includes(assetId)) {
      if (selectedAssets.length > 2) {
        const next = selectedAssets.filter((id) => id !== assetId);
        setSelectedAssets(next);
      }
    } else {
      setSelectedAssets([...selectedAssets, assetId]);
    }
  };

  const handleAddView = () => {
    if (selectedAssets.length < 2) return;
    const newView: BlackLittermanViewItem = {
      view_type: 'relative',
      assets: [selectedAssets[0], selectedAssets[1]],
      weights: [1.0, -1.0],
      target_return: 0.02,
      confidence: 0.50,
      description: `${selectedAssets[0]} relative outperformance`,
    };
    setViews([...views, newView]);
  };

  const handleRemoveView = (index: number) => {
    setViews(views.filter((_, i) => i !== index));
  };

  const handleUpdateView = (index: number, updated: Partial<BlackLittermanViewItem>) => {
    const nextViews = [...views];
    nextViews[index] = { ...nextViews[index], ...updated };
    setViews(nextViews);
  };

  const handleRunOptimization = async () => {
    if (!currentDataset) {
      setOptimizationError('No dataset selected. Please register a dataset in Market Data.');
      return;
    }
    if (selectedAssets.length < 2) {
      setOptimizationError('At least 2 assets are required for Black-Litterman optimization.');
      return;
    }

    setIsOptimizing(true);
    setOptimizationError(null);

    const payload: BlackLittermanOptimizeRequest = {
      dataset_id: currentDataset.dataset_id,
      assets: selectedAssets,
      start_date: startDate || undefined,
      end_date: endDate || undefined,
      tau,
      risk_aversion: riskAversion,
      risk_free_rate: riskFreeRate,
      equilibrium_weights: null,
      views: views.map((v) => ({
        view_type: v.view_type,
        assets: v.assets,
        weights: v.weights,
        target_return: v.target_return,
        confidence: v.confidence,
      })),
      objective,
      constraints: {
        default_min_weight: minWeight,
        default_max_weight: maxWeight,
      },
    };

    try {
      const resp = await apiClient.optimizeBlackLitterman(payload);
      setOptResult(resp);
    } catch (err: any) {
      setOptimizationError(err?.message || 'Black-Litterman optimization failed.');
    } finally {
      setIsOptimizing(false);
    }
  };

  const handleRunBacktest = async () => {
    if (!currentDataset) {
      setBacktestError('No dataset selected. Please register a dataset in Market Data.');
      return;
    }
    if (!trainEndDate) {
      setBacktestError('Please specify an in-sample training cutoff date.');
      return;
    }

    setIsBacktesting(true);
    setBacktestError(null);

    const payload: BlackLittermanBacktestRequest = {
      dataset_id: currentDataset.dataset_id,
      assets: selectedAssets,
      train_end_date: trainEndDate,
      tau,
      risk_aversion: riskAversion,
      risk_free_rate: riskFreeRate,
      equilibrium_weights: null,
      views: views.map((v) => ({
        view_type: v.view_type,
        assets: v.assets,
        weights: v.weights,
        target_return: v.target_return,
        confidence: v.confidence,
      })),
      objective,
      min_weight: minWeight,
      max_weight: maxWeight,
      rebalance_frequency: rebalanceFrequency,
      cost_bps: costBps,
      slippage_bps: slippageBps,
    };

    try {
      const resp = await apiClient.backtestBlackLitterman(payload);
      setBacktestResult(resp);
    } catch (err: any) {
      setBacktestError(err?.message || 'Black-Litterman backtest failed.');
    } finally {
      setIsBacktesting(false);
    }
  };

  return (
    <div className="workspace-container">
      {/* Page Header */}
      <div style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <span className="badge badge-primary">Stage 14: Bayesian Framework</span>
          <span className="badge badge-info">Woodbury Formula</span>
          <span className="badge badge-neutral">Idzorek Confidence</span>
        </div>
        <h2 style={{ fontSize: '20px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>
          Black-Litterman Bayesian Portfolio Optimization
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '13px', maxWidth: '850px' }}>
          Combine market equilibrium implied returns with subjective or quantitative views to produce stable, intuitive
          active tilts without extreme corner solutions.
        </p>
      </div>

      {/* Tabs */}
      <div className="tabs" style={{ marginBottom: '20px' }}>
        <button
          className={`tab-btn ${activeTab === 'optimization' ? 'active' : ''}`}
          onClick={() => setActiveTab('optimization')}
        >
          <Sliders size={15} style={{ marginRight: '6px' }} />
          Bayesian Optimization & Tilts
        </button>
        <button
          className={`tab-btn ${activeTab === 'backtest' ? 'active' : ''}`}
          onClick={() => setActiveTab('backtest')}
        >
          <Calendar size={15} style={{ marginRight: '6px' }} />
          Chronological Out-of-Sample Backtest
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '380px 1fr', gap: '24px', alignItems: 'start' }}>
        {/* Left Column: Parameter Configuration */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
          <div>
            <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '10px' }}>1. Asset Universe</h3>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
              Select assets to include in the market equilibrium and view portfolio (min 2).
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {availableAssets.map((asset) => {
                const isSelected = selectedAssets.includes(asset.asset_id);
                return (
                  <button
                    key={asset.asset_id}
                    onClick={() => toggleAsset(asset.asset_id)}
                    className={`btn ${isSelected ? 'btn-primary' : 'btn-secondary'}`}
                    style={{ fontSize: '12px', padding: '4px 8px' }}
                  >
                    {asset.ticker}
                  </button>
                );
              })}
            </div>
          </div>

          <hr style={{ border: 'none', borderTop: '1px solid var(--border-subtle)' }} />

          {/* Hyperparameters */}
          <div>
            <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '10px' }}>2. Prior & Market Hyperparameters</h3>
            
            <div style={{ marginBottom: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '4px' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Prior Uncertainty Scalar (τ):</span>
                <span style={{ fontWeight: 600 }}>{tau.toFixed(3)}</span>
              </div>
              <input
                type="range"
                min="0.005"
                max="0.50"
                step="0.005"
                value={tau}
                onChange={(e) => setTau(parseFloat(e.target.value))}
                style={{ width: '100%' }}
              />
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                Smaller τ (e.g. 0.025 - 0.05) anchors posterior closely to market equilibrium.
              </span>
            </div>

            <div style={{ marginBottom: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '4px' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Market Risk Aversion (γ):</span>
                <span style={{ fontWeight: 600 }}>{riskAversion.toFixed(1)}</span>
              </div>
              <input
                type="range"
                min="1.0"
                max="10.0"
                step="0.5"
                value={riskAversion}
                onChange={(e) => setRiskAversion(parseFloat(e.target.value))}
                style={{ width: '100%' }}
              />
            </div>

            <div style={{ marginBottom: '12px' }}>
              <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
                Risk-Free Rate (Rf):
              </label>
              <input
                type="number"
                step="0.005"
                value={riskFreeRate}
                onChange={(e) => setRiskFreeRate(parseFloat(e.target.value))}
                className="input"
                style={{ width: '100%' }}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
              <div>
                <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Start Date (Opt):</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="input"
                  style={{ width: '100%' }}
                />
              </div>
              <div>
                <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>End Date (Opt):</label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="input"
                  style={{ width: '100%' }}
                />
              </div>
            </div>
          </div>

          <hr style={{ border: 'none', borderTop: '1px solid var(--border-subtle)' }} />

          {/* Views Studio */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <h3 style={{ fontSize: '14px', fontWeight: 600 }}>3. Quantitative Views Studio</h3>
              <button onClick={handleAddView} className="btn btn-secondary" style={{ fontSize: '11px', padding: '3px 8px' }}>
                <Plus size={12} style={{ marginRight: '4px' }} />
                Add View
              </button>
            </div>

            {views.length === 0 ? (
              <p style={{ fontSize: '12px', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                Zero views configured. Optimization will strictly reproduce the implied market equilibrium.
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {views.map((v, idx) => (
                  <div
                    key={idx}
                    style={{
                      background: 'var(--bg-secondary)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: 'var(--radius-md)',
                      padding: '10px',
                      fontSize: '12px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <span style={{ fontWeight: 600, color: 'var(--primary)' }}>View #{idx + 1}</span>
                      <button
                        onClick={() => handleRemoveView(idx)}
                        style={{ background: 'none', border: 'none', color: 'var(--danger)', cursor: 'pointer', padding: 0 }}
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', marginBottom: '6px' }}>
                      <div>
                        <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Type:</label>
                        <select
                          value={v.view_type}
                          onChange={(e) =>
                            handleUpdateView(idx, {
                              view_type: e.target.value as 'relative' | 'absolute',
                              weights: e.target.value === 'relative' ? [1.0, -1.0] : [1.0],
                            })
                          }
                          className="input"
                          style={{ width: '100%', padding: '4px' }}
                        >
                          <option value="relative">Relative (A &gt; B)</option>
                          <option value="absolute">Absolute (A Target)</option>
                        </select>
                      </div>

                      <div>
                        <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Target Return:</label>
                        <input
                          type="number"
                          step="0.005"
                          value={v.target_return}
                          onChange={(e) => handleUpdateView(idx, { target_return: parseFloat(e.target.value) || 0.0 })}
                          className="input"
                          style={{ width: '100%', padding: '4px' }}
                        />
                      </div>
                    </div>

                    {v.view_type === 'relative' ? (
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', marginBottom: '6px' }}>
                        <div>
                          <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Long Asset:</label>
                          <select
                            value={v.assets[0] || ''}
                            onChange={(e) => {
                              const newAssets = [e.target.value, v.assets[1] || selectedAssets[1] || selectedAssets[0]];
                              handleUpdateView(idx, { assets: newAssets });
                            }}
                            className="input"
                            style={{ width: '100%', padding: '4px' }}
                          >
                            {selectedAssets.map((a) => (
                              <option key={a} value={a}>
                                {a}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Short Asset:</label>
                          <select
                            value={v.assets[1] || ''}
                            onChange={(e) => {
                              const newAssets = [v.assets[0] || selectedAssets[0], e.target.value];
                              handleUpdateView(idx, { assets: newAssets });
                            }}
                            className="input"
                            style={{ width: '100%', padding: '4px' }}
                          >
                            {selectedAssets.map((a) => (
                              <option key={a} value={a}>
                                {a}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                    ) : (
                      <div style={{ marginBottom: '6px' }}>
                        <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Target Asset:</label>
                        <select
                          value={v.assets[0] || ''}
                          onChange={(e) => handleUpdateView(idx, { assets: [e.target.value] })}
                          className="input"
                          style={{ width: '100%', padding: '4px' }}
                        >
                          {selectedAssets.map((a) => (
                            <option key={a} value={a}>
                              {a}
                            </option>
                          ))}
                        </select>
                      </div>
                    )}

                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
                        <span style={{ color: 'var(--text-secondary)' }}>Confidence:</span>
                        <span style={{ fontWeight: 600 }}>{(v.confidence * 100).toFixed(0)}%</span>
                      </div>
                      <input
                        type="range"
                        min="0.05"
                        max="0.95"
                        step="0.05"
                        value={v.confidence}
                        onChange={(e) => handleUpdateView(idx, { confidence: parseFloat(e.target.value) })}
                        style={{ width: '100%' }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <hr style={{ border: 'none', borderTop: '1px solid var(--border-subtle)' }} />

          {/* Constraints & Solvers */}
          <div>
            <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '10px' }}>4. Constraints & Solvers</h3>
            
            <div style={{ marginBottom: '10px' }}>
              <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
                Optimization Objective:
              </label>
              <select
                value={objective}
                onChange={(e) => setObjective(e.target.value as any)}
                className="input"
                style={{ width: '100%' }}
              >
                <option value="max_sharpe">Maximum Sharpe Ratio</option>
                <option value="min_variance">Minimum Variance</option>
                <option value="mean_variance_utility">Mean-Variance Utility</option>
              </select>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
              <div>
                <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Min Weight:</label>
                <input
                  type="number"
                  step="0.05"
                  value={minWeight}
                  onChange={(e) => setMinWeight(parseFloat(e.target.value))}
                  className="input"
                  style={{ width: '100%' }}
                />
              </div>
              <div>
                <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Max Weight:</label>
                <input
                  type="number"
                  step="0.05"
                  value={maxWeight}
                  onChange={(e) => setMaxWeight(parseFloat(e.target.value))}
                  className="input"
                  style={{ width: '100%' }}
                />
              </div>
            </div>
          </div>

          {activeTab === 'backtest' && (
            <>
              <hr style={{ border: 'none', borderTop: '1px solid var(--border-subtle)' }} />
              <div>
                <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '10px' }}>5. Backtest Window</h3>
                <div style={{ marginBottom: '8px' }}>
                  <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>In-Sample Split Date:</label>
                  <input
                    type="date"
                    value={trainEndDate}
                    onChange={(e) => setTrainEndDate(e.target.value)}
                    className="input"
                    style={{ width: '100%' }}
                  />
                  <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                    Data before this date is used for prior & views calibration; data after is out-of-sample test.
                  </span>
                </div>

                <div style={{ marginBottom: '8px' }}>
                  <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Rebalance Frequency:</label>
                  <select
                    value={rebalanceFrequency}
                    onChange={(e) => setRebalanceFrequency(e.target.value as any)}
                    className="input"
                    style={{ width: '100%' }}
                  >
                    <option value="monthly">Monthly</option>
                    <option value="quarterly">Quarterly</option>
                    <option value="daily">Daily</option>
                  </select>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '8px' }}>
                  <div>
                    <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Cost (bps):</label>
                    <input
                      type="number"
                      step="1"
                      value={costBps}
                      onChange={(e) => setCostBps(parseFloat(e.target.value) || 0)}
                      className="input"
                      style={{ width: '100%' }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Slippage (bps):</label>
                    <input
                      type="number"
                      step="1"
                      value={slippageBps}
                      onChange={(e) => setSlippageBps(parseFloat(e.target.value) || 0)}
                      className="input"
                      style={{ width: '100%' }}
                    />
                  </div>
                </div>
              </div>
            </>
          )}

          {/* Action Button */}
          {activeTab === 'optimization' ? (
            <button
              onClick={handleRunOptimization}
              disabled={isOptimizing}
              className="btn btn-primary"
              style={{ width: '100%', justifyContent: 'center' }}
            >
              {isOptimizing ? 'Computing Bayesian Posterior...' : 'Execute Black-Litterman Optimization'}
            </button>
          ) : (
            <button
              onClick={handleRunBacktest}
              disabled={isBacktesting}
              className="btn btn-primary"
              style={{ width: '100%', justifyContent: 'center' }}
            >
              {isBacktesting ? 'Running Out-of-Sample Backtest...' : 'Execute Chronological Backtest'}
            </button>
          )}

          {optimizationError && (
            <div className="alert alert-danger" style={{ fontSize: '12px', padding: '8px 12px' }}>
              <AlertTriangle size={14} style={{ marginRight: '6px', flexShrink: 0 }} />
              <span>{optimizationError}</span>
            </div>
          )}

          {backtestError && (
            <div className="alert alert-danger" style={{ fontSize: '12px', padding: '8px 12px' }}>
              <AlertTriangle size={14} style={{ marginRight: '6px', flexShrink: 0 }} />
              <span>{backtestError}</span>
            </div>
          )}
        </div>

        {/* Right Column: Interactive Results */}
        <div>
          {activeTab === 'optimization' ? (
            optResult ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                {/* Status & Diagnostic Badges */}
                <div className="card" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
                  <div>
                    <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>L1 Active Tilt Distance</span>
                    <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--primary)' }}>
                      {(optResult.diagnostics.weight_distance_d1 * 100).toFixed(1)}%
                    </div>
                    <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                      Max: {optResult.diagnostics.max_tilt_asset} ({optResult.diagnostics.max_tilt_value > 0 ? '+' : ''}
                      {(optResult.diagnostics.max_tilt_value * 100).toFixed(1)}%)
                    </span>
                  </div>

                  <div>
                    <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Effective Assets (N_eff)</span>
                    <div style={{ fontSize: '18px', fontWeight: 700 }}>
                      {optResult.diagnostics.effective_assets_optimal.toFixed(2)}
                    </div>
                    <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                      Prior: {optResult.diagnostics.effective_assets_prior.toFixed(2)}
                    </span>
                  </div>

                  <div>
                    <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Posterior Expected Return</span>
                    <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--success)' }}>
                      {((optResult.portfolio_metrics.expected_return || 0) * 100).toFixed(2)}%
                    </div>
                    <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                      Annualized BL expected return
                    </span>
                  </div>

                  <div>
                    <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Posterior Sharpe Ratio</span>
                    <div style={{ fontSize: '18px', fontWeight: 700 }}>
                      {optResult.portfolio_metrics.sharpe_ratio !== null && optResult.portfolio_metrics.sharpe_ratio !== undefined
                        ? optResult.portfolio_metrics.sharpe_ratio.toFixed(2)
                        : 'N/A'}
                    </div>
                    <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                      Vol: {((optResult.portfolio_metrics.volatility || 0) * 100).toFixed(2)}%
                    </span>
                  </div>
                </div>

                {/* Active Tilts Bar Chart */}
                <div className="card">
                  <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '6px' }}>Active Tilts (Δw = w* - w_eq)</h3>
                  <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
                    Visualizing Bayesian portfolio reallocations away from benchmark equilibrium toward view assets.
                  </p>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {optResult.assets.map((asset) => {
                      const tilt = optResult.active_tilts[asset] || 0.0;
                      const absMax = Math.max(...Object.values(optResult.active_tilts).map(Math.abs), 0.1);
                      const barWidth = Math.min(100, (Math.abs(tilt) / absMax) * 100);
                      const isPositive = tilt >= 0;

                      return (
                        <div key={asset} style={{ display: 'grid', gridTemplateColumns: '90px 1fr 60px', alignItems: 'center', gap: '12px' }}>
                          <span style={{ fontSize: '12px', fontWeight: 500 }}>{asset}</span>
                          <div style={{ display: 'flex', alignItems: 'center', height: '18px', background: 'var(--bg-secondary)', borderRadius: '4px', position: 'relative' }}>
                            <div
                              style={{
                                width: '50%',
                                display: 'flex',
                                justifyContent: 'flex-end',
                                borderRight: '1px solid var(--border-subtle)',
                              }}
                            >
                              {!isPositive && (
                                <div
                                  style={{
                                    height: '10px',
                                    width: `${barWidth}%`,
                                    background: 'var(--danger)',
                                    borderRadius: '2px 0 0 2px',
                                  }}
                                />
                              )}
                            </div>
                            <div style={{ width: '50%', display: 'flex', justifyContent: 'flex-start' }}>
                              {isPositive && (
                                <div
                                  style={{
                                    height: '10px',
                                    width: `${barWidth}%`,
                                    background: 'var(--success)',
                                    borderRadius: '0 2px 2px 0',
                                  }}
                                />
                              )}
                            </div>
                          </div>
                          <span
                            style={{
                              fontSize: '12px',
                              fontWeight: 600,
                              textAlign: 'right',
                              color: isPositive ? 'var(--success)' : 'var(--danger)',
                            }}
                          >
                            {isPositive ? '+' : ''}
                            {(tilt * 100).toFixed(1)}%
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Prior vs Posterior & Weights Breakdown Table */}
                <div className="card">
                  <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '12px' }}>Prior vs. Posterior Allocation Summary</h3>
                  <div style={{ overflowX: 'auto' }}>
                    <table className="table" style={{ width: '100%', fontSize: '12px' }}>
                      <thead>
                        <tr>
                          <th>Asset</th>
                          <th>Prior Implied Return (Π)</th>
                          <th>Posterior Return (μ_BL)</th>
                          <th>Prior Weight (w_eq)</th>
                          <th>Optimal Weight (w*)</th>
                          <th>Active Tilt (Δw)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {optResult.assets.map((asset) => (
                          <tr key={asset}>
                            <td style={{ fontWeight: 600 }}>{asset}</td>
                            <td>{((optResult.equilibrium_returns[asset] || 0) * 100).toFixed(2)}%</td>
                            <td style={{ fontWeight: 600, color: 'var(--primary)' }}>
                              {((optResult.posterior_returns[asset] || 0) * 100).toFixed(2)}%
                            </td>
                            <td>{((optResult.prior_weights[asset] || 0) * 100).toFixed(1)}%</td>
                            <td style={{ fontWeight: 600 }}>{((optResult.optimal_weights[asset] || 0) * 100).toFixed(1)}%</td>
                            <td
                              style={{
                                fontWeight: 600,
                                color: (optResult.active_tilts[asset] || 0) >= 0 ? 'var(--success)' : 'var(--danger)',
                              }}
                            >
                              {(optResult.active_tilts[asset] || 0) >= 0 ? '+' : ''}
                              {((optResult.active_tilts[asset] || 0) * 100).toFixed(1)}%
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Views Summary Table */}
                {optResult.views_summary.length > 0 && (
                  <div className="card">
                    <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '12px' }}>Views Impact & Absorption Details</h3>
                    <div style={{ overflowX: 'auto' }}>
                      <table className="table" style={{ width: '100%', fontSize: '12px' }}>
                        <thead>
                          <tr>
                            <th>Description</th>
                            <th>Confidence</th>
                            <th>Prior Expected</th>
                            <th>Target Return</th>
                            <th>Posterior Spread</th>
                            <th>Absorbed Difference</th>
                          </tr>
                        </thead>
                        <tbody>
                          {optResult.views_summary.map((v, i) => (
                            <tr key={i}>
                              <td style={{ fontWeight: 500 }}>{v.description}</td>
                              <td>{(v.confidence * 100).toFixed(0)}%</td>
                              <td>{(v.prior_expected_spread * 100).toFixed(2)}%</td>
                              <td style={{ fontWeight: 600 }}>{(v.target_return * 100).toFixed(2)}%</td>
                              <td style={{ fontWeight: 600, color: 'var(--primary)' }}>
                                {(v.posterior_expected_spread * 100).toFixed(2)}%
                              </td>
                              <td style={{ color: v.absorbed_difference >= 0 ? 'var(--success)' : 'var(--danger)' }}>
                                {v.absorbed_difference >= 0 ? '+' : ''}
                                {(v.absorbed_difference * 100).toFixed(2)}%
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="card empty-state" style={{ padding: '60px 20px', textAlign: 'center' }}>
                <Layers size={40} style={{ color: 'var(--text-muted)', marginBottom: '16px' }} />
                <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '8px' }}>
                  No Optimization Executed Yet
                </h3>
                <p style={{ color: 'var(--text-secondary)', fontSize: '13px', maxWidth: '420px', margin: '0 auto 20px' }}>
                  Configure prior market parameters, formulate your analyst views, and click "Execute Black-Litterman Optimization"
                  to compute the posterior distribution.
                </p>
              </div>
            )
          ) : backtestResult ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {/* Backtest KPI Summary Cards */}
              <div className="card" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
                <div>
                  <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Out-of-Sample Sharpe Ratio</span>
                  <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--primary)' }}>
                    {backtestResult.black_litterman_kpis.sharpe_ratio?.toFixed(2) ?? 'N/A'}
                  </div>
                  <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                    Benchmark: {backtestResult.equilibrium_kpis.sharpe_ratio?.toFixed(2) ?? 'N/A'}
                  </span>
                </div>

                <div>
                  <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Cumulative Return (Net)</span>
                  <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--success)' }}>
                    {(backtestResult.black_litterman_kpis.cumulative_return * 100).toFixed(2)}%
                  </div>
                  <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                    Benchmark: {(backtestResult.equilibrium_kpis.cumulative_return * 100).toFixed(2)}%
                  </span>
                </div>

                <div>
                  <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Maximum Drawdown</span>
                  <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--danger)' }}>
                    {(backtestResult.black_litterman_kpis.max_drawdown * 100).toFixed(2)}%
                  </div>
                  <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                    Benchmark: {(backtestResult.equilibrium_kpis.max_drawdown * 100).toFixed(2)}%
                  </span>
                </div>

                <div>
                  <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Total Friction & Turnover</span>
                  <div style={{ fontSize: '18px', fontWeight: 700 }}>
                    {(backtestResult.black_litterman_kpis.total_turnover * 100).toFixed(1)}%
                  </div>
                  <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                    Friction: ${backtestResult.black_litterman_kpis.total_friction_costs?.toFixed(2) ?? '0.00'}
                  </span>
                </div>
              </div>

              {/* Equity Curves Visualization */}
              <div className="card">
                <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '6px' }}>Out-of-Sample Wealth Progression</h3>
                <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
                  Comparing net compounded wealth of Black-Litterman active portfolio vs. Equilibrium Benchmark over the test period.
                </p>

                {backtestResult.equity_curves.length > 1 && (
                  <div style={{ height: '220px', width: '100%', position: 'relative' }}>
                    <svg style={{ width: '100%', height: '100%', overflow: 'visible' }}>
                      {(() => {
                        const pts = backtestResult.equity_curves;
                        const minVal = Math.min(...pts.map((p) => Math.min(p.black_litterman_portfolio_value, p.equilibrium_portfolio_value)));
                        const maxVal = Math.max(...pts.map((p) => Math.max(p.black_litterman_portfolio_value, p.equilibrium_portfolio_value)));
                        const range = Math.max(maxVal - minVal, 100.0);

                        const blCoords = pts.map((p, i) => {
                          const x = (i / (pts.length - 1)) * 100;
                          const y = 100 - ((p.black_litterman_portfolio_value - minVal) / range) * 90;
                          return `${x}%,${y}%`;
                        }).join(' ');

                        const eqCoords = pts.map((p, i) => {
                          const x = (i / (pts.length - 1)) * 100;
                          const y = 100 - ((p.equilibrium_portfolio_value - minVal) / range) * 90;
                          return `${x}%,${y}%`;
                        }).join(' ');

                        return (
                          <>
                            <polyline
                              fill="none"
                              stroke="var(--text-muted)"
                              strokeWidth="2"
                              strokeDasharray="4,4"
                              points={eqCoords}
                            />
                            <polyline
                              fill="none"
                              stroke="var(--primary)"
                              strokeWidth="2.5"
                              points={blCoords}
                            />
                          </>
                        );
                      })()}
                    </svg>

                    <div style={{ display: 'flex', gap: '16px', justifyContent: 'center', marginTop: '12px', fontSize: '12px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <div style={{ width: '12px', height: '3px', background: 'var(--primary)' }} />
                        <span>Black-Litterman Active Portfolio</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <div style={{ width: '12px', height: '3px', borderTop: '2px dashed var(--text-muted)' }} />
                        <span>Equilibrium Benchmark</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="card empty-state" style={{ padding: '60px 20px', textAlign: 'center' }}>
              <Calendar size={40} style={{ color: 'var(--text-muted)', marginBottom: '16px' }} />
              <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '8px' }}>
                No Backtest Run Yet
              </h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', maxWidth: '420px', margin: '0 auto 20px' }}>
                Select an in-sample training cutoff date and click "Execute Chronological Backtest" to test out-of-sample performance.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
