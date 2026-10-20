import React from 'react';
import {
  LayoutDashboard,
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
  Server,
  ChevronRight
} from 'lucide-react';

export type NavItem =
  | 'overview'
  | 'market-data'
  | 'portfolio-setup'
  | 'optimization'
  | 'efficient-frontier'
  | 'risk-analytics'
  | 'comparison'
  | 'backtesting'
  | 'scenario-analysis'
  | 'monte-carlo'
  | 'performance'
  | 'research-lab'
  | 'robust-optimization'
  | 'black-litterman'
  | 'risk-parity'
  | 'factor-investing'
  | 'multi-asset'
  | 'execution'
  | 'regime-switching'
  | 'brinson-attribution'
  | 'copula-tail-risk'
  | 'system-info';

interface SidebarProps {
  currentNav: NavItem;
  onNavigate: (item: NavItem) => void;
  isOpen: boolean;
  onCloseMobile?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ currentNav, onNavigate, isOpen, onCloseMobile }) => {
  const navItems: { id: NavItem; label: string; icon: React.FC<{ size?: number; className?: string }> }[] = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'market-data', label: 'Market Data', icon: Database },
    { id: 'portfolio-setup', label: 'Portfolio Definition', icon: SlidersHorizontal },
    { id: 'optimization', label: 'Optimization', icon: Target },
    { id: 'efficient-frontier', label: 'Efficient Frontier', icon: TrendingUp },
    { id: 'risk-analytics', label: 'Risk Analytics', icon: ShieldAlert },
    { id: 'comparison', label: 'Portfolio Comparison', icon: GitCompare },
    { id: 'backtesting', label: 'Backtesting', icon: PlayCircle },
    { id: 'scenario-analysis', label: 'Scenario & Stress', icon: Zap },
    { id: 'monte-carlo', label: 'Monte Carlo Risk', icon: Dice5 },
    { id: 'performance', label: 'Attribution & Benchmarks', icon: Award },
    { id: 'research-lab', label: 'Research Lab', icon: FlaskConical },
    { id: 'robust-optimization', label: 'Robust Optimization', icon: Scale },
    { id: 'black-litterman', label: 'Black-Litterman', icon: Layers },
    { id: 'risk-parity', label: 'Risk Parity & HRP', icon: ShieldCheck },
    { id: 'factor-investing', label: 'Factor Investing', icon: Cpu },
    { id: 'multi-asset', label: 'Multi-Asset & FX', icon: Coins },
    { id: 'execution', label: 'Optimal Execution', icon: Gauge },
    { id: 'regime-switching', label: 'Regime Switching & Vol', icon: Activity },
    { id: 'brinson-attribution', label: 'Brinson & Factor Attribution', icon: Award },
    { id: 'copula-tail-risk', label: 'Copula & Tail Risk Parity', icon: Network },
    { id: 'system-info', label: 'System & Registry', icon: Server },
  ];

  return (
    <aside
      className={`sidebar ${isOpen ? 'open' : ''}`}
      style={{
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
      }}
    >
      <div>
        {/* Brand header */}
        <div
          style={{
            height: 'var(--header-height)',
            display: 'flex',
            alignItems: 'center',
            padding: '0 20px',
            borderBottom: '1px solid var(--border-subtle)',
            gap: '10px',
          }}
        >
          <div
            style={{
              width: '28px',
              height: '28px',
              borderRadius: '6px',
              background: 'linear-gradient(135deg, #0284C7 0%, #38BDF8 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 700,
              fontSize: '15px',
              color: '#041226',
            }}
          >
            Q
          </div>
          <div>
            <div style={{ fontWeight: 600, fontSize: '14px', letterSpacing: '-0.01em', color: 'var(--text-primary)' }}>
              Quant Engine
            </div>
            <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Institutional Research
            </div>
          </div>
        </div>

        {/* Navigation Section */}
        <div style={{ padding: '16px 12px' }}>
          <div
            style={{
              fontSize: '10px',
              fontWeight: 600,
              color: 'var(--text-dim)',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              padding: '0 8px 8px 8px',
            }}
          >
            Research Workspaces
          </div>
          <nav style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = currentNav === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => {
                    onNavigate(item.id);
                    if (onCloseMobile) onCloseMobile();
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid',
                    borderColor: isActive ? 'var(--border-medium)' : 'transparent',
                    backgroundColor: isActive ? 'var(--bg-elevated)' : 'transparent',
                    color: isActive ? 'var(--accent)' : 'var(--text-secondary)',
                    fontSize: '13px',
                    fontWeight: isActive ? 600 : 500,
                    cursor: 'pointer',
                    textAlign: 'left',
                    transition: 'all 0.15s ease',
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive) {
                      e.currentTarget.style.backgroundColor = 'var(--bg-card-hover)';
                      e.currentTarget.style.color = 'var(--text-primary)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive) {
                      e.currentTarget.style.backgroundColor = 'transparent';
                      e.currentTarget.style.color = 'var(--text-secondary)';
                    }
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <Icon size={16} />
                    <span>{item.label}</span>
                  </div>
                  {isActive && <ChevronRight size={14} style={{ color: 'var(--accent)' }} />}
                </button>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Footer Info */}
      <div
        style={{
          padding: '16px',
          borderTop: '1px solid var(--border-subtle)',
          fontSize: '11px',
          color: 'var(--text-dim)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
          <span>Engine Release</span>
          <span className="font-mono" style={{ color: 'var(--text-secondary)' }}>v0.5.0</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span>Session State</span>
          <span style={{ color: 'var(--success)' }}>Session 09 UI</span>
        </div>
      </div>
    </aside>
  );
};
