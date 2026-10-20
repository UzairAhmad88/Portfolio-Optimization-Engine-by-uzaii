"""
Portfolio construction and constraint management package.
"""

from app.portfolio.models import (
    AssetMetadata,
    EfficientFrontierRequest,
    EfficientFrontierResponse,
    FrontierPointModel,
    InvestmentConstraintsModel,
    OptimizationRequest,
    OptimizationResponse,
    PortfolioComparisonItemModel,
    PortfolioComparisonRequest,
    PortfolioComparisonResponse,
    PortfolioDefinition,
    PortfolioMetricsModel,
    PortfolioRiskSummaryModel,
    PortfolioValidationReport,
    SolverDiagnosticsModel,
    WeightBoundsModel,
)
from app.portfolio.optimization_service import (
    execute_efficient_frontier,
    execute_portfolio_comparison,
    execute_portfolio_optimization,
)
from app.portfolio.service import (
    get_dataset_assets,
    validate_portfolio_definition,
)

__all__ = [
    "AssetMetadata",
    "EfficientFrontierRequest",
    "EfficientFrontierResponse",
    "FrontierPointModel",
    "InvestmentConstraintsModel",
    "OptimizationRequest",
    "OptimizationResponse",
    "PortfolioComparisonItemModel",
    "PortfolioComparisonRequest",
    "PortfolioComparisonResponse",
    "PortfolioDefinition",
    "PortfolioMetricsModel",
    "PortfolioRiskSummaryModel",
    "PortfolioValidationReport",
    "SolverDiagnosticsModel",
    "WeightBoundsModel",
    "execute_efficient_frontier",
    "execute_portfolio_comparison",
    "execute_portfolio_optimization",
    "get_dataset_assets",
    "validate_portfolio_definition",
]
