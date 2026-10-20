import React, { useState, useEffect } from 'react';
import {
  Award,
  TrendingUp,
  PieChart,
  PlayCircle,
  Trash2,
  History,
  AlertTriangle,
  Info,
  Layers,
  TrendingDown,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { useDataset } from '../../context/DatasetContext';
import type {
  BacktestListItem,
  PerformanceAnalysisRequest,
  PerformanceReportListItem,
  PerformanceResponse,
  PortfolioDefinition,
} from '../../types/api';

interface PerformancePageProps {
  initialPortfolio?: PortfolioDefinition | null;
}

type SourceMode = 'custom_portfolio' | 'saved_backtest';

export const PerformancePage: React.FC<PerformancePageProps> = ({ initialPortfolio }) => {
  const { currentDataset, availableAssets } = useDataset();

  // Mode & configuration
  const [sourceMode, setSourceMode] = useState<SourceMode>('custom_portfolio');
  const [reportName, setReportName] = useState<string>('Performance Attribution & Benchmark Analysis');
  const [benchmarkAsset, setBenchmarkAsset] = useState<string>('');
  const [riskFreeRate, setRiskFreeRate] = useState<number>(0.02);
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [saveReport, setSaveReport] = useState<boolean>(true);

  // Custom Portfolio state
  const [selectedAssets, setSelectedAssets] = useState<string[]>([]);
  const [weights, setWeights] = useState<Record<string, number>>({});

  // Backtest state
  const [savedBacktests, setSavedBacktests] = useState<BacktestListItem[]>([]);
  const [selectedBacktestId, setSelectedBacktestId] = useState<string>('');
  const [loadingBacktests, setLoadingBacktests] = useState<boolean>(false);

  // Saved reports history drawer
  const [savedReports, setSavedReports] = useState<PerformanceReportListItem[]>([]);
  const [loadingReports, setLoadingReports] = useState<boolean>(false);
  const [showHistoryDrawer, setShowHistoryDrawer] = useState<boolean>(false);

  // Analysis state
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PerformanceResponse | null>(null);

  // Initialize from props / available assets
  useEffect(() => {
    if (availableAssets.length > 0) {
      // Find default benchmark asset: SPY or first asset
      const spyCandidate = availableAssets.find(
        (a) => a.ticker.toUpperCase() === 'SPY' || a.asset_id.toUpperCase().startsWith('SPY:')
      );
      if (spyCandidate) {
        setBenchmarkAsset(spyCandidate.asset_id);
      } else if (!benchmarkAsset) {
        setBenchmarkAsset(availableAssets[0].asset_id);
      }

      // Initialize custom portfolio assets
      if (initialPortfolio && initialPortfolio.assets.length > 0) {
        setSelectedAssets(initialPortfolio.assets);
        setWeights(initialPortfolio.weights ? { ...initialPortfolio.weights } : {});
      } else if (selectedAssets.length === 0) {
        const nonBenchAssets = availableAssets
          .map((a) => a.asset_id)
          .filter((id) => id !== (spyCandidate?.asset_id || availableAssets[0].asset_id));
        const initial = nonBenchAssets.slice(0, 3);
        if (initial.length > 0) {
          setSelectedAssets(initial);
          const eqW = 1.0 / initial.length;
          const wMap: Record<string, number> = {};
          initial.forEach((a) => {
            wMap[a] = eqW;
          });
          setWeights(wMap);
        }
      }
    }
  }, [availableAssets, initialPortfolio]);

  const loadSavedReports = async () => {
    setLoadingReports(true);
    try {
      const reports = await apiClient.listPerformanceReports();
      setSavedReports(reports);
    } catch (err) {
      console.error('Failed to load performance reports:', err);
    } finally {
      setLoadingReports(false);
    }
  };

  const loadSavedBacktests = async () => {
    setLoadingBacktests(true);
    try {
      const bts = await apiClient.listBacktests();
      setSavedBacktests(bts);
      if (bts.length > 0 && !selectedBacktestId) {
        setSelectedBacktestId(bts[0].id);
      }
    } catch (err) {
      console.error('Failed to load saved backtests:', err);
    } finally {
      setLoadingBacktests(false);
    }
  };

  // Load backtests and saved reports on mount
  useEffect(() => {
    void loadSavedReports();
    void loadSavedBacktests();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleAssetToggle = (assetId: string) => {
    if (assetId === benchmarkAsset) return;
    if (selectedAssets.includes(assetId)) {
      const next = selectedAssets.filter((a) => a !== assetId);
      setSelectedAssets(next);
      const nextWeights = { ...weights };
      delete nextWeights[assetId];
      if (next.length > 0) {
        const eqW = 1.0 / next.length;
        next.forEach((a) => {
          nextWeights[a] = eqW;
        });
      }
      setWeights(nextWeights);
    } else {
      const next = [...selectedAssets, assetId];
      setSelectedAssets(next);
      const eqW = 1.0 / next.length;
      const nextWeights: Record<string, number> = {};
      next.forEach((a) => {
        nextWeights[a] = eqW;
      });
      setWeights(nextWeights);
    }
  };

  const handleWeightChange = (assetId: string, val: number) => {
    setWeights((prev) => ({
      ...prev,
      [assetId]: val,
    }));
  };

  const handleEqualWeight = () => {
    if (selectedAssets.length === 0) return;
    const eqW = 1.0 / selectedAssets.length;
    const wMap: Record<string, number> = {};
    selectedAssets.forEach((a) => {
      wMap[a] = eqW;
    });
    setWeights(wMap);
  };

  const handleExecute = async () => {
    if (!currentDataset) {
      setError('Please select or upload a dataset first.');
      return;
    }
    if (!benchmarkAsset) {
      setError('Please select a benchmark asset.');
      return;
    }

    setError(null);
    setIsAnalyzing(true);

    try {
      let resp: PerformanceResponse;
      if (sourceMode === 'saved_backtest') {
        if (!selectedBacktestId) {
          throw new Error('Please select a saved backtest.');
        }
        resp = await apiClient.getBacktestPerformance(
          selectedBacktestId,
          benchmarkAsset,
          riskFreeRate,
          saveReport
        );
      } else {
        if (selectedAssets.length === 0) {
          throw new Error('Select at least one portfolio asset.');
        }
        const totalW = Object.values(weights).reduce((a, b) => a + b, 0);
        if (Math.abs(totalW - 1.0) > 1e-3) {
          throw new Error(`Portfolio weights must sum to 100% (current: ${(totalW * 100).toFixed(1)}%).`);
        }

        const req: PerformanceAnalysisRequest = {
          dataset_id: currentDataset.dataset_id,
          name: reportName,
          benchmark_asset: benchmarkAsset,
          assets: selectedAssets,
          weights,
          risk_free_rate: riskFreeRate,
          start_date: startDate || null,
          end_date: endDate || null,
          save_report: saveReport,
        };
        resp = await apiClient.analyzePerformance(req);
      }

      setResult(resp);
      if (saveReport) {
        loadSavedReports();
      }
    } catch (err: any) {
      const msg = err.data?.detail?.errors?.[0] || err.message || 'Performance evaluation failed.';
      setError(msg);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleLoadSavedReport = async (reportId: string) => {
    try {
      setIsAnalyzing(true);
      setError(null);
      const rep = await apiClient.getPerformanceReport(reportId);
      setResult(rep);
      setShowHistoryDrawer(false);
    } catch (err: any) {
      setError(err.message || 'Failed to load report.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleDeleteSavedReport = async (e: React.MouseEvent, reportId: string) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this saved performance report?')) return;
    try {
      await apiClient.deletePerformanceReport(reportId);
      setSavedReports((prev) => prev.filter((r) => r.id !== reportId));
      if (result && result.id === reportId) {
        setResult(null);
      }
    } catch (err: any) {
      alert('Failed to delete report: ' + err.message);
    }
  };

  // Helper chart renderer for Cumulative Wealth
  const renderCumulativeChart = () => {
    if (!result || result.timeseries.length === 0) return null;
    const data = result.timeseries;
    const svgWidth = 800;
    const svgHeight = 240;
    const padX = 55;
    const padY = 25;

    const portValues = data.map((d) => d.portfolio_cumulative);
    const benchValues = data.map((d) => d.benchmark_cumulative);
    const minVal = Math.min(...portValues, ...benchValues, 0);
    const maxVal = Math.max(...portValues, ...benchValues, 0.05);
    const range = maxVal - minVal || 1;

    const getX = (idx: number) => padX + (idx / (data.length - 1)) * (svgWidth - padX - 20);
    const getY = (val: number) => svgHeight - padY - ((val - minVal) / range) * (svgHeight - padY * 2);

    const portPoints = data.map((d, i) => `${getX(i)},${getY(d.portfolio_cumulative)}`).join(' ');
    const benchPoints = data.map((d, i) => `${getX(i)},${getY(d.benchmark_cumulative)}`).join(' ');
    const zeroY = getY(0);

    return (
      <div style={{ position: 'relative', width: '100%', overflowX: 'auto' }}>
        <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} style={{ width: '100%', height: 'auto', display: 'block' }}>
          {/* Zero Return Reference Line */}
          <line x1={padX} y1={zeroY} x2={svgWidth - 20} y2={zeroY} stroke="var(--border-subtle)" strokeDasharray="3 3" />
          <text x={padX - 8} y={zeroY + 4} fill="var(--text-muted)" fontSize="10" textAnchor="end">0.0%</text>

          {/* Max/Min Labels */}
          <text x={padX - 8} y={padY + 4} fill="var(--text-muted)" fontSize="10" textAnchor="end">
            {(maxVal * 100).toFixed(1)}%
          </text>
          <text x={padX - 8} y={svgHeight - padY + 4} fill="var(--text-muted)" fontSize="10" textAnchor="end">
            {(minVal * 100).toFixed(1)}%
          </text>

          {/* Benchmark Curve */}
          <polyline fill="none" stroke="#94A3B8" strokeWidth="2" strokeDasharray="4 4" points={benchPoints} />

          {/* Portfolio Curve */}
          <polyline fill="none" stroke="#38BDF8" strokeWidth="2.5" points={portPoints} />

          {/* Start and End date labels */}
          <text x={padX} y={svgHeight - 6} fill="var(--text-muted)" fontSize="10">
            {data[0].date}
          </text>
          <text x={svgWidth - 20} y={svgHeight - 6} fill="var(--text-muted)" fontSize="10" textAnchor="end">
            {data[data.length - 1].date}
          </text>
        </svg>

        {/* Legend */}
        <div style={{ display: 'flex', gap: '20px', justifyContent: 'center', marginTop: '10px', fontSize: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '14px', height: '3px', backgroundColor: '#38BDF8', borderRadius: '2px' }} />
            <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>Portfolio Cumulative</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '14px', height: '2px', backgroundColor: '#94A3B8', borderTop: '2px dashed #94A3B8' }} />
            <span style={{ color: 'var(--text-secondary)' }}>Benchmark ({result.benchmark_asset})</span>
          </div>
        </div>
      </div>
    );
  };

  // Helper chart renderer for Active Return & Drawdowns
  const renderActiveAndDrawdownChart = () => {
    if (!result || result.timeseries.length === 0) return null;
    const data = result.timeseries;
    const svgWidth = 800;
    const svgHeight = 200;
    const padX = 55;
    const padY = 20;

    const ddPort = data.map((d) => d.drawdown_portfolio);
    const ddBench = data.map((d) => d.drawdown_benchmark);
    const minDd = Math.min(...ddPort, ...ddBench, -0.05);

    const getX = (idx: number) => padX + (idx / (data.length - 1)) * (svgWidth - padX - 20);
    const getY = (val: number) => padY + ((0 - val) / (0 - minDd)) * (svgHeight - padY * 2);

    const portDdPoints = data.map((d, i) => `${getX(i)},${getY(d.drawdown_portfolio)}`).join(' ');
    const benchDdPoints = data.map((d, i) => `${getX(i)},${getY(d.drawdown_benchmark)}`).join(' ');
    const zeroY = getY(0);

    return (
      <div style={{ position: 'relative', width: '100%', overflowX: 'auto' }}>
        <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} style={{ width: '100%', height: 'auto', display: 'block' }}>
          <line x1={padX} y1={zeroY} x2={svgWidth - 20} y2={zeroY} stroke="var(--border-subtle)" />
          <text x={padX - 8} y={zeroY + 4} fill="var(--text-muted)" fontSize="10" textAnchor="end">0.0%</text>
          <text x={padX - 8} y={svgHeight - padY} fill="var(--text-muted)" fontSize="10" textAnchor="end">
            {(minDd * 100).toFixed(1)}%
          </text>

          {/* Benchmark Drawdown */}
          <polyline fill="none" stroke="#EF4444" strokeWidth="1.5" strokeDasharray="3 3" points={benchDdPoints} />
          {/* Portfolio Drawdown */}
          <polyline fill="none" stroke="#F97316" strokeWidth="2" points={portDdPoints} />

          <text x={padX} y={svgHeight - 4} fill="var(--text-muted)" fontSize="10">{data[0].date}</text>
          <text x={svgWidth - 20} y={svgHeight - 4} fill="var(--text-muted)" fontSize="10" textAnchor="end">
            {data[data.length - 1].date}
          </text>
        </svg>

        <div style={{ display: 'flex', gap: '20px', justifyContent: 'center', marginTop: '8px', fontSize: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '12px', height: '3px', backgroundColor: '#F97316' }} />
            <span style={{ color: 'var(--text-primary)' }}>Portfolio Drawdown</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '12px', height: '2px', backgroundColor: '#EF4444', borderTop: '2px dashed #EF4444' }} />
            <span style={{ color: 'var(--text-secondary)' }}>Benchmark Drawdown</span>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="workspace-container">
      {/* Top Banner & Mode Toggle */}
      <div
        style={{
          background: 'linear-gradient(180deg, var(--bg-card) 0%, var(--bg-secondary) 100%)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-lg)',
          padding: '20px',
          marginBottom: '20px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '16px',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <span className="badge badge-info">Portfolio Attribution</span>
            <span className="badge badge-neutral">Stage 11 Production</span>
          </div>
          <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>
            Portfolio Performance Attribution & Benchmark Analysis
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '13px', maxWidth: '750px', lineHeight: 1.5 }}>
            Evaluate active returns relative to an empirical benchmark, analyze Menchero-linked asset return contributions,
            and inspect institutional risk-adjusted performance metrics.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={() => setShowHistoryDrawer(!showHistoryDrawer)}
            className="btn btn-secondary"
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <History size={15} />
            <span>Saved Reports ({savedReports.length})</span>
          </button>
        </div>
      </div>

      {/* History Drawer Modal / Sidebar */}
      {showHistoryDrawer && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            right: 0,
            width: '400px',
            height: '100vh',
            backgroundColor: 'var(--bg-card)',
            borderLeft: '1px solid var(--border-subtle)',
            zIndex: 100,
            padding: '24px',
            boxShadow: '-4px 0 24px rgba(0,0,0,0.4)',
            overflowY: 'auto',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '16px', fontWeight: 600 }}>Saved Attribution Reports</h3>
            <button onClick={() => setShowHistoryDrawer(false)} className="btn btn-ghost btn-sm">Close</button>
          </div>

          {loadingReports ? (
            <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>Loading reports...</p>
          ) : savedReports.length === 0 ? (
            <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>No saved performance reports yet.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {savedReports.map((rep) => (
                <div
                  key={rep.id}
                  onClick={() => handleLoadSavedReport(rep.id)}
                  style={{
                    padding: '12px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-subtle)',
                    backgroundColor: 'var(--bg-secondary)',
                    cursor: 'pointer',
                    transition: 'border-color 0.15s ease',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '6px' }}>
                    <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--text-primary)' }}>{rep.name}</div>
                    <button
                      onClick={(e) => handleDeleteSavedReport(e, rep.id)}
                      className="btn btn-ghost btn-sm"
                      style={{ padding: '2px', color: '#EF4444' }}
                      title="Delete report"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    Bench: <span style={{ color: 'var(--text-primary)' }}>{rep.benchmark_asset}</span> |{' '}
                    Active Ret: <span style={{ color: rep.arithmetic_active_return >= 0 ? '#10B981' : '#EF4444' }}>
                      {(rep.arithmetic_active_return * 100).toFixed(2)}%
                    </span>
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    Created: {new Date(rep.created_at).toLocaleDateString()}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Configuration Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1.8fr', gap: '20px', marginBottom: '24px' }}>
        {/* Source & Benchmark Controls */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Layers size={18} color="var(--accent-primary)" />
            <h3 style={{ fontSize: '15px', fontWeight: 600 }}>Evaluation Universe & Benchmark</h3>
          </div>

          {/* Mode Selector */}
          <div style={{ display: 'flex', gap: '10px', marginBottom: '16px' }}>
            <button
              onClick={() => setSourceMode('custom_portfolio')}
              className={`btn btn-sm ${sourceMode === 'custom_portfolio' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ flex: 1 }}
            >
              Custom Portfolio
            </button>
            <button
              onClick={() => setSourceMode('saved_backtest')}
              className={`btn btn-sm ${sourceMode === 'saved_backtest' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ flex: 1 }}
            >
              Saved Backtest
            </button>
          </div>

          {/* Report Name */}
          <div className="form-group" style={{ marginBottom: '12px' }}>
            <label className="form-label">Report Label</label>
            <input
              type="text"
              className="input-field"
              value={reportName}
              onChange={(e) => setReportName(e.target.value)}
            />
          </div>

          {/* Benchmark Asset Selector */}
          <div className="form-group" style={{ marginBottom: '12px' }}>
            <label className="form-label">Benchmark Asset</label>
            <select
              className="input-field"
              value={benchmarkAsset}
              onChange={(e) => setBenchmarkAsset(e.target.value)}
            >
              {availableAssets.map((a) => (
                <option key={a.asset_id} value={a.asset_id}>
                  {a.ticker} ({a.market}) — {a.asset_id}
                </option>
              ))}
            </select>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px', display: 'block' }}>
              Must exist in the selected dataset with identical currency.
            </span>
          </div>

          {/* If Saved Backtest Mode */}
          {sourceMode === 'saved_backtest' ? (
            <div className="form-group" style={{ marginBottom: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label className="form-label">Select Saved Backtest</label>
                {loadingBacktests && <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Loading...</span>}
              </div>
              {savedBacktests.length === 0 ? (
                <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  {loadingBacktests ? 'Loading saved backtests...' : 'No saved backtest runs found. Please run a backtest first.'}
                </div>
              ) : (
                <select
                  className="input-field"
                  value={selectedBacktestId}
                  onChange={(e) => setSelectedBacktestId(e.target.value)}
                >
                  {savedBacktests.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name} ({b.strategy_type}) — Total Ret: {(b.cumulative_return_net * 100).toFixed(1)}%
                    </option>
                  ))}
                </select>
              )}
            </div>
          ) : (
            /* Custom Portfolio Universe */
            <div style={{ marginBottom: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <label className="form-label" style={{ marginBottom: 0 }}>Portfolio Constituents</label>
                <button onClick={handleEqualWeight} className="btn btn-ghost btn-sm" style={{ fontSize: '11px' }}>
                  Equal Weight
                </button>
              </div>

              <div style={{ maxHeight: '180px', overflowY: 'auto', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '8px' }}>
                {availableAssets
                  .filter((a) => a.asset_id !== benchmarkAsset)
                  .map((a) => {
                    const isSelected = selectedAssets.includes(a.asset_id);
                    return (
                      <div
                        key={a.asset_id}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '4px 6px',
                          borderBottom: '1px solid var(--border-subtle)',
                        }}
                      >
                        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '12px' }}>
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => handleAssetToggle(a.asset_id)}
                          />
                          <span>{a.ticker}</span>
                        </label>
                        {isSelected && (
                          <input
                            type="number"
                            step="0.05"
                            min="0"
                            max="1"
                            style={{ width: '70px', padding: '2px 4px', fontSize: '12px', textAlign: 'right' }}
                            className="input-field"
                            value={weights[a.asset_id] ?? 0}
                            onChange={(e) => handleWeightChange(a.asset_id, parseFloat(e.target.value) || 0)}
                          />
                        )}
                      </div>
                    );
                  })}
              </div>
            </div>
          )}

          {/* Date Filter Inputs */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginTop: '12px' }}>
            <div className="form-group">
              <label className="form-label">Start Date (Optional)</label>
              <input
                type="date"
                className="input-field"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label">End Date (Optional)</label>
              <input
                type="date"
                className="input-field"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </div>
          </div>

          {/* Risk-Free Rate & Persist Toggle */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginTop: '12px' }}>
            <div className="form-group">
              <label className="form-label">Annual Risk-Free Rate</label>
              <input
                type="number"
                step="0.005"
                min="-0.05"
                max="0.30"
                className="input-field"
                value={riskFreeRate}
                onChange={(e) => setRiskFreeRate(parseFloat(e.target.value) || 0)}
              />
            </div>
            <div className="form-group" style={{ display: 'flex', alignItems: 'center', paddingTop: '20px' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '12px' }}>
                <input
                  type="checkbox"
                  checked={saveReport}
                  onChange={(e) => setSaveReport(e.target.checked)}
                />
                <span>Persist Report</span>
              </label>
            </div>
          </div>

          {/* Action Button */}
          <button
            onClick={handleExecute}
            disabled={isAnalyzing}
            className="btn btn-primary"
            style={{ width: '100%', marginTop: '16px', display: 'flex', justifyContent: 'center', gap: '8px' }}
          >
            {isAnalyzing ? (
              <span>Evaluating Attribution...</span>
            ) : (
              <>
                <PlayCircle size={16} />
                <span>Run Performance Attribution</span>
              </>
            )}
          </button>

          {error && (
            <div className="alert alert-error" style={{ marginTop: '12px' }}>
              <AlertTriangle size={16} />
              <div style={{ fontSize: '12px' }}>{error}</div>
            </div>
          )}
        </div>

        {/* Executive Summary Metrics Card */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Award size={18} color="var(--accent-primary)" />
            <h3 style={{ fontSize: '15px', fontWeight: 600 }}>Comparative Performance Summary</h3>
          </div>

          {!result ? (
            <div style={{ padding: '60px 20px', textAlign: 'center', color: 'var(--text-muted)' }}>
              <Award size={32} style={{ margin: '0 auto 12px', opacity: 0.4 }} />
              <p style={{ fontSize: '13px' }}>
                Select a benchmark and portfolio, then run performance evaluation to view active metrics.
              </p>
            </div>
          ) : (
            <div>
              {/* Primary KPI Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px', marginBottom: '16px' }}>
                <div style={{ padding: '10px', backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Portfolio Cumulative</div>
                  <div style={{ fontSize: '16px', fontWeight: 700, color: result.metrics.portfolio_cumulative_return >= 0 ? '#10B981' : '#EF4444' }}>
                    {(result.metrics.portfolio_cumulative_return * 100).toFixed(2)}%
                  </div>
                </div>

                <div style={{ padding: '10px', backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Benchmark Cumulative</div>
                  <div style={{ fontSize: '16px', fontWeight: 700, color: result.metrics.benchmark_cumulative_return >= 0 ? '#10B981' : '#EF4444' }}>
                    {(result.metrics.benchmark_cumulative_return * 100).toFixed(2)}%
                  </div>
                </div>

                <div style={{ padding: '10px', backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Arithmetic Active Return</div>
                  <div style={{ fontSize: '16px', fontWeight: 700, color: result.metrics.arithmetic_active_return >= 0 ? '#10B981' : '#EF4444' }}>
                    {(result.metrics.arithmetic_active_return * 100).toFixed(2)}%
                  </div>
                </div>

                <div style={{ padding: '10px', backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Tracking Error (Ann.)</div>
                  <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)' }}>
                    {(result.metrics.tracking_error * 100).toFixed(2)}%
                  </div>
                </div>
              </div>

              {/* Detailed Metrics Table */}
              <table className="table" style={{ fontSize: '12px', width: '100%', marginBottom: '16px' }}>
                <thead>
                  <tr>
                    <th>Risk-Adjusted Metric</th>
                    <th>Portfolio</th>
                    <th>Benchmark</th>
                    <th>Active / Ratio</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Annualized Return</td>
                    <td>{(result.metrics.portfolio_annualized_return * 100).toFixed(2)}%</td>
                    <td>{(result.metrics.benchmark_annualized_return * 100).toFixed(2)}%</td>
                    <td style={{ color: result.metrics.annualized_active_return >= 0 ? '#10B981' : '#EF4444' }}>
                      {(result.metrics.annualized_active_return * 100).toFixed(2)}%
                    </td>
                  </tr>
                  <tr>
                    <td>Annualized Volatility</td>
                    <td>{(result.metrics.portfolio_annualized_volatility * 100).toFixed(2)}%</td>
                    <td>{(result.metrics.benchmark_annualized_volatility * 100).toFixed(2)}%</td>
                    <td>—</td>
                  </tr>
                  <tr>
                    <td>Sharpe Ratio</td>
                    <td>{result.metrics.portfolio_sharpe_ratio !== null ? result.metrics.portfolio_sharpe_ratio.toFixed(2) : 'N/A'}</td>
                    <td>{result.metrics.benchmark_sharpe_ratio !== null ? result.metrics.benchmark_sharpe_ratio.toFixed(2) : 'N/A'}</td>
                    <td>—</td>
                  </tr>
                  <tr>
                    <td>Sortino Ratio</td>
                    <td>{result.metrics.portfolio_sortino_ratio !== null ? result.metrics.portfolio_sortino_ratio.toFixed(2) : 'N/A'}</td>
                    <td>{result.metrics.benchmark_sortino_ratio !== null ? result.metrics.benchmark_sortino_ratio.toFixed(2) : 'N/A'}</td>
                    <td>—</td>
                  </tr>
                  <tr>
                    <td>Max Drawdown</td>
                    <td style={{ color: '#EF4444' }}>{(result.metrics.portfolio_max_drawdown * 100).toFixed(2)}%</td>
                    <td style={{ color: '#EF4444' }}>{(result.metrics.benchmark_max_drawdown * 100).toFixed(2)}%</td>
                    <td>—</td>
                  </tr>
                  <tr>
                    <td>Information Ratio (IR)</td>
                    <td colSpan={2} style={{ color: 'var(--text-muted)' }}>Mean Active Ret / Tracking Error</td>
                    <td style={{ fontWeight: 600 }}>{result.metrics.information_ratio !== null ? result.metrics.information_ratio.toFixed(2) : 'N/A'}</td>
                  </tr>
                  <tr>
                    <td>Portfolio Beta (β)</td>
                    <td colSpan={2} style={{ color: 'var(--text-muted)' }}>Cov(p,b) / Var(b)</td>
                    <td style={{ fontWeight: 600 }}>{result.metrics.beta !== null ? result.metrics.beta.toFixed(2) : 'N/A'}</td>
                  </tr>
                  <tr>
                    <td>Jensen's Alpha (Ann.)</td>
                    <td colSpan={2} style={{ color: 'var(--text-muted)' }}>Excess Return - Beta * Bench Excess</td>
                    <td style={{ fontWeight: 600, color: (result.metrics.alpha_annualized ?? 0) >= 0 ? '#10B981' : '#EF4444' }}>
                      {result.metrics.alpha_annualized !== null ? `${(result.metrics.alpha_annualized * 100).toFixed(2)}%` : 'N/A'}
                    </td>
                  </tr>
                  <tr>
                    <td>Treynor Ratio</td>
                    <td colSpan={2} style={{ color: 'var(--text-muted)' }}>(Portfolio Return - Rf) / Beta</td>
                    <td style={{ fontWeight: 600 }}>{result.metrics.treynor_ratio !== null ? result.metrics.treynor_ratio.toFixed(2) : 'N/A'}</td>
                  </tr>
                  <tr>
                    <td>Up / Down Capture</td>
                    <td>Up: {result.metrics.up_capture_ratio !== null ? `${(result.metrics.up_capture_ratio * 100).toFixed(1)}%` : 'N/A'}</td>
                    <td>Down: {result.metrics.down_capture_ratio !== null ? `${(result.metrics.down_capture_ratio * 100).toFixed(1)}%` : 'N/A'}</td>
                    <td style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Relative Market Capture</td>
                  </tr>
                </tbody>
              </table>

              {result.warnings.length > 0 && (
                <div className="alert alert-warning" style={{ fontSize: '11px', padding: '8px 12px' }}>
                  <Info size={14} />
                  <div>{result.warnings.join(' ')}</div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Visual Analytics Section */}
      {result && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', marginBottom: '24px' }}>
          {/* Cumulative Wealth Comparison Chart */}
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
              <TrendingUp size={18} color="#38BDF8" />
              <h3 style={{ fontSize: '15px', fontWeight: 600 }}>Cumulative Wealth Evolution vs Benchmark</h3>
            </div>
            {renderCumulativeChart()}
          </div>

          {/* Drawdowns Over Time */}
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
              <TrendingDown size={18} color="#F97316" />
              <h3 style={{ fontSize: '15px', fontWeight: 600 }}>Drawdown Comparison Over Time</h3>
            </div>
            {renderActiveAndDrawdownChart()}
          </div>

          {/* Asset-Level Return Contribution Breakdown (Menchero Multi-Period) */}
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
              <PieChart size={18} color="var(--accent-primary)" />
              <h3 style={{ fontSize: '15px', fontWeight: 600 }}>
                Asset-Level Return Contribution (Menchero Multi-Period Linking)
              </h3>
            </div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '12px', marginBottom: '16px' }}>
              Multi-period asset contributions reconcile additively to cumulative portfolio return (
              <strong>{(result.metrics.portfolio_cumulative_return * 100).toFixed(2)}%</strong>) via Menchero logarithmic linking.
            </p>

            <table className="table" style={{ fontSize: '12px', width: '100%' }}>
              <thead>
                <tr>
                  <th>Asset Identifier</th>
                  <th>Weight</th>
                  <th>Cumulative Asset Return</th>
                  <th>Total Return Contribution</th>
                  <th>Share of Portfolio Return</th>
                  <th>Contribution Share Bar</th>
                </tr>
              </thead>
              <tbody>
                {result.contributions.map((c) => {
                  const contribPct = (c.total_contribution * 100).toFixed(2);
                  const sharePct = (c.share_of_return * 100).toFixed(1);
                  const barWidth = Math.min(Math.abs(c.share_of_return) * 100, 100);
                  const isPositive = c.total_contribution >= 0;

                  return (
                    <tr key={c.asset}>
                      <td style={{ fontWeight: 600 }}>{c.asset}</td>
                      <td>{(c.weight * 100).toFixed(1)}%</td>
                      <td style={{ color: c.cumulative_return >= 0 ? '#10B981' : '#EF4444' }}>
                        {(c.cumulative_return * 100).toFixed(2)}%
                      </td>
                      <td style={{ fontWeight: 600, color: isPositive ? '#10B981' : '#EF4444' }}>
                        {contribPct}%
                      </td>
                      <td>{sharePct}%</td>
                      <td style={{ width: '180px' }}>
                        <div style={{ width: '100%', height: '8px', backgroundColor: 'var(--bg-secondary)', borderRadius: '4px', overflow: 'hidden' }}>
                          <div
                            style={{
                              width: `${barWidth}%`,
                              height: '100%',
                              backgroundColor: isPositive ? '#10B981' : '#EF4444',
                              borderRadius: '4px',
                            }}
                          />
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Institutional Disclaimer */}
      <div className="alert alert-neutral" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
        <Info size={14} style={{ flexShrink: 0, marginTop: '2px' }} />
        <div>
          <strong>Quantitative Research Attribution Policy:</strong> Asset return contributions and risk-adjusted
          metrics (Tracking Error, Information Ratio, Beta, Jensen's Alpha) are historical diagnostic measurements.
          Brinson allocation and selection attribution is conditionally deferred when empirical benchmark constituent
          weights are unobserved in the uploaded price dataset. These analytics do not constitute investment recommendations.
        </div>
      </div>
    </div>
  );
};
