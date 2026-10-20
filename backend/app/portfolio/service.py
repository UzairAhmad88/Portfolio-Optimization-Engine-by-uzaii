"""
Portfolio construction and validation service.

Coordinates dataset asset discovery, asset selection, historical observation alignment,
cross-market currency safeguards, and investment constraint feasibility validation.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from app.market_data.service import DatasetNotFoundError, get_dataset_rows
from app.portfolio.models import (
    AssetMetadata,
    InvestmentConstraintsModel,
    PortfolioDefinition,
    PortfolioValidationReport,
)
from app.quant.constraints import (
    AssetWeightBounds,
    ConstraintInfeasibleError,
    ConstraintValidationError,
    InvestmentConstraints,
    check_constraint_feasibility,
    validate_weights_against_constraints,
)
from app.quant.portfolio import summarize_weights, validate_weights


def get_dataset_assets(dataset_id: str) -> list[AssetMetadata]:
    """
    Extracts uniquely identified assets from a registered dataset along with verified
    coverage dates, trading currency, and observation counts.

    Parameters:
        dataset_id: UUIDv4 identifier of the registered dataset.

    Returns:
        Sorted list of AssetMetadata.

    Raises:
        DatasetNotFoundError: If the dataset is not in the active registry.
    """
    rows = get_dataset_rows(dataset_id)
    if not rows:
        return []

    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        key = (str(row["ticker"]).strip().upper(), str(row["market"]).strip().upper())
        grouped[key].append(row)

    assets: list[AssetMetadata] = []
    for (ticker, market), item_rows in grouped.items():
        dates = [r["date"] for r in item_rows if r.get("date")]
        dates.sort()
        currency = str(item_rows[0].get("currency", "USD")).strip().upper()
        asset_id = f"{ticker}:{market}"

        assets.append(
            AssetMetadata(
                asset_id=asset_id,
                ticker=ticker,
                market=market,  # type: ignore[arg-type]
                currency=currency,
                start_date=dates[0] if dates else "1970-01-01",
                end_date=dates[-1] if dates else "1970-01-01",
                observation_count=len(item_rows),
            )
        )

    assets.sort(key=lambda a: (a.ticker, a.market))
    return assets


def _build_quant_constraints(
    model: InvestmentConstraintsModel,
    asset_id_map: dict[str, str],
) -> InvestmentConstraints:
    """
    Translates Pydantic InvestmentConstraintsModel into the pure domain
    InvestmentConstraints dataclass, resolving asset identifiers.
    """
    converted_bounds: dict[str, AssetWeightBounds] = {}
    for raw_key, bounds_model in model.asset_bounds.items():
        norm_key = str(raw_key).strip().upper()
        # Resolve to standardized asset_id if bare ticker was supplied
        resolved_key = asset_id_map.get(norm_key, norm_key)
        converted_bounds[resolved_key] = AssetWeightBounds(
            lower=bounds_model.lower,
            upper=bounds_model.upper,
        )

    included = [
        asset_id_map.get(str(a).strip().upper(), str(a).strip().upper())
        for a in model.included_assets
    ]
    excluded = [
        asset_id_map.get(str(a).strip().upper(), str(a).strip().upper())
        for a in model.excluded_assets
    ]

    return InvestmentConstraints(
        default_min_weight=model.default_min_weight,
        default_max_weight=model.default_max_weight,
        asset_bounds=converted_bounds,
        target_total_weight=model.target_total_weight,
        allow_short=model.allow_short,
        max_gross_exposure=model.max_gross_exposure,
        min_net_exposure=model.min_net_exposure,
        max_net_exposure=model.max_net_exposure,
        included_assets=included,
        excluded_assets=excluded,
    )


def validate_portfolio_definition(
    portfolio: PortfolioDefinition,
) -> PortfolioValidationReport:
    """
    Performs comprehensive multi-layer validation of a portfolio definition:
    1. Dataset verification in registry.
    2. Asset existence, identity disambiguation, and stable ordering.
    3. Historical date coverage and synchronized observation count.
    4. Cross-market currency compatibility.
    5. Mathematical constraint feasibility checks.
    6. Explicit weight validation against constraints (if weights provided).

    Returns:
        PortfolioValidationReport with is_valid status and diagnostic details.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Dataset existence
    try:
        available_assets = get_dataset_assets(portfolio.dataset_id)
        raw_rows = get_dataset_rows(portfolio.dataset_id)
    except DatasetNotFoundError as exc:
        return PortfolioValidationReport(
            is_valid=False,
            portfolio_name=portfolio.name,
            dataset_id=portfolio.dataset_id,
            selected_assets=portfolio.assets,
            asset_details=[],
            currency_policy={"error": str(exc)},
            date_coverage={},
            weight_summary=None,
            feasibility={"is_feasible": False, "messages": [str(exc)]},
            errors=[str(exc)],
            warnings=[],
        )

    # 2. Build lookup maps for asset resolution
    # asset_id -> AssetMetadata (e.g. "AAPL:US" -> metadata)
    asset_by_id: dict[str, AssetMetadata] = {a.asset_id: a for a in available_assets}
    # ticker -> list[AssetMetadata] to check for ambiguous tickers across markets
    assets_by_ticker: dict[str, list[AssetMetadata]] = defaultdict(list)
    for a in available_assets:
        assets_by_ticker[a.ticker].append(a)

    resolved_asset_metadata: list[AssetMetadata] = []
    resolved_asset_ids: list[str] = []
    # Map for constraint lookup: both bare ticker (if unambiguous) and asset_id -> asset_id
    asset_id_map: dict[str, str] = {}

    for raw_sel in portfolio.assets:
        sel = str(raw_sel).strip().upper()
        matched_meta: AssetMetadata | None = None

        if sel in asset_by_id:
            matched_meta = asset_by_id[sel]
        elif sel in assets_by_ticker:
            candidates = assets_by_ticker[sel]
            if len(candidates) == 1:
                matched_meta = candidates[0]
            else:
                markets = [c.market for c in candidates]
                errors.append(
                    f"Ambiguous ticker '{sel}' matches multiple markets ({markets}). "
                    f"Specify the exact asset identifier (e.g. '{sel}:{markets[0]}')."
                )
                continue
        else:
            errors.append(
                f"Selected asset '{sel}' does not exist in dataset '{portfolio.dataset_id}'."
            )
            continue

        resolved_asset_metadata.append(matched_meta)
        resolved_asset_ids.append(matched_meta.asset_id)
        asset_id_map[matched_meta.asset_id] = matched_meta.asset_id
        asset_id_map[matched_meta.ticker] = matched_meta.asset_id

    # 3. Currency and Cross-Market Safeguards
    currencies_present = sorted({a.currency for a in resolved_asset_metadata})
    is_multi_currency = len(currencies_present) > 1

    currency_policy: dict[str, Any] = {
        "currencies_present": currencies_present,
        "is_multi_currency": is_multi_currency,
        "base_currency": portfolio.base_currency
        or (currencies_present[0] if currencies_present else None),
    }

    if is_multi_currency:
        errors.append(
            f"Selected assets span multiple currencies ({', '.join(currencies_present)}). "
            "Cross-currency portfolio aggregation is disabled until an explicit FX conversion series "
            "and base-currency policy are implemented."
        )

    # 4. Date Coverage & Aligned Observation Validation
    date_coverage: dict[str, Any] = {}
    if (
        portfolio.start_date
        and portfolio.end_date
        and portfolio.start_date > portfolio.end_date
    ):
        errors.append(
            f"Invalid historical period: start_date ({portfolio.start_date}) is after end_date ({portfolio.end_date})."
        )
    elif resolved_asset_metadata:
        # Check intersection of trading dates for selected assets
        dates_per_asset: dict[str, set[str]] = defaultdict(set)
        for r in raw_rows:
            row_asset_id = f"{r['ticker']}:{r['market']}"
            if row_asset_id in resolved_asset_ids:
                row_d = date.fromisoformat(r["date"])
                if portfolio.start_date and row_d < portfolio.start_date:
                    continue
                if portfolio.end_date and row_d > portfolio.end_date:
                    continue
                dates_per_asset[row_asset_id].add(r["date"])

        common_dates: set[str] = set()
        if dates_per_asset and len(dates_per_asset) == len(resolved_asset_ids):
            common_dates = set.intersection(*dates_per_asset.values())

        sorted_common = sorted(common_dates)
        date_coverage = {
            "requested_start_date": portfolio.start_date.isoformat()
            if portfolio.start_date
            else None,
            "requested_end_date": portfolio.end_date.isoformat()
            if portfolio.end_date
            else None,
            "common_observation_count": len(sorted_common),
            "effective_start_date": sorted_common[0] if sorted_common else None,
            "effective_end_date": sorted_common[-1] if sorted_common else None,
        }

        if len(sorted_common) < 2:
            errors.append(
                f"Selected assets share {len(sorted_common)} common trading observation dates in the requested window. "
                "At least 2 synchronized observations are required to calculate returns and risk metrics."
            )
        elif len(sorted_common) < len(resolved_asset_ids) + 1:
            warnings.append(
                f"Observation count ({len(sorted_common)}) is relatively small for {len(resolved_asset_ids)} assets. "
                "Sample covariance matrix may be rank-deficient or ill-conditioned."
            )

    # 5. Mathematical Constraint Feasibility Checks
    feasibility_summary: dict[str, Any] = {"is_feasible": False, "messages": []}
    quant_constraints: InvestmentConstraints | None = None

    if resolved_asset_ids:
        try:
            quant_constraints = _build_quant_constraints(
                portfolio.constraints, asset_id_map
            )
            feas_report = check_constraint_feasibility(
                resolved_asset_ids, quant_constraints
            )
            feasibility_summary = {
                "is_feasible": feas_report.is_feasible,
                "sum_lower_bounds": feas_report.sum_lower_bounds,
                "sum_upper_bounds": feas_report.sum_upper_bounds,
                "target_total_weight": feas_report.target_total_weight,
                "resolved_bounds": {
                    k: {"lower": v[0], "upper": v[1]}
                    for k, v in feas_report.resolved_bounds.items()
                },
                "messages": feas_report.messages,
            }
            if not feas_report.is_feasible:
                errors.extend(feas_report.messages)
        except (
            ConstraintInfeasibleError,
            ConstraintValidationError,
            ValueError,
        ) as exc:
            feasibility_summary = {"is_feasible": False, "messages": [str(exc)]}
            errors.append(f"Constraint configuration error: {exc}")

    # 6. Weight Validation (if explicit weights provided)
    weight_summary_dict: dict[str, Any] | None = None
    if portfolio.weights is not None and resolved_asset_ids:
        # Standardize weights keys to resolved asset IDs or tickers
        mapped_weights: dict[str, float] = {}
        for raw_k, w in portfolio.weights.items():
            norm_k = str(raw_k).strip().upper()
            resolved_k = asset_id_map.get(norm_k, norm_k)
            mapped_weights[resolved_k] = float(w)

        try:
            w_series = validate_weights(
                mapped_weights, expected_assets=resolved_asset_ids
            )
            w_summary = summarize_weights(w_series)
            weight_summary_dict = {
                "asset_count": w_summary.asset_count,
                "total_weight": w_summary.total_weight,
                "gross_exposure": w_summary.gross_exposure,
                "net_exposure": w_summary.net_exposure,
                "is_fully_invested": w_summary.is_fully_invested,
                "is_long_only": w_summary.is_long_only,
                "has_short_positions": w_summary.has_short_positions,
                "max_weight": w_summary.max_weight,
                "min_weight": w_summary.min_weight,
            }

            if quant_constraints is not None:
                violations = validate_weights_against_constraints(
                    mapped_weights, resolved_asset_ids, quant_constraints
                )
                errors.extend(violations)

        except (ValueError, TypeError) as exc:
            errors.append(f"Weight validation failed: {exc}")

    is_valid = len(errors) == 0

    return PortfolioValidationReport(
        is_valid=is_valid,
        portfolio_name=portfolio.name,
        dataset_id=portfolio.dataset_id,
        selected_assets=portfolio.assets,
        asset_details=resolved_asset_metadata,
        currency_policy=currency_policy,
        date_coverage=date_coverage,
        weight_summary=weight_summary_dict,
        feasibility=feasibility_summary,
        errors=errors,
        warnings=warnings,
    )
