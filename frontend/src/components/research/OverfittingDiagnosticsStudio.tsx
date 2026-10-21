import React, { useState, useEffect, useMemo, useId } from 'react';
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  Copy,
  Download,
  FileSpreadsheet,
  Info,
  RefreshCw,
  Sliders,
  TrendingDown,
  Award,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { SnapshotProvenanceBadge } from '../common/SnapshotProvenanceBadge';
import type {
  ExperimentListItem,
  ExperimentRunListItem,
  OverfittingDiagnosticsRequest,
  OverfittingDiagnosticsResponse,
  PBORiskLevel,
  CSCVCombinationsPoint,
  CSCVHistogramBin,
  RunOverfittingSummary,
} from '../../types/api';

/**
 * Format CSCV subsampling disclosure distinguishing plotted sample points
 * from complete combinatorial partition count (DEF-E-02).
 */
export function formatCscvSamplingDisclosure(
  sampleCount: number,
  totalCount?: number | null
): string {
  if (totalCount != null && totalCount > sampleCount) {
    return `${sampleCount.toLocaleString()} sampled points of ${totalCount.toLocaleString()} total CSCV combinations`;
  }
  if (totalCount != null && totalCount <= sampleCount) {
    return `${totalCount.toLocaleString()} total CSCV combinations (complete partition)`;
  }
  return `${sampleCount.toLocaleString()} CSCV combinations`;
}

/**
 * Escape a CSV field according to RFC 4180 standard (DEF-E-03).
 */
export function escapeCsvField(value: unknown): string {
  if (value === null || value === undefined) {
    return '';
  }
  const str = String(value);
  if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

/**
 * Format a row of CSV fields.
 */
export function toCsvRow(fields: unknown[]): string {
  return fields.map(escapeCsvField).join(',');
}

/**
 * Format histogram bin range with mathematically consistent interval notation (DEF-E-01).
 * Bins <= 0.5: [start, end) except bin ending at 0.5 which is [0.40, 0.50].
 * Bins > 0.5: (start, end].
 */
export function formatHistogramBinRange(bin: CSCVHistogramBin): string {
  if (bin.bin_end < 0.5) {
    return `[${bin.bin_start.toFixed(2)}, ${bin.bin_end.toFixed(2)})`;
  }
  if (bin.bin_end === 0.5) {
    return `[${bin.bin_start.toFixed(2)}, ${bin.bin_end.toFixed(2)}]`;
  }
  return `(${bin.bin_start.toFixed(2)}, ${bin.bin_end.toFixed(2)}]`;
}

/**
 * Generate comprehensive CSV export string with RFC 4180 escaping and advisory warnings (DEF-E-03).
 */
export function generateDiagnosticsCsv(diagnosticsResult: OverfittingDiagnosticsResponse): string {
  const lines: string[] = [];
  lines.push('--- RESEARCH EXPERIMENT OVERFITTING DIAGNOSTICS REPORT ---');
  lines.push(toCsvRow(['Experiment ID', diagnosticsResult.experiment_id]));
  lines.push(toCsvRow(['Experiment Name', diagnosticsResult.experiment_name]));
  lines.push(toCsvRow(['Strategy Type', diagnosticsResult.strategy_type]));
  lines.push(toCsvRow(['Dataset ID', diagnosticsResult.dataset_id]));
  lines.push(toCsvRow(['Snapshot ID', diagnosticsResult.snapshot_id ?? 'None']));
  lines.push(toCsvRow(['Generated At', diagnosticsResult.generated_at]));
  lines.push(toCsvRow(['Evaluated Runs Count', diagnosticsResult.evaluated_runs_count]));
  lines.push(toCsvRow(['Aligned Daily Observations', diagnosticsResult.aligned_observations_count]));
  lines.push(toCsvRow(['CSCV Slices', diagnosticsResult.n_slices]));
  lines.push(toCsvRow(['Combinatorial Splits', diagnosticsResult.total_combinations_count]));
  lines.push(toCsvRow(['PBO', diagnosticsResult.pbo]));
  lines.push(toCsvRow(['PBO Risk Level', diagnosticsResult.pbo_risk_level]));
  lines.push(toCsvRow(['Deflated Sharpe Ratio', diagnosticsResult.deflated_sharpe_ratio]));
  lines.push(toCsvRow(['Is Statistically Significant', diagnosticsResult.is_statistically_significant]));
  lines.push(toCsvRow(['Best Nominal Sharpe', diagnosticsResult.best_nominal_sharpe]));
  lines.push(toCsvRow(['Expected Max Sharpe (SR*)', diagnosticsResult.expected_max_sharpe]));
  lines.push(toCsvRow(['MinBTL (Years)', diagnosticsResult.min_backtest_length_years ?? 'Undefined']));
  lines.push(toCsvRow(['Actual Track Record (Years)', diagnosticsResult.actual_backtest_length_years]));
  lines.push(toCsvRow(['Skewness', diagnosticsResult.skewness]));
  lines.push(toCsvRow(['Kurtosis', diagnosticsResult.kurtosis]));
  lines.push(toCsvRow(['Degradation Slope Beta', diagnosticsResult.degradation_regression.slope]));
  lines.push(toCsvRow(['Degradation Intercept Alpha', diagnosticsResult.degradation_regression.intercept]));
  lines.push(toCsvRow(['Degradation R2', diagnosticsResult.degradation_regression.r_squared]));

  // Advisory Warnings Section
  lines.push('');
  lines.push('--- ADVISORY WARNINGS ---');
  if (diagnosticsResult.warnings && diagnosticsResult.warnings.length > 0) {
    lines.push(toCsvRow(['Warning Index', 'Warning Message']));
    diagnosticsResult.warnings.forEach((warn, idx) => {
      lines.push(toCsvRow([idx + 1, warn]));
    });
  } else {
    lines.push(toCsvRow(['Status', 'No advisory warnings detected.']));
  }

  // Run-level Summary
  lines.push('');
  lines.push('--- RUN-LEVEL SUMMARY TABLE ---');
  lines.push(toCsvRow([
    'Run Number',
    'Run ID',
    'Nominal Sharpe',
    'IS Selection Frequency',
    'Mean OOS Sharpe',
    'Mean OOS Relative Rank',
  ]));
  for (const r of diagnosticsResult.runs_summary) {
    lines.push(toCsvRow([
      r.run_number,
      r.run_id,
      r.nominal_sharpe.toFixed(4),
      `${(r.selection_frequency_is * 100).toFixed(2)}%`,
      r.mean_oos_sharpe_when_selected != null ? r.mean_oos_sharpe_when_selected.toFixed(4) : 'N/A',
      r.mean_oos_rank_when_selected != null ? r.mean_oos_rank_when_selected.toFixed(4) : 'N/A',
    ]));
  }

  // Combinations Sample
  lines.push('');
  lines.push('--- CSCV COMBINATIONS SAMPLE ---');
  lines.push(toCsvRow([
    'Combination ID',
    'Selected Run ID',
    'IS Sharpe',
    'OOS Sharpe',
    'OOS Rank',
    'Relative Rank',
    'Is Overfitted',
  ]));
  for (const pt of diagnosticsResult.combinations_sample) {
    lines.push(toCsvRow([
      pt.combination_id,
      pt.selected_run_id,
      pt.is_sharpe.toFixed(4),
      pt.oos_sharpe.toFixed(4),
      pt.oos_rank,
      pt.relative_rank.toFixed(4),
      pt.is_overfitted,
    ]));
  }

  return lines.join('\n');
}


interface OverfittingDiagnosticsStudioProps {
  experiments: ExperimentListItem[];
  initialExperimentId?: string | null;
  onSelectExperiment?: (experimentId: string) => void;
}

export const OverfittingDiagnosticsStudio: React.FC<OverfittingDiagnosticsStudioProps> = ({
  experiments,
  initialExperimentId,
  onSelectExperiment,
}) => {
  // Experiment selection
  const [selectedExpId, setSelectedExpId] = useState<string>(
    initialExperimentId || (experiments.length > 0 ? experiments[0].id : '')
  );

  // Available runs for selected experiment
  const [runs, setRuns] = useState<ExperimentRunListItem[]>([]);
  const [loadingRuns, setLoadingRuns] = useState<boolean>(false);
  const [runsError, setRunsError] = useState<string | null>(null);

  // Selected runs subset (defaults to all succeeded runs)
  const [selectedRunIds, setSelectedRunIds] = useState<string[]>([]);

  // Diagnostics configuration parameters
  const [nSlices, setNSlices] = useState<number>(16);
  const [significanceLevel, setSignificanceLevel] = useState<number>(0.05);
  const [annualizationFactor, setAnnualizationFactor] = useState<number>(252);

  // Execution & results state
  const [isCalculating, setIsCalculating] = useState<boolean>(false);
  const [diagnosticsResult, setDiagnosticsResult] = useState<OverfittingDiagnosticsResponse | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [isStale, setIsStale] = useState<boolean>(false);

  // UI state for visualizations & tables
  const [hoveredPoint, setHoveredPoint] = useState<CSCVCombinationsPoint | null>(null);
  const [hoveredBin, setHoveredBin] = useState<CSCVHistogramBin | null>(null);
  const [showScatterTable, setShowScatterTable] = useState<boolean>(false);
  const [showHistogramTable, setShowHistogramTable] = useState<boolean>(false);
  const [runSortColumn, setRunSortColumn] = useState<keyof RunOverfittingSummary>('nominal_sharpe');
  const [runSortAsc, setRunSortAsc] = useState<boolean>(false);
  const [copiedMemo, setCopiedMemo] = useState<boolean>(false);

  // Sync selectedExpId if prop changes
  useEffect(() => {
    if (initialExperimentId && initialExperimentId !== selectedExpId) {
      setSelectedExpId(initialExperimentId);
    }
  }, [initialExperimentId, selectedExpId]);

  // Load runs when selected experiment changes
  useEffect(() => {
    if (!selectedExpId) {
      setRuns([]);
      setSelectedRunIds([]);
      setDiagnosticsResult(null);
      return;
    }

    const loadRuns = async () => {
      setLoadingRuns(true);
      setRunsError(null);
      try {
        const fetchedRuns = await apiClient.listExperimentRuns(selectedExpId);
        setRuns(fetchedRuns);
        // Default select all succeeded runs
        const succeeded = fetchedRuns.filter((r) => r.status === 'succeeded').map((r) => r.id);
        setSelectedRunIds(succeeded);
        // Invalidate previous diagnostics when experiment changes
        setDiagnosticsResult(null);
        setIsStale(false);
      } catch (err: any) {
        setRunsError(err.message || 'Failed to load runs for selected experiment.');
        setRuns([]);
        setSelectedRunIds([]);
      } finally {
        setLoadingRuns(false);
      }
    };

    loadRuns();
    if (onSelectExperiment) {
      onSelectExperiment(selectedExpId);
    }
  }, [selectedExpId, onSelectExperiment]);

  // Mark results stale when configuration inputs change
  const handleRunSelectionChange = (runId: string) => {
    setSelectedRunIds((prev) => {
      const next = prev.includes(runId) ? prev.filter((id) => id !== runId) : [...prev, runId];
      if (diagnosticsResult) setIsStale(true);
      return next;
    });
  };

  const handleSelectAllRuns = () => {
    const succeeded = runs.filter((r) => r.status === 'succeeded').map((r) => r.id);
    setSelectedRunIds(succeeded);
    if (diagnosticsResult) setIsStale(true);
  };

  const handleClearRuns = () => {
    setSelectedRunIds([]);
    if (diagnosticsResult) setIsStale(true);
  };

  const handleSlicesChange = (val: number) => {
    setNSlices(val);
    if (diagnosticsResult) setIsStale(true);
  };

  const handleSignificanceChange = (val: number) => {
    setSignificanceLevel(val);
    if (diagnosticsResult) setIsStale(true);
  };

  const handleAnnualizationChange = (val: number) => {
    setAnnualizationFactor(val);
    if (diagnosticsResult) setIsStale(true);
  };

  // Eligible succeeded runs
  const succeededRuns = useMemo(() => {
    return runs.filter((r) => r.status === 'succeeded');
  }, [runs]);

  // CSCV combination count helper C = binom(S, S/2)
  const combinationsCountPreview = useMemo(() => {
    const k = nSlices / 2;
    let num = 1;
    let den = 1;
    for (let i = 1; i <= k; i++) {
      num *= nSlices - i + 1;
      den *= i;
    }
    return Math.round(num / den);
  }, [nSlices]);

  // Validation
  const validationError = useMemo(() => {
    if (!selectedExpId) return 'Select an experiment to evaluate.';
    if (succeededRuns.length < 2) {
      return `This experiment only has ${succeededRuns.length} completed run(s). At least 2 completed runs are required for combinatorial cross-validation.`;
    }
    if (selectedRunIds.length < 2) {
      return `Please select at least 2 runs (currently selected: ${selectedRunIds.length}).`;
    }
    if (nSlices % 2 !== 0 || nSlices < 4 || nSlices > 16) {
      return 'Number of slices must be an even integer between 4 and 16.';
    }
    return null;
  }, [selectedExpId, succeededRuns, selectedRunIds, nSlices]);

  // Execute diagnostics
  const handleExecuteDiagnostics = async () => {
    if (validationError || !selectedExpId) return;

    setIsCalculating(true);
    setApiError(null);
    try {
      const payload: OverfittingDiagnosticsRequest = {
        experiment_id: selectedExpId,
        run_ids: selectedRunIds.length === succeededRuns.length ? null : selectedRunIds,
        n_slices: nSlices,
        significance_level: significanceLevel,
        annualization_factor: annualizationFactor,
      };

      const result = await apiClient.computeOverfittingDiagnostics(selectedExpId, payload);
      setDiagnosticsResult(result);
      setIsStale(false);
    } catch (err: any) {
      setApiError(err.message || 'Error computing backtest overfitting diagnostics.');
    } finally {
      setIsCalculating(false);
    }
  };

  // Helper for PBO Risk Badge styling
  const renderRiskBadge = (level: PBORiskLevel, pboVal: number) => {
    let badgeClass = 'badge-success';
    let label = 'Low Overfitting Risk';
    if (level === 'moderate') {
      badgeClass = 'badge-warning';
      label = 'Moderate Overfitting Risk';
    } else if (level === 'high') {
      badgeClass = 'badge-warning';
      label = 'High Overfitting Risk';
    } else if (level === 'severe') {
      badgeClass = 'badge-danger';
      label = 'Severe Overfitting Risk';
    }
    return (
      <span className={`badge ${badgeClass}`} style={{ fontSize: '12px', padding: '4px 10px' }}>
        {label} ({(pboVal * 100).toFixed(1)}%)
      </span>
    );
  };

  // Sorted run summaries
  const sortedRunsSummary = useMemo(() => {
    if (!diagnosticsResult?.runs_summary) return [];
    return [...diagnosticsResult.runs_summary].sort((a, b) => {
      const aVal = a[runSortColumn] ?? -Infinity;
      const bVal = b[runSortColumn] ?? -Infinity;
      if (aVal < bVal) return runSortAsc ? -1 : 1;
      if (aVal > bVal) return runSortAsc ? 1 : -1;
      return 0;
    });
  }, [diagnosticsResult, runSortColumn, runSortAsc]);

  const handleSortRuns = (col: keyof RunOverfittingSummary) => {
    if (runSortColumn === col) {
      setRunSortAsc((prev) => !prev);
    } else {
      setRunSortColumn(col);
      setRunSortAsc(false);
    }
  };

  // Export functions
  const handleExportJson = () => {
    if (!diagnosticsResult) return;
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(diagnosticsResult, null, 2));
    const dlAnchor = document.createElement('a');
    dlAnchor.setAttribute('href', dataStr);
    dlAnchor.setAttribute('download', `overfitting_diagnostics_${diagnosticsResult.experiment_id}.json`);
    dlAnchor.click();
  };

  const handleExportCsv = () => {
    if (!diagnosticsResult) return;
    const csvContent = 'data:text/csv;charset=utf-8,' + encodeURIComponent(generateDiagnosticsCsv(diagnosticsResult));
    const dlAnchor = document.createElement('a');
    dlAnchor.setAttribute('href', csvContent);
    dlAnchor.setAttribute('download', `overfitting_diagnostics_${diagnosticsResult.experiment_id}.csv`);
    dlAnchor.click();
  };

  const handleCopyMarkdownMemo = () => {
    if (!diagnosticsResult) return;
    const memo = `### Institutional Research Tear Sheet: Overfitting Diagnostics
**Experiment:** ${diagnosticsResult.experiment_name} (\`${diagnosticsResult.experiment_id}\`)  
**Strategy Type:** \`${diagnosticsResult.strategy_type}\`  
**Dataset:** \`${diagnosticsResult.dataset_id}\` ${diagnosticsResult.snapshot_id ? `(Snapshot: \`${diagnosticsResult.snapshot_id}\`)` : ''}  
**Generated:** ${new Date(diagnosticsResult.generated_at).toUTCString()}  

#### 1. Core Overfitting & Deflation Scorecard
| Metric | Result | Institutional Interpretation |
| :--- | :--- | :--- |
| **PBO (Probability of Overfitting)** | **${(diagnosticsResult.pbo * 100).toFixed(2)}%** | Risk Tier: **${diagnosticsResult.pbo_risk_level.toUpperCase()}** |
| **Deflated Sharpe Ratio (DSR)** | **${(diagnosticsResult.deflated_sharpe_ratio * 100).toFixed(2)}%** | **${diagnosticsResult.is_statistically_significant ? 'Statistically Significant (p < alpha)' : 'False Discovery Warning'}** |
| **Best Observed Nominal SR** | **${diagnosticsResult.best_nominal_sharpe.toFixed(3)}** | Run #${diagnosticsResult.best_run_number} (\`${diagnosticsResult.best_run_id}\`) |
| **Expected Max SR Null (SR*)** | **${diagnosticsResult.expected_max_sharpe.toFixed(3)}** | Multiple-testing selection bias adjustment |
| **Minimum Backtest Length (MinBTL)** | **${diagnosticsResult.min_backtest_length_years != null ? `${diagnosticsResult.min_backtest_length_years.toFixed(2)} yrs` : 'Undefined under assumptions'}** | Actual Track Record: **${diagnosticsResult.actual_backtest_length_years.toFixed(2)} yrs** |
| **Degradation Slope (Beta)** | **${diagnosticsResult.degradation_regression.slope.toFixed(3)}** | R^2 = ${diagnosticsResult.degradation_regression.r_squared.toFixed(3)} (Intercept = ${diagnosticsResult.degradation_regression.intercept.toFixed(3)}) |
| **Return Skewness / Kurtosis** | **${diagnosticsResult.skewness.toFixed(3)} / ${diagnosticsResult.kurtosis.toFixed(3)}** | Pearson sample moments (Normal = 3.0) |

#### 2. Sample Dimensions & Cross-Validation Structure
- **Evaluated Trials (N):** ${diagnosticsResult.evaluated_runs_count}
- **Aligned Daily Bars (T):** ${diagnosticsResult.aligned_observations_count}
- **Contiguous Partitions (S):** ${diagnosticsResult.n_slices}
- **Combinatorial Splits (C):** ${diagnosticsResult.total_combinations_count.toLocaleString()}

*Notice: CSCV evaluates cross-validation stability under multi-trial selection. High DSR or low PBO does not guarantee future live performance.*
`;
    navigator.clipboard.writeText(memo);
    setCopiedMemo(true);
    setTimeout(() => setCopiedMemo(false), 2500);
  };

  return (
    <div className="overfitting-studio-container" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* ========================================================================= */}
      {/* 1. Header & Institutional Purpose Banner                                   */}
      {/* ========================================================================= */}
      <div
        className="card"
        style={{
          backgroundColor: 'var(--bg-card)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-lg)',
          padding: '20px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <TrendingDown size={20} color="var(--accent)" />
              <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                Institutional Overfitting Diagnostics & Deflated Sharpe Engine
              </h2>
              <span className="badge badge-info" style={{ fontSize: '11px' }}>
                Stage 33 / Gate E
              </span>
            </div>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', maxWidth: '900px', lineHeight: 1.5 }}>
              Rigorous quantitative validation based on Bailey, Borwein, López de Prado, and Zhu (2014 & 2017).
              Performs Combinatorially Symmetric Cross-Validation (CSCV) to compute the Probability of Backtest Overfitting (PBO),
              adjusts observed performance via the Deflated Sharpe Ratio (DSR), and assesses track-record adequacy with Minimum Backtest Length (MinBTL).
            </p>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            {diagnosticsResult && (
              <>
                <button onClick={handleCopyMarkdownMemo} className="btn btn-secondary btn-sm" title="Copy Research Memo to Clipboard">
                  <Copy size={13} />
                  <span>{copiedMemo ? 'Copied Memo!' : 'Copy Tear Sheet'}</span>
                </button>
                <button onClick={handleExportCsv} className="btn btn-secondary btn-sm" title="Download CSV Report">
                  <FileSpreadsheet size={13} />
                  <span>CSV</span>
                </button>
                <button onClick={handleExportJson} className="btn btn-secondary btn-sm" title="Download JSON Diagnostic File">
                  <Download size={13} />
                  <span>JSON</span>
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 2. Experiment & Diagnostic Configuration Workspace                         */}
      {/* ========================================================================= */}
      <div
        className="card"
        style={{
          backgroundColor: 'var(--bg-card)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-lg)',
          padding: '20px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
          <Sliders size={16} color="var(--accent)" />
          <h3 style={{ fontSize: '15px', fontWeight: 600, margin: 0 }}>Diagnostic Configuration & Run Selection</h3>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginBottom: '20px' }}>
          {/* Experiment Dropdown */}
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, color: 'var(--text-secondary)', marginBottom: '6px' }}>
              Target Research Experiment
            </label>
            <select
              value={selectedExpId}
              onChange={(e) => setSelectedExpId(e.target.value)}
              className="select-input"
              style={{
                width: '100%',
                padding: '8px 12px',
                backgroundColor: 'var(--bg-input)',
                border: '1px solid var(--border-medium)',
                borderRadius: 'var(--radius-md)',
                color: 'var(--text-primary)',
                fontSize: '13px',
              }}
            >
              {experiments.length === 0 ? (
                <option value="">No experiments found</option>
              ) : (
                experiments.map((exp) => (
                  <option key={exp.id} value={exp.id}>
                    {exp.name} ({exp.strategy_type} • {exp.total_runs_count} runs)
                  </option>
                ))
              )}
            </select>
          </div>

          {/* CSCV Slices S */}
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, color: 'var(--text-secondary)', marginBottom: '6px' }}>
              CSCV Time Partitions (Slices S): <strong>{nSlices}</strong>
            </label>
            <select
              value={nSlices}
              onChange={(e) => handleSlicesChange(Number(e.target.value))}
              style={{
                width: '100%',
                padding: '8px 12px',
                backgroundColor: 'var(--bg-input)',
                border: '1px solid var(--border-medium)',
                borderRadius: 'var(--radius-md)',
                color: 'var(--text-primary)',
                fontSize: '13px',
              }}
            >
              <option value={4}>4 slices (6 combinations)</option>
              <option value={6}>6 slices (20 combinations)</option>
              <option value={8}>8 slices (70 combinations)</option>
              <option value={10}>10 slices (252 combinations)</option>
              <option value={12}>12 slices (924 combinations)</option>
              <option value={14}>14 slices (3,432 combinations)</option>
              <option value={16}>16 slices (12,870 combinations — Recommended)</option>
            </select>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
              Splits sample into {nSlices} equal chronological slices; evaluates C = binom({nSlices}, {nSlices / 2}) = {combinationsCountPreview.toLocaleString()} IS/OOS partitions.
            </div>
          </div>

          {/* Significance Level alpha */}
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, color: 'var(--text-secondary)', marginBottom: '6px' }}>
              Significance Level (&alpha;): <strong>{significanceLevel}</strong>
            </label>
            <select
              value={significanceLevel}
              onChange={(e) => handleSignificanceChange(Number(e.target.value))}
              style={{
                width: '100%',
                padding: '8px 12px',
                backgroundColor: 'var(--bg-input)',
                border: '1px solid var(--border-medium)',
                borderRadius: 'var(--radius-md)',
                color: 'var(--text-primary)',
                fontSize: '13px',
              }}
            >
              <option value={0.01}>0.01 (99% Confidence Threshold)</option>
              <option value={0.05}>0.05 (95% Confidence Threshold — Institutional Standard)</option>
              <option value={0.10}>0.10 (90% Confidence Threshold)</option>
            </select>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
              Null hypothesis rejection requires DSR &ge; {(1 - significanceLevel).toFixed(2)}.
            </div>
          </div>

          {/* Annualization Factor */}
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, color: 'var(--text-secondary)', marginBottom: '6px' }}>
              Annualization Factor (Trading Days): <strong>{annualizationFactor}</strong>
            </label>
            <select
              value={annualizationFactor}
              onChange={(e) => handleAnnualizationChange(Number(e.target.value))}
              style={{
                width: '100%',
                padding: '8px 12px',
                backgroundColor: 'var(--bg-input)',
                border: '1px solid var(--border-medium)',
                borderRadius: 'var(--radius-md)',
                color: 'var(--text-primary)',
                fontSize: '13px',
              }}
            >
              <option value={252}>252 (Daily Returns - Standard)</option>
              <option value={52}>52 (Weekly Returns)</option>
              <option value={12}>12 (Monthly Returns)</option>
            </select>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
              Converts sample observations into annualized Sharpe ratio units.
            </div>
          </div>
        </div>

        {/* Strategy Run Multi-Selection Checklist */}
        <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                Candidate Strategy Runs ({selectedRunIds.length} of {succeededRuns.length} selected)
              </span>
              {loadingRuns && <RefreshCw size={13} className="spin" color="var(--accent)" />}
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                type="button"
                onClick={handleSelectAllRuns}
                className="btn btn-ghost btn-xs"
                style={{ fontSize: '11px' }}
                disabled={loadingRuns || succeededRuns.length === 0}
              >
                Select All ({succeededRuns.length})
              </button>
              <button
                type="button"
                onClick={handleClearRuns}
                className="btn btn-ghost btn-xs"
                style={{ fontSize: '11px' }}
                disabled={loadingRuns || selectedRunIds.length === 0}
              >
                Clear
              </button>
            </div>
          </div>

          {runsError && (
            <div className="alert alert-danger" style={{ marginBottom: '12px', fontSize: '12px' }}>
              <AlertTriangle size={14} />
              <span>{runsError}</span>
            </div>
          )}

          {succeededRuns.length === 0 && !loadingRuns ? (
            <div
              style={{
                padding: '16px',
                backgroundColor: 'var(--bg-secondary)',
                borderRadius: 'var(--radius-md)',
                fontSize: '12px',
                color: 'var(--text-muted)',
                textAlign: 'center',
              }}
            >
              No completed simulation runs found for this experiment. Please run at least 2 strategy simulations before diagnosing overfitting.
            </div>
          ) : (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
                gap: '8px',
                maxHeight: '180px',
                overflowY: 'auto',
                padding: '8px',
                backgroundColor: 'var(--bg-secondary)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              {succeededRuns.map((r) => {
                const isSelected = selectedRunIds.includes(r.id);
                const nominalSharpe = r.summary_kpis?.sharpe_ratio;
                return (
                  <label
                    key={r.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '6px 10px',
                      borderRadius: 'var(--radius-sm)',
                      backgroundColor: isSelected ? 'var(--bg-card)' : 'transparent',
                      border: isSelected ? '1px solid var(--accent)' : '1px solid transparent',
                      cursor: 'pointer',
                      fontSize: '12px',
                      color: 'var(--text-primary)',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => handleRunSelectionChange(r.id)}
                      style={{ cursor: 'pointer' }}
                    />
                    <div style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <strong>Run #{r.run_number}</strong>{' '}
                      <span className="font-mono" style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                        ({r.id.slice(0, 8)})
                      </span>
                    </div>
                    {nominalSharpe != null && (
                      <span className="font-mono" style={{ fontSize: '11px', color: 'var(--accent)' }}>
                        SR: {Number(nominalSharpe).toFixed(2)}
                      </span>
                    )}
                  </label>
                );
              })}
            </div>
          )}
        </div>

        {/* Validation Error Message */}
        {validationError && (
          <div
            style={{
              marginTop: '14px',
              padding: '10px 14px',
              backgroundColor: 'var(--warning-bg)',
              border: '1px solid rgba(245, 158, 11, 0.3)',
              borderRadius: 'var(--radius-md)',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '12px',
              color: 'var(--warning)',
            }}
          >
            <Info size={14} />
            <span>{validationError}</span>
          </div>
        )}

        {/* Stale state warning */}
        {isStale && diagnosticsResult && (
          <div
            style={{
              marginTop: '14px',
              padding: '10px 14px',
              backgroundColor: 'rgba(56, 189, 248, 0.1)',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              borderRadius: 'var(--radius-md)',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '12px',
              color: 'var(--accent)',
            }}
          >
            <RefreshCw size={14} />
            <span>Inputs modified since last execution. Results below reflect prior calculation. Click re-run to refresh.</span>
          </div>
        )}

        {/* Action Button */}
        <div style={{ marginTop: '16px', display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: '12px' }}>
          <button
            onClick={handleExecuteDiagnostics}
            disabled={isCalculating || Boolean(validationError)}
            className="btn btn-primary"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '8px 20px',
              fontSize: '13px',
              fontWeight: 600,
            }}
          >
            {isCalculating ? (
              <>
                <RefreshCw size={14} className="spin" />
                <span>Partitioning & Evaluating {combinationsCountPreview.toLocaleString()} CSCV Splits...</span>
              </>
            ) : (
              <>
                <Activity size={14} />
                <span>Compute Overfitting Diagnostics</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 3. API Error Banner (if any)                                              */}
      {/* ========================================================================= */}
      {apiError && (
        <div className="alert alert-danger" style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', padding: '14px' }}>
          <AlertTriangle size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
          <div>
            <strong style={{ display: 'block', marginBottom: '2px' }}>Diagnostic Calculation Failed</strong>
            <span style={{ fontSize: '13px' }}>{apiError}</span>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 4. Diagnostic Results Presentation                                        */}
      {/* ========================================================================= */}
      {diagnosticsResult && (
        <>
          {/* Advisory Warnings Banner */}
          {diagnosticsResult.warnings && diagnosticsResult.warnings.length > 0 && (
            <div
              style={{
                padding: '12px 16px',
                backgroundColor: 'var(--warning-bg)',
                border: '1px solid rgba(245, 158, 11, 0.3)',
                borderRadius: 'var(--radius-md)',
                display: 'flex',
                flexDirection: 'column',
                gap: '4px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--warning)', fontWeight: 600, fontSize: '13px' }}>
                <AlertTriangle size={14} />
                <span>Data Alignment & Statistical Advisory Warnings ({diagnosticsResult.warnings.length})</span>
              </div>
              <ul style={{ margin: '4px 0 0 20px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                {diagnosticsResult.warnings.map((w, idx) => (
                  <li key={idx}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          {/* KPI Summary Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))', gap: '14px' }}>
            {/* KPI 1: PBO */}
            <div
              className="card"
              style={{
                backgroundColor: 'var(--bg-card)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-md)',
                padding: '16px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
              }}
            >
              <div>
                <div style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600, letterSpacing: '0.05em' }}>
                  Probability of Backtest Overfitting (PBO)
                </div>
                <div className="font-mono" style={{ fontSize: '28px', fontWeight: 700, color: 'var(--text-primary)', margin: '6px 0' }}>
                  {(diagnosticsResult.pbo * 100).toFixed(1)}%
                </div>
              </div>
              <div>
                <div style={{ marginBottom: '8px' }}>
                  {renderRiskBadge(diagnosticsResult.pbo_risk_level, diagnosticsResult.pbo)}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                  Empirical fraction of CSCV splits where the in-sample optimal strategy underperformed the out-of-sample median.
                </div>
              </div>
            </div>

            {/* KPI 2: DSR */}
            <div
              className="card"
              style={{
                backgroundColor: 'var(--bg-card)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-md)',
                padding: '16px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
              }}
            >
              <div>
                <div style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600, letterSpacing: '0.05em' }}>
                  Deflated Sharpe Ratio (DSR)
                </div>
                <div className="font-mono" style={{ fontSize: '28px', fontWeight: 700, color: 'var(--accent)', margin: '6px 0' }}>
                  {(diagnosticsResult.deflated_sharpe_ratio * 100).toFixed(1)}%
                </div>
              </div>
              <div>
                <div style={{ marginBottom: '8px' }}>
                  {diagnosticsResult.is_statistically_significant ? (
                    <span className="badge badge-success" style={{ fontSize: '11px', padding: '3px 8px' }}>
                      <CheckCircle size={10} style={{ display: 'inline', marginRight: '3px' }} />
                      Significant (p &lt; {significanceLevel})
                    </span>
                  ) : (
                    <span className="badge badge-danger" style={{ fontSize: '11px', padding: '3px 8px' }}>
                      <AlertTriangle size={10} style={{ display: 'inline', marginRight: '3px' }} />
                      False Discovery Risk (p &ge; {significanceLevel})
                    </span>
                  )}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                  Best SR = <strong>{diagnosticsResult.best_nominal_sharpe.toFixed(2)}</strong> vs Expected Max SR* ={' '}
                  <strong>{diagnosticsResult.expected_max_sharpe.toFixed(2)}</strong> under null hypothesis.
                </div>
              </div>
            </div>

            {/* KPI 3: MinBTL */}
            <div
              className="card"
              style={{
                backgroundColor: 'var(--bg-card)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-md)',
                padding: '16px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
              }}
            >
              <div>
                <div style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600, letterSpacing: '0.05em' }}>
                  Minimum Backtest Length (MinBTL)
                </div>
                <div className="font-mono" style={{ fontSize: '24px', fontWeight: 700, color: 'var(--text-primary)', margin: '6px 0' }}>
                  {diagnosticsResult.min_backtest_length_years != null ? (
                    `${diagnosticsResult.min_backtest_length_years.toFixed(2)} Years`
                  ) : (
                    <span style={{ fontSize: '16px', color: 'var(--text-muted)' }}>Undefined</span>
                  )}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                  Observed Sample: <strong className="font-mono">{diagnosticsResult.actual_backtest_length_years.toFixed(2)} Years</strong>
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                  {diagnosticsResult.min_backtest_length_years != null ? (
                    diagnosticsResult.actual_backtest_length_years >= diagnosticsResult.min_backtest_length_years ? (
                      <span style={{ color: 'var(--success)' }}>Track record length exceeds statistical discovery threshold.</span>
                    ) : (
                      <span style={{ color: 'var(--warning)' }}>Sample length below required track record threshold.</span>
                    )
                  ) : (
                    <span>Undefined under current statistical assumptions (observed SR &le; benchmark).</span>
                  )}
                </div>
              </div>
            </div>

            {/* KPI 4: Degradation Regression */}
            <div
              className="card"
              style={{
                backgroundColor: 'var(--bg-card)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-md)',
                padding: '16px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
              }}
            >
              <div>
                <div style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600, letterSpacing: '0.05em' }}>
                  Degradation Slope (&beta;)
                </div>
                <div className="font-mono" style={{ fontSize: '28px', fontWeight: 700, color: 'var(--text-primary)', margin: '6px 0' }}>
                  {diagnosticsResult.degradation_regression.slope.toFixed(2)}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                  R&sup2;: <strong className="font-mono">{diagnosticsResult.degradation_regression.r_squared.toFixed(2)}</strong> • Intercept:{' '}
                  <strong className="font-mono">{diagnosticsResult.degradation_regression.intercept.toFixed(2)}</strong>
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                  {diagnosticsResult.degradation_regression.slope > 0.5 ? (
                    <span style={{ color: 'var(--success)' }}>Moderate to strong persistence between IS and OOS.</span>
                  ) : diagnosticsResult.degradation_regression.slope > 0 ? (
                    <span style={{ color: 'var(--warning)' }}>Weak persistence with notable degradation.</span>
                  ) : (
                    <span style={{ color: 'var(--danger)' }}>Severe degradation (&beta; &le; 0); IS alpha does not carry forward.</span>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Snapshot Lineage Bar */}
          {diagnosticsResult.snapshot_id && (
            <div style={{ margin: '4px 0' }}>
              <SnapshotProvenanceBadge snapshotId={diagnosticsResult.snapshot_id} compact={true} />
            </div>
          )}

          {/* ========================================================================= */}
          {/* 5. Interactive Visualizations Grid                                         */}
          {/* ========================================================================= */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(480px, 1fr))', gap: '20px' }}>
            {/* Chart 1: CSCV IS vs OOS Sharpe Scatter Plot */}
            <div
              className="card"
              style={{
                backgroundColor: 'var(--bg-card)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-lg)',
                padding: '20px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <div>
                  <h4 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                    In-Sample vs Out-of-Sample Sharpe Degradation
                  </h4>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                    {formatCscvSamplingDisclosure(diagnosticsResult.combinations_sample.length, diagnosticsResult.total_combinations_count)} • Red = Overfitted (&le; Median) • Green = Persistent
                  </div>
                </div>
                <button
                  onClick={() => setShowScatterTable((prev) => !prev)}
                  className="btn btn-ghost btn-xs"
                  style={{ fontSize: '11px' }}
                >
                  {showScatterTable ? 'Show Chart' : 'Show Data Table'}
                </button>
              </div>

              {!showScatterTable ? (
                <div>
                  <CSCVScatterChart
                    points={diagnosticsResult.combinations_sample}
                    regression={diagnosticsResult.degradation_regression}
                    hoveredPoint={hoveredPoint}
                    onHoverPoint={setHoveredPoint}
                  />

                  {/* Active Point Details Tooltip Bar */}
                  <div
                    style={{
                      marginTop: '10px',
                      padding: '8px 12px',
                      backgroundColor: 'var(--bg-secondary)',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '12px',
                      minHeight: '38px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      flexWrap: 'wrap',
                      gap: '8px',
                    }}
                  >
                    {hoveredPoint ? (
                      <>
                        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                          <span>
                            Split <strong>#{hoveredPoint.combination_id}</strong>
                          </span>
                          <span>
                            Selected Run: <strong>{hoveredPoint.selected_run_id.slice(0, 8)}</strong>
                          </span>
                          <span>
                            IS SR: <strong className="font-mono">{hoveredPoint.is_sharpe.toFixed(2)}</strong>
                          </span>
                          <span>
                            OOS SR: <strong className="font-mono">{hoveredPoint.oos_sharpe.toFixed(2)}</strong>
                          </span>
                          <span>
                            Relative Rank: <strong className="font-mono">{(hoveredPoint.relative_rank * 100).toFixed(0)}%</strong>
                          </span>
                        </div>
                        <span
                          className={`badge ${hoveredPoint.is_overfitted ? 'badge-danger' : 'badge-success'}`}
                          style={{ fontSize: '10px' }}
                        >
                          {hoveredPoint.is_overfitted ? 'Overfitted (Rank <= Median)' : 'Persistent (Rank > Median)'}
                        </span>
                      </>
                    ) : (
                      <span style={{ color: 'var(--text-dim)', fontSize: '11px' }}>
                        Hover over any combination split point to inspect In-Sample and Out-of-Sample metrics.
                      </span>
                    )}
                  </div>
                </div>
              ) : (
                /* Tabular summary for accessibility */
                <div className="table-container" style={{ maxHeight: '300px', overflowY: 'auto' }}>
                  <table className="table" style={{ fontSize: '11px' }}>
                    <thead>
                      <tr>
                        <th>Split #</th>
                        <th>Selected Run</th>
                        <th>IS Sharpe</th>
                        <th>OOS Sharpe</th>
                        <th>OOS Rank</th>
                        <th>Rel Rank</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {diagnosticsResult.combinations_sample.map((pt) => (
                        <tr key={pt.combination_id}>
                          <td className="font-mono">{pt.combination_id}</td>
                          <td className="font-mono">{pt.selected_run_id.slice(0, 8)}</td>
                          <td className="font-mono">{pt.is_sharpe.toFixed(3)}</td>
                          <td className="font-mono">{pt.oos_sharpe.toFixed(3)}</td>
                          <td className="font-mono">{pt.oos_rank}</td>
                          <td className="font-mono">{(pt.relative_rank * 100).toFixed(1)}%</td>
                          <td>
                            <span className={`badge ${pt.is_overfitted ? 'badge-danger' : 'badge-success'}`} style={{ fontSize: '10px' }}>
                              {pt.is_overfitted ? 'Overfitted' : 'Persistent'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Chart 2: Relative-Rank Distribution Histogram */}
            <div
              className="card"
              style={{
                backgroundColor: 'var(--bg-card)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-lg)',
                padding: '20px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <div>
                  <h4 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                    Out-of-Sample Relative-Rank Distribution
                  </h4>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                    PBO Threshold at 0.5 (Median) • Bins &le; 0.5 sum to PBO = {(diagnosticsResult.pbo * 100).toFixed(1)}%
                  </div>
                </div>
                <button
                  onClick={() => setShowHistogramTable((prev) => !prev)}
                  className="btn btn-ghost btn-xs"
                  style={{ fontSize: '11px' }}
                >
                  {showHistogramTable ? 'Show Chart' : 'Show Data Table'}
                </button>
              </div>

              {!showHistogramTable ? (
                <div>
                  <CSCVHistogramChart
                    bins={diagnosticsResult.rank_distribution}
                    pbo={diagnosticsResult.pbo}
                    hoveredBin={hoveredBin}
                    onHoverBin={setHoveredBin}
                  />

                  {/* Active Bin Tooltip Bar */}
                  <div
                    style={{
                      marginTop: '10px',
                      padding: '8px 12px',
                      backgroundColor: 'var(--bg-secondary)',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '12px',
                      minHeight: '38px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    {hoveredBin ? (
                      <>
                        <div>
                          Rank Range: <strong>{formatHistogramBinRange(hoveredBin)}</strong> •{' '}
                          Count: <strong>{hoveredBin.count.toLocaleString()}</strong> splits (
                          {(hoveredBin.relative_frequency * 100).toFixed(1)}%)
                        </div>
                        <span
                          className={`badge ${hoveredBin.bin_end <= 0.5 ? 'badge-danger' : 'badge-success'}`}
                          style={{ fontSize: '10px' }}
                        >
                          {hoveredBin.bin_end <= 0.5 ? 'Underperforming (<= Median)' : 'Outperforming (> Median)'}
                        </span>
                      </>
                    ) : (
                      <span style={{ color: 'var(--text-dim)', fontSize: '11px' }}>
                        Relative rank 0.0 = worst OOS performance; 1.0 = best OOS performance. PBO is cumulative density &le; 0.5.
                      </span>
                    )}
                  </div>
                </div>
              ) : (
                /* Tabular summary for accessibility */
                <div className="table-container" style={{ maxHeight: '300px', overflowY: 'auto' }}>
                  <table className="table" style={{ fontSize: '11px' }}>
                    <thead>
                      <tr>
                        <th>Bin Range</th>
                        <th>Splits Count</th>
                        <th>Relative Frequency</th>
                        <th>Region</th>
                      </tr>
                    </thead>
                    <tbody>
                      {diagnosticsResult.rank_distribution.map((bin, idx) => (
                        <tr key={idx}>
                          <td className="font-mono">
                            {formatHistogramBinRange(bin)}
                          </td>
                          <td className="font-mono">{bin.count.toLocaleString()}</td>
                          <td className="font-mono">{(bin.relative_frequency * 100).toFixed(2)}%</td>
                          <td>
                            <span className={`badge ${bin.bin_end <= 0.5 ? 'badge-danger' : 'badge-success'}`} style={{ fontSize: '10px' }}>
                              {bin.bin_end <= 0.5 ? 'Overfitted Region' : 'Persistent Region'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>

          {/* ========================================================================= */}
          {/* 6. Run-Level Multi-Trial Summary Table                                     */}
          {/* ========================================================================= */}
          <div
            className="card"
            style={{
              backgroundColor: 'var(--bg-card)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-lg)',
              padding: '20px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <div>
                <h4 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                  Candidate Strategy Trials Performance & Selection Stability
                </h4>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                  Analysis across {diagnosticsResult.evaluated_runs_count} evaluated strategy trials in this experiment.
                </div>
              </div>
            </div>

            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th onClick={() => handleSortRuns('run_number')} style={{ cursor: 'pointer' }}>
                      Run # {runSortColumn === 'run_number' && (runSortAsc ? '▲' : '▼')}
                    </th>
                    <th>Strategy Run ID</th>
                    <th onClick={() => handleSortRuns('nominal_sharpe')} style={{ cursor: 'pointer' }}>
                      Nominal Sharpe {runSortColumn === 'nominal_sharpe' && (runSortAsc ? '▲' : '▼')}
                    </th>
                    <th onClick={() => handleSortRuns('selection_frequency_is')} style={{ cursor: 'pointer' }}>
                      IS Selection Freq {runSortColumn === 'selection_frequency_is' && (runSortAsc ? '▲' : '▼')}
                    </th>
                    <th onClick={() => handleSortRuns('mean_oos_sharpe_when_selected')} style={{ cursor: 'pointer' }}>
                      Mean OOS Sharpe (When Selected) {runSortColumn === 'mean_oos_sharpe_when_selected' && (runSortAsc ? '▲' : '▼')}
                    </th>
                    <th onClick={() => handleSortRuns('mean_oos_rank_when_selected')} style={{ cursor: 'pointer' }}>
                      Mean OOS Rank (When Selected) {runSortColumn === 'mean_oos_rank_when_selected' && (runSortAsc ? '▲' : '▼')}
                    </th>
                    <th>Status / Distinction</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedRunsSummary.map((r) => {
                    const isBestOverall = r.run_id === diagnosticsResult.best_run_id;
                    return (
                      <tr key={r.run_id} style={{ backgroundColor: isBestOverall ? 'rgba(56, 189, 248, 0.05)' : undefined }}>
                        <td className="font-mono">
                          <strong>Run #{r.run_number}</strong>
                        </td>
                        <td className="font-mono" style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                          {r.run_id}
                        </td>
                        <td className="font-mono">
                          <strong style={{ color: isBestOverall ? 'var(--accent)' : 'inherit' }}>
                            {r.nominal_sharpe.toFixed(3)}
                          </strong>
                        </td>
                        <td className="font-mono">
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span>{(r.selection_frequency_is * 100).toFixed(1)}%</span>
                            <div
                              style={{
                                width: '60px',
                                height: '6px',
                                backgroundColor: 'var(--bg-secondary)',
                                borderRadius: '3px',
                                overflow: 'hidden',
                              }}
                            >
                              <div
                                style={{
                                  width: `${Math.min(100, r.selection_frequency_is * 100)}%`,
                                  height: '100%',
                                  backgroundColor: 'var(--accent)',
                                }}
                              />
                            </div>
                          </div>
                        </td>
                        <td className="font-mono">
                          {r.mean_oos_sharpe_when_selected != null ? (
                            <span style={{ color: r.mean_oos_sharpe_when_selected >= 0 ? 'var(--success)' : 'var(--danger)' }}>
                              {r.mean_oos_sharpe_when_selected.toFixed(3)}
                            </span>
                          ) : (
                            <span style={{ color: 'var(--text-dim)' }}>—</span>
                          )}
                        </td>
                        <td className="font-mono">
                          {r.mean_oos_rank_when_selected != null ? (
                            <span>{r.mean_oos_rank_when_selected.toFixed(2)}</span>
                          ) : (
                            <span style={{ color: 'var(--text-dim)' }}>—</span>
                          )}
                        </td>
                        <td>
                          {isBestOverall ? (
                            <span className="badge badge-info" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '10px' }}>
                              <Award size={11} />
                              <span>Highest Nominal SR</span>
                            </span>
                          ) : (
                            <span className="badge badge-neutral" style={{ fontSize: '10px' }}>
                              Trial #{r.run_number}
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

          {/* ========================================================================= */}
          {/* 7. Institutional Disclosures & Limitations Notice                          */}
          {/* ========================================================================= */}
          <div
            style={{
              padding: '16px',
              backgroundColor: 'var(--bg-secondary)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-md)',
              fontSize: '12px',
              color: 'var(--text-muted)',
              lineHeight: 1.6,
            }}
          >
            <div style={{ fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>
              Institutional Methodology Notes & Analytical Disclosures
            </div>
            <ul style={{ margin: '4px 0 0 16px' }}>
              <li>
                <strong>CSCV vs Walk-Forward:</strong> Combinatorially Symmetric Cross-Validation constructs all &omega; = S/2 slice combinations, preserving sample length while generating empirical out-of-sample distributions without assuming stationarity. It does not substitute for chronological forward execution.
              </li>
              <li>
                <strong>Multiple Testing Scope:</strong> DSR adjusts the observed Sharpe ratio based on the candidate trials provided. If additional unrecorded strategy trials were conducted outside this experiment, the true multiple-testing hazard may be larger.
              </li>
              <li>
                <strong>Statistical Limitations:</strong> Neither PBO nor DSR proves live profitability or protects against structural market regime breaks, liquidity shifts, or model specification error.
              </li>
            </ul>
          </div>
        </>
      )}
    </div>
  );
};

/* ========================================================================= */
/* SVG SCATTER PLOT COMPONENT                                                */
/* ========================================================================= */
interface CSCVScatterChartProps {
  points: CSCVCombinationsPoint[];
  regression: { slope: number; intercept: number };
  hoveredPoint: CSCVCombinationsPoint | null;
  onHoverPoint: (pt: CSCVCombinationsPoint | null) => void;
}

const CSCVScatterChart: React.FC<CSCVScatterChartProps> = ({
  points,
  regression,
  hoveredPoint,
  onHoverPoint,
}) => {
  const clipId = useId();
  const width = 600;
  const height = 300;
  const padding = { top: 20, right: 30, bottom: 40, left: 50 };

  const { xMin, xMax, yMin, yMax } = useMemo(() => {
    if (points.length === 0) return { xMin: -1, xMax: 3, yMin: -1, yMax: 3 };
    let minX = Infinity;
    let maxX = -Infinity;
    let minY = Infinity;
    let maxY = -Infinity;

    for (const p of points) {
      if (p.is_sharpe < minX) minX = p.is_sharpe;
      if (p.is_sharpe > maxX) maxX = p.is_sharpe;
      if (p.oos_sharpe < minY) minY = p.oos_sharpe;
      if (p.oos_sharpe > maxY) maxY = p.oos_sharpe;
    }

    // Add 10% padding
    const xSpan = Math.max(0.5, maxX - minX);
    const ySpan = Math.max(0.5, maxY - minY);
    return {
      xMin: minX - 0.1 * xSpan,
      xMax: maxX + 0.1 * xSpan,
      yMin: minY - 0.1 * ySpan,
      yMax: maxY + 0.1 * ySpan,
    };
  }, [points]);

  const scaleX = (val: number) => {
    const range = xMax - xMin || 1;
    return padding.left + ((val - xMin) / range) * (width - padding.left - padding.right);
  };

  const scaleY = (val: number) => {
    const range = yMax - yMin || 1;
    return height - padding.bottom - ((val - yMin) / range) * (height - padding.top - padding.bottom);
  };

  // Parity line points (y = x)
  const parityStartVal = Math.max(xMin, yMin);
  const parityEndVal = Math.min(xMax, yMax);

  // Degradation fit line points (y = slope * x + intercept)
  const regYStart = regression.slope * xMin + regression.intercept;
  const regYEnd = regression.slope * xMax + regression.intercept;

  return (
    <svg
      data-testid="cscv-scatter-chart"
      viewBox={`0 0 ${width} ${height}`}
      style={{ width: '100%', height: 'auto', display: 'block', overflow: 'visible' }}
    >
      <defs>
        <clipPath id={clipId}>
          <rect
            x={padding.left}
            y={padding.top}
            width={width - padding.left - padding.right}
            height={height - padding.top - padding.bottom}
          />
        </clipPath>
      </defs>

      {/* Background & Grid */}
      <rect
        x={padding.left}
        y={padding.top}
        width={width - padding.left - padding.right}
        height={height - padding.top - padding.bottom}
        fill="var(--bg-secondary)"
        stroke="var(--border-subtle)"
      />

      {/* Clipped Plot Area: lines and points constrained to plot area (DEF-E-04) */}
      <g clipPath={`url(#${clipId})`}>
        {/* Zero lines if in range */}
        {xMin < 0 && xMax > 0 && (
          <line
            x1={scaleX(0)}
            y1={padding.top}
            x2={scaleX(0)}
            y2={height - padding.bottom}
            stroke="var(--border-medium)"
            strokeWidth="1"
            strokeDasharray="3 3"
          />
        )}
        {yMin < 0 && yMax > 0 && (
          <line
            x1={padding.left}
            y1={scaleY(0)}
            x2={width - padding.right}
            y2={scaleY(0)}
            stroke="var(--border-medium)"
            strokeWidth="1"
            strokeDasharray="3 3"
          />
        )}

        {/* 1:1 Parity Line (Zero Degradation) */}
        {parityStartVal < parityEndVal && (
          <line
            x1={scaleX(parityStartVal)}
            y1={scaleY(parityStartVal)}
            x2={scaleX(parityEndVal)}
            y2={scaleY(parityEndVal)}
            stroke="var(--text-dim)"
            strokeWidth="1.5"
            strokeDasharray="4 4"
          />
        )}

        {/* OLS Degradation Line */}
        <line
          x1={scaleX(xMin)}
          y1={scaleY(regYStart)}
          x2={scaleX(xMax)}
          y2={scaleY(regYEnd)}
          stroke="var(--accent)"
          strokeWidth="2"
        />

        {/* Scatter Points */}
        {points.map((pt) => {
          const cx = scaleX(pt.is_sharpe);
          const cy = scaleY(pt.oos_sharpe);
          const isHovered = hoveredPoint?.combination_id === pt.combination_id;
          const color = pt.is_overfitted ? 'var(--danger)' : 'var(--success)';

          return (
            <circle
              key={pt.combination_id}
              cx={cx}
              cy={cy}
              r={isHovered ? 6 : 3.5}
              fill={color}
              opacity={isHovered ? 1.0 : 0.75}
              stroke={isHovered ? '#fff' : 'none'}
              strokeWidth={isHovered ? 1.5 : 0}
              style={{ cursor: 'pointer', transition: 'r 0.1s ease' }}
              onMouseEnter={() => onHoverPoint(pt)}
              onMouseLeave={() => onHoverPoint(null)}
            />
          );
        })}
      </g>

      {/* Axes & Ticks */}
      <line
        x1={padding.left}
        y1={height - padding.bottom}
        x2={width - padding.right}
        y2={height - padding.bottom}
        stroke="var(--border-medium)"
      />
      <line
        x1={padding.left}
        y1={padding.top}
        x2={padding.left}
        y2={height - padding.bottom}
        stroke="var(--border-medium)"
      />

      {/* Axis Labels */}
      <text
        x={(width + padding.left - padding.right) / 2}
        y={height - 8}
        textAnchor="middle"
        fontSize="11"
        fill="var(--text-muted)"
      >
        In-Sample Sharpe Ratio (IS SR)
      </text>
      <text
        x={16}
        y={(height + padding.top - padding.bottom) / 2}
        textAnchor="middle"
        fontSize="11"
        fill="var(--text-muted)"
        transform={`rotate(-90, 16, ${(height + padding.top - padding.bottom) / 2})`}
      >
        Out-of-Sample Sharpe (OOS SR)
      </text>

      {/* Min/Max numeric tick labels */}
      <text x={padding.left} y={height - padding.bottom + 14} fontSize="10" fill="var(--text-dim)" textAnchor="middle">
        {xMin.toFixed(1)}
      </text>
      <text x={width - padding.right} y={height - padding.bottom + 14} fontSize="10" fill="var(--text-dim)" textAnchor="middle">
        {xMax.toFixed(1)}
      </text>
      <text x={padding.left - 6} y={scaleY(yMin) + 4} fontSize="10" fill="var(--text-dim)" textAnchor="end">
        {yMin.toFixed(1)}
      </text>
      <text x={padding.left - 6} y={scaleY(yMax) + 4} fontSize="10" fill="var(--text-dim)" textAnchor="end">
        {yMax.toFixed(1)}
      </text>
    </svg>
  );
};

/* ========================================================================= */
/* SVG HISTOGRAM COMPONENT                                                   */
/* ========================================================================= */
interface CSCVHistogramChartProps {
  bins: CSCVHistogramBin[];
  pbo: number;
  hoveredBin: CSCVHistogramBin | null;
  onHoverBin: (bin: CSCVHistogramBin | null) => void;
}

const CSCVHistogramChart: React.FC<CSCVHistogramChartProps> = ({
  bins,
  pbo,
  hoveredBin,
  onHoverBin,
}) => {
  const width = 600;
  const height = 300;
  const padding = { top: 25, right: 30, bottom: 40, left: 50 };

  const maxFreq = useMemo(() => {
    let max = 0.05;
    for (const b of bins) {
      if (b.relative_frequency > max) max = b.relative_frequency;
    }
    return max * 1.15; // 15% headroom
  }, [bins]);

  const scaleX = (val: number) => {
    return padding.left + val * (width - padding.left - padding.right);
  };

  const scaleY = (freq: number) => {
    return height - padding.bottom - (freq / maxFreq) * (height - padding.top - padding.bottom);
  };

  const pboCutoffX = scaleX(0.5);

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      style={{ width: '100%', height: 'auto', display: 'block', overflow: 'visible' }}
    >
      {/* Background */}
      <rect
        x={padding.left}
        y={padding.top}
        width={width - padding.left - padding.right}
        height={height - padding.top - padding.bottom}
        fill="var(--bg-secondary)"
        stroke="var(--border-subtle)"
      />

      {/* Shaded PBO Region (< 0.5) */}
      <rect
        x={padding.left}
        y={padding.top}
        width={pboCutoffX - padding.left}
        height={height - padding.top - padding.bottom}
        fill="rgba(239, 68, 68, 0.04)"
      />

      {/* Bars */}
      {bins.map((b, idx) => {
        const x1 = scaleX(b.bin_start);
        const x2 = scaleX(b.bin_end);
        const barWidth = Math.max(1, x2 - x1 - 2);
        const yTop = scaleY(b.relative_frequency);
        const barHeight = Math.max(0, height - padding.bottom - yTop);
        const isOverfittedRegion = b.bin_end <= 0.5;
        const isHovered = hoveredBin === b;

        const fillColor = isOverfittedRegion ? 'var(--danger)' : 'var(--success)';

        return (
          <g key={idx}>
            <rect
              x={x1 + 1}
              y={yTop}
              width={barWidth}
              height={barHeight}
              fill={fillColor}
              opacity={isHovered ? 1.0 : isOverfittedRegion ? 0.8 : 0.7}
              stroke={isHovered ? '#fff' : 'none'}
              strokeWidth={isHovered ? 1.5 : 0}
              style={{ cursor: 'pointer', transition: 'opacity 0.15s ease' }}
              onMouseEnter={() => onHoverBin(b)}
              onMouseLeave={() => onHoverBin(null)}
            />
            {/* Percentage text above bar if space permits */}
            {b.relative_frequency > 0.03 && (
              <text
                x={x1 + barWidth / 2}
                y={yTop - 4}
                textAnchor="middle"
                fontSize="9"
                fill="var(--text-secondary)"
                className="font-mono"
              >
                {(b.relative_frequency * 100).toFixed(0)}%
              </text>
            )}
          </g>
        );
      })}

      {/* PBO Cutoff Line at Relative Rank = 0.5 */}
      <line
        x1={pboCutoffX}
        y1={padding.top - 5}
        x2={pboCutoffX}
        y2={height - padding.bottom}
        stroke="#fff"
        strokeWidth="2"
        strokeDasharray="4 3"
      />
      <text
        x={pboCutoffX}
        y={padding.top - 10}
        textAnchor="middle"
        fontSize="11"
        fontWeight="600"
        fill="var(--danger)"
      >
        PBO Cutoff (Median &le; 0.5 • PBO: {(pbo * 100).toFixed(1)}%)
      </text>

      {/* Axes */}
      <line
        x1={padding.left}
        y1={height - padding.bottom}
        x2={width - padding.right}
        y2={height - padding.bottom}
        stroke="var(--border-medium)"
      />
      <line
        x1={padding.left}
        y1={padding.top}
        x2={padding.left}
        y2={height - padding.bottom}
        stroke="var(--border-medium)"
      />

      {/* Axis Labels */}
      <text
        x={(width + padding.left - padding.right) / 2}
        y={height - 8}
        textAnchor="middle"
        fontSize="11"
        fill="var(--text-muted)"
      >
        Out-of-Sample Relative Rank (&omega;&#772; = rank / [N + 1])
      </text>
      <text
        x={16}
        y={(height + padding.top - padding.bottom) / 2}
        textAnchor="middle"
        fontSize="11"
        fill="var(--text-muted)"
        transform={`rotate(-90, 16, ${(height + padding.top - padding.bottom) / 2})`}
      >
        Relative Frequency
      </text>

      {/* Numeric Ticks */}
      <text x={scaleX(0.0)} y={height - padding.bottom + 14} fontSize="10" fill="var(--text-dim)" textAnchor="middle">
        0.0 (Worst)
      </text>
      <text x={scaleX(0.5)} y={height - padding.bottom + 14} fontSize="10" fill="var(--text-primary)" textAnchor="middle" fontWeight="600">
        0.5 (Median)
      </text>
      <text x={scaleX(1.0)} y={height - padding.bottom + 14} fontSize="10" fill="var(--text-dim)" textAnchor="middle">
        1.0 (Best)
      </text>
      <text x={padding.left - 6} y={scaleY(maxFreq) + 4} fontSize="10" fill="var(--text-dim)" textAnchor="end">
        {(maxFreq * 100).toFixed(0)}%
      </text>
    </svg>
  );
};
