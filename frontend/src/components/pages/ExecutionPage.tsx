import React, { useState, useEffect } from 'react';
import {
  Gauge,
  Sliders,
  Play,
  TrendingDown,
  Clock,
  DollarSign,
  Activity,
  ShieldAlert,
  Info,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { useDataset } from '../../context/DatasetContext';
import type {
  OptimalExecutionRequest,
  OptimalExecutionResponse,
  RebalanceImpactRequest,
  RebalanceImpactResponse,
} from '../../types/api';

type ExecutionTab = 'almgren_chriss' | 'rebalance_impact';

export const ExecutionPage: React.FC = () => {
  const { currentDataset, availableAssets } = useDataset();

  const [activeTab, setActiveTab] = useState<ExecutionTab>('almgren_chriss');

  // ============================================================================
  // Tab 1: Almgren-Chriss Optimal Trajectory State
  // ============================================================================
  const [orderSize, setOrderSize] = useState<number>(100000);
  const [assetPrice, setAssetPrice] = useState<number>(50.0);
  const [dailyVolume, setDailyVolume] = useState<number>(2000000);
  const [dailyVolatility, setDailyVolatility] = useState<number>(1.50);
  const [bidAskSpread, setBidAskSpread] = useState<number>(0.02);
  const [horizonPeriods, setHorizonPeriods] = useState<number>(10);
  const [tradingHours, setTradingHours] = useState<number>(6.5);
  const [riskAversion, setRiskAversion] = useState<number>(1e-6);

  const [scheduleLoading, setScheduleLoading] = useState<boolean>(false);
  const [scheduleError, setScheduleError] = useState<string | null>(null);
  const [scheduleResult, setScheduleResult] = useState<OptimalExecutionResponse | null>(null);

  // ============================================================================
  // Tab 2: Portfolio Rebalance Market Impact State
  // ============================================================================
  const [portfolioEquity, setPortfolioEquity] = useState<number>(10000000);
  const [executionHorizonDays, setExecutionHorizonDays] = useState<number>(1.0);
  const [impactModel, setImpactModel] = useState<'square_root' | 'linear' | 'fixed_bps'>('square_root');
  const [targetWeights, setTargetWeights] = useState<Record<string, number>>({});
  const [currentWeights, setCurrentWeights] = useState<Record<string, number>>({});

  const [impactLoading, setImpactLoading] = useState<boolean>(false);
  const [impactError, setImpactError] = useState<string | null>(null);
  const [impactResult, setImpactResult] = useState<RebalanceImpactResponse | null>(null);

  // Initialize weights when available assets change
  useEffect(() => {
    if (availableAssets.length > 0) {
      const n = availableAssets.length;
      const initialTarget: Record<string, number> = {};
      const initialCurrent: Record<string, number> = {};

      availableAssets.forEach((a, idx) => {
        initialTarget[a.ticker] = Number((1.0 / n).toFixed(4));
        // Simulate a slight drift for current weights
        const drift = idx % 2 === 0 ? 0.05 : -0.05 / Math.max(1, n - 1);
        initialCurrent[a.ticker] = Math.max(0, Number(((1.0 / n) + drift).toFixed(4)));
      });

      setTargetWeights(initialTarget);
      setCurrentWeights(initialCurrent);
    }
  }, [availableAssets]);

  // Handle Tab 1 Almgren-Chriss Calculation
  const handleCalculateSchedule = async () => {
    setScheduleLoading(true);
    setScheduleError(null);
    try {
      const payload: OptimalExecutionRequest = {
        order_size: orderSize,
        asset_price: assetPrice,
        daily_volume: dailyVolume,
        daily_volatility: dailyVolatility,
        bid_ask_spread: bidAskSpread,
        horizon_periods: horizonPeriods,
        trading_hours: tradingHours,
        risk_aversion: riskAversion,
      };
      const res = await apiClient.getOptimalExecutionSchedule(payload);
      setScheduleResult(res);
    } catch (err: any) {
      setScheduleError(err?.message || 'Failed to compute optimal execution schedule.');
    } finally {
      setScheduleLoading(false);
    }
  };

  // Handle Tab 2 Rebalance Impact Calculation
  const handleCalculateImpact = async () => {
    if (!currentDataset) {
      setImpactError('Please select an active dataset in the header before evaluating rebalance impact.');
      return;
    }

    setImpactLoading(true);
    setImpactError(null);
    try {
      const payload: RebalanceImpactRequest = {
        dataset_id: currentDataset.dataset_id,
        target_weights: targetWeights,
        current_weights: currentWeights,
        portfolio_equity: portfolioEquity,
        execution_horizon_days: executionHorizonDays,
        impact_model: impactModel,
      };
      const res = await apiClient.evaluateRebalanceImpact(payload);
      setImpactResult(res);
    } catch (err: any) {
      setImpactError(err?.message || 'Failed to evaluate portfolio rebalance market impact.');
    } finally {
      setImpactLoading(false);
    }
  };

  // Run default calculation on mount
  useEffect(() => {
    handleCalculateSchedule();
  }, []);

  return (
    <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header and Stage Notice */}
      <div style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
          <div style={{ padding: '10px', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(245, 158, 11, 0.12)', color: '#F59E0B' }}>
            <Gauge size={24} />
          </div>
          <div>
            <h1 style={{ fontSize: '22px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
              Optimal Execution & Market Impact Engine
            </h1>
            <p style={{ margin: 0, fontSize: '13px', color: 'var(--text-secondary)' }}>
              Almgren-Chriss (2000) optimal trade scheduling and non-linear portfolio rebalance market impact modeling under the Square-Root Law.
            </p>
          </div>
        </div>

        {/* Tab Navigation */}
        <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--border-color)', paddingTop: '12px' }}>
          <button
            onClick={() => setActiveTab('almgren_chriss')}
            className={`btn ${activeTab === 'almgren_chriss' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ borderRadius: 'var(--radius-md) var(--radius-md) 0 0', display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            <Clock size={16} />
            <span>1. Almgren-Chriss Trade Scheduling</span>
          </button>
          <button
            onClick={() => setActiveTab('rebalance_impact')}
            className={`btn ${activeTab === 'rebalance_impact' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ borderRadius: 'var(--radius-md) var(--radius-md) 0 0', display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            <TrendingDown size={16} />
            <span>2. Portfolio Rebalance Market Impact</span>
          </button>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* TAB 1: ALMGREN-CHRISS OPTIMAL TRAJECTORY */}
      {/* ========================================================================= */}
      {activeTab === 'almgren_chriss' && (
        <div style={{ display: 'grid', gridTemplateColumns: '360px 1fr', gap: '24px' }}>
          {/* Controls Panel */}
          <div className="card" style={{ padding: '20px', height: 'fit-content' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
              <Sliders size={18} color="var(--primary)" />
              <h3 style={{ fontSize: '15px', fontWeight: 600, margin: 0 }}>Order & Market Parameters</h3>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
                  Total Order Size (Shares)
                </label>
                <input
                  type="number"
                  className="input"
                  value={orderSize}
                  onChange={(e) => setOrderSize(Number(e.target.value))}
                  min={1}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
                    Asset Price ($)
                  </label>
                  <input
                    type="number"
                    className="input"
                    value={assetPrice}
                    onChange={(e) => setAssetPrice(Number(e.target.value))}
                    step="0.5"
                    min={0.1}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
                    Spread ($)
                  </label>
                  <input
                    type="number"
                    className="input"
                    value={bidAskSpread}
                    onChange={(e) => setBidAskSpread(Number(e.target.value))}
                    step="0.01"
                    min={0}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
                    Daily Volume (ADV)
                  </label>
                  <input
                    type="number"
                    className="input"
                    value={dailyVolume}
                    onChange={(e) => setDailyVolume(Number(e.target.value))}
                    min={1000}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
                    Daily Price Vol ($)
                  </label>
                  <input
                    type="number"
                    className="input"
                    value={dailyVolatility}
                    onChange={(e) => setDailyVolatility(Number(e.target.value))}
                    step="0.1"
                    min={0.01}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
                    Intervals (N)
                  </label>
                  <input
                    type="number"
                    className="input"
                    value={horizonPeriods}
                    onChange={(e) => setHorizonPeriods(Number(e.target.value))}
                    min={2}
                    max={50}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
                    Trading Hours
                  </label>
                  <input
                    type="number"
                    className="input"
                    value={tradingHours}
                    onChange={(e) => setTradingHours(Number(e.target.value))}
                    step="0.5"
                    min={1}
                    max={24}
                  />
                </div>
              </div>

              {/* Risk Aversion Slider & Presets */}
              <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <label style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                    Risk Aversion (λ = {riskAversion.toExponential(1)})
                  </label>
                </div>
                <input
                  type="range"
                  min="0"
                  max="0.0001"
                  step="0.000001"
                  value={riskAversion}
                  onChange={(e) => setRiskAversion(Number(e.target.value))}
                  style={{ width: '100%', accentColor: 'var(--primary)' }}
                />

                <div style={{ display: 'flex', gap: '6px', marginTop: '8px' }}>
                  <button
                    type="button"
                    onClick={() => setRiskAversion(0)}
                    className="btn btn-secondary"
                    style={{ fontSize: '11px', padding: '4px 8px', flex: 1 }}
                  >
                    Risk-Neutral (TWAP)
                  </button>
                  <button
                    type="button"
                    onClick={() => setRiskAversion(1e-6)}
                    className="btn btn-secondary"
                    style={{ fontSize: '11px', padding: '4px 8px', flex: 1 }}
                  >
                    Balanced
                  </button>
                  <button
                    type="button"
                    onClick={() => setRiskAversion(2e-5)}
                    className="btn btn-secondary"
                    style={{ fontSize: '11px', padding: '4px 8px', flex: 1 }}
                  >
                    High Urgency
                  </button>
                </div>
              </div>

              <button
                onClick={handleCalculateSchedule}
                disabled={scheduleLoading}
                className="btn btn-primary"
                style={{ width: '100%', marginTop: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}
              >
                <Play size={16} />
                <span>{scheduleLoading ? 'Solving...' : 'Compute Trajectory'}</span>
              </button>
            </div>
          </div>

          {/* Results Area */}
          <div>
            {scheduleError && (
              <div className="alert alert-danger" style={{ marginBottom: '16px' }}>
                <ShieldAlert size={16} />
                <span>{scheduleError}</span>
              </div>
            )}

            {scheduleResult && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                {/* KPI Cards */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '14px' }}>
                  <div className="card" style={{ padding: '14px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                      EXPECTED COST
                    </div>
                    <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--danger)' }}>
                      ${scheduleResult.summary.expected_cost.toLocaleString()}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      {scheduleResult.summary.expected_cost_bps} bps of order
                    </div>
                  </div>

                  <div className="card" style={{ padding: '14px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                      TIMING RISK VOLATILITY
                    </div>
                    <div style={{ fontSize: '20px', fontWeight: 700, color: '#38BDF8' }}>
                      ${scheduleResult.summary.timing_risk_std.toLocaleString()}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      1-sigma price variance
                    </div>
                  </div>

                  <div className="card" style={{ padding: '14px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                      URGENCY (κ) & HALF-LIFE
                    </div>
                    <div style={{ fontSize: '20px', fontWeight: 700, color: '#F59E0B' }}>
                      κ = {scheduleResult.summary.urgency_parameter}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      t½ = {scheduleResult.summary.half_life_hours} hrs
                    </div>
                  </div>

                  <div className="card" style={{ padding: '14px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                      UTILITY BENEFIT VS TWAP
                    </div>
                    <div style={{ fontSize: '20px', fontWeight: 700, color: '#10B981' }}>
                      +${Math.max(0, scheduleResult.summary.cost_savings_vs_twap).toLocaleString()}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      +{Math.max(0, scheduleResult.summary.cost_savings_vs_twap_bps)} bps efficiency
                    </div>
                  </div>
                </div>

                {/* Trajectory SVG Vector Chart */}
                <div className="card" style={{ padding: '20px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Activity size={18} color="var(--primary)" />
                      <h4 style={{ fontSize: '15px', fontWeight: 600, margin: 0 }}>
                        Holdings Execution Trajectory ($x_j$ Remaining Shares)
                      </h4>
                    </div>
                    <div style={{ display: 'flex', gap: '16px', fontSize: '12px' }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ width: '12px', height: '3px', backgroundColor: '#38BDF8', display: 'inline-block' }}></span>
                        Almgren-Chriss Optimal
                      </span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ width: '12px', height: '2px', backgroundColor: '#10B981', borderTop: '2px dashed #10B981', display: 'inline-block' }}></span>
                        TWAP Baseline
                      </span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ width: '12px', height: '2px', backgroundColor: '#F59E0B', borderTop: '2px dotted #F59E0B', display: 'inline-block' }}></span>
                        VWAP Baseline
                      </span>
                    </div>
                  </div>

                  {/* SVG Chart Rendering */}
                  <div style={{ width: '100%', height: '240px', position: 'relative' }}>
                    <svg viewBox="0 0 800 240" style={{ width: '100%', height: '100%', overflow: 'visible' }}>
                      {/* Grid Lines */}
                      {[0, 0.25, 0.5, 0.75, 1.0].map((frac, idx) => {
                        const y = 20 + frac * 190;
                        return (
                          <g key={idx}>
                            <line x1="60" y1={y} x2="780" y2={y} stroke="rgba(255, 255, 255, 0.08)" strokeDasharray="4 4" />
                            <text x="50" y={y + 4} textAnchor="end" fill="var(--text-secondary)" fontSize="10">
                              {Math.round((1.0 - frac) * orderSize).toLocaleString()}
                            </text>
                          </g>
                        );
                      })}

                      {/* X-axis labels */}
                      {scheduleResult.schedule.map((pt, idx) => {
                        const x = 60 + (idx / Math.max(1, scheduleResult.schedule.length - 1)) * 720;
                        return (
                          <text key={idx} x={x} y="230" textAnchor="middle" fill="var(--text-secondary)" fontSize="10">
                            P{pt.period} ({pt.time_elapsed_hours}h)
                          </text>
                        );
                      })}

                      {/* TWAP Path */}
                      <path
                        d={
                          'M 60 20 ' +
                          scheduleResult.schedule
                            .map((pt, idx) => {
                              const x = 60 + (idx / Math.max(1, scheduleResult.schedule.length - 1)) * 720;
                              const y = 20 + (1.0 - pt.twap_remaining / orderSize) * 190;
                              return `L ${x} ${y}`;
                            })
                            .join(' ')
                        }
                        fill="none"
                        stroke="#10B981"
                        strokeWidth="2"
                        strokeDasharray="5 5"
                      />

                      {/* VWAP Path */}
                      <path
                        d={
                          'M 60 20 ' +
                          scheduleResult.schedule
                            .map((pt, idx) => {
                              const x = 60 + (idx / Math.max(1, scheduleResult.schedule.length - 1)) * 720;
                              const y = 20 + (1.0 - pt.vwap_remaining / orderSize) * 190;
                              return `L ${x} ${y}`;
                            })
                            .join(' ')
                        }
                        fill="none"
                        stroke="#F59E0B"
                        strokeWidth="2"
                        strokeDasharray="2 3"
                      />

                      {/* Almgren-Chriss Optimal Path */}
                      <path
                        d={
                          'M 60 20 ' +
                          scheduleResult.schedule
                            .map((pt, idx) => {
                              const x = 60 + (idx / Math.max(1, scheduleResult.schedule.length - 1)) * 720;
                              const y = 20 + (1.0 - pt.almgren_chriss_remaining / orderSize) * 190;
                              return `L ${x} ${y}`;
                            })
                            .join(' ')
                        }
                        fill="none"
                        stroke="#38BDF8"
                        strokeWidth="3"
                      />

                      {/* Data Points */}
                      {scheduleResult.schedule.map((pt, idx) => {
                        const x = 60 + (idx / Math.max(1, scheduleResult.schedule.length - 1)) * 720;
                        const y = 20 + (1.0 - pt.almgren_chriss_remaining / orderSize) * 190;
                        return (
                          <circle
                            key={idx}
                            cx={x}
                            cy={y}
                            r="4"
                            fill="#38BDF8"
                            stroke="#0F172A"
                            strokeWidth="2"
                          />
                        );
                      })}
                    </svg>
                  </div>
                </div>

                {/* Schedule Interval Table */}
                <div className="card" style={{ padding: '20px' }}>
                  <h4 style={{ fontSize: '15px', fontWeight: 600, margin: '0 0 14px 0' }}>
                    Discrete Execution Schedule Breakdown
                  </h4>
                  <div className="table-container" style={{ maxHeight: '280px', overflowY: 'auto' }}>
                    <table className="table" style={{ width: '100%', fontSize: '12px' }}>
                      <thead>
                        <tr>
                          <th>Period</th>
                          <th>Time (Hrs)</th>
                          <th style={{ textAlign: 'right' }}>Optimal Shares</th>
                          <th style={{ textAlign: 'right' }}>Remaining</th>
                          <th style={{ textAlign: 'right' }}>TWAP Shares</th>
                          <th style={{ textAlign: 'right' }}>VWAP Shares</th>
                          <th style={{ textAlign: 'right' }}>Volume Profile</th>
                        </tr>
                      </thead>
                      <tbody>
                        {scheduleResult.schedule.map((pt) => (
                          <tr key={pt.period}>
                            <td style={{ fontWeight: 600 }}>Period {pt.period}</td>
                            <td>{pt.time_elapsed_hours}h ({Math.round(pt.time_elapsed_pct * 100)}%)</td>
                            <td style={{ textAlign: 'right', fontWeight: 700, color: '#38BDF8' }}>
                              {pt.almgren_chriss_shares.toLocaleString()}
                            </td>
                            <td style={{ textAlign: 'right' }}>
                              {pt.almgren_chriss_remaining.toLocaleString()}
                            </td>
                            <td style={{ textAlign: 'right', color: '#10B981' }}>
                              {pt.twap_shares.toLocaleString()}
                            </td>
                            <td style={{ textAlign: 'right', color: '#F59E0B' }}>
                              {pt.vwap_shares.toLocaleString()}
                            </td>
                            <td style={{ textAlign: 'right' }}>
                              {pt.volume_weight_pct}%
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: PORTFOLIO REBALANCE MARKET IMPACT */}
      {/* ========================================================================= */}
      {activeTab === 'rebalance_impact' && (
        <div style={{ display: 'grid', gridTemplateColumns: '380px 1fr', gap: '24px' }}>
          {/* Controls Panel */}
          <div className="card" style={{ padding: '20px', height: 'fit-content' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
              <DollarSign size={18} color="var(--primary)" />
              <h3 style={{ fontSize: '15px', fontWeight: 600, margin: 0 }}>Rebalance Parameters</h3>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
                  Portfolio Equity ($)
                </label>
                <input
                  type="number"
                  className="input"
                  value={portfolioEquity}
                  onChange={(e) => setPortfolioEquity(Number(e.target.value))}
                  step="1000000"
                  min={10000}
                />
              </div>

              <div>
                <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
                  Execution Horizon (Days)
                </label>
                <input
                  type="number"
                  className="input"
                  value={executionHorizonDays}
                  onChange={(e) => setExecutionHorizonDays(Number(e.target.value))}
                  step="0.5"
                  min={0.1}
                  max={20}
                />
              </div>

              <div>
                <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
                  Market Impact Model Archetype
                </label>
                <select
                  className="select"
                  value={impactModel}
                  onChange={(e) => setImpactModel(e.target.value as any)}
                >
                  <option value="square_root">Square-Root Law (Barra / Almgren et al.)</option>
                  <option value="linear">Linear Market Impact (Kyle Lambda)</option>
                  <option value="fixed_bps">Fixed Basis-Point Fee Baseline</option>
                </select>
              </div>

              {/* Target Allocation Weights */}
              <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '12px' }}>
                <h4 style={{ fontSize: '13px', fontWeight: 600, margin: '0 0 8px 0' }}>Target Asset Allocations</h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '220px', overflowY: 'auto' }}>
                  {availableAssets.map((a) => (
                    <div key={a.ticker} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
                      <span style={{ fontSize: '12px', fontWeight: 600, width: '70px' }}>{a.ticker}</span>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Target:</span>
                        <input
                          type="number"
                          className="input"
                          style={{ width: '75px', padding: '4px 8px', fontSize: '12px' }}
                          value={targetWeights[a.ticker] ?? 0}
                          onChange={(e) =>
                            setTargetWeights({ ...targetWeights, [a.ticker]: Number(e.target.value) })
                          }
                          step="0.05"
                          min={0}
                          max={1}
                        />
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Curr:</span>
                        <input
                          type="number"
                          className="input"
                          style={{ width: '75px', padding: '4px 8px', fontSize: '12px' }}
                          value={currentWeights[a.ticker] ?? 0}
                          onChange={(e) =>
                            setCurrentWeights({ ...currentWeights, [a.ticker]: Number(e.target.value) })
                          }
                          step="0.05"
                          min={0}
                          max={1}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <button
                onClick={handleCalculateImpact}
                disabled={impactLoading}
                className="btn btn-primary"
                style={{ width: '100%', marginTop: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}
              >
                <Play size={16} />
                <span>{impactLoading ? 'Evaluating...' : 'Evaluate Rebalance Impact'}</span>
              </button>
            </div>
          </div>

          {/* Results Area */}
          <div>
            {impactError && (
              <div className="alert alert-danger" style={{ marginBottom: '16px' }}>
                <ShieldAlert size={16} />
                <span>{impactError}</span>
              </div>
            )}

            {impactResult && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                {/* KPI Cards */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '14px' }}>
                  <div className="card" style={{ padding: '14px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                      TRADED NOTIONAL
                    </div>
                    <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)' }}>
                      ${impactResult.summary.total_traded_notional.toLocaleString()}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      Total rebalance volume
                    </div>
                  </div>

                  <div className="card" style={{ padding: '14px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                      EFFECTIVE COST (BPS)
                    </div>
                    <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--danger)' }}>
                      {impactResult.summary.effective_cost_bps} bps
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      Total friction drag
                    </div>
                  </div>

                  <div className="card" style={{ padding: '14px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                      TEMP IMPACT COST
                    </div>
                    <div style={{ fontSize: '20px', fontWeight: 700, color: '#F59E0B' }}>
                      ${impactResult.summary.total_temporary_impact_cost.toLocaleString()}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      Transient book depletion
                    </div>
                  </div>

                  <div className="card" style={{ padding: '14px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                      TOTAL IMPACT COST
                    </div>
                    <div style={{ fontSize: '20px', fontWeight: 700, color: '#EF4444' }}>
                      ${impactResult.summary.total_impact_cost.toLocaleString()}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      Spread + Temp + Perm
                    </div>
                  </div>
                </div>

                {/* Per-Asset Impact Table */}
                <div className="card" style={{ padding: '20px' }}>
                  <h4 style={{ fontSize: '15px', fontWeight: 600, margin: '0 0 14px 0' }}>
                    Asset-Level Market Impact & Liquidity Breakdown
                  </h4>
                  <div className="table-container" style={{ maxHeight: '350px', overflowY: 'auto' }}>
                    <table className="table" style={{ width: '100%', fontSize: '12px' }}>
                      <thead>
                        <tr>
                          <th>Ticker</th>
                          <th style={{ textAlign: 'right' }}>Traded Value</th>
                          <th style={{ textAlign: 'right' }}>Estimated ADV</th>
                          <th style={{ textAlign: 'right' }}>ADV Participation</th>
                          <th style={{ textAlign: 'right' }}>Spread Cost</th>
                          <th style={{ textAlign: 'right' }}>Temp Impact</th>
                          <th style={{ textAlign: 'right' }}>Perm Impact</th>
                          <th style={{ textAlign: 'right' }}>Total Cost</th>
                          <th style={{ textAlign: 'right' }}>Cost (BPS)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {impactResult.asset_impacts.map((item) => (
                          <tr key={item.ticker}>
                            <td style={{ fontWeight: 700 }}>{item.ticker}</td>
                            <td style={{ textAlign: 'right', fontWeight: 600 }}>
                              ${item.traded_notional.toLocaleString()}
                            </td>
                            <td style={{ textAlign: 'right' }}>
                              ${item.adv.toLocaleString()}
                            </td>
                            <td style={{ textAlign: 'right' }}>
                              <span
                                style={{
                                  padding: '2px 6px',
                                  borderRadius: '4px',
                                  backgroundColor:
                                    item.participation_rate_pct > 20
                                      ? 'rgba(239, 68, 68, 0.15)'
                                      : 'rgba(56, 189, 248, 0.15)',
                                  color:
                                    item.participation_rate_pct > 20
                                      ? '#EF4444'
                                      : '#38BDF8',
                                  fontWeight: 600,
                                }}
                              >
                                {item.participation_rate_pct}%
                              </span>
                            </td>
                            <td style={{ textAlign: 'right' }}>${item.spread_cost.toLocaleString()}</td>
                            <td style={{ textAlign: 'right', color: '#F59E0B' }}>
                              ${item.temporary_impact_cost.toLocaleString()}
                            </td>
                            <td style={{ textAlign: 'right', color: '#818CF8' }}>
                              ${item.permanent_impact_cost.toLocaleString()}
                            </td>
                            <td style={{ textAlign: 'right', fontWeight: 700, color: 'var(--danger)' }}>
                              ${item.total_cost.toLocaleString()}
                            </td>
                            <td style={{ textAlign: 'right', fontWeight: 700 }}>
                              {item.total_cost_bps} bps
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {!impactResult && !impactLoading && (
              <div className="card" style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                <Info size={32} style={{ margin: '0 auto 12px auto', opacity: 0.5 }} />
                <div style={{ fontWeight: 600, fontSize: '15px', marginBottom: '6px' }}>
                  No Rebalance Impact Evaluated Yet
                </div>
                <div style={{ fontSize: '13px' }}>
                  Configure portfolio equity, execution horizon, and asset targets, then click "Evaluate Rebalance Impact".
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
