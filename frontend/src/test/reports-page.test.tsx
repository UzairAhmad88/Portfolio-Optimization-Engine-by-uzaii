import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { ReportsPage } from '../components/pages/ReportsPage';
import { apiClient } from '../api/client';
import { createMockUnifiedReport } from './reporting-fixtures';
import type { BacktestListItem } from '../types/api';

vi.mock('../api/client', () => ({
  apiClient: {
    listBacktests: vi.fn(),
    getUnifiedInstitutionalReport: vi.fn(),
    exportUnifiedInstitutionalReportPdf: vi.fn(),
  },
}));

describe('ReportsPage (Mockup 11: Reports Library & Mockup 12: PDF Report Preview)', () => {
  const mockBacktests: BacktestListItem[] = [
    {
      id: 'bt-001',
      dataset_id: 'ds-tech',
      name: 'US Tech Momentum Strategy',
      strategy_type: 'walk_forward_optimization',
      rebalance_frequency: 'monthly',
      initial_capital: 100000,
      final_value_net: 125000,
      cumulative_return_net: 0.25,
      cagr_net: 0.25,
      sharpe_ratio_net: 1.45,
      max_drawdown_net: -0.08,
      status: 'completed',
      created_at: '2026-10-24T12:00:00Z',
    },
    {
      id: 'bt-002',
      dataset_id: 'ds-global',
      name: 'Global Equity Low Volatility',
      strategy_type: 'minimum_variance',
      rebalance_frequency: 'quarterly',
      initial_capital: 250000,
      final_value_net: 280000,
      cumulative_return_net: 0.12,
      cagr_net: 0.12,
      sharpe_ratio_net: 1.82,
      max_drawdown_net: -0.04,
      status: 'completed',
      created_at: '2026-10-24T14:30:00Z',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.listBacktests).mockResolvedValue(mockBacktests);
    vi.mocked(apiClient.getUnifiedInstitutionalReport).mockResolvedValue(createMockUnifiedReport());
  });

  it('renders the Reports Library page header, KPI cards, and reports table', async () => {
    render(<ReportsPage />);

    expect(screen.getByRole('heading', { level: 1, name: /reports/i })).toBeInTheDocument();
    expect(screen.getByText(/publication-ready strategy tear sheets/i)).toBeInTheDocument();

    // Verify backtest list was queried
    await waitFor(() => {
      expect(apiClient.listBacktests).toHaveBeenCalled();
    });

    // Check table rows
    expect(await screen.findByText(/US Tech Momentum Strategy - Institutional Dossier/i)).toBeInTheDocument();
    expect(screen.getByText(/Global Equity Low Volatility - Institutional Dossier/i)).toBeInTheDocument();
  });

  it('opens and closes the Generate Report modal dialog', async () => {
    render(<ReportsPage />);

    await waitFor(() => {
      expect(screen.getByText(/US Tech Momentum Strategy - Institutional Dossier/i)).toBeInTheDocument();
    });

    // Click Generate Report button
    const generateBtn = screen.getByRole('button', { name: /generate report/i });
    fireEvent.click(generateBtn);

    // Modal should be open
    expect(screen.getByText(/compile institutional report/i)).toBeInTheDocument();
    expect(screen.getByText(/report dossier format/i)).toBeInTheDocument();

    // Close modal via Cancel button
    const cancelBtn = screen.getByRole('button', { name: /cancel/i });
    fireEvent.click(cancelBtn);

    expect(screen.queryByText(/compile institutional report/i)).not.toBeInTheDocument();
  });

  it('navigates to Report Preview (Mockup 12) when Preview button is clicked', async () => {
    render(<ReportsPage />);

    await waitFor(() => {
      expect(screen.getByText(/US Tech Momentum Strategy - Institutional Dossier/i)).toBeInTheDocument();
    });

    const previewButtons = screen.getAllByRole('button', { name: /preview/i });
    fireEvent.click(previewButtons[0]);

    // Should call getUnifiedInstitutionalReport
    await waitFor(() => {
      expect(apiClient.getUnifiedInstitutionalReport).toHaveBeenCalledWith('bt-001');
    });

    // Should display back button
    expect(await screen.findByRole('button', { name: /back to reports library/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /download pdf/i })).toBeInTheDocument();

    // Clicking back returns to library list
    const backBtn = screen.getByRole('button', { name: /back to reports library/i });
    fireEvent.click(backBtn);

    expect(await screen.findByText(/generated reports library/i)).toBeInTheDocument();
  });

  it('triggers PDF download when Download PDF action is clicked', async () => {
    const mockBlob = new Blob(['%PDF-1.4 test'], { type: 'application/pdf' });
    vi.mocked(apiClient.exportUnifiedInstitutionalReportPdf).mockResolvedValue(mockBlob);

    // Mock URL.createObjectURL and revokeObjectURL
    const createObjectURLSpy = vi.spyOn(window.URL, 'createObjectURL').mockReturnValue('blob:http://localhost/test');
    const revokeObjectURLSpy = vi.spyOn(window.URL, 'revokeObjectURL').mockImplementation(() => {});

    render(<ReportsPage />);

    await waitFor(() => {
      expect(screen.getByText(/US Tech Momentum Strategy - Institutional Dossier/i)).toBeInTheDocument();
    });

    const downloadButtons = screen.getAllByTitle(/download pdf/i);
    fireEvent.click(downloadButtons[0]);

    await waitFor(() => {
      expect(apiClient.exportUnifiedInstitutionalReportPdf).toHaveBeenCalledWith('bt-001');
    });

    expect(createObjectURLSpy).toHaveBeenCalledWith(mockBlob);
    createObjectURLSpy.mockRestore();
    revokeObjectURLSpy.mockRestore();
  });
});
