import React, { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { DatasetProvider } from './context/DatasetContext';
import { Header } from './components/layout/Header';
import { Sidebar, type NavItem } from './components/layout/Sidebar';
import { OverviewPage } from './components/pages/OverviewPage';
import { MarketDataPage } from './components/pages/MarketDataPage';
import { PortfolioSetupPage } from './components/pages/PortfolioSetupPage';
import { OptimizationPage } from './components/pages/OptimizationPage';
import { EfficientFrontierPage } from './components/pages/EfficientFrontierPage';
import { RiskAnalyticsPage } from './components/pages/RiskAnalyticsPage';
import { PortfolioComparisonPage } from './components/pages/PortfolioComparisonPage';
import { BacktestingPage } from './components/pages/BacktestingPage';
import { ScenarioAnalysisPage } from './components/pages/ScenarioAnalysisPage';
import { MonteCarloPage } from './components/pages/MonteCarloPage';
import { PerformancePage } from './components/pages/PerformancePage';
import { ResearchLabPage } from './components/pages/ResearchLabPage';
import { RobustOptimizationPage } from './components/pages/RobustOptimizationPage';
import { BlackLittermanPage } from './components/pages/BlackLittermanPage';
import { RiskParityPage } from './components/pages/RiskParityPage';
import { FactorInvestingPage } from './components/pages/FactorInvestingPage';
import { MultiAssetPage } from './components/pages/MultiAssetPage';
import { ExecutionPage } from './components/pages/ExecutionPage';
import { RegimeSwitchingPage } from './components/pages/RegimeSwitchingPage';
import { BrinsonAttributionPage } from './components/pages/BrinsonAttributionPage';
import { CopulaTailRiskPage } from './components/pages/CopulaTailRiskPage';
import { SystemInfoPage } from './components/pages/SystemInfoPage';
import { AuthPage } from './components/auth/AuthPage';
import type { PortfolioDefinition } from './types/api';

const MainApp: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();
  const [currentNav, setCurrentNav] = useState<NavItem>('overview');
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(false);
  const [activePortfolio, setActivePortfolio] = useState<PortfolioDefinition | null>(null);

  const toggleSidebar = () => {
    setIsSidebarOpen((prev) => !prev);
  };

  const closeSidebarMobile = () => {
    setIsSidebarOpen(false);
  };

  if (isLoading) {
    return (
      <div className="loading-screen" role="status" aria-label="Loading workspace">
        <div className="loading-spinner"></div>
        <p style={{ fontSize: '13px', fontWeight: 500, letterSpacing: '0.02em' }}>
          Verifying secure quant researcher session...
        </p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <AuthPage />;
  }

  const renderContent = () => {
    switch (currentNav) {
      case 'overview':
        return <OverviewPage onNavigate={setCurrentNav} />;
      case 'market-data':
        return <MarketDataPage />;
      case 'portfolio-setup':
        return <PortfolioSetupPage onValidatedPortfolio={setActivePortfolio} />;
      case 'optimization':
        return <OptimizationPage initialPortfolio={activePortfolio} />;
      case 'efficient-frontier':
        return <EfficientFrontierPage initialPortfolio={activePortfolio} />;
      case 'risk-analytics':
        return <RiskAnalyticsPage initialPortfolio={activePortfolio} />;
      case 'comparison':
        return <PortfolioComparisonPage initialPortfolio={activePortfolio} />;
      case 'backtesting':
        return <BacktestingPage initialPortfolio={activePortfolio} />;
      case 'scenario-analysis':
        return <ScenarioAnalysisPage initialPortfolio={activePortfolio} />;
      case 'monte-carlo':
        return <MonteCarloPage initialPortfolio={activePortfolio} />;
      case 'performance':
        return <PerformancePage initialPortfolio={activePortfolio} />;
      case 'research-lab':
        return <ResearchLabPage />;
      case 'robust-optimization':
        return <RobustOptimizationPage />;
      case 'black-litterman':
        return <BlackLittermanPage />;
      case 'risk-parity':
        return <RiskParityPage />;
      case 'factor-investing':
        return <FactorInvestingPage />;
      case 'multi-asset':
        return <MultiAssetPage />;
      case 'execution':
        return <ExecutionPage />;
      case 'regime-switching':
        return <RegimeSwitchingPage />;
      case 'brinson-attribution':
        return <BrinsonAttributionPage />;
      case 'copula-tail-risk':
        return <CopulaTailRiskPage />;
      case 'system-info':
        return <SystemInfoPage />;
      default:
        return <OverviewPage onNavigate={setCurrentNav} />;
    }
  };

  return (
    <div className="app-layout">
      <Sidebar
        currentNav={currentNav}
        onNavigate={setCurrentNav}
        isOpen={isSidebarOpen}
        onCloseMobile={closeSidebarMobile}
      />
      <div className="main-content">
        <Header
          currentNav={currentNav}
          onNavigate={setCurrentNav}
          onToggleSidebar={toggleSidebar}
        />
        <main>{renderContent()}</main>
      </div>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <DatasetProvider>
        <MainApp />
      </DatasetProvider>
    </AuthProvider>
  );
};

export default App;
