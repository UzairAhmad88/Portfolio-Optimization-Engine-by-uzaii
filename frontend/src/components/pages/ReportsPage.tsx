import React, { useState, useEffect } from 'react';
import {
  FileText,
  Download,
  Eye,
  RefreshCw,
  AlertCircle,
  Plus,
  ArrowLeft,
  CheckCircle,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import type { BacktestListItem } from '../../types/api';
import type { InstitutionalReportResponse } from '../../types/reporting';
import { InstitutionalReportViewer } from '../reports/InstitutionalReportViewer';

export interface ReportItem {
  id: string;
  name: string;
  reportType: 'unified_tear_sheet' | 'tear_sheet' | 'fact_sheet';
  sourceBacktestId: string;
  strategyType: string;
  createdAt: string;
  status: 'ready' | 'generating' | 'failed';
}

export const ReportsPage: React.FC = () => {
  const [backtestRuns, setBacktestRuns] = useState<BacktestListItem[]>([]);
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Active report viewing state (Page 12: PDF Report Preview)
  const [activeReport, setActiveReport] = useState<InstitutionalReportResponse | null>(null);
  const [activeReportTitle, setActiveReportTitle] = useState<string>('');
  const [activeBacktestId, setActiveBacktestId] = useState<string | null>(null);
  const [isPreviewLoading, setIsPreviewLoading] = useState<boolean>(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  // Generate Report Modal
  const [isGenerateModalOpen, setIsGenerateModalOpen] = useState<boolean>(false);
  const [selectedBacktestId, setSelectedBacktestId] = useState<string>('');
  const [selectedReportType, setSelectedReportType] = useState<'unified_tear_sheet' | 'tear_sheet' | 'fact_sheet'>('unified_tear_sheet');
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const runs = await apiClient.listBacktests(50, 0);
      setBacktestRuns(runs);

      // Map completed backtests to available reports
      const generatedReports: ReportItem[] = runs
        .filter((r) => r.status === 'completed')
        .map((r) => ({
          id: `rep-${r.id}`,
          name: `${r.name || 'Strategy'} - Institutional Dossier`,
          reportType: 'unified_tear_sheet',
          sourceBacktestId: r.id,
          strategyType: r.strategy_type,
          createdAt: r.created_at,
          status: 'ready',
        }));

      setReports(generatedReports);
      if (runs.length > 0 && !selectedBacktestId) {
        setSelectedBacktestId(runs[0].id);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load reports and backtest history.');
    } finally {
      setIsLoading(false);
    }
  };

  const handlePreviewReport = async (report: ReportItem) => {
    setIsPreviewLoading(true);
    setPreviewError(null);
    setActiveBacktestId(report.sourceBacktestId);
    setActiveReportTitle(report.name);

    try {
      const unified = await apiClient.getUnifiedInstitutionalReport(report.sourceBacktestId);
      setActiveReport(unified as InstitutionalReportResponse);
    } catch (err: any) {
      setPreviewError(err.message || 'Failed to assemble report preview.');
      setActiveReport(null);
    } finally {
      setIsPreviewLoading(false);
    }
  };

  const handleClosePreview = () => {
    setActiveReport(null);
    setActiveBacktestId(null);
    setPreviewError(null);
  };

  const handleDownloadPdf = async (backtestId: string, reportName: string) => {
    setDownloadingId(backtestId);
    try {
      const blob = await apiClient.exportUnifiedInstitutionalReportPdf(backtestId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${reportName.replace(/\s+/g, '_')}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      alert(`PDF Export failed: ${err.message || 'Server-side rendering error'}`);
    } finally {
      setDownloadingId(null);
    }
  };

  const handleGenerateReportSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedBacktestId) return;

    setIsGenerating(true);
    try {
      const targetRun = backtestRuns.find((r) => r.id === selectedBacktestId);
      const newReport: ReportItem = {
        id: `rep-${selectedBacktestId}-${Date.now()}`,
        name: `${targetRun?.name || 'Quantitative Strategy'} - ${
          selectedReportType === 'fact_sheet'
            ? 'Strategy Fact Sheet'
            : selectedReportType === 'tear_sheet'
            ? 'Institutional Tear Sheet'
            : 'Unified Report Dossier'
        }`,
        reportType: selectedReportType,
        sourceBacktestId: selectedBacktestId,
        strategyType: targetRun?.strategy_type || 'custom',
        createdAt: new Date().toISOString(),
        status: 'ready',
      };

      setReports((prev) => [newReport, ...prev]);
      setIsGenerateModalOpen(false);

      // Automatically open preview for the generated report
      await handlePreviewReport(newReport);
    } catch (err: any) {
      alert(`Report compilation failed: ${err.message}`);
    } finally {
      setIsGenerating(false);
    }
  };

  // If in Preview Mode (Page 12: PDF Report Preview)
  if (activeReport || isPreviewLoading || previewError) {
    return (
      <div className="workspace-container animate-fade-in" style={{ padding: '24px', maxWidth: '1280px', margin: '0 auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <button
            onClick={handleClosePreview}
            className="btn btn-secondary"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
          >
            <ArrowLeft size={16} />
            Back to Reports Library
          </button>
          
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
              Source Backtest: <code style={{ color: 'var(--accent)' }}>{activeBacktestId?.slice(0, 8)}</code>
            </span>
            {activeBacktestId && (
              <button
                onClick={() => handleDownloadPdf(activeBacktestId, activeReportTitle || 'Report')}
                disabled={downloadingId === activeBacktestId}
                className="btn btn-primary"
                style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
              >
                {downloadingId === activeBacktestId ? (
                  <>
                    <RefreshCw size={16} className="animate-spin" />
                    Generating PDF...
                  </>
                ) : (
                  <>
                    <Download size={16} />
                    Download PDF
                  </>
                )}
              </button>
            )}
          </div>
        </div>

        {isPreviewLoading && (
          <div className="card" style={{ padding: '60px', textAlign: 'center' }}>
            <RefreshCw size={36} className="animate-spin" style={{ color: 'var(--accent)', margin: '0 auto 16px' }} />
            <h3 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '8px' }}>
              Compiling Institutional PDF Report...
            </h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>
              Assembling performance attribution, verified provenance manifests, vector wealth curves, and risk matrices.
            </p>
          </div>
        )}

        {previewError && (
          <div className="card" style={{ padding: '40px', borderLeft: '4px solid var(--danger)' }}>
            <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
              <AlertCircle size={24} style={{ color: 'var(--danger)', flexShrink: 0 }} />
              <div>
                <h4 style={{ color: 'var(--danger)', fontSize: '16px', fontWeight: 600, marginBottom: '4px' }}>
                  Report Compilation Error
                </h4>
                <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '16px' }}>
                  {previewError}
                </p>
                <button onClick={handleClosePreview} className="btn btn-secondary">
                  Return to Reports
                </button>
              </div>
            </div>
          </div>
        )}

        {activeReport && (
          <div style={{ background: 'var(--bg-card)', borderRadius: 'var(--radius-lg)', padding: '24px', border: '1px solid var(--border-medium)' }}>
            <InstitutionalReportViewer report={activeReport} />
          </div>
        )}
      </div>
    );
  }

  // Reports Library List View (Page 11: Reports Page)
  return (
    <div className="workspace-container animate-fade-in" style={{ padding: '24px', maxWidth: '1280px', margin: '0 auto' }}>
      {/* Header bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '4px' }}>
            Reports
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>
            Publication-ready strategy tear sheets, allocator fact sheets, and institutional PDF dossiers.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '12px' }}>
          <button
            onClick={loadData}
            disabled={isLoading}
            className="btn btn-secondary"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
          >
            <RefreshCw size={15} className={isLoading ? 'animate-spin' : ''} />
            Refresh
          </button>
          <button
            onClick={() => setIsGenerateModalOpen(true)}
            className="btn btn-primary"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
          >
            <Plus size={16} />
            Generate Report
          </button>
        </div>
      </div>

      {/* KPI Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        <div className="card" style={{ padding: '16px' }}>
          <div style={{ color: 'var(--text-muted)', fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', marginBottom: '4px' }}>
            Available Reports
          </div>
          <div style={{ fontSize: '26px', fontWeight: 700, color: 'var(--text-primary)' }}>
            {reports.length}
          </div>
        </div>

        <div className="card" style={{ padding: '16px' }}>
          <div style={{ color: 'var(--text-muted)', fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', marginBottom: '4px' }}>
            Completed Backtests
          </div>
          <div style={{ fontSize: '26px', fontWeight: 700, color: 'var(--accent)' }}>
            {backtestRuns.filter((r) => r.status === 'completed').length}
          </div>
        </div>

        <div className="card" style={{ padding: '16px' }}>
          <div style={{ color: 'var(--text-muted)', fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', marginBottom: '4px' }}>
            PDF Export Engine
          </div>
          <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--success)', display: 'flex', alignItems: 'center', gap: '6px', marginTop: '6px' }}>
            <CheckCircle size={16} />
            Headless Chromium Active
          </div>
        </div>

        <div className="card" style={{ padding: '16px' }}>
          <div style={{ color: 'var(--text-muted)', fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', marginBottom: '4px' }}>
            Format Standard
          </div>
          <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-secondary)', marginTop: '6px' }}>
            CSS Paged Media (@page)
          </div>
        </div>
      </div>

      {/* Main Reports Table */}
      <div className="card" style={{ overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ fontSize: '16px', fontWeight: 600 }}>Generated Reports Library</h3>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Showing {reports.length} publication-ready reports
          </span>
        </div>

        {isLoading ? (
          <div style={{ padding: '48px', textAlign: 'center', color: 'var(--text-secondary)' }}>
            <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 12px', color: 'var(--accent)' }} />
            Loading generated reports library...
          </div>
        ) : error ? (
          <div style={{ padding: '32px', textAlign: 'center', color: 'var(--danger)' }}>
            <AlertCircle size={24} style={{ margin: '0 auto 8px' }} />
            {error}
          </div>
        ) : reports.length === 0 ? (
          <div style={{ padding: '60px 20px', textAlign: 'center' }}>
            <FileText size={48} style={{ color: 'var(--text-muted)', margin: '0 auto 16px', opacity: 0.5 }} />
            <h4 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '6px' }}>No Reports Generated Yet</h4>
            <p style={{ color: 'var(--text-secondary)', fontSize: '14px', maxWidth: '440px', margin: '0 auto 20px' }}>
              Execute a strategy simulation in the Backtesting module or click Generate Report above to compile an institutional dossier.
            </p>
            <button
              onClick={() => setIsGenerateModalOpen(true)}
              disabled={backtestRuns.length === 0}
              className="btn btn-primary"
            >
              Generate First Report
            </button>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="table" style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead>
                <tr style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)', fontSize: '12px', textTransform: 'uppercase' }}>
                  <th style={{ padding: '12px 20px' }}>Name</th>
                  <th style={{ padding: '12px 16px' }}>Type</th>
                  <th style={{ padding: '12px 16px' }}>Strategy</th>
                  <th style={{ padding: '12px 16px' }}>Created</th>
                  <th style={{ padding: '12px 20px', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {reports.map((report) => (
                  <tr
                    key={report.id}
                    style={{ borderBottom: '1px solid var(--border-subtle)', transition: 'background-color 0.15s ease' }}
                    className="hover-row"
                  >
                    <td style={{ padding: '16px 20px', fontWeight: 600, color: 'var(--text-primary)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <FileText size={18} style={{ color: 'var(--accent)', flexShrink: 0 }} />
                        <span>{report.name}</span>
                      </div>
                    </td>
                    <td style={{ padding: '16px 16px' }}>
                      <span
                        style={{
                          fontSize: '11px',
                          fontWeight: 700,
                          padding: '3px 8px',
                          borderRadius: '4px',
                          background: 'rgba(56, 189, 248, 0.15)',
                          color: 'var(--accent)',
                          letterSpacing: '0.04em',
                        }}
                      >
                        PDF
                      </span>
                    </td>
                    <td style={{ padding: '16px 16px', color: 'var(--text-secondary)', fontSize: '13px' }}>
                      <code>{report.strategyType}</code>
                    </td>
                    <td style={{ padding: '16px 16px', color: 'var(--text-secondary)', fontSize: '13px' }}>
                      {new Date(report.createdAt).toLocaleDateString()}
                    </td>
                    <td style={{ padding: '16px 20px', textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', gap: '8px' }}>
                        <button
                          onClick={() => handlePreviewReport(report)}
                          title="Preview in browser"
                          className="btn btn-secondary"
                          style={{ padding: '6px 10px', fontSize: '12px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                        >
                          <Eye size={14} />
                          Preview
                        </button>

                        <button
                          onClick={() => handleDownloadPdf(report.sourceBacktestId, report.name)}
                          disabled={downloadingId === report.sourceBacktestId}
                          title="Download PDF export"
                          className="btn btn-secondary"
                          style={{ padding: '6px 10px', fontSize: '12px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                        >
                          {downloadingId === report.sourceBacktestId ? (
                            <RefreshCw size={14} className="animate-spin" />
                          ) : (
                            <Download size={14} />
                          )}
                          PDF
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

      {/* Generate Report Modal Dialog */}
      {isGenerateModalOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.75)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '16px',
          }}
        >
          <div
            className="card"
            style={{
              width: '100%',
              maxWidth: '520px',
              padding: '24px',
              background: 'var(--bg-card)',
              boxShadow: '0 20px 40px rgba(0, 0, 0, 0.5)',
            }}
          >
            <h3 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '6px' }}>
              Compile Institutional Report
            </h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginBottom: '20px' }}>
              Select an executed strategy backtest to assemble publication-ready tear sheets and metrics.
            </p>

            <form onSubmit={handleGenerateReportSubmit}>
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', marginBottom: '6px', color: 'var(--text-muted)' }}>
                  Select Backtest Run
                </label>
                <select
                  value={selectedBacktestId}
                  onChange={(e) => setSelectedBacktestId(e.target.value)}
                  className="input"
                  style={{ width: '100%', padding: '10px 12px' }}
                  required
                >
                  {backtestRuns
                    .filter((r) => r.status === 'completed')
                    .map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.name || 'Strategy Backtest'} ({r.strategy_type}) — {new Date(r.created_at).toLocaleDateString()}
                      </option>
                    ))}
                </select>
              </div>

              <div style={{ marginBottom: '24px' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', marginBottom: '6px', color: 'var(--text-muted)' }}>
                  Report Dossier Format
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
                  <button
                    type="button"
                    onClick={() => setSelectedReportType('unified_tear_sheet')}
                    className={`btn ${selectedReportType === 'unified_tear_sheet' ? 'btn-primary' : 'btn-secondary'}`}
                    style={{ fontSize: '12px', padding: '10px 6px', textAlign: 'center' }}
                  >
                    Unified (3-Page)
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedReportType('tear_sheet')}
                    className={`btn ${selectedReportType === 'tear_sheet' ? 'btn-primary' : 'btn-secondary'}`}
                    style={{ fontSize: '12px', padding: '10px 6px', textAlign: 'center' }}
                  >
                    Tear Sheet (2-Page)
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedReportType('fact_sheet')}
                    className={`btn ${selectedReportType === 'fact_sheet' ? 'btn-primary' : 'btn-secondary'}`}
                    style={{ fontSize: '12px', padding: '10px 6px', textAlign: 'center' }}
                  >
                    Fact Sheet (1-Page)
                  </button>
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                <button
                  type="button"
                  onClick={() => setIsGenerateModalOpen(false)}
                  className="btn btn-secondary"
                  disabled={isGenerating}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={isGenerating || !selectedBacktestId}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                >
                  {isGenerating ? (
                    <>
                      <RefreshCw size={14} className="animate-spin" />
                      Compiling...
                    </>
                  ) : (
                    'Generate Report'
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
