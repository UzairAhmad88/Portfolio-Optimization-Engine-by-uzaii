"""
Quantitative investment constraint engine and feasibility validator.

Provides mathematically rigorous, pure domain models and algorithms for
weight bounds, portfolio-level exposure constraints, and pre-optimization
feasibility validation.

Independent of web frameworks or external I/O.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np


class ConstraintInfeasibleError(ValueError):
    """Raised when an investment constraint configuration is mathematically impossible."""


class ConstraintValidationError(ValueError):
    """Raised when constraint parameters are malformed or invalid."""


@dataclass(frozen=True)
class AssetWeightBounds:
    """
    Lower and upper allocation bounds for a single asset:
        l_i <= w_i <= u_i
    """

    lower: float
    upper: float

    def __post_init__(self) -> None:
        if not np.isfinite(self.lower):
            raise ConstraintValidationError(
                f"Lower bound must be finite, got {self.lower}."
            )
        if not np.isfinite(self.upper):
            raise ConstraintValidationError(
                f"Upper bound must be finite, got {self.upper}."
            )
        if self.lower > self.upper:
            raise ConstraintInfeasibleError(
                f"Lower bound ({self.lower}) cannot exceed upper bound ({self.upper})."
            )


@dataclass(frozen=True)
class InvestmentConstraints:
    """
    Complete investment constraint configuration for portfolio construction.

    Attributes:
        default_min_weight: Default lower bound for assets where no specific bound is given.
        default_max_weight: Default upper bound for assets where no specific bound is given.
        asset_bounds: Explicit per-asset overrides mapping asset_id -> AssetWeightBounds.
        target_total_weight: Target sum of weights (1.0 for fully invested).
        allow_short: Whether negative weights are permitted. If False, all lower bounds must be >= 0.
        max_gross_exposure: Maximum sum of absolute weights sum(|w_i|). Defaults to target_total_weight if None.
        min_net_exposure: Minimum net exposure sum(w_i). If None, target_total_weight is used.
        max_net_exposure: Maximum net exposure sum(w_i). If None, target_total_weight is used.
        included_assets: Assets required to be present in the portfolio (w_i > 0).
        excluded_assets: Assets barred from allocation (w_i = 0).
    """

    default_min_weight: float = 0.0
    default_max_weight: float = 1.0
    asset_bounds: dict[str, AssetWeightBounds] = field(default_factory=dict)
    target_total_weight: float = 1.0
    allow_short: bool = False
    max_gross_exposure: float | None = None
    min_net_exposure: float | None = None
    max_net_exposure: float | None = None
    included_assets: list[str] = field(default_factory=list)
    excluded_assets: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not np.isfinite(self.default_min_weight):
            raise ConstraintValidationError(
                "default_min_weight must be a finite number."
            )
        if not np.isfinite(self.default_max_weight):
            raise ConstraintValidationError(
                "default_max_weight must be a finite number."
            )
        if self.default_min_weight > self.default_max_weight:
            raise ConstraintInfeasibleError(
                f"default_min_weight ({self.default_min_weight}) exceeds default_max_weight ({self.default_max_weight})."
            )
        if not self.allow_short and self.default_min_weight < -1e-12:
            raise ConstraintInfeasibleError(
                f"default_min_weight ({self.default_min_weight}) is negative but allow_short is False."
            )
        if not np.isfinite(self.target_total_weight):
            raise ConstraintValidationError(
                "target_total_weight must be a finite number."
            )

        if self.max_gross_exposure is not None:
            if not np.isfinite(self.max_gross_exposure) or self.max_gross_exposure <= 0:
                raise ConstraintValidationError(
                    "max_gross_exposure must be a strictly positive finite number."
                )
            if self.max_gross_exposure < abs(self.target_total_weight) - 1e-6:
                raise ConstraintInfeasibleError(
                    f"max_gross_exposure ({self.max_gross_exposure}) cannot be less than absolute target total weight ({abs(self.target_total_weight)})."
                )


@dataclass(frozen=True)
class FeasibilityReport:
    """
    Audit report from pre-optimization mathematical feasibility checks.
    """

    is_feasible: bool
    resolved_bounds: dict[str, tuple[float, float]]
    sum_lower_bounds: float
    sum_upper_bounds: float
    target_total_weight: float
    messages: list[str]


def resolve_asset_bounds(
    assets: Sequence[str],
    constraints: InvestmentConstraints,
) -> dict[str, AssetWeightBounds]:
    """
    Resolves effective [lower, upper] bounds for every asset in the portfolio,
    taking into account defaults, per-asset overrides, and inclusion/exclusion lists.

    Parameters:
        assets: List of unique asset identifiers in the portfolio.
        constraints: InvestmentConstraints specification.

    Returns:
        Mapping of asset_id -> AssetWeightBounds.
    """
    resolved: dict[str, AssetWeightBounds] = {}
    included_set = set(constraints.included_assets)
    excluded_set = set(constraints.excluded_assets)

    overlap = included_set & excluded_set
    if overlap:
        raise ConstraintInfeasibleError(
            f"Assets cannot be simultaneously included and excluded: {sorted(overlap)}."
        )

    for asset in assets:
        if asset in excluded_set:
            # Excluded asset: forced to exactly 0.0
            resolved[asset] = AssetWeightBounds(lower=0.0, upper=0.0)
            continue

        if asset in constraints.asset_bounds:
            b = constraints.asset_bounds[asset]
            lower = b.lower
            upper = b.upper
        else:
            lower = constraints.default_min_weight
            upper = constraints.default_max_weight

        # Check short restriction
        if not constraints.allow_short and lower < -1e-12:
            raise ConstraintInfeasibleError(
                f"Asset '{asset}' has negative lower bound ({lower}) but allow_short is False."
            )

        # Check inclusion restriction
        if asset in included_set:
            if upper <= 0.0:
                raise ConstraintInfeasibleError(
                    f"Asset '{asset}' is in included_assets but has maximum weight upper bound <= 0.0 ({upper})."
                )
            if lower <= 0.0:
                # Ensure minimum positive weight if not specified
                lower = max(lower, 1e-4)

        resolved[asset] = AssetWeightBounds(lower=lower, upper=upper)

    return resolved


def check_constraint_feasibility(
    assets: Sequence[str],
    constraints: InvestmentConstraints,
) -> FeasibilityReport:
    """
    Performs pre-optimization mathematical feasibility checks on asset bounds
    and total weight limits.

    Checks:
    1. Per-asset bounds consistency: l_i <= u_i for all assets.
    2. Aggregate lower bound feasibility: sum(l_i) <= target_total_weight.
    3. Aggregate upper bound feasibility: sum(u_i) >= target_total_weight.
    4. Gross exposure feasibility vs absolute target weight.

    Parameters:
        assets: Sequence of asset identifiers.
        constraints: Investment constraints to evaluate.

    Returns:
        FeasibilityReport indicating feasibility status, resolved bounds, and explanatory messages.

    Raises:
        ConstraintInfeasibleError: If raise_on_infeasible is required or configuration is impossible.
    """
    if not assets:
        raise ConstraintValidationError(
            "Asset list cannot be empty for feasibility check."
        )

    if len(assets) != len(set(assets)):
        duplicates = [a for a in assets if assets.count(a) > 1]
        raise ConstraintValidationError(
            f"Duplicate asset identifiers found: {sorted(set(duplicates))}."
        )

    messages: list[str] = []
    is_feasible = True

    try:
        resolved = resolve_asset_bounds(assets, constraints)
    except (ConstraintInfeasibleError, ConstraintValidationError) as exc:
        return FeasibilityReport(
            is_feasible=False,
            resolved_bounds={},
            sum_lower_bounds=0.0,
            sum_upper_bounds=0.0,
            target_total_weight=constraints.target_total_weight,
            messages=[str(exc)],
        )

    sum_l = float(sum(b.lower for b in resolved.values()))
    sum_u = float(sum(b.upper for b in resolved.values()))
    target = float(constraints.target_total_weight)

    # Tolerance for floating-point comparisons
    tol = 1e-6

    if sum_l > target + tol:
        is_feasible = False
        messages.append(
            f"Infeasible bounds: sum of lower bounds ({sum_l:.4f}) exceeds target total weight ({target:.4f}). "
            "Lower bounds are too restrictive to form a valid portfolio."
        )

    if sum_u < target - tol:
        is_feasible = False
        messages.append(
            f"Infeasible bounds: sum of upper bounds ({sum_u:.4f}) is less than target total weight ({target:.4f}). "
            "Upper bounds cap total allocation below the required investment target."
        )

    bounds_dict = {a: (b.lower, b.upper) for a, b in resolved.items()}

    return FeasibilityReport(
        is_feasible=is_feasible,
        resolved_bounds=bounds_dict,
        sum_lower_bounds=sum_l,
        sum_upper_bounds=sum_u,
        target_total_weight=target,
        messages=messages,
    )


def validate_weights_against_constraints(
    weights: Mapping[str, float] | Sequence[float],
    assets: Sequence[str],
    constraints: InvestmentConstraints,
    tolerance: float = 1e-5,
) -> list[str]:
    """
    Validates an explicit weight vector against the configured investment constraints.

    Returns:
        List of violation error messages (empty list if weights are completely valid).
    """
    violations: list[str] = []

    # Map weights to assets
    if isinstance(weights, Mapping):
        weight_dict = {k: float(v) for k, v in weights.items()}
        for a in assets:
            if a not in weight_dict:
                violations.append(f"Missing weight for asset '{a}'.")
        for k in weight_dict:
            if k not in assets:
                violations.append(f"Weight provided for unrecognized asset '{k}'.")
        if violations:
            return violations
    else:
        if len(weights) != len(assets):
            return [
                f"Weight count ({len(weights)}) does not match asset count ({len(assets)})."
            ]
        weight_dict = {assets[i]: float(weights[i]) for i in range(len(assets))}

    # Check non-finite
    for a, w in weight_dict.items():
        if not np.isfinite(w):
            violations.append(f"Weight for asset '{a}' is not a finite number: {w}.")
    if violations:
        return violations

    # Check bounds
    resolved = resolve_asset_bounds(assets, constraints)
    for a, w in weight_dict.items():
        b = resolved[a]
        if w < b.lower - tolerance:
            violations.append(
                f"Asset '{a}' weight ({w:.6f}) is below lower bound ({b.lower:.6f})."
            )
        if w > b.upper + tolerance:
            violations.append(
                f"Asset '{a}' weight ({w:.6f}) exceeds upper bound ({b.upper:.6f})."
            )

    # Check total weight
    total_w = sum(weight_dict.values())
    target = constraints.target_total_weight
    if abs(total_w - target) > tolerance:
        violations.append(
            f"Total portfolio weight ({total_w:.6f}) does not match target ({target:.6f}) within tolerance {tolerance}."
        )

    # Check gross exposure
    if constraints.max_gross_exposure is not None:
        gross = sum(abs(w) for w in weight_dict.values())
        if gross > constraints.max_gross_exposure + tolerance:
            violations.append(
                f"Gross exposure ({gross:.6f}) exceeds maximum allowed ({constraints.max_gross_exposure:.6f})."
            )

    # Check long-only
    if not constraints.allow_short:
        for a, w in weight_dict.items():
            if w < -tolerance:
                violations.append(
                    f"Short position in asset '{a}' ({w:.6f}) violates long-only constraint."
                )

    return violations
