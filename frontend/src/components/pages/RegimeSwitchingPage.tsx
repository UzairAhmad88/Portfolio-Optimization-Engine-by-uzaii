import React, { useState } from 'react';
import {
  Activity,
  Sliders,
  Play,
  TrendingUp,
  ShieldAlert,
  Info,
  Clock,
  Layers,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { useDataset } from '../../context/DatasetContext';
import type {
  RegimeDetectionRequest,
  RegimeDetectionResponse,
  RegimeBacktestRequest,
  RegimeBacktestResponse,
} from '../../types/api';

type RegimeTab = 'detection' | 'backtest';

export const RegimeSwitchingPage: React.FC = () => {
  const { currentDataset } = useDataset();

  const [activeTab, setActiveTab] = useState<RegimeTab>('detection');

  // ============================================================================
  // Tab 1: Regime Detection State
  // ============================================================================
  const [numRegimes, setNumRegimes] = useState<number>(2);
  const [maxIterations, setMaxIterations] = useState<number>(100);
  const [tolerance, setTolerance] = useState<number>(1e-4);

  const [detectLoading, setDetectLoading] = useState<boolean>(false);
  const [detectError, setDetectError] = useState<string | null>(null);
  const [detectResult, setDetectResult] = useState<RegimeDetectionResponse | null>(null);

  // ============================================================================
  // Tab 2: Walk-Forward Backtest & Volatility Targeting State
  // ============================================================================
  const [targetVolatility, setTargetVolatility] = useState<number>(0.10);
  const [maxLeverage, setMaxLeverage] = useState<number>(1.5);
  const [rebalanceFrequency, setRebalanceFrequency] = useState<'daily' | 'weekly' | 'monthly'>('monthly');
  const [lookbackWindow, setLookbackWindow] = useState<number>(252);
  const [transactionCostBps, setTransactionCostBps] = useState<number>(10.0);

  const [backtestLoading, setBacktestLoading] = useState<boolean>(false);
  const [backtestError, setBacktestError] = useState<string | null>(null);
  const [backtestResult, setBacktestResult] = useState<RegimeBacktestResponse | null>(null);

  // ============================================================================
  // Execution Handlers
  // ============================================================================
  const handleRunDetection = async () => {
    if (!currentDataset) {
      setDetectError('Please select or upload a verified dataset in the Market Data workspace.');
      return;
    }
    setDetectLoading(true);
    setDetectError(null);
    try {
      const payload: RegimeDetectionRequest = {
        dataset_id: currentDataset.dataset_id,
        num_states: numRegimes,
        max_iter: maxIterations,
        tolerance: tolerance,
      };
      const res = await apiClient.detectRegimes(payload);
      setDetectResult(res);
    } catch (err: any) {
      setDetectError(err?.message || 'Failed to execute regime detection.');
    } finally {
      setDetectLoading(false);
    }
  };

  const handleRunBacktest = async () => {
    if (!currentDataset) {
      setBacktestError('Please select or upload a verified dataset in the Market Data workspace.');
      return;
    }
    setBacktestLoading(true);
    setBacktestError(null);
    try {
      const payload: RegimeBacktestRequest = {
        dataset_id: currentDataset.dataset_id,
        num_states: numRegimes,
        target_volatility: targetVolatility,
        max_leverage: maxLeverage,
        rebalance_frequency: rebalanceFrequency,
        lookback_window: lookbackWindow,
        transaction_cost_bps: transactionCostBps,
      };
      const res = await apiClient.backtestRegimes(payload);
      setBacktestResult(res);
    } catch (err: any) {
      setBacktestError(err?.message || 'Failed to execute regime-switching backtest.');
    } finally {
      setBacktestLoading(false);
    }
  };

  const regimeColors = ['#10B981', '#F59E0B', '#EF4444'];

  return (
    <div className="workspace-container">
      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '24px', fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Activity style={{ color: 'var(--accent)' }} size={26} />
            Regime-Switching & Volatility Targeting
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '14px', margin: '4px 0 0' }}>
            Gaussian Hidden Markov Models (HMM), Baum-Welch EM calibration, causal forward-filtered probabilities, regime-conditioned covariance blending, and dynamic volatility targeting overlays.
          </p>
        </div>

        {/* Tab Selector */}
        <div style={{ display: 'flex', gap: '8px', background: 'var(--bg-secondary)', padding: '4px', borderRadius: 'var(--radius-md)' }}>
          <button
            onClick={() => setActiveTab('detection')}
            className={`btn ${activeTab === 'detection' ? 'btn-primary' : 'btn-ghost'}`}
            style={{ fontSize: '13px', padding: '6px 14px' }}
          >
            <Activity size={14} style={{ marginRight: '6px' }} />
            Latent Regime Detection
          </button>
          <button
            onClick={() => setActiveTab('backtest')}
            className={`btn ${activeTab === 'backtest' ? 'btn-primary' : 'btn-ghost'}`}
            style={{ fontSize: '13px', padding: '6px 14px' }}
          >
            <TrendingUp size={14} style={{ marginRight: '6px' }} />
            Volatility Targeting Backtest
          </button>
        </div>
      </div>

      {/* Dataset Warning */}
      {!currentDataset && (
        <div className="alert alert-warning" style={{ marginBottom: '20px' }}>
          <ShieldAlert size={18} />
          <span>No market dataset active. Please select a registered dataset from the Market Data workspace before proceeding.</span>
        </div>
      )}

      {/* ==================================================================== */}
      {/* TAB 1: LATENT REGIME DETECTION                                       */}
      {/* ==================================================================== */}
      {activeTab === 'detection' && (
        <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '24px' }}>
          {/* Controls Column */}
          <div className="card" style={{ height: 'fit-content' }}>
            <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Sliders size={16} style={{ color: 'var(--accent)' }} />
              HMM Specifications
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label className="label">Active Dataset</label>
                <input
                  type="text"
                  disabled
                  value={currentDataset?.filename || 'No dataset loaded'}
                  className="input"
                  style={{ backgroundColor: 'var(--bg-secondary)', cursor: 'not-allowed' }}
                />
              </div>

              <div>
                <label className="label">Number of Latent Regimes (K)</label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                  <button
                    type="button"
                    onClick={() => setNumRegimes(2)}
                    className={`btn ${numRegimes === 2 ? 'btn-primary' : 'btn-secondary'}`}
                    style={{ fontSize: '13px', padding: '8px' }}
                  >
                    2 Regimes (Bull / Bear)
                  </button>
                  <button
                    type="button"
                    onClick={() => setNumRegimes(3)}
                    className={`btn ${numRegimes === 3 ? 'btn-primary' : 'btn-secondary'}`}
                    style={{ fontSize: '13px', padding: '8px' }}
                  >
                    3 Regimes (Normal / High / Crisis)
                  </button>
                </div>
              </div>

              <div>
                <label className="label">Max EM Iterations</label>
                <input
                  type="number"
                  min="10"
                  max="500"
                  value={maxIterations}
                  onChange={(e) => setMaxIterations(Number(e.target.value))}
                  className="input font-mono"
                />
              </div>

              <div>
                <label className="label">Convergence Tolerance</label>
                <select
                  value={tolerance}
                  onChange={(e) => setTolerance(Number(e.target.value))}
                  className="input font-mono"
                >
                  <option value={1e-3}>1e-3 (Fast coarse)</option>
                  <option value={1e-4}>1e-4 (Standard institutional)</option>
                  <option value={1e-6}>1e-6 (High precision)</option>
                </select>
              </div>

              <button
                onClick={handleRunDetection}
                disabled={detectLoading || !currentDataset}
                className="btn btn-primary"
                style={{ width: '100%', marginTop: '8px', justifyContent: 'center' }}
              >
                {detectLoading ? (
                  <>
                    <Clock size={16} className="animate-spin" style={{ marginRight: '8px' }} />
                    Calibrating Baum-Welch EM...
                  </>
                ) : (
                  <>
                    <Play size={16} style={{ marginRight: '8px' }} />
                    Fit Latent HMM & Decoded Path
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Results Column */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {detectError && (
              <div className="alert alert-danger">
                <ShieldAlert size={18} />
                <span>{detectError}</span>
              </div>
            )}

            {detectResult && (
              <>
                {/* Metric Summary Cards */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
                  <div className="metric-card">
                    <div className="metric-label">Current Latent State</div>
                    <div className="metric-value" style={{ color: regimeColors[detectResult.current_state % regimeColors.length] }}>
                      State {detectResult.current_state}
                    </div>
                    <div className="metric-sub">
                      {detectResult.current_state_label}
                    </div>
                  </div>

                  <div className="metric-card">
                    <div className="metric-label">Current State Probability</div>
                    <div className="metric-value font-mono">
                      {(detectResult.current_regime_probabilities[detectResult.current_state] * 100).toFixed(1)}%
                    </div>
                    <div className="metric-sub">Causal filtered probability α̂_T</div>
                  </div>

                  <div className="metric-card">
                    <div className="metric-label">Latent Model Order</div>
                    <div className="metric-value font-mono" style={{ fontSize: '18px' }}>
                      {detectResult.num_states} Regimes
                    </div>
                    <div className="metric-sub">Gaussian emission distributions</div>
                  </div>

                  <div className="metric-card">
                    <div className="metric-label">Total Observations</div>
                    <div className="metric-value font-mono">
                      {detectResult.timeline.length}
                    </div>
                    <div className="metric-sub">Daily return points analyzed</div>
                  </div>
                </div>

                {/* Calibrated Regimes Table */}
                <div className="card">
                  <h4 style={{ fontSize: '15px', fontWeight: 600, marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Layers size={16} style={{ color: 'var(--accent)' }} />
                    Latent Regime Characterization (Sorted by Variance)
                  </h4>
                  <div className="table-container">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>Regime</th>
                          <th>Classification Label</th>
                          <th style={{ textAlign: 'right' }}>Annualized Return</th>
                          <th style={{ textAlign: 'right' }}>Annualized Volatility</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detectResult.state_labels.map((label, idx) => (
                          <tr key={idx}>
                            <td style={{ fontWeight: 600 }}>
                              <span
                                style={{
                                  display: 'inline-block',
                                  width: '10px',
                                  height: '10px',
                                  borderRadius: '50%',
                                  backgroundColor: regimeColors[idx % regimeColors.length],
                                  marginRight: '8px',
                                }}
                              />
                              Regime {idx}
                            </td>
                            <td>
                              <span className="badge" style={{ backgroundColor: 'var(--bg-secondary)', color: 'var(--text-primary)' }}>
                                {label}
                              </span>
                            </td>
                            <td style={{ textAlign: 'right' }} className={`font-mono ${(detectResult.state_means[idx] || 0) >= 0 ? 'text-success' : 'text-danger'}`}>
                              {((detectResult.state_means[idx] || 0) * 252 * 100).toFixed(2)}%
                            </td>
                            <td style={{ textAlign: 'right' }} className="font-mono">
                              {((detectResult.state_volatilities_annual[idx] || 0) * 100).toFixed(2)}%
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Transition Probability Matrix */}
                <div className="card">
                  <h4 style={{ fontSize: '15px', fontWeight: 600, marginBottom: '14px' }}>
                    Regime Transition Probability Matrix A = [P(s_t = j | s_&#123;t-1&#125; = i)]
                  </h4>
                  <div style={{ display: 'grid', gridTemplateColumns: `repeat(${detectResult.num_states}, 1fr)`, gap: '12px' }}>
                    {detectResult.transition_matrix.map((row, i) => (
                      <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)' }}>
                          From Regime {i} ({detectResult.state_labels[i]})
                        </div>
                        {row.map((prob, j) => (
                          <div
                            key={j}
                            style={{
                              padding: '12px',
                              borderRadius: 'var(--radius-sm)',
                              backgroundColor: `rgba(99, 102, 241, ${Math.max(0.08, prob * 0.85)})`,
                              border: '1px solid var(--border)',
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                            }}
                          >
                            <span style={{ fontSize: '12px' }}>To State {j}:</span>
                            <span className="font-mono" style={{ fontWeight: 700 }}>
                              {(prob * 100).toFixed(1)}%
                            </span>
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Interactive State Timeline Visualization (SVG) */}
                <div className="card">
                  <h4 style={{ fontSize: '15px', fontWeight: 600, marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Activity size={16} style={{ color: 'var(--accent)' }} />
                    Historical Causal Filtered Probabilities & Decoded State Path
                  </h4>
                  <div style={{ width: '100%', height: '220px', position: 'relative' }}>
                    <svg width="100%" height="100%" viewBox="0 0 800 200" preserveAspectRatio="none">
                      <line x1="0" y1="50" x2="800" y2="50" stroke="var(--border)" strokeDasharray="3,3" />
                      <line x1="0" y1="100" x2="800" y2="100" stroke="var(--border)" strokeDasharray="3,3" />
                      <line x1="0" y1="150" x2="800" y2="150" stroke="var(--border)" strokeDasharray="3,3" />

                      {/* State 0 Probability Line */}
                      {detectResult.timeline.length > 1 && (
                        <polyline
                          fill="none"
                          stroke={regimeColors[0]}
                          strokeWidth="2"
                          points={detectResult.timeline
                            .map((pt, idx) => {
                              const x = (idx / (detectResult.timeline.length - 1)) * 800;
                              const y = 200 - (pt.filtered_prob[0] || 0) * 180 - 10;
                              return `${x},${y}`;
                            })
                            .join(' ')}
                        />
                      )}

                      {/* State 1 Probability Line */}
                      {detectResult.timeline.length > 1 && (
                        <polyline
                          fill="none"
                          stroke={regimeColors[1]}
                          strokeWidth="2"
                          points={detectResult.timeline
                            .map((pt, idx) => {
                              const x = (idx / (detectResult.timeline.length - 1)) * 800;
                              const y = 200 - (pt.filtered_prob[1] || 0) * 180 - 10;
                              return `${x},${y}`;
                            })
                            .join(' ')}
                        />
                      )}

                      {/* State 2 Probability Line (if 3 regimes) */}
                      {detectResult.num_states === 3 && detectResult.timeline.length > 1 && (
                        <polyline
                          fill="none"
                          stroke={regimeColors[2]}
                          strokeWidth="2"
                          points={detectResult.timeline
                            .map((pt, idx) => {
                              const x = (idx / (detectResult.timeline.length - 1)) * 800;
                              const y = 200 - (pt.filtered_prob[2] || 0) * 180 - 10;
                              return `${x},${y}`;
                            })
                            .join(' ')}
                        />
                      )}
                    </svg>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'center', gap: '20px', marginTop: '12px', fontSize: '12px' }}>
                    {detectResult.state_labels.map((label, idx) => (
                      <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ width: '12px', height: '3px', backgroundColor: regimeColors[idx % regimeColors.length] }} />
                        <span>P(Regime {idx} - {label})</span>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}

            {!detectResult && !detectLoading && !detectError && (
              <div className="card" style={{ textAlign: 'center', padding: '48px 24px', color: 'var(--text-muted)' }}>
                <Activity size={40} style={{ opacity: 0.3, marginBottom: '12px' }} />
                <div style={{ fontWeight: 600, fontSize: '16px', color: 'var(--text-primary)', marginBottom: '4px' }}>
                  Awaiting HMM Specification & Calibration
                </div>
                <div style={{ fontSize: '13px', maxWidth: '420px', margin: '0 auto' }}>
                  Select the number of market regimes and convergence parameters, then click &quot;Fit Latent HMM&quot; to decode regime shifts using the Baum-Welch Expectation-Maximization algorithm.
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* TAB 2: VOLATILITY TARGETING WALK-FORWARD BACKTEST                     */}
      {/* ==================================================================== */}
      {activeTab === 'backtest' && (
        <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '24px' }}>
          {/* Controls Column */}
          <div className="card" style={{ height: 'fit-content' }}>
            <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Sliders size={16} style={{ color: 'var(--accent)' }} />
              Volatility Targeting Overlay
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label className="label">Target Annualized Volatility</label>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <input
                    type="range"
                    min="0.05"
                    max="0.30"
                    step="0.01"
                    value={targetVolatility}
                    onChange={(e) => setTargetVolatility(Number(e.target.value))}
                    style={{ flex: 1 }}
                  />
                  <span className="font-mono" style={{ fontWeight: 600, width: '45px', textAlign: 'right' }}>
                    {(targetVolatility * 100).toFixed(0)}%
                  </span>
                </div>
              </div>

              <div>
                <label className="label">Maximum Leverage Cap</label>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <input
                    type="range"
                    min="1.0"
                    max="2.5"
                    step="0.1"
                    value={maxLeverage}
                    onChange={(e) => setMaxLeverage(Number(e.target.value))}
                    style={{ flex: 1 }}
                  />
                  <span className="font-mono" style={{ fontWeight: 600, width: '45px', textAlign: 'right' }}>
                    {maxLeverage.toFixed(1)}x
                  </span>
                </div>
              </div>

              <div>
                <label className="label">Rebalance Frequency</label>
                <select
                  value={rebalanceFrequency}
                  onChange={(e) => setRebalanceFrequency(e.target.value as any)}
                  className="input"
                >
                  <option value="monthly">Monthly Rebalancing</option>
                  <option value="weekly">Weekly Rebalancing</option>
                  <option value="daily">Daily Rebalancing</option>
                </select>
              </div>

              <div>
                <label className="label">Rolling Estimation Window</label>
                <input
                  type="number"
                  min="60"
                  max="504"
                  value={lookbackWindow}
                  onChange={(e) => setLookbackWindow(Number(e.target.value))}
                  className="input font-mono"
                />
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Trading days for Baum-Welch EM estimation</span>
              </div>

              <div>
                <label className="label">Transaction Cost (bps)</label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={transactionCostBps}
                  onChange={(e) => setTransactionCostBps(Number(e.target.value))}
                  className="input font-mono"
                />
              </div>

              <button
                onClick={handleRunBacktest}
                disabled={backtestLoading || !currentDataset}
                className="btn btn-primary"
                style={{ width: '100%', marginTop: '8px', justifyContent: 'center' }}
              >
                {backtestLoading ? (
                  <>
                    <Clock size={16} className="animate-spin" style={{ marginRight: '8px' }} />
                    Running Walk-Forward Simulation...
                  </>
                ) : (
                  <>
                    <Play size={16} style={{ marginRight: '8px' }} />
                    Run Volatility-Targeted Backtest
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Results Column */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {backtestError && (
              <div className="alert alert-danger">
                <ShieldAlert size={18} />
                <span>{backtestError}</span>
              </div>
            )}

            {backtestResult && (
              <>
                {/* Metric Summary Cards */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px' }}>
                  <div className="metric-card">
                    <div className="metric-label">Strategy CAGR</div>
                    <div className={`metric-value font-mono ${backtestResult.summary.cagr >= 0 ? 'text-success' : 'text-danger'}`}>
                      {(backtestResult.summary.cagr * 100).toFixed(2)}%
                    </div>
                    <div className="metric-sub">
                      Benchmark: {(backtestResult.summary.benchmark_cagr * 100).toFixed(2)}%
                    </div>
                  </div>

                  <div className="metric-card">
                    <div className="metric-label">Realized Volatility</div>
                    <div className="metric-value font-mono" style={{ color: 'var(--accent)' }}>
                      {(backtestResult.summary.annualized_volatility * 100).toFixed(2)}%
                    </div>
                    <div className="metric-sub">
                      Target: {(backtestResult.summary.target_volatility * 100).toFixed(0)}% (Bmk: {(backtestResult.summary.benchmark_volatility * 100).toFixed(2)}%)
                    </div>
                  </div>

                  <div className="metric-card">
                    <div className="metric-label">Sharpe Ratio</div>
                    <div className="metric-value font-mono">
                      {backtestResult.summary.sharpe_ratio.toFixed(2)}
                    </div>
                    <div className="metric-sub">
                      Benchmark: {backtestResult.summary.benchmark_sharpe.toFixed(2)}
                    </div>
                  </div>

                  <div className="metric-card">
                    <div className="metric-label">Max Drawdown</div>
                    <div className="metric-value font-mono text-danger">
                      {(backtestResult.summary.max_drawdown * 100).toFixed(2)}%
                    </div>
                    <div className="metric-sub">
                      Calmar: {backtestResult.summary.calmar_ratio.toFixed(2)}
                    </div>
                  </div>

                  <div className="metric-card">
                    <div className="metric-label">Total Rebalances</div>
                    <div className="metric-value font-mono">
                      {backtestResult.summary.total_rebalances}
                    </div>
                    <div className="metric-sub">
                      Max Leverage Cap: {backtestResult.summary.max_leverage.toFixed(1)}x
                    </div>
                  </div>
                </div>

                {/* Equity Curve SVG */}
                <div className="card">
                  <h4 style={{ fontSize: '15px', fontWeight: 600, marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <TrendingUp size={16} style={{ color: 'var(--accent)' }} />
                    Cumulative Performance: Dynamic Volatility Target Overlay vs Unscaled Benchmark
                  </h4>
                  <div style={{ width: '100%', height: '240px', position: 'relative' }}>
                    <svg width="100%" height="100%" viewBox="0 0 800 240" preserveAspectRatio="none">
                      <line x1="0" y1="60" x2="800" y2="60" stroke="var(--border)" strokeDasharray="3,3" />
                      <line x1="0" y1="120" x2="800" y2="120" stroke="var(--border)" strokeDasharray="3,3" />
                      <line x1="0" y1="180" x2="800" y2="180" stroke="var(--border)" strokeDasharray="3,3" />

                      {/* Benchmark Equity Curve */}
                      {backtestResult.equity_curve.length > 1 && (
                        <polyline
                          fill="none"
                          stroke="var(--text-muted)"
                          strokeWidth="1.5"
                          strokeDasharray="4,4"
                          points={(() => {
                            const maxVal = Math.max(
                              ...backtestResult.equity_curve.map((d) => Math.max(d.portfolio_equity, d.benchmark_equity))
                            );
                            const minVal = Math.min(
                              ...backtestResult.equity_curve.map((d) => Math.min(d.portfolio_equity, d.benchmark_equity))
                            );
                            const range = Math.max(1e-5, maxVal - minVal);
                            return backtestResult.equity_curve
                              .map((pt, idx) => {
                                const x = (idx / (backtestResult.equity_curve.length - 1)) * 800;
                                const y = 230 - ((pt.benchmark_equity - minVal) / range) * 210;
                                return `${x},${y}`;
                              })
                              .join(' ');
                          })()}
                        />
                      )}

                      {/* Strategy Equity Curve */}
                      {backtestResult.equity_curve.length > 1 && (
                        <polyline
                          fill="none"
                          stroke="var(--accent)"
                          strokeWidth="2.5"
                          points={(() => {
                            const maxVal = Math.max(
                              ...backtestResult.equity_curve.map((d) => Math.max(d.portfolio_equity, d.benchmark_equity))
                            );
                            const minVal = Math.min(
                              ...backtestResult.equity_curve.map((d) => Math.min(d.portfolio_equity, d.benchmark_equity))
                            );
                            const range = Math.max(1e-5, maxVal - minVal);
                            return backtestResult.equity_curve
                              .map((pt, idx) => {
                                const x = (idx / (backtestResult.equity_curve.length - 1)) * 800;
                                const y = 230 - ((pt.portfolio_equity - minVal) / range) * 210;
                                return `${x},${y}`;
                              })
                              .join(' ');
                          })()}
                        />
                      )}
                    </svg>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'center', gap: '24px', marginTop: '12px', fontSize: '12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ width: '16px', height: '3px', backgroundColor: 'var(--accent)' }} />
                      <span style={{ fontWeight: 600 }}>Volatility-Targeted Strategy</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ width: '16px', height: '2px', backgroundColor: 'var(--text-muted)', borderBottom: '1px dashed' }} />
                      <span>Unscaled Benchmark Portfolio</span>
                    </div>
                  </div>
                </div>

                {/* Rebalance History Audit Table */}
                <div className="card">
                  <h4 style={{ fontSize: '15px', fontWeight: 600, marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Clock size={16} style={{ color: 'var(--accent)' }} />
                    Walk-Forward Rebalance History & Dynamic Leverage Audit
                  </h4>
                  <div className="table-container" style={{ maxHeight: '280px', overflowY: 'auto' }}>
                    <table className="table">
                      <thead>
                        <tr>
                          <th>Rebalance Date</th>
                          <th>Causal Regime</th>
                          <th style={{ textAlign: 'right' }}>Leverage Multiplier (k_t)</th>
                          <th style={{ textAlign: 'right' }}>Cash / Buffer</th>
                          <th style={{ textAlign: 'right' }}>Turnover</th>
                          <th style={{ textAlign: 'right' }}>Fee Deducted</th>
                        </tr>
                      </thead>
                      <tbody>
                        {backtestResult.rebalance_events.map((reb, idx) => (
                          <tr key={idx}>
                            <td className="font-mono">{reb.date}</td>
                            <td>
                              <span
                                className="badge"
                                style={{
                                  backgroundColor: `rgba(99, 102, 241, 0.15)`,
                                  color: regimeColors[reb.regime_state % regimeColors.length],
                                }}
                              >
                                State {reb.regime_state}
                              </span>
                            </td>
                            <td style={{ textAlign: 'right' }} className="font-mono font-bold">
                              {reb.scaling_factor.toFixed(2)}x
                            </td>
                            <td style={{ textAlign: 'right' }} className="font-mono">
                              {(reb.cash_weight * 100).toFixed(1)}%
                            </td>
                            <td style={{ textAlign: 'right' }} className="font-mono">
                              {(reb.turnover * 100).toFixed(1)}%
                            </td>
                            <td style={{ textAlign: 'right' }} className="font-mono">
                              ${reb.fee_deducted.toFixed(2)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            )}

            {!backtestResult && !backtestLoading && !backtestError && (
              <div className="card" style={{ textAlign: 'center', padding: '48px 24px', color: 'var(--text-muted)' }}>
                <TrendingUp size={40} style={{ opacity: 0.3, marginBottom: '12px' }} />
                <div style={{ fontWeight: 600, fontSize: '16px', color: 'var(--text-primary)', marginBottom: '4px' }}>
                  Awaiting Volatility Targeting Simulation
                </div>
                <div style={{ fontSize: '13px', maxWidth: '420px', margin: '0 auto' }}>
                  Configure your target annualized volatility and maximum leverage, then run the walk-forward simulation to evaluate dynamic risk scaling.
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Governance & Assumptions Notice */}
      <div className="alert alert-info" style={{ marginTop: '24px' }}>
        <Info size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
        <div>
          <div style={{ fontWeight: 600, marginBottom: '4px' }}>Mathematical & Execution Governance</div>
          <div style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            • Strict Zero Look-Ahead Bias: All walk-forward asset allocations are conditioned strictly on causal forward-filtered probabilities α̂_t = P(s_t = k | r_1, ..., r_t). Smoothed probabilities are reserved exclusively for retrospective diagnostic analysis.<br />
            • Label-Switching Invariance: Regimes are deterministically sorted by variance so that State 0 always represents the lowest volatility regime.<br />
            • Volatility Scaling Law: Allocation leverage is bounded by k_t = min(Lev_max, σ_target / σ̂_t). If k_t &lt; 1, the unallocated portion is held in risk-free cash.
          </div>
        </div>
      </div>
    </div>
  );
};
