"""
Unit tests for research experiment canonicalization, fingerprinting, and configuration validation.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.research.fingerprint import (
    canonical_json_dumps,
    compute_config_fingerprint,
    extract_semantic_config,
)
from app.research.models import ExperimentConfig


def test_canonical_fingerprint_deterministic_stability():
    """Identical configurations serialized repeatedly produce identical SHA-256 fingerprints."""
    cfg1 = {
        "strategy_type": "target_weights",
        "dataset_id": "dataset-123",
        "assets": ["MSFT", "AAPL", "GOOG"],
        "weights": {"GOOG": 0.2, "AAPL": 0.5, "MSFT": 0.3},
        "rebalance_frequency": "monthly",
        "transaction_cost_bps": 10.0,
        "slippage_bps": 5.0,
    }
    cfg2 = {
        # Different key order, different asset ordering, whitespace
        "transaction_cost_bps": 10.00000000,
        "weights": {"AAPL": 0.5, "MSFT": 0.3, "GOOG": 0.2},
        "assets": ["  goog ", "aapl", "msft  "],
        "strategy_type": "target_weights",
        "dataset_id": "dataset-123",
        "slippage_bps": 5.0,
        "rebalance_frequency": "monthly",
    }

    fp1 = compute_config_fingerprint(cfg1)
    fp2 = compute_config_fingerprint(cfg2)

    assert len(fp1) == 64
    assert fp1 == fp2


def test_non_semantic_fields_do_not_alter_fingerprint():
    """Metadata fields (name, description, user_id, timestamps) do not alter the fingerprint."""
    base_cfg = {
        "strategy_type": "equal_weight",
        "dataset_id": "dataset-xyz",
        "assets": ["AAPL", "NVDA"],
        "rebalance_frequency": "quarterly",
    }
    fp_base = compute_config_fingerprint(base_cfg)

    perturbed_cfg = dict(base_cfg)
    perturbed_cfg["name"] = "Different Name Alpha"
    perturbed_cfg["description"] = "Brand new hypothesis notes"
    perturbed_cfg["user_id"] = "user-999"
    perturbed_cfg["created_at"] = "2026-10-18T00:00:00Z"
    perturbed_cfg["version"] = 42

    fp_perturbed = compute_config_fingerprint(perturbed_cfg)
    assert fp_base == fp_perturbed


def test_semantic_fields_alter_fingerprint():
    """Any change to financial parameters produces a distinct fingerprint."""
    base_cfg = {
        "strategy_type": "target_weights",
        "dataset_id": "dataset-1",
        "assets": ["AAPL", "MSFT"],
        "weights": {"AAPL": 0.6, "MSFT": 0.4},
        "transaction_cost_bps": 10.0,
        "slippage_bps": 5.0,
    }
    fp_base = compute_config_fingerprint(base_cfg)

    # 1. Modify transaction costs
    cfg_cost = dict(base_cfg, transaction_cost_bps=15.0)
    assert compute_config_fingerprint(cfg_cost) != fp_base

    # 2. Modify weights
    cfg_weights = dict(base_cfg, weights={"AAPL": 0.7, "MSFT": 0.3})
    assert compute_config_fingerprint(cfg_weights) != fp_base

    # 3. Modify strategy
    cfg_strat = dict(base_cfg, strategy_type="equal_weight")
    assert compute_config_fingerprint(cfg_strat) != fp_base

    # 4. Modify seed
    cfg_seed = dict(base_cfg, seed=42)
    assert compute_config_fingerprint(cfg_seed) != fp_base


def test_experiment_config_validation_target_weights():
    """Target weights strategy validates sum of weights to 1.0."""
    # Valid
    cfg = ExperimentConfig(
        strategy_type="target_weights",
        dataset_id="ds-1",
        assets=["AAPL", "MSFT"],
        weights={"AAPL": 0.6, "MSFT": 0.4},
    )
    assert cfg.weights == {"AAPL": 0.6, "MSFT": 0.4}

    # Missing weights
    with pytest.raises(ValidationError, match="requires 'weights' dictionary"):
        ExperimentConfig(
            strategy_type="target_weights",
            dataset_id="ds-1",
            assets=["AAPL", "MSFT"],
        )

    # Weights don't sum to 1.0
    with pytest.raises(ValidationError, match="must sum to 1.0"):
        ExperimentConfig(
            strategy_type="target_weights",
            dataset_id="ds-1",
            assets=["AAPL", "MSFT"],
            weights={"AAPL": 0.5, "MSFT": 0.3},
        )


def test_experiment_config_validation_equal_weight():
    """Equal weight automatically distributes 1/N weights."""
    cfg = ExperimentConfig(
        strategy_type="equal_weight",
        dataset_id="ds-1",
        assets=["AAPL", "MSFT", "GOOG", "AMZN"],
    )
    assert len(cfg.weights) == 4
    for w in cfg.weights.values():
        assert abs(w - 0.25) < 1e-6


def test_experiment_config_validation_benchmark_attribution():
    """Benchmark attribution requires benchmark_asset."""
    # Valid
    cfg = ExperimentConfig(
        strategy_type="benchmark_attribution",
        dataset_id="ds-1",
        assets=["AAPL", "MSFT"],
        benchmark_asset="SPY",
    )
    assert cfg.benchmark_asset == "SPY"

    # Missing benchmark_asset
    with pytest.raises(ValidationError, match="requires 'benchmark_asset'"):
        ExperimentConfig(
            strategy_type="benchmark_attribution",
            dataset_id="ds-1",
            assets=["AAPL", "MSFT"],
        )


def test_experiment_config_duplicate_assets_rejected():
    """Duplicate assets in universe are strictly rejected."""
    with pytest.raises(ValidationError, match="Assets list contains duplicate tickers"):
        ExperimentConfig(
            strategy_type="equal_weight",
            dataset_id="ds-1",
            assets=["AAPL", "MSFT", "AAPL"],
        )


def test_experiment_config_invalid_date_range():
    """Start date after end date is rejected."""
    with pytest.raises(ValidationError, match="start_date .* cannot be after end_date"):
        ExperimentConfig(
            strategy_type="equal_weight",
            dataset_id="ds-1",
            assets=["AAPL", "MSFT"],
            start_date="2024-01-01",
            end_date="2023-01-01",
        )
