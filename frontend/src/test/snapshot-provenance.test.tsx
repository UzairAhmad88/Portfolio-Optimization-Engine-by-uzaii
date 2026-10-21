import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { SnapshotProvenanceBadge } from '../components/common/SnapshotProvenanceBadge';
import { apiClient } from '../api/client';

describe('SnapshotProvenanceBadge Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders operational mutable data badge when no snapshot ID or provenance is provided', () => {
    render(<SnapshotProvenanceBadge snapshotId={null} provenance={null} />);
    expect(screen.getByText('Operational Market Data (Mutable)')).toBeInTheDocument();
    expect(
      screen.getByText(/Simulation executed against mutable database tables/i)
    ).toBeInTheDocument();
    expect(screen.getByText('Unfrozen Run')).toBeInTheDocument();
  });

  it('renders frozen snapshot provenance details when snapshot is provided', () => {
    const mockProvenance = {
      snapshot_id: 'snap-12345678-abcd-ef01-2345-6789abcdef01',
      dataset_id: 'ds-sample-1',
      tag: 'v2024-Q1-prod',
      manifest_sha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
      manifest_version: '1.1',
      as_of_date: '2024-03-31',
      point_in_time_status: 'verified_point_in_time',
      calendar_version: 'NYSE_v2024_1',
      adjustment_policy_version: 'adj_split_div_v1',
      is_frozen: true,
      verified_replay: true,
      replayed_bars_count: 1000,
    };

    render(
      <SnapshotProvenanceBadge
        snapshotId={mockProvenance.snapshot_id}
        provenance={mockProvenance}
        compact={false}
      />
    );

    expect(screen.getByText('Dataset Provenance & Cryptographic Lineage')).toBeInTheDocument();
    expect(screen.getByText(/Verified Frozen/)).toBeInTheDocument();
    expect(screen.getByText('Point-in-Time Certified')).toBeInTheDocument();
    expect(screen.getByText('tag: v2024-Q1-prod')).toBeInTheDocument();
    expect(screen.getByText('snap-12345678-abcd-ef01-2345-6789abcdef01')).toBeInTheDocument();
    expect(screen.getByText('e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855')).toBeInTheDocument();
    expect(screen.getByText('Verify Integrity Now')).toBeInTheDocument();
  });

  it('performs live cryptographic verification when button is clicked', async () => {
    const mockProvenance = {
      snapshot_id: 'snap-live-check-1',
      manifest_sha256: 'fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210',
      is_frozen: true,
    };

    const verifySpy = vi.spyOn(apiClient, 'verifySnapshotIntegrity').mockResolvedValueOnce({
      snapshot_id: 'snap-live-check-1',
      is_verified: true,
      expected_hash: mockProvenance.manifest_sha256,
      computed_hash: mockProvenance.manifest_sha256,
      manifest_sha256: mockProvenance.manifest_sha256,
      message: 'Cryptographic payload digest matches manifest digest exactly.',
      verified_at: '2026-10-21T18:00:00Z',
    });

    render(
      <SnapshotProvenanceBadge
        snapshotId={mockProvenance.snapshot_id}
        provenance={mockProvenance}
        compact={false}
      />
    );

    const verifyBtn = screen.getByText('Verify Integrity Now');
    fireEvent.click(verifyBtn);

    expect(verifySpy).toHaveBeenCalledWith('snap-live-check-1');

    await waitFor(() => {
      expect(screen.getByText(/Cryptographic Verification Confirmed:/)).toBeInTheDocument();
      expect(
        screen.getByText(/Cryptographic payload digest matches manifest digest exactly./)
      ).toBeInTheDocument();
    });
  });

  it('displays error state if cryptographic integrity check fails', async () => {
    const mockProvenance = {
      snapshot_id: 'snap-tampered-1',
      manifest_sha256: '1111111111111111111111111111111111111111111111111111111111111111',
      is_frozen: true,
    };

    vi.spyOn(apiClient, 'verifySnapshotIntegrity').mockRejectedValueOnce(
      new Error('Payload digest mismatch! Expected hash does not equal computed hash.')
    );

    render(
      <SnapshotProvenanceBadge
        snapshotId={mockProvenance.snapshot_id}
        provenance={mockProvenance}
        compact={false}
      />
    );

    const verifyBtn = screen.getByText('Verify Integrity Now');
    fireEvent.click(verifyBtn);

    await waitFor(() => {
      expect(screen.getByText(/Integrity Verification Failed:/)).toBeInTheDocument();
      expect(
        screen.getByText(/Payload digest mismatch! Expected hash does not equal computed hash./)
      ).toBeInTheDocument();
    });
  });

  it('copies full hash to clipboard when copy button is clicked', async () => {
    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: {
        writeText: writeTextMock,
      },
    });

    const mockProvenance = {
      snapshot_id: 'snap-copy-test',
      manifest_sha256: 'abcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdef',
      is_frozen: true,
    };

    render(
      <SnapshotProvenanceBadge
        snapshotId={mockProvenance.snapshot_id}
        provenance={mockProvenance}
        compact={false}
      />
    );

    const copyBtn = screen.getByTitle('Copy Merkle Manifest Hash');
    fireEvent.click(copyBtn);

    expect(writeTextMock).toHaveBeenCalledWith(
      'abcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdef'
    );
  });
});
