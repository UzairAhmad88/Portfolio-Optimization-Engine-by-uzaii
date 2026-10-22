/**
 * Institutional Report Header & Provenance Section
 * Renders executive title, reporting window, currency, strategy mandate metadata,
 * dataset snapshot lineage, cryptographic digests, and structured warning alerts.
 */

import React from 'react';
import type { CommonReportEnvelope, StrategyMandate, ReportWarning } from '../../types/reporting';
import { formatDate, formatCurrency, formatPercent } from './formatters';

interface ReportHeaderAndProvenanceProps {
  envelope: CommonReportEnvelope;
  mandate?: StrategyMandate | null;
  pageNumber?: number;
  totalPages?: number;
  subtitle?: string;
}

export const ReportHeaderAndProvenance: React.FC<ReportHeaderAndProvenanceProps> = ({
  envelope,
  mandate,
  pageNumber,
  totalPages,
  subtitle,
}) => {
  return (
    <header className="report-header" role="banner">
      <div className="report-header-top">
        <div className="report-brand">
          <div className="report-brand-mark">QPE</div>
          <div className="report-brand-text">
            <span className="brand-name">QUANTITATIVE PORTFOLIO ENGINE</span>
            <span className="brand-sub">Institutional Analytics &amp; Risk Research</span>
          </div>
        </div>

        <div className="report-doc-meta">
          <div className="doc-meta-item">
            <span className="meta-label">REPORT TYPE</span>
            <span className="meta-value uppercase">{envelope.report_type.replace('_', ' ')}</span>
          </div>
          <div className="doc-meta-item">
            <span className="meta-label">GENERATED</span>
            <span className="meta-value font-mono">{formatDate(envelope.generated_at, true)}</span>
          </div>
          {pageNumber && totalPages && (
            <div className="doc-meta-item page-counter">
              <span className="meta-label">PAGE</span>
              <span className="meta-value font-mono">
                {pageNumber} / {totalPages}
              </span>
            </div>
          )}
        </div>
      </div>

      <div className="report-title-bar">
        <div className="title-left">
          <h1 className="report-main-title">{envelope.report_title}</h1>
          {subtitle && <div className="report-subtitle">{subtitle}</div>}
        </div>
        <div className="title-right">
          <div className="report-pill">
            <span className="pill-label">Period:</span>
            <span className="pill-value font-mono">
              {envelope.reporting_start_date} → {envelope.reporting_end_date}
            </span>
          </div>
          <div className="report-pill">
            <span className="pill-label">Currency:</span>
            <span className="pill-value font-mono font-bold">{envelope.base_currency}</span>
          </div>
        </div>
      </div>

      {/* Mandate & Parameters Summary Bar if provided */}
      {mandate && (
        <div className="report-mandate-bar">
          <div className="mandate-col">
            <span className="mandate-label">Strategy Type:</span>
            <span className="mandate-val">{mandate.strategy_type.replace(/_/g, ' ')}</span>
          </div>
          <div className="mandate-col">
            <span className="mandate-label">Objective:</span>
            <span className="mandate-val">{mandate.optimization_objective || 'Max Sharpe'}</span>
          </div>
          <div className="mandate-col">
            <span className="mandate-label">Rebalance:</span>
            <span className="mandate-val capitalize">{mandate.rebalance_frequency}</span>
          </div>
          <div className="mandate-col">
            <span className="mandate-label">Initial Capital:</span>
            <span className="mandate-val font-mono">
              {formatCurrency(mandate.initial_capital, envelope.base_currency)}
            </span>
          </div>
          <div className="mandate-col">
            <span className="mandate-label">Risk-Free Rate:</span>
            <span className="mandate-val font-mono">{formatPercent(mandate.risk_free_rate, 2)}</span>
          </div>
        </div>
      )}
    </header>
  );
};

interface ReportWarningsBannerProps {
  warnings: ReportWarning[];
}

export const ReportWarningsBanner: React.FC<ReportWarningsBannerProps> = ({ warnings }) => {
  if (!warnings || warnings.length === 0) return null;

  return (
    <div className="report-warnings-container" role="region" aria-label="Report Disclosures & Warnings">
      <div className="report-warnings-header">
        <span className="warning-icon">⚠</span>
        <span className="warning-title">Material Disclosures &amp; Dataset Constraints ({warnings.length})</span>
      </div>
      <div className="report-warnings-list">
        {warnings.map((w, idx) => (
          <div key={idx} className={`report-warning-item ${w.severity}`}>
            <span className="warning-code font-mono">[{w.code}]</span>
            <span className="warning-msg">{w.message}</span>
            {w.affected_metric && (
              <span className="warning-affected font-mono">({w.affected_metric})</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

interface ReportProvenanceFooterProps {
  envelope: CommonReportEnvelope;
}

export const ReportProvenanceFooter: React.FC<ReportProvenanceFooterProps> = ({ envelope }) => {
  const isSnapshotCertified = Boolean(envelope.snapshot_id);

  return (
    <footer className="report-footer" role="contentinfo">
      <div className="provenance-grid">
        <div className="prov-col">
          <span className="prov-label">Dataset Provenance:</span>
          <span className="prov-val font-mono">{envelope.dataset_id}</span>
          {envelope.dataset_filename && (
            <span className="prov-sub font-mono">({envelope.dataset_filename})</span>
          )}
        </div>
        <div className="prov-col">
          <span className="prov-label">Cryptographic Lineage:</span>
          {isSnapshotCertified ? (
            <>
              <span className="prov-val certified">
                ✓ Certified Snapshot: <span className="font-mono">{envelope.snapshot_id}</span>
              </span>
              {envelope.snapshot_manifest_digest && (
                <span className="prov-digest font-mono">
                  SHA-256: {envelope.snapshot_manifest_digest.substring(0, 16)}...
                </span>
              )}
            </>
          ) : (
            <span className="prov-val uncertified">Operational Mutable Data (Unfrozen Simulation)</span>
          )}
        </div>
        <div className="prov-col">
          <span className="prov-label">Audit Lineage:</span>
          <span className="prov-val font-mono">
            Backtest ID: {envelope.source_backtest_id || 'N/A'}
          </span>
          <span className="prov-sub font-mono">Calc Engine v{envelope.calculation_version}</span>
        </div>
      </div>

      <div className="report-disclaimer">
        <strong>REGULATORY DISCLAIMER: </strong>
        {envelope.regulatory_disclaimer}
      </div>
    </footer>
  );
};
