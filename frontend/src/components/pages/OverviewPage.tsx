import React from 'react';
import {
  Database,
  SlidersHorizontal,
  Target,
  TrendingUp,
  ShieldAlert,
  GitCompare,
  PlayCircle,
  Zap,
  Dice5,
  Award,
  FlaskConical,
  Scale,
  Layers,
  ShieldCheck,
  Cpu,
  Coins,
  Gauge,
  Activity,
  Network,
  ArrowRight,
  Info,
  CheckCircle,
  AlertTriangle,
} from 'lucide-react';
import { useDataset } from '../../context/DatasetContext';
import type { NavItem } from '../layout/Sidebar';

interface OverviewPageProps {
  onNavigate: (item: NavItem) => void;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({ onNavigate }) => {
  const { currentDataset, availableAssets, apiHealth } = useDataset();

  return (
    <div className="workspace-container">
      {/* Welcome Banner */}
      <div
        style={{
          background: 'linear-gradient(180deg, var(--bg-card) 0%, var(--bg-secondary) 100%)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-lg)',
          padding: '24px',
          marginBottom: '24px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '16px',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <span className="badge badge-info">Production Research Engine</span>
            <span className="badge badge-neutral">Stage: {apiHealth?.stage || 'Connecting...'}</span>
          </div>
          <h2 style={{ fontSize: '20px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '6px' }}>
            Quantitative Portfolio Research & Optimization Engine
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '13px', maxWidth: '750px', lineHeight: 1.5 }}>
            Institutional research workspace for market data ingestion, portfolio constraint verification,
            constrained numerical optimization (SLSQP), continuous efficient-frontier modeling, and risk tear-sheet analytics.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button onClick={() => onNavigate('market-data')} className="btn btn-primary">
            <Database size={15} />
            <span>Manage Market Data</span>
          </button>
          <button onClick={() => onNavigate('optimization')} className="btn btn-secondary">
            <Target size={15} />
            <span>Launch Optimizer</span>
          </button>
        </div>
      </div>

      {/* Research Telemetry Grid */}
      <div className="metric-grid">
        <div className="metric-card">
          <div className="metric-label">Active Dataset</div>
          <div className="metric-value" style={{ fontSize: '18px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {currentDataset ? currentDataset.filename : 'None Selected'}
          </div>
          <div className="metric-sub">
            {currentDataset ? (
              <span style={{ color: 'var(--success)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <CheckCircle size={12} /> {currentDataset.valid_rows.toLocaleString()} clean price bars
              </span>
            ) : (
              <span style={{ color: 'var(--warning)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <AlertTriangle size={12} /> Ready for CSV import
              </span>
            )}
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-label">Available Assets</div>
          <div className="metric-value font-mono">
            {availableAssets.length > 0 ? availableAssets.length : '0'}
          </div>
          <div className="metric-sub">
            {availableAssets.length > 0 ? (
              <span>Verified asset universe</span>
            ) : (
              <span>Requires registered dataset</span>
            )}
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-label">Primary Market / Currency</div>
          <div className="metric-value" style={{ fontSize: '18px' }}>
            {availableAssets.length > 0 ? `${availableAssets[0].market} / ${availableAssets[0].currency}` : '—'}
          </div>
          <div className="metric-sub">
            {availableAssets.length > 0 ? (
              <span>Homogeneous currency universe</span>
            ) : (
              <span>Awaiting data registry</span>
            )}
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-label">Engine API Status</div>
          <div className="metric-value" style={{ fontSize: '18px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span
              style={{
                width: '10px',
                height: '10px',
                borderRadius: '50%',
                backgroundColor: apiHealth ? 'var(--success)' : 'var(--danger)',
                display: 'inline-block',
              }}
            />
            {apiHealth ? 'Online & Healthy' : 'Disconnected'}
          </div>
          <div className="metric-sub">
            <span>FastAPI v0.5.0 • Python 3.11</span>
          </div>
        </div>
      </div>

      {/* Guided Research Workflows */}
      <div style={{ marginBottom: '24px' }}>
        <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '14px' }}>
          Quantitative Research Workspaces
        </h3>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px' }}>
          {/* Card 1: Market Data */}
          <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                <div style={{ padding: '8px', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--accent-light)', color: 'var(--accent)' }}>
                  <Database size={18} />
                </div>
                <div style={{ fontWeight: 600, fontSize: '15px' }}>1. Market Data Ingestion</div>
              </div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', lineHeight: 1.5, marginBottom: '16px' }}>
                Upload historical price CSVs with client-side preview, cryptographic SHA-256 verification, strict schema validation, and date-range queries.
              </p>
            </div>
            <button onClick={() => onNavigate('market-data')} className="btn btn-secondary" style={{ width: '100%', justifyContent: 'space-between' }}>
              <span>Open Ingestion Workspace</span>
              <ArrowRight size={14} />
            </button>
          </div>

          {/* Card 2: Portfolio Universe */}
          <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                <div style={{ padding: '8px', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(16, 185, 129, 0.12)', color: 'var(--success)' }}>
                  <SlidersHorizontal size={18} />
                </div>
                <div style={{ fontWeight: 600, fontSize: '15px' }}>2. Portfolio Universe & Constraints</div>
              </div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', lineHeight: 1.5, marginBottom: '16px' }}>
                Select assets, specify box bounds (l_i, u_i), enforce long-only or long-short rules, set gross exposure limits, and test mathematical feasibility.
              </p>
            </div>
            <button onClick={() => onNavigate('portfolio-setup')} className="btn btn-secondary" style={{ width: '100%', justifyContent: 'space-between' }}>
              <span>Configure Universe & Bounds</span>
              <ArrowRight size={14} />
            </button>
          </div>

          {/* Card 3: Optimization */}
          <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                <div style={{ padding: '8px', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(245, 158, 11, 0.12)', color: 'var(--warning)' }}>
                  <Target size={18} />
                </div>
                <div style={{ fontWeight: 600, fontSize: '15px' }}>3. Numerical Optimization Engine</div>
              </div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', lineHeight: 1.5, marginBottom: '16px' }}>
                Solve constrained mean-variance quadratic programs using SciPy SLSQP. Compute minimum-variance, maximum Sharpe, or benchmark allocations.
              </p>
            </div>
            <button onClick={() => onNavigate('optimization')} className="btn btn-secondary" style={{ width: '100%', justifyContent: 'space-between' }}>
              <span>Execute Solver</span>
              <ArrowRight size={14} />
            </button>
          </div>

          {/* Card 4: Efficient Frontier */}
          <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                <div style={{ padding: '8px', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(99, 102, 241, 0.12)', color: '#818CF8' }}>
                  <TrendingUp size={18} />
                </div>
                <div style={{ fontWeight: 600, fontSize: '15px' }}>4. Efficient Frontier Spectrum</div>
              </div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', lineHeight: 1.5, marginBottom: '16px' }}>
                Generate continuous Markowitz frontier curves. Analyze target return solutions, distinguish efficient from dominated portfolios, and locate GMV.
              </p>
            </div>
            <button onClick={() => onNavigate('efficient-frontier')} className="btn btn-secondary" style={{ width: '100%', justifyContent: 'space-between' }}>
              <span>Plot Efficient Frontier</span>
              <ArrowRight size={14} />
            </button>
          </div>

          {/* Card 5: Risk Analytics */}
          <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                <div style={{ padding: '8px', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(239, 68, 68, 0.12)', color: 'var(--danger)' }}>
                  <ShieldAlert size={18} />
                </div>
                <div style={{ fontWeight: 600, fontSize: '15px' }}>5. Risk Tear-Sheet Analytics</div>
              </div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', lineHeight: 1.5, marginBottom: '16px' }}>
                Examine comprehensive historical downside risk metrics: peak-to-trough maximum drawdown, downside semi-deviation below MAR, and Sortino ratios.
              </p>
            </div>
            <button onClick={() => onNavigate('risk-analytics')} className="btn btn-secondary" style={{ width: '100%', justifyContent: 'space-between' }}>
              <span>Inspect Risk Tear-Sheet</span>
              <ArrowRight size={14} />
            </button>
          </div>

          {/* Card 6: Comparative Analysis */}
          <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                <div style={{ padding: '8px', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(14, 165, 233, 0.12)', color: '#38BDF8' }}>
                  <GitCompare size={18} />
                </div>
                <div style={{ fontWeight: 600, fontSize: '15px' }}>6. Portfolio Comparison Matrix</div>
              </div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', lineHeight: 1.5, marginBottom: '16px' }}>
                Cross-compare Global Minimum Variance, Maximum Sharpe, 1/N Equal Weight, and custom user weights over identical historical market windows.
              </p>
            </div>
            <button onClick={() => onNavigate('comparison')} className="btn btn-secondary" style={{ width: '100%', justifyContent: 'space-between' }}>
              <span>Compare Allocations</span>
              <ArrowRight size={14} />
            </button>
          </div>

          {/* Card 7: Walk-Forward Backtesting */}
          <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                <div style={{ padding: '8px', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(168, 85, 247, 0.12)', color: '#A855F7' }}>
                  <PlayCircle size={18} />
                </div>
                <div style={{ fontWeight: 600, fontSize: '15px' }}>7. Walk-Forward Backtesting Engine</div>
              </div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', lineHeight: 1.5, marginBottom: '16px' }}>
                Simulate out-of-sample wealth compounding with realistic asset drift, rebalancing schedules, basis-point transaction costs, and execution slippage.
              </p>
            </div>
            <button onClick={() => onNavigate('backtesting')} className="btn btn-secondary" style={{ width: '100%', justifyContent: 'space-between' }}>
              <span>Launch Backtester</span>
              <ArrowRight size={14} />
            </button>
          </div>

          {/* Card 8: Scenario Analysis & Stress Testing */}
          <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                <div style={{ padding: '8px', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(234, 179, 8, 0.12)', color: '#EAB308' }}>
                  <Zap size={18} />
                </div>
                <div style={{ fontWeight: 600, fontSize: '15px' }}>8. Scenario Analysis & Stress Testing</div>
              </div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', lineHeight: 1.5, marginBottom: '16px' }}>
                Evaluate instantaneous asset-level price shocks, replay historical crisis periods, perturb covariance matrices, and run parametric sensitivity sweeps.
              </p>
            </div>
            <button onClick={() => onNavigate('scenario-analysis')} className="btn btn-secondary" style={{ width: '100%', justifyContent: 'space-between' }}>
              <span>Open Scenario Workspace</span>
              <ArrowRight size={14} />
            </button>
          </div>

          {/* Card 9: Monte Carlo Risk Analysis & VaR/CVaR */}
          <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                <div style={{ padding: '8px', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(56, 189, 248, 0.12)', color: '#38BDF8' }}>
                  <Dice5 size={18} />
                </div>
                <div style={{ fontWeight: 600, fontSize: '15px' }}>9. Monte Carlo & Probabilistic Risk</div>
              </div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', lineHeight: 1.5, marginBottom: '16px' }}>
                Generate multi-period probabilistic wealth distributions, estimate empirical and parametric VaR & CVaR, simulate Multivariate Normal and Student-t distributions, and inspect fan chart trajectories.
              </p>
            </div>
            <button onClick={() => onNavigate('monte-carlo')} className="btn btn-secondary" style={{ width: '100%', justifyContent: 'space-between' }}>
              <span>Launch Monte Carlo Engine</span>
              <ArrowRight size={14} />
            </button>
          </div>

          {/* Card 10: Performance Attribution & Benchmark Analysis */}
          <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                <div style={{ padding: '8px', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(2, 132, 199, 0.12)', color: '#0284C7' }}>
                  <Award size={18} />
                </div>
                <div style={{ fontWeight: 600, fontSize: '15px' }}>10. Performance Attribution & Benchmarks</div>
              </div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', lineHeight: 1.5, marginBottom: '16px' }}>
                Evaluate portfolio returns against a benchmark asset, compute active returns, tracking error, Information Ratio, Beta, Jensen's Alpha, and Menchero multi-period asset contributions.
              </p>
            </div>
            <button onClick={() => onNavigate('performance')} className="btn btn-secondary" style={{ width: '100%', justifyContent: 'space-between' }}>
              <span>Open Performance Workspace</span>
              <ArrowRight size={14} />
            </button>
          </div>

          {/* Card 11: Research Experiments & Strategy Comparison */}
          <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                <div style={{ padding: '8px', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(16, 185, 129, 0.12)', color: '#10B981' }}>
                  <FlaskConical size={18} />
                </div>
                <div style={{ fontWeight: 600, fontSize: '15px' }}>11. Research Experiments & Strategy Comparison</div>
              </div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', lineHeight: 1.5, marginBottom: '16px' }}>
                Define versioned hypotheses, execute reproducible runs with SHA-256 configuration fingerprints, audit dataset provenance, and compare multi-strategy performance, tail risk, and costs side-by-side.
              </p>
            </div>
            <button onClick={() => onNavigate('research-lab')} className="btn btn-secondary" style={{ width: '100%', justifyContent: 'space-between' }}>
              <span>Open Research Lab</span>
              <ArrowRight size={14} />
            </button>
          </div>

          {/* Card 12: Robust Portfolio Optimization & Estimation Uncertainty */}
          <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                <div style={{ padding: '8px', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(234, 179, 8, 0.12)', color: '#EAB308' }}>
                  <Scale size={18} />
                </div>
                <div style={{ fontWeight: 600, fontSize: '15px' }}>12. Robust Portfolio Optimization</div>
              </div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', lineHeight: 1.5, marginBottom: '16px' }}>
                Construct portfolios under worst-case expected returns (Box and Ellipsoidal uncertainty sets), regularize covariance with shrinkage (Ledoit-Wolf diagonal, scaled identity, constant correlation), sweep constraint sensitivities, and validate out-of-sample stability.
              </p>
            </div>
            <button onClick={() => onNavigate('robust-optimization')} className="btn btn-secondary" style={{ width: '100%', justifyContent: 'space-between' }}>
              <span>Launch Robust Workspace</span>
              <ArrowRight size={14} />
            </button>
          </div>

          {/* Card 13: Black-Litterman Bayesian Portfolio Optimization */}
          <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                <div style={{ padding: '8px', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(168, 85, 247, 0.12)', color: '#A855F7' }}>
                  <Layers size={18} />
                </div>
                <div style={{ fontWeight: 600, fontSize: '15px' }}>13. Black-Litterman Bayesian Optimization</div>
              </div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', lineHeight: 1.5, marginBottom: '16px' }}>
                Reverse-engineer market implied equilibrium returns, formulate analyst views with confidence-calibrated uncertainty, compute posterior distributions, and backtest active tilts out-of-sample.
              </p>
            </div>
            <button onClick={() => onNavigate('black-litterman')} className="btn btn-secondary" style={{ width: '100%', justifyContent: 'space-between' }}>
              <span>Launch Black-Litterman</span>
              <ArrowRight size={14} />
            </button>
          </div>

          {/* Card 14: Risk Parity & Hierarchical Risk Parity (HRP) */}
          <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                <div style={{ padding: '8px', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(16, 185, 129, 0.12)', color: '#10B981' }}>
                  <ShieldCheck size={18} />
                </div>
                <div style={{ fontWeight: 600, fontSize: '15px' }}>14. Risk Parity & Hierarchical Risk Parity</div>
              </div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', lineHeight: 1.5, marginBottom: '16px' }}>
                Equalize risk contributions across assets via convex log-barrier SLSQP optimization, or eliminate covariance inversion instabilities using graph-theoretic Hierarchical Risk Parity (HRP) clustering and recursive bisection.
              </p>
            </div>
            <button onClick={() => onNavigate('risk-parity')} className="btn btn-secondary" style={{ width: '100%', justifyContent: 'space-between' }}>
              <span>Launch Risk Parity & HRP</span>
              <ArrowRight size={14} />
            </button>
          </div>

          {/* Card 15: Factor Investing & Systematic Risk Decomposition */}
          <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                <div style={{ padding: '8px', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(56, 189, 248, 0.12)', color: '#38BDF8' }}>
                  <Cpu size={18} />
                </div>
                <div style={{ fontWeight: 600, fontSize: '15px' }}>15. Factor Investing & Risk Decomposition</div>
              </div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', lineHeight: 1.5, marginBottom: '16px' }}>
                Decompose asset risk into systematic multi-factor exposures (CAPM, Fama-French, Carhart, PCA) and idiosyncratic variance using Barra structural modeling. Solve factor-constrained portfolios with custom beta tilts.
              </p>
            </div>
            <button onClick={() => onNavigate('factor-investing')} className="btn btn-secondary" style={{ width: '100%', justifyContent: 'space-between' }}>
              <span>Launch Factor Investing</span>
              <ArrowRight size={14} />
            </button>
          </div>

          {/* Card 16: Dynamic Factor Walk-Forward Backtesting */}
          <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                <div style={{ padding: '8px', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(16, 185, 129, 0.12)', color: '#10B981' }}>
                  <TrendingUp size={18} />
                </div>
                <div style={{ fontWeight: 600, fontSize: '15px' }}>16. Dynamic Factor Backtesting</div>
              </div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', lineHeight: 1.5, marginBottom: '16px' }}>
                Simulate chronological walk-forward factor strategies with rolling OLS estimation, multi-factor alpha tilting, turnover penalty constraints, slippage friction, and factor exposure tracking.
              </p>
            </div>
            <button onClick={() => onNavigate('factor-investing')} className="btn btn-secondary" style={{ width: '100%', justifyContent: 'space-between' }}>
              <span>Launch Factor Backtest</span>
              <ArrowRight size={14} />
            </button>
          </div>

          {/* Card 17: Multi-Asset Allocation & FX Hedging */}
          <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                <div style={{ padding: '8px', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(99, 102, 241, 0.12)', color: '#818CF8' }}>
                  <Coins size={18} />
                </div>
                <div style={{ fontWeight: 600, fontSize: '15px' }}>17. Multi-Asset Allocation & FX Hedging</div>
              </div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', lineHeight: 1.5, marginBottom: '16px' }}>
                Allocate across Equities, Fixed Income, Commodities, and Cash buffers. Model cash yield & drag, decompose FX currency risk vs asset volatility, and evaluate hedged walk-forward backtests.
              </p>
            </div>
            <button onClick={() => onNavigate('multi-asset')} className="btn btn-secondary" style={{ width: '100%', justifyContent: 'space-between' }}>
              <span>Launch Multi-Asset Workspace</span>
              <ArrowRight size={14} />
            </button>
          </div>

          {/* Card 18: Optimal Execution & Market Impact Modeling */}
          <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                <div style={{ padding: '8px', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(245, 158, 11, 0.12)', color: '#F59E0B' }}>
                  <Gauge size={18} />
                </div>
                <div style={{ fontWeight: 600, fontSize: '15px' }}>18. Optimal Execution & Market Impact</div>
              </div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', lineHeight: 1.5, marginBottom: '16px' }}>
                Almgren-Chriss (2000) optimal execution trajectories, TWAP/VWAP scheduling, and non-linear portfolio rebalance market impact modeling under the Square-Root Law.
              </p>
            </div>
            <button onClick={() => onNavigate('execution')} className="btn btn-secondary" style={{ width: '100%', justifyContent: 'space-between' }}>
              <span>Launch Optimal Execution</span>
              <ArrowRight size={14} />
            </button>
          </div>

          {/* Card 19: Regime-Switching & Volatility Targeting */}
          <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                <div style={{ padding: '8px', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(16, 185, 129, 0.12)', color: '#10B981' }}>
                  <Activity size={18} />
                </div>
                <div style={{ fontWeight: 600, fontSize: '15px' }}>19. Regime-Switching & Volatility Targeting</div>
              </div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', lineHeight: 1.5, marginBottom: '16px' }}>
                Gaussian Hidden Markov Models (HMM), Baum-Welch EM calibration, causal forward-filtered probabilities, regime-conditioned covariance blending, and dynamic volatility targeting overlays.
              </p>
            </div>
            <button onClick={() => onNavigate('regime-switching')} className="btn btn-secondary" style={{ width: '100%', justifyContent: 'space-between' }}>
              <span>Launch Regime Switching</span>
              <ArrowRight size={14} />
            </button>
          </div>

          {/* Card 20: Performance Attribution & Factor Decomposition */}
          <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                <div style={{ padding: '8px', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(236, 72, 153, 0.12)', color: '#EC4899' }}>
                  <Award size={18} />
                </div>
                <div style={{ fontWeight: 600, fontSize: '15px' }}>20. Brinson & Systematic Factor Attribution</div>
              </div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', lineHeight: 1.5, marginBottom: '16px' }}>
                Single and multi-period Brinson-Fachler attribution with Cariño logarithmic compounding linking, exact residual reconciliation, and systematic Barra factor active risk & return decomposition.
              </p>
            </div>
            <button onClick={() => onNavigate('brinson-attribution')} className="btn btn-secondary" style={{ width: '100%', justifyContent: 'space-between' }}>
              <span>Launch Attribution Workspace</span>
              <ArrowRight size={14} />
            </button>
          </div>

          {/* Card 21: Copula Tail Risk & Tail Risk Parity */}
          <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                <div style={{ padding: '8px', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(99, 102, 241, 0.12)', color: '#6366F1' }}>
                  <Network size={18} />
                </div>
                <div style={{ fontWeight: 600, fontSize: '15px' }}>21. Copula Tail Risk & Tail Risk Parity</div>
              </div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', lineHeight: 1.5, marginBottom: '16px' }}>
                Archimedean and elliptical copulas (Clayton, Gumbel, Student-t, Gaussian), asymmetric lower-tail crash modeling, dependent return simulation, and Tail Risk Parity (TRP) allocation.
              </p>
            </div>
            <button onClick={() => onNavigate('copula-tail-risk')} className="btn btn-secondary" style={{ width: '100%', justifyContent: 'space-between' }}>
              <span>Launch Copula Workspace</span>
              <ArrowRight size={14} />
            </button>
          </div>
        </div>
      </div>

      {/* Assumptions & Methodological Governance Notice */}
      <div className="alert alert-info">
        <Info size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
        <div>
          <div style={{ fontWeight: 600, marginBottom: '4px' }}>Quantitative Engine Governance & Assumptions</div>
          <div style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            • In-Memory Registry & Persistent DB: Datasets are verified and indexed in PostgreSQL/SQLite with content SHA-256 deduplication.<br />
            • Multi-Asset & Currency Architecture: Stage 18 enables cross-asset allocation (Equities, Bonds, Cash) and multi-currency FX risk decomposition with forward hedging overlays.<br />
            • Numerical Solvers: Optimization is performed via SciPy SLSQP quadratic programming with strict tolerance checks and sample covariance matrix estimation.
          </div>
        </div>
      </div>
    </div>
  );
};
