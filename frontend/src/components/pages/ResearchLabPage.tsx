import React, { useState, useEffect } from 'react';
import {
  FlaskConical,
  PlayCircle,
  RotateCw,
  GitCompare,
  Trash2,
  AlertTriangle,
  Layers,
  ShieldCheck,
  PlusCircle,
  History as HistoryIcon,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { useDataset } from '../../context/DatasetContext';
import type {
  ComparisonResponse,
  DatasetMetadataResponse,
  ExperimentListItem,
  ExperimentResponse,
  ExperimentRunListItem,
  ExperimentRunResponse,
  ResearchStrategyType,
} from '../../types/api';

type ActiveTab = 'library' | 'new-experiment' | 'run-detail' | 'comparison';

export const ResearchLabPage: React.FC = () => {
  const { currentDataset, savedDatasets, availableAssets } = useDataset();

  // Navigation tab
  const [activeTab, setActiveTab] = useState<ActiveTab>('library');

  // Experiments state
  const [experiments, setExperiments] = useState<ExperimentListItem[]>([]);
  const [loadingExperiments, setLoadingExperiments] = useState<boolean>(false);
  const [experimentError, setExperimentError] = useState<string | null>(null);

  // Selected experiment & runs state
  const [selectedExperiment, setSelectedExperiment] = useState<ExperimentResponse | null>(null);
  const [experimentRuns, setExperimentRuns] = useState<ExperimentRunListItem[]>([]);
  const [selectedRunDetail, setSelectedRunDetail] = useState<ExperimentRunResponse | null>(null);
  const [loadingRuns, setLoadingRuns] = useState<boolean>(false);
  const [isExecutingRun, setIsExecutingRun] = useState<boolean>(false);

  // Form state for creating an experiment
  const [expName, setExpName] = useState<string>('Momentum vs Benchmark Alpha Hypothesis');
  const [expDescription, setExpDescription] = useState<string>('Out-of-sample attribution and tail risk testing');
  const [strategyType, setStrategyType] = useState<ResearchStrategyType>('target_weights');
  const [targetDatasetId, setTargetDatasetId] = useState<string>(currentDataset?.dataset_id || '');
  const [selectedAssets, setSelectedAssets] = useState<string[]>([]);
  const [assetWeights, setAssetWeights] = useState<Record<string, number>>({});
  const [rebalanceFreq, setRebalanceFreq] = useState<string>('monthly');
  const [costBps, setCostBps] = useState<number>(10.0);
  const [slippageBps, setSlippageBps] = useState<number>(5.0);
  const [objective, setObjective] = useState<string>('max_sharpe');
  const [benchmarkAsset, setBenchmarkAsset] = useState<string>('');
  const [riskFreeRate, setRiskFreeRate] = useState<number>(0.02);
  const [mcPaths, setMcPaths] = useState<number>(1000);
  const [mcHorizonDays, setMcHorizonDays] = useState<number>(21);
  const [mcDistribution, setMcDistribution] = useState<string>('normal');
  const [mcSeed, setMcSeed] = useState<number>(42);
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  // Comparison state
  const [selectedRunIdsForCompare, setSelectedRunIdsForCompare] = useState<string[]>([]);
  const [comparisonResult, setComparisonResult] = useState<ComparisonResponse | null>(null);
  const [isComparing, setIsComparing] = useState<boolean>(false);
  const [compareError, setCompareError] = useState<string | null>(null);

  // Available completed runs for comparison
  const [allCompletedRuns, setAllCompletedRuns] = useState<{ runId: string; label: string; expName: string; strat: string }[]>([]);

  // Load experiments on mount
  useEffect(() => {
    loadExperiments();
  }, []);

  // Update targetDatasetId if currentDataset changes
  useEffect(() => {
    if (currentDataset && !targetDatasetId) {
      setTargetDatasetId(currentDataset.dataset_id);
    }
  }, [currentDataset]);

  // Set default assets and benchmark from availableAssets
  useEffect(() => {
    if (availableAssets.length > 0 && selectedAssets.length === 0) {
      const top3 = availableAssets.slice(0, 3).map((a) => a.asset_id);
      setSelectedAssets(top3);
      const w: Record<string, number> = {};
      const split = Number((1.0 / top3.length).toFixed(4));
      top3.forEach((id, idx) => {
        w[id] = idx === top3.length - 1 ? Number((1.0 - split * (top3.length - 1)).toFixed(4)) : split;
      });
      setAssetWeights(w);

      const spyAsset = availableAssets.find((a) => a.ticker.toUpperCase() === 'SPY');
      if (spyAsset) {
        setBenchmarkAsset(spyAsset.asset_id);
      } else if (availableAssets.length > 0) {
        setBenchmarkAsset(availableAssets[0].asset_id);
      }
    }
  }, [availableAssets]);

  const loadExperiments = async () => {
    setLoadingExperiments(true);
    setExperimentError(null);
    try {
      const exps = await apiClient.listExperiments();
      setExperiments(exps);

      // Collect completed runs across experiments for the comparison picker
      const completedList: { runId: string; label: string; expName: string; strat: string }[] = [];
      for (const e of exps) {
        try {
          const runs = await apiClient.listExperimentRuns(e.id);
          runs.forEach((r) => {
            if (r.status === 'succeeded') {
              completedList.push({
                runId: r.id,
                label: `${e.name} (Run #${r.run_number})`,
                expName: e.name,
                strat: e.strategy_type,
              });
            }
          });
        } catch {
          // Ignore per-experiment run fetch errors
        }
      }
      setAllCompletedRuns(completedList);
    } catch (err: any) {
      setExperimentError(err.message || 'Failed to load research experiments.');
    } finally {
      setLoadingExperiments(false);
    }
  };

  const handleSelectExperiment = async (expId: string) => {
    setLoadingRuns(true);
    try {
      const exp = await apiClient.getExperiment(expId);
      setSelectedExperiment(exp);
      const runs = await apiClient.listExperimentRuns(expId);
      setExperimentRuns(runs);
      setSelectedRunDetail(null);
      setActiveTab('run-detail');
    } catch (err: any) {
      setExperimentError(err.message || 'Failed to fetch experiment details.');
    } finally {
      setLoadingRuns(false);
    }
  };

  const handleExecuteRun = async (expId: string) => {
    setIsExecutingRun(true);
    setExperimentError(null);
    try {
      const run = await apiClient.executeExperimentRun(expId);
      setSelectedRunDetail(run);
      // Reload runs list
      const updatedRuns = await apiClient.listExperimentRuns(expId);
      setExperimentRuns(updatedRuns);
      // Update experiments list in background
      loadExperiments();
    } catch (err: any) {
      setExperimentError(err.message || 'Experiment run execution failed.');
    } finally {
      setIsExecutingRun(false);
    }
  };

  const handleDeleteExperiment = async (expId: string, expName: string) => {
    if (!window.confirm(`Are you sure you want to delete research experiment "${expName}"? All execution runs will be permanently pruned.`)) {
      return;
    }
    try {
      await apiClient.deleteExperiment(expId);
      if (selectedExperiment?.id === expId) {
        setSelectedExperiment(null);
        setActiveTab('library');
      }
      loadExperiments();
    } catch (err: any) {
      alert(err.message || 'Failed to delete experiment.');
    }
  };

  const handleCreateExperiment = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!targetDatasetId) {
      setFormError('Please select a valid dataset for this research experiment.');
      return;
    }
    if (selectedAssets.length === 0) {
      setFormError('Please select at least one asset in the portfolio universe.');
      return;
    }

    if (strategyType === 'target_weights') {
      const totalW = Object.values(assetWeights).reduce((a, b) => a + b, 0);
      if (Math.abs(totalW - 1.0) > 0.005) {
        setFormError(`Target weights must sum to 1.0 (current sum: ${totalW.toFixed(4)}).`);
        return;
      }
    }

    if (strategyType === 'benchmark_attribution' && !benchmarkAsset) {
      setFormError('Benchmark attribution requires specifying a benchmark asset identifier.');
      return;
    }

    setIsSubmitting(true);
    try {
      const config: Record<string, any> = {
        assets: selectedAssets,
        rebalance_frequency: rebalanceFreq,
        transaction_cost_bps: costBps,
        slippage_bps: slippageBps,
      };

      if (strategyType === 'target_weights') {
        config.weights = assetWeights;
      } else if (strategyType === 'walk_forward_optimization') {
        config.objective = objective;
        config.training_window = 126;
      } else if (strategyType === 'benchmark_attribution') {
        config.benchmark_asset = benchmarkAsset;
        config.risk_free_rate = riskFreeRate;
        config.weights = assetWeights;
      } else if (strategyType === 'monte_carlo_risk') {
        config.weights = assetWeights;
        config.num_paths = mcPaths;
        config.horizon_days = mcHorizonDays;
        config.distribution = mcDistribution;
        config.seed = mcSeed;
      }

      const created = await apiClient.createExperiment({
        name: expName.trim(),
        description: expDescription.trim() || undefined,
        strategy_type: strategyType,
        dataset_id: targetDatasetId,
        config,
      });

      await loadExperiments();
      handleSelectExperiment(created.id);
    } catch (err: any) {
      setFormError(err.message || 'Failed to register research experiment.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCompareRuns = async () => {
    if (selectedRunIdsForCompare.length < 2) {
      setCompareError('Select at least 2 completed runs to perform cross-strategy comparison.');
      return;
    }
    setIsComparing(true);
    setCompareError(null);
    try {
      const resp = await apiClient.compareExperimentRuns({ run_ids: selectedRunIdsForCompare });
      setComparisonResult(resp);
    } catch (err: any) {
      setCompareError(err.message || 'Comparison failed.');
    } finally {
      setIsComparing(false);
    }
  };

  const toggleRunForCompare = (runId: string) => {
    setSelectedRunIdsForCompare((prev) =>
      prev.includes(runId) ? prev.filter((id) => id !== runId) : prev.length < 10 ? [...prev, runId] : prev
    );
  };

  const renderStrategyBadge = (type: string) => {
    switch (type) {
      case 'target_weights':
        return <span className="badge badge-info" style={{ fontSize: '11px' }}>Fixed Allocation</span>;
      case 'equal_weight':
        return <span className="badge badge-secondary" style={{ fontSize: '11px' }}>1/N Baseline</span>;
      case 'walk_forward_optimization':
        return <span className="badge badge-warning" style={{ fontSize: '11px' }}>Walk-Forward Optimization</span>;
      case 'benchmark_attribution':
        return <span className="badge badge-primary" style={{ fontSize: '11px' }}>Benchmark Attribution</span>;
      case 'monte_carlo_risk':
        return <span className="badge badge-purple" style={{ fontSize: '11px', backgroundColor: 'rgba(168, 85, 247, 0.15)', color: '#C084FC', border: '1px solid rgba(168, 85, 247, 0.3)' }}>Monte Carlo Risk</span>;
      default:
        return <span className="badge badge-neutral" style={{ fontSize: '11px' }}>{type}</span>;
    }
  };

  const renderStatusBadge = (status?: string | null) => {
    switch (status) {
      case 'succeeded':
        return <span className="badge badge-success" style={{ fontSize: '11px' }}>Succeeded</span>;
      case 'running':
        return <span className="badge badge-warning" style={{ fontSize: '11px' }}>Running...</span>;
      case 'failed':
        return <span className="badge badge-danger" style={{ fontSize: '11px' }}>Failed</span>;
      case 'pending':
        return <span className="badge badge-neutral" style={{ fontSize: '11px' }}>Pending</span>;
      default:
        return <span className="badge badge-neutral" style={{ fontSize: '11px' }}>No Runs Yet</span>;
    }
  };

  return (
    <div className="workspace-container">
      {/* Page Navigation Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '8px' }}>
          <button
            onClick={() => setActiveTab('library')}
            className={`btn ${activeTab === 'library' ? 'btn-primary' : 'btn-ghost'}`}
            style={{ fontSize: '13px', padding: '6px 14px' }}
          >
            <Layers size={14} />
            <span>Experiment Library ({experiments.length})</span>
          </button>
          <button
            onClick={() => setActiveTab('new-experiment')}
            className={`btn ${activeTab === 'new-experiment' ? 'btn-primary' : 'btn-ghost'}`}
            style={{ fontSize: '13px', padding: '6px 14px' }}
          >
            <PlusCircle size={14} />
            <span>New Hypothesis</span>
          </button>
          {selectedExperiment && (
            <button
              onClick={() => setActiveTab('run-detail')}
              className={`btn ${activeTab === 'run-detail' ? 'btn-primary' : 'btn-ghost'}`}
              style={{ fontSize: '13px', padding: '6px 14px' }}
            >
              <HistoryIcon size={14} />
              <span>{selectedExperiment.name} ({experimentRuns.length} Runs)</span>
            </button>
          )}
          <button
            onClick={() => setActiveTab('comparison')}
            className={`btn ${activeTab === 'comparison' ? 'btn-primary' : 'btn-ghost'}`}
            style={{ fontSize: '13px', padding: '6px 14px' }}
          >
            <GitCompare size={14} />
            <span>Strategy Comparison {selectedRunIdsForCompare.length > 0 ? `(${selectedRunIdsForCompare.length})` : ''}</span>
          </button>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Active Dataset: <strong style={{ color: 'var(--text-primary)' }}>{currentDataset ? currentDataset.filename : 'None'}</strong>
          </span>
          <button onClick={loadExperiments} className="btn btn-secondary btn-sm" title="Refresh Experiments">
            <RotateCw size={13} className={loadingExperiments ? 'spin' : ''} />
          </button>
        </div>
      </div>

      {experimentError && (
        <div className="alert alert-danger" style={{ marginBottom: '16px' }}>
          <AlertTriangle size={16} />
          <span>{experimentError}</span>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 1: EXPERIMENT LIBRARY                                                  */}
      {/* ========================================================================= */}
      {activeTab === 'library' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <div>
              <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                Quantitative Research Experiment Catalog
              </h3>
              <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '4px 0 0 0' }}>
                Auditable, versioned research blueprints linking hypotheses, mathematical constraints, and execution provenance.
              </p>
            </div>
            <button onClick={() => setActiveTab('new-experiment')} className="btn btn-primary btn-sm">
              <PlusCircle size={14} />
              <span>Define New Experiment</span>
            </button>
          </div>

          {loadingExperiments ? (
            <div className="card" style={{ textAlign: 'center', padding: '40px' }}>
              <div className="loading-spinner" style={{ margin: '0 auto 12px' }}></div>
              <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>Loading registered experiment Blueprints...</p>
            </div>
          ) : experiments.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: '50px 20px' }}>
              <FlaskConical size={36} style={{ color: 'var(--primary)', margin: '0 auto 14px', opacity: 0.8 }} />
              <h4 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '6px' }}>No Research Experiments Defined Yet</h4>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', maxWidth: '500px', margin: '0 auto 20px', lineHeight: 1.5 }}>
                Transform ad-hoc analytical runs into reproducible scientific research. Create an experiment to freeze parameters, audit dataset hashes, and compare multi-run variations.
              </p>
              <button onClick={() => setActiveTab('new-experiment')} className="btn btn-primary">
                <PlusCircle size={15} />
                <span>Create First Experiment</span>
              </button>
            </div>
          ) : (
            <div className="table-responsive card" style={{ padding: 0 }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Experiment Name</th>
                    <th>Strategy Archetype</th>
                    <th>Version</th>
                    <th>Config Fingerprint</th>
                    <th>Last Status</th>
                    <th>Runs</th>
                    <th>Created</th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {experiments.map((exp) => (
                    <tr key={exp.id}>
                      <td>
                        <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{exp.name}</div>
                        {exp.description && (
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)', maxWidth: '280px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {exp.description}
                          </div>
                        )}
                      </td>
                      <td>{renderStrategyBadge(exp.strategy_type)}</td>
                      <td>
                        <span className="badge badge-neutral" style={{ fontSize: '11px' }}>v{exp.version}</span>
                      </td>
                      <td>
                        <span className="font-mono text-xs" style={{ color: 'var(--primary)', backgroundColor: 'rgba(2, 132, 199, 0.08)', padding: '2px 6px', borderRadius: '4px' }}>
                          {exp.config_fingerprint.substring(0, 10)}...
                        </span>
                      </td>
                      <td>{renderStatusBadge(exp.latest_run_status)}</td>
                      <td>
                        <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>{exp.total_runs_count}</span>
                      </td>
                      <td style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                        {new Date(exp.created_at).toLocaleDateString()}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '6px' }}>
                          <button
                            onClick={() => handleSelectExperiment(exp.id)}
                            className="btn btn-secondary btn-sm"
                            title="Inspect History and Rerun"
                          >
                            <PlayCircle size={13} />
                            <span>Runs</span>
                          </button>
                          <button
                            onClick={() => handleDeleteExperiment(exp.id, exp.name)}
                            className="btn btn-ghost btn-sm"
                            style={{ color: 'var(--danger)' }}
                            title="Delete Experiment"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: NEW EXPERIMENT CONFIGURATION                                        */}
      {/* ========================================================================= */}
      {activeTab === 'new-experiment' && (
        <div style={{ maxWidth: '900px', margin: '0 auto' }}>
          <div className="card" style={{ marginBottom: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
              <div style={{ padding: '8px', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(2, 132, 199, 0.12)', color: 'var(--primary)' }}>
                <FlaskConical size={20} />
              </div>
              <div>
                <h3 style={{ fontSize: '16px', fontWeight: 600, margin: 0, color: 'var(--text-primary)' }}>
                  Define Reproducible Research Blueprint
                </h3>
                <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: 0 }}>
                  Configure validated quantitative hypotheses with frozen analytical inputs and deterministic seeds.
                </p>
              </div>
            </div>

            {formError && (
              <div className="alert alert-danger" style={{ marginBottom: '16px' }}>
                <AlertTriangle size={16} />
                <span>{formError}</span>
              </div>
            )}

            <form onSubmit={handleCreateExperiment}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px', marginBottom: '16px' }}>
                <div>
                  <label className="form-label">Experiment Name *</label>
                  <input
                    type="text"
                    className="form-control"
                    value={expName}
                    onChange={(e) => setExpName(e.target.value)}
                    required
                    placeholder="e.g. Min Variance vs Tech Heavy Benchmark"
                  />
                </div>
                <div>
                  <label className="form-label">Strategy Archetype *</label>
                  <select
                    className="form-control"
                    value={strategyType}
                    onChange={(e) => setStrategyType(e.target.value as ResearchStrategyType)}
                  >
                    <option value="target_weights">Target Weights (Fixed Allocation)</option>
                    <option value="equal_weight">Equal Weight (1/N Baseline)</option>
                    <option value="walk_forward_optimization">Walk-Forward Optimization (Rolling Out-of-Sample)</option>
                    <option value="benchmark_attribution">Benchmark Attribution & Relative Alpha</option>
                    <option value="monte_carlo_risk">Monte Carlo Risk & Tail Distribution</option>
                  </select>
                </div>
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label className="form-label">Research Hypothesis & Description</label>
                <textarea
                  className="form-control"
                  rows={2}
                  value={expDescription}
                  onChange={(e) => setExpDescription(e.target.value)}
                  placeholder="Declare investment thesis, expected return assumptions, or rebalance rationale..."
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px', marginBottom: '16px' }}>
                <div>
                  <label className="form-label">Authoritative Dataset *</label>
                  <select
                    className="form-control"
                    value={targetDatasetId}
                    onChange={(e) => setTargetDatasetId(e.target.value)}
                    required
                  >
                    <option value="">-- Select Registered Dataset --</option>
                    {savedDatasets.map((ds: DatasetMetadataResponse) => (
                      <option key={ds.dataset_id} value={ds.dataset_id}>
                        {ds.filename} ({ds.valid_rows.toLocaleString()} bars, {ds.content_sha256.substring(0, 8)}...)
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="form-label">Rebalance Frequency</label>
                  <select
                    className="form-control"
                    value={rebalanceFreq}
                    onChange={(e) => setRebalanceFreq(e.target.value)}
                    disabled={strategyType === 'benchmark_attribution'}
                  >
                    <option value="daily">Daily Rebalancing</option>
                    <option value="weekly">Weekly Rebalancing</option>
                    <option value="monthly">Monthly Rebalancing</option>
                    <option value="quarterly">Quarterly Rebalancing</option>
                    <option value="buy_and_hold">Buy & Hold (Zero Rebalance)</option>
                  </select>
                </div>
              </div>

              {/* Execution Frictions */}
              {strategyType !== 'monte_carlo_risk' && strategyType !== 'benchmark_attribution' && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '16px', padding: '12px', backgroundColor: 'var(--bg-subtle)', borderRadius: 'var(--radius-md)' }}>
                  <div>
                    <label className="form-label">Transaction Costs (bps)</label>
                    <input
                      type="number"
                      step="0.5"
                      min="0"
                      max="500"
                      className="form-control"
                      value={costBps}
                      onChange={(e) => setCostBps(parseFloat(e.target.value) || 0)}
                    />
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>10 bps = 0.10% fee</span>
                  </div>
                  <div>
                    <label className="form-label">Execution Slippage (bps)</label>
                    <input
                      type="number"
                      step="0.5"
                      min="0"
                      max="500"
                      className="form-control"
                      value={slippageBps}
                      onChange={(e) => setSlippageBps(parseFloat(e.target.value) || 0)}
                    />
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Market impact drag</span>
                  </div>
                </div>
              )}

              {/* Optimization Specific */}
              {strategyType === 'walk_forward_optimization' && (
                <div style={{ marginBottom: '16px', padding: '12px', backgroundColor: 'var(--bg-subtle)', borderRadius: 'var(--radius-md)' }}>
                  <label className="form-label">Optimization Objective</label>
                  <select className="form-control" value={objective} onChange={(e) => setObjective(e.target.value)}>
                    <option value="max_sharpe">Maximum Sharpe Ratio (Tangent Portfolio)</option>
                    <option value="min_variance">Minimum Variance (Global Minimum Risk)</option>
                  </select>
                </div>
              )}

              {/* Benchmark Specific */}
              {strategyType === 'benchmark_attribution' && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '16px', padding: '12px', backgroundColor: 'var(--bg-subtle)', borderRadius: 'var(--radius-md)' }}>
                  <div>
                    <label className="form-label">Benchmark Asset ID *</label>
                    <input
                      type="text"
                      className="form-control"
                      value={benchmarkAsset}
                      onChange={(e) => setBenchmarkAsset(e.target.value.toUpperCase())}
                      placeholder="e.g. SPY:US"
                      required
                    />
                  </div>
                  <div>
                    <label className="form-label">Risk-Free Rate (Annual)</label>
                    <input
                      type="number"
                      step="0.005"
                      className="form-control"
                      value={riskFreeRate}
                      onChange={(e) => setRiskFreeRate(parseFloat(e.target.value) || 0)}
                    />
                  </div>
                </div>
              )}

              {/* Monte Carlo Specific */}
              {strategyType === 'monte_carlo_risk' && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '14px', marginBottom: '16px', padding: '12px', backgroundColor: 'var(--bg-subtle)', borderRadius: 'var(--radius-md)' }}>
                  <div>
                    <label className="form-label">Simulation Paths</label>
                    <input
                      type="number"
                      min="100"
                      max="5000"
                      className="form-control"
                      value={mcPaths}
                      onChange={(e) => setMcPaths(parseInt(e.target.value) || 1000)}
                    />
                  </div>
                  <div>
                    <label className="form-label">Horizon (Days)</label>
                    <input
                      type="number"
                      min="1"
                      max="252"
                      className="form-control"
                      value={mcHorizonDays}
                      onChange={(e) => setMcHorizonDays(parseInt(e.target.value) || 21)}
                    />
                  </div>
                  <div>
                    <label className="form-label">Distribution</label>
                    <select className="form-control" value={mcDistribution} onChange={(e) => setMcDistribution(e.target.value)}>
                      <option value="normal">Multivariate Normal</option>
                      <option value="student_t">Multivariate Student-t (Fat tails)</option>
                    </select>
                  </div>
                  <div>
                    <label className="form-label">Seed (Reproducibility)</label>
                    <input
                      type="number"
                      className="form-control font-mono"
                      value={mcSeed}
                      onChange={(e) => setMcSeed(parseInt(e.target.value) || 42)}
                    />
                  </div>
                </div>
              )}

              {/* Asset Universe & Weights */}
              <div style={{ marginBottom: '20px' }}>
                <label className="form-label">Portfolio Constituent Assets</label>
                {availableAssets.length === 0 ? (
                  <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                    No assets discovered. Upload or select a dataset first.
                  </p>
                ) : (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '12px' }}>
                    {availableAssets.map((asset) => {
                      const isSelected = selectedAssets.includes(asset.asset_id);
                      return (
                        <button
                          key={asset.asset_id}
                          type="button"
                          onClick={() => {
                            if (isSelected) {
                              setSelectedAssets((prev) => prev.filter((id) => id !== asset.asset_id));
                              const copy = { ...assetWeights };
                              delete copy[asset.asset_id];
                              setAssetWeights(copy);
                            } else {
                              setSelectedAssets((prev) => [...prev, asset.asset_id]);
                              setAssetWeights((prev) => ({ ...prev, [asset.asset_id]: 0.0 }));
                            }
                          }}
                          className={`btn btn-sm ${isSelected ? 'btn-primary' : 'btn-secondary'}`}
                        >
                          {asset.ticker} ({asset.market})
                        </button>
                      );
                    })}
                  </div>
                )}

                {/* Weight Inputs if target weights */}
                {strategyType === 'target_weights' && selectedAssets.length > 0 && (
                  <div style={{ padding: '12px', backgroundColor: 'var(--bg-subtle)', borderRadius: 'var(--radius-md)' }}>
                    <div style={{ fontSize: '12px', fontWeight: 600, marginBottom: '8px' }}>Asset Allocation Weights (Sum = 1.0)</div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '10px' }}>
                      {selectedAssets.map((aid) => (
                        <div key={aid} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span style={{ fontSize: '12px', minWidth: '70px', fontWeight: 500 }}>{aid.split(':')[0]}:</span>
                          <input
                            type="number"
                            step="0.05"
                            min="0"
                            max="1"
                            className="form-control form-control-sm font-mono"
                            value={assetWeights[aid] ?? 0.0}
                            onChange={(e) => {
                              const val = parseFloat(e.target.value) || 0.0;
                              setAssetWeights((prev) => ({ ...prev, [aid]: val }));
                            }}
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button type="button" onClick={() => setActiveTab('library')} className="btn btn-secondary">
                  Cancel
                </button>
                <button type="submit" disabled={isSubmitting} className="btn btn-primary">
                  {isSubmitting ? (
                    <>
                      <div className="loading-spinner" style={{ width: '14px', height: '14px', borderWidth: '2px' }}></div>
                      <span>Hashing & Creating...</span>
                    </>
                  ) : (
                    <>
                      <FlaskConical size={14} />
                      <span>Create Experiment</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 3: RUN DETAIL & REPRODUCIBILITY AUDIT                                 */}
      {/* ========================================================================= */}
      {activeTab === 'run-detail' && selectedExperiment && (
        <div>
          {/* Header Card */}
          <div className="card" style={{ marginBottom: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                  <h3 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                    {selectedExperiment.name}
                  </h3>
                  <span className="badge badge-neutral">v{selectedExperiment.version}</span>
                  {renderStrategyBadge(selectedExperiment.strategy_type)}
                </div>
                {selectedExperiment.description && (
                  <p style={{ color: 'var(--text-secondary)', fontSize: '13px', margin: '0 0 10px 0' }}>
                    {selectedExperiment.description}
                  </p>
                )}
                <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', fontSize: '12px', color: 'var(--text-muted)' }}>
                  <div>
                    Config Fingerprint: <span className="font-mono" style={{ color: 'var(--primary)' }}>{selectedExperiment.config_fingerprint.substring(0, 16)}...</span>
                  </div>
                  <div>
                    Total Executions: <strong style={{ color: 'var(--text-primary)' }}>{experimentRuns.length}</strong>
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  onClick={() => handleExecuteRun(selectedExperiment.id)}
                  disabled={isExecutingRun}
                  className="btn btn-primary"
                >
                  {isExecutingRun ? (
                    <>
                      <div className="loading-spinner" style={{ width: '14px', height: '14px', borderWidth: '2px' }}></div>
                      <span>Simulating...</span>
                    </>
                  ) : (
                    <>
                      <PlayCircle size={15} />
                      <span>Execute Rerun (Run #{experimentRuns.length + 1})</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* Rerun Invariant Notice */}
          <div className="alert alert-info" style={{ marginBottom: '16px' }}>
            <ShieldCheck size={16} />
            <span>
              <strong>Scientific Rerun Invariant:</strong> Executing a rerun creates a separate, sequentially numbered execution run record (Run #{experimentRuns.length + 1}) while preserving all previous runs and capturing current dataset provenance. Historical records are never overwritten.
            </span>
          </div>

          {/* Runs History Table */}
          <div className="card" style={{ padding: 0, marginBottom: '20px' }}>
            <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ fontWeight: 600, fontSize: '14px' }}>Execution Run History</div>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Latest runs listed first</span>
            </div>

            {loadingRuns ? (
              <div style={{ padding: '30px', textAlign: 'center' }}>
                <div className="loading-spinner" style={{ margin: '0 auto 10px' }}></div>
                <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Fetching run records...</p>
              </div>
            ) : experimentRuns.length === 0 ? (
              <div style={{ padding: '30px', textAlign: 'center' }}>
                <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginBottom: '12px' }}>
                  No runs executed yet for this experiment definition.
                </p>
                <button onClick={() => handleExecuteRun(selectedExperiment.id)} disabled={isExecutingRun} className="btn btn-secondary btn-sm">
                  <PlayCircle size={13} />
                  <span>Execute Initial Run</span>
                </button>
              </div>
            ) : (
              <div className="table-responsive">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Run #</th>
                      <th>Status</th>
                      <th>Duration</th>
                      <th>Cumulative Return</th>
                      <th>Annualized Vol</th>
                      <th>Sharpe Ratio</th>
                      <th>Max Drawdown</th>
                      <th>Provenance</th>
                      <th>Executed At</th>
                      <th style={{ textAlign: 'right' }}>Inspect</th>
                    </tr>
                  </thead>
                  <tbody>
                    {experimentRuns.map((r) => {
                      const kpis = r.summary_kpis || {};
                      const isSelected = selectedRunDetail?.id === r.id;
                      return (
                        <tr key={r.id} style={{ backgroundColor: isSelected ? 'rgba(2, 132, 199, 0.05)' : undefined }}>
                          <td style={{ fontWeight: 600 }}>Run #{r.run_number}</td>
                          <td>{renderStatusBadge(r.status)}</td>
                          <td style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                            {r.execution_duration_ms ? `${r.execution_duration_ms} ms` : '—'}
                          </td>
                          <td style={{ fontWeight: 600, color: (kpis.cumulative_return ?? 0) >= 0 ? 'var(--success)' : 'var(--danger)' }}>
                            {kpis.cumulative_return !== undefined && kpis.cumulative_return !== null
                              ? `${(kpis.cumulative_return * 100).toFixed(2)}%`
                              : '—'}
                          </td>
                          <td>
                            {kpis.annualized_volatility !== undefined && kpis.annualized_volatility !== null
                              ? `${(kpis.annualized_volatility * 100).toFixed(2)}%`
                              : '—'}
                          </td>
                          <td>
                            {kpis.sharpe_ratio !== undefined && kpis.sharpe_ratio !== null
                              ? kpis.sharpe_ratio.toFixed(2)
                              : '—'}
                          </td>
                          <td style={{ color: 'var(--danger)' }}>
                            {kpis.max_drawdown !== undefined && kpis.max_drawdown !== null
                              ? `${(kpis.max_drawdown * 100).toFixed(2)}%`
                              : '—'}
                          </td>
                          <td>
                            {r.is_reproducible ? (
                              <span className="badge badge-success" style={{ fontSize: '10px' }}>Reproducible</span>
                            ) : (
                              <span className="badge badge-warning" style={{ fontSize: '10px' }}>Hash Drifted</span>
                            )}
                          </td>
                          <td style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                            {new Date(r.created_at).toLocaleTimeString()}
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            <button
                              onClick={async () => {
                                try {
                                  const full = await apiClient.getExperimentRun(r.id);
                                  setSelectedRunDetail(full);
                                } catch (err: any) {
                                  alert(err.message || 'Failed to fetch run details.');
                                }
                              }}
                              className="btn btn-secondary btn-sm"
                            >
                              <span>View KPIs</span>
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Selected Run Detailed Inspector */}
          {selectedRunDetail && (
            <div className="card" style={{ marginBottom: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '10px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <h4 style={{ fontSize: '16px', fontWeight: 600, margin: 0 }}>
                    Run #{selectedRunDetail.run_number} Diagnostic Tear-Sheet
                  </h4>
                  {renderStatusBadge(selectedRunDetail.status)}
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  ID: <span className="font-mono">{selectedRunDetail.id}</span>
                </div>
              </div>

              {/* Reproducibility Notes */}
              <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginBottom: '16px', padding: '10px 14px', backgroundColor: 'var(--bg-subtle)', borderRadius: 'var(--radius-md)' }}>
                <ShieldCheck size={18} style={{ color: selectedRunDetail.is_reproducible ? 'var(--success)' : 'var(--warning)', flexShrink: 0 }} />
                <div style={{ fontSize: '12px' }}>
                  <strong>Dataset Provenance:</strong> {selectedRunDetail.reproducibility_notes.join(' ')}
                  {selectedRunDetail.dataset_version_hash && (
                    <span className="font-mono" style={{ marginLeft: '6px', color: 'var(--text-muted)' }}>
                      [SHA-256: {selectedRunDetail.dataset_version_hash.substring(0, 12)}...]
                    </span>
                  )}
                </div>
              </div>

              {/* KPI Metrics Grid */}
              {selectedRunDetail.summary_kpis && (
                <div className="metric-grid" style={{ marginBottom: '16px' }}>
                  {Object.entries(selectedRunDetail.summary_kpis).map(([k, v]) => {
                    if (v === null || v === undefined) return null;
                    let displayVal = String(v);
                    if (typeof v === 'number') {
                      if (['cumulative_return', 'cagr', 'annualized_volatility', 'max_drawdown', 'active_return', 'var_95', 'cvar_95', 'prob_loss'].includes(k)) {
                        displayVal = `${(v * 100).toFixed(2)}%`;
                      } else if (['final_value', 'initial_capital', 'total_friction_costs'].includes(k)) {
                        displayVal = v.toLocaleString(undefined, { maximumFractionDigits: 2 });
                      } else {
                        displayVal = v.toFixed(3);
                      }
                    }
                    const formattedLabel = k.replace(/_/g, ' ').toUpperCase();
                    return (
                      <div key={k} className="metric-card">
                        <div className="metric-label">{formattedLabel}</div>
                        <div className="metric-value font-mono" style={{ fontSize: '18px' }}>
                          {displayVal}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Linked Artifact References */}
              <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', fontSize: '12px', color: 'var(--text-secondary)' }}>
                {selectedRunDetail.backtest_id && (
                  <div>
                    Linked Backtest: <span className="font-mono text-xs">{selectedRunDetail.backtest_id}</span>
                  </div>
                )}
                {selectedRunDetail.performance_report_id && (
                  <div>
                    Linked Report: <span className="font-mono text-xs">{selectedRunDetail.performance_report_id}</span>
                  </div>
                )}
                {selectedRunDetail.risk_simulation_id && (
                  <div>
                    Linked Risk Sim: <span className="font-mono text-xs">{selectedRunDetail.risk_simulation_id}</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 4: MULTI-STRATEGY COMPARISON WORKSPACE                                */}
      {/* ========================================================================= */}
      {activeTab === 'comparison' && (
        <div>
          {/* Picker Card */}
          <div className="card" style={{ marginBottom: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px', marginBottom: '14px' }}>
              <div>
                <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                  Multi-Strategy Cross-Sectional Comparison
                </h3>
                <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '4px 0 0 0' }}>
                  Select 2 to 10 completed research runs to cross-examine Sharpe, Tail Risk (VaR), Cumulative Return, and Cost Friction.
                </p>
              </div>
              <button
                onClick={handleCompareRuns}
                disabled={isComparing || selectedRunIdsForCompare.length < 2}
                className="btn btn-primary"
              >
                {isComparing ? (
                  <>
                    <div className="loading-spinner" style={{ width: '14px', height: '14px', borderWidth: '2px' }}></div>
                    <span>Comparing...</span>
                  </>
                ) : (
                  <>
                    <GitCompare size={15} />
                    <span>Compare Selected Runs ({selectedRunIdsForCompare.length})</span>
                  </>
                )}
              </button>
            </div>

            {compareError && (
              <div className="alert alert-danger" style={{ marginBottom: '14px' }}>
                <AlertTriangle size={16} />
                <span>{compareError}</span>
              </div>
            )}

            {allCompletedRuns.length === 0 ? (
              <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>
                No completed runs available across experiments yet. Execute runs in the library first.
              </p>
            ) : (
              <div>
                <div style={{ fontSize: '12px', fontWeight: 600, marginBottom: '8px' }}>Available Completed Runs:</div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '8px' }}>
                  {allCompletedRuns.map((r) => {
                    const isChecked = selectedRunIdsForCompare.includes(r.runId);
                    return (
                      <label
                        key={r.runId}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '10px',
                          padding: '8px 12px',
                          borderRadius: 'var(--radius-md)',
                          border: `1px solid ${isChecked ? 'var(--primary)' : 'var(--border-subtle)'}`,
                          backgroundColor: isChecked ? 'rgba(2, 132, 199, 0.08)' : 'var(--bg-subtle)',
                          cursor: 'pointer',
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => toggleRunForCompare(r.runId)}
                        />
                        <div style={{ overflow: 'hidden' }}>
                          <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                            {r.label}
                          </div>
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{r.strat}</div>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Comparison Results */}
          {comparisonResult && (
            <div>
              {/* Divergence Warnings */}
              {comparisonResult.warnings.length > 0 && (
                <div className="alert alert-warning" style={{ marginBottom: '16px' }}>
                  <AlertTriangle size={18} style={{ flexShrink: 0 }} />
                  <div>
                    <div style={{ fontWeight: 600, marginBottom: '4px' }}>Data Provenance & Evaluation Notices</div>
                    {comparisonResult.warnings.map((w, idx) => (
                      <div key={idx} style={{ fontSize: '12px' }}>• {w}</div>
                    ))}
                  </div>
                </div>
              )}

              {/* Comparative Metrics Table */}
              <div className="card" style={{ padding: 0, marginBottom: '20px' }}>
                <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ fontWeight: 600, fontSize: '15px' }}>Cross-Sectional Metric Comparison</div>
                  <span className="badge badge-info" style={{ fontSize: '11px' }}>
                    Currency: {comparisonResult.common_currency}
                  </span>
                </div>
                <div className="table-responsive">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Metric / Parameter</th>
                        {comparisonResult.runs.map((r) => (
                          <th key={r.run_id} style={{ minWidth: '180px' }}>
                            <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{r.experiment_name}</div>
                            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Run #{r.run_number} ({r.strategy_type})</div>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td style={{ fontWeight: 600 }}>Cumulative Return</td>
                        {comparisonResult.runs.map((r) => {
                          const val = r.metrics.cumulative_return;
                          return (
                            <td key={r.run_id} style={{ fontWeight: 600, color: (val ?? 0) >= 0 ? 'var(--success)' : 'var(--danger)' }}>
                              {val !== undefined && val !== null ? `${(val * 100).toFixed(2)}%` : '—'}
                            </td>
                          );
                        })}
                      </tr>
                      <tr>
                        <td style={{ fontWeight: 600 }}>CAGR (Net)</td>
                        {comparisonResult.runs.map((r) => {
                          const val = r.metrics.cagr;
                          return (
                            <td key={r.run_id}>
                              {val !== undefined && val !== null ? `${(val * 100).toFixed(2)}%` : '—'}
                            </td>
                          );
                        })}
                      </tr>
                      <tr>
                        <td style={{ fontWeight: 600 }}>Annualized Volatility</td>
                        {comparisonResult.runs.map((r) => {
                          const val = r.metrics.annualized_volatility;
                          return (
                            <td key={r.run_id}>
                              {val !== undefined && val !== null ? `${(val * 100).toFixed(2)}%` : '—'}
                            </td>
                          );
                        })}
                      </tr>
                      <tr>
                        <td style={{ fontWeight: 600 }}>Sharpe Ratio</td>
                        {comparisonResult.runs.map((r) => {
                          const val = r.metrics.sharpe_ratio;
                          return (
                            <td key={r.run_id} style={{ fontWeight: 600 }}>
                              {val !== undefined && val !== null ? val.toFixed(2) : '—'}
                            </td>
                          );
                        })}
                      </tr>
                      <tr>
                        <td style={{ fontWeight: 600 }}>Sortino Ratio</td>
                        {comparisonResult.runs.map((r) => {
                          const val = r.metrics.sortino_ratio;
                          return (
                            <td key={r.run_id}>
                              {val !== undefined && val !== null ? val.toFixed(2) : '—'}
                            </td>
                          );
                        })}
                      </tr>
                      <tr>
                        <td style={{ fontWeight: 600 }}>Maximum Drawdown</td>
                        {comparisonResult.runs.map((r) => {
                          const val = r.metrics.max_drawdown;
                          return (
                            <td key={r.run_id} style={{ color: 'var(--danger)' }}>
                              {val !== undefined && val !== null ? `${(val * 100).toFixed(2)}%` : '—'}
                            </td>
                          );
                        })}
                      </tr>
                      <tr>
                        <td style={{ fontWeight: 600 }}>VaR (95%) Tail Risk</td>
                        {comparisonResult.runs.map((r) => {
                          const val = r.metrics.var_95;
                          return (
                            <td key={r.run_id}>
                              {val !== undefined && val !== null ? `${(val * 100).toFixed(2)}%` : '—'}
                            </td>
                          );
                        })}
                      </tr>
                      <tr>
                        <td style={{ fontWeight: 600 }}>Tracking Error vs Benchmark</td>
                        {comparisonResult.runs.map((r) => {
                          const val = r.metrics.tracking_error;
                          return (
                            <td key={r.run_id}>
                              {val !== undefined && val !== null ? `${(val * 100).toFixed(2)}%` : '—'}
                            </td>
                          );
                        })}
                      </tr>
                      <tr>
                        <td style={{ fontWeight: 600 }}>Friction Costs Paid</td>
                        {comparisonResult.runs.map((r) => {
                          const val = r.metrics.total_friction_costs;
                          return (
                            <td key={r.run_id}>
                              {val !== undefined && val !== null ? `$${val.toFixed(2)}` : '—'}
                            </td>
                          );
                        })}
                      </tr>
                      <tr>
                        <td style={{ fontWeight: 600 }}>Rebalance Frequency</td>
                        {comparisonResult.runs.map((r) => (
                          <td key={r.run_id}>{r.config_summary.rebalance_frequency || '—'}</td>
                        ))}
                      </tr>
                      <tr>
                        <td style={{ fontWeight: 600 }}>Cost / Slippage Assumptions</td>
                        {comparisonResult.runs.map((r) => (
                          <td key={r.run_id}>
                            {r.config_summary.transaction_cost_bps ?? 0} bps / {r.config_summary.slippage_bps ?? 0} bps
                          </td>
                        ))}
                      </tr>
                      <tr>
                        <td style={{ fontWeight: 600 }}>Provenance & Reproducibility</td>
                        {comparisonResult.runs.map((r) => (
                          <td key={r.run_id}>
                            {r.is_reproducible ? (
                              <span className="badge badge-success" style={{ fontSize: '10px' }}>Reproducible</span>
                            ) : (
                              <span className="badge badge-warning" style={{ fontSize: '10px' }}>Non-Reproducible</span>
                            )}
                          </td>
                        ))}
                      </tr>
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
