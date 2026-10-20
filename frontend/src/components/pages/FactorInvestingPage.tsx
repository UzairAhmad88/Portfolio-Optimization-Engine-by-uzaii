import React, { useState, useEffect } from 'react';
import {
  Cpu,
  Sliders,
  Play,
  PlayCircle,
  TrendingUp,
  CheckCircle2,
  XCircle,
  BarChart3,
  PieChart,
  ShieldAlert,
  Activity,
  History,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { useDataset } from '../../context/DatasetContext';
import type {
  DynamicFactorBacktestRequest,
  DynamicFactorBacktestResponse,
  FactorAttributionRequest,
  FactorAttributionResponse,
  FactorConstrainedOptimizeRequest,
  FactorConstrainedOptimizeResponse,
} from '../../types/api';

type ActiveTab = 'attribution' | 'optimization' | 'backtest';

export const FactorInvestingPage: React.FC = () => {
  const { currentDataset, availableAssets } = useDataset();

  // Tab State
  const [activeTab, setActiveTab] = useState<ActiveTab>('attribution');

  // Shared Parameters
  const [factorModel, setFactorModel] = useState<'capm' | 'ff3' | 'carhart4' | 'pca'>('carhart4');
  const [numPcaFactors, setNumPcaFactors] = useState<number>(3);
  const [riskFreeRate, setRiskFreeRate] = useState<number>(0.02);

  // Attribution State
  const [customWeights, setCustomWeights] = useState<Record<string, number>>({});
  const [useCustomWeights, setUseCustomWeights] = useState<boolean>(false);
  const [isAttributing, setIsAttributing] = useState<boolean>(false);
  const [attributionError, setAttributionError] = useState<string | null>(null);
  const [attributionResult, setAttributionResult] = useState<FactorAttributionResponse | null>(null);

  // Optimization State
  const [objective, setObjective] = useState<'min_variance' | 'max_sharpe' | 'max_utility'>('min_variance');
  const [riskAversion, setRiskAversion] = useState<number>(2.5);
  const [minWeight, setMinWeight] = useState<number>(0.0);
  const [maxWeight, setMaxWeight] = useState<number>(1.0);
  const [factorBounds, setFactorBounds] = useState<Record<string, { min_beta: string; max_beta: string }>>({
    MKT: { min_beta: '0.8', max_beta: '1.2' },
    SMB: { min_beta: '-0.5', max_beta: '0.5' },
    HML: { min_beta: '-0.5', max_beta: '0.5' },
    MOM: { min_beta: '-0.5', max_beta: '0.5' },
  });
  const [isOptimizing, setIsOptimizing] = useState<boolean>(false);
  const [optimizationError, setOptimizationError] = useState<string | null>(null);
  const [optimizationResult, setOptimizationResult] = useState<FactorConstrainedOptimizeResponse | null>(null);

  // Dynamic Backtesting State
  const [strategyType, setStrategyType] = useState<'factor_tilt' | 'factor_min_variance' | 'factor_momentum_rotation'>('factor_tilt');
  const [estimationWindow, setEstimationWindow] = useState<number>(60);
  const [rebalanceFrequency, setRebalanceFrequency] = useState<'daily' | 'weekly' | 'biweekly' | 'monthly' | 'quarterly'>('monthly');
  const [backtestModel, setBacktestModel] = useState<'capm' | 'ff3' | 'carhart4' | 'pca'>('carhart4');
  const [backtestNumPca, setBacktestNumPca] = useState<number>(3);
  const [factorTilts, setFactorTilts] = useState<Record<string, number>>({
    MKT: 1.0,
    MOM: 0.5,
    HML: 0.2,
    SMB: -0.2,
  });
  const [transactionCostBps, setTransactionCostBps] = useState<number>(10.0);
  const [slippageBps, setSlippageBps] = useState<number>(5.0);
  const [turnoverPenalty, setTurnoverPenalty] = useState<number>(0.001);
  const [topNAssets, setTopNAssets] = useState<number>(5);
  const [initialCapital, setInitialCapital] = useState<number>(100000);
  const [backtestRiskAversion, setBacktestRiskAversion] = useState<number>(2.5);
  const [backtestMinWeight, setBacktestMinWeight] = useState<number>(0.0);
  const [backtestMaxWeight, setBacktestMaxWeight] = useState<number>(0.4);

  const [isBacktesting, setIsBacktesting] = useState<boolean>(false);
  const [backtestError, setBacktestError] = useState<string | null>(null);
  const [backtestResult, setBacktestResult] = useState<DynamicFactorBacktestResponse | null>(null);

  // Initialize weights when available assets update
  useEffect(() => {
    if (availableAssets.length > 0) {
      const n = availableAssets.length;
      const initial: Record<string, number> = {};
      availableAssets.forEach((a) => {
        initial[a.asset_id] = Number((1.0 / n).toFixed(4));
      });
      setCustomWeights(initial);
    }
  }, [availableAssets]);

  const handleWeightChange = (assetId: string, val: number) => {
    setCustomWeights((prev) => ({
      ...prev,
      [assetId]: Math.max(0, val),
    }));
  };

  const normalizeWeights = () => {
    const sum = Object.values(customWeights).reduce((a, b) => a + b, 0);
    if (sum > 0) {
      const normalized: Record<string, number> = {};
      Object.entries(customWeights).forEach(([k, v]) => {
        normalized[k] = Number((v / sum).toFixed(4));
      });
      setCustomWeights(normalized);
    }
  };

  const handleRunAttribution = async () => {
    if (!currentDataset) {
      setAttributionError('Please select or upload a dataset first.');
      return;
    }

    setIsAttributing(true);
    setAttributionError(null);

    try {
      const req: FactorAttributionRequest = {
        dataset_id: currentDataset.dataset_id,
        factor_model: factorModel,
        num_pca_factors: factorModel === 'pca' ? numPcaFactors : undefined,
        risk_free_rate: riskFreeRate,
        weights: useCustomWeights ? customWeights : undefined,
      };

      const res = await apiClient.attributeFactorRisk(req);
      setAttributionResult(res);

      // Pre-populate optimization factor bounds with available factors
      if (res.factors && res.factors.length > 0) {
        setFactorBounds((prev) => {
          const next = { ...prev };
          res.factors.forEach((f) => {
            if (!next[f]) {
              next[f] = { min_beta: '-1.0', max_beta: '1.0' };
            }
          });
          return next;
        });
      }
    } catch (err: any) {
      setAttributionError(err?.message || 'Failed to compute factor risk attribution.');
    } finally {
      setIsAttributing(false);
    }
  };

  const handleRunOptimization = async () => {
    if (!currentDataset) {
      setOptimizationError('Please select or upload a dataset first.');
      return;
    }

    setIsOptimizing(true);
    setOptimizationError(null);

    try {
      const parsedConstraints: Record<string, { min_beta?: number; max_beta?: number }> = {};
      Object.entries(factorBounds).forEach(([fname, bound]) => {
        const c: { min_beta?: number; max_beta?: number } = {};
        if (bound.min_beta.trim() !== '') {
          c.min_beta = parseFloat(bound.min_beta);
        }
        if (bound.max_beta.trim() !== '') {
          c.max_beta = parseFloat(bound.max_beta);
        }
        if (c.min_beta !== undefined || c.max_beta !== undefined) {
          parsedConstraints[fname] = c;
        }
      });

      const req: FactorConstrainedOptimizeRequest = {
        dataset_id: currentDataset.dataset_id,
        factor_model: factorModel,
        num_pca_factors: factorModel === 'pca' ? numPcaFactors : undefined,
        objective,
        risk_aversion: riskAversion,
        risk_free_rate: riskFreeRate,
        min_weight: minWeight,
        max_weight: maxWeight,
        factor_constraints: parsedConstraints,
      };

      const res = await apiClient.optimizeFactorConstrained(req);
      setOptimizationResult(res);
    } catch (err: any) {
      setOptimizationError(err?.message || 'Failed to solve factor-constrained portfolio.');
    } finally {
      setIsOptimizing(false);
    }
  };

  const handleRunBacktest = async () => {
    if (!currentDataset) {
      setBacktestError('Please select or upload a dataset first.');
      return;
    }
    setIsBacktesting(true);
    setBacktestError(null);

    try {
      const req: DynamicFactorBacktestRequest = {
        dataset_id: currentDataset.dataset_id,
        factor_model: backtestModel,
        num_pca_factors: backtestModel === 'pca' ? backtestNumPca : undefined,
        strategy_type: strategyType,
        estimation_window: estimationWindow,
        rebalance_frequency: rebalanceFrequency,
        factor_tilts: strategyType === 'factor_tilt' || strategyType === 'factor_momentum_rotation' ? factorTilts : undefined,
        top_n_assets: strategyType === 'factor_momentum_rotation' ? topNAssets : undefined,
        risk_aversion: backtestRiskAversion,
        turnover_penalty: turnoverPenalty,
        min_weight: backtestMinWeight,
        max_weight: backtestMaxWeight,
        transaction_cost_bps: transactionCostBps,
        slippage_bps: slippageBps,
        initial_capital: initialCapital,
        risk_free_rate: riskFreeRate,
      };
      const res = await apiClient.backtestDynamicFactors(req);
      setBacktestResult(res);
    } catch (err: any) {
      setBacktestError(err?.message || 'Dynamic factor backtest simulation failed.');
    } finally {
      setIsBacktesting(false);
    }
  };

  return (
    <div className="page-container" style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header Info */}
      <div style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '20px', fontWeight: 700, margin: '0 0 6px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Cpu className="text-primary" size={22} />
          Multi-Factor Risk Modeling & Systematic Attribution
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '13px', margin: 0 }}>
          Barra-style structural factor decomposition, Fama-French & Carhart exposures, systematic vs. idiosyncratic variance attribution, and factor-tilted portfolio optimization.
        </p>
      </div>

      {/* Dataset Warning */}
      {!currentDataset && (
        <div className="card" style={{ padding: '16px', marginBottom: '20px', backgroundColor: 'rgba(239, 68, 68, 0.08)', borderColor: 'rgba(239, 68, 68, 0.2)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#EF4444', fontSize: '13px' }}>
            <ShieldAlert size={18} />
            <span>No dataset currently active. Please select or upload a dataset in Market Data before executing factor analytics.</span>
          </div>
        </div>
      )}

      {/* Navigation Tabs */}
      <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--border-subtle)', marginBottom: '20px' }}>
        <button
          onClick={() => setActiveTab('attribution')}
          className="btn"
          style={{
            padding: '8px 16px',
            borderRadius: '6px 6px 0 0',
            backgroundColor: activeTab === 'attribution' ? 'var(--bg-card)' : 'transparent',
            borderBottom: activeTab === 'attribution' ? '2px solid var(--primary)' : 'none',
            color: activeTab === 'attribution' ? 'var(--text-primary)' : 'var(--text-secondary)',
            fontWeight: activeTab === 'attribution' ? 600 : 400,
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <BarChart3 size={16} />
          Factor Risk Attribution
        </button>
        <button
          onClick={() => setActiveTab('optimization')}
          className="btn"
          style={{
            padding: '8px 16px',
            borderRadius: '6px 6px 0 0',
            backgroundColor: activeTab === 'optimization' ? 'var(--bg-card)' : 'transparent',
            borderBottom: activeTab === 'optimization' ? '2px solid var(--primary)' : 'none',
            color: activeTab === 'optimization' ? 'var(--text-primary)' : 'var(--text-secondary)',
            fontWeight: activeTab === 'optimization' ? 600 : 400,
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <Sliders size={16} />
          Factor-Constrained Optimization
        </button>
        <button
          onClick={() => setActiveTab('backtest')}
          className="btn"
          style={{
            padding: '8px 16px',
            borderRadius: '6px 6px 0 0',
            backgroundColor: activeTab === 'backtest' ? 'var(--bg-card)' : 'transparent',
            borderBottom: activeTab === 'backtest' ? '2px solid var(--primary)' : 'none',
            color: activeTab === 'backtest' ? 'var(--text-primary)' : 'var(--text-secondary)',
            fontWeight: activeTab === 'backtest' ? 600 : 400,
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <PlayCircle size={16} />
          Dynamic Walk-Forward Backtesting
        </button>
      </div>

      {/* TAB 1: FACTOR RISK ATTRIBUTION */}
      {activeTab === 'attribution' && (
        <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '20px' }}>
          {/* Controls Sidebar */}
          <div className="card" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 600, margin: 0, display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Sliders size={15} /> Model Parameters
            </h3>

            {/* Model Archetype */}
            <div>
              <label style={{ fontSize: '12px', fontWeight: 500, display: 'block', marginBottom: '6px' }}>
                Factor Model Archetype
              </label>
              <select
                className="input-select"
                value={factorModel}
                onChange={(e) => setFactorModel(e.target.value as any)}
                style={{ width: '100%' }}
              >
                <option value="capm">CAPM (1-Factor Market)</option>
                <option value="ff3">Fama-French 3-Factor (MKT, SMB, HML)</option>
                <option value="carhart4">Carhart 4-Factor (MKT, SMB, HML, MOM)</option>
                <option value="pca">PCA Statistical Eigen-Factors</option>
              </select>
            </div>

            {/* PCA factor count if applicable */}
            {factorModel === 'pca' && (
              <div>
                <label style={{ fontSize: '12px', fontWeight: 500, display: 'block', marginBottom: '6px' }}>
                  Principal Components (K)
                </label>
                <input
                  type="number"
                  min={1}
                  max={5}
                  value={numPcaFactors}
                  onChange={(e) => setNumPcaFactors(parseInt(e.target.value) || 3)}
                  className="input-text"
                  style={{ width: '100%' }}
                />
              </div>
            )}

            {/* Risk-free Rate */}
            <div>
              <label style={{ fontSize: '12px', fontWeight: 500, display: 'block', marginBottom: '6px' }}>
                Risk-Free Rate (Annualized)
              </label>
              <input
                type="number"
                step="0.005"
                value={riskFreeRate}
                onChange={(e) => setRiskFreeRate(parseFloat(e.target.value) || 0.02)}
                className="input-text"
                style={{ width: '100%' }}
              />
            </div>

            {/* Portfolio Weights Mode */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                <label style={{ fontSize: '12px', fontWeight: 500 }}>Custom Portfolio Weights</label>
                <input
                  type="checkbox"
                  checked={useCustomWeights}
                  onChange={(e) => setUseCustomWeights(e.target.checked)}
                />
              </div>
              {useCustomWeights && (
                <div style={{ maxHeight: '180px', overflowY: 'auto', border: '1px solid var(--border-subtle)', borderRadius: '4px', padding: '8px' }}>
                  {availableAssets.map((a) => (
                    <div key={a.asset_id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px', fontSize: '11px' }}>
                      <span>{a.ticker}</span>
                      <input
                        type="number"
                        step="0.05"
                        min="0"
                        value={customWeights[a.asset_id] ?? 0}
                        onChange={(e) => handleWeightChange(a.asset_id, parseFloat(e.target.value) || 0)}
                        style={{ width: '70px', padding: '2px 4px', fontSize: '11px' }}
                      />
                    </div>
                  ))}
                  <button onClick={normalizeWeights} className="btn btn-outline" style={{ width: '100%', fontSize: '11px', marginTop: '6px', padding: '4px' }}>
                    Normalize Sum to 1.0
                  </button>
                </div>
              )}
            </div>

            {/* Execute Button */}
            <button
              onClick={handleRunAttribution}
              disabled={isAttributing || !currentDataset}
              className="btn btn-primary"
              style={{ width: '100%', padding: '10px', marginTop: '8px', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px' }}
            >
              {isAttributing ? (
                <>
                  <div className="loading-spinner" style={{ width: '14px', height: '14px' }}></div>
                  Decomposing Risk...
                </>
              ) : (
                <>
                  <Play size={15} /> Compute Factor Attribution
                </>
              )}
            </button>

            {attributionError && (
              <div style={{ color: '#EF4444', fontSize: '11px', marginTop: '4px', lineHeight: 1.4 }}>
                {attributionError}
              </div>
            )}
          </div>

          {/* Attribution Results Panel */}
          <div>
            {!attributionResult ? (
              <div className="card" style={{ padding: '48px 24px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                <PieChart size={36} style={{ margin: '0 auto 12px auto', opacity: 0.4 }} />
                <h4 style={{ fontSize: '15px', fontWeight: 600, margin: '0 0 6px 0' }}>No Factor Attribution Results</h4>
                <p style={{ fontSize: '13px', margin: 0 }}>
                  Select a factor model archetype on the left and click "Compute Factor Attribution" to decompose systematic vs idiosyncratic risk.
                </p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                {/* KPI Metrics Row */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '14px' }}>
                  <div className="card" style={{ padding: '14px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '4px' }}>Total Volatility</div>
                    <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)' }}>
                      {(attributionResult.risk_decomposition.total_volatility * 100).toFixed(2)}%
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Annualized portfolio risk</div>
                  </div>

                  <div className="card" style={{ padding: '14px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '4px' }}>Systematic Risk</div>
                    <div style={{ fontSize: '20px', fontWeight: 700, color: '#0EA5E9' }}>
                      {(attributionResult.risk_decomposition.systematic_volatility * 100).toFixed(2)}%
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                      {attributionResult.risk_decomposition.systematic_share_pct.toFixed(1)}% of total variance
                    </div>
                  </div>

                  <div className="card" style={{ padding: '14px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '4px' }}>Specific / Idio Risk</div>
                    <div style={{ fontSize: '20px', fontWeight: 700, color: '#F59E0B' }}>
                      {(attributionResult.risk_decomposition.idiosyncratic_volatility * 100).toFixed(2)}%
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                      {attributionResult.risk_decomposition.idiosyncratic_share_pct.toFixed(1)}% of total variance
                    </div>
                  </div>

                  <div className="card" style={{ padding: '14px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '4px' }}>Market Beta</div>
                    <div style={{ fontSize: '20px', fontWeight: 700, color: '#10B981' }}>
                      {(attributionResult.portfolio_betas?.['MKT'] ?? 1.0).toFixed(3)}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Market sensitivity</div>
                  </div>
                </div>

                {/* Variance Decomposition Bar */}
                <div className="card" style={{ padding: '16px' }}>
                  <h4 style={{ fontSize: '13px', fontWeight: 600, margin: '0 0 12px 0' }}>Barra Structural Variance Decomposition</h4>
                  <div style={{ height: '20px', width: '100%', borderRadius: '4px', overflow: 'hidden', display: 'flex', marginBottom: '8px' }}>
                    <div
                      style={{
                        width: `${attributionResult.risk_decomposition.systematic_share_pct}%`,
                        backgroundColor: '#0EA5E9',
                        transition: 'width 0.4s ease',
                      }}
                      title={`Systematic Risk: ${attributionResult.risk_decomposition.systematic_share_pct.toFixed(1)}%`}
                    />
                    <div
                      style={{
                        width: `${attributionResult.risk_decomposition.idiosyncratic_share_pct}%`,
                        backgroundColor: '#F59E0B',
                        transition: 'width 0.4s ease',
                      }}
                      title={`Idiosyncratic Risk: ${attributionResult.risk_decomposition.idiosyncratic_share_pct.toFixed(1)}%`}
                    />
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-secondary)' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#0EA5E9' }}></span>
                      Systematic Variance ({attributionResult.risk_decomposition.systematic_share_pct.toFixed(1)}%)
                    </span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#F59E0B' }}></span>
                      Idiosyncratic Variance ({attributionResult.risk_decomposition.idiosyncratic_share_pct.toFixed(1)}%)
                    </span>
                  </div>
                </div>

                {/* Factor Contribution Table */}
                <div className="card" style={{ padding: '16px' }}>
                  <h4 style={{ fontSize: '13px', fontWeight: 600, margin: '0 0 12px 0' }}>Factor Exposures & Variance Attribution</h4>
                  <div style={{ overflowX: 'auto' }}>
                    <table className="table" style={{ width: '100%', fontSize: '12px' }}>
                      <thead>
                        <tr>
                          <th>Factor</th>
                          <th>Portfolio Beta</th>
                          <th>Marginal Contrib</th>
                          <th>Variance Contrib</th>
                          <th>% of Systematic Risk</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(attributionResult.risk_decomposition.factor_contributions).map(([fname, c]) => (
                          <tr key={fname}>
                            <td style={{ fontWeight: 600 }}>{fname}</td>
                            <td>{c.exposure.toFixed(4)}</td>
                            <td>{c.marginal_contrib.toFixed(4)}</td>
                            <td>{c.total_variance_contrib.toFixed(6)}</td>
                            <td>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <div style={{ width: '60px', height: '6px', backgroundColor: 'var(--bg-subtle)', borderRadius: '3px', overflow: 'hidden' }}>
                                  <div style={{ width: `${Math.min(100, Math.max(0, c.pct_of_systematic_risk))}%`, height: '100%', backgroundColor: '#0EA5E9' }} />
                                </div>
                                <span>{c.pct_of_systematic_risk.toFixed(1)}%</span>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Asset Loadings Table */}
                <div className="card" style={{ padding: '16px' }}>
                  <h4 style={{ fontSize: '13px', fontWeight: 600, margin: '0 0 12px 0' }}>Asset Factor Loadings & Regression Diagnostics</h4>
                  <div style={{ overflowX: 'auto' }}>
                    <table className="table" style={{ width: '100%', fontSize: '12px' }}>
                      <thead>
                        <tr>
                          <th>Asset</th>
                          <th>Alpha (Ann.)</th>
                          <th>Alpha t-stat</th>
                          {attributionResult.factors.map((f) => (
                            <th key={f}>Beta ({f})</th>
                          ))}
                          <th>Specific Vol</th>
                          <th>R²</th>
                        </tr>
                      </thead>
                      <tbody>
                        {attributionResult.assets.map((asset) => {
                          const p = attributionResult.asset_profiles[asset];
                          if (!p) return null;
                          const ticker = asset.split(':')[0];
                          return (
                            <tr key={asset}>
                              <td style={{ fontWeight: 600 }}>{ticker}</td>
                              <td>{(p.alpha_annualized * 100).toFixed(2)}%</td>
                              <td style={{ color: Math.abs(p.alpha_tstat) >= 1.96 ? '#10B981' : 'var(--text-secondary)' }}>
                                {p.alpha_tstat.toFixed(2)}
                              </td>
                              {attributionResult.factors.map((f) => {
                                const b = p.betas[f];
                                return (
                                  <td key={f}>
                                    {b ? b.beta.toFixed(3) : '-'}
                                  </td>
                                );
                              })}
                              <td>{(p.specific_volatility_annualized * 100).toFixed(2)}%</td>
                              <td>{(p.r_squared * 100).toFixed(1)}%</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: FACTOR-CONSTRAINED OPTIMIZATION */}
      {activeTab === 'optimization' && (
        <div style={{ display: 'grid', gridTemplateColumns: '340px 1fr', gap: '20px' }}>
          {/* Controls Sidebar */}
          <div className="card" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 600, margin: 0, display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Sliders size={15} /> Optimization & Tilts
            </h3>

            {/* Objective */}
            <div>
              <label style={{ fontSize: '12px', fontWeight: 500, display: 'block', marginBottom: '6px' }}>
                Optimization Objective
              </label>
              <select
                className="input-select"
                value={objective}
                onChange={(e) => setObjective(e.target.value as any)}
                style={{ width: '100%' }}
              >
                <option value="min_variance">Minimum Variance</option>
                <option value="max_sharpe">Maximum Sharpe Ratio</option>
                <option value="max_utility">Maximum Quadratic Utility</option>
              </select>
            </div>

            {objective === 'max_utility' && (
              <div>
                <label style={{ fontSize: '12px', fontWeight: 500, display: 'block', marginBottom: '6px' }}>
                  Risk Aversion (γ)
                </label>
                <input
                  type="number"
                  step="0.5"
                  min="0.1"
                  max="20"
                  value={riskAversion}
                  onChange={(e) => setRiskAversion(parseFloat(e.target.value) || 2.5)}
                  className="input-text"
                  style={{ width: '100%' }}
                />
              </div>
            )}

            {/* Factor Model */}
            <div>
              <label style={{ fontSize: '12px', fontWeight: 500, display: 'block', marginBottom: '6px' }}>
                Underlying Factor Model
              </label>
              <select
                className="input-select"
                value={factorModel}
                onChange={(e) => setFactorModel(e.target.value as any)}
                style={{ width: '100%' }}
              >
                <option value="capm">CAPM (1-Factor Market)</option>
                <option value="ff3">Fama-French 3-Factor (MKT, SMB, HML)</option>
                <option value="carhart4">Carhart 4-Factor (MKT, SMB, HML, MOM)</option>
                <option value="pca">PCA Statistical Eigen-Factors</option>
              </select>
            </div>

            {/* Weight Bounds */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <div>
                <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Min Weight</label>
                <input
                  type="number"
                  step="0.05"
                  min="0"
                  max="1"
                  value={minWeight}
                  onChange={(e) => setMinWeight(parseFloat(e.target.value) || 0)}
                  className="input-text"
                  style={{ width: '100%' }}
                />
              </div>
              <div>
                <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Max Weight</label>
                <input
                  type="number"
                  step="0.05"
                  min="0"
                  max="1"
                  value={maxWeight}
                  onChange={(e) => setMaxWeight(parseFloat(e.target.value) || 1)}
                  className="input-text"
                  style={{ width: '100%' }}
                />
              </div>
            </div>

            {/* Factor Tilt Constraints Table */}
            <div>
              <label style={{ fontSize: '12px', fontWeight: 500, display: 'block', marginBottom: '6px' }}>
                Factor Exposure Tilt Bounds (Min / Max Beta)
              </label>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {Object.keys(factorBounds).map((fname) => (
                  <div key={fname} style={{ display: 'grid', gridTemplateColumns: '60px 1fr 1fr', gap: '6px', alignItems: 'center' }}>
                    <span style={{ fontSize: '11px', fontWeight: 600 }}>{fname}</span>
                    <input
                      type="text"
                      placeholder="Min β"
                      value={factorBounds[fname]?.min_beta ?? ''}
                      onChange={(e) =>
                        setFactorBounds((prev) => ({
                          ...prev,
                          [fname]: { ...prev[fname], min_beta: e.target.value },
                        }))
                      }
                      style={{ padding: '4px 6px', fontSize: '11px' }}
                    />
                    <input
                      type="text"
                      placeholder="Max β"
                      value={factorBounds[fname]?.max_beta ?? ''}
                      onChange={(e) =>
                        setFactorBounds((prev) => ({
                          ...prev,
                          [fname]: { ...prev[fname], max_beta: e.target.value },
                        }))
                      }
                      style={{ padding: '4px 6px', fontSize: '11px' }}
                    />
                  </div>
                ))}
              </div>
            </div>

            {/* Solve Button */}
            <button
              onClick={handleRunOptimization}
              disabled={isOptimizing || !currentDataset}
              className="btn btn-primary"
              style={{ width: '100%', padding: '10px', marginTop: '8px', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px' }}
            >
              {isOptimizing ? (
                <>
                  <div className="loading-spinner" style={{ width: '14px', height: '14px' }}></div>
                  Solving Factor Tilt QP...
                </>
              ) : (
                <>
                  <Play size={15} /> Solve Factor-Constrained Portfolio
                </>
              )}
            </button>

            {optimizationError && (
              <div style={{ color: '#EF4444', fontSize: '11px', marginTop: '4px', lineHeight: 1.4 }}>
                {optimizationError}
              </div>
            )}
          </div>

          {/* Optimization Results Panel */}
          <div>
            {!optimizationResult ? (
              <div className="card" style={{ padding: '48px 24px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                <TrendingUp size={36} style={{ margin: '0 auto 12px auto', opacity: 0.4 }} />
                <h4 style={{ fontSize: '15px', fontWeight: 600, margin: '0 0 6px 0' }}>No Optimization Results</h4>
                <p style={{ fontSize: '13px', margin: 0 }}>
                  Configure your factor tilt constraints and click "Solve Factor-Constrained Portfolio" to generate optimal asset weights.
                </p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                {/* Status Alert */}
                <div
                  className="card"
                  style={{
                    padding: '14px 18px',
                    backgroundColor: optimizationResult.is_feasible ? 'rgba(16, 185, 129, 0.08)' : 'rgba(239, 68, 68, 0.08)',
                    borderColor: optimizationResult.is_feasible ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    {optimizationResult.is_feasible ? (
                      <CheckCircle2 size={18} color="#10B981" />
                    ) : (
                      <XCircle size={18} color="#EF4444" />
                    )}
                    <span style={{ fontSize: '13px', fontWeight: 600 }}>
                      Solver Status: {optimizationResult.solver_status} — {optimizationResult.solver_message}
                    </span>
                  </div>
                  <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                    Objective: {optimizationResult.objective}
                  </span>
                </div>

                {/* Optimal Weights & Realized Betas Grid */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                  {/* Optimal Weights Table */}
                  <div className="card" style={{ padding: '16px' }}>
                    <h4 style={{ fontSize: '13px', fontWeight: 600, margin: '0 0 12px 0' }}>Optimal Allocations</h4>
                    <table className="table" style={{ width: '100%', fontSize: '12px' }}>
                      <thead>
                        <tr>
                          <th>Asset</th>
                          <th>Optimal Weight</th>
                          <th>Allocation Bar</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(optimizationResult.weights).map(([asset, weight]) => {
                          const ticker = asset.split(':')[0];
                          const pct = (weight * 100).toFixed(2);
                          return (
                            <tr key={asset}>
                              <td style={{ fontWeight: 600 }}>{ticker}</td>
                              <td>{pct}%</td>
                              <td>
                                <div style={{ width: '100px', height: '6px', backgroundColor: 'var(--bg-subtle)', borderRadius: '3px', overflow: 'hidden' }}>
                                  <div style={{ width: `${Math.min(100, Math.max(0, weight * 100))}%`, height: '100%', backgroundColor: '#0EA5E9' }} />
                                </div>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>

                  {/* Realized Factor Exposures */}
                  <div className="card" style={{ padding: '16px' }}>
                    <h4 style={{ fontSize: '13px', fontWeight: 600, margin: '0 0 12px 0' }}>Realized Factor Betas vs Constraints</h4>
                    <table className="table" style={{ width: '100%', fontSize: '12px' }}>
                      <thead>
                        <tr>
                          <th>Factor</th>
                          <th>Realized Beta</th>
                          <th>Target Bounds</th>
                          <th>Compliance</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(optimizationResult.portfolio_betas).map(([fname, beta]) => {
                          const bound = factorBounds[fname];
                          const minB = bound && bound.min_beta !== '' ? parseFloat(bound.min_beta) : -Infinity;
                          const maxB = bound && bound.max_beta !== '' ? parseFloat(bound.max_beta) : Infinity;
                          const isCompliant = beta >= minB - 0.01 && beta <= maxB + 0.01;

                          return (
                            <tr key={fname}>
                              <td style={{ fontWeight: 600 }}>{fname}</td>
                              <td style={{ fontWeight: 600, color: '#0EA5E9' }}>{beta.toFixed(4)}</td>
                              <td>
                                [{minB === -Infinity ? '-∞' : minB}, {maxB === Infinity ? '+∞' : maxB}]
                              </td>
                              <td>
                                {isCompliant ? (
                                  <span style={{ color: '#10B981', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                                    <CheckCircle2 size={13} /> Feasible
                                  </span>
                                ) : (
                                  <span style={{ color: '#EF4444', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                                    <XCircle size={13} /> Breached
                                  </span>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Resulting Risk Breakdown */}
                <div className="card" style={{ padding: '16px' }}>
                  <h4 style={{ fontSize: '13px', fontWeight: 600, margin: '0 0 12px 0' }}>Resulting Risk Profile</h4>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '14px' }}>
                    <div style={{ padding: '10px', backgroundColor: 'var(--bg-subtle)', borderRadius: '6px' }}>
                      <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>Total Annualized Volatility</div>
                      <div style={{ fontSize: '18px', fontWeight: 700 }}>
                        {(optimizationResult.risk_decomposition.total_volatility * 100).toFixed(2)}%
                      </div>
                    </div>
                    <div style={{ padding: '10px', backgroundColor: 'var(--bg-subtle)', borderRadius: '6px' }}>
                      <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>Systematic Volatility</div>
                      <div style={{ fontSize: '18px', fontWeight: 700, color: '#0EA5E9' }}>
                        {(optimizationResult.risk_decomposition.systematic_volatility * 100).toFixed(2)}%
                      </div>
                    </div>
                    <div style={{ padding: '10px', backgroundColor: 'var(--bg-subtle)', borderRadius: '6px' }}>
                      <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>Idiosyncratic Volatility</div>
                      <div style={{ fontSize: '18px', fontWeight: 700, color: '#F59E0B' }}>
                        {(optimizationResult.risk_decomposition.idiosyncratic_volatility * 100).toFixed(2)}%
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: DYNAMIC WALK-FORWARD BACKTESTING */}
      {activeTab === 'backtest' && (
        <div style={{ display: 'grid', gridTemplateColumns: '340px 1fr', gap: '20px' }}>
          {/* Backtest Parameters Sidebar */}
          <div className="card" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 600, margin: 0, display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Sliders size={15} /> Backtest Configuration
            </h3>

            {/* Strategy Archetype */}
            <div>
              <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '6px' }}>Strategy Archetype</label>
              <select
                className="input"
                style={{ width: '100%', fontSize: '12px' }}
                value={strategyType}
                onChange={(e) => setStrategyType(e.target.value as any)}
              >
                <option value="factor_tilt">Factor Tilt & Active Alpha</option>
                <option value="factor_min_variance">Factor-Constrained Min-Variance</option>
                <option value="factor_momentum_rotation">Cross-Sectional Factor Rotation</option>
              </select>
            </div>

            {/* Factor Model Archetype */}
            <div>
              <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '6px' }}>Factor Model</label>
              <select
                className="input"
                style={{ width: '100%', fontSize: '12px' }}
                value={backtestModel}
                onChange={(e) => setBacktestModel(e.target.value as any)}
              >
                <option value="carhart4">Carhart 4-Factor (MKT, SMB, HML, MOM)</option>
                <option value="ff3">Fama-French 3-Factor (MKT, SMB, HML)</option>
                <option value="capm">CAPM (MKT Factor)</option>
                <option value="pca">PCA Eigen-Factors</option>
              </select>
            </div>

            {/* PCA Number of Factors */}
            {backtestModel === 'pca' && (
              <div>
                <label style={{ fontSize: '11px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>PCA Components</label>
                <input
                  type="number"
                  min="1"
                  max="10"
                  className="input"
                  style={{ width: '100%', fontSize: '12px' }}
                  value={backtestNumPca}
                  onChange={(e) => setBacktestNumPca(parseInt(e.target.value) || 3)}
                />
              </div>
            )}

            {/* Top N Assets for Momentum Rotation */}
            {strategyType === 'factor_momentum_rotation' && (
              <div>
                <label style={{ fontSize: '11px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>Top N Assets</label>
                <input
                  type="number"
                  min="1"
                  max="20"
                  className="input"
                  style={{ width: '100%', fontSize: '12px' }}
                  value={topNAssets}
                  onChange={(e) => setTopNAssets(parseInt(e.target.value) || 5)}
                />
              </div>
            )}

            {/* Rebalance Frequency */}
            <div>
              <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '6px' }}>Rebalance Frequency</label>
              <select
                className="input"
                style={{ width: '100%', fontSize: '12px' }}
                value={rebalanceFrequency}
                onChange={(e) => setRebalanceFrequency(e.target.value as any)}
              >
                <option value="monthly">Monthly (Calendar Month)</option>
                <option value="weekly">Weekly (ISO Week)</option>
                <option value="biweekly">Bi-Weekly (10 Trading Days)</option>
                <option value="quarterly">Quarterly</option>
                <option value="daily">Daily</option>
              </select>
            </div>

            {/* Estimation Window */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '4px' }}>
                <span style={{ fontWeight: 600 }}>Estimation Window (W)</span>
                <span style={{ color: 'var(--text-secondary)' }}>{estimationWindow} days</span>
              </div>
              <input
                type="range"
                min="30"
                max="252"
                step="5"
                value={estimationWindow}
                onChange={(e) => setEstimationWindow(parseInt(e.target.value))}
                style={{ width: '100%' }}
              />
            </div>

            {/* Factor Tilts (if tilt or rotation) */}
            {(strategyType === 'factor_tilt' || strategyType === 'factor_momentum_rotation') && (
              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, display: 'block', marginBottom: '6px' }}>
                  Target Factor Tilts (Intensity)
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px' }}>
                  {['MKT', 'MOM', 'HML', 'SMB'].map((f) => (
                    <div key={f} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ fontSize: '11px', width: '36px', fontWeight: 600 }}>{f}:</span>
                      <input
                        type="number"
                        step="0.1"
                        className="input"
                        style={{ width: '100%', fontSize: '11px', padding: '4px 6px' }}
                        value={factorTilts[f] ?? 0.0}
                        onChange={(e) =>
                          setFactorTilts((prev) => ({
                            ...prev,
                            [f]: parseFloat(e.target.value) || 0.0,
                          }))
                        }
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Friction Parameters */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <div>
                <label style={{ fontSize: '11px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>Fee (bps)</label>
                <input
                  type="number"
                  className="input"
                  style={{ width: '100%', fontSize: '12px' }}
                  value={transactionCostBps}
                  onChange={(e) => setTransactionCostBps(parseFloat(e.target.value) || 0)}
                />
              </div>
              <div>
                <label style={{ fontSize: '11px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>Slippage (bps)</label>
                <input
                  type="number"
                  className="input"
                  style={{ width: '100%', fontSize: '12px' }}
                  value={slippageBps}
                  onChange={(e) => setSlippageBps(parseFloat(e.target.value) || 0)}
                />
              </div>
            </div>

            {/* Turnover Penalty */}
            <div>
              <label style={{ fontSize: '11px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>Turnover Penalty (λ)</label>
              <input
                type="number"
                step="0.001"
                className="input"
                style={{ width: '100%', fontSize: '12px' }}
                value={turnoverPenalty}
                onChange={(e) => setTurnoverPenalty(parseFloat(e.target.value) || 0)}
              />
            </div>

            {/* Portfolio Constraints & Initial Capital */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <div>
                <label style={{ fontSize: '11px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>Capital ($)</label>
                <input
                  type="number"
                  step="10000"
                  className="input"
                  style={{ width: '100%', fontSize: '12px' }}
                  value={initialCapital}
                  onChange={(e) => setInitialCapital(parseFloat(e.target.value) || 100000)}
                />
              </div>
              <div>
                <label style={{ fontSize: '11px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>Risk Aversion (γ)</label>
                <input
                  type="number"
                  step="0.5"
                  className="input"
                  style={{ width: '100%', fontSize: '12px' }}
                  value={backtestRiskAversion}
                  onChange={(e) => setBacktestRiskAversion(parseFloat(e.target.value) || 2.5)}
                />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <div>
                <label style={{ fontSize: '11px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>Min Weight</label>
                <input
                  type="number"
                  step="0.05"
                  className="input"
                  style={{ width: '100%', fontSize: '12px' }}
                  value={backtestMinWeight}
                  onChange={(e) => setBacktestMinWeight(parseFloat(e.target.value) || 0.0)}
                />
              </div>
              <div>
                <label style={{ fontSize: '11px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>Max Weight</label>
                <input
                  type="number"
                  step="0.05"
                  className="input"
                  style={{ width: '100%', fontSize: '12px' }}
                  value={backtestMaxWeight}
                  onChange={(e) => setBacktestMaxWeight(parseFloat(e.target.value) || 0.4)}
                />
              </div>
            </div>

            {/* Run Button */}
            <button
              onClick={handleRunBacktest}
              disabled={isBacktesting || !currentDataset}
              className="btn btn-primary"
              style={{
                width: '100%',
                padding: '10px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                marginTop: '4px',
              }}
            >
              {isBacktesting ? (
                <>
                  <div className="spinner-sm" /> Simulating Walk-Forward...
                </>
              ) : (
                <>
                  <Play size={16} /> Run Dynamic Factor Backtest
                </>
              )}
            </button>

            {backtestError && (
              <div style={{ padding: '10px', backgroundColor: 'rgba(239, 68, 68, 0.1)', color: '#EF4444', fontSize: '12px', borderRadius: '6px' }}>
                {backtestError}
              </div>
            )}
          </div>

          {/* Backtest Results Area */}
          <div>
            {!backtestResult && !isBacktesting && (
              <div className="card" style={{ padding: '48px 24px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                <Cpu size={40} style={{ opacity: 0.3, margin: '0 auto 12px auto' }} />
                <h3 style={{ fontSize: '16px', fontWeight: 600, margin: '0 0 6px 0', color: 'var(--text-primary)' }}>
                  Ready to Simulate Dynamic Factor Backtest
                </h3>
                <p style={{ fontSize: '13px', maxWidth: '480px', margin: '0 auto' }}>
                  Execute a walk-forward simulation with rolling multi-factor loading re-estimation, turnover penalties, transaction fees, and dynamic factor exposure attribution.
                </p>
              </div>
            )}

            {isBacktesting && (
              <div className="card" style={{ padding: '64px 24px', textAlign: 'center' }}>
                <div className="spinner" style={{ margin: '0 auto 16px auto' }} />
                <h3 style={{ fontSize: '15px', fontWeight: 600 }}>Running Walk-Forward Factor Simulation</h3>
                <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                  Estimating rolling multivariate OLS loadings and structural covariance at each rebalance date with zero look-ahead bias...
                </p>
              </div>
            )}

            {backtestResult && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                {/* Summary KPI Cards */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '12px' }}>
                  <div className="card" style={{ padding: '14px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>Strategy CAGR</div>
                    <div style={{ fontSize: '20px', fontWeight: 700, color: backtestResult.summary_metrics.cagr >= 0 ? '#10B981' : '#EF4444' }}>
                      {(backtestResult.summary_metrics.cagr * 100).toFixed(2)}%
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      Bench: {(backtestResult.benchmark_metrics.cagr * 100).toFixed(2)}%
                    </div>
                  </div>

                  <div className="card" style={{ padding: '14px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>Sharpe Ratio</div>
                    <div style={{ fontSize: '20px', fontWeight: 700, color: '#0EA5E9' }}>
                      {backtestResult.summary_metrics.sharpe_ratio.toFixed(2)}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      Sortino: {backtestResult.summary_metrics.sortino_ratio.toFixed(2)}
                    </div>
                  </div>

                  <div className="card" style={{ padding: '14px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>Max Drawdown</div>
                    <div style={{ fontSize: '20px', fontWeight: 700, color: '#EF4444' }}>
                      {(backtestResult.summary_metrics.max_drawdown * 100).toFixed(2)}%
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      Calmar: {backtestResult.summary_metrics.calmar_ratio.toFixed(2)}
                    </div>
                  </div>

                  <div className="card" style={{ padding: '14px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>Information Ratio</div>
                    <div style={{ fontSize: '20px', fontWeight: 700, color: backtestResult.summary_metrics.information_ratio >= 0 ? '#10B981' : '#F59E0B' }}>
                      {backtestResult.summary_metrics.information_ratio.toFixed(2)}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      Alpha: {(backtestResult.summary_metrics.active_return * 100).toFixed(2)}%
                    </div>
                  </div>

                  <div className="card" style={{ padding: '14px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>Avg Turnover / Costs</div>
                    <div style={{ fontSize: '20px', fontWeight: 700 }}>
                      {(backtestResult.summary_metrics.average_turnover * 100).toFixed(1)}%
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      Costs: ${backtestResult.summary_metrics.total_transaction_costs.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </div>
                  </div>
                </div>

                {/* Equity Curve SVG Chart */}
                <div className="card" style={{ padding: '20px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                    <h4 style={{ fontSize: '14px', fontWeight: 600, margin: 0, display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <TrendingUp size={16} /> Cumulative Wealth Compounding & Drawdown
                    </h4>
                    <div style={{ display: 'flex', gap: '16px', fontSize: '12px' }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#10B981', fontWeight: 600 }}>
                        <span style={{ width: '12px', height: '3px', backgroundColor: '#10B981', display: 'inline-block' }} /> Strategy Net
                      </span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#94A3B8' }}>
                        <span style={{ width: '12px', height: '3px', backgroundColor: '#94A3B8', display: 'inline-block' }} /> Benchmark
                      </span>
                    </div>
                  </div>

                  {backtestResult.equity_curve.length > 1 && (() => {
                    const pts = backtestResult.equity_curve;
                    const n = pts.length;
                    const width = 800;
                    const height = 280;
                    const padding = 50;

                    const stratVals = pts.map((p) => p.strategy_equity);
                    const benchVals = pts.map((p) => p.benchmark_equity);
                    const minVal = Math.min(...stratVals, ...benchVals) * 0.98;
                    const maxVal = Math.max(...stratVals, ...benchVals) * 1.02;

                    const getX = (i: number) => padding + (i / (n - 1)) * (width - 2 * padding);
                    const getY = (v: number) => height - padding - ((v - minVal) / (maxVal - minVal || 1)) * (height - 2 * padding);

                    const stratPath = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${getX(i)} ${getY(p.strategy_equity)}`).join(' ');
                    const benchPath = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${getX(i)} ${getY(p.benchmark_equity)}`).join(' ');

                    return (
                      <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: 'auto', maxHeight: '300px' }}>
                        {[0, 0.25, 0.5, 0.75, 1].map((pct, i) => {
                          const val = minVal + pct * (maxVal - minVal);
                          const y = getY(val);
                          return (
                            <g key={i}>
                              <line x1={padding} y1={y} x2={width - padding} y2={y} stroke="#1E293B" strokeDasharray="3 3" />
                              <text x={padding - 8} y={y + 4} fill="#64748B" fontSize="10" textAnchor="end" fontFamily="monospace">
                                ${val.toLocaleString('en-US', { maximumFractionDigits: 0 })}
                              </text>
                            </g>
                          );
                        })}
                        <text x={padding} y={height - 15} fill="#64748B" fontSize="10" fontFamily="monospace">
                          {pts[0].date}
                        </text>
                        <text x={width - padding} y={height - 15} fill="#64748B" fontSize="10" textAnchor="end" fontFamily="monospace">
                          {pts[n - 1].date}
                        </text>
                        <path d={benchPath} fill="none" stroke="#94A3B8" strokeWidth="1.5" strokeDasharray="3 3" />
                        <path d={stratPath} fill="none" stroke="#10B981" strokeWidth="2.5" />
                      </svg>
                    );
                  })()}
                </div>

                {/* Rebalance Events History Table */}
                <div className="card" style={{ padding: '16px' }}>
                  <h4 style={{ fontSize: '13px', fontWeight: 600, margin: '0 0 12px 0', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <History size={15} /> Rebalance Events History ({backtestResult.total_rebalances} Rebalances)
                  </h4>
                  <div style={{ overflowX: 'auto' }}>
                    <table className="table" style={{ width: '100%', fontSize: '12px' }}>
                      <thead>
                        <tr>
                          <th>Date</th>
                          <th>Turnover</th>
                          <th>Friction Cost</th>
                          <th>Systematic Vol</th>
                          <th>Specific Vol</th>
                          <th>Systematic Share</th>
                          <th>Portfolio Factor Betas</th>
                          <th>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {backtestResult.rebalance_history.map((reb, i) => (
                          <tr key={i}>
                            <td style={{ fontFamily: 'monospace', fontWeight: 600 }}>{reb.date}</td>
                            <td>{(reb.turnover * 100).toFixed(1)}%</td>
                            <td>${reb.cost_incurred.toFixed(2)}</td>
                            <td style={{ color: '#0EA5E9' }}>{(reb.systematic_volatility * 100).toFixed(2)}%</td>
                            <td style={{ color: '#F59E0B' }}>{(reb.idiosyncratic_volatility * 100).toFixed(2)}%</td>
                            <td>
                              <span style={{ fontWeight: 600 }}>{reb.systematic_share_pct.toFixed(1)}%</span>
                            </td>
                            <td>
                              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                                {Object.entries(reb.portfolio_betas).map(([fname, b]) => (
                                  <span
                                    key={fname}
                                    style={{
                                      padding: '2px 6px',
                                      borderRadius: '4px',
                                      backgroundColor: 'var(--bg-subtle)',
                                      fontSize: '11px',
                                      fontFamily: 'monospace',
                                    }}
                                  >
                                    {fname}: {b.toFixed(2)}
                                  </span>
                                ))}
                              </div>
                            </td>
                            <td>
                              {reb.is_feasible ? (
                                <span style={{ color: '#10B981', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px' }}>
                                  <CheckCircle2 size={13} /> Feasible
                                </span>
                              ) : (
                                <span style={{ color: '#F59E0B', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px' }}>
                                  Relaxed
                                </span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Factor Exposure Evolution Time Series */}
                {backtestResult.factor_exposure_series.dates.length > 0 && (
                  <div className="card" style={{ padding: '16px' }}>
                    <h4 style={{ fontSize: '13px', fontWeight: 600, margin: '0 0 12px 0', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Activity size={15} /> Factor Exposure Evolution Over Time
                    </h4>
                    <div style={{ overflowX: 'auto' }}>
                      <table className="table" style={{ width: '100%', fontSize: '12px' }}>
                        <thead>
                          <tr>
                            <th>Date</th>
                            {Object.keys(backtestResult.factor_exposure_series.exposures).map((fname) => (
                              <th key={fname}>{fname} Beta</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {backtestResult.factor_exposure_series.dates.map((dt, idx) => (
                            <tr key={dt}>
                              <td style={{ fontFamily: 'monospace', fontWeight: 600 }}>{dt}</td>
                              {Object.entries(backtestResult.factor_exposure_series.exposures).map(([fname, series]) => (
                                <td key={fname} style={{ fontFamily: 'monospace' }}>
                                  {series[idx]?.toFixed(3) ?? '-'}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

