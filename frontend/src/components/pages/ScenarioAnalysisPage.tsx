import React, { useState, useEffect } from 'react';
import {
  Zap,
  Activity,
  History,
  Trash2,
  AlertTriangle,
  PlayCircle,
  Sliders,
  Calendar,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { useDataset } from '../../context/DatasetContext';
import type {
  AssetShockContribution,
  PortfolioDefinition,
  ScenarioListItem,
  ScenarioRequest,
  ScenarioResponse,
  ScenarioType,
  SensitivityGridPoint,
  SensitivityRequest,
  SensitivityResponse,
} from '../../types/api';

interface ScenarioAnalysisPageProps {
  initialPortfolio?: PortfolioDefinition | null;
}

type AnalysisMode = 'custom_shock' | 'historical_window' | 'covariance_stress' | 'sensitivity';

export const ScenarioAnalysisPage: React.FC<ScenarioAnalysisPageProps> = ({ initialPortfolio }) => {
  const { currentDataset, availableAssets } = useDataset();

  // Mode Selection
  const [mode, setMode] = useState<AnalysisMode>('custom_shock');
  const [name, setName] = useState<string>('Portfolio Stress Test');

  // Asset Holdings & Capital
  const [selectedAssets, setSelectedAssets] = useState<string[]>([]);
  const [weights, setWeights] = useState<Record<string, number>>({});
  const [initialCapital, setInitialCapital] = useState<number>(100000);

  // Custom Shocks (Asset ID -> Fractional shock, e.g. -0.15)
  const [shocks, setShocks] = useState<Record<string, number>>({});

  // Historical Window
  const [histStartDate, setHistStartDate] = useState<string>('');
  const [histEndDate, setHistEndDate] = useState<string>('');

  // Covariance Stress
  const [volMultiplier, setVolMultiplier] = useState<number>(1.50);
  const [corrMultiplier, setCorrMultiplier] = useState<number>(1.20);
  const [autoProjectPsd, setAutoProjectPsd] = useState<boolean>(true);

  // Sensitivity Analysis
  const [factor1Asset, setFactor1Asset] = useState<string>('');
  const [f1MinShock, setF1MinShock] = useState<number>(-0.30);
  const [f1MaxShock, setF1MaxShock] = useState<number>(0.30);
  const [f1Steps, setF1Steps] = useState<number>(13);

  // Execution State
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [scenarioResult, setScenarioResult] = useState<ScenarioResponse | null>(null);
  const [sensitivityResult, setSensitivityResult] = useState<SensitivityResponse | null>(null);

  // History State
  const [savedScenarios, setSavedScenarios] = useState<ScenarioListItem[]>([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>('');

  // Initialize assets from initialPortfolio or currentDataset
  useEffect(() => {
    if (initialPortfolio && initialPortfolio.assets && initialPortfolio.assets.length > 0) {
      setSelectedAssets(initialPortfolio.assets);
      setName(`${initialPortfolio.name} Stress Analysis`);
      const equalW = 1.0 / initialPortfolio.assets.length;
      const initialW: Record<string, number> = {};
      const initialS: Record<string, number> = {};
      initialPortfolio.assets.forEach((t) => {
        initialW[t] = parseFloat(equalW.toFixed(4));
        initialS[t] = -0.10; // Default -10% shock
      });
      setWeights(initialW);
      setShocks(initialS);
      setFactor1Asset(initialPortfolio.assets[0]);
    } else if (availableAssets.length > 0 && selectedAssets.length === 0) {
      const tickers = availableAssets.map((a) => a.ticker);
      setSelectedAssets(tickers);
      const equalW = 1.0 / tickers.length;
      const initialW: Record<string, number> = {};
      const initialS: Record<string, number> = {};
      tickers.forEach((t) => {
        initialW[t] = parseFloat(equalW.toFixed(4));
        initialS[t] = -0.10;
      });
      setWeights(initialW);
      setShocks(initialS);
      if (tickers.length > 0) setFactor1Asset(tickers[0]);
    }
  }, [availableAssets, initialPortfolio]);

  // Load Saved Scenarios
  const loadHistory = async () => {
    try {
      const list = await apiClient.listScenarios();
      setSavedScenarios(list);
    } catch {
      // Background listing failure ignored
    }
  };

  useEffect(() => {
    loadHistory();
  }, []);

  const handleAssetToggle = (ticker: string) => {
    if (selectedAssets.includes(ticker)) {
      if (selectedAssets.length === 1) return;
      const updated = selectedAssets.filter((a) => a !== ticker);
      setSelectedAssets(updated);
      const newW = { ...weights };
      const newS = { ...shocks };
      delete newW[ticker];
      delete newS[ticker];
      setWeights(newW);
      setShocks(newS);
      if (factor1Asset === ticker && updated.length > 0) {
        setFactor1Asset(updated[0]);
      }
    } else {
      const updated = [...selectedAssets, ticker];
      setSelectedAssets(updated);
      const equalW = 1.0 / updated.length;
      const newW: Record<string, number> = {};
      const newS: Record<string, number> = { ...shocks, [ticker]: -0.10 };
      updated.forEach((t) => {
        newW[t] = parseFloat(equalW.toFixed(4));
      });
      setWeights(newW);
      setShocks(newS);
    }
  };

  const applyPreset = (presetName: string) => {
    const updatedS: Record<string, number> = {};
    if (presetName === 'crash_20') {
      selectedAssets.forEach((t) => {
        updatedS[t] = -0.20;
      });
      setName('Broad Market -20% Crash');
      setMode('custom_shock');
    } else if (presetName === 'correction_10') {
      selectedAssets.forEach((t) => {
        updatedS[t] = -0.10;
      });
      setName('Market -10% Correction');
      setMode('custom_shock');
    } else if (presetName === 'asymmetric') {
      selectedAssets.forEach((t, i) => {
        updatedS[t] = i % 2 === 0 ? -0.25 : 0.05;
      });
      setName('Asymmetric Asset Shock');
      setMode('custom_shock');
    } else if (presetName === 'vol_spike') {
      setMode('covariance_stress');
      setVolMultiplier(1.50);
      setCorrMultiplier(1.25);
      setName('Volatility & Correlation Spike');
    }
    setShocks(updatedS);
  };

  const handleExecute = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentDataset) {
      setError('Please select an active dataset first.');
      return;
    }
    if (selectedAssets.length === 0) {
      setError('Please select at least one asset.');
      return;
    }

    setIsRunning(true);
    setError(null);
    setScenarioResult(null);
    setSensitivityResult(null);

    try {
      if (mode === 'sensitivity') {
        const req: SensitivityRequest = {
          dataset_id: currentDataset.dataset_id,
          name,
          assets: selectedAssets,
          weights,
          initial_capital: Number(initialCapital),
          factor_1_asset: factor1Asset,
          factor_1_min_shock: Number(f1MinShock),
          factor_1_max_shock: Number(f1MaxShock),
          factor_1_steps: Number(f1Steps),
        };
        const resp = await apiClient.executeSensitivity(req);
        setSensitivityResult(resp);
      } else {
        let scnType: ScenarioType = 'custom_asset_shock';
        if (mode === 'historical_window') scnType = 'historical_window';
        if (mode === 'covariance_stress') scnType = 'covariance_stress';

        const req: ScenarioRequest = {
          dataset_id: currentDataset.dataset_id,
          name,
          scenario_type: scnType,
          assets: selectedAssets,
          weights,
          initial_capital: Number(initialCapital),
          asset_shocks: shocks,
          historical_start_date: histStartDate || null,
          historical_end_date: histEndDate || null,
          volatility_multiplier: mode === 'covariance_stress' ? Number(volMultiplier) : null,
          correlation_multiplier: mode === 'covariance_stress' ? Number(corrMultiplier) : null,
          auto_project_psd: autoProjectPsd,
        };

        const resp = await apiClient.executeScenario(req);
        setScenarioResult(resp);
        setSelectedScenarioId(resp.id);
        loadHistory();
      }
    } catch (err: any) {
      setError(err.message || 'Scenario execution failed.');
    } finally {
      setIsRunning(false);
    }
  };

  const handleSelectSavedScenario = async (id: string) => {
    if (!id) return;
    setSelectedScenarioId(id);
    setIsRunning(true);
    setError(null);
    try {
      const resp = await apiClient.getScenario(id);
      setScenarioResult(resp);
      setSensitivityResult(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load saved scenario.');
    } finally {
      setIsRunning(false);
    }
  };

  const handleDeleteScenario = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await apiClient.deleteScenario(id);
      setSavedScenarios((prev) => prev.filter((s) => s.id !== id));
      if (scenarioResult && scenarioResult.id === id) {
        setScenarioResult(null);
        setSelectedScenarioId('');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to delete scenario.');
    }
  };

  // Render Waterfall / Bar Chart of Asset Contributions
  const renderContributionChart = (contributions: AssetShockContribution[]) => {
    if (!contributions || contributions.length === 0) return null;
    const width = 750;
    const height = 260;
    const padding = 50;
    const barWidth = Math.min(45, (width - 2 * padding) / contributions.length - 12);

    const maxAbsVal = Math.max(...contributions.map((c) => Math.abs(c.value_change)), 1.0);
    const zeroY = height / 2;

    const getY = (val: number) => {
      const scale = (height / 2 - padding) / maxAbsVal;
      return zeroY - val * scale;
    };

    return (
      <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: 'auto', maxHeight: '300px' }}>
        {/* Zero baseline */}
        <line x1={padding} y1={zeroY} x2={width - padding} y2={zeroY} stroke="#475569" strokeWidth="1.5" />
        <text x={padding - 8} y={zeroY + 4} fill="#94A3B8" fontSize="10" textAnchor="end" fontFamily="monospace">
          $0
        </text>

        {contributions.map((c, i) => {
          const x = padding + i * ((width - 2 * padding) / contributions.length) + 6;
          const y = getY(Math.max(0, c.value_change));
          const barH = Math.max(2, Math.abs(getY(c.value_change) - zeroY));
          const isPos = c.value_change >= 0;
          const fill = isPos ? '#10B981' : '#EF4444';

          return (
            <g key={c.asset_id}>
              <rect
                x={x}
                y={isPos ? y : zeroY}
                width={barWidth}
                height={barH}
                fill={fill}
                rx={2}
                opacity={0.85}
              />
              {/* Asset label */}
              <text
                x={x + barWidth / 2}
                y={height - 10}
                fill="#94A3B8"
                fontSize="10"
                textAnchor="middle"
                fontFamily="monospace"
              >
                {c.ticker}
              </text>
              {/* Dollar value */}
              <text
                x={x + barWidth / 2}
                y={isPos ? y - 6 : zeroY + barH + 12}
                fill={fill}
                fontSize="9"
                textAnchor="middle"
                fontFamily="monospace"
              >
                {c.value_change >= 0 ? '+' : ''}${Math.round(c.value_change).toLocaleString()}
              </text>
            </g>
          );
        })}
      </svg>
    );
  };

  // Render 1D Sensitivity Curve
  const renderSensitivityChart = (points: SensitivityGridPoint[]) => {
    if (!points || points.length < 2) return null;
    const width = 750;
    const height = 260;
    const padding = 50;

    const xVals = points.map((p) => p.factor_1_value);
    const yVals = points.map((p) => p.percentage_change);

    const minX = Math.min(...xVals);
    const maxX = Math.max(...xVals);
    const minY = Math.min(...yVals, 0.0);
    const maxY = Math.max(...yVals, 0.0);

    const getX = (val: number) => padding + ((val - minX) / (maxX - minX || 1)) * (width - 2 * padding);
    const getY = (val: number) => height - padding - ((val - minY) / (maxY - minY || 1)) * (height - 2 * padding);

    const pathD = points
      .map((p, i) => `${i === 0 ? 'M' : 'L'} ${getX(p.factor_1_value)} ${getY(p.percentage_change)}`)
      .join(' ');

    return (
      <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: 'auto', maxHeight: '300px' }}>
        {/* Zero Return Line */}
        <line
          x1={padding}
          y1={getY(0)}
          x2={width - padding}
          y2={getY(0)}
          stroke="#475569"
          strokeWidth="1"
          strokeDasharray="3 3"
        />
        <text x={padding - 8} y={getY(0) + 4} fill="#94A3B8" fontSize="10" textAnchor="end" fontFamily="monospace">
          0.0%
        </text>

        {/* Sensitivity Curve */}
        <path d={pathD} fill="none" stroke="#38BDF8" strokeWidth="2.5" />

        {/* Data points */}
        {points.map((p, i) => (
          <circle key={i} cx={getX(p.factor_1_value)} cy={getY(p.percentage_change)} r={3.5} fill="#38BDF8" />
        ))}

        {/* Axis labels */}
        <text x={padding} y={height - 15} fill="#64748B" fontSize="10" fontFamily="monospace">
          {(minX * 100).toFixed(0)}% Shock
        </text>
        <text x={width - padding} y={height - 15} fill="#64748B" fontSize="10" textAnchor="end" fontFamily="monospace">
          {(maxX * 100).toFixed(0)}% Shock
        </text>
      </svg>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-4 border-b border-slate-800 gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <Zap className="text-sky-400" size={26} />
            Scenario Analysis & Portfolio Stress Testing
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Simulate instantaneous asset shocks, historical crisis replays, covariance stress, and parametric sensitivity.
          </p>
        </div>

        {/* Saved Scenarios Selector */}
        {savedScenarios.length > 0 && (
          <div className="flex items-center gap-2">
            <History size={16} className="text-slate-400" />
            <select
              value={selectedScenarioId}
              onChange={(e) => handleSelectSavedScenario(e.target.value)}
              className="bg-slate-900 border border-slate-700 text-xs text-slate-200 rounded px-2.5 py-1.5 focus:border-sky-500 focus:outline-none"
            >
              <option value="">-- Load Saved Scenario ({savedScenarios.length}) --</option>
              {savedScenarios.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({(s.percentage_change * 100).toFixed(1)}% | {s.created_at.slice(0, 10)})
                </option>
              ))}
            </select>
            {selectedScenarioId && (
              <button
                type="button"
                onClick={(e) => handleDeleteScenario(selectedScenarioId, e)}
                className="p-1.5 text-red-400 hover:text-red-300 hover:bg-red-950/50 rounded border border-red-800 transition-colors"
                title="Delete saved scenario run"
                aria-label="Delete saved scenario run"
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

      {/* Main Workspace Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Controls Column */}
        <div className="lg:col-span-5 space-y-5">
          <div className="card space-y-4">
            {/* Mode Tabs */}
            <div>
              <label className="block text-slate-400 text-xs font-medium uppercase tracking-wider mb-2">
                Analysis Engine Mode
              </label>
              <div className="grid grid-cols-2 gap-1.5 bg-slate-950 p-1.5 rounded-lg border border-slate-800 text-xs">
                <button
                  type="button"
                  onClick={() => setMode('custom_shock')}
                  className={`py-1.5 px-2 rounded font-medium transition-all ${
                    mode === 'custom_shock' ? 'bg-sky-600 text-white shadow' : 'text-slate-400 hover:text-white'
                  }`}
                >
                  Custom Shock
                </button>
                <button
                  type="button"
                  onClick={() => setMode('historical_window')}
                  className={`py-1.5 px-2 rounded font-medium transition-all ${
                    mode === 'historical_window' ? 'bg-sky-600 text-white shadow' : 'text-slate-400 hover:text-white'
                  }`}
                >
                  Historical Replay
                </button>
                <button
                  type="button"
                  onClick={() => setMode('covariance_stress')}
                  className={`py-1.5 px-2 rounded font-medium transition-all ${
                    mode === 'covariance_stress' ? 'bg-sky-600 text-white shadow' : 'text-slate-400 hover:text-white'
                  }`}
                >
                  Covariance Stress
                </button>
                <button
                  type="button"
                  onClick={() => setMode('sensitivity')}
                  className={`py-1.5 px-2 rounded font-medium transition-all ${
                    mode === 'sensitivity' ? 'bg-sky-600 text-white shadow' : 'text-slate-400 hover:text-white'
                  }`}
                >
                  Sensitivity Sweep
                </button>
              </div>
            </div>

            {/* Scenario Name */}
            <div>
              <label className="block text-slate-400 text-xs font-medium mb-1">Scenario Title</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-white text-xs"
              />
            </div>

            {/* Presets Bar */}
            <div>
              <label className="block text-slate-400 text-[11px] font-medium mb-1">Quick Presets</label>
              <div className="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  onClick={() => applyPreset('correction_10')}
                  className="px-2 py-1 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 rounded text-[11px]"
                >
                  -10% Correction
                </button>
                <button
                  type="button"
                  onClick={() => applyPreset('crash_20')}
                  className="px-2 py-1 bg-red-950/40 hover:bg-red-900/50 border border-red-800/80 text-red-300 rounded text-[11px]"
                >
                  -20% Market Crash
                </button>
                <button
                  type="button"
                  onClick={() => applyPreset('asymmetric')}
                  className="px-2 py-1 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 rounded text-[11px]"
                >
                  Asymmetric Shock
                </button>
                <button
                  type="button"
                  onClick={() => applyPreset('vol_spike')}
                  className="px-2 py-1 bg-amber-950/40 hover:bg-amber-900/50 border border-amber-800/80 text-amber-300 rounded text-[11px]"
                >
                  +50% Vol Spike
                </button>
              </div>
            </div>

            {/* Asset Selection & Holdings */}
            <div>
              <label className="block text-slate-400 text-xs font-medium mb-1">
                Portfolio Assets ({selectedAssets.length} selected)
              </label>
              <div className="max-h-28 overflow-y-auto space-y-1 bg-slate-950 p-2 rounded border border-slate-800">
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

            {/* Asset Weights & Shocks Table */}
            {mode === 'custom_shock' && (
              <div className="space-y-2">
                <label className="block text-slate-400 text-xs font-medium">Asset Allocation & Shocks</label>
                <div className="max-h-48 overflow-y-auto space-y-1.5 pr-1">
                  {selectedAssets.map((t) => (
                    <div key={t} className="grid grid-cols-12 gap-2 items-center bg-slate-950 p-1.5 rounded border border-slate-800">
                      <span className="col-span-3 font-mono text-xs text-white truncate">{t}</span>
                      <div className="col-span-4 flex items-center gap-1">
                        <span className="text-[10px] text-slate-500">W:</span>
                        <input
                          type="number"
                          step="0.05"
                          min="0"
                          max="1"
                          value={weights[t] ?? 0}
                          onChange={(e) => setWeights({ ...weights, [t]: parseFloat(e.target.value) || 0 })}
                          className="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5 text-xs text-white font-mono"
                        />
                      </div>
                      <div className="col-span-5 flex items-center gap-1">
                        <span className="text-[10px] text-slate-500">Shock:</span>
                        <input
                          type="number"
                          step="5"
                          min="-100"
                          max="200"
                          value={Math.round((shocks[t] ?? 0) * 100)}
                          onChange={(e) => setShocks({ ...shocks, [t]: (parseFloat(e.target.value) || 0) / 100 })}
                          className="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5 text-xs text-white font-mono"
                        />
                        <span className="text-[10px] text-slate-400">%</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Historical Window Inputs */}
            {mode === 'historical_window' && (
              <div className="space-y-3 p-3 bg-slate-950 rounded-lg border border-slate-800">
                <div className="flex items-center gap-2 text-xs font-medium text-slate-300">
                  <Calendar size={14} className="text-sky-400" />
                  <span>Historical Observation Window</span>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">Start Date</label>
                    <input
                      type="date"
                      value={histStartDate}
                      onChange={(e) => setHistStartDate(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs text-white font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">End Date</label>
                    <input
                      type="date"
                      value={histEndDate}
                      onChange={(e) => setHistEndDate(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs text-white font-mono"
                    />
                  </div>
                </div>
                <p className="text-[11px] text-slate-500">
                  Replays cumulative observed returns over the chosen interval without forward-filling.
                </p>
              </div>
            )}

            {/* Covariance Stress Inputs */}
            {mode === 'covariance_stress' && (
              <div className="space-y-3 p-3 bg-slate-950 rounded-lg border border-slate-800">
                <div className="flex items-center gap-2 text-xs font-medium text-slate-300">
                  <Activity size={14} className="text-amber-400" />
                  <span>Covariance Perturbation Controls</span>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">Vol Multiplier</label>
                    <input
                      type="number"
                      step="0.1"
                      min="0.1"
                      max="3.0"
                      value={volMultiplier}
                      onChange={(e) => setVolMultiplier(parseFloat(e.target.value) || 1.0)}
                      className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs text-white font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">Corr Multiplier</label>
                    <input
                      type="number"
                      step="0.05"
                      min="0.1"
                      max="2.0"
                      value={corrMultiplier}
                      onChange={(e) => setCorrMultiplier(parseFloat(e.target.value) || 1.0)}
                      className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs text-white font-mono"
                    />
                  </div>
                </div>
                <label className="flex items-center gap-2 text-[11px] text-slate-400 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={autoProjectPsd}
                    onChange={(e) => setAutoProjectPsd(e.target.checked)}
                    className="rounded border-slate-700"
                  />
                  <span>Auto-project negative eigenvalues to PSD (Spectral Clipping)</span>
                </label>
              </div>
            )}

            {/* Sensitivity Controls */}
            {mode === 'sensitivity' && (
              <div className="space-y-3 p-3 bg-slate-950 rounded-lg border border-slate-800">
                <div className="flex items-center gap-2 text-xs font-medium text-slate-300">
                  <Sliders size={14} className="text-sky-400" />
                  <span>1-Factor Sensitivity Parameters</span>
                </div>
                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">Target Factor Asset</label>
                  <select
                    value={factor1Asset}
                    onChange={(e) => setFactor1Asset(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs text-white font-mono"
                  >
                    {selectedAssets.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="block text-[10px] text-slate-400 mb-1">Min Shock</label>
                    <input
                      type="number"
                      step="0.05"
                      value={f1MinShock}
                      onChange={(e) => setF1MinShock(parseFloat(e.target.value) || -0.3)}
                      className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs text-white font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] text-slate-400 mb-1">Max Shock</label>
                    <input
                      type="number"
                      step="0.05"
                      value={f1MaxShock}
                      onChange={(e) => setF1MaxShock(parseFloat(e.target.value) || 0.3)}
                      className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs text-white font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] text-slate-400 mb-1">Steps</label>
                    <input
                      type="number"
                      min="3"
                      max="51"
                      value={f1Steps}
                      onChange={(e) => setF1Steps(parseInt(e.target.value) || 13)}
                      className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs text-white font-mono"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Base Capital */}
            <div>
              <label className="block text-slate-400 text-xs font-medium mb-1">Portfolio Base Capital ($)</label>
              <input
                type="number"
                step="1000"
                min="1000"
                value={initialCapital}
                onChange={(e) => setInitialCapital(parseFloat(e.target.value) || 100000)}
                className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-white text-xs font-mono"
              />
            </div>

            {/* Execute Button */}
            <button
              type="button"
              onClick={handleExecute}
              disabled={isRunning}
              className="w-full py-2.5 px-4 bg-gradient-to-r from-sky-600 to-sky-500 hover:from-sky-500 hover:to-sky-400 text-white font-medium rounded shadow-lg transition-all flex items-center justify-center gap-2 mt-2 disabled:opacity-50"
            >
              {isRunning ? (
                <span>Simulating Scenario...</span>
              ) : (
                <>
                  <PlayCircle size={16} />
                  <span>Execute Stress Analysis</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Results Column */}
        <div className="lg:col-span-7 space-y-5">
          {/* Scenario Results View */}
          {scenarioResult && (
            <div className="space-y-4">
              {/* Telemetry Cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="metric-card">
                  <div className="metric-label">Stressed Value</div>
                  <div className="metric-value font-mono" style={{ fontSize: '18px' }}>
                    ${scenarioResult.metrics.stressed_portfolio_value.toLocaleString()}
                  </div>
                  <div className="metric-sub">Base: ${scenarioResult.metrics.baseline_portfolio_value.toLocaleString()}</div>
                </div>

                <div className="metric-card">
                  <div className="metric-label">Net Impact ($)</div>
                  <div
                    className="metric-value font-mono"
                    style={{
                      fontSize: '18px',
                      color: scenarioResult.metrics.absolute_change >= 0 ? 'var(--success)' : 'var(--danger)',
                    }}
                  >
                    {scenarioResult.metrics.absolute_change >= 0 ? '+' : ''}$
                    {scenarioResult.metrics.absolute_change.toLocaleString()}
                  </div>
                  <div className="metric-sub">Absolute P&L</div>
                </div>

                <div className="metric-card">
                  <div className="metric-label">Return Impact (%)</div>
                  <div
                    className="metric-value font-mono"
                    style={{
                      fontSize: '18px',
                      color: scenarioResult.metrics.percentage_change >= 0 ? 'var(--success)' : 'var(--danger)',
                    }}
                  >
                    {(scenarioResult.metrics.percentage_change * 100).toFixed(2)}%
                  </div>
                  <div className="metric-sub">Portfolio Drawdown</div>
                </div>

                <div className="metric-card">
                  <div className="metric-label">Stressed Volatility</div>
                  <div className="metric-value font-mono" style={{ fontSize: '18px' }}>
                    {scenarioResult.metrics.stressed_volatility !== null && scenarioResult.metrics.stressed_volatility !== undefined
                      ? `${(scenarioResult.metrics.stressed_volatility * 100).toFixed(1)}%`
                      : '—'}
                  </div>
                  <div className="metric-sub">
                    {scenarioResult.metrics.baseline_volatility
                      ? `Base: ${(scenarioResult.metrics.baseline_volatility * 100).toFixed(1)}%`
                      : 'Covariance Stressed'}
                  </div>
                </div>
              </div>

              {/* Waterfall Chart Card */}
              <div className="card space-y-2">
                <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                  <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                    Asset Contribution Waterfall ($ Impact)
                  </span>
                  <span className="text-[11px] text-slate-500 font-mono">
                    Net: {scenarioResult.metrics.absolute_change >= 0 ? '+' : ''}$
                    {scenarioResult.metrics.absolute_change.toLocaleString()}
                  </span>
                </div>
                {renderContributionChart(scenarioResult.contributions)}
              </div>

              {/* Asset Contributions Table */}
              <div className="card space-y-2">
                <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider block pb-2 border-b border-slate-800">
                  Constituent Impact Breakdown
                </span>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-slate-800 text-slate-400 font-medium">
                        <th className="py-1.5 px-2">Asset</th>
                        <th className="py-1.5 px-2">Weight</th>
                        <th className="py-1.5 px-2">Shock</th>
                        <th className="py-1.5 px-2">Base Value</th>
                        <th className="py-1.5 px-2">Stressed Value</th>
                        <th className="py-1.5 px-2">P&L ($)</th>
                        <th className="py-1.5 px-2">Share of Loss</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 font-mono text-slate-200">
                      {scenarioResult.contributions.map((c) => (
                        <tr key={c.asset_id} className="hover:bg-slate-900/40">
                          <td className="py-1.5 px-2 font-semibold text-white">{c.ticker}</td>
                          <td className="py-1.5 px-2">{(c.baseline_weight * 100).toFixed(1)}%</td>
                          <td className="py-1.5 px-2" style={{ color: c.shock_pct >= 0 ? 'var(--success)' : 'var(--danger)' }}>
                            {c.shock_pct >= 0 ? '+' : ''}{c.shock_pct.toFixed(1)}%
                          </td>
                          <td className="py-1.5 px-2">${c.baseline_value.toLocaleString()}</td>
                          <td className="py-1.5 px-2">${c.stressed_value.toLocaleString()}</td>
                          <td
                            className="py-1.5 px-2"
                            style={{ color: c.value_change >= 0 ? 'var(--success)' : 'var(--danger)' }}
                          >
                            {c.value_change >= 0 ? '+' : ''}${c.value_change.toLocaleString()}
                          </td>
                          <td className="py-1.5 px-2">{(c.share_of_total_change * 100).toFixed(1)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Disclaimer */}
              <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-lg text-[11px] text-slate-400 leading-relaxed">
                <span className="font-semibold text-slate-300">Governance Notice: </span>
                {scenarioResult.disclaimer}
              </div>
            </div>
          )}

          {/* Sensitivity Results View */}
          {sensitivityResult && (
            <div className="space-y-4">
              <div className="card space-y-2">
                <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                  <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                    Parametric Sensitivity Curve ({sensitivityResult.factor_1_asset})
                  </span>
                  <span className="text-[11px] text-slate-500 font-mono">
                    {sensitivityResult.grid.length} evaluation points
                  </span>
                </div>
                {renderSensitivityChart(sensitivityResult.grid)}
              </div>

              <div className="card space-y-2">
                <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider block pb-2 border-b border-slate-800">
                  Sensitivity Grid Observations
                </span>
                <div className="max-h-60 overflow-y-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-slate-800 text-slate-400 font-medium">
                        <th className="py-1.5 px-2">Shock Value</th>
                        <th className="py-1.5 px-2">Stressed Portfolio Value</th>
                        <th className="py-1.5 px-2">P&L ($)</th>
                        <th className="py-1.5 px-2">Return (%)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 font-mono text-slate-200">
                      {sensitivityResult.grid.map((p, i) => (
                        <tr key={i} className="hover:bg-slate-900/40">
                          <td className="py-1.5 px-2">{(p.factor_1_value * 100).toFixed(1)}%</td>
                          <td className="py-1.5 px-2">${p.stressed_portfolio_value.toLocaleString()}</td>
                          <td
                            className="py-1.5 px-2"
                            style={{ color: p.absolute_change >= 0 ? 'var(--success)' : 'var(--danger)' }}
                          >
                            {p.absolute_change >= 0 ? '+' : ''}${p.absolute_change.toLocaleString()}
                          </td>
                          <td
                            className="py-1.5 px-2"
                            style={{ color: p.percentage_change >= 0 ? 'var(--success)' : 'var(--danger)' }}
                          >
                            {(p.percentage_change * 100).toFixed(2)}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Placeholder when no results yet */}
          {!scenarioResult && !sensitivityResult && (
            <div className="card flex flex-col items-center justify-center p-12 text-center text-slate-500 space-y-3">
              <Zap size={36} className="text-slate-600" />
              <div className="text-sm font-medium text-slate-400">Ready to Execute Stress Scenario</div>
              <p className="text-xs max-w-sm">
                Select an analysis mode, configure your asset shock parameters or sensitivity sweep on the left, and run the calculation.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
