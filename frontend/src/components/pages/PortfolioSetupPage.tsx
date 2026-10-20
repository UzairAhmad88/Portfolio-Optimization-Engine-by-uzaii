import React, { useState } from 'react';
import {
  SlidersHorizontal,
  CheckCircle,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Info,
  Calendar,
  Layers,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { useDataset } from '../../context/DatasetContext';
import type {
  PortfolioDefinition,
  PortfolioValidationReport,
} from '../../types/api';

interface PortfolioSetupPageProps {
  onValidatedPortfolio?: (portfolio: PortfolioDefinition) => void;
}

export const PortfolioSetupPage: React.FC<PortfolioSetupPageProps> = ({ onValidatedPortfolio }) => {
  const { currentDataset, availableAssets } = useDataset();

  const [portfolioName, setPortfolioName] = useState<string>('Institutional Core Portfolio');
  const [selectedAssetTickers, setSelectedAssetTickers] = useState<string[]>([]);
  const [defaultMinWeight, setDefaultMinWeight] = useState<number>(0.0);
  const [defaultMaxWeight, setDefaultMaxWeight] = useState<number>(1.0);
  const [targetTotalWeight, setTargetTotalWeight] = useState<number>(1.0);
  const [allowShort, setAllowShort] = useState<boolean>(false);
  const [maxGrossExposure, setMaxGrossExposure] = useState<string>('');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');

  const [isValidating, setIsValidating] = useState<boolean>(false);
  const [validationReport, setValidationReport] = useState<PortfolioValidationReport | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Auto-select all available assets initially if none selected
  React.useEffect(() => {
    if (availableAssets.length > 0 && selectedAssetTickers.length === 0) {
      setSelectedAssetTickers(availableAssets.map((a) => a.ticker));
    }
  }, [availableAssets]);

  const handleToggleAsset = (ticker: string) => {
    setSelectedAssetTickers((prev) =>
      prev.includes(ticker) ? prev.filter((t) => t !== ticker) : [...prev, ticker]
    );
  };

  const handleSelectAll = () => {
    setSelectedAssetTickers(availableAssets.map((a) => a.ticker));
  };

  const handleDeselectAll = () => {
    setSelectedAssetTickers([]);
  };

  const handleValidate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentDataset) {
      setValidationError('No active dataset selected. Please upload or register a dataset first.');
      return;
    }

    if (selectedAssetTickers.length === 0) {
      setValidationError('Please select at least one asset for the portfolio.');
      return;
    }

    setIsValidating(true);
    setValidationError(null);

    const definition: PortfolioDefinition = {
      name: portfolioName.trim() || 'Custom Portfolio',
      dataset_id: currentDataset.dataset_id,
      assets: selectedAssetTickers,
      constraints: {
        default_min_weight: Number(defaultMinWeight),
        default_max_weight: Number(defaultMaxWeight),
        target_total_weight: Number(targetTotalWeight),
        allow_short: allowShort,
        max_gross_exposure: maxGrossExposure ? Number(maxGrossExposure) : null,
      },
      start_date: startDate.trim() || null,
      end_date: endDate.trim() || null,
    };

    try {
      const report = await apiClient.validatePortfolio(definition);
      setValidationReport(report);
      if (report.is_valid && onValidatedPortfolio) {
        onValidatedPortfolio(definition);
      }
    } catch (err: any) {
      setValidationError(err.message || 'Validation request failed.');
      setValidationReport(null);
    } finally {
      setIsValidating(false);
    }
  };

  if (!currentDataset) {
    return (
      <div className="workspace-container">
        <div className="alert alert-info">
          <Info size={18} style={{ flexShrink: 0 }} />
          <div>
            <strong>No Dataset Registered</strong>
            <p style={{ marginTop: '4px', fontSize: '13px' }}>
              Please navigate to <strong>Market Data</strong> to upload or register a CSV dataset before defining a portfolio universe.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="workspace-container">
      <form onSubmit={handleValidate}>
        {/* Portfolio Specification Card */}
        <div className="card" style={{ marginBottom: '24px' }}>
          <div className="card-header">
            <div className="card-title">
              <SlidersHorizontal size={18} style={{ color: 'var(--accent)' }} />
              <span>Portfolio Universe Definition & Constraints</span>
            </div>
            <span className="badge badge-neutral">Dataset: {currentDataset.filename}</span>
          </div>

          {validationError && (
            <div className="alert alert-danger">
              <XCircle size={18} style={{ flexShrink: 0 }} />
              <div>{validationError}</div>
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginBottom: '20px' }}>
            <div className="form-group">
              <label className="form-label">Portfolio Name</label>
              <input
                type="text"
                className="input"
                value={portfolioName}
                onChange={(e) => setPortfolioName(e.target.value)}
                required
                maxLength={120}
              />
            </div>

            <div className="form-group">
              <label className="form-label">
                <span>Start Date Slice (Optional)</span>
                <Calendar size={13} style={{ color: 'var(--text-muted)' }} />
              </label>
              <input
                type="date"
                className="input"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">
                <span>End Date Slice (Optional)</span>
                <Calendar size={13} style={{ color: 'var(--text-muted)' }} />
              </label>
              <input
                type="date"
                className="input"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </div>
          </div>

          {/* Asset Selection Grid */}
          <div style={{ marginBottom: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
              <label className="form-label" style={{ marginBottom: 0 }}>
                Select Asset Universe ({selectedAssetTickers.length} of {availableAssets.length} selected)
              </label>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button type="button" onClick={handleSelectAll} className="btn btn-outline" style={{ padding: '2px 8px', fontSize: '11px' }}>
                  Select All
                </button>
                <button type="button" onClick={handleDeselectAll} className="btn btn-outline" style={{ padding: '2px 8px', fontSize: '11px' }}>
                  Deselect All
                </button>
              </div>
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
                gap: '8px',
                padding: '12px',
                backgroundColor: 'var(--bg-input)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-medium)',
                maxHeight: '220px',
                overflowY: 'auto',
              }}
            >
              {availableAssets.map((asset) => {
                const isSelected = selectedAssetTickers.includes(asset.ticker);
                return (
                  <div
                    key={asset.asset_id}
                    onClick={() => handleToggleAsset(asset.ticker)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '8px 10px',
                      borderRadius: 'var(--radius-sm)',
                      backgroundColor: isSelected ? 'var(--bg-elevated)' : 'transparent',
                      border: '1px solid',
                      borderColor: isSelected ? 'var(--accent)' : 'var(--border-subtle)',
                      cursor: 'pointer',
                      transition: 'all 0.1s ease',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => {}} // handled by div onClick
                      style={{ cursor: 'pointer' }}
                    />
                    <div>
                      <div className="font-mono" style={{ fontWeight: 600, fontSize: '13px', color: isSelected ? 'var(--accent)' : 'var(--text-primary)' }}>
                        {asset.ticker}
                      </div>
                      <div style={{ fontSize: '10px', color: 'var(--text-dim)' }}>
                        {asset.market} • {asset.currency}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Investment Constraints Box */}
          <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '20px', marginBottom: '20px' }}>
            <h4 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Layers size={14} /> Investment Constraints & Exposure Limits
            </h4>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
              <div className="form-group">
                <label className="form-label">
                  <span>Min Weight Cap (l_i)</span>
                  <span className="font-mono">{defaultMinWeight * 100}%</span>
                </label>
                <input
                  type="number"
                  step="0.01"
                  className="input font-mono"
                  value={defaultMinWeight}
                  onChange={(e) => setDefaultMinWeight(parseFloat(e.target.value) || 0)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">
                  <span>Max Weight Cap (u_i)</span>
                  <span className="font-mono">{defaultMaxWeight * 100}%</span>
                </label>
                <input
                  type="number"
                  step="0.01"
                  className="input font-mono"
                  value={defaultMaxWeight}
                  onChange={(e) => setDefaultMaxWeight(parseFloat(e.target.value) || 0)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">
                  <span>Target Net Exposure sum(w_i)</span>
                  <span className="font-mono">{targetTotalWeight * 100}%</span>
                </label>
                <input
                  type="number"
                  step="0.01"
                  className="input font-mono"
                  value={targetTotalWeight}
                  onChange={(e) => setTargetTotalWeight(parseFloat(e.target.value) || 0)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Gross Exposure Limit sum(|w_i|)</label>
                <input
                  type="number"
                  step="0.1"
                  className="input font-mono"
                  placeholder="e.g. 1.0 (Optional)"
                  value={maxGrossExposure}
                  onChange={(e) => setMaxGrossExposure(e.target.value)}
                />
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '10px' }}>
              <input
                id="allow-short-checkbox"
                type="checkbox"
                checked={allowShort}
                onChange={(e) => setAllowShort(e.target.checked)}
                style={{ cursor: 'pointer' }}
              />
              <label htmlFor="allow-short-checkbox" style={{ fontSize: '13px', cursor: 'pointer', color: 'var(--text-secondary)' }}>
                Allow Short Positions (<code className="font-mono">allow_short = true</code>)
              </label>
            </div>
          </div>

          {/* Validation Action */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
            <button
              type="submit"
              disabled={isValidating || selectedAssetTickers.length === 0}
              className="btn btn-primary"
            >
              {isValidating ? <RefreshCw size={15} className="spin" /> : <CheckCircle size={15} />}
              <span>{isValidating ? 'Validating Constraints...' : 'Validate Portfolio Definition'}</span>
            </button>
          </div>
        </div>
      </form>

      {/* Validation Report Output */}
      {validationReport && (
        <div className="card" style={{ marginBottom: '24px' }}>
          <div className="card-header">
            <div className="card-title">
              {validationReport.is_valid ? (
                <CheckCircle size={18} style={{ color: 'var(--success)' }} />
              ) : (
                <XCircle size={18} style={{ color: 'var(--danger)' }} />
              )}
              <span>
                Portfolio Validation Audit: {validationReport.is_valid ? 'Mathematically Feasible' : 'Validation Infeasible'}
              </span>
            </div>
            <span className={`badge ${validationReport.is_valid ? 'badge-success' : 'badge-danger'}`}>
              {validationReport.is_valid ? 'PASSED' : 'REJECTED'}
            </span>
          </div>

          {/* Blocking Errors */}
          {validationReport.errors && validationReport.errors.length > 0 && (
            <div className="alert alert-danger" style={{ marginBottom: '16px' }}>
              <XCircle size={18} style={{ flexShrink: 0 }} />
              <div>
                <strong>Blocking Errors ({validationReport.errors.length}):</strong>
                <ul style={{ paddingLeft: '20px', marginTop: '4px' }}>
                  {validationReport.errors.map((err, idx) => (
                    <li key={idx}>{err}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* Non-blocking Warnings */}
          {validationReport.warnings && validationReport.warnings.length > 0 && (
            <div className="alert alert-warning" style={{ marginBottom: '16px' }}>
              <AlertTriangle size={18} style={{ flexShrink: 0 }} />
              <div>
                <strong>Non-Blocking Warnings ({validationReport.warnings.length}):</strong>
                <ul style={{ paddingLeft: '20px', marginTop: '4px' }}>
                  {validationReport.warnings.map((w, idx) => (
                    <li key={idx}>{w}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '14px', marginBottom: '16px' }}>
            <div style={{ padding: '12px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Currency Policy</div>
              <div style={{ fontSize: '14px', fontWeight: 600, marginTop: '4px' }}>
                Base Currency: <span className="badge badge-info">{validationReport.currency_policy?.base_currency || 'USD'}</span>
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                Currencies present: {(validationReport.currency_policy?.currencies_present || []).join(', ')}
              </div>
            </div>

            <div style={{ padding: '12px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Historical Window</div>
              <div className="font-mono" style={{ fontSize: '14px', fontWeight: 600, marginTop: '4px' }}>
                {validationReport.date_coverage?.start_date} to {validationReport.date_coverage?.end_date}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                Common clean bars: <strong style={{ color: 'var(--success)' }}>{validationReport.date_coverage?.common_bar_count}</strong>
              </div>
            </div>

            <div style={{ padding: '12px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Constraint Space</div>
              <div style={{ fontSize: '14px', fontWeight: 600, marginTop: '4px' }}>
                {validationReport.feasibility?.is_feasible ? (
                  <span style={{ color: 'var(--success)' }}>Feasible Hypercube</span>
                ) : (
                  <span style={{ color: 'var(--danger)' }}>Infeasible Bounds</span>
                )}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                Target: {Number(targetTotalWeight * 100).toFixed(0)}% • [{Number(defaultMinWeight * 100).toFixed(0)}%, {Number(defaultMaxWeight * 100).toFixed(0)}%]
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
