import React, { useState, useEffect } from 'react';
import {
  Scale,
  PlayCircle,
  AlertTriangle,
  Info,
  CheckCircle,
  Sliders,
  Layers,
  Shield,
  Activity,
  BarChart2,
  Calendar,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { useDataset } from '../../context/DatasetContext';
import type {
  RobustOptimizationRequest,
  RobustOptimizationResponse,
  SensitivityAnalysisRequest,
  SensitivityAnalysisResponse,
  RobustBacktestRequest,
  RobustBacktestResponse,
} from '../../types/api';

type ActiveTab = 'optimization' | 'sensitivity' | 'backtest';

export const RobustOptimizationPage: React.FC = () => {
  const { currentDataset, availableAssets } = useDataset();

  // Tab State
  const [activeTab, setActiveTab] = useState<ActiveTab>('optimization');

  // Universe & Estimation Window
  const [selectedAssets, setSelectedAssets] = useState<string[]>([]);
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [riskFreeRate, setRiskFreeRate] = useState<number>(0.02);

  // Objective
  const [objective, setObjective] = useState<'max_sharpe' | 'min_variance' | 'mean_variance_utility'>('max_sharpe');
  const [riskAversion, setRiskAversion] = useState<number>(3.0);

  // Return Uncertainty
  const [uncertaintyModel, setUncertaintyModel] = useState<'box' | 'ellipsoidal' | 'none'>('box');
  const [confidenceLevel, setConfidenceLevel] = useState<number>(1.96);

  // Covariance Shrinkage
  const [shrinkageTarget, setShrinkageTarget] = useState<'diagonal' | 'scaled_identity' | 'constant_correlation' | 'none'>('diagonal');
  const [shrinkageIntensity, setShrinkageIntensity] = useState<number>(0.2);

  // Constraints
  const [minWeight, setMinWeight] = useState<number>(0.0);
  const [maxWeight, setMaxWeight] = useState<number>(1.0);
  const [maxGrossExposure, setMaxGrossExposure] = useState<number>(1.0);

  // Sensitivity Sweep Options
  const [parameterToSweep, setParameterToSweep] = useState<'max_weight' | 'uncertainty_level' | 'shrinkage_intensity'>('uncertainty_level');
  const [gridMin, setGridMin] = useState<number>(0.0);
  const [gridMax, setGridMax] = useState<number>(2.5);
  const [numSteps, setNumSteps] = useState<number>(6);

  // Backtest Options
  const [trainEndDate, setTrainEndDate] = useState<string>('');
  const [rebalanceFrequency, setRebalanceFrequency] = useState<'monthly' | 'quarterly'>('monthly');
  const [costBps, setCostBps] = useState<number>(10.0);
  const [slippageBps, setSlippageBps] = useState<number>(5.0);

  // Execution states
  const [isOptimizing, setIsOptimizing] = useState<boolean>(false);
  const [optimizationError, setOptimizationError] = useState<string | null>(null);
  const [optResult, setOptResult] = useState<RobustOptimizationResponse | null>(null);

  const [isSweeping, setIsSweeping] = useState<boolean>(false);
  const [sweepError, setSweepError] = useState<string | null>(null);
  const [sweepResult, setSweepResult] = useState<SensitivityAnalysisResponse | null>(null);

  const [isBacktesting, setIsBacktesting] = useState<boolean>(false);
  const [backtestError, setBacktestError] = useState<string | null>(null);
  const [backtestResult, setBacktestResult] = useState<RobustBacktestResponse | null>(null);

  // Initialize assets from dataset
  useEffect(() => {
    if (availableAssets.length > 0 && selectedAssets.length === 0) {
      const initial = availableAssets.slice(0, Math.min(5, availableAssets.length)).map((a) => a.asset_id);
      setSelectedAssets(initial);
    }
  }, [availableAssets]);

  const toggleAsset = (assetId: string) => {
    if (selectedAssets.includes(assetId)) {
      if (selectedAssets.length > 2) {
        setSelectedAssets(selectedAssets.filter((id) => id !== assetId));
      }
    } else {
      setSelectedAssets([...selectedAssets, assetId]);
    }
  };

  const handleRunOptimization = async () => {
    if (!currentDataset) {
      setOptimizationError('No dataset loaded. Please register a dataset in Market Data.');
      return;
    }
    if (selectedAssets.length < 2) {
      setOptimizationError('At least 2 assets are required for robust portfolio optimization.');
      return;
    }

    setIsOptimizing(true);
    setOptimizationError(null);

    const payload: RobustOptimizationRequest = {
      dataset_id: currentDataset.dataset_id,
      assets: selectedAssets,
      start_date: startDate || undefined,
      end_date: endDate || undefined,
      objective,
      risk_aversion: riskAversion,
      risk_free_rate: riskFreeRate,
      uncertainty: {
        model: uncertaintyModel,
        confidence_level: uncertaintyModel !== 'none' ? confidenceLevel : 0.0,
      },
      shrinkage: {
        target: shrinkageTarget,
        intensity: shrinkageTarget !== 'none' ? shrinkageIntensity : 0.0,
      },
      constraints: {
        default_min_weight: minWeight,
        default_max_weight: maxWeight,
        target_total_weight: 1.0,
        allow_short: false,
        max_gross_exposure: maxGrossExposure,
      },
    };

    try {
      const response = await apiClient.optimizeRobustPortfolio(payload);
      setOptResult(response);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Robust optimization failed.';
      setOptimizationError(msg);
    } finally {
      setIsOptimizing(false);
    }
  };

  const handleRunSensitivity = async () => {
    if (!currentDataset) {
      setSweepError('No dataset loaded.');
      return;
    }
    if (selectedAssets.length < 2) {
      setSweepError('At least 2 assets are required.');
      return;
    }

    setIsSweeping(true);
    setSweepError(null);

    const payload: SensitivityAnalysisRequest = {
      dataset_id: currentDataset.dataset_id,
      assets: selectedAssets,
      start_date: startDate || undefined,
      end_date: endDate || undefined,
      parameter_to_sweep: parameterToSweep,
      grid_min: gridMin,
      grid_max: gridMax,
      num_steps: numSteps,
      objective,
      uncertainty: {
        model: uncertaintyModel,
        confidence_level: confidenceLevel,
      },
      shrinkage: {
        target: shrinkageTarget,
        intensity: shrinkageIntensity,
      },
      constraints: {
        default_min_weight: minWeight,
        default_max_weight: maxWeight,
        target_total_weight: 1.0,
        allow_short: false,
        max_gross_exposure: maxGrossExposure,
      },
      risk_free_rate: riskFreeRate,
    };

    try {
      const response = await apiClient.runRobustSensitivity(payload);
      setSweepResult(response);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Sensitivity sweep failed.';
      setSweepError(msg);
    } finally {
      setIsSweeping(false);
    }
  };

  const handleRunBacktest = async () => {
    if (!currentDataset) {
      setBacktestError('No dataset loaded.');
      return;
    }
    if (selectedAssets.length < 2) {
      setBacktestError('At least 2 assets are required.');
      return;
    }
    if (!trainEndDate) {
      setBacktestError('Please specify an in-sample training end date (YYYY-MM-DD).');
      return;
    }

    setIsBacktesting(true);
    setBacktestError(null);

    const payload: RobustBacktestRequest = {
      dataset_id: currentDataset.dataset_id,
      assets: selectedAssets,
      train_end_date: trainEndDate,
      objective,
      uncertainty: {
        model: uncertaintyModel,
        confidence_level: confidenceLevel,
      },
      shrinkage: {
        target: shrinkageTarget,
        intensity: shrinkageIntensity,
      },
      constraints: {
        default_min_weight: minWeight,
        default_max_weight: maxWeight,
        target_total_weight: 1.0,
        allow_short: false,
        max_gross_exposure: maxGrossExposure,
      },
      rebalance_frequency: rebalanceFrequency,
      cost_bps: costBps,
      slippage_bps: slippageBps,
      risk_free_rate: riskFreeRate,
    };

    try {
      const response = await apiClient.runRobustBacktest(payload);
      setBacktestResult(response);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Robust out-of-sample backtest failed.';
      setBacktestError(msg);
    } finally {
      setIsBacktesting(false);
    }
  };

  return (
    <div className="page-container" style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header Banner */}
      <div style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
          <div style={{ padding: '10px', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(234, 179, 8, 0.12)', color: '#EAB308' }}>
            <Scale size={24} />
          </div>
          <div>
            <h1 style={{ fontSize: '24px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
              Robust Portfolio Optimization & Estimation Uncertainty
            </h1>
            <p style={{ margin: '4px 0 0 0', color: 'var(--text-secondary)', fontSize: '14px' }}>
              Solve portfolio allocations under explicit return uncertainty sets and regularized covariance shrinkage.
            </p>
          </div>
        </div>
      </div>

      {/* Epistemological & Risk Disclaimer Alert */}
      <div className="alert alert-info" style={{ marginBottom: '20px' }}>
        <Info size={20} style={{ flexShrink: 0, marginTop: '2px' }} />
        <div>
          <div style={{ fontWeight: 600, marginBottom: '2px' }}>Methodological Grounding & Risk Invariant</div>
          <div style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            Robust optimization constructs solutions against <em>worst-case estimation uncertainty</em> within mathematically defined bounds (Box or Ellipsoidal sets) and shrinks covariance matrices toward structured targets.
            <strong> It does not eliminate future market drawdown risk nor guarantee out-of-sample outperformance.</strong>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--border-color)', marginBottom: '24px' }}>
        <button
          onClick={() => setActiveTab('optimization')}
          className={`tab-btn ${activeTab === 'optimization' ? 'active' : ''}`}
          style={{
            padding: '10px 18px',
            fontWeight: 600,
            fontSize: '14px',
            borderBottom: activeTab === 'optimization' ? '2px solid var(--accent)' : '2px solid transparent',
            color: activeTab === 'optimization' ? 'var(--accent)' : 'var(--text-secondary)',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <Activity size={16} />
          Optimization & Diagnostics
        </button>

        <button
          onClick={() => setActiveTab('sensitivity')}
          className={`tab-btn ${activeTab === 'sensitivity' ? 'active' : ''}`}
          style={{
            padding: '10px 18px',
            fontWeight: 600,
            fontSize: '14px',
            borderBottom: activeTab === 'sensitivity' ? '2px solid var(--accent)' : '2px solid transparent',
            color: activeTab === 'sensitivity' ? 'var(--accent)' : 'var(--text-secondary)',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <Sliders size={16} />
          Constraint & Parameter Sensitivity
        </button>

        <button
          onClick={() => setActiveTab('backtest')}
          className={`tab-btn ${activeTab === 'backtest' ? 'active' : ''}`}
          style={{
            padding: '10px 18px',
            fontWeight: 600,
            fontSize: '14px',
            borderBottom: activeTab === 'backtest' ? '2px solid var(--accent)' : '2px solid transparent',
            color: activeTab === 'backtest' ? 'var(--accent)' : 'var(--text-secondary)',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <BarChart2 size={16} />
          Chronological Out-of-Sample Backtest
        </button>
      </div>

      {/* Main Grid: Controls Left (380px), Results Right */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(340px, 380px) 1fr', gap: '24px' }}>
        {/* Controls Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Asset Selection Card */}
          <div className="card" style={{ padding: '18px' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Layers size={16} color="var(--accent)" />
              Asset Universe ({selectedAssets.length} Selected)
            </h3>
            {availableAssets.length === 0 ? (
              <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                No assets available. Register a dataset in Market Data.
              </div>
            ) : (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', maxHeight: '140px', overflowY: 'auto' }}>
                {availableAssets.map((asset) => {
                  const isSelected = selectedAssets.includes(asset.asset_id);
                  return (
                    <button
                      key={asset.asset_id}
                      onClick={() => toggleAsset(asset.asset_id)}
                      className={`btn ${isSelected ? 'btn-primary' : 'btn-secondary'}`}
                      style={{
                        padding: '4px 10px',
                        fontSize: '12px',
                        borderRadius: 'var(--radius-sm)',
                      }}
                    >
                      {asset.ticker}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Estimation Window & Objective Card */}
          <div className="card" style={{ padding: '18px' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Calendar size={16} color="var(--accent)" />
              Estimation & Objective
            </h3>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '12px' }}>
              <div>
                <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                  Start Date (Opt)
                </label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="input-field"
                  style={{ width: '100%', fontSize: '12px', padding: '6px 8px' }}
                />
              </div>
              <div>
                <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                  End Date (Opt)
                </label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="input-field"
                  style={{ width: '100%', fontSize: '12px', padding: '6px 8px' }}
                />
              </div>
            </div>

            <div style={{ marginBottom: '12px' }}>
              <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                Optimization Objective
              </label>
              <select
                value={objective}
                onChange={(e) => setObjective(e.target.value as any)}
                className="input-field"
                style={{ width: '100%', fontSize: '12px', padding: '6px 8px' }}
              >
                <option value="max_sharpe">Maximum Sharpe Ratio</option>
                <option value="min_variance">Global Minimum Variance</option>
                <option value="mean_variance_utility">Mean-Variance Utility (μ - 0.5 γ σ²)</option>
              </select>
            </div>

            {objective === 'mean_variance_utility' && (
              <div style={{ marginBottom: '12px' }}>
                <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                  Risk Aversion Coefficient (γ = {riskAversion})
                </label>
                <input
                  type="range"
                  min="0.5"
                  max="10.0"
                  step="0.5"
                  value={riskAversion}
                  onChange={(e) => setRiskAversion(parseFloat(e.target.value))}
                  style={{ width: '100%' }}
                />
              </div>
            )}

            <div>
              <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                Risk-Free Rate (Annualized): {(riskFreeRate * 100).toFixed(1)}%
              </label>
              <input
                type="number"
                step="0.005"
                min="0.0"
                max="0.2"
                value={riskFreeRate}
                onChange={(e) => setRiskFreeRate(parseFloat(e.target.value) || 0.0)}
                className="input-field"
                style={{ width: '100%', fontSize: '12px', padding: '6px 8px' }}
              />
            </div>
          </div>

          {/* Uncertainty Set Formulation Card */}
          <div className="card" style={{ padding: '18px' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Shield size={16} color="#EAB308" />
              Expected Return Uncertainty Set
            </h3>

            <div style={{ marginBottom: '12px' }}>
              <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                Uncertainty Geometry
              </label>
              <select
                value={uncertaintyModel}
                onChange={(e) => setUncertaintyModel(e.target.value as any)}
                className="input-field"
                style={{ width: '100%', fontSize: '12px', padding: '6px 8px' }}
              >
                <option value="box">Box Uncertainty (Independent intervals μ_i ± κ·SE_i)</option>
                <option value="ellipsoidal">Ellipsoidal Uncertainty ((μ - μ̂)' Σ⁻¹ (μ - μ̂) ≤ κ²)</option>
                <option value="none">None (Point Estimate Baseline)</option>
              </select>
            </div>

            {uncertaintyModel !== 'none' && (
              <div>
                <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                  Robustness Parameter κ: {confidenceLevel.toFixed(2)} (95% ≈ 1.96)
                </label>
                <input
                  type="range"
                  min="0.0"
                  max="4.0"
                  step="0.1"
                  value={confidenceLevel}
                  onChange={(e) => setConfidenceLevel(parseFloat(e.target.value))}
                  style={{ width: '100%' }}
                />
              </div>
            )}
          </div>

          {/* Covariance Regularization & Shrinkage Card */}
          <div className="card" style={{ padding: '18px' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Sliders size={16} color="var(--accent)" />
              Covariance Shrinkage Target
            </h3>

            <div style={{ marginBottom: '12px' }}>
              <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                Shrinkage Target Matrix (T)
              </label>
              <select
                value={shrinkageTarget}
                onChange={(e) => setShrinkageTarget(e.target.value as any)}
                className="input-field"
                style={{ width: '100%', fontSize: '12px', padding: '6px 8px' }}
              >
                <option value="diagonal">Diagonal Sample Variances (Ledoit-Wolf Target)</option>
                <option value="scaled_identity">Scaled Identity (Equal Variance, Zero Covariance)</option>
                <option value="constant_correlation">Constant Correlation Target</option>
                <option value="none">No Shrinkage (Sample Covariance Σ)</option>
              </select>
            </div>

            {shrinkageTarget !== 'none' && (
              <div>
                <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                  Shrinkage Intensity λ = {shrinkageIntensity.toFixed(2)}: (1-λ)Σ + λT
                </label>
                <input
                  type="range"
                  min="0.0"
                  max="1.0"
                  step="0.05"
                  value={shrinkageIntensity}
                  onChange={(e) => setShrinkageIntensity(parseFloat(e.target.value))}
                  style={{ width: '100%' }}
                />
              </div>
            )}
          </div>

          {/* Portfolio Constraints Card */}
          <div className="card" style={{ padding: '18px' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Scale size={16} color="var(--accent)" />
              Portfolio Constraints
            </h3>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <div>
                <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                  Min Weight (w_min)
                </label>
                <input
                  type="number"
                  step="0.05"
                  min="-0.5"
                  max="0.5"
                  value={minWeight}
                  onChange={(e) => setMinWeight(parseFloat(e.target.value) || 0.0)}
                  className="input-field"
                  style={{ width: '100%', fontSize: '12px', padding: '6px 8px' }}
                />
              </div>
              <div>
                <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                  Max Weight (w_max)
                </label>
                <input
                  type="number"
                  step="0.05"
                  min="0.1"
                  max="1.0"
                  value={maxWeight}
                  onChange={(e) => setMaxWeight(parseFloat(e.target.value) || 1.0)}
                  className="input-field"
                  style={{ width: '100%', fontSize: '12px', padding: '6px 8px' }}
                />
              </div>
            </div>

            <div style={{ marginTop: '10px' }}>
              <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                Max Gross Exposure Cap: {maxGrossExposure.toFixed(2)}
              </label>
              <input
                type="number"
                step="0.1"
                min="0.5"
                max="2.0"
                value={maxGrossExposure}
                onChange={(e) => setMaxGrossExposure(parseFloat(e.target.value) || 1.0)}
                className="input-field"
                style={{ width: '100%', fontSize: '12px', padding: '6px 8px' }}
              />
            </div>
          </div>

          {/* Action Button */}
          {activeTab === 'optimization' && (
            <button
              onClick={handleRunOptimization}
              disabled={isOptimizing || !currentDataset}
              className="btn btn-primary"
              style={{
                width: '100%',
                padding: '12px',
                fontSize: '14px',
                fontWeight: 600,
                justifyContent: 'center',
                gap: '8px',
              }}
            >
              <PlayCircle size={18} />
              {isOptimizing ? 'Solving Robust Allocation...' : 'Execute Robust Optimization'}
            </button>
          )}

          {activeTab === 'sensitivity' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div className="card" style={{ padding: '14px' }}>
                <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                  Parameter to Sweep
                </label>
                <select
                  value={parameterToSweep}
                  onChange={(e) => {
                    const p = e.target.value as any;
                    setParameterToSweep(p);
                    if (p === 'uncertainty_level') {
                      setGridMin(0.0);
                      setGridMax(2.5);
                    } else if (p === 'shrinkage_intensity') {
                      setGridMin(0.0);
                      setGridMax(1.0);
                    } else {
                      setGridMin(0.2);
                      setGridMax(1.0);
                    }
                  }}
                  className="input-field"
                  style={{ width: '100%', fontSize: '12px', padding: '6px 8px', marginBottom: '10px' }}
                >
                  <option value="uncertainty_level">Uncertainty Radius (κ: 0.0 → 2.5)</option>
                  <option value="shrinkage_intensity">Shrinkage Intensity (λ: 0.0 → 1.0)</option>
                  <option value="max_weight">Max Position Constraint (w_max)</option>
                </select>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '10px' }}>
                  <div>
                    <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '2px' }}>
                      Grid Min
                    </label>
                    <input
                      type="number"
                      step="0.05"
                      value={gridMin}
                      onChange={(e) => setGridMin(parseFloat(e.target.value) || 0)}
                      className="input-field"
                      style={{ width: '100%', fontSize: '12px', padding: '4px 6px' }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '2px' }}>
                      Grid Max
                    </label>
                    <input
                      type="number"
                      step="0.05"
                      value={gridMax}
                      onChange={(e) => setGridMax(parseFloat(e.target.value) || 1)}
                      className="input-field"
                      style={{ width: '100%', fontSize: '12px', padding: '4px 6px' }}
                    />
                  </div>
                </div>

                <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                  Sweep Points: {numSteps} (Bounded ≤ 25)
                </label>
                <input
                  type="range"
                  min="3"
                  max="15"
                  step="1"
                  value={numSteps}
                  onChange={(e) => setNumSteps(parseInt(e.target.value, 10))}
                  style={{ width: '100%' }}
                />
              </div>

              <button
                onClick={handleRunSensitivity}
                disabled={isSweeping || !currentDataset}
                className="btn btn-primary"
                style={{
                  width: '100%',
                  padding: '12px',
                  fontSize: '14px',
                  fontWeight: 600,
                  justifyContent: 'center',
                  gap: '8px',
                }}
              >
                <Sliders size={18} />
                {isSweeping ? 'Sweeping Parameter Grid...' : 'Run Sensitivity Analysis'}
              </button>
            </div>
          )}

          {activeTab === 'backtest' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div className="card" style={{ padding: '14px' }}>
                <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                  In-Sample Train End Date (Split Point) *
                </label>
                <input
                  type="date"
                  value={trainEndDate}
                  onChange={(e) => setTrainEndDate(e.target.value)}
                  className="input-field"
                  style={{ width: '100%', fontSize: '12px', padding: '6px 8px', marginBottom: '10px' }}
                />

                <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                  Rebalance Frequency
                </label>
                <select
                  value={rebalanceFrequency}
                  onChange={(e) => setRebalanceFrequency(e.target.value as any)}
                  className="input-field"
                  style={{ width: '100%', fontSize: '12px', padding: '6px 8px', marginBottom: '10px' }}
                >
                  <option value="monthly">Monthly Rebalancing</option>
                  <option value="quarterly">Quarterly Rebalancing</option>
                </select>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                  <div>
                    <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '2px' }}>
                      Fee Bps ({costBps})
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="100"
                      value={costBps}
                      onChange={(e) => setCostBps(parseFloat(e.target.value) || 0)}
                      className="input-field"
                      style={{ width: '100%', fontSize: '12px', padding: '4px 6px' }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '2px' }}>
                      Slippage Bps ({slippageBps})
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="100"
                      value={slippageBps}
                      onChange={(e) => setSlippageBps(parseFloat(e.target.value) || 0)}
                      className="input-field"
                      style={{ width: '100%', fontSize: '12px', padding: '4px 6px' }}
                    />
                  </div>
                </div>
              </div>

              <button
                onClick={handleRunBacktest}
                disabled={isBacktesting || !currentDataset}
                className="btn btn-primary"
                style={{
                  width: '100%',
                  padding: '12px',
                  fontSize: '14px',
                  fontWeight: 600,
                  justifyContent: 'center',
                  gap: '8px',
                }}
              >
                <BarChart2 size={18} />
                {isBacktesting ? 'Simulating Out-of-Sample...' : 'Run Out-of-Sample Backtest'}
              </button>
            </div>
          )}
        </div>

        {/* Results Column */}
        <div>
          {/* TAB 1: OPTIMIZATION & DIAGNOSTICS */}
          {activeTab === 'optimization' && (
            <div>
              {optimizationError && (
                <div className="alert alert-danger" style={{ marginBottom: '16px' }}>
                  <AlertTriangle size={18} />
                  <span>{optimizationError}</span>
                </div>
              )}

              {!optResult && !isOptimizing && (
                <div className="card" style={{ padding: '60px 24px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  <Scale size={48} style={{ margin: '0 auto 16px', opacity: 0.3 }} />
                  <div style={{ fontSize: '16px', fontWeight: 600, marginBottom: '6px', color: 'var(--text-secondary)' }}>
                    No Optimization Results Yet
                  </div>
                  <div style={{ fontSize: '13px', maxWidth: '420px', margin: '0 auto' }}>
                    Select your asset universe, configure uncertainty geometry and shrinkage intensity, and click "Execute Robust Optimization" to compare baseline vs. robust solutions.
                  </div>
                </div>
              )}

              {isOptimizing && (
                <div className="card" style={{ padding: '60px 24px', textAlign: 'center' }}>
                  <div className="spinner" style={{ margin: '0 auto 16px' }} />
                  <div style={{ fontSize: '15px', fontWeight: 600 }}>Solving Robust Quadratic Allocation...</div>
                  <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Computing worst-case bounds and regularizing covariance structure.</div>
                </div>
              )}

              {optResult && !isOptimizing && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  {/* Status Banner */}
                  <div
                    className="card"
                    style={{
                      padding: '14px 18px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      borderLeft: optResult.is_feasible ? '4px solid var(--success)' : '4px solid var(--danger)',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      {optResult.is_feasible ? (
                        <CheckCircle size={20} color="var(--success)" />
                      ) : (
                        <AlertTriangle size={20} color="var(--danger)" />
                      )}
                      <div>
                        <div style={{ fontWeight: 600, fontSize: '14px' }}>
                          Robust Allocation {optResult.is_feasible ? 'Feasible & Converged' : 'Infeasible'}
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                          Status: {optResult.solver_status} • {optResult.solver_message}
                        </div>
                      </div>
                    </div>
                    <div style={{ textAlign: 'right', fontSize: '12px', color: 'var(--text-secondary)' }}>
                      <div>Objective: {optResult.objective}</div>
                      <div>Assets: {optResult.assets.length} items</div>
                    </div>
                  </div>

                  {/* High-Level Comparison Metrics */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '14px' }}>
                    <div className="metric-card">
                      <div className="metric-label">Expected Return (Nominal)</div>
                      <div className="metric-value" style={{ fontSize: '18px' }}>
                        {optResult.robust_metrics?.nominal_return !== undefined
                          ? `${(optResult.robust_metrics.nominal_return * 100).toFixed(2)}%`
                          : '—'}
                      </div>
                      <div className="metric-sub">
                        <span>Baseline: {(Number(optResult.baseline_metrics?.nominal_return || 0) * 100).toFixed(2)}%</span>
                      </div>
                    </div>

                    <div className="metric-card">
                      <div className="metric-label">Worst-Case Expected Return</div>
                      <div className="metric-value" style={{ fontSize: '18px', color: '#EAB308' }}>
                        {optResult.robust_metrics?.worst_case_return !== undefined
                          ? `${(optResult.robust_metrics.worst_case_return * 100).toFixed(2)}%`
                          : '—'}
                      </div>
                      <div className="metric-sub">
                        <span>Under robust uncertainty set</span>
                      </div>
                    </div>

                    <div className="metric-card">
                      <div className="metric-label">Annualized Volatility</div>
                      <div className="metric-value" style={{ fontSize: '18px' }}>
                        {optResult.robust_metrics?.volatility !== undefined
                          ? `${(optResult.robust_metrics.volatility * 100).toFixed(2)}%`
                          : '—'}
                      </div>
                      <div className="metric-sub">
                        <span>Baseline: {(Number(optResult.baseline_metrics?.volatility || 0) * 100).toFixed(2)}%</span>
                      </div>
                    </div>

                    <div className="metric-card">
                      <div className="metric-label">Sharpe Ratio (Nominal)</div>
                      <div className="metric-value" style={{ fontSize: '18px' }}>
                        {optResult.robust_metrics?.sharpe_ratio !== undefined && optResult.robust_metrics?.sharpe_ratio !== null
                          ? Number(optResult.robust_metrics.sharpe_ratio).toFixed(2)
                          : '—'}
                      </div>
                      <div className="metric-sub">
                        <span>Baseline: {optResult.baseline_metrics?.sharpe_ratio ? Number(optResult.baseline_metrics.sharpe_ratio).toFixed(2) : '—'}</span>
                      </div>
                    </div>
                  </div>

                  {/* Stability & Distance Diagnostics */}
                  <div className="card" style={{ padding: '18px' }}>
                    <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Activity size={16} color="var(--accent)" />
                      Allocation Stability & Concentration Diagnostics
                    </h3>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '14px' }}>
                      <div style={{ padding: '12px', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-secondary)' }}>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>D₁ Weight Distance</div>
                        <div style={{ fontSize: '16px', fontWeight: 700 }}>
                          {optResult.diagnostics?.weight_distance_d1 !== undefined
                            ? `${(Number(optResult.diagnostics.weight_distance_d1) * 100).toFixed(1)}%`
                            : '—'}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Σ |w_robust - w_base|</div>
                      </div>

                      <div style={{ padding: '12px', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-secondary)' }}>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>Max Single Weight Shift</div>
                        <div style={{ fontSize: '16px', fontWeight: 700 }}>
                          {optResult.diagnostics?.max_weight_shift !== undefined
                            ? `${(Number(optResult.diagnostics.max_weight_shift) * 100).toFixed(1)}%`
                            : '—'}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Asset: {optResult.diagnostics?.max_weight_shift_asset || '—'}</div>
                      </div>

                      <div style={{ padding: '12px', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-secondary)' }}>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>Effective Asset Count (N_eff)</div>
                        <div style={{ fontSize: '16px', fontWeight: 700 }}>
                          {optResult.diagnostics?.robust_n_eff !== undefined
                            ? Number(optResult.diagnostics.robust_n_eff).toFixed(2)
                            : '—'}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          Base: {optResult.diagnostics?.baseline_n_eff !== undefined ? Number(optResult.diagnostics.baseline_n_eff).toFixed(2) : '—'}
                        </div>
                      </div>

                      <div style={{ padding: '12px', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-secondary)' }}>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>Herfindahl Index (HHI)</div>
                        <div style={{ fontSize: '16px', fontWeight: 700 }}>
                          {optResult.diagnostics?.robust_hhi !== undefined
                            ? Number(optResult.diagnostics.robust_hhi).toFixed(3)
                            : '—'}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          Base: {optResult.diagnostics?.baseline_hhi !== undefined ? Number(optResult.diagnostics.baseline_hhi).toFixed(3) : '—'}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Side-by-Side Asset Weights Table */}
                  <div className="card" style={{ padding: '18px' }}>
                    <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <BarChart2 size={16} color="var(--accent)" />
                      Asset Allocation Comparison: Baseline vs. Robust
                    </h3>

                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid var(--border-color)', textAlign: 'left', color: 'var(--text-muted)' }}>
                          <th style={{ padding: '8px 10px' }}>Asset</th>
                          <th style={{ padding: '8px 10px' }}>Baseline Weight</th>
                          <th style={{ padding: '8px 10px' }}>Robust Weight</th>
                          <th style={{ padding: '8px 10px' }}>Net Shift (Δ)</th>
                          <th style={{ padding: '8px 10px' }}>Nominal Return (μ̂)</th>
                          <th style={{ padding: '8px 10px' }}>Worst-Case (μ_worst)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {optResult.weights.map((item) => (
                          <tr key={item.asset_id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                            <td style={{ padding: '10px', fontWeight: 600 }}>{item.asset_id}</td>
                            <td style={{ padding: '10px' }}>{(item.baseline_weight * 100).toFixed(1)}%</td>
                            <td style={{ padding: '10px', fontWeight: 600, color: 'var(--accent)' }}>
                              {(item.robust_weight * 100).toFixed(1)}%
                            </td>
                            <td
                              style={{
                                padding: '10px',
                                fontWeight: 600,
                                color: item.weight_difference > 0 ? 'var(--success)' : item.weight_difference < 0 ? 'var(--danger)' : 'var(--text-muted)',
                              }}
                            >
                              {item.weight_difference > 0 ? `+${(item.weight_difference * 100).toFixed(1)}%` : `${(item.weight_difference * 100).toFixed(1)}%`}
                            </td>
                            <td style={{ padding: '10px' }}>{(item.nominal_return * 100).toFixed(2)}%</td>
                            <td style={{ padding: '10px', color: '#EAB308' }}>{(item.worst_case_return * 100).toFixed(2)}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 2: CONSTRAINT & PARAMETER SENSITIVITY */}
          {activeTab === 'sensitivity' && (
            <div>
              {sweepError && (
                <div className="alert alert-danger" style={{ marginBottom: '16px' }}>
                  <AlertTriangle size={18} />
                  <span>{sweepError}</span>
                </div>
              )}

              {!sweepResult && !isSweeping && (
                <div className="card" style={{ padding: '60px 24px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  <Sliders size={48} style={{ margin: '0 auto 16px', opacity: 0.3 }} />
                  <div style={{ fontSize: '16px', fontWeight: 600, marginBottom: '6px', color: 'var(--text-secondary)' }}>
                    No Sensitivity Sweep Generated
                  </div>
                  <div style={{ fontSize: '13px', maxWidth: '420px', margin: '0 auto' }}>
                    Configure a parameter to sweep (uncertainty multiplier κ, shrinkage intensity λ, or max weight cap w_max) and click "Run Sensitivity Analysis".
                  </div>
                </div>
              )}

              {isSweeping && (
                <div className="card" style={{ padding: '60px 24px', textAlign: 'center' }}>
                  <div className="spinner" style={{ margin: '0 auto 16px' }} />
                  <div style={{ fontSize: '15px', fontWeight: 600 }}>Executing Sensitivity Sweep...</div>
                  <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Solving portfolio allocations across parameter grid.</div>
                </div>
              )}

              {sweepResult && !isSweeping && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  <div className="card" style={{ padding: '18px' }}>
                    <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Activity size={16} color="var(--accent)" />
                      Sensitivity Sweep Results: {sweepResult.parameter_name} ({sweepResult.parameter_description})
                    </h3>

                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid var(--border-color)', textAlign: 'left', color: 'var(--text-muted)' }}>
                          <th style={{ padding: '8px 10px' }}>Parameter Value</th>
                          <th style={{ padding: '8px 10px' }}>Feasible</th>
                          <th style={{ padding: '8px 10px' }}>Exp Return (Worst)</th>
                          <th style={{ padding: '8px 10px' }}>Exp Return (Nom)</th>
                          <th style={{ padding: '8px 10px' }}>Volatility</th>
                          <th style={{ padding: '8px 10px' }}>Sharpe</th>
                          <th style={{ padding: '8px 10px' }}>D₁ Distance</th>
                          <th style={{ padding: '8px 10px' }}>N_eff</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sweepResult.points.map((pt, idx) => (
                          <tr key={idx} style={{ borderBottom: '1px solid var(--border-color)' }}>
                            <td style={{ padding: '10px', fontWeight: 600 }}>{pt.parameter_label}</td>
                            <td style={{ padding: '10px' }}>
                              {pt.is_feasible ? (
                                <span style={{ color: 'var(--success)', fontWeight: 600 }}>Feasible</span>
                              ) : (
                                <span style={{ color: 'var(--danger)', fontWeight: 600 }}>Infeasible</span>
                              )}
                            </td>
                            <td style={{ padding: '10px', color: '#EAB308' }}>
                              {pt.worst_case_expected_return !== null ? `${(pt.worst_case_expected_return * 100).toFixed(2)}%` : '—'}
                            </td>
                            <td style={{ padding: '10px' }}>
                              {pt.nominal_expected_return !== null ? `${(pt.nominal_expected_return * 100).toFixed(2)}%` : '—'}
                            </td>
                            <td style={{ padding: '10px' }}>
                              {pt.volatility !== null ? `${(pt.volatility * 100).toFixed(2)}%` : '—'}
                            </td>
                            <td style={{ padding: '10px' }}>
                              {pt.sharpe_ratio !== null && pt.sharpe_ratio !== undefined ? pt.sharpe_ratio.toFixed(2) : '—'}
                            </td>
                            <td style={{ padding: '10px' }}>
                              {pt.weight_distance_d1 !== null ? `${(pt.weight_distance_d1 * 100).toFixed(1)}%` : '—'}
                            </td>
                            <td style={{ padding: '10px' }}>
                              {pt.effective_assets !== null ? pt.effective_assets.toFixed(2) : '—'}
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

          {/* TAB 3: OUT-OF-SAMPLE BACKTEST */}
          {activeTab === 'backtest' && (
            <div>
              {backtestError && (
                <div className="alert alert-danger" style={{ marginBottom: '16px' }}>
                  <AlertTriangle size={18} />
                  <span>{backtestError}</span>
                </div>
              )}

              {!backtestResult && !isBacktesting && (
                <div className="card" style={{ padding: '60px 24px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  <BarChart2 size={48} style={{ margin: '0 auto 16px', opacity: 0.3 }} />
                  <div style={{ fontSize: '16px', fontWeight: 600, marginBottom: '6px', color: 'var(--text-secondary)' }}>
                    No Out-of-Sample Backtest Results Yet
                  </div>
                  <div style={{ fontSize: '13px', maxWidth: '440px', margin: '0 auto' }}>
                    Configure the in-sample training split date and rebalancing frequency, then click "Run Out-of-Sample Backtest" to evaluate baseline vs. robust allocations out-of-sample with realistic transaction costs.
                  </div>
                </div>
              )}

              {isBacktesting && (
                <div className="card" style={{ padding: '60px 24px', textAlign: 'center' }}>
                  <div className="spinner" style={{ margin: '0 auto 16px' }} />
                  <div style={{ fontSize: '15px', fontWeight: 600 }}>Simulating Out-of-Sample Returns...</div>
                  <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Executing chronological walk-forward backtest with transaction costs.</div>
                </div>
              )}

              {backtestResult && !isBacktesting && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  {/* Summary Comparison Cards */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '14px' }}>
                    <div className="metric-card">
                      <div className="metric-label">Annualized Return (Net)</div>
                      <div className="metric-value" style={{ fontSize: '18px', color: 'var(--accent)' }}>
                        {(Number(backtestResult.robust_kpis?.annualized_return || 0) * 100).toFixed(2)}%
                      </div>
                      <div className="metric-sub">
                        <span>Baseline: {(Number(backtestResult.baseline_kpis?.annualized_return || 0) * 100).toFixed(2)}%</span>
                      </div>
                    </div>

                    <div className="metric-card">
                      <div className="metric-label">Annualized Volatility (Net)</div>
                      <div className="metric-value" style={{ fontSize: '18px' }}>
                        {(Number(backtestResult.robust_kpis?.volatility || 0) * 100).toFixed(2)}%
                      </div>
                      <div className="metric-sub">
                        <span>Baseline: {(Number(backtestResult.baseline_kpis?.volatility || 0) * 100).toFixed(2)}%</span>
                      </div>
                    </div>

                    <div className="metric-card">
                      <div className="metric-label">Out-of-Sample Sharpe</div>
                      <div className="metric-value" style={{ fontSize: '18px' }}>
                        {backtestResult.robust_kpis?.sharpe_ratio !== undefined && backtestResult.robust_kpis?.sharpe_ratio !== null
                          ? Number(backtestResult.robust_kpis.sharpe_ratio).toFixed(2)
                          : '—'}
                      </div>
                      <div className="metric-sub">
                        <span>Baseline: {backtestResult.baseline_kpis?.sharpe_ratio !== undefined ? Number(backtestResult.baseline_kpis.sharpe_ratio).toFixed(2) : '—'}</span>
                      </div>
                    </div>

                    <div className="metric-card">
                      <div className="metric-label">Max Drawdown (Net)</div>
                      <div className="metric-value" style={{ fontSize: '18px', color: 'var(--danger)' }}>
                        {(Number(backtestResult.robust_kpis?.max_drawdown || 0) * 100).toFixed(2)}%
                      </div>
                      <div className="metric-sub">
                        <span>Baseline: {(Number(backtestResult.baseline_kpis?.max_drawdown || 0) * 100).toFixed(2)}%</span>
                      </div>
                    </div>
                  </div>

                  {/* Window & Cost Diagnostics */}
                  <div className="card" style={{ padding: '18px' }}>
                    <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '14px' }}>
                      Chronological Backtest Audit & Execution Friction
                    </h3>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '14px', fontSize: '13px' }}>
                      <div>
                        <div style={{ color: 'var(--text-muted)', marginBottom: '4px' }}>Training Window (In-Sample)</div>
                        <div style={{ fontWeight: 600 }}>{backtestResult.train_period.start} → {backtestResult.train_period.end}</div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Estimated strictly prior to test window</div>
                      </div>
                      <div>
                        <div style={{ color: 'var(--text-muted)', marginBottom: '4px' }}>Evaluation Window (Out-of-Sample)</div>
                        <div style={{ fontWeight: 600 }}>{backtestResult.test_period.start} → {backtestResult.test_period.end}</div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Zero look-ahead bias</div>
                      </div>
                      <div>
                        <div style={{ color: 'var(--text-muted)', marginBottom: '4px' }}>Execution Friction (Costs)</div>
                        <div style={{ fontWeight: 600 }}>
                          ${Number(backtestResult.robust_kpis?.friction_costs || 0).toFixed(2)} (Robust)
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          Baseline: ${Number(backtestResult.baseline_kpis?.friction_costs || 0).toFixed(2)}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
