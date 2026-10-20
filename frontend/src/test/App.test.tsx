import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import App from '../App';

describe('Quant Research Dashboard UI Shell', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url: any) => {
      const urlStr = String(url);
      if (urlStr.includes('/auth/me')) {
        return {
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({
            id: 'test-user-id',
            email: 'researcher@firm.com',
            full_name: 'Dr. Researcher',
            role: 'researcher',
            is_active: true,
            created_at: '2026-01-01T00:00:00Z',
          }),
        } as Response;
      }
      if (urlStr.includes('/health')) {
        return {
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ status: 'ok', stage: 'secure-access-control' }),
        } as Response;
      }
      if (urlStr.includes('/market-data/datasets')) {
        return {
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => [],
        } as Response;
      }
      if (urlStr.includes('/backtests')) {
        return {
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => [],
        } as Response;
      }
      if (urlStr.includes('/scenarios')) {
        return {
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => [],
        } as Response;
      }
      if (urlStr.includes('/risk-simulations')) {
        return {
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => [],
        } as Response;
      }
      if (urlStr.includes('/performance/reports')) {
        return {
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => [],
        } as Response;
      }
      if (urlStr.includes('/research/experiments')) {
        return {
          ok: true,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => [],
        } as Response;
      }
      return {
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({}),
      } as Response;
    });
  });

  it('renders application brand, header, and research workspaces sidebar for authenticated user', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Quant Engine')).toBeInTheDocument();
    });

    expect(screen.getByText('Institutional Research')).toBeInTheDocument();
    expect(screen.getByText('Research Workspace Overview')).toBeInTheDocument();
    expect(screen.getByText('Dr. Researcher')).toBeInTheDocument();
    expect(screen.getByText('researcher')).toBeInTheDocument();

    expect(screen.getByRole('button', { name: /^Market Data$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Portfolio Definition$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Optimization$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Efficient Frontier$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Risk Analytics$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Portfolio Comparison$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Backtesting$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Scenario & Stress$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Monte Carlo Risk$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Attribution & Benchmarks$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Research Lab$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Robust Optimization$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Black-Litterman$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Risk Parity & HRP$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Factor Investing$/i })).toBeInTheDocument();
  });

  it('switches between workspaces seamlessly via navigation links', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^Market Data$/i })).toBeInTheDocument();
    });

    // Click on Market Data
    const marketDataNav = screen.getByRole('button', { name: /^Market Data$/i });
    fireEvent.click(marketDataNav);

    expect(
      screen.getByText(/CSV Market Data Ingestion & Pre-Registration Validation/i)
    ).toBeInTheDocument();

    // Click on Backtesting
    const backtestingNav = screen.getByRole('button', { name: /^Backtesting$/i });
    fireEvent.click(backtestingNav);

    await waitFor(() => {
      expect(
        screen.getByText(/Historical Simulation & Walk-Forward Backtesting/i)
      ).toBeInTheDocument();
    });

    // Click on Scenario & Stress
    const scenarioNav = screen.getByRole('button', { name: /^Scenario & Stress$/i });
    fireEvent.click(scenarioNav);

    await waitFor(() => {
      expect(
        screen.getByText(/Scenario Analysis & Portfolio Stress Testing/i)
      ).toBeInTheDocument();
    });

    // Click on Monte Carlo Risk
    const monteCarloNav = screen.getByRole('button', { name: /^Monte Carlo Risk$/i });
    fireEvent.click(monteCarloNav);

    await waitFor(() => {
      expect(
        screen.getByText(/Monte Carlo Simulation & Probabilistic Risk Analysis/i)
      ).toBeInTheDocument();
    });

    // Click on Research Lab
    const researchLabNav = screen.getByRole('button', { name: /^Research Lab$/i });
    fireEvent.click(researchLabNav);

    await waitFor(() => {
      expect(
        screen.getByText(/Portfolio Research Lab & Strategy Comparison/i)
      ).toBeInTheDocument();
    });

    // Click on Robust Optimization
    const robustNav = screen.getByRole('button', { name: /^Robust Optimization$/i });
    fireEvent.click(robustNav);

    await waitFor(() => {
      expect(
        screen.getAllByText(/Robust Portfolio Optimization & Estimation Uncertainty/i)[0]
      ).toBeInTheDocument();
    });

    // Click on Black-Litterman
    const blNav = screen.getByRole('button', { name: /^Black-Litterman$/i });
    fireEvent.click(blNav);

    await waitFor(() => {
      expect(
        screen.getAllByText(/Black-Litterman Bayesian Portfolio Optimization/i)[0]
      ).toBeInTheDocument();
    });

    // Click on Risk Parity & HRP
    const riskParityNav = screen.getByRole('button', { name: /^Risk Parity & HRP$/i });
    fireEvent.click(riskParityNav);

    await waitFor(() => {
      expect(
        screen.getAllByText(/Equal Risk Contribution & Hierarchical Risk Parity/i)[0]
      ).toBeInTheDocument();
    });

    // Click on Factor Investing
    const factorNav = screen.getByRole('button', { name: /^Factor Investing$/i });
    fireEvent.click(factorNav);

    await waitFor(() => {
      expect(
        screen.getAllByText(/Multi-Factor Risk Modeling & Systematic Attribution/i)[0]
      ).toBeInTheDocument();
    });

    // Click on Regime Switching & Vol
    const regimeNav = screen.getByRole('button', { name: /^Regime Switching & Vol$/i });
    fireEvent.click(regimeNav);

    await waitFor(() => {
      expect(
        screen.getAllByText(/Regime-Switching & Volatility Targeting/i)[0]
      ).toBeInTheDocument();
    });

    // Click on Brinson & Factor Attribution
    const brinsonNav = screen.getByRole('button', { name: /^Brinson & Factor Attribution$/i });
    fireEvent.click(brinsonNav);

    await waitFor(() => {
      expect(
        screen.getAllByText(/Performance Attribution & Factor Risk Decomposition/i)[0]
      ).toBeInTheDocument();
    });

    // Click on System & Registry
    const systemNav = screen.getByRole('button', { name: /^System & Registry$/i });
    fireEvent.click(systemNav);

    expect(
      screen.getByText(/Quantitative Engine API Infrastructure & Health/i)
    ).toBeInTheDocument();
  }, 25000);

  it('displays API active indicator when health check succeeds', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Active')).toBeInTheDocument();
    });
  });

  it('renders authentication login view when session is unauthenticated', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url: any) => {
      if (String(url).includes('/auth/me')) {
        return {
          ok: false,
          status: 401,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ detail: 'Authentication required' }),
        } as Response;
      }
      return {
        ok: true,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({}),
      } as Response;
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Quant Portfolio Engine')).toBeInTheDocument();
      expect(screen.getByText('Institutional Research & Risk Analytics Platform')).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: 'Enter Research Workspace' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Sign In' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Create Account' })).toBeInTheDocument();

    // Switch to Register Tab
    fireEvent.click(screen.getByRole('tab', { name: 'Create Account' }));
    expect(screen.getByRole('button', { name: 'Register Institutional Account' })).toBeInTheDocument();
  });
});
