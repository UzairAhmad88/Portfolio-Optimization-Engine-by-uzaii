import React from 'react';
import { Menu, Database, Activity, AlertCircle, User as UserIcon, LogOut } from 'lucide-react';
import { useDataset } from '../../context/DatasetContext';
import { useAuth } from '../../context/AuthContext';
import type { NavItem } from './Sidebar';

interface HeaderProps {
  currentNav: NavItem;
  onNavigate: (item: NavItem) => void;
  onToggleSidebar: () => void;
}

const pageTitles: Record<NavItem, { title: string; subtitle: string }> = {
  overview: {
    title: 'Research Workspace Overview',
    subtitle: 'System state, registered dataset telemetry, and quantitative research workflows.',
  },
  'market-data': {
    title: 'Market Data Ingestion & Registry',
    subtitle: 'Upload, preview, validate, and query CSV historical market prices.',
  },
  'portfolio-setup': {
    title: 'Portfolio Universe & Constraints',
    subtitle: 'Configure asset universe, long/short limits, exposure caps, and mathematically validate.',
  },
  optimization: {
    title: 'Portfolio Optimization Engine',
    subtitle: 'Solve constrained mean-variance, maximum Sharpe, and benchmark allocations via SLSQP.',
  },
  'efficient-frontier': {
    title: 'Markowitz Efficient Frontier',
    subtitle: 'Generate and inspect the continuous risk-return frontier and GMV anchor.',
  },
  'risk-analytics': {
    title: 'Comprehensive Risk Tear-Sheet',
    subtitle: 'Examine annualized volatility, maximum drawdowns, Sharpe, and Sortino ratios.',
  },
  comparison: {
    title: 'Comparative Portfolio Analysis',
    subtitle: 'Cross-examine GMV, Max Sharpe, Equal Weight, and custom allocations side-by-side.',
  },
  backtesting: {
    title: 'Walk-Forward Backtesting Engine',
    subtitle: 'Simulate out-of-sample portfolio wealth compounding with rebalancing, basis-point transaction costs, and slippage.',
  },
  'scenario-analysis': {
    title: 'Scenario Analysis & Stress Testing',
    subtitle: 'Simulate instantaneous price shocks, historical crisis replays, covariance stress, and parametric sensitivity.',
  },
  'monte-carlo': {
    title: 'Monte Carlo Risk Analysis & Probabilistic Simulation',
    subtitle: 'Simulate multi-period portfolio wealth paths, estimate empirical VaR & CVaR, and evaluate terminal distribution quantiles.',
  },
  performance: {
    title: 'Performance Attribution & Benchmark Analysis',
    subtitle: 'Evaluate active returns, tracking error, Information Ratio, Beta, Jensen Alpha, and Menchero asset contributions.',
  },
  'research-lab': {
    title: 'Portfolio Research Lab & Strategy Comparison',
    subtitle: 'Define hypotheses, execute reproducible runs, audit configuration provenance, and cross-examine multi-strategy outcomes.',
  },
  'robust-optimization': {
    title: 'Robust Portfolio Optimization & Estimation Uncertainty',
    subtitle: 'Evaluate worst-case expected returns, regularized covariance shrinkage, constraint sensitivity, and out-of-sample stability.',
  },
  'black-litterman': {
    title: 'Black-Litterman Bayesian Portfolio Optimization',
    subtitle: 'Derive market implied equilibrium returns, formulate analyst views, calculate posterior distributions, and backtest active tilts.',
  },
  'risk-parity': {
    title: 'Equal Risk Contribution & Hierarchical Risk Parity',
    subtitle: 'Construct robust, inverse-risk-weighted and cluster-diversified portfolios immune to covariance inversion instabilities.',
  },
  'factor-investing': {
    title: 'Multi-Factor Risk Modeling & Systematic Attribution',
    subtitle: 'Barra structural risk decomposition, Fama-French & Carhart exposures, systematic vs specific variance, and factor-tilted optimization.',
  },
  'multi-asset': {
    title: 'Multi-Asset Class Allocation & FX Hedging',
    subtitle: 'Hierarchical asset class allocation bounds, cash drag & yield modeling, and multi-currency FX risk decomposition.',
  },
  execution: {
    title: 'Optimal Execution & Market Impact Modeling',
    subtitle: 'Almgren-Chriss optimal trade trajectories, TWAP/VWAP scheduling, and portfolio rebalance non-linear Square-Root Law market impact.',
  },
  'regime-switching': {
    title: 'Regime-Switching Asset Allocation & Volatility Targeting',
    subtitle: 'Gaussian Hidden Markov Models (HMM), causal forward-filtered regime detection, covariance blending, and dynamic volatility targeting.',
  },
  'brinson-attribution': {
    title: 'Performance Attribution & Factor Risk Decomposition',
    subtitle: 'Brinson-Fachler arithmetic decomposition, Cariño logarithmic multi-period linking, and systematic multi-factor active risk/return attribution.',
  },
  'copula-tail-risk': {
    title: 'Copula-Based Tail Dependency & Tail Risk Parity',
    subtitle: 'Archimedean & elliptical copulas (Clayton, Gumbel, Student-t, Gaussian), asymmetric lower-tail crash risk, and Tail Risk Parity allocation.',
  },
  'system-info': {
    title: 'System Health & Registry Architecture',
    subtitle: 'Inspect backend health, stage milestones, memory lifecycle, and assumptions.',
  },
  reports: {
    title: 'Institutional Reports & PDF Export',
    subtitle: 'Publication-ready strategy tear sheets, allocator fact sheets, and institutional PDF dossiers.',
  },
};

export const Header: React.FC<HeaderProps> = ({ currentNav, onNavigate, onToggleSidebar }) => {
  const { currentDataset, apiHealth } = useDataset();
  const { user, logout } = useAuth();
  const info = pageTitles[currentNav] || { title: 'Quantitative Workspace', subtitle: '' };

  return (
    <header className="header">
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <button
          onClick={onToggleSidebar}
          className="btn btn-outline"
          style={{ padding: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          aria-label="Toggle navigation menu"
        >
          <Menu size={18} />
        </button>

        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Workspace / {currentNav.replace('-', ' ')}
            </span>
          </div>
          <h1 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.2 }}>
            {info.title}
          </h1>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        {/* Active Dataset Context Badge */}
        {currentDataset ? (
          <div
            onClick={() => onNavigate('market-data')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '4px 10px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--bg-elevated)',
              border: '1px solid var(--border-medium)',
              cursor: 'pointer',
              fontSize: '12px',
            }}
            title={`Dataset ID: ${currentDataset.dataset_id} (${currentDataset.valid_rows} valid rows)`}
          >
            <Database size={13} style={{ color: 'var(--accent)' }} />
            <span style={{ color: 'var(--text-muted)' }}>Dataset:</span>
            <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{currentDataset.filename}</span>
            <span className="badge badge-info" style={{ fontSize: '10px' }}>
              {currentDataset.valid_rows.toLocaleString()} bars
            </span>
          </div>
        ) : (
          <button
            onClick={() => onNavigate('market-data')}
            className="btn btn-outline"
            style={{ fontSize: '12px', padding: '4px 10px' }}
          >
            <Database size={13} />
            <span>Select / Upload Dataset</span>
          </button>
        )}

        {/* Backend API Connection Indicator */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '12px',
            padding: '4px 8px',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'var(--bg-input)',
            border: '1px solid var(--border-subtle)',
          }}
          title={apiHealth ? `Backend stage: ${apiHealth.stage}` : 'API offline or unreachable'}
        >
          {apiHealth ? (
            <>
              <Activity size={13} style={{ color: 'var(--success)' }} />
              <span style={{ color: 'var(--text-secondary)' }}>API:</span>
              <span style={{ color: 'var(--success)', fontWeight: 600 }}>Active</span>
            </>
          ) : (
            <>
              <AlertCircle size={13} style={{ color: 'var(--danger)' }} />
              <span style={{ color: 'var(--danger)', fontWeight: 600 }}>Disconnected</span>
            </>
          )}
        </div>

        {/* Authenticated User Identity & Role Badge */}
        {user && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              padding: '4px 10px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--bg-elevated)',
              border: '1px solid var(--border-medium)',
              fontSize: '12px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <UserIcon size={13} style={{ color: 'var(--accent)' }} />
              <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                {user.full_name || user.email?.split('@')[0] || 'Researcher'}
              </span>
              <span
                className="badge"
                style={{
                  fontSize: '9px',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  backgroundColor: user.role === 'admin' ? 'rgba(234, 179, 8, 0.15)' : 'rgba(56, 189, 248, 0.15)',
                  color: user.role === 'admin' ? '#eab308' : '#38bdf8',
                  border: user.role === 'admin' ? '1px solid rgba(234, 179, 8, 0.3)' : '1px solid rgba(56, 189, 248, 0.3)',
                }}
              >
                {user.role}
              </span>
            </div>

            <button
              onClick={() => logout()}
              className="btn btn-outline"
              style={{
                padding: '2px 8px',
                fontSize: '11px',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                color: 'var(--text-muted)',
              }}
              title="Sign out of research workspace"
              aria-label="Sign out"
              id="header-logout-btn"
            >
              <LogOut size={12} />
              <span>Sign Out</span>
            </button>
          </div>
        )}
      </div>
    </header>
  );
};
