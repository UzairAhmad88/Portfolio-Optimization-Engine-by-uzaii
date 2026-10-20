import React, { useState, useEffect } from 'react';
import {
  Dice5,
  Activity,
  History,
  Trash2,
  AlertTriangle,
  PlayCircle,
  Sliders,
  Info,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { useDataset } from '../../context/DatasetContext';
import type {
  DistributionModel,
  MultiEstimatorComparison,
  PortfolioDefinition,
  RebalancePolicy,
  RiskSimulationListItem,
  RiskSimulationRequest,
  RiskSimulationResponse,
} from '../../types/api';

interface MonteCarloPageProps {
  initialPortfolio?: PortfolioDefinition | null;
}

type WorkspaceTab = 'simulation' | 'var_cvar' | 'saved_runs';

export const MonteCarloPage: React.FC<MonteCarloPageProps> = ({ initialPortfolio }) => {
  const { currentDataset, availableAssets } = useDataset();

  // Active Tab
  const [activeTab, setActiveTab] = useState<WorkspaceTab>('simulation');
  const [name, setName] = useState<string>('Portfolio Monte Carlo Risk Analysis');

  // Portfolio Holdings & Weights
  const [selectedAssets, setSelectedAssets] = useState<string[]>([]);
  const [weights, setWeights] = useState<Record<string, number>>({});
  const [initialCapital, setInitialCapital] = useState<number>(100000.0);

  // Simulation Parameters
  const [horizonDays, setHorizonDays] = useState<number>(21);
  const [numPaths, setNumPaths] = useState<number>(1000);
  const [distribution, setDistribution] = useState<DistributionModel>('multivariate_normal');
  const [degreesOfFreedom, setDegreesOfFreedom] = useState<number>(5.0);
  const [rebalancePolicy, setRebalancePolicy] = useState<RebalancePolicy>('buy_and_hold');
  const [seed, setSeed] = useState<string>('');
  const [conf95, setConf95] = useState<boolean>(true);
  const [conf99, setConf99] = useState<boolean>(true);
  const [lossThreshold, setLossThreshold] = useState<string>('15000');

  // Execution & Results State
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [simulationResult, setSimulationResult] = useState<RiskSimulationResponse | null>(null);
  const [standaloneComparisons, setStandaloneComparisons] = useState<MultiEstimatorComparison[] | null>(null);

  // Saved Runs Drawer & State
  const [savedRuns, setSavedRuns] = useState<RiskSimulationListItem[]>([]);
  const [loadingRuns, setLoadingRuns] = useState<boolean>(false);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  // Initialize from initialPortfolio or availableAssets
  useEffect(() => {
    if (initialPortfolio && initialPortfolio.weights && Object.keys(initialPortfolio.weights).length > 0) {
      setSelectedAssets(Object.keys(initialPortfolio.weights));
      setWeights(initialPortfolio.weights);
    } else if (availableAssets.length > 0 && selectedAssets.length === 0) {
      const topAssets = availableAssets.slice(0, 3).map((a) => a.asset_id);
      setSelectedAssets(topAssets);
      const equalWeight = Number((1.0 / topAssets.length).toFixed(4));
      const newWeights: Record<string, number> = {};
      topAssets.forEach((aid) => {
        newWeights[aid] = equalWeight;
      });
      setWeights(newWeights);
    }
  }, [initialPortfolio, availableAssets]);

  // Fetch saved runs when tab changes
  useEffect(() => {
    if (activeTab === 'saved_runs') {
      fetchSavedRuns();
    }
  }, [activeTab]);

  const fetchSavedRuns = async () => {
    setLoadingRuns(true);
    try {
      const runs = await apiClient.listRiskSimulations();
      setSavedRuns(runs);
    } catch (err: any) {
      setError(err?.message || 'Failed to load saved simulation runs.');
    } finally {
      setLoadingRuns(false);
    }
  };

  const handleWeightChange = (assetId: string, valStr: string) => {
    const val = parseFloat(valStr) || 0.0;
    setWeights((prev) => ({ ...prev, [assetId]: val }));
  };

  const handleAssetToggle = (assetId: string) => {
    if (selectedAssets.includes(assetId)) {
      if (selectedAssets.length <= 1) return;
      const next = selectedAssets.filter((a) => a !== assetId);
      setSelectedAssets(next);
      const eq = Number((1.0 / next.length).toFixed(4));
      const nextWeights: Record<string, number> = {};
      next.forEach((a) => {
        nextWeights[a] = eq;
      });
      setWeights(nextWeights);
    } else {
      const next = [...selectedAssets, assetId];
      setSelectedAssets(next);
      const eq = Number((1.0 / next.length).toFixed(4));
      const nextWeights: Record<string, number> = {};
      next.forEach((a) => {
        nextWeights[a] = eq;
      });
      setWeights(nextWeights);
    }
  };

  const applyPreset = (presetType: 'equal' | 'growth' | 'balanced') => {
    if (selectedAssets.length === 0) return;
    const n = selectedAssets.length;
    const newWeights: Record<string, number> = {};

    if (presetType === 'equal') {
      const eq = Number((1.0 / n).toFixed(4));
      selectedAssets.forEach((a) => {
        newWeights[a] = eq;
      });
    } else if (presetType === 'growth') {
      selectedAssets.forEach((a, i) => {
        newWeights[a] = i === 0 ? 0.7 : Number((0.3 / Math.max(1, n - 1)).toFixed(4));
      });
    } else if (presetType === 'balanced') {
      selectedAssets.forEach((a, i) => {
        newWeights[a] = i < Math.ceil(n / 2) ? Number((0.6 / Math.ceil(n / 2)).toFixed(4)) : Number((0.4 / Math.max(1, n - Math.ceil(n / 2))).toFixed(4));
      });
    }
    setWeights(newWeights);
  };

  const handleRunSimulation = async () => {
    if (!currentDataset) {
      setError('Please select or upload a dataset before running simulation.');
      return;
    }
    setError(null);
    setIsRunning(true);

    try {
      const confidenceLevels: number[] = [];
      if (conf95) confidenceLevels.push(0.95);
      if (conf99) confidenceLevels.push(0.99);
      if (confidenceLevels.length === 0) confidenceLevels.push(0.95);

      const parsedSeed = seed.trim() !== '' ? parseInt(seed, 10) : null;
      const parsedThresh = lossThreshold.trim() !== '' ? parseFloat(lossThreshold) : null;

      const req: RiskSimulationRequest = {
        dataset_id: currentDataset.dataset_id,
        name: name || 'Monte Carlo Simulation',
        assets: selectedAssets,
        weights,
        initial_capital: initialCapital,
        horizon_days: horizonDays,
        num_paths: numPaths,
        confidence_levels: confidenceLevels,
        distribution,
        degrees_of_freedom: distribution === 'multivariate_student_t' ? degreesOfFreedom : undefined,
        rebalance_policy: rebalancePolicy,
        seed: parsedSeed,
        loss_threshold: parsedThresh,
      };

      const resp = await apiClient.executeRiskSimulation(req);
      setSimulationResult(resp);
      setSelectedRunId(resp.id);
      setActiveTab('simulation');
    } catch (err: any) {
      setError(err?.message || 'Monte Carlo risk simulation execution failed.');
    } finally {
      setIsRunning(false);
    }
  };

  const handleStandaloneVaRCVaR = async () => {
    if (!currentDataset) {
      setError('Please select a dataset first.');
      return;
    }
    setError(null);
    setIsRunning(true);
    try {
      const confidenceLevels: number[] = [];
      if (conf95) confidenceLevels.push(0.95);
      if (conf99) confidenceLevels.push(0.99);

      const comps = await apiClient.calculateStandaloneVaRCVaR({
        dataset_id: currentDataset.dataset_id,
        assets: selectedAssets,
        weights,
        initial_capital: initialCapital,
        horizon_days: horizonDays,
        confidence_levels: confidenceLevels,
      });
      setStandaloneComparisons(comps);
      setActiveTab('var_cvar');
    } catch (err: any) {
      setError(err?.message || 'Failed to compute standalone VaR and CVaR.');
    } finally {
      setIsRunning(false);
    }
  };

  const handleLoadRun = async (runId: string) => {
    setError(null);
    setIsRunning(true);
    try {
      const resp = await apiClient.getRiskSimulation(runId);
      setSimulationResult(resp);
      setSelectedRunId(resp.id);
      setActiveTab('simulation');
    } catch (err: any) {
      setError(err?.message || `Failed to load run ${runId}`);
    } finally {
      setIsRunning(false);
    }
  };

  const handleDeleteRun = async (runId: string) => {
    try {
      await apiClient.deleteRiskSimulation(runId);
      setSavedRuns((prev) => prev.filter((r) => r.id !== runId));
      if (selectedRunId === runId) {
        setSimulationResult(null);
        setSelectedRunId(null);
      }
    } catch (err: any) {
      setError(err?.message || `Failed to delete run ${runId}`);
    }
  };

  // SVG Histogram Renderer for Terminal Return / Loss Distribution
  const renderDistributionHistogram = () => {
    if (!simulationResult || simulationResult.distribution_bins.length === 0) return null;

    const bins = simulationResult.distribution_bins;
    const maxFreq = Math.max(...bins.map((b) => b.relative_frequency), 0.001);

    const width = 640;
    const height = 260;
    const padX = 50;
    const padY = 35;
    const plotWidth = width - padX * 2;
    const plotHeight = height - padY * 2;

    const minReturn = bins[0].bin_start;
    const maxReturn = bins[bins.length - 1].bin_end;
    const returnRange = maxReturn - minReturn || 1.0;

    const getX = (val: number) => padX + ((val - minReturn) / returnRange) * plotWidth;
    const getY = (freq: number) => height - padY - (freq / maxFreq) * plotHeight;

    // Threshold lines: 0% return
    const zeroX = getX(0.0);

    // 95% and 99% VaR percentage lines
    const var95 = simulationResult.summary.var_cvar_metrics.find((m) => Math.abs(m.confidence_level - 0.95) < 1e-4);
    const var99 = simulationResult.summary.var_cvar_metrics.find((m) => Math.abs(m.confidence_level - 0.99) < 1e-4);

    // VaR is reported as positive loss: return is -var_percentage
    const var95X = var95 ? getX(-var95.var_percentage) : null;
    const var99X = var99 ? getX(-var99.var_percentage) : null;
    const cvar95X = var95 ? getX(-var95.cvar_percentage) : null;

    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h4 className="text-sm font-semibold text-slate-200">Terminal Portfolio Return Distribution</h4>
            <p className="text-xs text-slate-400">
              {simulationResult.num_paths.toLocaleString()} simulated paths over {simulationResult.horizon_days} trading days
            </p>
          </div>
          <div className="flex items-center gap-4 text-xs">
            <span className="flex items-center gap-1.5 text-slate-300">
              <span className="w-3 h-3 bg-indigo-500/60 border border-indigo-400 rounded-sm"></span> Density
            </span>
            <span className="flex items-center gap-1.5 text-rose-400 font-medium">
              <span className="w-3.5 h-0.5 bg-rose-500 inline-block border-b-2 border-dashed border-rose-500"></span> 95% VaR
            </span>
            <span className="flex items-center gap-1.5 text-purple-400 font-medium">
              <span className="w-3.5 h-0.5 bg-purple-500 inline-block border-b-2 border-dashed border-purple-500"></span> 95% CVaR
            </span>
          </div>
        </div>

        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto overflow-visible select-none">
          {/* Grid lines */}
          {[0, 0.25, 0.5, 0.75, 1.0].map((tickRatio) => {
            const y = height - padY - tickRatio * plotHeight;
            return (
              <g key={`grid-${tickRatio}`}>
                <line x1={padX} y1={y} x2={width - padX} y2={y} stroke="#334155" strokeDasharray="3,3" opacity="0.4" />
                <text x={padX - 8} y={y + 4} textAnchor="end" className="fill-slate-500 text-[10px] font-mono">
                  {(tickRatio * maxFreq * 100).toFixed(1)}%
                </text>
              </g>
            );
          })}

          {/* Histogram Bars */}
          {bins.map((b, idx) => {
            const bx = getX(b.bin_start);
            const bw = Math.max(1, getX(b.bin_end) - bx - 1);
            const by = getY(b.relative_frequency);
            const bh = height - padY - by;
            const isNegative = b.bin_end <= 0;

            return (
              <rect
                key={`bin-${idx}`}
                x={bx}
                y={by}
                width={bw}
                height={bh}
                fill={isNegative ? '#f43f5e' : '#6366f1'}
                fillOpacity="0.65"
                stroke={isNegative ? '#fda4af' : '#a5b4fc'}
                strokeWidth="0.75"
                rx="1"
              >
                <title>
                  {`Range: ${(b.bin_start * 100).toFixed(2)}% to ${(b.bin_end * 100).toFixed(2)}%\nCount: ${b.count} (${(b.relative_frequency * 100).toFixed(1)}%)`}
                </title>
              </rect>
            );
          })}

          {/* 0% Baseline */}
          {zeroX >= padX && zeroX <= width - padX && (
            <line x1={zeroX} y1={padY} x2={zeroX} y2={height - padY} stroke="#94a3b8" strokeWidth="1.5" strokeDasharray="2,2" />
          )}

          {/* 95% VaR Vertical Line */}
          {var95X && var95X >= padX && var95X <= width - padX && (
            <g>
              <line x1={var95X} y1={padY} x2={var95X} y2={height - padY} stroke="#f43f5e" strokeWidth="2" strokeDasharray="4,3" />
              <text x={var95X} y={padY - 8} textAnchor="middle" className="fill-rose-400 font-mono text-[10px] font-bold">
                VaR 95% ({- (var95!.var_percentage * 100).toFixed(1)}%)
              </text>
            </g>
          )}

          {/* 95% CVaR Vertical Line */}
          {cvar95X && cvar95X >= padX && cvar95X <= width - padX && (
            <g>
              <line x1={cvar95X} y1={padY} x2={cvar95X} y2={height - padY} stroke="#c084fc" strokeWidth="2" strokeDasharray="3,3" />
              <text x={cvar95X} y={padY - 20} textAnchor="middle" className="fill-purple-400 font-mono text-[10px] font-bold">
                CVaR 95% ({- (var95!.cvar_percentage * 100).toFixed(1)}%)
              </text>
            </g>
          )}

          {/* 99% VaR Vertical Line */}
          {var99X && var99X >= padX && var99X <= width - padX && (
            <line x1={var99X} y1={padY} x2={var99X} y2={height - padY} stroke="#e11d48" strokeWidth="1.5" strokeDasharray="2,2" />
          )}

          {/* X-axis labels */}
          {[-0.2, -0.1, 0, 0.1, 0.2].map((retTick) => {
            if (retTick < minReturn || retTick > maxReturn) return null;
            const x = getX(retTick);
            return (
              <g key={`x-${retTick}`}>
                <line x1={x} y1={height - padY} x2={x} y2={height - padY + 4} stroke="#64748b" />
                <text x={x} y={height - padY + 16} textAnchor="middle" className="fill-slate-400 text-[10px] font-mono">
                  {(retTick * 100).toFixed(0)}%
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    );
  };

  // SVG Trajectory Fan Chart Renderer
  const renderTrajectoryFanChart = () => {
    if (!simulationResult || simulationResult.trajectory.length === 0) return null;

    const traj = simulationResult.trajectory;
    const width = 640;
    const height = 260;
    const padX = 65;
    const padY = 30;
    const plotWidth = width - padX * 2;
    const plotHeight = height - padY * 2;

    const maxDay = traj[traj.length - 1].day || 1;
    let minVal = Math.min(...traj.map((p) => p.percentile_5));
    let maxVal = Math.max(...traj.map((p) => p.percentile_95));
    // Include initial capital in range
    minVal = Math.min(minVal, initialCapital * 0.95);
    maxVal = Math.max(maxVal, initialCapital * 1.05);
    const valRange = maxVal - minVal || 1.0;

    const getX = (d: number) => padX + (d / maxDay) * plotWidth;
    const getY = (v: number) => height - padY - ((v - minVal) / valRange) * plotHeight;

    // Construct SVG ribbon area (p5 to p95)
    let ribbonD = '';
    traj.forEach((pt, idx) => {
      const x = getX(pt.day);
      const y = getY(pt.percentile_95);
      ribbonD += `${idx === 0 ? 'M' : 'L'} ${x} ${y} `;
    });
    for (let i = traj.length - 1; i >= 0; i--) {
      const x = getX(traj[i].day);
      const y = getY(traj[i].percentile_5);
      ribbonD += `L ${x} ${y} `;
    }
    ribbonD += 'Z';

    // Median line path
    const medianD = traj.reduce((acc, pt, idx) => {
      const x = getX(pt.day);
      const y = getY(pt.median_value);
      return `${acc} ${idx === 0 ? 'M' : 'L'} ${x} ${y}`;
    }, '');

    // Sample paths (up to 15 paths)
    const sampleCount = traj[0].sample_paths.length;
    const pathsToRender = Math.min(15, sampleCount);

    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h4 className="text-sm font-semibold text-slate-200">Simulation Trajectory & Confidence Envelope</h4>
            <p className="text-xs text-slate-400">
              Evolution of portfolio wealth ($) across horizon ({simulationResult.horizon_days} trading days)
            </p>
          </div>
          <div className="flex items-center gap-4 text-xs">
            <span className="flex items-center gap-1.5 text-cyan-400 font-medium">
              <span className="w-3.5 h-0.5 bg-cyan-400 inline-block"></span> Median
            </span>
            <span className="flex items-center gap-1.5 text-indigo-400">
              <span className="w-3 h-3 bg-indigo-500/20 border border-indigo-500/40 rounded-sm"></span> 5th–95th %
            </span>
            <span className="flex items-center gap-1.5 text-slate-400">
              <span className="w-3 h-0.5 bg-slate-600 inline-block"></span> Sample Paths
            </span>
          </div>
        </div>

        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto overflow-visible select-none">
          {/* Y-axis grid */}
          {[0, 0.25, 0.5, 0.75, 1.0].map((ratio) => {
            const val = minVal + ratio * valRange;
            const y = height - padY - ratio * plotHeight;
            return (
              <g key={`ygrid-${ratio}`}>
                <line x1={padX} y1={y} x2={width - padX} y2={y} stroke="#334155" strokeDasharray="3,3" opacity="0.4" />
                <text x={padX - 8} y={y + 4} textAnchor="end" className="fill-slate-500 text-[10px] font-mono">
                  ${Math.round(val).toLocaleString()}
                </text>
              </g>
            );
          })}

          {/* 5th-95th Percentile Ribbon */}
          <path d={ribbonD} fill="#6366f1" fillOpacity="0.15" stroke="#6366f1" strokeOpacity="0.4" strokeWidth="1" />

          {/* Individual sample paths */}
          {Array.from({ length: pathsToRender }).map((_, pIdx) => {
            const pathD = traj.reduce((acc, pt, idx) => {
              const x = getX(pt.day);
              const y = getY(pt.sample_paths[pIdx] || initialCapital);
              return `${acc} ${idx === 0 ? 'M' : 'L'} ${x} ${y}`;
            }, '');
            return (
              <path
                key={`samp-path-${pIdx}`}
                d={pathD}
                fill="none"
                stroke="#94a3b8"
                strokeOpacity="0.25"
                strokeWidth="0.85"
              />
            );
          })}

          {/* Baseline Capital Line */}
          <line
            x1={padX}
            y1={getY(initialCapital)}
            x2={width - padX}
            y2={getY(initialCapital)}
            stroke="#e2e8f0"
            strokeDasharray="2,2"
            strokeWidth="1.2"
            opacity="0.6"
          />

          {/* Median Trajectory */}
          <path d={medianD} fill="none" stroke="#22d3ee" strokeWidth="2.5" />

          {/* X-axis days */}
          {[0, Math.floor(maxDay * 0.25), Math.floor(maxDay * 0.5), Math.floor(maxDay * 0.75), maxDay].map((d) => {
            const x = getX(d);
            return (
              <g key={`xday-${d}`}>
                <line x1={x} y1={height - padY} x2={x} y2={height - padY + 4} stroke="#64748b" />
                <text x={x} y={height - padY + 16} textAnchor="middle" className="fill-slate-400 text-[10px] font-mono">
                  Day {d}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    );
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header & Subtitle */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <Dice5 className="w-6 h-6 text-indigo-400" />
            <h1 className="text-2xl font-bold tracking-tight text-white">
              Monte Carlo Simulation & Probabilistic Risk Analysis
            </h1>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Multivariate stochastic return simulation, Value at Risk (VaR), Conditional Value at Risk (CVaR), and multi-estimator stress analytics.
          </p>
        </div>

        {/* Workspace Mode Tabs */}
        <div className="flex items-center bg-slate-900 border border-slate-800 p-1 rounded-lg">
          <button
            onClick={() => setActiveTab('simulation')}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
              activeTab === 'simulation' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Simulation Runner
          </button>
          <button
            onClick={() => setActiveTab('var_cvar')}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
              activeTab === 'var_cvar' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Multi-Estimator Comparison
          </button>
          <button
            onClick={() => setActiveTab('saved_runs')}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
              activeTab === 'saved_runs' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Saved Runs
          </button>
        </div>
      </div>

      {/* Error / Warning Alert */}
      {error && (
        <div className="bg-rose-950/40 border border-rose-800/80 rounded-lg p-4 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
          <div className="text-sm text-rose-200">
            <span className="font-semibold">Execution Error: </span>
            {error}
          </div>
        </div>
      )}

      {/* Main Grid: Parameters on Left, Output on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Configuration Controls */}
        <div className="lg:col-span-4 space-y-5">
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                <Sliders className="w-4 h-4 text-indigo-400" /> Simulation Parameters
              </h3>
              <div className="text-[11px] text-slate-400 font-mono">
                Dataset: {currentDataset?.filename ? currentDataset.filename.slice(0, 16) : 'None'}
              </div>
            </div>

            {/* Simulation Name */}
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Scenario / Run Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500"
              />
            </div>

            {/* Presets */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-medium text-slate-300">Quick Allocations</label>
                <span className="text-[10px] text-slate-500">Presets</span>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => applyPreset('equal')}
                  className="bg-slate-800/80 hover:bg-slate-800 border border-slate-700/60 rounded px-2 py-1 text-[11px] text-slate-300 transition"
                >
                  Equal Weight
                </button>
                <button
                  type="button"
                  onClick={() => applyPreset('growth')}
                  className="bg-slate-800/80 hover:bg-slate-800 border border-slate-700/60 rounded px-2 py-1 text-[11px] text-slate-300 transition"
                >
                  70/30 Growth
                </button>
                <button
                  type="button"
                  onClick={() => applyPreset('balanced')}
                  className="bg-slate-800/80 hover:bg-slate-800 border border-slate-700/60 rounded px-2 py-1 text-[11px] text-slate-300 transition"
                >
                  60/40 Balanced
                </button>
              </div>
            </div>

            {/* Initial Capital & Horizon */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Initial Capital ($)</label>
                <input
                  type="number"
                  min="1000"
                  step="5000"
                  value={initialCapital}
                  onChange={(e) => setInitialCapital(parseFloat(e.target.value) || 0)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500 font-mono"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Horizon (Days)</label>
                <select
                  value={horizonDays}
                  onChange={(e) => setHorizonDays(parseInt(e.target.value, 10))}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500 font-mono"
                >
                  <option value={1}>1 Day (Daily VaR)</option>
                  <option value={5}>5 Days (1 Week)</option>
                  <option value={10}>10 Days (2 Weeks)</option>
                  <option value={21}>21 Days (1 Month)</option>
                  <option value={63}>63 Days (1 Quarter)</option>
                  <option value={126}>126 Days (6 Months)</option>
                  <option value={252}>252 Days (1 Year)</option>
                </select>
              </div>
            </div>

            {/* Path Count & Distribution */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Number of Paths</label>
                <select
                  value={numPaths}
                  onChange={(e) => setNumPaths(parseInt(e.target.value, 10))}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500 font-mono"
                >
                  <option value={500}>500 Paths (Fast)</option>
                  <option value={1000}>1,000 Paths (Standard)</option>
                  <option value={2500}>2,500 Paths (High)</option>
                  <option value={5000}>5,000 Paths (Rigorous)</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Distribution</label>
                <select
                  value={distribution}
                  onChange={(e) => setDistribution(e.target.value as DistributionModel)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                >
                  <option value="multivariate_normal">Multivariate Normal</option>
                  <option value="multivariate_student_t">Multivariate Student-t</option>
                </select>
              </div>
            </div>

            {/* Student-t Degrees of Freedom (if selected) */}
            {distribution === 'multivariate_student_t' && (
              <div className="bg-slate-950 border border-slate-800 p-3 rounded space-y-1.5">
                <div className="flex justify-between text-xs">
                  <span className="text-slate-300 font-medium">Degrees of Freedom (ν):</span>
                  <span className="text-indigo-400 font-mono font-bold">{degreesOfFreedom.toFixed(1)}</span>
                </div>
                <input
                  type="range"
                  min="2.5"
                  max="15.0"
                  step="0.5"
                  value={degreesOfFreedom}
                  onChange={(e) => setDegreesOfFreedom(parseFloat(e.target.value))}
                  className="w-full accent-indigo-500"
                />
                <span className="text-[10px] text-slate-500 block">Lower ν produces fatter tails and heavier extreme losses.</span>
              </div>
            )}

            {/* Rebalance Policy & Seed */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Rebalancing</label>
                <select
                  value={rebalancePolicy}
                  onChange={(e) => setRebalancePolicy(e.target.value as RebalancePolicy)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                >
                  <option value="buy_and_hold">Buy & Hold (Drift)</option>
                  <option value="constant_weights">Constant Weights</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Random Seed</label>
                <input
                  type="number"
                  placeholder="e.g. 42 (Optional)"
                  value={seed}
                  onChange={(e) => setSeed(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500 font-mono"
                />
              </div>
            </div>

            {/* Confidence Levels & Loss Threshold */}
            <div className="space-y-2 pt-1 border-t border-slate-800">
              <label className="block text-xs font-medium text-slate-300">Confidence Levels</label>
              <div className="flex items-center gap-4 text-xs">
                <label className="flex items-center gap-1.5 text-slate-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={conf95}
                    onChange={(e) => setConf95(e.target.checked)}
                    className="accent-indigo-600 rounded"
                  />
                  95% Confidence
                </label>
                <label className="flex items-center gap-1.5 text-slate-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={conf99}
                    onChange={(e) => setConf99(e.target.checked)}
                    className="accent-indigo-600 rounded"
                  />
                  99% Confidence
                </label>
              </div>
              <div className="pt-2">
                <label className="block text-xs font-medium text-slate-300 mb-1">Tail Loss Threshold ($)</label>
                <input
                  type="number"
                  placeholder="e.g. 15000"
                  value={lossThreshold}
                  onChange={(e) => setLossThreshold(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500 font-mono"
                />
              </div>
            </div>

            {/* Constituent Assets & Weights */}
            <div className="space-y-2 pt-2 border-t border-slate-800">
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-slate-300">Holdings & Target Weights</label>
                <span className="text-[11px] font-mono text-indigo-400">
                  Sum: {(Object.values(weights).reduce((a, b) => a + b, 0) * 100).toFixed(1)}%
                </span>
              </div>
              <div className="max-h-40 overflow-y-auto space-y-1.5 pr-1">
                {availableAssets.map((asset) => {
                  const isChecked = selectedAssets.includes(asset.asset_id);
                  const w = weights[asset.asset_id] !== undefined ? weights[asset.asset_id] : 0.0;
                  return (
                    <div
                      key={asset.asset_id}
                      className="flex items-center justify-between bg-slate-950 px-2.5 py-1.5 rounded border border-slate-800/80"
                    >
                      <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => handleAssetToggle(asset.asset_id)}
                          className="accent-indigo-600 rounded"
                        />
                        <span className="font-semibold">{asset.ticker}</span>
                        <span className="text-[10px] text-slate-500">{asset.market}</span>
                      </label>
                      {isChecked && (
                        <div className="flex items-center gap-1">
                          <input
                            type="number"
                            min="0"
                            max="1"
                            step="0.05"
                            value={w}
                            onChange={(e) => handleWeightChange(asset.asset_id, e.target.value)}
                            className="w-16 bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5 text-right text-xs font-mono text-white focus:outline-none focus:border-indigo-500"
                          />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Run Actions */}
            <div className="pt-2 flex flex-col gap-2">
              <button
                type="button"
                onClick={handleRunSimulation}
                disabled={isRunning}
                className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-medium py-2 px-4 rounded-md text-xs flex items-center justify-center gap-2 transition disabled:opacity-50"
              >
                <PlayCircle className="w-4 h-4" />
                {isRunning ? 'Simulating Paths...' : 'Execute Monte Carlo Simulation'}
              </button>

              <button
                type="button"
                onClick={handleStandaloneVaRCVaR}
                disabled={isRunning}
                className="w-full bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium py-1.5 px-4 rounded-md text-xs flex items-center justify-center gap-2 transition disabled:opacity-50"
              >
                <Activity className="w-4 h-4 text-emerald-400" />
                Compute Quick Analytical VaR / CVaR
              </button>
            </div>
          </div>
        </div>

        {/* Right Column: Visualizations & Analytics Output */}
        <div className="lg:col-span-8 space-y-6">
          {activeTab === 'saved_runs' ? (
            /* Saved Runs Drawer */
            <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                  <History className="w-4 h-4 text-indigo-400" /> Saved Simulation Runs
                </h3>
                <button
                  type="button"
                  onClick={fetchSavedRuns}
                  className="text-xs text-indigo-400 hover:underline"
                >
                  Refresh
                </button>
              </div>

              {loadingRuns ? (
                <div className="text-xs text-slate-400 py-6 text-center">Loading simulation archive...</div>
              ) : savedRuns.length === 0 ? (
                <div className="text-xs text-slate-500 py-8 text-center">
                  No saved risk simulations found for this account.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-slate-950 text-slate-400 font-mono uppercase text-[10px]">
                      <tr>
                        <th className="px-3 py-2">Name</th>
                        <th className="px-3 py-2">Distribution</th>
                        <th className="px-3 py-2">Horizon</th>
                        <th className="px-3 py-2">Paths</th>
                        <th className="px-3 py-2">95% VaR</th>
                        <th className="px-3 py-2">95% CVaR</th>
                        <th className="px-3 py-2 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800 font-mono">
                      {savedRuns.map((r) => (
                        <tr key={r.id} className="hover:bg-slate-800/40">
                          <td className="px-3 py-2 font-sans font-medium text-slate-200">{r.name}</td>
                          <td className="px-3 py-2 text-slate-300">{r.distribution}</td>
                          <td className="px-3 py-2 text-slate-300">{r.horizon_days}d</td>
                          <td className="px-3 py-2 text-slate-300">{r.num_paths}</td>
                          <td className="px-3 py-2 text-rose-400">${Math.round(r.var_95).toLocaleString()}</td>
                          <td className="px-3 py-2 text-purple-400">${Math.round(r.cvar_95).toLocaleString()}</td>
                          <td className="px-3 py-2 text-right space-x-2">
                            <button
                              type="button"
                              onClick={() => handleLoadRun(r.id)}
                              className="text-indigo-400 hover:text-indigo-300 underline"
                            >
                              Load
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDeleteRun(r.id)}
                              className="text-rose-400 hover:text-rose-300"
                            >
                              <Trash2 className="w-3.5 h-3.5 inline" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : simulationResult ? (
            /* Active Simulation Tear Sheet */
            <div className="space-y-6">
              {/* KPI Summary Cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="bg-slate-900 border border-slate-800 p-3.5 rounded-lg">
                  <span className="text-[11px] font-medium text-slate-400 block mb-1">Expected Terminal Wealth</span>
                  <div className="text-base font-bold font-mono text-slate-100">
                    ${Math.round(simulationResult.summary.expected_terminal_value).toLocaleString()}
                  </div>
                  <span className={`text-[10px] font-mono ${simulationResult.summary.expected_terminal_return >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {(simulationResult.summary.expected_terminal_return * 100).toFixed(2)}% expected return
                  </span>
                </div>

                <div className="bg-slate-900 border border-slate-800 p-3.5 rounded-lg">
                  <span className="text-[11px] font-medium text-slate-400 block mb-1">Median Terminal Wealth</span>
                  <div className="text-base font-bold font-mono text-cyan-300">
                    ${Math.round(simulationResult.summary.median_terminal_value).toLocaleString()}
                  </div>
                  <span className="text-[10px] text-slate-500 font-mono">50th percentile outcome</span>
                </div>

                <div className="bg-slate-900 border border-slate-800 p-3.5 rounded-lg">
                  <span className="text-[11px] font-medium text-slate-400 block mb-1">Probability of Loss P(V_T &lt; V_0)</span>
                  <div className="text-base font-bold font-mono text-amber-400">
                    {(simulationResult.summary.prob_negative_return * 100).toFixed(1)}%
                  </div>
                  <span className="text-[10px] text-slate-500 font-mono">Negative terminal return</span>
                </div>

                <div className="bg-slate-900 border border-slate-800 p-3.5 rounded-lg">
                  <span className="text-[11px] font-medium text-slate-400 block mb-1">95% Value at Risk (VaR)</span>
                  <div className="text-base font-bold font-mono text-rose-400">
                    {simulationResult.summary.var_cvar_metrics[0]
                      ? `$${Math.round(simulationResult.summary.var_cvar_metrics[0].var_absolute).toLocaleString()}`
                      : 'N/A'}
                  </div>
                  <span className="text-[10px] text-rose-300/80 font-mono">
                    {simulationResult.summary.var_cvar_metrics[0]
                      ? `${(simulationResult.summary.var_cvar_metrics[0].var_percentage * 100).toFixed(2)}% of capital`
                      : ''}
                  </span>
                </div>
              </div>

              {/* Visualizations: Histogram & Trajectory */}
              {renderDistributionHistogram()}
              {renderTrajectoryFanChart()}

              {/* VaR & CVaR Estimator Comparison Table */}
              <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="text-sm font-semibold text-slate-200">
                      Multi-Estimator Value at Risk & Expected Shortfall Comparison
                    </h4>
                    <p className="text-xs text-slate-400">
                      Side-by-side comparison across Monte Carlo empirical, Parametric normal, and Historical empirical models
                    </p>
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-slate-950 text-slate-400 font-mono uppercase text-[10px]">
                      <tr>
                        <th className="px-3 py-2">Confidence Level</th>
                        <th className="px-3 py-2 text-rose-400">Monte Carlo VaR</th>
                        <th className="px-3 py-2 text-purple-400">Monte Carlo CVaR</th>
                        <th className="px-3 py-2 text-blue-400">Parametric VaR</th>
                        <th className="px-3 py-2 text-indigo-400">Parametric CVaR</th>
                        <th className="px-3 py-2 text-amber-400">Historical VaR</th>
                        <th className="px-3 py-2 text-amber-300">Historical CVaR</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800 font-mono">
                      {simulationResult.summary.estimator_comparisons.map((c) => (
                        <tr key={c.confidence_level} className="hover:bg-slate-800/40">
                          <td className="px-3 py-2.5 font-bold text-slate-200">
                            {(c.confidence_level * 100).toFixed(0)}%
                          </td>
                          <td className="px-3 py-2.5 text-rose-300 font-semibold">
                            ${Math.round(c.monte_carlo_var).toLocaleString()}
                          </td>
                          <td className="px-3 py-2.5 text-purple-300 font-semibold">
                            ${Math.round(c.monte_carlo_cvar).toLocaleString()}
                          </td>
                          <td className="px-3 py-2.5 text-blue-300">
                            ${Math.round(c.parametric_var).toLocaleString()}
                          </td>
                          <td className="px-3 py-2.5 text-indigo-300">
                            ${Math.round(c.parametric_cvar).toLocaleString()}
                          </td>
                          <td className="px-3 py-2.5 text-amber-300">
                            {c.historical_var !== null && c.historical_var !== undefined
                              ? `$${Math.round(c.historical_var).toLocaleString()}`
                              : 'N/A'}
                          </td>
                          <td className="px-3 py-2.5 text-amber-200">
                            {c.historical_cvar !== null && c.historical_cvar !== undefined
                              ? `$${Math.round(c.historical_cvar).toLocaleString()}`
                              : 'N/A'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Terminal Value Quantile Table */}
              <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-3">
                <h4 className="text-sm font-semibold text-slate-200">Simulated Terminal Quantiles</h4>
                <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
                  {Object.entries(simulationResult.summary.terminal_quantiles).map(([pKey, pVal]) => (
                    <div key={pKey} className="bg-slate-950 border border-slate-800 p-2.5 rounded text-center">
                      <span className="text-[10px] text-slate-500 uppercase font-mono">{pKey} Percentile</span>
                      <div className="text-xs font-bold font-mono text-slate-200 mt-0.5">
                        ${Math.round(pVal).toLocaleString()}
                      </div>
                      <span className={`text-[10px] font-mono ${pVal >= initialCapital ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {(((pVal - initialCapital) / initialCapital) * 100).toFixed(1)}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Non-prediction disclaimer */}
              <div className="bg-slate-950 border border-slate-800/80 rounded-lg p-4 flex items-start gap-3 text-xs text-slate-400">
                <Info className="w-4 h-4 text-slate-500 shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold text-slate-300">Institutional Model Governance Notice: </span>
                  {simulationResult.disclaimer}
                </div>
              </div>
            </div>
          ) : standaloneComparisons ? (
            /* Standalone VaR/CVaR Breakdown */
            <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-4">
              <h3 className="text-sm font-semibold text-slate-200">Analytical & Historical Risk Estimates</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead className="bg-slate-950 text-slate-400 font-mono uppercase text-[10px]">
                    <tr>
                      <th className="px-3 py-2">Confidence Level</th>
                      <th className="px-3 py-2 text-blue-400">Parametric VaR</th>
                      <th className="px-3 py-2 text-indigo-400">Parametric CVaR</th>
                      <th className="px-3 py-2 text-amber-400">Historical VaR</th>
                      <th className="px-3 py-2 text-amber-300">Historical CVaR</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800 font-mono">
                    {standaloneComparisons.map((c) => (
                      <tr key={c.confidence_level} className="hover:bg-slate-800/40">
                        <td className="px-3 py-2.5 font-bold text-slate-200">{(c.confidence_level * 100).toFixed(0)}%</td>
                        <td className="px-3 py-2.5 text-blue-300">${Math.round(c.parametric_var).toLocaleString()}</td>
                        <td className="px-3 py-2.5 text-indigo-300">${Math.round(c.parametric_cvar).toLocaleString()}</td>
                        <td className="px-3 py-2.5 text-amber-300">
                          {c.historical_var !== null && c.historical_var !== undefined
                            ? `$${Math.round(c.historical_var).toLocaleString()}`
                            : 'N/A'}
                        </td>
                        <td className="px-3 py-2.5 text-amber-200">
                          {c.historical_cvar !== null && c.historical_cvar !== undefined
                            ? `$${Math.round(c.historical_cvar).toLocaleString()}`
                            : 'N/A'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            /* Empty State */
            <div className="bg-slate-900 border border-slate-800 rounded-lg p-12 text-center space-y-3">
              <Dice5 className="w-12 h-12 text-indigo-500/60 mx-auto" />
              <h3 className="text-base font-semibold text-slate-200">Ready for Monte Carlo Simulation</h3>
              <p className="text-xs text-slate-400 max-w-md mx-auto">
                Configure your portfolio assets, simulation horizon, and distributional model on the left, then click{' '}
                <span className="text-indigo-400 font-medium">Execute Monte Carlo Simulation</span> to generate simulated wealth distributions, VaR, and CVaR.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
