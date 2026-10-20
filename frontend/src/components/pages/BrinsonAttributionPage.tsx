import React, { useState, useEffect } from 'react';
import {
  Award,
  Layers,
  TrendingUp,
  BarChart3,
  AlertCircle,
  RefreshCw,
  PieChart,
  ShieldCheck,
  Info,
} from 'lucide-react';
import { useDataset } from '../../context/DatasetContext';
import { apiClient } from '../../api/client';
import type {
  BrinsonAttributionResponse,
  SystematicFactorAttributionResponse,
} from '../../types/api';

export const BrinsonAttributionPage: React.FC = () => {
  const { currentDataset, availableAssets } = useDataset();

  // Active Tab
  const [activeTab, setActiveTab] = useState<'brinson' | 'factor'>('brinson');

  // Input states
  const [portfolioWeights, setPortfolioWeights] = useState<Record<string, number>>({});
  const [benchmarkWeights, setBenchmarkWeights] = useState<Record<string, number>>({});
  const [segmentMapping, setSegmentMapping] = useState<Record<string, string>>({});
  const [frequency, setFrequency] = useState<'daily' | 'weekly' | 'monthly'>('monthly');
  const [attributionMethod, setAttributionMethod] = useState<'brinson_fachler' | 'brinson_hood_beebower'>('brinson_fachler');
  const [factorModel, setFactorModel] = useState<'capm' | 'fama_french_3' | 'carhart_4' | 'pca'>('fama_french_3');

  // Execution & result states
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [brinsonResult, setBrinsonResult] = useState<BrinsonAttributionResponse | null>(null);
  const [factorResult, setFactorResult] = useState<SystematicFactorAttributionResponse | null>(null);

  // Initialize weights and sector assignments when dataset changes
  useEffect(() => {
    if (availableAssets && availableAssets.length > 0) {
      const n = availableAssets.length;
      const equalWeight = parseFloat((1.0 / n).toFixed(4));
      const pw: Record<string, number> = {};
      const bw: Record<string, number> = {};
      const segs: Record<string, string> = {};

      // Standard sector defaults based on common tickers
      const defaultSectors: Record<string, string> = {
        AAPL: 'Information Technology',
        MSFT: 'Information Technology',
        GOOGL: 'Communication Services',
        AMZN: 'Consumer Discretionary',
        META: 'Communication Services',
        TSLA: 'Consumer Discretionary',
        NVDA: 'Information Technology',
        JPM: 'Financials',
        V: 'Financials',
        JNJ: 'Healthcare',
        XOM: 'Energy',
        PG: 'Consumer Staples',
        SPY: 'Index Proxy',
        QQQ: 'Technology Index',
      };

      availableAssets.forEach((a: any, idx: number) => {
        const ticker = a.ticker || a.asset_id;
        // Introduce small portfolio tilts relative to benchmark to demonstrate attribution
        const tilt = idx % 2 === 0 ? 0.05 : -0.05;
        pw[ticker] = Math.max(0.01, parseFloat((equalWeight + (n > 2 ? tilt : 0)).toFixed(4)));
        bw[ticker] = equalWeight;
        segs[ticker] = defaultSectors[ticker] || a.market || 'Equities';
      });

      // Normalize weights so sum is 1.0
      const sumP = Object.values(pw).reduce((acc, v) => acc + v, 0);
      const sumB = Object.values(bw).reduce((acc, v) => acc + v, 0);
      Object.keys(pw).forEach((k) => (pw[k] = parseFloat((pw[k] / sumP).toFixed(4))));
      Object.keys(bw).forEach((k) => (bw[k] = parseFloat((bw[k] / sumB).toFixed(4))));

      setPortfolioWeights(pw);
      setBenchmarkWeights(bw);
      setSegmentMapping(segs);
    }
  }, [availableAssets]);

  const handleRunBrinson = async () => {
    if (!currentDataset) return;
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const res = await apiClient.computeBrinsonAttribution({
        dataset_id: currentDataset.dataset_id,
        portfolio_weights: portfolioWeights,
        benchmark_weights: benchmarkWeights,
        segment_mapping: segmentMapping,
        frequency: frequency,
        method: attributionMethod,
      });
      setBrinsonResult(res);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to compute Brinson performance attribution.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRunFactor = async () => {
    if (!currentDataset) return;
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const res = await apiClient.computeSystematicFactorAttribution({
        dataset_id: currentDataset.dataset_id,
        portfolio_weights: portfolioWeights,
        benchmark_weights: benchmarkWeights,
        factor_model: factorModel,
      });
      setFactorResult(res);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to compute systematic factor risk attribution.');
    } finally {
      setIsLoading(false);
    }
  };

  if (!currentDataset) {
    return (
      <div className="card" style={{ padding: '32px', textAlign: 'center' }}>
        <AlertCircle size={36} style={{ color: 'var(--color-warning)', margin: '0 auto 16px' }} />
        <h3 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '8px' }}>No Active Dataset Selected</h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: '14px', maxWidth: '480px', margin: '0 auto' }}>
          Please select or register a dataset from Market Data Ingestion to execute multi-period Brinson performance attribution and systematic factor risk decomposition.
        </p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header Info & Tab Navigation */}
      <div className="card" style={{ padding: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
              <div style={{ padding: '8px', borderRadius: '8px', backgroundColor: 'rgba(236, 72, 153, 0.12)', color: '#EC4899' }}>
                <Award size={20} />
              </div>
              <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0 }}>
                Performance Attribution & Systematic Factor Risk Decomposition
              </h2>
            </div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '13px', margin: 0 }}>
              Audit active return sources using Brinson-Fachler arithmetic decomposition, Cariño multi-period compounding linking, and Barra multi-factor systematic risk breakdown.
            </p>
          </div>

          {/* Tab Selector */}
          <div style={{ display: 'flex', gap: '8px', background: 'var(--bg-secondary)', padding: '4px', borderRadius: '8px' }}>
            <button
              onClick={() => setActiveTab('brinson')}
              className={`btn ${activeTab === 'brinson' ? 'btn-primary' : 'btn-outline'}`}
              style={{ fontSize: '13px', padding: '6px 14px', display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <PieChart size={15} />
              Brinson-Fachler Decomposition
            </button>
            <button
              onClick={() => setActiveTab('factor')}
              className={`btn ${activeTab === 'factor' ? 'btn-primary' : 'btn-outline'}`}
              style={{ fontSize: '13px', padding: '6px 14px', display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <Layers size={15} />
              Systematic Factor Risk Attribution
            </button>
          </div>
        </div>

        {errorMessage && (
          <div className="alert alert-danger" style={{ marginTop: '16px' }}>
            <AlertCircle size={16} />
            <span>{errorMessage}</span>
          </div>
        )}
      </div>

      {/* Tab 1: Brinson-Fachler Decomposition */}
      {activeTab === 'brinson' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Configuration Panel */}
          <div className="card" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '15px', fontWeight: 600, margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                <TrendingUp size={16} style={{ color: 'var(--color-primary)' }} />
                Attribution Parameters & Universe Tilts
              </h3>
              <button
                onClick={handleRunBrinson}
                disabled={isLoading}
                className="btn btn-primary"
                style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
              >
                {isLoading ? <RefreshCw size={15} className="spin" /> : <PlayCircleIcon />}
                <span>Execute Brinson Attribution</span>
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '20px' }}>
              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                  Decomposition Formulation
                </label>
                <select
                  value={attributionMethod}
                  onChange={(e) => setAttributionMethod(e.target.value as any)}
                  className="input-select"
                  style={{ width: '100%', padding: '8px', fontSize: '13px' }}
                >
                  <option value="brinson_fachler">Brinson-Fachler (1985) - Benchmark Relative</option>
                  <option value="brinson_hood_beebower">Brinson-Hood-Beebower (1986) - Absolute Benchmark</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                  Compounding Frequency
                </label>
                <select
                  value={frequency}
                  onChange={(e) => setFrequency(e.target.value as any)}
                  className="input-select"
                  style={{ width: '100%', padding: '8px', fontSize: '13px' }}
                >
                  <option value="monthly">Monthly (21 Trading Days)</option>
                  <option value="weekly">Weekly (5 Trading Days)</option>
                  <option value="daily">Daily (1 Trading Day)</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                  Multi-Period Compounding
                </label>
                <div style={{ padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: '6px', fontSize: '13px', color: 'var(--text-primary)' }}>
                  Cariño (1999) Logarithmic Linking
                </div>
              </div>
            </div>

            {/* Asset Weight & Sector Allocation Table */}
            <div style={{ overflowX: 'auto' }}>
              <table className="table" style={{ width: '100%', fontSize: '13px' }}>
                <thead>
                  <tr>
                    <th>Asset Ticker</th>
                    <th>Sector / Segment</th>
                    <th>Portfolio Weight (w_p)</th>
                    <th>Benchmark Weight (w_b)</th>
                    <th>Active Tilt (Δw)</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.keys(portfolioWeights).map((t) => {
                    const pw = portfolioWeights[t] || 0.0;
                    const bw = benchmarkWeights[t] || 0.0;
                    const activeW = pw - bw;
                    return (
                      <tr key={t}>
                        <td style={{ fontWeight: 600 }}>{t}</td>
                        <td>
                          <input
                            type="text"
                            value={segmentMapping[t] || ''}
                            onChange={(e) => setSegmentMapping({ ...segmentMapping, [t]: e.target.value })}
                            className="input-text"
                            style={{ padding: '4px 8px', fontSize: '12px', width: '160px' }}
                          />
                        </td>
                        <td>
                          <input
                            type="number"
                            step="0.01"
                            min="0"
                            max="1"
                            value={pw}
                            onChange={(e) => setPortfolioWeights({ ...portfolioWeights, [t]: parseFloat(e.target.value) || 0 })}
                            className="input-text"
                            style={{ padding: '4px 8px', fontSize: '12px', width: '90px' }}
                          />
                        </td>
                        <td>
                          <input
                            type="number"
                            step="0.01"
                            min="0"
                            max="1"
                            value={bw}
                            onChange={(e) => setBenchmarkWeights({ ...benchmarkWeights, [t]: parseFloat(e.target.value) || 0 })}
                            className="input-text"
                            style={{ padding: '4px 8px', fontSize: '12px', width: '90px' }}
                          />
                        </td>
                        <td style={{ fontWeight: 600, color: activeW > 0 ? '#10B981' : activeW < 0 ? '#F43F5E' : 'inherit' }}>
                          {activeW > 0 ? `+${(activeW * 100).toFixed(2)}%` : `${(activeW * 100).toFixed(2)}%`}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Results Display */}
          {brinsonResult && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              {/* Metric Cards Banner */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px' }}>
                <MetricCard
                  title="Cumulative Portfolio Return"
                  value={`${(brinsonResult.summary.cumulative_portfolio_return * 100).toFixed(2)}%`}
                  accent="#3B82F6"
                  badge={`${brinsonResult.summary.total_periods} Periods`}
                />
                <MetricCard
                  title="Cumulative Benchmark Return"
                  value={`${(brinsonResult.summary.cumulative_benchmark_return * 100).toFixed(2)}%`}
                  accent="#64748B"
                  badge="Index Base"
                />
                <MetricCard
                  title="Cumulative Active Return (ΔR)"
                  value={`${(brinsonResult.summary.cumulative_active_return * 100).toFixed(2)}%`}
                  accent={brinsonResult.summary.cumulative_active_return >= 0 ? '#10B981' : '#F43F5E'}
                  badge={brinsonResult.summary.cumulative_active_return >= 0 ? 'Outperformance' : 'Underperformance'}
                />
                <MetricCard
                  title="Allocation Effect (A)"
                  value={`${(brinsonResult.summary.total_allocation_effect * 100).toFixed(2)}%`}
                  accent="#8B5CF6"
                  badge="Sector Tilts"
                />
                <MetricCard
                  title="Selection Effect (S)"
                  value={`${(brinsonResult.summary.total_selection_effect * 100).toFixed(2)}%`}
                  accent="#EC4899"
                  badge="Stock Picking"
                />
                <MetricCard
                  title="Interaction Effect (I)"
                  value={`${(brinsonResult.summary.total_interaction_effect * 100).toFixed(2)}%`}
                  accent="#F59E0B"
                  badge="Cross Interaction"
                />
              </div>

              {/* Exact Reconciliation Banner */}
              <div
                className="card"
                style={{
                  padding: '16px 20px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0%, rgba(59, 130, 246, 0.05) 100%)',
                  border: '1px solid rgba(16, 185, 129, 0.25)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <ShieldCheck size={24} style={{ color: '#10B981' }} />
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--text-primary)' }}>
                      Cariño Multi-Period Exact Mathematical Reconciliation
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                      Allocation ({(brinsonResult.summary.total_allocation_effect * 100).toFixed(4)}%) + Selection ({(brinsonResult.summary.total_selection_effect * 100).toFixed(4)}%) + Interaction ({(brinsonResult.summary.total_interaction_effect * 100).toFixed(4)}%) ≡ Active Return ({(brinsonResult.summary.cumulative_active_return * 100).toFixed(4)}%)
                    </div>
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Residual Error</div>
                  <div style={{ fontSize: '14px', fontWeight: 700, color: '#10B981', fontFamily: 'monospace' }}>
                    {Math.abs(brinsonResult.summary.reconciliation_error) < 1e-12 ? '0.00000000%' : `${(brinsonResult.summary.reconciliation_error * 100).toFixed(8)}%`}
                  </div>
                </div>
              </div>

              {/* Attribution Waterfall Chart */}
              <div className="card" style={{ padding: '20px' }}>
                <h3 style={{ fontSize: '15px', fontWeight: 600, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <BarChart3 size={16} style={{ color: 'var(--color-primary)' }} />
                  Cariño Linked Attribution Waterfall Decomposition
                </h3>
                <WaterfallChart summary={brinsonResult.summary} />
              </div>

              {/* Segment Attribution Table */}
              <div className="card" style={{ padding: '20px' }}>
                <h3 style={{ fontSize: '15px', fontWeight: 600, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <PieChart size={16} style={{ color: 'var(--color-primary)' }} />
                  Sector & Segment Level Attribution Breakdown
                </h3>
                <div style={{ overflowX: 'auto' }}>
                  <table className="table" style={{ width: '100%', fontSize: '13px' }}>
                    <thead>
                      <tr>
                        <th>Segment / Sector</th>
                        <th>Avg Port Weight</th>
                        <th>Avg Bmk Weight</th>
                        <th>Active Weight</th>
                        <th>Linked Allocation</th>
                        <th>Linked Selection</th>
                        <th>Linked Interaction</th>
                        <th>Total Contribution</th>
                      </tr>
                    </thead>
                    <tbody>
                      {brinsonResult.segment_attribution.map((seg) => (
                        <tr key={seg.segment}>
                          <td style={{ fontWeight: 600 }}>{seg.segment}</td>
                          <td>{(seg.average_portfolio_weight * 100).toFixed(2)}%</td>
                          <td>{(seg.average_benchmark_weight * 100).toFixed(2)}%</td>
                          <td style={{ fontWeight: 600, color: seg.active_weight >= 0 ? '#10B981' : '#F43F5E' }}>
                            {seg.active_weight >= 0 ? `+${(seg.active_weight * 100).toFixed(2)}%` : `${(seg.active_weight * 100).toFixed(2)}%`}
                          </td>
                          <td style={{ color: seg.linked_allocation_effect >= 0 ? '#10B981' : '#F43F5E' }}>
                            {(seg.linked_allocation_effect * 100).toFixed(2)}%
                          </td>
                          <td style={{ color: seg.linked_selection_effect >= 0 ? '#10B981' : '#F43F5E' }}>
                            {(seg.linked_selection_effect * 100).toFixed(2)}%
                          </td>
                          <td style={{ color: seg.linked_interaction_effect >= 0 ? '#10B981' : '#F43F5E' }}>
                            {(seg.linked_interaction_effect * 100).toFixed(2)}%
                          </td>
                          <td style={{ fontWeight: 700, color: seg.total_contribution >= 0 ? '#10B981' : '#F43F5E' }}>
                            {(seg.total_contribution * 100).toFixed(2)}%
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

      {/* Tab 2: Systematic Factor Risk Attribution */}
      {activeTab === 'factor' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Controls */}
          <div className="card" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '15px', fontWeight: 600, margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Layers size={16} style={{ color: 'var(--color-primary)' }} />
                Systematic Factor Risk Model Parameters
              </h3>
              <button
                onClick={handleRunFactor}
                disabled={isLoading}
                className="btn btn-primary"
                style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
              >
                {isLoading ? <RefreshCw size={15} className="spin" /> : <PlayCircleIcon />}
                <span>Execute Factor Attribution</span>
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                  Risk Factor Model
                </label>
                <select
                  value={factorModel}
                  onChange={(e) => setFactorModel(e.target.value as any)}
                  className="input-select"
                  style={{ width: '100%', padding: '8px', fontSize: '13px' }}
                >
                  <option value="fama_french_3">Fama-French 3-Factor (MKT, SMB, HML)</option>
                  <option value="carhart_4">Carhart 4-Factor (MKT, SMB, HML, MOM)</option>
                  <option value="capm">Capital Asset Pricing Model (Single MKT Factor)</option>
                  <option value="pca">Principal Component Analysis (Statistical Factors)</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                  Formulation
                </label>
                <div style={{ padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: '6px', fontSize: '13px', color: 'var(--text-primary)' }}>
                  Barra-Style Active Risk & Return Decomposition
                </div>
              </div>
            </div>
          </div>

          {/* Factor Results Display */}
          {factorResult && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              {/* Summary Metrics Banner */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px' }}>
                <MetricCard
                  title="Annualized Portfolio Return"
                  value={`${(factorResult.annualized_portfolio_return * 100).toFixed(2)}%`}
                  accent="#3B82F6"
                  badge="Annualized"
                />
                <MetricCard
                  title="Annualized Benchmark Return"
                  value={`${(factorResult.annualized_benchmark_return * 100).toFixed(2)}%`}
                  accent="#64748B"
                  badge="Annualized"
                />
                <MetricCard
                  title="Total Active Return"
                  value={`${(factorResult.total_active_return * 100).toFixed(2)}%`}
                  accent={factorResult.total_active_return >= 0 ? '#10B981' : '#F43F5E'}
                  badge="Annualized Spread"
                />
                <MetricCard
                  title="Systematic Active Return"
                  value={`${(factorResult.systematic_active_return * 100).toFixed(2)}%`}
                  accent="#8B5CF6"
                  badge="Factor Driven"
                />
                <MetricCard
                  title="Specific (Stock Selection) Return"
                  value={`${(factorResult.specific_active_return * 100).toFixed(2)}%`}
                  accent="#EC4899"
                  badge="Idiosyncratic"
                />
                <MetricCard
                  title="Total Tracking Error (Active Risk)"
                  value={`${(factorResult.total_tracking_error * 100).toFixed(2)}%`}
                  accent="#F59E0B"
                  badge="Volatility"
                />
              </div>

              {/* Active Risk Decomposition Visual */}
              <div className="card" style={{ padding: '20px' }}>
                <h3 style={{ fontSize: '15px', fontWeight: 600, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <ShieldCheck size={16} style={{ color: 'var(--color-primary)' }} />
                  Active Tracking Error Variance Decomposition
                </h3>
                <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap', alignItems: 'center' }}>
                  <div style={{ flex: 1, minWidth: '240px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '13px' }}>
                      <span style={{ fontWeight: 600, color: '#8B5CF6' }}>Systematic Factor Risk</span>
                      <span>{factorResult.systematic_risk_percent.toFixed(1)}%</span>
                    </div>
                    <div style={{ width: '100%', height: '12px', background: 'var(--bg-secondary)', borderRadius: '6px', overflow: 'hidden' }}>
                      <div style={{ width: `${factorResult.systematic_risk_percent}%`, height: '100%', background: '#8B5CF6', borderRadius: '6px' }} />
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                      Vol: {(factorResult.systematic_tracking_error * 100).toFixed(2)}%
                    </div>
                  </div>

                  <div style={{ flex: 1, minWidth: '240px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '13px' }}>
                      <span style={{ fontWeight: 600, color: '#EC4899' }}>Specific Idiosyncratic Risk</span>
                      <span>{factorResult.specific_risk_percent.toFixed(1)}%</span>
                    </div>
                    <div style={{ width: '100%', height: '12px', background: 'var(--bg-secondary)', borderRadius: '6px', overflow: 'hidden' }}>
                      <div style={{ width: `${factorResult.specific_risk_percent}%`, height: '100%', background: '#EC4899', borderRadius: '6px' }} />
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                      Vol: {(factorResult.specific_tracking_error * 100).toFixed(2)}%
                    </div>
                  </div>
                </div>
              </div>

              {/* Factor Contributions Table */}
              <div className="card" style={{ padding: '20px' }}>
                <h3 style={{ fontSize: '15px', fontWeight: 600, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <BarChart3 size={16} style={{ color: 'var(--color-primary)' }} />
                  Factor Active Exposures and Return Contributions
                </h3>
                <div style={{ overflowX: 'auto' }}>
                  <table className="table" style={{ width: '100%', fontSize: '13px' }}>
                    <thead>
                      <tr>
                        <th>Factor</th>
                        <th>Portfolio Beta</th>
                        <th>Benchmark Beta</th>
                        <th>Active Beta (Δβ)</th>
                        <th>Annualized Factor Return</th>
                        <th>Annualized Return Contribution</th>
                      </tr>
                    </thead>
                    <tbody>
                      {factorResult.factor_contributions.map((fc) => (
                        <tr key={fc.factor}>
                          <td style={{ fontWeight: 600 }}>{fc.factor}</td>
                          <td>{fc.portfolio_beta.toFixed(3)}</td>
                          <td>{fc.benchmark_beta.toFixed(3)}</td>
                          <td style={{ fontWeight: 600, color: fc.active_beta >= 0 ? '#10B981' : '#F43F5E' }}>
                            {fc.active_beta >= 0 ? `+${fc.active_beta.toFixed(3)}` : fc.active_beta.toFixed(3)}
                          </td>
                          <td>{(fc.annualized_factor_return * 100).toFixed(2)}%</td>
                          <td style={{ fontWeight: 700, color: fc.annualized_contribution >= 0 ? '#10B981' : '#F43F5E' }}>
                            {(fc.annualized_contribution * 100).toFixed(2)}%
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

      {/* Institutional Mathematical Reference Drawer */}
      <div className="card" style={{ padding: '20px', backgroundColor: 'rgba(30, 41, 59, 0.4)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
          <Info size={16} style={{ color: 'var(--color-primary)' }} />
          <h4 style={{ fontSize: '14px', fontWeight: 600, margin: 0 }}>Attribution Mathematical Integrity & Formulation Reference</h4>
        </div>
        <div style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          • <strong>Brinson-Fachler (1985)</strong>: Allocation effect is benchmark-relative:{' '}
          <code>A_i = (w_{'{p,i}'} - w_{'{b,i}'}) × (R_{'{b,i}'} - R_b)</code>, rewarding active overweighting of sectors that outperformed the broad benchmark.<br />
          • <strong>Cariño (1999) Multi-Period Linking</strong>: Logarithmic coefficients{' '}
          <code>c_t = [ln(1+R_{'{p,t}'}) - ln(1+R_{'{b,t}'})] / (R_{'{p,t}'} - R_{'{b,t}'}) × ΔR^{'{cum}'} / ln(1+ΔR^{'{cum}'})</code>{' '}
          scale sub-period effects such that their cumulative sum algebraically reconciles to exact compounded excess return with zero residual.<br />
          • <strong>Barra Factor Attribution</strong>: Active risk decomposes into systematic covariance risk{' '}
          <code>Δβ^T Σ_F Δβ</code> and idiosyncratic stock-picking variance <code>Δw^T Σ_ε Δw</code>.
        </div>
      </div>
    </div>
  );
};

// Reusable Metric Card Component
interface MetricCardProps {
  title: string;
  value: string;
  accent: string;
  badge?: string;
}

const MetricCard: React.FC<MetricCardProps> = ({ title, value, accent, badge }) => (
  <div
    className="card"
    style={{
      padding: '16px',
      borderLeft: `4px solid ${accent}`,
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'space-between',
    }}
  >
    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 600, marginBottom: '8px' }}>
      {title}
    </div>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
      <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)' }}>
        {value}
      </div>
      {badge && (
        <span
          style={{
            fontSize: '11px',
            padding: '2px 8px',
            borderRadius: '4px',
            backgroundColor: `${accent}1A`,
            color: accent,
            fontWeight: 600,
          }}
        >
          {badge}
        </span>
      )}
    </div>
  </div>
);

// Waterfall SVG Chart Component
const WaterfallChart: React.FC<{ summary: any }> = ({ summary }) => {
  const R_b = summary.cumulative_benchmark_return * 100;
  const Alloc = summary.total_allocation_effect * 100;
  const Select = summary.total_selection_effect * 100;
  const Inter = summary.total_interaction_effect * 100;
  const R_p = summary.cumulative_portfolio_return * 100;

  const data = [
    { label: 'Benchmark', value: R_b, isTotal: true },
    { label: 'Allocation', value: Alloc, isTotal: false },
    { label: 'Selection', value: Select, isTotal: false },
    { label: 'Interaction', value: Inter, isTotal: false },
    { label: 'Portfolio', value: R_p, isTotal: true },
  ];

  const maxVal = Math.max(R_b, R_p, R_b + Alloc, R_b + Alloc + Select, 1.0) * 1.25;
  const minVal = Math.min(0, R_b, R_p, Alloc, Select, Inter) * 1.25;
  const range = maxVal - minVal;

  const chartHeight = 180;
  const chartWidth = 600;
  const barWidth = 60;
  const spacing = (chartWidth - barWidth * data.length) / (data.length + 1);

  let currentTotal = 0;

  return (
    <div style={{ width: '100%', overflowX: 'auto' }}>
      <svg width={chartWidth} height={chartHeight} style={{ overflow: 'visible', margin: '20px 0' }}>
        {/* Zero baseline */}
        {minVal < 0 && (
          <line
            x1="0"
            y1={chartHeight - ((0 - minVal) / range) * chartHeight}
            x2={chartWidth}
            y2={chartHeight - ((0 - minVal) / range) * chartHeight}
            stroke="var(--border-subtle)"
            strokeDasharray="4 4"
          />
        )}

        {data.map((d, i) => {
          const x = spacing + i * (barWidth + spacing);
          let y = 0;
          let h = 0;
          let fill = '#3B82F6';

          if (d.isTotal) {
            y = chartHeight - ((Math.max(0, d.value) - minVal) / range) * chartHeight;
            h = (Math.abs(d.value) / range) * chartHeight;
            fill = d.label === 'Benchmark' ? '#64748B' : '#3B82F6';
            currentTotal = d.value;
          } else {
            const startVal = currentTotal;
            const endVal = currentTotal + d.value;
            const topVal = Math.max(startVal, endVal);
            const botVal = Math.min(startVal, endVal);
            y = chartHeight - ((topVal - minVal) / range) * chartHeight;
            h = ((topVal - botVal) / range) * chartHeight;
            fill = d.value >= 0 ? '#10B981' : '#F43F5E';
            currentTotal = endVal;
          }

          return (
            <g key={d.label}>
              <rect x={x} y={y} width={barWidth} height={Math.max(2, h)} rx="4" fill={fill} opacity={0.9} />
              <text
                x={x + barWidth / 2}
                y={y - 8}
                textAnchor="middle"
                fontSize="11"
                fontWeight="700"
                fill="var(--text-primary)"
              >
                {d.value >= 0 && !d.isTotal ? `+${d.value.toFixed(2)}%` : `${d.value.toFixed(2)}%`}
              </text>
              <text
                x={x + barWidth / 2}
                y={chartHeight + 16}
                textAnchor="middle"
                fontSize="11"
                fontWeight="600"
                fill="var(--text-secondary)"
              >
                {d.label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
};

const PlayCircleIcon: React.FC = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10"></circle>
    <polygon points="10 8 16 12 10 16 10 8"></polygon>
  </svg>
);
