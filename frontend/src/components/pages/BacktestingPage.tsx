import React, { useState, useEffect } from 'react';
import {
  PlayCircle,
  TrendingUp,
  RefreshCw,
  AlertTriangle,
  History,
  Trash2,
  Activity,
  Layers,
  Lock,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { useDataset } from '../../context/DatasetContext';
import { SnapshotProvenanceBadge } from '../common/SnapshotProvenanceBadge';
import type {
  BacktestListItem,
  BacktestOptimizationObjective,
  BacktestRequest,
  BacktestResponse,
  PortfolioDefinition,
  RebalanceFrequency,
  StrategyType,
} from '../../types/api';

interface BacktestingPageProps {
  initialPortfolio?: PortfolioDefinition | null;
}

export const BacktestingPage: React.FC<BacktestingPageProps> = ({ initialPortfolio }) => {
  const { currentDataset, availableAssets } = useDataset();

  // Form State
  const [strategyType, setStrategyType] = useState<StrategyType>('target_weights');
  const [name, setName] = useState<string>('Long-Term Growth Simulation');
  const [selectedAssets, setSelectedAssets] = useState<string[]>([]);
  const [weights, setWeights] = useState<Record<string, number>>({});
  const [rebalanceFreq, setRebalanceFreq] = useState<RebalanceFrequency>('monthly');
  const [initialCapital, setInitialCapital] = useState<number>(100000);
  const [feeBps, setFeeBps] = useState<number>(10.0);
  const [slippageBps, setSlippageBps] = useState<number>(5.0);
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [trainingWindow, setTrainingWindow] = useState<number>(126);
  const [testWindow, setTestWindow] = useState<number>(21);
  const [optObjective, setOptObjective] = useState<BacktestOptimizationObjective>('max_sharpe');
  const [autoSnapshot, setAutoSnapshot] = useState<boolean>(true);

  // Execution & Results State
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BacktestResponse | null>(null);

  // History State
  const [historyRuns, setHistoryRuns] = useState<BacktestListItem[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string>('');

  // Initialize assets when dataset changes or initialPortfolio is provided
  useEffect(() => {
    if (initialPortfolio && initialPortfolio.assets && initialPortfolio.assets.length > 0) {
      setSelectedAssets(initialPortfolio.assets);
      setName(`${initialPortfolio.name} Simulation`);
      const equalWeight = 1.0 / initialPortfolio.assets.length;
      const initialW: Record<string, number> = {};
      initialPortfolio.assets.forEach((t) => {
        initialW[t] = parseFloat(equalWeight.toFixed(4));
      });
      setWeights(initialW);
    } else if (availableAssets.length > 0 && selectedAssets.length === 0) {
      const tickers = availableAssets.map((a) => a.ticker);
      setSelectedAssets(tickers);
      const equalWeight = 1.0 / tickers.length;
      const initialW: Record<string, number> = {};
      tickers.forEach((t) => {
        initialW[t] = parseFloat(equalWeight.toFixed(4));
      });
      setWeights(initialW);
    }
  }, [availableAssets, initialPortfolio]);

  // Fetch past backtests
  const loadHistory = async () => {
    try {
      const list = await apiClient.listBacktests();
      setHistoryRuns(list);
    } catch {
      // Ignore background listing errors
    }
  };

  useEffect(() => {
    loadHistory();
  }, []);

  const handleAssetToggle = (ticker: string) => {
    if (selectedAssets.includes(ticker)) {
      if (selectedAssets.length === 1) return; // Keep at least 1
      const updated = selectedAssets.filter((a) => a !== ticker);
      setSelectedAssets(updated);
      const newW = { ...weights };
      delete newW[ticker];
      setWeights(newW);
    } else {
      const updated = [...selectedAssets, ticker];
      setSelectedAssets(updated);
      const equalW = 1.0 / updated.length;
      const newW: Record<string, number> = {};
      updated.forEach((t) => {
        newW[t] = parseFloat(equalW.toFixed(4));
      });
      setWeights(newW);
    }
  };

  const handleWeightChange = (ticker: string, val: number) => {
    setWeights((prev) => ({
      ...prev,
      [ticker]: Math.max(0, val),
    }));
  };

  const handleNormalizeWeights = () => {
    const sum = Object.values(weights).reduce((a, b) => a + b, 0);
    if (sum <= 0) return;
    const normalized: Record<string, number> = {};
    Object.keys(weights).forEach((t) => {
      normalized[t] = parseFloat((weights[t] / sum).toFixed(4));
    });
    setWeights(normalized);
  };

  const handleRunSimulation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentDataset) {
      setError('Please select or upload a dataset before running a backtest.');
      return;
    }
    if (selectedAssets.length === 0) {
      setError('Please select at least one asset for the backtest.');
      return;
    }

    setIsRunning(true);
    setError(null);

    const req: BacktestRequest = {
      dataset_id: currentDataset.dataset_id,
      name,
      strategy_type: strategyType,
      assets: selectedAssets,
      weights: strategyType === 'target_weights' ? weights : null,
      rebalance_frequency: rebalanceFreq,
      initial_capital: Number(initialCapital),
      transaction_cost_bps: Number(feeBps),
      slippage_bps: Number(slippageBps),
      start_date: startDate || null,
      end_date: endDate || null,
      training_window: Number(trainingWindow),
      test_window: Number(testWindow),
      optimization_objective: optObjective,
      risk_free_rate: 0.02,
      auto_snapshot: autoSnapshot,
    };

    try {
      const resp = await apiClient.executeBacktest(req);
      setResult(resp);
      setSelectedRunId(resp.id);
      loadHistory();
    } catch (err: any) {
      setError(err.message || 'Simulation execution failed.');
    } finally {
      setIsRunning(false);
    }
  };

  const handleSelectPastRun = async (id: string) => {
    if (!id) return;
    setSelectedRunId(id);
    setIsRunning(true);
    setError(null);
    try {
      const resp = await apiClient.getBacktest(id);
      setResult(resp);
    } catch (err: any) {
      setError(err.message || 'Failed to load past backtest results.');
    } finally {
      setIsRunning(false);
    }
  };

  const handleDeleteRun = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await apiClient.deleteBacktest(id);
      setHistoryRuns((prev) => prev.filter((r) => r.id !== id));
      if (result && result.id === id) {
        setResult(null);
        setSelectedRunId('');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to delete backtest run.');
    }
  };

  const totalW = Object.values(weights).reduce((a, b) => a + b, 0);

  // SVG Chart helpers
  const renderEquityChart = () => {
    if (!result || result.equity_curve.length < 2) return null;
    const pts = result.equity_curve;
    const n = pts.length;
    const width = 800;
    const height = 300;
    const padding = 50;

    const valuesNet = pts.map((p) => p.portfolio_value_net);
    const valuesGross = pts.map((p) => p.portfolio_value_gross);
    const minVal = Math.min(...valuesNet, ...valuesGross) * 0.98;
    const maxVal = Math.max(...valuesNet, ...valuesGross) * 1.02;

    const getX = (idx: number) => padding + (idx / (n - 1)) * (width - 2 * padding);
    const getY = (val: number) => height - padding - ((val - minVal) / (maxVal - minVal || 1)) * (height - 2 * padding);

    const pathNet = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${getX(i)} ${getY(p.portfolio_value_net)}`).join(' ');
    const pathGross = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${getX(i)} ${getY(p.portfolio_value_gross)}`).join(' ');

    return (
      <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: 'auto', maxHeight: '350px' }}>
        {/* Horizontal grid lines */}
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

        {/* Date labels */}
        <text x={padding} y={height - 15} fill="#64748B" fontSize="10" fontFamily="monospace">
          {pts[0].date}
        </text>
        <text x={width - padding} y={height - 15} fill="#64748B" fontSize="10" textAnchor="end" fontFamily="monospace">
          {pts[n - 1].date}
        </text>

        {/* Gross Equity Line */}
        <path d={pathGross} fill="none" stroke="#94A3B8" strokeWidth="1.5" strokeDasharray="4 4" />

        {/* Net Equity Line */}
        <path d={pathNet} fill="none" stroke="#38BDF8" strokeWidth="2.5" />
      </svg>
    );
  };

  const renderDrawdownChart = () => {
    if (!result || result.equity_curve.length < 2) return null;
    const pts = result.equity_curve;
    const n = pts.length;
    const width = 800;
    const height = 180;
    const padding = 50;

    const minDd = Math.min(...pts.map((p) => p.drawdown_net), -0.05);
    const maxDd = 0.0;

    const getX = (idx: number) => padding + (idx / (n - 1)) * (width - 2 * padding);
    const getY = (val: number) => padding + ((maxDd - val) / (maxDd - minDd || 1)) * (height - 2 * padding);

    const pathDd = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${getX(i)} ${getY(p.drawdown_net)}`).join(' ');
    const areaDd = `${pathDd} L ${getX(n - 1)} ${getY(0)} L ${getX(0)} ${getY(0)} Z`;

    return (
      <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: 'auto', maxHeight: '200px' }}>
        {/* Zero baseline */}
        <line x1={padding} y1={getY(0)} x2={width - padding} y2={getY(0)} stroke="#475569" strokeWidth="1" />
        <text x={padding - 8} y={getY(0) + 4} fill="#64748B" fontSize="10" textAnchor="end" fontFamily="monospace">
          0.0%
        </text>
        <text x={padding - 8} y={getY(minDd) + 4} fill="#EF4444" fontSize="10" textAnchor="end" fontFamily="monospace">
          {(minDd * 100).toFixed(1)}%
        </text>

        {/* Drawdown Area */}
        <path d={areaDd} fill="rgba(239, 68, 68, 0.2)" />
        <path d={pathDd} fill="none" stroke="#EF4444" strokeWidth="1.5" />
      </svg>
    );
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-4 border-b border-slate-800 gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <PlayCircle className="text-sky-400" size={26} />
            Historical Simulation & Walk-Forward Backtesting
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Simulate portfolio performance with realistic rebalancing schedules, transaction fees, and execution slippage.
          </p>
        </div>

        {/* Run Selector */}
        {historyRuns.length > 0 && (
          <div className="flex items-center gap-2">
            <History size={16} className="text-slate-400" />
            <select
              value={selectedRunId}
              onChange={(e) => handleSelectPastRun(e.target.value)}
              className="bg-slate-900 border border-slate-700 text-xs text-slate-200 rounded px-2.5 py-1.5 focus:border-sky-500 focus:outline-none"
            >
              <option value="">-- Load Saved Backtest ({historyRuns.length}) --</option>
              {historyRuns.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name} ({(r.cumulative_return_net * 100).toFixed(1)}% | {r.created_at.slice(0, 10)})
                </option>
              ))}
            </select>
            {selectedRunId && (
              <button
                type="button"
                onClick={(e) => handleDeleteRun(selectedRunId, e)}
                className="p-1.5 text-red-400 hover:text-red-300 hover:bg-red-950/50 rounded border border-red-800 transition-colors"
                title="Delete this saved backtest run"
                aria-label="Delete saved backtest run"
              >
                <Trash2 size={14} />
              </button>
            )}
          </div>
        )}
      </div>

      {error && (
        <div className="p-4 bg-red-950/60 border border-red-800 rounded-lg flex items-center gap-3 text-red-200 text-sm">
          <AlertTriangle size={18} className="text-red-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Main Grid: Config Form & Simulation Results */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Configuration Card (4 cols) */}
        <div className="lg:col-span-4 space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-4 flex items-center gap-2">
              <Layers size={16} className="text-sky-400" />
              Strategy Configuration
            </h2>

            <form onSubmit={handleRunSimulation} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-400 font-medium mb-1">Backtest Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-white focus:border-sky-500 focus:outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-400 font-medium mb-1">Strategy Archetype</label>
                <select
                  value={strategyType}
                  onChange={(e) => setStrategyType(e.target.value as StrategyType)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-white focus:border-sky-500 focus:outline-none"
                >
                  <option value="target_weights">Target Weights (Fixed Allocation)</option>
                  <option value="equal_weight">Equal Weight (1/N Balanced)</option>
                  <option value="walk_forward_optimization">Walk-Forward Optimization (Zero Leakage)</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-400 font-medium mb-1">Rebalancing Schedule</label>
                <select
                  value={rebalanceFreq}
                  onChange={(e) => setRebalanceFreq(e.target.value as RebalanceFrequency)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-white focus:border-sky-500 focus:outline-none"
                >
                  <option value="monthly">Monthly (Calendar Month Boundaries)</option>
                  <option value="quarterly">Quarterly</option>
                  <option value="weekly">Weekly</option>
                  <option value="daily">Daily</option>
                  <option value="buy_and_hold">Buy & Hold (Inception Only)</option>
                </select>
              </div>

              {strategyType === 'walk_forward_optimization' && (
                <div className="p-3 bg-slate-950/80 border border-slate-800/80 rounded space-y-3">
                  <span className="text-sky-400 font-semibold block text-[11px] uppercase tracking-wider">
                    Walk-Forward Windows
                  </span>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-slate-400 text-[11px] mb-1">Train Window (Days)</label>
                      <input
                        type="number"
                        min="20"
                        max="1000"
                        value={trainingWindow}
                        onChange={(e) => setTrainingWindow(parseInt(e.target.value) || 126)}
                        className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-white text-xs"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 text-[11px] mb-1">Test Window (Days)</label>
                      <input
                        type="number"
                        min="1"
                        max="252"
                        value={testWindow}
                        onChange={(e) => setTestWindow(parseInt(e.target.value) || 21)}
                        className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-white text-xs"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-slate-400 text-[11px] mb-1">Objective</label>
                    <select
                      value={optObjective}
                      onChange={(e) => setOptObjective(e.target.value as BacktestOptimizationObjective)}
                      className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-white text-xs"
                    >
                      <option value="max_sharpe">Maximum Sharpe Ratio</option>
                      <option value="min_variance">Minimum Variance</option>
                    </select>
                  </div>
                </div>
              )}

              {/* Asset Selection */}
              <div>
                <label className="block text-slate-400 font-medium mb-1">
                  Asset Universe ({selectedAssets.length} selected)
                </label>
                <div className="max-h-32 overflow-y-auto space-y-1 bg-slate-950 p-2 rounded border border-slate-800">
                  {availableAssets.map((asset) => {
                    const isSelected = selectedAssets.includes(asset.ticker);
                    return (
                      <div
                        key={asset.asset_id}
                        onClick={() => handleAssetToggle(asset.ticker)}
                        className={`flex items-center justify-between px-2 py-1 rounded cursor-pointer transition-colors ${
                          isSelected ? 'bg-sky-950/60 text-sky-300' : 'text-slate-400 hover:bg-slate-900'
                        }`}
                      >
                        <span className="font-mono text-xs">{asset.ticker}</span>
                        <span className="text-[10px] text-slate-500">{asset.market}</span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Target Weights Inputs */}
              {strategyType === 'target_weights' && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-slate-400 font-medium">Target Weights</label>
                    <button
                      type="button"
                      onClick={handleNormalizeWeights}
                      className="text-[11px] text-sky-400 hover:text-sky-300 underline"
                    >
                      Normalize (Sum: {(totalW * 100).toFixed(1)}%)
                    </button>
                  </div>
                  <div className="max-h-36 overflow-y-auto space-y-1.5 bg-slate-950 p-2 rounded border border-slate-800">
                    {selectedAssets.map((ticker) => (
                      <div key={ticker} className="flex items-center gap-2">
                        <span className="w-16 font-mono text-xs text-slate-300">{ticker}</span>
                        <input
                          type="number"
                          step="0.01"
                          min="0"
                          max="1"
                          value={weights[ticker] ?? 0}
                          onChange={(e) => handleWeightChange(ticker, parseFloat(e.target.value) || 0)}
                          className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-white text-xs font-mono"
                        />
                        <span className="text-slate-500 font-mono text-xs w-10">
                          {(((weights[ticker] ?? 0) / (totalW || 1)) * 100).toFixed(0)}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Optional Date Range Filter */}
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-slate-400 text-[11px] mb-1">Start Date (Optional)</label>
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-white text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 text-[11px] mb-1">End Date (Optional)</label>
                  <input
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-white text-xs font-mono"
                  />
                </div>
              </div>

              {/* Capital & Friction Parameters */}
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block text-slate-400 text-[11px] mb-1">Capital ($)</label>
                  <input
                    type="number"
                    min="1000"
                    step="1000"
                    value={initialCapital}
                    onChange={(e) => setInitialCapital(parseFloat(e.target.value) || 100000)}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-white text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 text-[11px] mb-1">Fee (bps)</label>
                  <input
                    type="number"
                    min="0"
                    step="1"
                    value={feeBps}
                    onChange={(e) => setFeeBps(parseFloat(e.target.value) || 0)}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-white text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 text-[11px] mb-1">Slippage (bps)</label>
                  <input
                    type="number"
                    min="0"
                    step="1"
                    value={slippageBps}
                    onChange={(e) => setSlippageBps(parseFloat(e.target.value) || 0)}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-white text-xs font-mono"
                  />
                </div>
              </div>

              {/* Immutable Snapshot Toggle */}
              <div className="flex items-center gap-2 pt-2">
                <input
                  type="checkbox"
                  id="auto_snapshot"
                  checked={autoSnapshot}
                  onChange={(e) => setAutoSnapshot(e.target.checked)}
                  className="rounded border-slate-700 bg-slate-950 text-sky-500 focus:ring-sky-500"
                />
                <label htmlFor="auto_snapshot" className="text-slate-300 text-xs cursor-pointer flex items-center gap-1.5 select-none">
                  <Lock size={12} className="text-emerald-400" />
                  Seal Immutable Snapshot (0.0 Drift Protection)
                </label>
              </div>

              <button
                type="submit"
                disabled={isRunning}
                className="w-full py-2.5 px-4 bg-gradient-to-r from-sky-600 to-sky-500 hover:from-sky-500 hover:to-sky-400 text-white font-medium rounded shadow-lg transition-all flex items-center justify-center gap-2 mt-4 disabled:opacity-50"
              >
                {isRunning ? (
                  <>
                    <RefreshCw className="animate-spin" size={16} />
                    Simulating Strategy...
                  </>
                ) : (
                  <>
                    <PlayCircle size={16} />
                    Run Backtest Simulation
                  </>
                )}
              </button>
            </form>
          </div>
        </div>

        {/* Right Column: Analytics & Performance Results (8 cols) */}
        <div className="lg:col-span-8 space-y-6">
          {!result && !isRunning && (
            <div className="bg-slate-900 border border-slate-800 rounded-lg p-12 text-center text-slate-400">
              <TrendingUp size={48} className="mx-auto mb-3 text-slate-600" />
              <h3 className="text-lg font-semibold text-white mb-1">No Simulation Active</h3>
              <p className="text-xs max-w-md mx-auto">
                Configure your strategy parameters on the left and click "Run Backtest Simulation" to compute historical gross and net returns with realistic transaction frictions.
              </p>
            </div>
          )}

          {result && (
            <>
              {/* Summary Metrics Cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="bg-slate-900 border border-slate-800 p-3.5 rounded-lg">
                  <div className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">Final Net Equity</div>
                  <div className="text-lg font-bold font-mono text-white">
                    ${result.metrics.final_value_net.toLocaleString('en-US', { maximumFractionDigits: 0 })}
                  </div>
                  <div className={`text-xs font-mono font-medium ${result.metrics.cumulative_return_net >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {(result.metrics.cumulative_return_net * 100).toFixed(2)}% Net
                  </div>
                </div>

                <div className="bg-slate-900 border border-slate-800 p-3.5 rounded-lg">
                  <div className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">CAGR (Annualized)</div>
                  <div className="text-lg font-bold font-mono text-sky-400">
                    {(result.metrics.cagr_net * 100).toFixed(2)}%
                  </div>
                  <div className="text-xs text-slate-500 font-mono">
                    Gross: {(result.metrics.cagr_gross * 100).toFixed(2)}%
                  </div>
                </div>

                <div className="bg-slate-900 border border-slate-800 p-3.5 rounded-lg">
                  <div className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">Sharpe & Sortino</div>
                  <div className="text-lg font-bold font-mono text-white">
                    {result.metrics.sharpe_ratio_net?.toFixed(2) ?? 'N/A'}
                  </div>
                  <div className="text-xs text-slate-500 font-mono">
                    Sortino: {result.metrics.sortino_ratio_net?.toFixed(2) ?? 'N/A'}
                  </div>
                </div>

                <div className="bg-slate-900 border border-slate-800 p-3.5 rounded-lg">
                  <div className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">Max Drawdown</div>
                  <div className="text-lg font-bold font-mono text-rose-400">
                    {(result.metrics.max_drawdown_net * 100).toFixed(2)}%
                  </div>
                  <div className="text-xs text-slate-500 font-mono">
                    Vol: {(result.metrics.volatility_annualized_net * 100).toFixed(1)}%
                  </div>
                </div>
              </div>

              {/* Friction & Turnover Row */}
              <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 flex flex-wrap items-center justify-between text-xs gap-4">
                <div className="flex items-center gap-6">
                  <div>
                    <span className="text-slate-500 block text-[10px] uppercase">Total Friction Drag</span>
                    <span className="font-mono font-bold text-amber-400">
                      ${result.metrics.total_friction_costs.toLocaleString('en-US', { maximumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[10px] uppercase">Broker Commissions</span>
                    <span className="font-mono text-slate-300">
                      ${result.metrics.total_transaction_costs.toLocaleString('en-US', { maximumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[10px] uppercase">Slippage Drag</span>
                    <span className="font-mono text-slate-300">
                      ${result.metrics.total_slippage_costs.toLocaleString('en-US', { maximumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[10px] uppercase">Total Turnover</span>
                    <span className="font-mono text-slate-300">
                      {(result.metrics.total_turnover * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[10px] uppercase">Rebalance Events</span>
                    <span className="font-mono text-slate-300">{result.metrics.number_of_rebalances}</span>
                  </div>
                </div>

                <div className="text-slate-500 text-[11px] font-mono">
                  {result.metrics.effective_start_date} → {result.metrics.effective_end_date} ({result.metrics.observation_count} bars)
                </div>
              </div>

              {/* Dataset Snapshot Provenance Badge */}
              <SnapshotProvenanceBadge
                snapshotId={result.snapshot_id}
                provenance={result.snapshot_provenance}
              />

              {/* Equity Curve SVG Chart */}
              <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                    <Activity size={16} className="text-sky-400" />
                    Portfolio Wealth Progression (Gross vs. Net)
                  </h3>
                  <div className="flex items-center gap-4 text-xs font-mono">
                    <div className="flex items-center gap-1.5">
                      <span className="w-3 h-0.5 bg-sky-400 inline-block"></span>
                      <span className="text-slate-300">Net Portfolio Value</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="w-3 h-0.5 bg-slate-400 inline-block border-t border-dashed"></span>
                      <span className="text-slate-400">Gross (Pre-Friction)</span>
                    </div>
                  </div>
                </div>
                {renderEquityChart()}
              </div>

              {/* Underwater Drawdown Chart */}
              <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-3">
                <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                  <TrendingUp size={16} className="text-rose-400" />
                  Underwater Drawdown Profile
                </h3>
                {renderDrawdownChart()}
              </div>

              {/* Rebalance Events Table */}
              <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-3">
                <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
                  Rebalance Event History ({result.rebalance_events.length} Events)
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-slate-800 text-slate-500 font-mono text-[11px]">
                        <th className="py-2 px-3">Date</th>
                        <th className="py-2 px-3">Trigger / Reason</th>
                        <th className="py-2 px-3 text-right">Turnover</th>
                        <th className="py-2 px-3 text-right">Traded Notional</th>
                        <th className="py-2 px-3 text-right">Friction (Fee+Slip)</th>
                        <th className="py-2 px-3 text-right">Post-Value</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 font-mono">
                      {result.rebalance_events.map((ev, i) => (
                        <tr key={i} className="hover:bg-slate-800/30">
                          <td className="py-2 px-3 text-slate-300 font-medium">{ev.date}</td>
                          <td className="py-2 px-3 text-slate-400">{ev.reason}</td>
                          <td className="py-2 px-3 text-right text-slate-300">
                            {(ev.turnover * 100).toFixed(1)}%
                          </td>
                          <td className="py-2 px-3 text-right text-slate-300">
                            ${ev.traded_notional.toLocaleString('en-US', { maximumFractionDigits: 0 })}
                          </td>
                          <td className="py-2 px-3 text-right text-amber-400">
                            ${(ev.transaction_cost + ev.slippage_cost).toFixed(2)}
                          </td>
                          <td className="py-2 px-3 text-right text-white font-medium">
                            ${ev.portfolio_value_after.toLocaleString('en-US', { maximumFractionDigits: 0 })}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
