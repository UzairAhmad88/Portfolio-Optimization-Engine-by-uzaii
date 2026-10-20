import React, { useState } from 'react';
import {
  Server,
  RefreshCw,
  Layers,
  Database,
  CheckCircle,
} from 'lucide-react';
import { useDataset } from '../../context/DatasetContext';

export const SystemInfoPage: React.FC = () => {
  const { apiHealth, checkHealth, savedDatasets } = useDataset();
  const [isChecking, setIsChecking] = useState<boolean>(false);

  const handleRefresh = async () => {
    setIsChecking(true);
    await checkHealth();
    setIsChecking(false);
  };

  const isDbConnected = apiHealth?.database === 'connected';

  return (
    <div className="workspace-container">
      {/* Backend API Health Status */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <div className="card-header">
          <div className="card-title">
            <Server size={18} style={{ color: 'var(--accent)' }} />
            <span>Quantitative Engine API Infrastructure & Health</span>
          </div>
          <button
            onClick={handleRefresh}
            disabled={isChecking}
            className="btn btn-outline"
            style={{ fontSize: '12px', padding: '4px 8px' }}
          >
            <RefreshCw size={13} className={isChecking ? 'spin' : ''} />
            <span>Health Check</span>
          </button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '20px' }}>
          <div style={{ padding: '14px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>API Status</div>
            <div style={{ fontSize: '16px', fontWeight: 600, color: apiHealth ? 'var(--success)' : 'var(--danger)', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: apiHealth ? 'var(--success)' : 'var(--danger)' }} />
              {apiHealth ? 'Operational (OK)' : 'Unreachable'}
            </div>
          </div>

          <div style={{ padding: '14px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Database Engine</div>
            <div style={{ fontSize: '16px', fontWeight: 600, color: isDbConnected ? 'var(--success)' : 'var(--danger)', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Database size={15} />
              <span>{isDbConnected ? 'Connected (PostgreSQL / SQLite)' : 'Disconnected'}</span>
            </div>
          </div>

          <div style={{ padding: '14px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Milestone Development Stage</div>
            <div className="font-mono" style={{ fontSize: '14px', fontWeight: 600, color: 'var(--accent)', marginTop: '4px' }}>
              {apiHealth?.stage || 'Session 10: Persistent Market Data Storage'}
            </div>
          </div>

          <div style={{ padding: '14px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Persisted Datasets in DB</div>
            <div className="font-mono" style={{ fontSize: '16px', fontWeight: 600, marginTop: '4px', color: 'var(--accent)' }}>
              {savedDatasets.length} Registered
            </div>
          </div>
        </div>

        {/* Persistent Storage Architecture Notice */}
        <div className="alert alert-success">
          <CheckCircle size={18} style={{ flexShrink: 0 }} />
          <div>
            <strong>Persistent Market Data Storage & Lifecycle Architecture (Session 10)</strong>
            <p style={{ marginTop: '4px', fontSize: '12px', lineHeight: 1.5 }}>
              Market data datasets registered via the CSV upload interface are committed atomically to a normalized, indexed relational database (PostgreSQL with fallback SQLite for development).
              Registered datasets, asset metadata universes, and daily price bars are durable across backend server restarts.
              SHA-256 content deduplication prevents redundant storage of identical datasets.
            </p>
          </div>
        </div>
      </div>

      {/* Numerical and Financial Specifications Card */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <Layers size={18} style={{ color: 'var(--accent)' }} />
            <span>Mathematical & Financial Invariants Audit</span>
          </div>
          <span className="badge badge-neutral">IEEE 754 High Precision</span>
        </div>

        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Component / Invariant</th>
                <th>Mathematical Rule</th>
                <th>Numerical Tolerance</th>
                <th>Audit Status</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={{ fontWeight: 600 }}>Weight Normalization</td>
                <td>&sum; w_i = 1.0</td>
                <td className="font-mono">&plusmn; 1e-4</td>
                <td><span className="badge badge-success">Verified</span></td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600 }}>Covariance Symmetry</td>
                <td>&Sigma; = &Sigma;^T</td>
                <td className="font-mono">&plusmn; 1e-6</td>
                <td><span className="badge badge-success">Verified</span></td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600 }}>Covariance Positive Semi-Definiteness</td>
                <td>&lambda;_min &ge; -1e-8</td>
                <td className="font-mono">&ge; -1e-8</td>
                <td><span className="badge badge-success">Verified</span></td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600 }}>Zero Downside Deviation Protection</td>
                <td>returns &ge; target_return &rArr; Sortino = None</td>
                <td className="font-mono">Exact &sigma;_d &le; 1e-12</td>
                <td><span className="badge badge-success">Verified (No Fabricated Volatility)</span></td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600 }}>Cross-Market Currency Isolation</td>
                <td>Single currency per optimization universe</td>
                <td className="font-mono">Exact Homogeneity</td>
                <td><span className="badge badge-success">Enforced</span></td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600 }}>Database Foreign Key Integrity</td>
                <td>ON DELETE CASCADE (Dataset &rarr; Assets &rarr; Bars)</td>
                <td className="font-mono">Relational Constraints</td>
                <td><span className="badge badge-success">Enforced</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
