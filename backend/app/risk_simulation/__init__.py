"""
Monte Carlo portfolio risk simulation and probabilistic risk analysis package.
"""

from app.risk_simulation.engine import (
    compute_distribution_histogram,
    downsample_trajectories,
    generate_multivariate_returns,
    project_covariance_psd,
    simulate_portfolio_wealth,
)
from app.risk_simulation.models import (
    DistributionBin,
    DistributionModel,
    MultiEstimatorComparison,
    RebalancePolicy,
    RiskSimulationListItem,
    RiskSimulationRequest,
    RiskSimulationResponse,
    RiskSimulationSummary,
    SimulationPathPoint,
    VaRCVaREstimate,
    VaRCVaRStandaloneRequest,
)
from app.risk_simulation.service import (
    calculate_standalone_var_cvar,
    delete_risk_simulation,
    execute_risk_simulation,
    get_risk_simulation,
    list_risk_simulations,
    prepare_simulation_data,
)

__all__ = [
    "DistributionBin",
    "DistributionModel",
    "MultiEstimatorComparison",
    "RebalancePolicy",
    "RiskSimulationListItem",
    "RiskSimulationRequest",
    "RiskSimulationResponse",
    "RiskSimulationSummary",
    "SimulationPathPoint",
    "VaRCVaREstimate",
    "VaRCVaRStandaloneRequest",
    "compute_distribution_histogram",
    "delete_risk_simulation",
    "downsample_trajectories",
    "execute_risk_simulation",
    "generate_multivariate_returns",
    "get_risk_simulation",
    "list_risk_simulations",
    "prepare_simulation_data",
    "project_covariance_psd",
    "simulate_portfolio_wealth",
]
