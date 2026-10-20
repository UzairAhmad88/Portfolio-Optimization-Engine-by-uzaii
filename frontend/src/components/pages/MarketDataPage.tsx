import React, { useState, useEffect } from 'react';
import {
  Upload,
  FileCheck,
  AlertTriangle,
  XCircle,
  Database,
  CheckCircle,
  Search,
  RefreshCw,
  Info,
  HardDrive,
  ShieldCheck,
  Activity,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { useDataset } from '../../context/DatasetContext';
import type {
  CorporateActionEvent,
  DatasetMetadataResponse,
  DatasetQueryResponse,
  QualityAuditReport,
  ValidationReportResponse,
} from '../../types/api';

export const MarketDataPage: React.FC = () => {
  const {
    currentDataset,
    setCurrentDataset,
    savedDatasets,
    refreshSavedDatasets,
    isLoadingDatasets,
    availableAssets,
    isLoadingAssets,
    refreshAssets,
  } = useDataset();

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isPreviewing, setIsPreviewing] = useState<boolean>(false);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [previewReport, setPreviewReport] = useState<ValidationReportResponse | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);

  // Query state
  const [queryStartDate, setQueryStartDate] = useState<string>('2023-01-01');
  const [queryEndDate, setQueryEndDate] = useState<string>('2023-12-31');
  const [queryTicker, setQueryTicker] = useState<string>('');
  const [isQuerying, setIsQuerying] = useState<boolean>(false);
  const [queryResult, setQueryResult] = useState<DatasetQueryResponse | null>(null);
  const [queryError, setQueryError] = useState<string | null>(null);

  // Quality Audit & Corporate Actions state
  const [isAuditing, setIsAuditing] = useState<boolean>(false);
  const [qualityReport, setQualityReport] = useState<QualityAuditReport | null>(null);
  const [auditError, setAuditError] = useState<string | null>(null);

  const [corporateActions, setCorporateActions] = useState<CorporateActionEvent[]>([]);
  const [isLoadingCAs, setIsLoadingCAs] = useState<boolean>(false);
  const [caError, setCaError] = useState<string | null>(null);

  useEffect(() => {
    if (currentDataset) {
      handleFetchCorporateActions(currentDataset.dataset_id);
      setQualityReport(null);
    }
  }, [currentDataset?.dataset_id]);

  const handleRunAudit = async () => {
    if (!currentDataset) return;
    setIsAuditing(true);
    setAuditError(null);
    try {
      const rep = await apiClient.auditDatasetQuality(currentDataset.dataset_id);
      setQualityReport(rep);
    } catch (err: any) {
      setAuditError(err.message || 'Quality audit failed.');
    } finally {
      setIsAuditing(false);
    }
  };

  const handleFetchCorporateActions = async (dsId: string) => {
    setIsLoadingCAs(true);
    setCaError(null);
    try {
      const cas = await apiClient.queryCorporateActions({ dataset_id: dsId });
      setCorporateActions(cas);
    } catch (err: any) {
      setCaError(err.message || 'Failed to fetch corporate actions.');
    } finally {
      setIsLoadingCAs(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setPreviewReport(null);
      setUploadError(null);
      setUploadSuccess(null);
    }
  };

  const handlePreview = async () => {
    if (!selectedFile) return;
    setIsPreviewing(true);
    setUploadError(null);
    setUploadSuccess(null);
    try {
      const report = await apiClient.previewCsv(selectedFile);
      setPreviewReport(report);
    } catch (err: any) {
      setUploadError(err.message || 'Failed to preview CSV file.');
      setPreviewReport(null);
    } finally {
      setIsPreviewing(false);
    }
  };

  const handleRegister = async () => {
    if (!selectedFile) return;
    setIsUploading(true);
    setUploadError(null);
    setUploadSuccess(null);
    try {
      const registered = await apiClient.uploadCsv(selectedFile);
      await refreshSavedDatasets();
      setCurrentDataset(registered);
      await refreshAssets(registered.dataset_id);
      setPreviewReport(null);
      setSelectedFile(null);
      setUploadSuccess(`Dataset '${registered.filename}' successfully persisted to database storage (${registered.valid_rows} price bars).`);
    } catch (err: any) {
      setUploadError(err.message || 'Failed to register dataset.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleSelectDataset = async (dataset: DatasetMetadataResponse) => {
    setCurrentDataset(dataset);
    await refreshAssets(dataset.dataset_id);
  };

  const handleExecuteQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentDataset) return;
    setIsQuerying(true);
    setQueryError(null);
    try {
      const tickers = queryTicker.trim()
        ? queryTicker.split(',').map((t) => t.trim().toUpperCase()).filter(Boolean)
        : undefined;

      const res = await apiClient.queryDataset({
        dataset_id: currentDataset.dataset_id,
        start_date: queryStartDate,
        end_date: queryEndDate,
        tickers,
      });
      setQueryResult(res);
    } catch (err: any) {
      setQueryError(err.message || 'Failed to execute dataset query.');
      setQueryResult(null);
    } finally {
      setIsQuerying(false);
    }
  };

  return (
    <div className="workspace-container">
      {/* Upload and Ingestion Section */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <div className="card-header">
          <div className="card-title">
            <Upload size={18} style={{ color: 'var(--accent)' }} />
            <span>CSV Market Data Ingestion & Pre-Registration Validation</span>
          </div>
          <span className="badge badge-neutral">Max file size: 10 MB</span>
        </div>

        <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginBottom: '16px' }}>
          Upload daily adjusted price series in CSV format. Required headers: <code className="font-mono">date, ticker, market, currency, close</code>.
          Optional: <code className="font-mono">open, high, low, volume, adj_close</code>. Datasets are validated and atomically stored in the persistent database.
        </p>

        {uploadSuccess && (
          <div className="alert alert-success" style={{ marginBottom: '16px' }}>
            <CheckCircle size={18} style={{ flexShrink: 0 }} />
            <div>{uploadSuccess}</div>
          </div>
        )}

        {uploadError && (
          <div className="alert alert-danger" style={{ marginBottom: '16px' }}>
            <XCircle size={18} style={{ flexShrink: 0 }} />
            <div>
              <strong>Ingestion Error:</strong> {uploadError}
            </div>
          </div>
        )}

        {/* File Select & Actions */}
        <div
          style={{
            border: '2px dashed var(--border-medium)',
            borderRadius: 'var(--radius-lg)',
            padding: '24px',
            textAlign: 'center',
            backgroundColor: 'var(--bg-input)',
            marginBottom: '16px',
          }}
        >
          <input
            id="csv-file-input"
            type="file"
            accept=".csv"
            onChange={handleFileChange}
            style={{ display: 'none' }}
          />
          <label htmlFor="csv-file-input" className="btn btn-secondary" style={{ cursor: 'pointer', marginBottom: '12px' }}>
            <Database size={15} />
            <span>{selectedFile ? selectedFile.name : 'Select CSV File...'}</span>
          </label>
          <div style={{ fontSize: '12px', color: 'var(--text-dim)' }}>
            {selectedFile
              ? `Selected file: ${selectedFile.name} (${(selectedFile.size / 1024).toFixed(1)} KB)`
              : 'Drag & drop or browse to select your historical market data CSV'}
          </div>
        </div>

        {selectedFile && (
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <button
              onClick={handlePreview}
              disabled={isPreviewing || isUploading}
              className="btn btn-secondary"
            >
              {isPreviewing ? <RefreshCw size={14} className="spin" /> : <FileCheck size={14} />}
              <span>{isPreviewing ? 'Validating Schema...' : 'Preview & Validate'}</span>
            </button>

            <button
              onClick={handleRegister}
              disabled={isUploading || isPreviewing}
              className="btn btn-primary"
            >
              {isUploading ? <RefreshCw size={14} className="spin" /> : <CheckCircle size={14} />}
              <span>{isUploading ? 'Persisting to Storage...' : 'Register Dataset into Persistent Storage'}</span>
            </button>
          </div>
        )}

        {/* Preview Report Card */}
        {previewReport && (
          <div
            style={{
              marginTop: '20px',
              padding: '16px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--bg-elevated)',
              border: '1px solid var(--border-medium)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <div style={{ fontWeight: 600, fontSize: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <CheckCircle size={16} style={{ color: 'var(--success)' }} />
                <span>Validation Audit Results</span>
              </div>
              <span className="font-mono" style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                SHA-256: {previewReport.content_sha256.substring(0, 16)}...
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px', marginBottom: '16px' }}>
              <div style={{ padding: '10px', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-input)' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Rows Examined</div>
                <div className="font-mono" style={{ fontSize: '18px', fontWeight: 600 }}>{previewReport.rows_examined.toLocaleString()}</div>
              </div>
              <div style={{ padding: '10px', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-input)' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Valid Bars Accepted</div>
                <div className="font-mono" style={{ fontSize: '18px', fontWeight: 600, color: 'var(--success)' }}>{previewReport.valid_rows.toLocaleString()}</div>
              </div>
              <div style={{ padding: '10px', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-input)' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Rejected Rows</div>
                <div className="font-mono" style={{ fontSize: '18px', fontWeight: 600, color: previewReport.rejected_rows > 0 ? 'var(--danger)' : 'var(--text-muted)' }}>
                  {previewReport.rejected_rows.toLocaleString()}
                </div>
              </div>
            </div>

            {/* Non-blocking warnings */}
            {previewReport.warnings && previewReport.warnings.length > 0 && (
              <div style={{ marginBottom: '12px' }}>
                <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--warning)', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                  <AlertTriangle size={14} /> Schema Warnings ({previewReport.warnings.length}):
                </div>
                <ul style={{ paddingLeft: '20px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                  {previewReport.warnings.map((w, idx) => (
                    <li key={idx}>{w.message}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Row rejection errors */}
            {previewReport.errors && previewReport.errors.length > 0 && (
              <div>
                <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                  <XCircle size={14} /> Rejected Rows Breakdown ({previewReport.errors.length}):
                </div>
                <div className="table-container" style={{ maxHeight: '160px' }}>
                  <table className="table">
                    <thead>
                      <tr>
                        <th>CSV Row</th>
                        <th>Failure Causes</th>
                      </tr>
                    </thead>
                    <tbody>
                      {previewReport.errors.slice(0, 50).map((err, idx) => (
                        <tr key={idx}>
                          <td className="num-cell" style={{ width: '100px' }}>{err.row}</td>
                          <td>{err.reasons.join(', ')}</td>
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

      {/* Persistent Datasets in Storage List */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <div className="card-header">
          <div className="card-title">
            <HardDrive size={18} style={{ color: 'var(--accent)' }} />
            <span>Persisted Datasets in Storage ({savedDatasets.length})</span>
          </div>
          <button
            onClick={() => refreshSavedDatasets()}
            disabled={isLoadingDatasets}
            className="btn btn-outline"
            style={{ padding: '4px 8px', fontSize: '12px' }}
            title="Refresh dataset list from database"
          >
            <RefreshCw size={13} className={isLoadingDatasets ? 'spin' : ''} />
            <span>Refresh List</span>
          </button>
        </div>

        {savedDatasets.length > 0 ? (
          <div className="table-container" style={{ maxHeight: '200px' }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Filename</th>
                  <th>Dataset ID</th>
                  <th>Stored Price Bars</th>
                  <th>Registered At</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {savedDatasets.map((ds) => {
                  const isActive = currentDataset?.dataset_id === ds.dataset_id;
                  return (
                    <tr key={ds.dataset_id} style={{ backgroundColor: isActive ? 'var(--bg-elevated)' : undefined }}>
                      <td style={{ fontWeight: 600 }}>
                        {ds.filename} {isActive && <span className="badge badge-success" style={{ marginLeft: '6px' }}>Active</span>}
                      </td>
                      <td className="font-mono" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                        {ds.dataset_id}
                      </td>
                      <td className="num-cell" style={{ color: 'var(--success)' }}>
                        {ds.valid_rows.toLocaleString()}
                      </td>
                      <td className="font-mono" style={{ fontSize: '11px' }}>
                        {ds.created_at ? new Date(ds.created_at).toLocaleString() : '—'}
                      </td>
                      <td>
                        <button
                          onClick={() => handleSelectDataset(ds)}
                          disabled={isActive}
                          className={`btn ${isActive ? 'btn-secondary' : 'btn-outline'}`}
                          style={{ fontSize: '11px', padding: '3px 8px' }}
                        >
                          {isActive ? 'Current' : 'Select as Active'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ padding: '16px', color: 'var(--text-dim)', textAlign: 'center', fontSize: '13px' }}>
            No persistent datasets currently found in the database. Upload a CSV file above to persist market data.
          </div>
        )}
      </div>

      {/* Active Dataset Overview & Assets Explorer */}
      {currentDataset ? (
        <div className="card" style={{ marginBottom: '24px' }}>
          <div className="card-header">
            <div className="card-title">
              <Database size={18} style={{ color: 'var(--accent)' }} />
              <span>Active Dataset: {currentDataset.filename}</span>
            </div>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <span className="badge badge-success">Durable Database Storage</span>
              <button
                onClick={() => refreshAssets(currentDataset.dataset_id)}
                disabled={isLoadingAssets}
                className="btn btn-outline"
                style={{ padding: '4px 8px', fontSize: '12px' }}
                title="Refresh assets"
              >
                <RefreshCw size={13} className={isLoadingAssets ? 'spin' : ''} />
              </button>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px', marginBottom: '20px' }}>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              <strong>Dataset ID:</strong> <span className="font-mono" style={{ color: 'var(--text-primary)' }}>{currentDataset.dataset_id}</span>
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              <strong>Registered At:</strong> <span className="font-mono">{currentDataset.created_at}</span>
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              <strong>Stored Price Bars:</strong> <span className="font-mono" style={{ color: 'var(--success)' }}>{currentDataset.valid_rows.toLocaleString()}</span>
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              <strong>PIT Integrity:</strong>{' '}
              <span className={`badge ${currentDataset.point_in_time_status === 'verified_pass' ? 'badge-success' : 'badge-neutral'}`} style={{ marginLeft: '4px' }}>
                <ShieldCheck size={12} style={{ display: 'inline', marginRight: '4px' }} />
                {currentDataset.point_in_time_status || 'unverified_legacy'}
              </span>
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              <strong>Exchange Calendar:</strong> <span className="font-mono">{currentDataset.calendar_version || 'US-NYSE / PSX-KHI (2026.1)'}</span>
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              <strong>Adjustment Policy:</strong> <span className="font-mono">{currentDataset.adjustment_policy_version || 'CRSP 2026.1'}</span>
            </div>
          </div>

          <h4 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '10px' }}>
            Discovered Asset Universe ({availableAssets.length})
          </h4>

          {isLoadingAssets ? (
            <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>
              <RefreshCw size={18} className="spin" style={{ margin: '0 auto 8px' }} />
              <div>Loading asset metadata from database...</div>
            </div>
          ) : availableAssets.length > 0 ? (
            <div className="table-container" style={{ marginBottom: '24px' }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Asset Identifier</th>
                    <th>Ticker</th>
                    <th>Market</th>
                    <th>Currency</th>
                    <th>Start Date</th>
                    <th>End Date</th>
                    <th className="num-cell">Observations</th>
                  </tr>
                </thead>
                <tbody>
                  {availableAssets.map((asset) => (
                    <tr key={asset.asset_id}>
                      <td className="font-mono" style={{ fontWeight: 600, color: 'var(--accent)' }}>
                        {asset.asset_id}
                      </td>
                      <td>{asset.ticker}</td>
                      <td>
                        <span className="badge badge-neutral">{asset.market}</span>
                      </td>
                      <td>{asset.currency}</td>
                      <td className="font-mono">{asset.start_date}</td>
                      <td className="font-mono">{asset.end_date}</td>
                      <td className="num-cell">{asset.observation_count.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ padding: '16px', color: 'var(--text-dim)', textAlign: 'center' }}>
              No assets discovered for this dataset.
            </div>
          )}

          {/* Market Data Quality & Corporate Actions Controls */}
          <div style={{ marginTop: '20px', borderTop: '1px solid var(--border-medium)', paddingTop: '20px', marginBottom: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '8px' }}>
              <div>
                <h4 style={{ fontSize: '14px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px', margin: 0 }}>
                  <ShieldCheck size={16} style={{ color: 'var(--accent)' }} />
                  Point-in-Time Quality Controls & Corporate Actions
                </h4>
                <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '2px 0 0' }}>
                  Audits OHLC geometry, missing calendar sessions, unadjusted price jumps, and registered corporate actions.
                </p>
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  onClick={handleRunAudit}
                  disabled={isAuditing}
                  className="btn btn-secondary"
                  style={{ fontSize: '12px', padding: '6px 12px' }}
                >
                  <Activity size={14} className={isAuditing ? 'spin' : ''} />
                  <span>{isAuditing ? 'Auditing...' : 'Run Quality Audit'}</span>
                </button>
              </div>
            </div>

            {auditError && (
              <div className="alert alert-danger" style={{ marginBottom: '12px' }}>
                <XCircle size={16} style={{ flexShrink: 0 }} />
                <div>{auditError}</div>
              </div>
            )}

            {qualityReport && (
              <div style={{ padding: '12px', backgroundColor: 'var(--bg-elevated)', borderRadius: '6px', marginBottom: '16px', border: '1px solid var(--border-subtle)' }}>
                <div style={{ display: 'flex', gap: '16px', alignItems: 'center', marginBottom: '10px', flexWrap: 'wrap' }}>
                  <span className={`badge ${qualityReport.is_valid ? 'badge-success' : 'badge-danger'}`} style={{ fontSize: '12px', padding: '4px 8px' }}>
                    {qualityReport.is_valid ? '✓ Quality Audit Passed' : '⚠ Quality Issues Detected'}
                  </span>
                  <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                    Errors: <strong style={{ color: qualityReport.error_count > 0 ? 'var(--danger)' : 'var(--text-primary)' }}>{qualityReport.error_count}</strong>
                  </span>
                  <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                    Warnings: <strong style={{ color: qualityReport.warning_count > 0 ? 'var(--warning)' : 'var(--text-primary)' }}>{qualityReport.warning_count}</strong>
                  </span>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    Policy: {qualityReport.policy_version}
                  </span>
                </div>

                {qualityReport.findings.length > 0 ? (
                  <div className="table-container" style={{ maxHeight: '180px' }}>
                    <table className="table">
                      <thead>
                        <tr>
                          <th>Severity</th>
                          <th>Rule</th>
                          <th>Security</th>
                          <th>Date</th>
                          <th>Finding Description</th>
                        </tr>
                      </thead>
                      <tbody>
                        {qualityReport.findings.slice(0, 50).map((f, idx) => (
                          <tr key={idx}>
                            <td>
                              <span className={`badge ${f.severity === 'error' ? 'badge-danger' : f.severity === 'warning' ? 'badge-warning' : 'badge-neutral'}`}>
                                {f.severity.toUpperCase()}
                              </span>
                            </td>
                            <td className="font-mono" style={{ fontSize: '11px' }}>{f.rule_id}</td>
                            <td>{f.ticker}:{f.market}</td>
                            <td className="font-mono">{f.date || '—'}</td>
                            <td style={{ fontSize: '12px' }}>{f.message}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div style={{ fontSize: '12px', color: 'var(--success)' }}>
                    ✓ No anomalies, missing sessions, or geometry inversions detected.
                  </div>
                )}
              </div>
            )}

            {/* Corporate Actions Ledger Sub-Table */}
            {caError && (
              <div className="alert alert-danger" style={{ marginTop: '10px', marginBottom: '10px' }}>
                <XCircle size={14} style={{ flexShrink: 0 }} />
                <div>{caError}</div>
              </div>
            )}

            {isLoadingCAs ? (
              <div style={{ padding: '12px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '12px' }}>
                <RefreshCw size={14} className="spin" style={{ display: 'inline', marginRight: '6px' }} />
                Loading registered corporate actions...
              </div>
            ) : corporateActions.length > 0 ? (
              <div style={{ marginTop: '14px' }}>
                <h5 style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '8px' }}>
                  Registered Corporate Actions ({corporateActions.length})
                </h5>
                <div className="table-container" style={{ maxHeight: '160px' }}>
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Event ID</th>
                        <th>Security</th>
                        <th>Type</th>
                        <th>Effective Date</th>
                        <th>Announcement</th>
                        <th className="num-cell">Value</th>
                        <th>Status</th>
                        <th>PIT Verified</th>
                      </tr>
                    </thead>
                    <tbody>
                      {corporateActions.map((ca) => (
                        <tr key={ca.id}>
                          <td className="font-mono" style={{ fontSize: '11px' }}>{ca.id}</td>
                          <td>{ca.ticker}:{ca.market}</td>
                          <td>
                            <span className="badge badge-neutral">{ca.event_type}</span>
                          </td>
                          <td className="font-mono">{ca.effective_date}</td>
                          <td className="font-mono">{ca.announcement_date || '—'}</td>
                          <td className="num-cell font-mono">{ca.value} {ca.currency}</td>
                          <td>
                            <span className={`badge ${ca.status === 'active' ? 'badge-success' : 'badge-neutral'}`}>
                              {ca.status}
                            </span>
                          </td>
                          <td>
                            {ca.is_point_in_time_verified ? (
                              <span style={{ color: 'var(--success)', fontSize: '12px' }}>✓ Verified</span>
                            ) : (
                              <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>Unverified</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}
          </div>

          {/* Historical Data Query Tool */}
          <div style={{ marginTop: '20px', borderTop: '1px solid var(--border-medium)', paddingTop: '20px' }}>
            <h4 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Search size={15} style={{ color: 'var(--accent)' }} />
              Historical Market Data Query
            </h4>

            {queryError && (
              <div className="alert alert-danger" style={{ marginBottom: '12px' }}>
                <XCircle size={16} style={{ flexShrink: 0 }} />
                <div>{queryError}</div>
              </div>
            )}

            <form onSubmit={handleExecuteQuery} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px', alignItems: 'end', marginBottom: '16px' }}>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Start Date</label>
                <input
                  type="date"
                  className="form-input"
                  value={queryStartDate}
                  onChange={(e) => setQueryStartDate(e.target.value)}
                  required
                />
              </div>

              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">End Date</label>
                <input
                  type="date"
                  className="form-input"
                  value={queryEndDate}
                  onChange={(e) => setQueryEndDate(e.target.value)}
                  required
                />
              </div>

              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Tickers (Optional, comma-separated)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. AAPL, MSFT"
                  value={queryTicker}
                  onChange={(e) => setQueryTicker(e.target.value)}
                />
              </div>

              <button
                type="submit"
                disabled={isQuerying}
                className="btn btn-secondary"
                style={{ height: '36px' }}
              >
                {isQuerying ? <RefreshCw size={14} className="spin" /> : <Search size={14} />}
                <span>{isQuerying ? 'Querying...' : 'Filter Records'}</span>
              </button>
            </form>

            {queryResult && (
              <div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '8px' }}>
                  Returned <strong style={{ color: 'var(--text-primary)' }}>{queryResult.row_count.toLocaleString()}</strong> matching price records ({queryResult.start_date} to {queryResult.end_date})
                </div>

                <div className="table-container" style={{ maxHeight: '240px' }}>
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Ticker</th>
                        <th>Market</th>
                        <th>Currency</th>
                        <th className="num-cell">Close</th>
                        <th className="num-cell">Volume</th>
                      </tr>
                    </thead>
                    <tbody>
                      {queryResult.data.slice(0, 100).map((row, idx) => (
                        <tr key={idx}>
                          <td className="font-mono">{row.date}</td>
                          <td style={{ fontWeight: 600 }}>{row.ticker}</td>
                          <td>{row.market}</td>
                          <td>{row.currency}</td>
                          <td className="num-cell">{Number(row.close).toFixed(2)}</td>
                          <td className="num-cell">{row.volume ? Number(row.volume).toLocaleString() : '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="alert alert-info">
          <Info size={18} style={{ flexShrink: 0 }} />
          <div>
            <strong>No Active Dataset Selected</strong>
            <p style={{ marginTop: '4px', fontSize: '12px' }}>
              Upload and register a new CSV dataset or select a persisted dataset from storage above to activate the asset universe, portfolio validation, numerical optimization, and risk modeling.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
