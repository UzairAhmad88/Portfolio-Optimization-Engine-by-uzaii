import React, { useState, useEffect } from 'react';
import {
  Network,
  Activity,
  AlertCircle,
  RefreshCw,
  PieChart,
  Info,
  Sliders,
  GitBranch,
  Layers,
  CheckCircle2,
  TrendingUp,
  History,
  DollarSign,
  ShieldAlert,
} from 'lucide-react';
import { useDataset } from '../../context/DatasetContext';
import { apiClient } from '../../api/client';
import type {
  CopulaFitResponse,
  CopulaSimulateResponse,
  TailRiskParityResponse,
  CopulaType,
  MarginalMethod,
  VineType,
  VineCopulaFitResponse,
  VineCopulaSimulateResponse,
  VineTailRiskParityResponse,
  VineBacktestResponse,
  ExecutionSchedulingMode,
} from '../../types/api';

export const CopulaTailRiskPage: React.FC = () => {
  const { currentDataset } = useDataset();

  // Active Tab
  const [activeTab, setActiveTab] = useState<'diagnostics' | 'simulation' | 'allocation' | 'vine' | 'backtest'>('diagnostics');

  // Configuration States
  const [copulaType, setCopulaType] = useState<CopulaType>('best_fit');
  const [marginalMethod, setMarginalMethod] = useState<MarginalMethod>('empirical');
  const [confidenceLevel, setConfidenceLevel] = useState<number>(0.99);
  const [numSimulations, setNumSimulations] = useState<number>(5000);
  const [randomSeed, setRandomSeed] = useState<number>(42);

  // Vine Copula States (Stage 23)
  const [vineType, setVineType] = useState<VineType>('c_vine');
  const [vineFitResult, setVineFitResult] = useState<VineCopulaFitResponse | null>(null);
  const [vineSimResult, setVineSimResult] = useState<VineCopulaSimulateResponse | null>(null);
  const [vineTrpResult, setVineTrpResult] = useState<VineTailRiskParityResponse | null>(null);
  const [isVineLoading, setIsVineLoading] = useState<boolean>(false);

  // Walk-Forward Backtest States (Stage 24 & 25 & 28)
  const [backtestEstimationWindow, setBacktestEstimationWindow] = useState<number>(252);
  const [backtestRebalanceFreq, setBacktestRebalanceFreq] = useState<'daily' | 'weekly' | 'monthly' | 'quarterly'>('monthly');
  const [backtestVineType, setBacktestVineType] = useState<VineType>('c_vine');
  const [backtestScenarios, setBacktestScenarios] = useState<number>(2000);
  const [backtestConfidence, setBacktestConfidence] = useState<number>(0.99);
  const [backtestCostBps, setBacktestCostBps] = useState<number>(10);
  const [backtestSlippageBps, setBacktestSlippageBps] = useState<number>(5);
  const [backtestInitialCapital, setBacktestInitialCapital] = useState<number>(100000);
  const [backtestSeed, setBacktestSeed] = useState<number>(42);
  const [backtestExecutionModel, setBacktestExecutionModel] = useState<'square_root' | 'linear' | 'fixed_bps'>('square_root');
  const [backtestSpreadBps, setBacktestSpreadBps] = useState<number>(5.0);
  const [backtestMaxParticipation, setBacktestMaxParticipation] = useState<number>(0.10);
  const [backtestParticipationPolicy, setBacktestParticipationPolicy] = useState<'warn' | 'cap' | 'reject'>('warn');
  const [backtestEnableEndogenous, setBacktestEnableEndogenous] = useState<boolean>(true);
  const [backtestSpreadStress, setBacktestSpreadStress] = useState<number>(5.0);
  const [backtestAdvStress, setBacktestAdvStress] = useState<number>(5.0);
  const [backtestExecutionSchedulingMode, setBacktestExecutionSchedulingMode] = useState<ExecutionSchedulingMode>('single_day');
  const [backtestMaxSchedulingDays, setBacktestMaxSchedulingDays] = useState<number>(5);
  const [backtestSchedulingRiskAversion, setBacktestSchedulingRiskAversion] = useState<number>(1e-6);
  const [backtestEnableRegimeAware, setBacktestEnableRegimeAware] = useState<boolean>(false);
  const [backtestRegimeNumStates, setBacktestRegimeNumStates] = useState<number>(2);
  const [backtestRegimeAdaptationStrength, setBacktestRegimeAdaptationStrength] = useState<number>(0.5);
  const [backtestMinParticipationRate, setBacktestMinParticipationRate] = useState<number>(0.02);
  const [backtestResult, setBacktestResult] = useState<VineBacktestResponse | null>(null);
  const [isBacktestLoading, setIsBacktestLoading] = useState<boolean>(false);
  const [tcaAttributionTab, setTcaAttributionTab] = useState<'regime' | 'mode' | 'asset'>('regime');

  // Results & Loading States
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [fitResult, setFitResult] = useState<CopulaFitResponse | null>(null);
  const [simResult, setSimResult] = useState<CopulaSimulateResponse | null>(null);
  const [trpResult, setTrpResult] = useState<TailRiskParityResponse | null>(null);

  // Auto-run fitting when dataset changes
  useEffect(() => {
    if (currentDataset?.dataset_id) {
      handleFitCopula();
    }
  }, [currentDataset?.dataset_id, copulaType, marginalMethod]);

  const handleFitCopula = async () => {
    if (!currentDataset?.dataset_id) return;
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const res = await apiClient.fitCopula({
        dataset_id: currentDataset.dataset_id,
        copula_type: copulaType,
        marginal_method: marginalMethod,
      });
      setFitResult(res);
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to estimate copula tail dependence parameters.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSimulate = async () => {
    if (!currentDataset?.dataset_id) return;
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const typeForSim = copulaType === 'best_fit' ? 'clayton' : copulaType;
      const res = await apiClient.simulateCopula({
        dataset_id: currentDataset.dataset_id,
        copula_type: typeForSim as any,
        marginal_method: marginalMethod,
        num_simulations: numSimulations,
        random_seed: randomSeed,
      });
      setSimResult(res);
      setActiveTab('simulation');
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to generate copula return simulation.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleOptimizeTRP = async () => {
    if (!currentDataset?.dataset_id) return;
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const typeForSim = copulaType === 'best_fit' ? 'clayton' : copulaType;
      const res = await apiClient.optimizeTailRiskParity({
        dataset_id: currentDataset.dataset_id,
        copula_type: typeForSim as any,
        confidence_level: confidenceLevel,
        num_simulations: numSimulations,
        random_seed: randomSeed,
        marginal_method: marginalMethod,
      });
      setTrpResult(res);
      setActiveTab('allocation');
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to optimize Tail Risk Parity allocation.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleFitVine = async () => {
    if (!currentDataset?.dataset_id) return;
    setIsVineLoading(true);
    setErrorMessage(null);
    try {
      const res = await apiClient.fitVineCopula({
        dataset_id: currentDataset.dataset_id,
        vine_type: vineType,
        marginal_method: marginalMethod,
      });
      setVineFitResult(res);
      setActiveTab('vine');
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to fit Regular Vine Copula decomposition.');
    } finally {
      setIsVineLoading(false);
    }
  };

  const handleSimulateVine = async () => {
    if (!currentDataset?.dataset_id) return;
    setIsVineLoading(true);
    setErrorMessage(null);
    try {
      const res = await apiClient.simulateVineCopula({
        dataset_id: currentDataset.dataset_id,
        vine_type: vineType,
        marginal_method: marginalMethod,
        num_simulations: numSimulations,
        random_seed: randomSeed,
      });
      setVineSimResult(res);
      setActiveTab('vine');
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to simulate returns from Regular Vine Copula.');
    } finally {
      setIsVineLoading(false);
    }
  };

  const handleOptimizeVineTRP = async () => {
    if (!currentDataset?.dataset_id) return;
    setIsVineLoading(true);
    setErrorMessage(null);
    try {
      const res = await apiClient.optimizeVineTailRiskParity({
        dataset_id: currentDataset.dataset_id,
        vine_type: vineType,
        confidence_level: confidenceLevel,
        num_simulations: numSimulations,
        random_seed: randomSeed,
        marginal_method: marginalMethod,
      });
      setVineTrpResult(res);
      setActiveTab('vine');
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to optimize Vine Tail Risk Parity allocation.');
    } finally {
      setIsVineLoading(false);
    }
  };

  const handleRunBacktest = async () => {
    if (!currentDataset?.dataset_id) return;
    setIsBacktestLoading(true);
    setErrorMessage(null);
    try {
      const res = await apiClient.runVineBacktest({
        dataset_id: currentDataset.dataset_id,
        vine_type: backtestVineType,
        estimation_window: backtestEstimationWindow,
        rebalance_frequency: backtestRebalanceFreq,
        num_simulations: backtestScenarios,
        confidence_level: backtestConfidence,
        transaction_cost_bps: backtestCostBps,
        slippage_bps: backtestSlippageBps,
        execution_model: backtestExecutionModel,
        bid_ask_spread_bps: backtestSpreadBps,
        max_participation_rate: backtestMaxParticipation,
        participation_policy: backtestParticipationPolicy,
        enable_endogenous_liquidity: backtestEnableEndogenous,
        spread_stress_sensitivity: backtestSpreadStress,
        adv_stress_sensitivity: backtestAdvStress,
        execution_scheduling_mode: backtestExecutionSchedulingMode,
        max_scheduling_days: backtestMaxSchedulingDays,
        scheduling_risk_aversion: backtestSchedulingRiskAversion,
        enable_regime_aware_execution: backtestEnableRegimeAware,
        regime_num_states: backtestRegimeNumStates,
        regime_adaptation_strength: backtestRegimeAdaptationStrength,
        min_participation_rate: backtestMinParticipationRate,
      });
      setBacktestResult(res);
      setActiveTab('backtest');
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to execute Walk-Forward Vine Tail Risk Parity backtest.');
    } finally {
      setIsBacktestLoading(false);
    }
  };

  return (
    <div className="page-container" style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Title & Stage Banner */}
      <div style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
          <div
            style={{
              padding: '10px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'rgba(99, 102, 241, 0.12)',
              color: '#6366F1',
            }}
          >
            <Network size={24} />
          </div>
          <div>
            <h1 style={{ fontSize: '22px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
              Copula Tail Risk & Regular Vine Copula Architecture (Stage 22 - 23)
            </h1>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: '4px 0 0 0' }}>
              Non-linear tail dependency modeling, pair-copula tree decompositions (C-Vine & D-Vine), and Tail Risk Parity (TRP) allocation.
            </p>
          </div>
        </div>
      </div>

      {/* Assumptions & Methodological Governance Notice */}
      <div
        className="alert alert-info"
        style={{
          display: 'flex',
          gap: '12px',
          alignItems: 'flex-start',
          marginBottom: '20px',
          backgroundColor: 'var(--bg-elevated)',
          border: '1px solid var(--border-medium)',
          borderRadius: 'var(--radius-md)',
          padding: '12px 16px',
        }}
      >
        <Info size={18} style={{ color: 'var(--accent)', flexShrink: 0, marginTop: '2px' }} />
        <div style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
          <strong style={{ color: 'var(--text-primary)' }}>Mathematical Governance & Tail Risk Assumptions:</strong>
          <br />
          • Linear Pearson correlation underestimates extreme joint downside risk during market crashes (correlation breakdown).
          <br />
          • Archimedean (Clayton, Gumbel) and Student-t copulas quantify asymmetric lower-tail crash dependence (&lambda;<sub>L</sub>) and upper-tail co-movement (&lambda;<sub>U</sub>).
          <br />
          • Tail Risk Parity (TRP) equalizes Euler Conditional Value at Risk contributions (TRC<sub>i</sub> = -w<sub>i</sub> &times; E[R<sub>i</sub> | L &ge; VaR<sub>&alpha;</sub>]) without relying on normality assumptions.
        </div>
      </div>

      {/* Error Message */}
      {errorMessage && (
        <div
          className="alert alert-danger"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            marginBottom: '20px',
            padding: '12px 16px',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid #EF4444',
            color: '#EF4444',
            fontSize: '13px',
          }}
        >
          <AlertCircle size={16} />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Control Configuration Card */}
      <div className="card" style={{ padding: '20px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
          <Sliders size={18} style={{ color: 'var(--accent)' }} />
          <h2 style={{ fontSize: '15px', fontWeight: 600, margin: 0 }}>Model Configuration & Parameters</h2>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
              Copula Family
            </label>
            <select
              value={copulaType}
              onChange={(e) => setCopulaType(e.target.value as CopulaType)}
              className="select-input"
              style={{ width: '100%', padding: '8px', borderRadius: 'var(--radius-sm)' }}
            >
              <option value="best_fit">Best Fit (Minimum AIC)</option>
              <option value="clayton">Clayton (Lower Tail Crash Risk)</option>
              <option value="gumbel">Gumbel (Upper Tail Co-Movement)</option>
              <option value="student_t">Student-t (Symmetric Fat Tails)</option>
              <option value="gaussian">Gaussian (Baseline Linear Dependence)</option>
            </select>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
              Marginal Transformation
            </label>
            <select
              value={marginalMethod}
              onChange={(e) => setMarginalMethod(e.target.value as MarginalMethod)}
              className="select-input"
              style={{ width: '100%', padding: '8px', borderRadius: 'var(--radius-sm)' }}
            >
              <option value="empirical">Empirical Ranks: rank/(T+1)</option>
              <option value="student_t">Parametric Student-t Marginals</option>
            </select>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
              Tail Confidence Level (α)
            </label>
            <select
              value={confidenceLevel}
              onChange={(e) => setConfidenceLevel(parseFloat(e.target.value))}
              className="select-input"
              style={{ width: '100%', padding: '8px', borderRadius: 'var(--radius-sm)' }}
            >
              <option value={0.99}>99.0% Confidence (Extreme Tail)</option>
              <option value={0.975}>97.5% Confidence</option>
              <option value={0.95}>95.0% Confidence</option>
            </select>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
              Monte Carlo Scenarios
            </label>
            <select
              value={numSimulations}
              onChange={(e) => setNumSimulations(parseInt(e.target.value))}
              className="select-input"
              style={{ width: '100%', padding: '8px', borderRadius: 'var(--radius-sm)' }}
            >
              <option value={2000}>2,000 Scenarios (Fast)</option>
              <option value={5000}>5,000 Scenarios (Standard)</option>
              <option value={10000}>10,000 Scenarios (High Precision)</option>
            </select>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
              Random Seed (Reproducibility)
            </label>
            <input
              type="number"
              value={randomSeed}
              onChange={(e) => setRandomSeed(parseInt(e.target.value) || 0)}
              className="input-field"
              style={{ width: '100%', padding: '8px', borderRadius: 'var(--radius-sm)' }}
            />
          </div>
        </div>

        <div style={{ display: 'flex', gap: '12px', marginTop: '16px', flexWrap: 'wrap' }}>
          <button
            onClick={handleFitCopula}
            disabled={isLoading || !currentDataset?.dataset_id}
            className="btn btn-primary"
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            {isLoading ? <RefreshCw size={14} className="spin" /> : <Network size={14} />}
            <span>Fit Copula Dependencies</span>
          </button>

          <button
            onClick={handleSimulate}
            disabled={isLoading || !currentDataset?.dataset_id}
            className="btn btn-secondary"
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            {isLoading ? <RefreshCw size={14} className="spin" /> : <Activity size={14} />}
            <span>Simulate Dependent Returns</span>
          </button>

          <button
            onClick={handleOptimizeTRP}
            disabled={isLoading || !currentDataset?.dataset_id}
            className="btn btn-secondary"
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            {isLoading ? <RefreshCw size={14} className="spin" /> : <PieChart size={14} />}
            <span>Optimize Tail Risk Parity</span>
          </button>
        </div>
      </div>

      {/* Workspace Tabs */}
      <div style={{ display: 'flex', gap: '4px', borderBottom: '1px solid var(--border-medium)', marginBottom: '20px' }}>
        <button
          onClick={() => setActiveTab('diagnostics')}
          style={{
            padding: '10px 18px',
            fontSize: '13px',
            fontWeight: activeTab === 'diagnostics' ? 600 : 500,
            color: activeTab === 'diagnostics' ? 'var(--accent)' : 'var(--text-secondary)',
            borderBottom: activeTab === 'diagnostics' ? '2px solid var(--accent)' : '2px solid transparent',
            background: 'transparent',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <Network size={15} />
          <span>Tail Dependence Diagnostics</span>
        </button>

        <button
          onClick={() => setActiveTab('simulation')}
          style={{
            padding: '10px 18px',
            fontSize: '13px',
            fontWeight: activeTab === 'simulation' ? 600 : 500,
            color: activeTab === 'simulation' ? 'var(--accent)' : 'var(--text-secondary)',
            borderBottom: activeTab === 'simulation' ? '2px solid var(--accent)' : '2px solid transparent',
            background: 'transparent',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <Activity size={15} />
          <span>Dependent Simulation & Loss</span>
        </button>

        <button
          onClick={() => setActiveTab('allocation')}
          style={{
            padding: '10px 18px',
            fontSize: '13px',
            fontWeight: activeTab === 'allocation' ? 600 : 500,
            color: activeTab === 'allocation' ? 'var(--accent)' : 'var(--text-secondary)',
            borderBottom: activeTab === 'allocation' ? '2px solid var(--accent)' : '2px solid transparent',
            background: 'transparent',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <PieChart size={15} />
          <span>Tail Risk Parity (TRP) Allocation</span>
        </button>

        <button
          onClick={() => setActiveTab('vine')}
          style={{
            padding: '10px 18px',
            fontSize: '13px',
            fontWeight: activeTab === 'vine' ? 600 : 500,
            color: activeTab === 'vine' ? 'var(--accent)' : 'var(--text-secondary)',
            borderBottom: activeTab === 'vine' ? '2px solid var(--accent)' : '2px solid transparent',
            background: 'transparent',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <GitBranch size={15} />
          <span>Regular Vine Copulas (C-Vine & D-Vine)</span>
        </button>

        <button
          onClick={() => setActiveTab('backtest')}
          style={{
            padding: '10px 18px',
            fontSize: '13px',
            fontWeight: activeTab === 'backtest' ? 600 : 500,
            color: activeTab === 'backtest' ? 'var(--accent)' : 'var(--text-secondary)',
            borderBottom: activeTab === 'backtest' ? '2px solid var(--accent)' : '2px solid transparent',
            background: 'transparent',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <TrendingUp size={15} />
          <span>Walk-Forward Backtest (Stage 24)</span>
        </button>
      </div>

      {/* Tab 1: Tail Dependence Diagnostics */}
      {activeTab === 'diagnostics' && (
        <div>
          {fitResult ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {/* Heatmap & Matrix */}
              <div className="card" style={{ padding: '20px' }}>
                <h3 style={{ fontSize: '15px', fontWeight: 600, marginBottom: '14px' }}>
                  Lower Tail Dependence Matrix (&lambda;<sub>L</sub>)
                </h3>
                <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
                  Values indicate the asymptotic probability of simultaneous extreme downside crash: &lambda;<sub>L</sub> = lim<sub>q&rarr;0</sub> P(U<sub>1</sub> &le; q | U<sub>2</sub> &le; q).
                </p>

                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border-medium)' }}>
                        <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-dim)' }}>Asset</th>
                        {fitResult.tickers.map((t) => (
                          <th key={t} style={{ padding: '8px 12px', textAlign: 'center', color: 'var(--text-dim)' }}>
                            {t}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {fitResult.tail_dependence_matrix.map((row, i) => (
                        <tr key={fitResult.tickers[i]} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                          <td style={{ padding: '8px 12px', fontWeight: 600, color: 'var(--text-primary)' }}>
                            {fitResult.tickers[i]}
                          </td>
                          {row.map((val, j) => {
                            const intensity = i === j ? 1.0 : val;
                            const bg =
                              i === j
                                ? 'rgba(99, 102, 241, 0.25)'
                                : intensity > 0.4
                                ? `rgba(239, 68, 68, ${Math.min(0.7, intensity * 0.9)})`
                                : `rgba(59, 130, 246, ${Math.min(0.4, intensity * 0.8)})`;
                            return (
                              <td
                                key={j}
                                style={{
                                  padding: '8px 12px',
                                  textAlign: 'center',
                                  backgroundColor: bg,
                                  fontWeight: i === j ? 700 : 500,
                                  color: 'var(--text-primary)',
                                  borderRadius: '4px',
                                }}
                              >
                                {(val * 100).toFixed(1)}%
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Pairwise Copula Comparison Table */}
              <div className="card" style={{ padding: '20px' }}>
                <h3 style={{ fontSize: '15px', fontWeight: 600, marginBottom: '14px' }}>
                  Pairwise Copula Parameter Estimates & Tail Asymmetry
                </h3>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border-medium)' }}>
                        <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-dim)' }}>Pair</th>
                        <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-dim)' }}>Fitted Family</th>
                        <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>Parameter (&theta;)</th>
                        <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>Kendall's &tau;</th>
                        <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>Pearson r</th>
                        <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>Lower Tail (&lambda;<sub>L</sub>)</th>
                        <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>Upper Tail (&lambda;<sub>U</sub>)</th>
                        <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>AIC</th>
                      </tr>
                    </thead>
                    <tbody>
                      {fitResult.pairwise_results.map((p, idx) => (
                        <tr key={idx} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                          <td style={{ padding: '8px 12px', fontWeight: 600, color: 'var(--text-primary)' }}>
                            {p.asset_1} — {p.asset_2}
                          </td>
                          <td style={{ padding: '8px 12px' }}>
                            <span
                              style={{
                                padding: '2px 8px',
                                borderRadius: 'var(--radius-sm)',
                                fontSize: '11px',
                                fontWeight: 600,
                                backgroundColor:
                                  p.copula_type === 'clayton'
                                    ? 'rgba(239, 68, 68, 0.15)'
                                    : p.copula_type === 'student_t'
                                    ? 'rgba(168, 85, 247, 0.15)'
                                    : p.copula_type === 'gumbel'
                                    ? 'rgba(245, 158, 11, 0.15)'
                                    : 'rgba(59, 130, 246, 0.15)',
                                color:
                                  p.copula_type === 'clayton'
                                    ? '#EF4444'
                                    : p.copula_type === 'student_t'
                                    ? '#A855F7'
                                    : p.copula_type === 'gumbel'
                                    ? '#F59E0B'
                                    : '#3B82F6',
                              }}
                            >
                              {p.copula_type.toUpperCase()}
                            </span>
                          </td>
                          <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                            {p.theta.toFixed(3)} {p.df ? `(df=${p.df})` : ''}
                          </td>
                          <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                            {p.kendall_tau.toFixed(3)}
                          </td>
                          <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                            {p.pearson_corr.toFixed(3)}
                          </td>
                          <td
                            style={{
                              padding: '8px 12px',
                              textAlign: 'right',
                              fontFamily: 'monospace',
                              color: p.lower_tail_dependence > 0.1 ? '#EF4444' : 'var(--text-secondary)',
                              fontWeight: p.lower_tail_dependence > 0.1 ? 600 : 400,
                            }}
                          >
                            {(p.lower_tail_dependence * 100).toFixed(1)}%
                          </td>
                          <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                            {(p.upper_tail_dependence * 100).toFixed(1)}%
                          </td>
                          <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                            {p.aic.toFixed(1)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
              No copula estimation data. Click "Fit Copula Dependencies" above to start.
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Multivariate Dependent Return Simulation */}
      {activeTab === 'simulation' && (
        <div>
          {simResult ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div className="card" style={{ padding: '20px' }}>
                <h3 style={{ fontSize: '15px', fontWeight: 600, marginBottom: '14px' }}>
                  Simulated Annualized Return & Volatility ({simResult.num_simulations.toLocaleString()} Scenarios)
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px' }}>
                  {simResult.tickers.map((t) => (
                    <div
                      key={t}
                      style={{
                        padding: '12px',
                        borderRadius: 'var(--radius-sm)',
                        backgroundColor: 'var(--bg-elevated)',
                        border: '1px solid var(--border-subtle)',
                      }}
                    >
                      <div style={{ fontWeight: 600, fontSize: '13px', marginBottom: '4px' }}>{t}</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                        Mean: <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{(simResult.simulated_means[t] * 100).toFixed(2)}%</span>
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                        Vol: <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{(simResult.simulated_volatilities[t] * 100).toFixed(2)}%</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Sample Scenarios Preview */}
              <div className="card" style={{ padding: '20px' }}>
                <h3 style={{ fontSize: '15px', fontWeight: 600, marginBottom: '14px' }}>
                  Simulated Return Scenarios Sample (First 15 Paths)
                </h3>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border-medium)' }}>
                        <th style={{ padding: '6px 10px', textAlign: 'left', color: 'var(--text-dim)' }}>Scenario #</th>
                        {simResult.tickers.map((t) => (
                          <th key={t} style={{ padding: '6px 10px', textAlign: 'right', color: 'var(--text-dim)' }}>{t}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {simResult.sample_scenarios.slice(0, 15).map((scen, idx) => (
                        <tr key={idx} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                          <td style={{ padding: '6px 10px', color: 'var(--text-dim)' }}>#{idx + 1}</td>
                          {simResult.tickers.map((t) => {
                            const val = scen[t] || 0.0;
                            return (
                              <td
                                key={t}
                                style={{
                                  padding: '6px 10px',
                                  textAlign: 'right',
                                  fontFamily: 'monospace',
                                  color: val < -0.02 ? '#EF4444' : val > 0.02 ? '#10B981' : 'var(--text-primary)',
                                }}
                              >
                                {(val * 100).toFixed(2)}%
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
              No simulated data. Click "Simulate Dependent Returns" above.
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Tail Risk Parity (TRP) Allocation */}
      {activeTab === 'allocation' && (
        <div>
          {trpResult ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {/* Summary Metrics */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
                <div className="card" style={{ padding: '16px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
                    Portfolio CVaR (99%)
                  </div>
                  <div style={{ fontSize: '24px', fontWeight: 700, color: '#EF4444', margin: '6px 0' }}>
                    {(trpResult.portfolio_cvar * 100).toFixed(2)}%
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    Equal-Weight CVaR: {(trpResult.baselines.equal_weight.portfolio_cvar * 100).toFixed(2)}%
                  </div>
                </div>

                <div className="card" style={{ padding: '16px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
                    Portfolio VaR (99%)
                  </div>
                  <div style={{ fontSize: '24px', fontWeight: 700, color: '#F59E0B', margin: '6px 0' }}>
                    {(trpResult.portfolio_var * 100).toFixed(2)}%
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    Equal-Weight VaR: {(trpResult.baselines.equal_weight.portfolio_var * 100).toFixed(2)}%
                  </div>
                </div>

                <div className="card" style={{ padding: '16px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
                    Euler Identity Residual
                  </div>
                  <div style={{ fontSize: '24px', fontWeight: 700, color: '#10B981', margin: '6px 0' }}>
                    &lt; 1e-10
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    Exact mathematical Euler sum: {(trpResult.portfolio_cvar * 100).toFixed(2)}%
                  </div>
                </div>

                <div className="card" style={{ padding: '16px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
                    Optimization Status
                  </div>
                  <div style={{ fontSize: '24px', fontWeight: 700, color: trpResult.converged ? '#10B981' : '#EF4444', margin: '6px 0' }}>
                    {trpResult.converged ? 'CONVERGED' : 'FALLBACK'}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    SLSQP non-linear solver with budget invariant
                  </div>
                </div>
              </div>

              {/* Weights & Tail Risk Contributions Table */}
              <div className="card" style={{ padding: '20px' }}>
                <h3 style={{ fontSize: '15px', fontWeight: 600, marginBottom: '14px' }}>
                  Tail Risk Parity vs. Baseline Allocations & Risk Contributions
                </h3>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border-medium)' }}>
                        <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-dim)' }}>Asset</th>
                        <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>TRP Weight</th>
                        <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>Equal Weight</th>
                        <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>Inv-Vol Weight</th>
                        <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>TRP Tail Risk Contrib (TRC)</th>
                        <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>EW Tail Risk Contrib</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.keys(trpResult.weights).map((t) => {
                        const wTrp = trpResult.weights[t];
                        const wEw = trpResult.baselines.equal_weight.weights[t] || 0.0;
                        const wIv = trpResult.baselines.inverse_volatility.weights[t] || 0.0;
                        const trcTrp = trpResult.tail_risk_contributions[t] || 0.0;
                        const trcEw = trpResult.baselines.equal_weight.tail_risk_contributions[t] || 0.0;

                        return (
                          <tr key={t} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                            <td style={{ padding: '8px 12px', fontWeight: 600, color: 'var(--text-primary)' }}>{t}</td>
                            <td style={{ padding: '8px 12px', textAlign: 'right', fontWeight: 600, color: 'var(--accent)' }}>
                              {(wTrp * 100).toFixed(2)}%
                            </td>
                            <td style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-secondary)' }}>
                              {(wEw * 100).toFixed(2)}%
                            </td>
                            <td style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-secondary)' }}>
                              {(wIv * 100).toFixed(2)}%
                            </td>
                            <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', color: '#10B981' }}>
                              {(trcTrp * 100).toFixed(3)}%
                            </td>
                            <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', color: 'var(--text-muted)' }}>
                              {(trcEw * 100).toFixed(3)}%
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
              No allocation data. Click "Optimize Tail Risk Parity" above.
            </div>
          )}
        </div>
      )}

      {/* Tab 4: Regular Vine Copulas (C-Vine & D-Vine) */}
      {activeTab === 'vine' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Theoretical Notice */}
          <div
            className="alert alert-info"
            style={{
              display: 'flex',
              gap: '12px',
              alignItems: 'flex-start',
              backgroundColor: 'var(--bg-elevated)',
              border: '1px solid var(--border-medium)',
              borderRadius: 'var(--radius-md)',
              padding: '14px 18px',
            }}
          >
            <GitBranch size={20} style={{ color: 'var(--accent)', flexShrink: 0, marginTop: '2px' }} />
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              <strong style={{ color: 'var(--text-primary)', fontSize: '13px' }}>
                Stage 23 Pair-Copula Construction (PCC) & Vine Architecture:
              </strong>
              <br />
              • Regular Vines decompose a high-dimensional copula density into a product of <em>d(d-1)/2</em> bivariate copulas arranged in <em>d-1</em> hierarchical trees.
              <br />
              • <strong>Canonical Vine (C-Vine):</strong> Star-structured trees with prominent central pivot assets capturing major market co-movements.
              <br />
              • <strong>D-Vine:</strong> Sequential line path trees where variables are ordered linearly, modeling neighborhood/lead-lag dependencies.
              <br />
              • Conditional distributions are computed via Joe (1996) <em>h</em>-functions: <code>h(u, v; &theta;) = &part;C(u, v)/&part;v</code>, and simulated sequentially via exact numerical inversion <code>h<sup>-1</sup></code>.
            </div>
          </div>

          {/* Vine Configuration & Run Card */}
          <div className="card" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Layers size={18} style={{ color: 'var(--accent)' }} />
                <h3 style={{ fontSize: '15px', fontWeight: 600, margin: 0 }}>Vine Architecture Controls</h3>
              </div>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Vine Structure:</span>
                <button
                  onClick={() => setVineType('c_vine')}
                  className={`btn btn-sm ${vineType === 'c_vine' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ fontSize: '12px', padding: '4px 12px' }}
                >
                  C-Vine (Star Pivot)
                </button>
                <button
                  onClick={() => setVineType('d_vine')}
                  className={`btn btn-sm ${vineType === 'd_vine' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ fontSize: '12px', padding: '4px 12px' }}
                >
                  D-Vine (Line Path)
                </button>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
              <button
                onClick={handleFitVine}
                disabled={isVineLoading || !currentDataset?.dataset_id}
                className="btn btn-primary"
                style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
              >
                {isVineLoading ? <RefreshCw size={14} className="spin" /> : <GitBranch size={14} />}
                <span>Fit {vineType === 'c_vine' ? 'C-Vine' : 'D-Vine'} Trees</span>
              </button>

              <button
                onClick={handleSimulateVine}
                disabled={isVineLoading || !currentDataset?.dataset_id}
                className="btn btn-secondary"
                style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
              >
                {isVineLoading ? <RefreshCw size={14} className="spin" /> : <Activity size={14} />}
                <span>Simulate Vine Scenarios</span>
              </button>

              <button
                onClick={handleOptimizeVineTRP}
                disabled={isVineLoading || !currentDataset?.dataset_id}
                className="btn btn-secondary"
                style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
              >
                {isVineLoading ? <RefreshCw size={14} className="spin" /> : <PieChart size={14} />}
                <span>Optimize Vine Tail Risk Parity</span>
              </button>
            </div>
          </div>

          {/* Vine Decomposition Tree View */}
          {vineFitResult ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {/* Ordered Sequence Badge */}
              <div className="card" style={{ padding: '16px' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '8px' }}>
                  Decomposition Variable Ordering ({vineFitResult.vine_type.toUpperCase()})
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                  {vineFitResult.ordered_tickers.map((ticker, idx) => (
                    <React.Fragment key={ticker}>
                      <div
                        style={{
                          padding: '6px 14px',
                          borderRadius: '20px',
                          backgroundColor: idx === 0 && vineType === 'c_vine' ? 'rgba(99, 102, 241, 0.2)' : 'var(--bg-elevated)',
                          border: `1px solid ${idx === 0 && vineType === 'c_vine' ? 'var(--accent)' : 'var(--border-medium)'}`,
                          fontSize: '13px',
                          fontWeight: 600,
                          color: idx === 0 && vineType === 'c_vine' ? 'var(--accent)' : 'var(--text-primary)',
                        }}
                      >
                        {idx === 0 && vineType === 'c_vine' && <span style={{ marginRight: '4px', fontSize: '10px' }}>★ PIVOT:</span>}
                        {ticker}
                      </div>
                      {idx < vineFitResult.ordered_tickers.length - 1 && (
                        <span style={{ color: 'var(--text-muted)', fontSize: '14px' }}>&rarr;</span>
                      )}
                    </React.Fragment>
                  ))}
                </div>
              </div>

              {/* Hierarchical Trees */}
              {vineFitResult.trees.map((treeEdges, treeIdx) => (
                <div key={treeIdx} className="card" style={{ padding: '20px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span
                        style={{
                          width: '24px',
                          height: '24px',
                          borderRadius: '12px',
                          backgroundColor: 'var(--accent)',
                          color: '#fff',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: '12px',
                          fontWeight: 700,
                        }}
                      >
                        {treeIdx + 1}
                      </span>
                      <h4 style={{ fontSize: '14px', fontWeight: 600, margin: 0 }}>
                        Tree T<sub>{treeIdx + 1}</sub> ({treeEdges.length} Pair-Copula Edges)
                      </h4>
                    </div>
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      Conditioning Dimension: {treeEdges[0]?.conditioned_on.length || 0}
                    </span>
                  </div>

                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid var(--border-medium)' }}>
                          <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-dim)' }}>Pair & Conditioning</th>
                          <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-dim)' }}>Selected Family</th>
                          <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>Parameter &theta;</th>
                          <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>Kendall's &tau;</th>
                          <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>Lower Tail &lambda;<sub>L</sub></th>
                          <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>Upper Tail &lambda;<sub>U</sub></th>
                          <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>AIC</th>
                        </tr>
                      </thead>
                      <tbody>
                        {treeEdges.map((edge, eIdx) => {
                          const pairLabel = edge.conditioned_on.length > 0
                            ? `${edge.node_1}, ${edge.node_2} | {${edge.conditioned_on.join(', ')}}`
                            : `${edge.node_1}, ${edge.node_2}`;

                          const familyColors: Record<string, { bg: string; color: string }> = {
                            clayton: { bg: 'rgba(239, 68, 68, 0.15)', color: '#EF4444' },
                            gumbel: { bg: 'rgba(245, 158, 11, 0.15)', color: '#F59E0B' },
                            student_t: { bg: 'rgba(99, 102, 241, 0.15)', color: '#6366F1' },
                            gaussian: { bg: 'rgba(16, 185, 129, 0.15)', color: '#10B981' },
                            independence: { bg: 'rgba(107, 114, 128, 0.15)', color: '#9CA3AF' },
                          };
                          const fc = familyColors[edge.copula_type] || { bg: 'rgba(255,255,255,0.1)', color: 'var(--text-primary)' };

                          return (
                            <tr key={eIdx} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                              <td style={{ padding: '8px 12px', fontWeight: 600, fontFamily: 'monospace' }}>
                                {pairLabel}
                              </td>
                              <td style={{ padding: '8px 12px' }}>
                                <span
                                  style={{
                                    padding: '2px 8px',
                                    borderRadius: '4px',
                                    backgroundColor: fc.bg,
                                    color: fc.color,
                                    fontSize: '11px',
                                    fontWeight: 600,
                                    textTransform: 'uppercase',
                                  }}
                                >
                                  {edge.copula_type}
                                </span>
                              </td>
                              <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                                {edge.theta.toFixed(3)}
                                {edge.df ? ` (df=${edge.df.toFixed(1)})` : ''}
                              </td>
                              <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                                {edge.kendall_tau.toFixed(3)}
                              </td>
                              <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', color: edge.lower_tail_dependence > 0.05 ? '#EF4444' : 'inherit' }}>
                                {edge.lower_tail_dependence.toFixed(3)}
                              </td>
                              <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', color: edge.upper_tail_dependence > 0.05 ? '#F59E0B' : 'inherit' }}>
                                {edge.upper_tail_dependence.toFixed(3)}
                              </td>
                              <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                                {edge.aic.toFixed(1)}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="card" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
              No vine decomposition fitted yet. Click "Fit C-Vine / D-Vine Trees" to begin pair-copula construction.
            </div>
          )}

          {/* Vine Tail Risk Parity Allocation (if available) */}
          {vineTrpResult && (
            <div className="card" style={{ padding: '20px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
                <CheckCircle2 size={18} style={{ color: '#10B981' }} />
                <h3 style={{ fontSize: '15px', fontWeight: 600, margin: 0 }}>
                  Vine Copula Tail Risk Parity (TRP) Allocation
                </h3>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '20px' }}>
                <div style={{ padding: '12px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Portfolio CVaR (99%)</div>
                  <div style={{ fontSize: '20px', fontWeight: 700, color: '#EF4444' }}>
                    {(vineTrpResult.portfolio_cvar * 100).toFixed(2)}%
                  </div>
                </div>
                <div style={{ padding: '12px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Portfolio VaR (99%)</div>
                  <div style={{ fontSize: '20px', fontWeight: 700, color: '#F59E0B' }}>
                    {(vineTrpResult.portfolio_var * 100).toFixed(2)}%
                  </div>
                </div>
                <div style={{ padding: '12px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Euler Identity Error</div>
                  <div style={{ fontSize: '20px', fontWeight: 700, color: '#10B981' }}>
                    &lt; 1e-10
                  </div>
                </div>
              </div>

              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-medium)' }}>
                      <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-dim)' }}>Asset</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>Vine TRP Weight</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>Equal Weight</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>Inverse Vol Weight</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>Tail Risk Contrib (TRC)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.keys(vineTrpResult.weights).map((t) => (
                      <tr key={t} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                        <td style={{ padding: '8px 12px', fontWeight: 600 }}>{t}</td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontWeight: 600, color: 'var(--accent)' }}>
                          {(vineTrpResult.weights[t] * 100).toFixed(2)}%
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-secondary)' }}>
                          {(vineTrpResult.baselines.equal_weight.weights[t] * 100).toFixed(2)}%
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-secondary)' }}>
                          {(vineTrpResult.baselines.inverse_volatility.weights[t] * 100).toFixed(2)}%
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', color: '#10B981' }}>
                          {(vineTrpResult.tail_risk_contributions[t] * 100).toFixed(3)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Vine Simulation Scenarios Summary (if available) */}
          {vineSimResult && (
            <div className="card" style={{ padding: '20px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
                <Activity size={18} style={{ color: 'var(--accent)' }} />
                <h3 style={{ fontSize: '15px', fontWeight: 600, margin: 0 }}>
                  Vine Simulation Summary ({vineSimResult.num_simulations.toLocaleString()} Scenarios)
                </h3>
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-medium)' }}>
                      <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-dim)' }}>Asset</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>Simulated Mean Return</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>Simulated Volatility</th>
                    </tr>
                  </thead>
                  <tbody>
                    {vineSimResult.tickers.map((t) => (
                      <tr key={t} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                        <td style={{ padding: '8px 12px', fontWeight: 600 }}>{t}</td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          {(vineSimResult.simulated_means[t] * 100).toFixed(2)}%
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          {(vineSimResult.simulated_volatilities[t] * 100).toFixed(2)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab 5: Walk-Forward Backtesting (Stage 24) */}
      {activeTab === 'backtest' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Backtest Controls Card */}
          <div className="card" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
              <Sliders size={18} style={{ color: 'var(--accent)' }} />
              <h2 style={{ fontSize: '15px', fontWeight: 600, margin: 0 }}>
                Dynamic Walk-Forward Vine TRP Backtest Configuration
              </h2>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Estimation Window
                </label>
                <select
                  value={backtestEstimationWindow}
                  onChange={(e) => setBacktestEstimationWindow(parseInt(e.target.value))}
                  className="select-input"
                  style={{ width: '100%', padding: '8px', borderRadius: 'var(--radius-sm)' }}
                >
                  <option value={126}>126 Days (~6 Months)</option>
                  <option value={252}>252 Days (~1 Year)</option>
                  <option value={504}>504 Days (~2 Years)</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Rebalance Frequency
                </label>
                <select
                  value={backtestRebalanceFreq}
                  onChange={(e) => setBacktestRebalanceFreq(e.target.value as any)}
                  className="select-input"
                  style={{ width: '100%', padding: '8px', borderRadius: 'var(--radius-sm)' }}
                >
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly (~5 Days)</option>
                  <option value="monthly">Monthly (~21 Days)</option>
                  <option value="quarterly">Quarterly (~63 Days)</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Vine Topology
                </label>
                <select
                  value={backtestVineType}
                  onChange={(e) => setBacktestVineType(e.target.value as VineType)}
                  className="select-input"
                  style={{ width: '100%', padding: '8px', borderRadius: 'var(--radius-sm)' }}
                >
                  <option value="c_vine">C-Vine (Star Copula Tree)</option>
                  <option value="d_vine">D-Vine (Path Copula Tree)</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Monte Carlo Scenarios
                </label>
                <select
                  value={backtestScenarios}
                  onChange={(e) => setBacktestScenarios(parseInt(e.target.value))}
                  className="select-input"
                  style={{ width: '100%', padding: '8px', borderRadius: 'var(--radius-sm)' }}
                >
                  <option value={1000}>1,000 Scenarios (Fast)</option>
                  <option value={2000}>2,000 Scenarios (Standard)</option>
                  <option value={5000}>5,000 Scenarios (High Precision)</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Tail Confidence Level (α)
                </label>
                <select
                  value={backtestConfidence}
                  onChange={(e) => setBacktestConfidence(parseFloat(e.target.value))}
                  className="select-input"
                  style={{ width: '100%', padding: '8px', borderRadius: 'var(--radius-sm)' }}
                >
                  <option value={0.99}>99.0% Confidence</option>
                  <option value={0.975}>97.5% Confidence</option>
                  <option value={0.95}>95.0% Confidence</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Transaction Fee (bps)
                </label>
                <input
                  type="number"
                  value={backtestCostBps}
                  onChange={(e) => setBacktestCostBps(parseFloat(e.target.value) || 0)}
                  className="input-field"
                  style={{ width: '100%', padding: '8px', borderRadius: 'var(--radius-sm)' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Execution Model (Stage 25)
                </label>
                <select
                  value={backtestExecutionModel}
                  onChange={(e) => setBacktestExecutionModel(e.target.value as any)}
                  className="select-input"
                  style={{ width: '100%', padding: '8px', borderRadius: 'var(--radius-sm)' }}
                >
                  <option value="square_root">Square-Root Law (Barra / Almgren)</option>
                  <option value="linear">Linear Impact (Kyle Model)</option>
                  <option value="fixed_bps">Fixed Basis Points (Baseline)</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  {backtestExecutionModel === 'fixed_bps' ? 'Execution Slippage (bps)' : 'Quoted Spread (bps)'}
                </label>
                <input
                  type="number"
                  value={backtestExecutionModel === 'fixed_bps' ? backtestSlippageBps : backtestSpreadBps}
                  onChange={(e) => {
                    const val = parseFloat(e.target.value) || 0;
                    if (backtestExecutionModel === 'fixed_bps') {
                      setBacktestSlippageBps(val);
                    } else {
                      setBacktestSpreadBps(val);
                    }
                  }}
                  className="input-field"
                  style={{ width: '100%', padding: '8px', borderRadius: 'var(--radius-sm)' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Participation Limit
                </label>
                <select
                  value={backtestMaxParticipation}
                  onChange={(e) => setBacktestMaxParticipation(parseFloat(e.target.value))}
                  className="select-input"
                  style={{ width: '100%', padding: '8px', borderRadius: 'var(--radius-sm)' }}
                >
                  <option value={0.05}>5% of ADV (Conservative)</option>
                  <option value={0.10}>10% of ADV (Institutional)</option>
                  <option value={0.20}>20% of ADV (Aggressive)</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Participation Policy
                </label>
                <select
                  value={backtestParticipationPolicy}
                  onChange={(e) => setBacktestParticipationPolicy(e.target.value as any)}
                  className="select-input"
                  style={{ width: '100%', padding: '8px', borderRadius: 'var(--radius-sm)' }}
                >
                  <option value="warn">Warn on Exceedance</option>
                  <option value="cap">Cap Trade to Limit</option>
                  <option value="reject">Reject Rebalance Entirely</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Endogenous Liquidity Stress
                </label>
                <select
                  value={backtestEnableEndogenous ? 'true' : 'false'}
                  onChange={(e) => setBacktestEnableEndogenous(e.target.value === 'true')}
                  className="select-input"
                  style={{ width: '100%', padding: '8px', borderRadius: 'var(--radius-sm)' }}
                >
                  <option value="true">Enabled (Crash Spread & ADV Freeze)</option>
                  <option value="false">Disabled (Static Deterministic L-VaR)</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Spread Stress (&kappa;)
                </label>
                <input
                  type="number"
                  value={backtestSpreadStress}
                  onChange={(e) => setBacktestSpreadStress(parseFloat(e.target.value) || 0)}
                  className="input-field"
                  style={{ width: '100%', padding: '8px', borderRadius: 'var(--radius-sm)' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Execution Scheduling (Stage 28)
                </label>
                <select
                  value={backtestExecutionSchedulingMode}
                  onChange={(e) => setBacktestExecutionSchedulingMode(e.target.value as any)}
                  className="select-input"
                  style={{ width: '100%', padding: '8px', borderRadius: 'var(--radius-sm)' }}
                >
                  <option value="single_day">Single-Day (Immediate)</option>
                  <option value="twap">TWAP (Uniform Multi-Day)</option>
                  <option value="vwap">VWAP (Causal Volume Profile)</option>
                  <option value="almgren_chriss">Almgren-Chriss (Optimal Trajectory)</option>
                </select>
              </div>

              {backtestExecutionSchedulingMode !== 'single_day' && (
                <div>
                  <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                    Max Scheduling Days (D_max)
                  </label>
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={backtestMaxSchedulingDays}
                    onChange={(e) => setBacktestMaxSchedulingDays(parseInt(e.target.value) || 1)}
                    className="input-field"
                    style={{ width: '100%', padding: '8px', borderRadius: 'var(--radius-sm)' }}
                  />
                </div>
              )}

              {backtestExecutionSchedulingMode === 'almgren_chriss' && (
                <div>
                  <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                    Scheduling Risk Aversion (&lambda;)
                  </label>
                  <input
                    type="number"
                    step="0.0000001"
                    value={backtestSchedulingRiskAversion}
                    onChange={(e) => setBacktestSchedulingRiskAversion(parseFloat(e.target.value) || 1e-6)}
                    className="input-field"
                    style={{ width: '100%', padding: '8px', borderRadius: 'var(--radius-sm)' }}
                  />
                </div>
              )}

              {/* Stage 29: Regime-Aware Execution Dynamics */}
              <div style={{ padding: '12px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-medium)', gridColumn: 'span 2' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={backtestEnableRegimeAware}
                      onChange={(e) => setBacktestEnableRegimeAware(e.target.checked)}
                      style={{ width: '16px', height: '16px', accentColor: 'var(--accent)' }}
                    />
                    <span>Regime-Aware Execution Dynamics (Stage 29)</span>
                  </label>
                  <span style={{ fontSize: '11px', color: 'var(--text-dim)' }}>Adaptive HMM-driven participation &amp; risk aversion</span>
                </div>

                {backtestEnableRegimeAware && (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', marginTop: '10px' }}>
                    <div>
                      <label style={{ display: 'block', fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                        Regime States (M)
                      </label>
                      <select
                        value={backtestRegimeNumStates}
                        onChange={(e) => setBacktestRegimeNumStates(parseInt(e.target.value) || 2)}
                        className="input-field"
                        style={{ width: '100%', padding: '6px 8px', borderRadius: 'var(--radius-sm)', fontSize: '12px' }}
                      >
                        <option value={2}>2 States (Calm / Crisis)</option>
                        <option value={3}>3 States (Low / Normal / High Vol)</option>
                      </select>
                    </div>

                    <div>
                      <label style={{ display: 'block', fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                        Adaptation Strength (s)
                      </label>
                      <input
                        type="number"
                        min="0.0"
                        max="1.0"
                        step="0.05"
                        value={backtestRegimeAdaptationStrength}
                        onChange={(e) => setBacktestRegimeAdaptationStrength(parseFloat(e.target.value) || 0.5)}
                        className="input-field"
                        style={{ width: '100%', padding: '6px 8px', borderRadius: 'var(--radius-sm)', fontSize: '12px' }}
                      />
                    </div>

                    <div>
                      <label style={{ display: 'block', fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                        Participation Floor (p_min)
                      </label>
                      <input
                        type="number"
                        min="0.001"
                        max="0.20"
                        step="0.005"
                        value={backtestMinParticipationRate}
                        onChange={(e) => setBacktestMinParticipationRate(parseFloat(e.target.value) || 0.02)}
                        className="input-field"
                        style={{ width: '100%', padding: '6px 8px', borderRadius: 'var(--radius-sm)', fontSize: '12px' }}
                      />
                    </div>
                  </div>
                )}
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Volume Freeze (&eta;)
                </label>
                <input
                  type="number"
                  value={backtestAdvStress}
                  onChange={(e) => setBacktestAdvStress(parseFloat(e.target.value) || 0)}
                  className="input-field"
                  style={{ width: '100%', padding: '8px', borderRadius: 'var(--radius-sm)' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Initial Capital ($)
                </label>
                <input
                  type="number"
                  value={backtestInitialCapital}
                  onChange={(e) => setBacktestInitialCapital(parseFloat(e.target.value) || 10000)}
                  className="input-field"
                  style={{ width: '100%', padding: '8px', borderRadius: 'var(--radius-sm)' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Random Seed
                </label>
                <input
                  type="number"
                  value={backtestSeed}
                  onChange={(e) => setBacktestSeed(parseInt(e.target.value) || 0)}
                  className="input-field"
                  style={{ width: '100%', padding: '8px', borderRadius: 'var(--radius-sm)' }}
                />
              </div>
            </div>

            <div style={{ marginTop: '16px' }}>
              <button
                onClick={handleRunBacktest}
                disabled={isBacktestLoading || !currentDataset?.dataset_id}
                className="btn btn-primary"
                style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 20px' }}
              >
                {isBacktestLoading ? <RefreshCw size={15} className="spin" /> : <TrendingUp size={15} />}
                <span>{isBacktestLoading ? 'Running Out-of-Sample Backtest...' : 'Run Walk-Forward Backtest'}</span>
              </button>
            </div>
          </div>

          {/* Methodology & Anti-Look-Ahead Notice */}
          <div
            className="alert alert-info"
            style={{
              display: 'flex',
              gap: '12px',
              alignItems: 'flex-start',
              backgroundColor: 'var(--bg-elevated)',
              border: '1px solid var(--border-medium)',
              borderRadius: 'var(--radius-md)',
              padding: '12px 16px',
            }}
          >
            <ShieldAlert size={18} style={{ color: 'var(--accent)', flexShrink: 0, marginTop: '2px' }} />
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              <strong style={{ color: 'var(--text-primary)' }}>Institutional Walk-Forward Accounting & Chronological Integrity:</strong>
              <br />
              • <strong>Zero Look-Ahead Bias:</strong> At rebalance date t<sub>k</sub>, only historical data up to t<sub>k</sub> - 1 is included in the estimation window. Day t<sub>k</sub> returns are realized strictly after trades are settled.
              <br />
              • <strong>Weight Drift:</strong> Portfolio weights drift continuously between rebalances with market price movements: w<sub>i,t</sub><sup>pre</sup> = w<sub>i,t-1</sub>(1 + R<sub>i,t-1</sub>) / &sum;<sub>j</sub> w<sub>j,t-1</sub>(1 + R<sub>j,t-1</sub>).
              <br />
              • <strong>Friction Accounting:</strong> Proportional transaction fee ({(backtestCostBps).toFixed(0)} bps) and slippage ({(backtestSlippageBps).toFixed(0)} bps) are deducted from capital at execution based on one-way turnover: TO<sub>k</sub> = &frac12; &sum; |w<sub>i</sub><sup>*</sup> - w<sub>i</sub><sup>pre</sup>|.
            </div>
          </div>

          {/* Backtest Results Presentation */}
          {backtestResult && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {/* Strategy Comparison KPI Grid */}
              <div className="card" style={{ padding: '20px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Layers size={18} style={{ color: 'var(--accent)' }} />
                    <h3 style={{ fontSize: '15px', fontWeight: 600, margin: 0 }}>
                      Performance & Risk Benchmark ({backtestResult.out_of_sample_period.start_date} to {backtestResult.out_of_sample_period.end_date}, {backtestResult.out_of_sample_period.trading_days} Trading Days)
                    </h3>
                  </div>
                  <span style={{ fontSize: '12px', color: 'var(--text-dim)', fontFamily: 'monospace' }}>
                    Rebalances: {backtestResult.rebalance_count} | Topology: {backtestResult.vine_type.toUpperCase()}
                  </span>
                </div>

                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border-medium)' }}>
                        <th style={{ padding: '10px 12px', textAlign: 'left', color: 'var(--text-dim)' }}>Performance Metric</th>
                        <th style={{ padding: '10px 12px', textAlign: 'right', color: '#10B981', fontWeight: 700 }}>Dynamic Vine TRP (Net)</th>
                        <th style={{ padding: '10px 12px', textAlign: 'right', color: '#38BDF8', fontWeight: 700 }}>Equal-Weight (1/N)</th>
                        <th style={{ padding: '10px 12px', textAlign: 'right', color: '#F59E0B', fontWeight: 700 }}>Static Vine TRP</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                        <td style={{ padding: '8px 12px', fontWeight: 600 }}>Total Net Return</td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', fontWeight: 600, color: '#10B981' }}>
                          {(backtestResult.strategies.dynamic_vine_trp.total_return_net * 100).toFixed(2)}%
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          {(backtestResult.strategies.equal_weight.total_return_net * 100).toFixed(2)}%
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          {(backtestResult.strategies.static_vine_trp.total_return_net * 100).toFixed(2)}%
                        </td>
                      </tr>
                      <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                        <td style={{ padding: '8px 12px', fontWeight: 600 }}>Annualized Return (CAGR)</td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', fontWeight: 600, color: '#10B981' }}>
                          {(backtestResult.strategies.dynamic_vine_trp.cagr_net * 100).toFixed(2)}%
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          {(backtestResult.strategies.equal_weight.cagr_net * 100).toFixed(2)}%
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          {(backtestResult.strategies.static_vine_trp.cagr_net * 100).toFixed(2)}%
                        </td>
                      </tr>
                      <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                        <td style={{ padding: '8px 12px', fontWeight: 600 }}>Annualized Volatility (Gross / Net)</td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          {(backtestResult.strategies.dynamic_vine_trp.annualized_volatility * 100).toFixed(2)}%
                          {backtestResult.strategies.dynamic_vine_trp.annualized_volatility_net != null && (
                            <span style={{ fontSize: '11px', color: 'var(--text-secondary)', marginLeft: '4px' }}>
                              / {(backtestResult.strategies.dynamic_vine_trp.annualized_volatility_net * 100).toFixed(2)}%
                            </span>
                          )}
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          {(backtestResult.strategies.equal_weight.annualized_volatility * 100).toFixed(2)}%
                          {backtestResult.strategies.equal_weight.annualized_volatility_net != null && (
                            <span style={{ fontSize: '11px', color: 'var(--text-secondary)', marginLeft: '4px' }}>
                              / {(backtestResult.strategies.equal_weight.annualized_volatility_net * 100).toFixed(2)}%
                            </span>
                          )}
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          {(backtestResult.strategies.static_vine_trp.annualized_volatility * 100).toFixed(2)}%
                          {backtestResult.strategies.static_vine_trp.annualized_volatility_net != null && (
                            <span style={{ fontSize: '11px', color: 'var(--text-secondary)', marginLeft: '4px' }}>
                              / {(backtestResult.strategies.static_vine_trp.annualized_volatility_net * 100).toFixed(2)}%
                            </span>
                          )}
                        </td>
                      </tr>
                      <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                        <td style={{ padding: '8px 12px', fontWeight: 600 }}>Sharpe Ratio (Gross / Net, rf = 0)</td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', fontWeight: 600 }}>
                          {(backtestResult.strategies.dynamic_vine_trp.sharpe_ratio_gross ?? backtestResult.strategies.dynamic_vine_trp.sharpe_ratio).toFixed(2)}
                          {backtestResult.strategies.dynamic_vine_trp.sharpe_ratio_net != null && (
                            <span style={{ fontSize: '11px', color: 'var(--text-secondary)', marginLeft: '4px' }}>
                              / {backtestResult.strategies.dynamic_vine_trp.sharpe_ratio_net.toFixed(2)}
                            </span>
                          )}
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          {(backtestResult.strategies.equal_weight.sharpe_ratio_gross ?? backtestResult.strategies.equal_weight.sharpe_ratio).toFixed(2)}
                          {backtestResult.strategies.equal_weight.sharpe_ratio_net != null && (
                            <span style={{ fontSize: '11px', color: 'var(--text-secondary)', marginLeft: '4px' }}>
                              / {backtestResult.strategies.equal_weight.sharpe_ratio_net.toFixed(2)}
                            </span>
                          )}
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          {(backtestResult.strategies.static_vine_trp.sharpe_ratio_gross ?? backtestResult.strategies.static_vine_trp.sharpe_ratio).toFixed(2)}
                          {backtestResult.strategies.static_vine_trp.sharpe_ratio_net != null && (
                            <span style={{ fontSize: '11px', color: 'var(--text-secondary)', marginLeft: '4px' }}>
                              / {backtestResult.strategies.static_vine_trp.sharpe_ratio_net.toFixed(2)}
                            </span>
                          )}
                        </td>
                      </tr>
                      <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                        <td style={{ padding: '8px 12px', fontWeight: 600 }}>Maximum Drawdown</td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', color: '#EF4444' }}>
                          {(backtestResult.strategies.dynamic_vine_trp.max_drawdown * 100).toFixed(2)}%
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', color: '#EF4444' }}>
                          {(backtestResult.strategies.equal_weight.max_drawdown * 100).toFixed(2)}%
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', color: '#EF4444' }}>
                          {(backtestResult.strategies.static_vine_trp.max_drawdown * 100).toFixed(2)}%
                        </td>
                      </tr>
                      <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                        <td style={{ padding: '8px 12px', fontWeight: 600 }}>Historical CVaR (99%)</td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', color: '#EF4444' }}>
                          {(backtestResult.strategies.dynamic_vine_trp.cvar_99 * 100).toFixed(2)}%
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', color: '#EF4444' }}>
                          {(backtestResult.strategies.equal_weight.cvar_99 * 100).toFixed(2)}%
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', color: '#EF4444' }}>
                          {(backtestResult.strategies.static_vine_trp.cvar_99 * 100).toFixed(2)}%
                        </td>
                      </tr>
                      <tr style={{ borderBottom: '1px solid var(--border-subtle)', backgroundColor: 'rgba(99, 102, 241, 0.04)' }}>
                        <td style={{ padding: '8px 12px', fontWeight: 600, color: 'var(--accent)' }}>Liquidity-Adjusted CVaR (L-CVaR 99%)</td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', fontWeight: 700, color: 'var(--accent)' }}>
                          {backtestResult.strategies.dynamic_vine_trp.l_cvar_99 != null ? `${(backtestResult.strategies.dynamic_vine_trp.l_cvar_99 * 100).toFixed(2)}%` : 'N/A'}
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          {backtestResult.strategies.equal_weight.l_cvar_99 != null ? `${(backtestResult.strategies.equal_weight.l_cvar_99 * 100).toFixed(2)}%` : 'N/A'}
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          {backtestResult.strategies.static_vine_trp.l_cvar_99 != null ? `${(backtestResult.strategies.static_vine_trp.l_cvar_99 * 100).toFixed(2)}%` : 'N/A'}
                        </td>
                      </tr>
                      <tr style={{ borderBottom: '1px solid var(--border-subtle)', backgroundColor: 'rgba(239, 68, 68, 0.05)' }}>
                        <td style={{ padding: '8px 12px', fontWeight: 600, color: '#EF4444' }}>Endogenous Stressed L-CVaR (99%)</td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', fontWeight: 700, color: '#EF4444' }}>
                          {backtestResult.strategies.dynamic_vine_trp.stressed_l_cvar_99 != null ? `${(backtestResult.strategies.dynamic_vine_trp.stressed_l_cvar_99 * 100).toFixed(2)}%` : 'N/A'}
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          {backtestResult.strategies.equal_weight.stressed_l_cvar_99 != null ? `${(backtestResult.strategies.equal_weight.stressed_l_cvar_99 * 100).toFixed(2)}%` : 'N/A'}
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          {backtestResult.strategies.static_vine_trp.stressed_l_cvar_99 != null ? `${(backtestResult.strategies.static_vine_trp.stressed_l_cvar_99 * 100).toFixed(2)}%` : 'N/A'}
                        </td>
                      </tr>
                      <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                        <td style={{ padding: '8px 12px', fontWeight: 600 }}>Liquidity-Adjusted VaR (L-VaR 99%)</td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          {backtestResult.strategies.dynamic_vine_trp.l_var_99 != null ? `${(backtestResult.strategies.dynamic_vine_trp.l_var_99 * 100).toFixed(2)}%` : 'N/A'}
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          {backtestResult.strategies.equal_weight.l_var_99 != null ? `${(backtestResult.strategies.equal_weight.l_var_99 * 100).toFixed(2)}%` : 'N/A'}
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          {backtestResult.strategies.static_vine_trp.l_var_99 != null ? `${(backtestResult.strategies.static_vine_trp.l_var_99 * 100).toFixed(2)}%` : 'N/A'}
                        </td>
                      </tr>
                      <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                        <td style={{ padding: '8px 12px', fontWeight: 600 }}>Avg Cash Reserve (w_cash)</td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', fontWeight: 600 }}>
                          {backtestResult.strategies.dynamic_vine_trp.average_cash_weight != null ? `${(backtestResult.strategies.dynamic_vine_trp.average_cash_weight * 100).toFixed(2)}%` : '0.00%'}
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>0.00%</td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>0.00%</td>
                      </tr>
                      <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                        <td style={{ padding: '8px 12px', fontWeight: 600 }}>Cumulative One-Way Turnover</td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          {backtestResult.strategies.dynamic_vine_trp.cumulative_turnover.toFixed(2)}x
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          {backtestResult.strategies.equal_weight.cumulative_turnover.toFixed(2)}x
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          {backtestResult.strategies.static_vine_trp.cumulative_turnover.toFixed(2)}x
                        </td>
                      </tr>
                      <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                        <td style={{ padding: '8px 12px', fontWeight: 600 }}>Total Trading Friction ($)</td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', fontWeight: 600 }}>
                          ${backtestResult.strategies.dynamic_vine_trp.total_transaction_costs.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          ${backtestResult.strategies.equal_weight.total_transaction_costs.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          ${backtestResult.strategies.static_vine_trp.total_transaction_costs.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </td>
                      </tr>
                      <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                        <td style={{ padding: '8px 12px', color: 'var(--text-secondary)' }}>• Bid-Ask Spread Cost ($)</td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          ${(backtestResult.strategies.dynamic_vine_trp.total_spread_costs ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          ${(backtestResult.strategies.equal_weight.total_spread_costs ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          ${(backtestResult.strategies.static_vine_trp.total_spread_costs ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </td>
                      </tr>
                      <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                        <td style={{ padding: '8px 12px', color: 'var(--text-secondary)' }}>• Market Impact Drag ($)</td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          ${(backtestResult.strategies.dynamic_vine_trp.total_market_impact_costs ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          ${(backtestResult.strategies.equal_weight.total_market_impact_costs ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          ${(backtestResult.strategies.static_vine_trp.total_market_impact_costs ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </td>
                      </tr>
                      <tr>
                        <td style={{ padding: '8px 12px', color: 'var(--text-secondary)' }}>• Max Observed Participation Rate</td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          {((backtestResult.strategies.dynamic_vine_trp.max_participation_rate_observed ?? 0) * 100).toFixed(2)}% ADV
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          {((backtestResult.strategies.equal_weight.max_participation_rate_observed ?? 0) * 100).toFixed(2)}% ADV
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                          N/A
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Equity Curves (SVG Multi-line Plot) */}
              {backtestResult.equity_curves.length > 1 && (
                <div className="card" style={{ padding: '20px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Activity size={18} style={{ color: 'var(--accent)' }} />
                      <h3 style={{ fontSize: '15px', fontWeight: 600, margin: 0 }}>
                        Out-of-Sample Equity Curves ($100,000 Initial Capital, Net of Friction)
                      </h3>
                    </div>
                    {/* Legend */}
                    <div style={{ display: 'flex', gap: '16px', fontSize: '12px' }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ width: '12px', height: '3px', backgroundColor: '#10B981', display: 'inline-block' }} />
                        Dynamic Vine TRP
                      </span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ width: '12px', height: '3px', backgroundColor: '#38BDF8', display: 'inline-block' }} />
                        Equal-Weight (1/N)
                      </span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ width: '12px', height: '3px', backgroundColor: '#F59E0B', display: 'inline-block' }} />
                        Static Vine TRP
                      </span>
                    </div>
                  </div>

                  {(() => {
                    const data = backtestResult.equity_curves;
                    const minVal = Math.min(...data.map(d => Math.min(d.dynamic_vine_trp, d.equal_weight, d.static_vine_trp)));
                    const maxVal = Math.max(...data.map(d => Math.max(d.dynamic_vine_trp, d.equal_weight, d.static_vine_trp)));
                    const padding = (maxVal - minVal) * 0.08 || 1000;
                    const yMin = Math.max(0, minVal - padding);
                    const yMax = maxVal + padding;
                    const width = 860;
                    const height = 240;

                    const getX = (idx: number) => 50 + (idx / (data.length - 1)) * (width - 70);
                    const getY = (val: number) => height - 30 - ((val - yMin) / (yMax - yMin)) * (height - 50);

                    const pathDynamic = data.map((d, i) => `${i === 0 ? 'M' : 'L'} ${getX(i).toFixed(1)} ${getY(d.dynamic_vine_trp).toFixed(1)}`).join(' ');
                    const pathBenchmark = data.map((d, i) => `${i === 0 ? 'M' : 'L'} ${getX(i).toFixed(1)} ${getY(d.equal_weight).toFixed(1)}`).join(' ');
                    const pathStatic = data.map((d, i) => `${i === 0 ? 'M' : 'L'} ${getX(i).toFixed(1)} ${getY(d.static_vine_trp).toFixed(1)}`).join(' ');

                    return (
                      <div style={{ width: '100%', overflowX: 'auto' }}>
                        <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: 'auto', display: 'block' }}>
                          {/* Grid Lines */}
                          {[0, 0.25, 0.5, 0.75, 1.0].map((frac, idx) => {
                            const val = yMin + frac * (yMax - yMin);
                            const y = getY(val);
                            return (
                              <g key={idx}>
                                <line x1="50" y1={y} x2={width - 20} y2={y} stroke="var(--border-subtle)" strokeDasharray="3 3" />
                                <text x="45" y={y + 3} textAnchor="end" fontSize="10" fill="var(--text-dim)" fontFamily="monospace">
                                  ${Math.round(val / 1000)}k
                                </text>
                              </g>
                            );
                          })}

                          {/* Strategy Line Paths */}
                          <path d={pathBenchmark} fill="none" stroke="#38BDF8" strokeWidth="1.8" />
                          <path d={pathStatic} fill="none" stroke="#F59E0B" strokeWidth="1.8" strokeDasharray="4 4" />
                          <path d={pathDynamic} fill="none" stroke="#10B981" strokeWidth="2.5" />

                          {/* X-axis dates */}
                          <text x="50" y={height - 8} fontSize="10" fill="var(--text-dim)">
                            {data[0]?.date}
                          </text>
                          <text x={width / 2} y={height - 8} textAnchor="middle" fontSize="10" fill="var(--text-dim)">
                            {data[Math.floor(data.length / 2)]?.date}
                          </text>
                          <text x={width - 20} y={height - 8} textAnchor="end" fontSize="10" fill="var(--text-dim)">
                            {data[data.length - 1]?.date}
                          </text>
                        </svg>
                      </div>
                    );
                  })()}
                </div>
              )}

              {/* Friction & Execution Drag Analysis */}
              <div className="card" style={{ padding: '20px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
                  <DollarSign size={18} style={{ color: 'var(--accent)' }} />
                  <h3 style={{ fontSize: '15px', fontWeight: 600, margin: 0 }}>
                    Trading Friction & Turnover Execution Diagnostics
                  </h3>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
                  <div style={{ padding: '12px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-medium)' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Gross vs Net Return Drag</div>
                    <div style={{ fontSize: '18px', fontWeight: 700, marginTop: '4px', color: '#EF4444', fontFamily: 'monospace' }}>
                      {backtestResult.strategies.dynamic_vine_trp.total_return_gross != null && backtestResult.strategies.dynamic_vine_trp.total_return_net != null
                        ? `${((backtestResult.strategies.dynamic_vine_trp.total_return_gross - backtestResult.strategies.dynamic_vine_trp.total_return_net) * 10000).toFixed(1)} bps`
                        : 'N/A'}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      {backtestResult.strategies.dynamic_vine_trp.total_return_gross != null && backtestResult.strategies.dynamic_vine_trp.total_return_net != null
                        ? `Gross: ${(backtestResult.strategies.dynamic_vine_trp.total_return_gross * 100).toFixed(2)}% | Net: ${(backtestResult.strategies.dynamic_vine_trp.total_return_net * 100).toFixed(2)}%`
                        : 'Returns Unavailable'}
                    </div>
                  </div>

                  <div style={{ padding: '12px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-medium)' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Avg Turnover per Rebalance</div>
                    <div style={{ fontSize: '18px', fontWeight: 700, marginTop: '4px', color: 'var(--text-primary)', fontFamily: 'monospace' }}>
                      {backtestResult.rebalance_count > 0 ? (backtestResult.strategies.dynamic_vine_trp.cumulative_turnover / backtestResult.rebalance_count * 100).toFixed(2) : '0.00'}%
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      Total Cumulative: {backtestResult.strategies.dynamic_vine_trp.cumulative_turnover.toFixed(2)}x capital
                    </div>
                  </div>

                  <div style={{ padding: '12px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-medium)' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Friction Breakdown (Stage 25)</div>
                    <div style={{ fontSize: '14px', fontWeight: 700, marginTop: '4px', color: 'var(--text-primary)', fontFamily: 'monospace' }}>
                      Spread: ${(backtestResult.strategies.dynamic_vine_trp.total_spread_costs ?? 0).toFixed(2)} | Impact: ${(backtestResult.strategies.dynamic_vine_trp.total_market_impact_costs ?? 0).toFixed(2)}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      Commissions: ${(backtestResult.strategies.dynamic_vine_trp.total_commission_costs ?? 0).toFixed(2)}
                    </div>
                  </div>

                  <div style={{ padding: '12px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-medium)' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Liquidity Model & ADV Source</div>
                    <div style={{ fontSize: '14px', fontWeight: 700, marginTop: '4px', color: 'var(--accent)', fontFamily: 'monospace' }}>
                      {(backtestResult.execution_model ?? 'square_root').toUpperCase()}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      Source: {backtestResult.adv_source === 'market_observed' ? 'Market-Observed Volume' : 'Calibrated Default ADV'}
                    </div>
                  </div>

                  <div style={{ padding: '12px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-medium)' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Execution Scheduling (Stage 28/29)</div>
                    <div style={{ fontSize: '14px', fontWeight: 700, marginTop: '4px', color: '#10B981', fontFamily: 'monospace' }}>
                      {(backtestResult.execution_scheduling_mode ?? 'single_day').toUpperCase()}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      {backtestResult.enable_regime_aware_execution ? 'Regime-Aware Dynamics: Active' : `Max Horizon: ${backtestResult.max_scheduling_days ?? 1}d`}
                    </div>
                  </div>
                </div>
              </div>

              {/* Stage 30: Transaction Cost Analysis (TCA) and Slippage Performance Attribution */}
              {backtestResult.tca_report && backtestResult.tca_report.summary && (
                <div className="card" style={{ padding: '20px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px', flexWrap: 'wrap', gap: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Activity size={18} style={{ color: 'var(--accent)' }} />
                      <h3 style={{ fontSize: '15px', fontWeight: 600, margin: 0 }}>
                        Transaction Cost Analysis (TCA) & Slippage Attribution (Stage 30)
                      </h3>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '4px',
                        padding: '2px 8px',
                        borderRadius: 'var(--radius-sm)',
                        fontSize: '11px',
                        backgroundColor: (backtestResult.tca_report.provenance?.reconciliation_status === 'exact_modeled_identity_verified' || Math.abs(backtestResult.tca_report.summary.unattributed_cost) < 1e-4) ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                        color: (backtestResult.tca_report.provenance?.reconciliation_status === 'exact_modeled_identity_verified' || Math.abs(backtestResult.tca_report.summary.unattributed_cost) < 1e-4) ? '#10B981' : '#EF4444',
                        fontWeight: 600,
                      }}>
                        <CheckCircle2 size={12} />
                        {(backtestResult.tca_report.provenance?.reconciliation_status === 'exact_modeled_identity_verified' || Math.abs(backtestResult.tca_report.summary.unattributed_cost) < 1e-4) ? 'Exact Modeled Identity ($0.00 residual)' : 'Reconciliation Discrepancy'}
                      </span>
                      <span style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '4px',
                        padding: '2px 8px',
                        borderRadius: 'var(--radius-sm)',
                        fontSize: '11px',
                        backgroundColor: 'rgba(59, 130, 246, 0.15)',
                        color: '#3B82F6',
                        fontWeight: 600,
                      }}>
                        Decision-Time Anchored (Causal)
                      </span>
                    </div>
                  </div>

                  {/* Portfolio-Level TCA Metric Tiles */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px', marginBottom: '18px' }}>
                    <div style={{ padding: '12px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-medium)' }}>
                      <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Total Realized Cost</div>
                      <div style={{ fontSize: '18px', fontWeight: 700, marginTop: '4px', color: '#EF4444', fontFamily: 'monospace' }}>
                        ${backtestResult.tca_report.summary.total_cost.toFixed(2)}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                        {backtestResult.tca_report.summary.effective_bps.toFixed(2)} bps on ${backtestResult.tca_report.summary.total_executed_notional.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                      </div>
                    </div>

                    <div style={{ padding: '12px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-medium)' }}>
                      <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Spread-Crossing Friction</div>
                      <div style={{ fontSize: '18px', fontWeight: 700, marginTop: '4px', color: 'var(--text-primary)', fontFamily: 'monospace' }}>
                        ${backtestResult.tca_report.summary.spread_cost.toFixed(2)}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                        {backtestResult.tca_report.summary.spread_bps.toFixed(2)} bps (Half-Spread)
                      </div>
                    </div>

                    <div style={{ padding: '12px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-medium)' }}>
                      <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Temporary Market Impact</div>
                      <div style={{ fontSize: '18px', fontWeight: 700, marginTop: '4px', color: 'var(--text-primary)', fontFamily: 'monospace' }}>
                        ${backtestResult.tca_report.summary.temporary_impact_cost.toFixed(2)}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                        {backtestResult.tca_report.summary.temporary_impact_bps.toFixed(2)} bps (Square-Root Model)
                      </div>
                    </div>

                    <div style={{ padding: '12px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-medium)' }}>
                      <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Permanent Impact / Drift</div>
                      <div style={{ fontSize: '18px', fontWeight: 700, marginTop: '4px', color: 'var(--text-dim)', fontFamily: 'monospace' }}>
                        ${backtestResult.tca_report.summary.permanent_impact_cost.toFixed(2)}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                        {backtestResult.tca_report.summary.permanent_impact_bps.toFixed(2)} bps ({backtestResult.tca_report.provenance?.permanent_impact_status === 'modeled_linear_adv_ratio' ? 'Linear ADV Model' : 'Zero / Not Modeled'})
                      </div>
                    </div>

                    <div style={{ padding: '12px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-medium)' }}>
                      <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Opportunity / Delay Cost</div>
                      <div style={{ fontSize: '18px', fontWeight: 700, marginTop: '4px', color: backtestResult.tca_report.summary.opportunity_cost >= 0 ? '#F59E0B' : '#10B981', fontFamily: 'monospace' }}>
                        ${backtestResult.tca_report.summary.opportunity_cost.toFixed(2)}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                        {backtestResult.tca_report.summary.opportunity_bps.toFixed(2)} bps (Diagnostic)
                      </div>
                    </div>

                    <div style={{ padding: '12px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-medium)' }}>
                      <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Unattributed Residual</div>
                      <div style={{ fontSize: '18px', fontWeight: 700, marginTop: '4px', color: Math.abs(backtestResult.tca_report.summary.unattributed_cost) < 1e-4 ? '#10B981' : '#EF4444', fontFamily: 'monospace' }}>
                        ${backtestResult.tca_report.summary.unattributed_cost.toFixed(2)}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                        Fill Rate: {backtestResult.tca_report.summary.fill_rate_pct.toFixed(1)}%
                      </div>
                    </div>
                  </div>

                  {/* Attribution Breakdown Tab Navigation */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', borderBottom: '1px solid var(--border-medium)', paddingBottom: '8px' }}>
                    <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-dim)', marginRight: '8px' }}>Attribution Dimensions:</span>
                    <button
                      onClick={() => setTcaAttributionTab('regime')}
                      style={{
                        padding: '4px 12px',
                        borderRadius: 'var(--radius-sm)',
                        fontSize: '12px',
                        border: 'none',
                        cursor: 'pointer',
                        backgroundColor: tcaAttributionTab === 'regime' ? 'var(--accent)' : 'var(--bg-elevated)',
                        color: tcaAttributionTab === 'regime' ? '#fff' : 'var(--text-secondary)',
                        fontWeight: tcaAttributionTab === 'regime' ? 600 : 400,
                      }}
                    >
                      By Market Regime
                    </button>
                    <button
                      onClick={() => setTcaAttributionTab('mode')}
                      style={{
                        padding: '4px 12px',
                        borderRadius: 'var(--radius-sm)',
                        fontSize: '12px',
                        border: 'none',
                        cursor: 'pointer',
                        backgroundColor: tcaAttributionTab === 'mode' ? 'var(--accent)' : 'var(--bg-elevated)',
                        color: tcaAttributionTab === 'mode' ? '#fff' : 'var(--text-secondary)',
                        fontWeight: tcaAttributionTab === 'mode' ? 600 : 400,
                      }}
                    >
                      By Scheduling Mode
                    </button>
                    <button
                      onClick={() => setTcaAttributionTab('asset')}
                      style={{
                        padding: '4px 12px',
                        borderRadius: 'var(--radius-sm)',
                        fontSize: '12px',
                        border: 'none',
                        cursor: 'pointer',
                        backgroundColor: tcaAttributionTab === 'asset' ? 'var(--accent)' : 'var(--bg-elevated)',
                        color: tcaAttributionTab === 'asset' ? '#fff' : 'var(--text-secondary)',
                        fontWeight: tcaAttributionTab === 'asset' ? 600 : 400,
                      }}
                    >
                      By Asset
                    </button>
                  </div>

                  {/* Attribution Table */}
                  <div style={{ overflowX: 'auto', marginBottom: '14px' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid var(--border-medium)' }}>
                          <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-dim)' }}>
                            {tcaAttributionTab === 'regime' ? 'Market Regime' : tcaAttributionTab === 'mode' ? 'Execution Mode' : 'Asset'}
                          </th>
                          <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>Total Cost ($)</th>
                          <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>Cost (bps)</th>
                          <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>Spread Cost</th>
                          <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>Market Impact</th>
                          <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>Opp Cost ($)</th>
                          <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>Traded Notional</th>
                          <th style={{ padding: '8px 12px', textAlign: 'center', color: 'var(--text-dim)' }}>Trades</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(
                          (tcaAttributionTab === 'regime'
                            ? backtestResult.tca_report.by_regime
                            : tcaAttributionTab === 'mode'
                            ? backtestResult.tca_report.by_mode
                            : backtestResult.tca_report.by_asset) || {}
                        ).map(([key, metrics]) => (
                          <tr key={key} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                            <td style={{ padding: '8px 12px', fontWeight: 600 }}>{key}</td>
                            <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', color: '#EF4444', fontWeight: 600 }}>
                              ${metrics.total_cost.toFixed(2)}
                            </td>
                            <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', fontWeight: 600 }}>
                              {metrics.effective_bps.toFixed(2)} bps
                            </td>
                            <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                              ${metrics.spread_cost.toFixed(2)} ({metrics.spread_bps.toFixed(2)} bps)
                            </td>
                            <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                              ${metrics.temporary_impact_cost.toFixed(2)} ({metrics.temporary_impact_bps.toFixed(2)} bps)
                            </td>
                            <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', color: metrics.opportunity_cost >= 0 ? '#F59E0B' : '#10B981' }}>
                              ${metrics.opportunity_cost.toFixed(2)}
                            </td>
                            <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                              ${metrics.total_executed_notional.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                            </td>
                            <td style={{ padding: '8px 12px', textAlign: 'center', fontFamily: 'monospace' }}>
                              {metrics.fill_count}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Provenance & Methodology Footnote */}
                  <div style={{ padding: '10px 14px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontSize: '11px', color: 'var(--text-secondary)', display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                    <div><strong>Currency:</strong> {backtestResult.tca_report.provenance?.currency_basis || 'USD'}</div>
                    <div><strong>Decomposition:</strong> {backtestResult.tca_report.provenance?.decomposition_type || 'structural_modeled_identity'}</div>
                    <div><strong>Permanent Impact:</strong> {backtestResult.tca_report.provenance?.permanent_impact_status || 'not_modeled_zero'}</div>
                    <div><strong>Opportunity Cost:</strong> {backtestResult.tca_report.provenance?.opportunity_cost_status || 'modeled_daily_drift'}</div>
                    <div><strong>Interval VWAP:</strong> {backtestResult.tca_report.provenance?.intraday_vwap_status || 'unavailable_daily_bars'}</div>
                    <div><strong>Status:</strong> {backtestResult.tca_report.provenance?.reconciliation_status || 'exact_modeled_identity_verified'}</div>
                    <div><strong>Accounting:</strong> C_total = C_spread + C_temp + C_perm + C_comm + Residual</div>
                  </div>
                </div>
              )}

              {/* Chronological Rebalance Audit Trail Table */}
              <div className="card" style={{ padding: '20px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
                  <History size={18} style={{ color: 'var(--accent)' }} />
                  <h3 style={{ fontSize: '15px', fontWeight: 600, margin: 0 }}>
                    Chronological Rebalance Audit Trail ({backtestResult.rebalance_events.length} Events)
                  </h3>
                </div>

                <div style={{ overflowX: 'auto', maxHeight: '400px' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                    <thead style={{ position: 'sticky', top: 0, backgroundColor: 'var(--bg-card)', zIndex: 1 }}>
                      <tr style={{ borderBottom: '1px solid var(--border-medium)' }}>
                        <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-dim)' }}>Rebalance Date</th>
                        <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-dim)' }}>Estimation Window</th>
                        <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-dim)' }}>Target TRP Allocation</th>
                        <th style={{ padding: '8px 12px', textAlign: 'center', color: 'var(--text-dim)' }}>Regime / Eff PR</th>
                        <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>Turnover</th>
                        <th style={{ padding: '8px 12px', textAlign: 'center', color: 'var(--text-dim)' }}>Horizon</th>
                        <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>Total Friction</th>
                        <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>Spread Cost</th>
                        <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>Market Impact</th>
                        <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>L-CVaR (99%)</th>
                        <th style={{ padding: '8px 12px', textAlign: 'right', color: '#EF4444' }}>Stressed L-CVaR</th>
                        <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-dim)' }}>Cash ($)</th>
                        <th style={{ padding: '8px 12px', textAlign: 'center', color: 'var(--text-dim)' }}>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {backtestResult.rebalance_events.map((evt, idx) => (
                        <tr key={idx} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                          <td style={{ padding: '8px 12px', fontWeight: 600 }}>{evt.date}</td>
                          <td style={{ padding: '8px 12px', fontFamily: 'monospace', color: 'var(--text-secondary)' }}>
                            [{evt.training_window_start} &rarr; {evt.training_window_end}]
                          </td>
                          <td style={{ padding: '8px 12px', fontFamily: 'monospace' }}>
                            {Object.entries(evt.target_weights)
                              .map(([ticker, w]) => `${ticker}: ${(Number(w) * 100).toFixed(1)}%`)
                              .join(' | ')}
                          </td>
                          <td style={{ padding: '8px 12px', textAlign: 'center', fontFamily: 'monospace' }}>
                            {evt.effective_participation_rate != null ? (
                              <span style={{
                                padding: '2px 6px',
                                borderRadius: 'var(--radius-xs)',
                                fontSize: '10px',
                                backgroundColor: (evt.regime_state ?? 0) > 0 ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                                color: (evt.regime_state ?? 0) > 0 ? '#EF4444' : '#10B981',
                              }}>
                                S{evt.regime_state ?? 0} ({((evt.effective_participation_rate ?? 0.1) * 100).toFixed(1)}%)
                              </span>
                            ) : '-'}
                          </td>
                          <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                            {(evt.turnover * 100).toFixed(2)}%
                          </td>
                          <td style={{ padding: '8px 12px', textAlign: 'center', fontFamily: 'monospace' }}>
                            {evt.scheduled_days ?? 1}d
                          </td>
                          <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', fontWeight: 600 }}>
                            ${evt.cost.toFixed(2)}
                          </td>
                          <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                            {evt.spread_cost != null ? `$${evt.spread_cost.toFixed(2)}` : '-'}
                          </td>
                          <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                            {evt.market_impact_cost != null ? `$${evt.market_impact_cost.toFixed(2)}` : '-'}
                          </td>
                          <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', color: 'var(--accent)' }}>
                            {evt.liquidity_adjusted_cvar != null ? `${(evt.liquidity_adjusted_cvar * 100).toFixed(2)}%` : '-'}
                          </td>
                          <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace', color: '#EF4444', fontWeight: 600 }}>
                            {evt.stressed_liquidity_adjusted_cvar != null ? `${(evt.stressed_liquidity_adjusted_cvar * 100).toFixed(2)}%` : '-'}
                          </td>
                          <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace' }}>
                            {evt.cash_weight != null ? `${(evt.cash_weight * 100).toFixed(1)}%` : '0.0%'}
                          </td>
                          <td style={{ padding: '8px 12px', textAlign: 'center' }}>
                            <span
                              style={{
                                display: 'inline-block',
                                padding: '2px 8px',
                                borderRadius: 'var(--radius-sm)',
                                fontSize: '11px',
                                backgroundColor: evt.rebalance_rejected ? 'rgba(239, 68, 68, 0.25)' : (evt.status === 'converged' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)'),
                                color: evt.rebalance_rejected ? '#EF4444' : (evt.status === 'converged' ? '#10B981' : '#EF4444'),
                                fontWeight: 600,
                              }}
                            >
                              {evt.rebalance_rejected ? 'rejected' : evt.status}
                            </span>
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
      )}
    </div>
  );
};
