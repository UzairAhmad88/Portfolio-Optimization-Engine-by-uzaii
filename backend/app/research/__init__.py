"""
Portfolio Research Experiments module.
"""

from app.research.fingerprint import canonical_json_dumps, compute_config_fingerprint
from app.research.models import (
    ComparisonRequest,
    ComparisonResponse,
    ComparisonRunMetricItem,
    ExperimentConfig,
    ExperimentCreateRequest,
    ExperimentListItem,
    ExperimentResponse,
    ExperimentRunListItem,
    ExperimentRunResponse,
    ExperimentUpdateRequest,
)
from app.research.service import ResearchService

__all__ = [
    "compute_config_fingerprint",
    "canonical_json_dumps",
    "ExperimentConfig",
    "ExperimentCreateRequest",
    "ExperimentUpdateRequest",
    "ExperimentResponse",
    "ExperimentListItem",
    "ExperimentRunResponse",
    "ExperimentRunListItem",
    "ComparisonRequest",
    "ComparisonResponse",
    "ComparisonRunMetricItem",
    "ResearchService",
]
