/**
 * Master Report Viewer & Interactive Print/PDF Studio
 *
 * Provides:
 * - Tabbed or unified preview across Fact Sheet, Tear Sheet, and Research Diagnostics Annex.
 * - Toggle for including/excluding the optional 3rd page Research Diagnostics Annex.
 * - Interactive action toolbar with Print / Save as PDF trigger.
 * - Screen preview canvas with subtle physical paper margins and shadows.
 * - Clean @media print rules that hide screen controls and enforce physical page breaks.
 */

import React, { useState } from 'react';
import type { InstitutionalReportResponse } from '../../types/reporting';
import { apiClient } from '../../api/client';
import { StrategyFactSheetView } from './StrategyFactSheetView';

import { InstitutionalTearSheetView } from './InstitutionalTearSheetView';
import { ResearchDiagnosticsAnnexView } from './ResearchDiagnosticsAnnexView';

interface InstitutionalReportViewerProps {
  report: InstitutionalReportResponse;
  initialTab?: 'fact_sheet' | 'tear_sheet' | 'all';
  onClose?: () => void;
}

export const InstitutionalReportViewer: React.FC<InstitutionalReportViewerProps> = ({
  report,
  initialTab = 'tear_sheet',
  onClose,
}) => {
  const [activeTab, setActiveTab] = useState<'fact_sheet' | 'tear_sheet' | 'all'>(initialTab);
  const [includeAnnex, setIncludeAnnex] = useState<boolean>(Boolean(report.research_annex));
  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const factSheet = report.fact_sheet;
  const tearSheet = report.tear_sheet;
  const annex = report.research_annex;

  const handlePrint = () => {
    window.print();
  };

  const handleExportPdf = async () => {
    const backtestId = report.envelope.source_backtest_id || 'backtest';
    setIsExporting(true);
    setExportError(null);
    try {
      let blob: Blob;
      let filename = `report_${activeTab}.pdf`;
      if (activeTab === 'fact_sheet') {
        blob = await apiClient.exportStrategyFactSheetPdf(backtestId);
        filename = `fact_sheet_${backtestId.slice(0, 8)}.pdf`;
      } else if (activeTab === 'tear_sheet') {
        blob = await apiClient.exportInstitutionalTearSheetPdf(backtestId);
        filename = `tear_sheet_${backtestId.slice(0, 8)}.pdf`;
      } else {
        blob = await apiClient.exportUnifiedInstitutionalReportPdf(backtestId, null, report.envelope.source_experiment_id || undefined);
        filename = `institutional_dossier_${backtestId.slice(0, 8)}.pdf`;
      }
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      setExportError(err?.message || 'Failed to export server PDF.');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="report-viewer-root" role="region" aria-label="Institutional Report Viewer">
      {/* Screen-Only Control Toolbar */}
      <div className="report-toolbar no-print" role="toolbar" aria-label="Report Preview Controls">
        <div className="toolbar-left">
          <div className="toolbar-title">
            <span className="toolbar-badge">STAGE 34</span>
            <span className="toolbar-heading">Institutional Report Generator</span>
          </div>

          <div className="toolbar-tabs" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === 'tear_sheet'}
              className={`toolbar-tab-btn ${activeTab === 'tear_sheet' ? 'active' : ''}`}
              onClick={() => setActiveTab('tear_sheet')}
              disabled={!tearSheet}
            >
              Institutional Tear Sheet (2-Page)
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === 'fact_sheet'}
              className={`toolbar-tab-btn ${activeTab === 'fact_sheet' ? 'active' : ''}`}
              onClick={() => setActiveTab('fact_sheet')}
              disabled={!factSheet}
            >
              Strategy Fact Sheet (1-Page)
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === 'all'}
              className={`toolbar-tab-btn ${activeTab === 'all' ? 'active' : ''}`}
              onClick={() => setActiveTab('all')}
            >
              Unified Complete Dossier
            </button>
          </div>
        </div>

        <div className="toolbar-right">
          {annex && (
            <label className="toolbar-annex-toggle">
              <input
                type="checkbox"
                checked={includeAnnex}
                onChange={(e) => setIncludeAnnex(e.target.checked)}
              />
              <span>Include Research Annex (Page 3)</span>
            </label>
          )}

          <button
            type="button"
            className="toolbar-export-btn"
            onClick={handleExportPdf}
            disabled={isExporting}
            style={{
              backgroundColor: '#0D9488',
              color: '#FFFFFF',
              border: 'none',
              fontSize: '13px',
              fontWeight: 600,
              padding: '8px 16px',
              borderRadius: '6px',
              cursor: isExporting ? 'wait' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              opacity: isExporting ? 0.7 : 1,
            }}
            title="Download authoritative server-rendered institutional PDF"
          >
            {isExporting ? '⏳ Rendering...' : '📥 Export PDF'}
          </button>

          <button
            type="button"
            className="toolbar-print-btn"
            onClick={handlePrint}
            title="Trigger browser print dialog to save as PDF or print on letter/A4 paper"
          >
            🖨 Print / Save as PDF
          </button>

          {onClose && (
            <button type="button" className="toolbar-close-btn" onClick={onClose} title="Close preview">
              ✕
            </button>
          )}
        </div>
      </div>

      {exportError && (
        <div style={{ backgroundColor: '#FEF2F2', borderBottom: '1px solid #FCA5A5', padding: '8px 24px', color: '#991B1B', fontSize: '12px' }}>
          <strong>Export Error:</strong> {exportError}
        </div>
      )}

      {/* Screen Canvas with Physical Page Simulation */}
      <main className="report-canvas-container">
        {/* Render Fact Sheet if active */}
        {activeTab === 'fact_sheet' && factSheet && (
          <div className="print-page-wrapper">
            <StrategyFactSheetView payload={factSheet} />
          </div>
        )}

        {/* Render Tear Sheet if active */}
        {activeTab === 'tear_sheet' && tearSheet && (
          <div className="print-page-wrapper">
            <InstitutionalTearSheetView payload={tearSheet} />
            {includeAnnex && annex && (
              <div className="print-page-wrapper page-break-before">
                <ResearchDiagnosticsAnnexView payload={annex} pageNumber={3} totalPages={3} />
              </div>
            )}
          </div>
        )}

        {/* Render Unified Dossier (Fact Sheet + Tear Sheet + Annex) */}
        {activeTab === 'all' && (
          <div className="print-page-wrapper">
            {factSheet && (
              <div className="print-section">
                <StrategyFactSheetView payload={factSheet} />
              </div>
            )}
            {tearSheet && (
              <div className="print-section page-break-before">
                <InstitutionalTearSheetView payload={tearSheet} />
              </div>
            )}
            {includeAnnex && annex && (
              <div className="print-section page-break-before">
                <ResearchDiagnosticsAnnexView
                  payload={annex}
                  pageNumber={factSheet && tearSheet ? 4 : 3}
                  totalPages={factSheet && tearSheet ? 4 : 3}
                />
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
};
