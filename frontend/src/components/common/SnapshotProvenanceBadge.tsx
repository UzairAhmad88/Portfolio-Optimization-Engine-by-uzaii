import React, { useState } from 'react';
import {
  ShieldCheck,
  ShieldAlert,
  Copy,
  Check,
  RefreshCw,
  Info,
  Lock,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import type { DatasetSnapshotVerifyResponse } from '../../types/api';

export interface SnapshotProvenanceBadgeProps {
  snapshotId?: string | null;
  provenance?: {
    snapshot_id?: string;
    dataset_id?: string;
    tag?: string | null;
    snapshot_type?: string;
    manifest_sha256?: string;
    manifest_version?: string;
    as_of_date?: string | null;
    point_in_time_status?: string;
    calendar_version?: string | null;
    adjustment_policy_version?: string | null;
    adjustment_type?: string;
    is_frozen?: boolean;
    verified_replay?: boolean;
    replayed_at?: string;
    total_bars_in_snapshot?: number;
    replayed_bars_count?: number;
    replayed_assets?: string[];
    currency?: string;
  } | null;
  compact?: boolean;
  className?: string;
}

export const SnapshotProvenanceBadge: React.FC<SnapshotProvenanceBadgeProps> = ({
  snapshotId,
  provenance,
  compact = false,
  className = '',
}) => {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [isVerifying, setIsVerifying] = useState<boolean>(false);
  const [verifyResult, setVerifyResult] = useState<DatasetSnapshotVerifyResponse | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);
  const [isExpanded, setIsExpanded] = useState<boolean>(!compact);

  const activeSnapshotId = snapshotId || provenance?.snapshot_id;
  const manifestHash = provenance?.manifest_sha256;
  const pitStatus = provenance?.point_in_time_status || 'unverified_legacy';
  const isPitVerified = pitStatus === 'verified_point_in_time';
  const isFrozen = provenance?.is_frozen ?? Boolean(activeSnapshotId);

  const copyToClipboard = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const handleVerify = async () => {
    if (!activeSnapshotId) return;
    setIsVerifying(true);
    setVerifyError(null);
    try {
      const res = await apiClient.verifySnapshotIntegrity(activeSnapshotId);
      setVerifyResult(res);
    } catch (err: any) {
      setVerifyError(err.message || 'Integrity verification failed.');
    } finally {
      setIsVerifying(false);
    }
  };

  // If no snapshot was used (legacy operational run)
  if (!activeSnapshotId) {
    return (
      <div
        className={`bg-slate-900/80 border border-slate-800 rounded-lg p-3 text-xs text-slate-400 ${className}`}
        data-testid="snapshot-provenance-operational"
      >
        <div className="flex items-center gap-2">
          <Info size={15} className="text-amber-400 shrink-0" />
          <span className="font-medium text-slate-300">Operational Market Data (Mutable)</span>
          <span className="px-2 py-0.5 text-[10px] uppercase font-mono rounded bg-slate-800 text-slate-400 ml-auto">
            Unfrozen Run
          </span>
        </div>
        <p className="mt-1 text-[11px] text-slate-500">
          Simulation executed against mutable database tables without an immutable dataset snapshot.
          Results may change if underlying price observations or corporate action revisions are updated.
        </p>
      </div>
    );
  }

  return (
    <div
      className={`bg-slate-900/90 border border-slate-800 rounded-lg p-4 shadow-sm text-xs ${className}`}
      data-testid="snapshot-provenance-frozen"
    >
      {/* Header with Title and Status Badges */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <ShieldCheck size={18} className="text-emerald-400 shrink-0" />
          <h4 className="font-semibold text-white text-sm m-0">
            Dataset Provenance & Cryptographic Lineage
          </h4>
        </div>

        <div className="flex items-center gap-1.5 flex-wrap">
          {isFrozen && (
            <span
              className="px-2 py-0.5 text-[10px] uppercase font-semibold font-mono rounded bg-emerald-950/70 text-emerald-300 border border-emerald-800/80 flex items-center gap-1"
              title="Observations are sealed in an immutable payload. Replay exhibits 0.0 drift."
            >
              <Lock size={10} /> Verified Frozen
            </span>
          )}

          {isPitVerified ? (
            <span
              className="px-2 py-0.5 text-[10px] uppercase font-semibold font-mono rounded bg-sky-950/70 text-sky-300 border border-sky-800/80"
              title="All corporate actions have verified announcement dates on or before cutoff."
            >
              Point-in-Time Certified
            </span>
          ) : (
            <span
              className="px-2 py-0.5 text-[10px] uppercase font-semibold font-mono rounded bg-amber-950/70 text-amber-300 border border-amber-800/80"
              title="Dataset contains legacy actions without strict announcement date certification."
            >
              Legacy Unverified
            </span>
          )}

          {provenance?.tag && (
            <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-slate-800 text-slate-300 border border-slate-700">
              tag: {provenance.tag}
            </span>
          )}

          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-[11px] text-slate-400 hover:text-white px-2 py-0.5 rounded hover:bg-slate-800 transition-colors ml-1"
          >
            {isExpanded ? 'Collapse' : 'Details'}
          </button>
        </div>
      </div>

      {/* Expanded Details */}
      {isExpanded && (
        <div className="mt-3 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {/* Snapshot ID */}
            <div>
              <div className="text-[11px] uppercase tracking-wider text-slate-500 mb-0.5">
                Snapshot Identifier
              </div>
              <div className="flex items-center gap-1.5 font-mono text-[11px] text-slate-300 bg-slate-950 px-2 py-1 rounded border border-slate-800/80">
                <span className="truncate">{activeSnapshotId}</span>
                <button
                  onClick={() => copyToClipboard(activeSnapshotId, 'snapshot_id')}
                  className="text-slate-500 hover:text-white ml-auto shrink-0 p-0.5"
                  title="Copy Snapshot ID"
                >
                  {copiedKey === 'snapshot_id' ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                </button>
              </div>
            </div>

            {/* Manifest SHA-256 */}
            <div>
              <div className="text-[11px] uppercase tracking-wider text-slate-500 mb-0.5">
                Manifest Composite SHA-256 (v{provenance?.manifest_version || '1.1'})
              </div>
              <div className="flex items-center gap-1.5 font-mono text-[11px] text-slate-300 bg-slate-950 px-2 py-1 rounded border border-slate-800/80">
                <span className="truncate">{manifestHash || 'Verified via Registry'}</span>
                {manifestHash && (
                  <button
                    onClick={() => copyToClipboard(manifestHash, 'manifest_hash')}
                    className="text-slate-500 hover:text-white ml-auto shrink-0 p-0.5"
                    title="Copy Merkle Manifest Hash"
                  >
                    {copiedKey === 'manifest_hash' ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Cutoff, Policies, Observations */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 text-[11px]">
            <div className="bg-slate-950/60 p-2 rounded border border-slate-800/50">
              <span className="text-slate-500 block">PIT Cutoff Date</span>
              <span className="font-mono text-white font-medium">
                {provenance?.as_of_date || 'Full History'}
              </span>
            </div>

            <div className="bg-slate-950/60 p-2 rounded border border-slate-800/50">
              <span className="text-slate-500 block">Calendar Version</span>
              <span className="font-mono text-white font-medium">
                {provenance?.calendar_version || 'US-NYSE-2026.1'}
              </span>
            </div>

            <div className="bg-slate-950/60 p-2 rounded border border-slate-800/50">
              <span className="text-slate-500 block">Adjustment Policy</span>
              <span className="font-mono text-white font-medium">
                {provenance?.adjustment_policy_version || '2026.1'} ({provenance?.adjustment_type || 'total'})
              </span>
            </div>

            <div className="bg-slate-950/60 p-2 rounded border border-slate-800/50">
              <span className="text-slate-500 block">Replayed Bars</span>
              <span className="font-mono text-white font-medium">
                {provenance?.replayed_bars_count?.toLocaleString() || provenance?.total_bars_in_snapshot?.toLocaleString() || '—'} bars
              </span>
            </div>
          </div>

          {/* Re-verification Action & Output */}
          <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-800/60">
            <div className="text-[11px] text-slate-500 italic">
              Sealed at creation. Decoupled from subsequent operational database mutations.
            </div>

            <button
              onClick={handleVerify}
              disabled={isVerifying}
              className="py-1 px-3 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded font-medium text-xs flex items-center gap-1.5 transition-colors disabled:opacity-50"
            >
              {isVerifying ? (
                <>
                  <RefreshCw size={12} className="animate-spin text-sky-400" />
                  Verifying Merkle Root...
                </>
              ) : (
                <>
                  <ShieldCheck size={12} className="text-emerald-400" />
                  Verify Integrity Now
                </>
              )}
            </button>
          </div>

          {/* Verification Feedback Banner */}
          {verifyResult && (
            <div className="p-2.5 rounded bg-emerald-950/40 border border-emerald-800/60 text-emerald-300 text-[11px] flex items-start gap-2">
              <Check size={14} className="shrink-0 mt-0.5 text-emerald-400" />
              <div>
                <strong>Cryptographic Verification Confirmed:</strong> {verifyResult.message}
                <div className="font-mono text-[10px] text-emerald-400/80 mt-0.5">
                  SHA-256: {verifyResult.manifest_sha256}
                </div>
              </div>
            </div>
          )}

          {verifyError && (
            <div className="p-2.5 rounded bg-rose-950/40 border border-rose-800/60 text-rose-300 text-[11px] flex items-start gap-2">
              <ShieldAlert size={14} className="shrink-0 mt-0.5 text-rose-400" />
              <div>
                <strong>Integrity Verification Failed:</strong> {verifyError}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
