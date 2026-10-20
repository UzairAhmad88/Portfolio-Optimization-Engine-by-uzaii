import type {
  AuthMessageResponse,
  BacktestListItem,
  BacktestRequest,
  BacktestResponse,
  BlackLittermanBacktestRequest,
  BlackLittermanBacktestResponse,
  BlackLittermanOptimizeRequest,
  BlackLittermanOptimizeResponse,
  BrinsonAttributionRequest,
  BrinsonAttributionResponse,
  SystematicFactorAttributionRequest,
  SystematicFactorAttributionResponse,
  CopulaFitRequest,
  CopulaFitResponse,
  CopulaSimulateRequest,
  CopulaSimulateResponse,
  TailRiskParityRequest,
  TailRiskParityResponse,
  VineCopulaFitRequest,
  VineCopulaFitResponse,
  VineCopulaSimulateRequest,
  VineCopulaSimulateResponse,
  VineTailRiskParityRequest,
  VineTailRiskParityResponse,
  VineBacktestRequest,
  VineBacktestResponse,
  DatasetAssetsResponse,
  DatasetMetadataResponse,
  DatasetQuery,
  DatasetQueryResponse,
  DynamicFactorBacktestRequest,
  DynamicFactorBacktestResponse,
  EfficientFrontierRequest,
  EfficientFrontierResponse,
  FactorAttributionRequest,
  FactorAttributionResponse,
  FactorConstrainedOptimizeRequest,
  FactorConstrainedOptimizeResponse,
  HealthResponse,
  LoginRequest,
  MultiEstimatorComparison,
  OptimizationRequest,
  OptimizationResponse,
  ComparisonRequest,
  ComparisonResponse,
  ExperimentCreateRequest,
  ExperimentListItem,
  ExperimentResponse,
  ExperimentRunListItem,
  ExperimentRunResponse,
  ExperimentUpdateRequest,
  PerformanceAnalysisRequest,
  PerformanceReportListItem,
  PerformanceResponse,
  PortfolioComparisonRequest,
  PortfolioComparisonResponse,
  PortfolioDefinition,
  PortfolioValidationReport,
  RegisterRequest,
  RiskSimulationListItem,
  RiskSimulationRequest,
  RiskSimulationResponse,
  RobustBacktestRequest,
  RobustBacktestResponse,
  RobustOptimizationRequest,
  RobustOptimizationResponse,
  RiskParityBacktestRequest,
  RiskParityBacktestResponse,
  RiskParityOptimizeRequest,
  RiskParityOptimizeResponse,
  ScenarioListItem,
  ScenarioRequest,
  ScenarioResponse,
  SensitivityAnalysisRequest,
  SensitivityAnalysisResponse,
  SensitivityRequest,
  MultiAssetBacktestRequest,
  MultiAssetBacktestResponse,
  MultiAssetOptimizeRequest,
  MultiAssetOptimizeResponse,
  OptimalExecutionRequest,
  OptimalExecutionResponse,
  RebalanceImpactRequest,
  RebalanceImpactResponse,
  RegimeDetectionRequest,
  RegimeDetectionResponse,
  RegimeBacktestRequest,
  RegimeBacktestResponse,
  SensitivityResponse,
  TokenResponse,
  User,
  ValidationReportResponse,
  VaRCVaRStandaloneRequest,
} from '../types/api';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export class ApiError extends Error {
  status: number;
  data: any;

  constructor(status: number, message: string, data?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  let body: any = null;
  const contentType = res.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    try {
      body = await res.json();
    } catch {
      body = null;
    }
  } else {
    try {
      body = await res.text();
    } catch {
      body = null;
    }
  }

  if (!res.ok) {
    let message = `API request failed with status ${res.status}`;
    if (body) {
      if (typeof body.detail === 'string') {
        message = body.detail;
      } else if (Array.isArray(body.detail)) {
        message = body.detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ');
      } else if (typeof body.detail === 'object' && body.detail !== null) {
        if (body.detail.errors && Array.isArray(body.detail.errors)) {
          message = body.detail.errors.join('; ');
        } else {
          message = JSON.stringify(body.detail);
        }
      } else if (typeof body.message === 'string') {
        message = body.message;
      }
    }
    throw new ApiError(res.status, message, body);
  }

  return body as T;
}

function secureFetch(url: string, init?: RequestInit): Promise<Response> {
  return fetch(url, {
    ...init,
    credentials: 'include', // Automatically passes HttpOnly session cookies
  });
}

export const apiClient = {
  // --- Authentication & Session APIs ---
  async register(req: RegisterRequest): Promise<User> {
    const res = await secureFetch(`${BASE_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    return handleResponse<User>(res);
  },

  async login(req: LoginRequest): Promise<TokenResponse> {
    const res = await secureFetch(`${BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    return handleResponse<TokenResponse>(res);
  },

  async logout(): Promise<AuthMessageResponse> {
    const res = await secureFetch(`${BASE_URL}/auth/logout`, {
      method: 'POST',
    });
    return handleResponse<AuthMessageResponse>(res);
  },

  async getMe(): Promise<User> {
    const res = await secureFetch(`${BASE_URL}/auth/me`);
    return handleResponse<User>(res);
  },

  // --- Market Data APIs ---
  async getHealth(): Promise<HealthResponse> {
    const res = await secureFetch(`${BASE_URL}/health`);
    return handleResponse<HealthResponse>(res);
  },

  async previewCsv(file: File): Promise<ValidationReportResponse> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await secureFetch(`${BASE_URL}/market-data/preview`, {
      method: 'POST',
      body: formData,
    });
    return handleResponse<ValidationReportResponse>(res);
  },

  async uploadCsv(file: File): Promise<DatasetMetadataResponse> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await secureFetch(`${BASE_URL}/market-data/uploads`, {
      method: 'POST',
      body: formData,
    });
    return handleResponse<DatasetMetadataResponse>(res);
  },

  async listDatasets(): Promise<DatasetMetadataResponse[]> {
    const res = await secureFetch(`${BASE_URL}/market-data/datasets`);
    return handleResponse<DatasetMetadataResponse[]>(res);
  },

  async getDatasetMetadata(datasetId: string): Promise<DatasetMetadataResponse> {
    const res = await secureFetch(`${BASE_URL}/market-data/datasets/${encodeURIComponent(datasetId)}`);
    return handleResponse<DatasetMetadataResponse>(res);
  },

  async listDatasetAssets(datasetId: string): Promise<DatasetAssetsResponse> {
    const res = await secureFetch(`${BASE_URL}/market-data/datasets/${encodeURIComponent(datasetId)}/assets`);
    return handleResponse<DatasetAssetsResponse>(res);
  },

  async queryDataset(query: DatasetQuery): Promise<DatasetQueryResponse> {
    const res = await secureFetch(`${BASE_URL}/market-data/datasets/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(query),
    });
    return handleResponse<DatasetQueryResponse>(res);
  },

  // --- Portfolio & Quantitative Analytics APIs ---
  async validatePortfolio(portfolio: PortfolioDefinition): Promise<PortfolioValidationReport> {
    const res = await secureFetch(`${BASE_URL}/portfolios/validate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(portfolio),
    });
    return handleResponse<PortfolioValidationReport>(res);
  },

  async optimizePortfolio(request: OptimizationRequest): Promise<OptimizationResponse> {
    const res = await secureFetch(`${BASE_URL}/portfolios/optimize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    return handleResponse<OptimizationResponse>(res);
  },

  async generateEfficientFrontier(request: EfficientFrontierRequest): Promise<EfficientFrontierResponse> {
    const res = await secureFetch(`${BASE_URL}/portfolios/efficient-frontier`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    return handleResponse<EfficientFrontierResponse>(res);
  },

  async comparePortfolios(request: PortfolioComparisonRequest): Promise<PortfolioComparisonResponse> {
    const res = await secureFetch(`${BASE_URL}/portfolios/compare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    return handleResponse<PortfolioComparisonResponse>(res);
  },

  // --- Backtesting & Simulation APIs ---
  async executeBacktest(request: BacktestRequest): Promise<BacktestResponse> {
    const res = await secureFetch(`${BASE_URL}/backtests`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    return handleResponse<BacktestResponse>(res);
  },

  async listBacktests(limit: number = 50, offset: number = 0): Promise<BacktestListItem[]> {
    const res = await secureFetch(`${BASE_URL}/backtests?limit=${limit}&offset=${offset}`, {
      method: 'GET',
    });
    return handleResponse<BacktestListItem[]>(res);
  },

  async getBacktest(backtestId: string): Promise<BacktestResponse> {
    const res = await secureFetch(`${BASE_URL}/backtests/${backtestId}`, {
      method: 'GET',
    });
    return handleResponse<BacktestResponse>(res);
  },

  async deleteBacktest(backtestId: string): Promise<{ status: string; id: string }> {
    const res = await secureFetch(`${BASE_URL}/backtests/${backtestId}`, {
      method: 'DELETE',
    });
    return handleResponse<{ status: string; id: string }>(res);
  },

  // --- Scenario Analysis & Stress Testing APIs ---
  async executeScenario(request: ScenarioRequest): Promise<ScenarioResponse> {
    const res = await secureFetch(`${BASE_URL}/scenarios`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    return handleResponse<ScenarioResponse>(res);
  },

  async executeStressTest(request: ScenarioRequest): Promise<ScenarioResponse> {
    const res = await secureFetch(`${BASE_URL}/scenarios/stress-test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    return handleResponse<ScenarioResponse>(res);
  },

  async executeSensitivity(request: SensitivityRequest): Promise<SensitivityResponse> {
    const res = await secureFetch(`${BASE_URL}/scenarios/sensitivity`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    return handleResponse<SensitivityResponse>(res);
  },

  async listScenarios(datasetId?: string): Promise<ScenarioListItem[]> {
    const url = datasetId
      ? `${BASE_URL}/scenarios?dataset_id=${encodeURIComponent(datasetId)}`
      : `${BASE_URL}/scenarios`;
    const res = await secureFetch(url, {
      method: 'GET',
    });
    return handleResponse<ScenarioListItem[]>(res);
  },

  async getScenario(scenarioId: string): Promise<ScenarioResponse> {
    const res = await secureFetch(`${BASE_URL}/scenarios/${scenarioId}`, {
      method: 'GET',
    });
    return handleResponse<ScenarioResponse>(res);
  },

  async deleteScenario(scenarioId: string): Promise<{ message: string; id: string }> {
    const res = await secureFetch(`${BASE_URL}/scenarios/${scenarioId}`, {
      method: 'DELETE',
    });
    return handleResponse<{ message: string; id: string }>(res);
  },

  // --- Monte Carlo Risk Simulation & VaR/CVaR APIs ---
  async executeRiskSimulation(request: RiskSimulationRequest): Promise<RiskSimulationResponse> {
    const res = await secureFetch(`${BASE_URL}/risk-simulations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    return handleResponse<RiskSimulationResponse>(res);
  },

  async calculateStandaloneVaRCVaR(request: VaRCVaRStandaloneRequest): Promise<MultiEstimatorComparison[]> {
    const res = await secureFetch(`${BASE_URL}/risk-simulations/var-cvar`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    return handleResponse<MultiEstimatorComparison[]>(res);
  },

  async listRiskSimulations(limit?: number, offset?: number): Promise<RiskSimulationListItem[]> {
    const params = new URLSearchParams();
    if (limit) params.set('limit', limit.toString());
    if (offset) params.set('offset', offset.toString());
    const query = params.toString() ? `?${params.toString()}` : '';

    const res = await secureFetch(`${BASE_URL}/risk-simulations${query}`, {
      method: 'GET',
    });
    return handleResponse<RiskSimulationListItem[]>(res);
  },

  async getRiskSimulation(runId: string): Promise<RiskSimulationResponse> {
    const res = await secureFetch(`${BASE_URL}/risk-simulations/${runId}`, {
      method: 'GET',
    });
    return handleResponse<RiskSimulationResponse>(res);
  },

  async deleteRiskSimulation(runId: string): Promise<{ status: string; message: string }> {
    const res = await secureFetch(`${BASE_URL}/risk-simulations/${runId}`, {
      method: 'DELETE',
    });
    return handleResponse<{ status: string; message: string }>(res);
  },

  async analyzePerformance(request: PerformanceAnalysisRequest): Promise<PerformanceResponse> {
    const res = await secureFetch(`${BASE_URL}/performance/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    return handleResponse<PerformanceResponse>(res);
  },

  async getBacktestPerformance(
    backtestId: string,
    benchmarkAsset: string,
    riskFreeRate: number = 0.0,
    saveReport: boolean = true
  ): Promise<PerformanceResponse> {
    const params = new URLSearchParams({
      benchmark_asset: benchmarkAsset,
      risk_free_rate: riskFreeRate.toString(),
      save_report: saveReport.toString(),
    });
    const res = await secureFetch(`${BASE_URL}/performance/backtests/${backtestId}?${params.toString()}`, {
      method: 'GET',
    });
    return handleResponse<PerformanceResponse>(res);
  },

  async listPerformanceReports(limit?: number, offset?: number): Promise<PerformanceReportListItem[]> {
    const params = new URLSearchParams();
    if (limit) params.set('limit', limit.toString());
    if (offset) params.set('offset', offset.toString());
    const query = params.toString() ? `?${params.toString()}` : '';

    const res = await secureFetch(`${BASE_URL}/performance/reports${query}`, {
      method: 'GET',
    });
    return handleResponse<PerformanceReportListItem[]>(res);
  },

  async getPerformanceReport(reportId: string): Promise<PerformanceResponse> {
    const res = await secureFetch(`${BASE_URL}/performance/reports/${reportId}`, {
      method: 'GET',
    });
    return handleResponse<PerformanceResponse>(res);
  },

  async deletePerformanceReport(reportId: string): Promise<{ status: string; message: string }> {
    const res = await secureFetch(`${BASE_URL}/performance/reports/${reportId}`, {
      method: 'DELETE',
    });
    return handleResponse<{ status: string; message: string }>(res);
  },

  // ============================================================================
  // Research Experiments & Strategy Comparison
  // ============================================================================

  async createExperiment(payload: ExperimentCreateRequest): Promise<ExperimentResponse> {
    const res = await secureFetch(`${BASE_URL}/research/experiments`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return handleResponse<ExperimentResponse>(res);
  },

  async listExperiments(): Promise<ExperimentListItem[]> {
    const res = await secureFetch(`${BASE_URL}/research/experiments`, {
      method: 'GET',
    });
    return handleResponse<ExperimentListItem[]>(res);
  },

  async getExperiment(experimentId: string): Promise<ExperimentResponse> {
    const res = await secureFetch(`${BASE_URL}/research/experiments/${experimentId}`, {
      method: 'GET',
    });
    return handleResponse<ExperimentResponse>(res);
  },

  async updateExperiment(
    experimentId: string,
    payload: ExperimentUpdateRequest
  ): Promise<ExperimentResponse> {
    const res = await secureFetch(`${BASE_URL}/research/experiments/${experimentId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
    return handleResponse<ExperimentResponse>(res);
  },

  async deleteExperiment(experimentId: string): Promise<void> {
    const res = await secureFetch(`${BASE_URL}/research/experiments/${experimentId}`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      return handleResponse<void>(res);
    }
  },

  async executeExperimentRun(experimentId: string): Promise<ExperimentRunResponse> {
    const res = await secureFetch(`${BASE_URL}/research/experiments/${experimentId}/runs`, {
      method: 'POST',
    });
    return handleResponse<ExperimentRunResponse>(res);
  },

  async listExperimentRuns(experimentId: string): Promise<ExperimentRunListItem[]> {
    const res = await secureFetch(`${BASE_URL}/research/experiments/${experimentId}/runs`, {
      method: 'GET',
    });
    return handleResponse<ExperimentRunListItem[]>(res);
  },

  async getExperimentRun(runId: string): Promise<ExperimentRunResponse> {
    const res = await secureFetch(`${BASE_URL}/research/runs/${runId}`, {
      method: 'GET',
    });
    return handleResponse<ExperimentRunResponse>(res);
  },

  async compareExperimentRuns(payload: ComparisonRequest): Promise<ComparisonResponse> {
    const res = await secureFetch(`${BASE_URL}/research/comparisons`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return handleResponse<ComparisonResponse>(res);
  },

  async optimizeRobustPortfolio(payload: RobustOptimizationRequest): Promise<RobustOptimizationResponse> {
    const res = await secureFetch(`${BASE_URL}/robust-optimization/optimize`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return handleResponse<RobustOptimizationResponse>(res);
  },

  async runRobustSensitivity(payload: SensitivityAnalysisRequest): Promise<SensitivityAnalysisResponse> {
    const res = await secureFetch(`${BASE_URL}/robust-optimization/sensitivity`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return handleResponse<SensitivityAnalysisResponse>(res);
  },

  async runRobustBacktest(payload: RobustBacktestRequest): Promise<RobustBacktestResponse> {
    const res = await secureFetch(`${BASE_URL}/robust-optimization/backtest`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return handleResponse<RobustBacktestResponse>(res);
  },

  // ============================================================================
  // Black-Litterman Bayesian Portfolio Optimization
  // ============================================================================

  async optimizeBlackLitterman(payload: BlackLittermanOptimizeRequest): Promise<BlackLittermanOptimizeResponse> {
    const res = await secureFetch(`${BASE_URL}/black-litterman/optimize`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return handleResponse<BlackLittermanOptimizeResponse>(res);
  },

  async backtestBlackLitterman(payload: BlackLittermanBacktestRequest): Promise<BlackLittermanBacktestResponse> {
    const res = await secureFetch(`${BASE_URL}/black-litterman/backtest`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return handleResponse<BlackLittermanBacktestResponse>(res);
  },

  // ============================================================================
  // Risk Parity & Hierarchical Risk Parity (HRP)
  // ============================================================================

  async optimizeRiskParity(payload: RiskParityOptimizeRequest): Promise<RiskParityOptimizeResponse> {
    const res = await secureFetch(`${BASE_URL}/risk-parity/optimize`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return handleResponse<RiskParityOptimizeResponse>(res);
  },

  async backtestRiskParity(payload: RiskParityBacktestRequest): Promise<RiskParityBacktestResponse> {
    const res = await secureFetch(`${BASE_URL}/risk-parity/backtest`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return handleResponse<RiskParityBacktestResponse>(res);
  },

  // ============================================================================
  // Factor Investing & Systematic Risk Decomposition
  // ============================================================================

  async attributeFactorRisk(payload: FactorAttributionRequest): Promise<FactorAttributionResponse> {
    const res = await secureFetch(`${BASE_URL}/factor-investing/attribute`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return handleResponse<FactorAttributionResponse>(res);
  },

  async optimizeFactorConstrained(payload: FactorConstrainedOptimizeRequest): Promise<FactorConstrainedOptimizeResponse> {
    const res = await secureFetch(`${BASE_URL}/factor-investing/optimize`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return handleResponse<FactorConstrainedOptimizeResponse>(res);
  },

  async backtestDynamicFactors(payload: DynamicFactorBacktestRequest): Promise<DynamicFactorBacktestResponse> {
    const res = await secureFetch(`${BASE_URL}/factor-investing/backtest`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return handleResponse<DynamicFactorBacktestResponse>(res);
  },

  // ============================================================================
  // Multi-Asset Class Allocation, Cash Drag & FX Hedging
  // ============================================================================

  async optimizeMultiAsset(payload: MultiAssetOptimizeRequest): Promise<MultiAssetOptimizeResponse> {
    const res = await secureFetch(`${BASE_URL}/multi-asset/optimize`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return handleResponse<MultiAssetOptimizeResponse>(res);
  },

  async backtestMultiAsset(payload: MultiAssetBacktestRequest): Promise<MultiAssetBacktestResponse> {
    const res = await secureFetch(`${BASE_URL}/multi-asset/backtest`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return handleResponse<MultiAssetBacktestResponse>(res);
  },

  // ============================================================================
  // Optimal Execution & Market Impact Modeling (Stage 19)
  // ============================================================================

  async getOptimalExecutionSchedule(payload: OptimalExecutionRequest): Promise<OptimalExecutionResponse> {
    const res = await secureFetch(`${BASE_URL}/execution/optimal-schedule`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return handleResponse<OptimalExecutionResponse>(res);
  },

  async evaluateRebalanceImpact(payload: RebalanceImpactRequest): Promise<RebalanceImpactResponse> {
    const res = await secureFetch(`${BASE_URL}/execution/rebalance-impact`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return handleResponse<RebalanceImpactResponse>(res);
  },

  // ============================================================================
  // Regime-Switching Asset Allocation & Volatility Targeting (Stage 20)
  // ============================================================================

  async detectRegimes(payload: RegimeDetectionRequest): Promise<RegimeDetectionResponse> {
    const res = await secureFetch(`${BASE_URL}/regime-switching/detect`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return handleResponse<RegimeDetectionResponse>(res);
  },

  async backtestRegimes(payload: RegimeBacktestRequest): Promise<RegimeBacktestResponse> {
    const res = await secureFetch(`${BASE_URL}/regime-switching/backtest`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return handleResponse<RegimeBacktestResponse>(res);
  },

  // ============================================================================
  // Performance Attribution & Brinson-Fachler Decomposition (Stage 21)
  // ============================================================================

  async computeBrinsonAttribution(payload: BrinsonAttributionRequest): Promise<BrinsonAttributionResponse> {
    const res = await secureFetch(`${BASE_URL}/attribution/brinson`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return handleResponse<BrinsonAttributionResponse>(res);
  },

  async computeSystematicFactorAttribution(payload: SystematicFactorAttributionRequest): Promise<SystematicFactorAttributionResponse> {
    const res = await secureFetch(`${BASE_URL}/attribution/factor`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return handleResponse<SystematicFactorAttributionResponse>(res);
  },

  // ============================================================================
  // Copula Tail Risk & Tail Risk Parity (Stage 22)
  // ============================================================================

  async fitCopula(payload: CopulaFitRequest): Promise<CopulaFitResponse> {
    const res = await secureFetch(`${BASE_URL}/copula/fit`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return handleResponse<CopulaFitResponse>(res);
  },

  async simulateCopula(payload: CopulaSimulateRequest): Promise<CopulaSimulateResponse> {
    const res = await secureFetch(`${BASE_URL}/copula/simulate`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return handleResponse<CopulaSimulateResponse>(res);
  },

  async optimizeTailRiskParity(payload: TailRiskParityRequest): Promise<TailRiskParityResponse> {
    const res = await secureFetch(`${BASE_URL}/copula/tail-risk-parity`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return handleResponse<TailRiskParityResponse>(res);
  },

  // ============================================================================
  // Regular Vine Copula Architecture (Stage 23)
  // ============================================================================

  async fitVineCopula(payload: VineCopulaFitRequest): Promise<VineCopulaFitResponse> {
    const res = await secureFetch(`${BASE_URL}/copula/vine/fit`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return handleResponse<VineCopulaFitResponse>(res);
  },

  async simulateVineCopula(payload: VineCopulaSimulateRequest): Promise<VineCopulaSimulateResponse> {
    const res = await secureFetch(`${BASE_URL}/copula/vine/simulate`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return handleResponse<VineCopulaSimulateResponse>(res);
  },

  async optimizeVineTailRiskParity(payload: VineTailRiskParityRequest): Promise<VineTailRiskParityResponse> {
    const res = await secureFetch(`${BASE_URL}/copula/vine/tail-risk-parity`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return handleResponse<VineTailRiskParityResponse>(res);
  },

  // ============================================================================
  // Dynamic Walk-Forward Vine Backtesting (Stage 24)
  // ============================================================================

  async runVineBacktest(payload: VineBacktestRequest): Promise<VineBacktestResponse> {
    const res = await secureFetch(`${BASE_URL}/copula/vine/backtest`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    const raw = await handleResponse<any>(res);
    if (raw && raw.strategy_metrics && !raw.strategies) {
      return {
        ...raw,
        out_of_sample_period: {
          start_date: raw.evaluation_start_date,
          end_date: raw.evaluation_end_date,
          trading_days: raw.total_evaluation_days,
        },
        rebalance_count: raw.total_rebalances,
        strategies: {
          dynamic_vine_trp: {
            total_return_gross: raw.strategy_metrics.total_return_gross ?? raw.strategy_metrics.total_return,
            total_return_net: raw.strategy_metrics.total_return_net ?? raw.strategy_metrics.total_return,
            cagr_gross: raw.strategy_metrics.cagr_gross,
            cagr_net: raw.strategy_metrics.cagr_net ?? raw.strategy_metrics.cagr,
            annualized_volatility: raw.strategy_metrics.annualized_volatility,
            annualized_volatility_gross: raw.strategy_metrics.annualized_volatility_gross ?? raw.strategy_metrics.annualized_volatility,
            annualized_volatility_net: raw.strategy_metrics.annualized_volatility_net,
            sharpe_ratio: raw.strategy_metrics.sharpe_ratio,
            sharpe_ratio_gross: raw.strategy_metrics.sharpe_ratio_gross ?? raw.strategy_metrics.sharpe_ratio,
            sharpe_ratio_net: raw.strategy_metrics.sharpe_ratio_net,
            max_drawdown: raw.strategy_metrics.max_drawdown,
            cvar_99: raw.strategy_metrics.historical_cvar_99,
            l_var_99: raw.strategy_metrics.l_var_99,
            l_cvar_99: raw.strategy_metrics.l_cvar_99,
            stressed_l_var_99: raw.strategy_metrics.stressed_l_var_99,
            stressed_l_cvar_99: raw.strategy_metrics.stressed_l_cvar_99,
            average_cash_weight: raw.strategy_metrics.average_cash_weight,
            cumulative_turnover: raw.strategy_metrics.total_turnover,
            total_transaction_costs: raw.strategy_metrics.total_transaction_costs,
            total_spread_costs: raw.strategy_metrics.total_spread_costs,
            total_market_impact_costs: raw.strategy_metrics.total_market_impact_costs,
            total_commission_costs: raw.strategy_metrics.total_commission_costs,
            max_participation_rate_observed: raw.strategy_metrics.max_participation_rate_observed,
            participation_warnings_count: raw.strategy_metrics.participation_warnings_count,
          },
          equal_weight: {
            total_return_gross: raw.benchmark_metrics.total_return_gross ?? raw.benchmark_metrics.total_return,
            total_return_net: raw.benchmark_metrics.total_return_net ?? raw.benchmark_metrics.total_return,
            cagr_gross: raw.benchmark_metrics.cagr_gross,
            cagr_net: raw.benchmark_metrics.cagr_net ?? raw.benchmark_metrics.cagr,
            annualized_volatility: raw.benchmark_metrics.annualized_volatility,
            annualized_volatility_gross: raw.benchmark_metrics.annualized_volatility_gross ?? raw.benchmark_metrics.annualized_volatility,
            annualized_volatility_net: raw.benchmark_metrics.annualized_volatility_net,
            sharpe_ratio: raw.benchmark_metrics.sharpe_ratio,
            sharpe_ratio_gross: raw.benchmark_metrics.sharpe_ratio_gross ?? raw.benchmark_metrics.sharpe_ratio,
            sharpe_ratio_net: raw.benchmark_metrics.sharpe_ratio_net,
            max_drawdown: raw.benchmark_metrics.max_drawdown,
            cvar_99: raw.benchmark_metrics.historical_cvar_99,
            cumulative_turnover: raw.benchmark_metrics.total_turnover,
            total_transaction_costs: raw.benchmark_metrics.total_transaction_costs,
          },
          static_vine_trp: {
            total_return_gross: raw.static_trp_metrics.total_return_gross ?? raw.static_trp_metrics.total_return,
            total_return_net: raw.static_trp_metrics.total_return_net ?? raw.static_trp_metrics.total_return,
            cagr_gross: raw.static_trp_metrics.cagr_gross,
            cagr_net: raw.static_trp_metrics.cagr_net ?? raw.static_trp_metrics.cagr,
            annualized_volatility: raw.static_trp_metrics.annualized_volatility,
            annualized_volatility_gross: raw.static_trp_metrics.annualized_volatility_gross ?? raw.static_trp_metrics.annualized_volatility,
            annualized_volatility_net: raw.static_trp_metrics.annualized_volatility_net,
            sharpe_ratio: raw.static_trp_metrics.sharpe_ratio,
            sharpe_ratio_gross: raw.static_trp_metrics.sharpe_ratio_gross ?? raw.static_trp_metrics.sharpe_ratio,
            sharpe_ratio_net: raw.static_trp_metrics.sharpe_ratio_net,
            max_drawdown: raw.static_trp_metrics.max_drawdown,
            cvar_99: raw.static_trp_metrics.historical_cvar_99,
            cumulative_turnover: raw.static_trp_metrics.total_turnover,
            total_transaction_costs: raw.static_trp_metrics.total_transaction_costs,
          },
        },
        equity_curves: (raw.equity_curve || []).map((pt: any) => ({
          date: pt.date,
          dynamic_vine_trp: pt.strategy_equity,
          equal_weight: pt.benchmark_equity,
          static_vine_trp: pt.static_trp_equity,
        })),
        rebalance_events: (raw.rebalance_history || []).map((evt: any) => ({
          date: evt.date,
          training_window_start: evt.training_window_start,
          training_window_end: evt.training_window_end,
          requested_weights: evt.requested_weights,
          executed_weights: evt.executed_weights || evt.weights,
          target_weights: evt.weights,
          pre_trade_weights: evt.weights,
          turnover: evt.turnover,
          cost: evt.transaction_cost,
          spread_cost: evt.spread_cost,
          market_impact_cost: evt.market_impact_cost,
          commission_cost: evt.commission_cost,
          liquidity_adjusted_cvar: evt.liquidity_adjusted_cvar,
          liquidity_adjusted_var: evt.liquidity_adjusted_var,
          stressed_liquidity_adjusted_cvar: evt.stressed_liquidity_adjusted_cvar,
          stressed_liquidity_adjusted_var: evt.stressed_liquidity_adjusted_var,
          liquidation_cost_pct: evt.liquidation_cost_pct,
          cash_weight: evt.cash_weight,
          max_participation_rate: evt.max_participation_rate,
          participation_warning: evt.participation_warning,
          rebalance_rejected: evt.rebalance_rejected,
          adv_source: evt.adv_source,
          scheduled_days: evt.scheduled_days,
          scheduling_mode: evt.scheduling_mode,
          regime_state: evt.regime_state,
          regime_probabilities: evt.regime_probabilities,
          effective_participation_rate: evt.effective_participation_rate,
          effective_risk_aversion: evt.effective_risk_aversion,
          regime_adaptation_strength: evt.regime_adaptation_strength,
          status: evt.converged ? 'converged' : 'fallback',
        })),
        tca_report: raw.tca_report,
      };
    }
    return raw as VineBacktestResponse;
  },
};




