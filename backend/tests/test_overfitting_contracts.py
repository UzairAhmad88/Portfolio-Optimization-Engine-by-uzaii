"""
Contract and domain model verification suite for Stage 33
Backtest Overfitting Diagnostics, Deflated Sharpe Ratio, and CSCV.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
import numpy as np
import pytest
from pydantic import ValidationError

from app.research.overfitting_models import (
    CSCVCombinationsPoint,
    CSCVHistogramBin,
    DegradationRegression,
    OverfittingDiagnosticsRequest,
    OverfittingDiagnosticsResponse,
    RunOverfittingSummary,
    classify_pbo_risk,
)
from tests.fixtures.overfitting_fixtures import (
    BaileyLopezDePradoFixture,
    NonGaussianFixture,
    generate_identical_runs_panel,
    generate_synthetic_alpha_panel,
    generate_synthetic_white_noise_panel,
)


class TestOverfittingDomainModels:
    """
    Validates Pydantic domain models, boundary conditions, and schema constraints.
    """

    def test_overfitting_request_valid_defaults(self):
        req = OverfittingDiagnosticsRequest(experiment_id="exp-12345")
        assert req.experiment_id == "exp-12345"
        assert req.run_ids is None
        assert req.n_slices == 16
        assert req.significance_level == 0.05
        assert req.annualization_factor == 252

    def test_overfitting_request_custom_valid(self):
        req = OverfittingDiagnosticsRequest(
            experiment_id="exp-999",
            run_ids=["run-1", "run-2", "run-3"],
            n_slices=10,
            significance_level=0.01,
            annualization_factor=52,
        )
        assert req.experiment_id == "exp-999"
        assert req.run_ids == ["run-1", "run-2", "run-3"]
        assert req.n_slices == 10
        assert req.significance_level == 0.01
        assert req.annualization_factor == 52

    def test_overfitting_request_rejects_odd_slices(self):
        with pytest.raises(ValidationError, match="n_slices must be an even integer"):
            OverfittingDiagnosticsRequest(
                experiment_id="exp-123",
                n_slices=15,
            )

    def test_overfitting_request_rejects_out_of_bounds_slices(self):
        with pytest.raises(ValidationError):
            OverfittingDiagnosticsRequest(
                experiment_id="exp-123",
                n_slices=2,  # ge=4
            )

        with pytest.raises(ValidationError):
            OverfittingDiagnosticsRequest(
                experiment_id="exp-123",
                n_slices=18,  # le=16
            )

    def test_overfitting_request_rejects_invalid_alpha(self):
        with pytest.raises(ValidationError):
            OverfittingDiagnosticsRequest(
                experiment_id="exp-123",
                significance_level=0.0,
            )
        with pytest.raises(ValidationError):
            OverfittingDiagnosticsRequest(
                experiment_id="exp-123",
                significance_level=0.55,
            )

    def test_overfitting_request_run_ids_validation(self):
        # Rejects fewer than 2 runs when specified
        with pytest.raises(ValidationError, match="at least 2 distinct run IDs"):
            OverfittingDiagnosticsRequest(
                experiment_id="exp-123",
                run_ids=["single-run"],
            )

        # Rejects duplicate run IDs
        with pytest.raises(ValidationError, match="run_ids contains duplicate entries"):
            OverfittingDiagnosticsRequest(
                experiment_id="exp-123",
                run_ids=["run-1", "run-1"],
            )

        # Normalizes whitespace
        req = OverfittingDiagnosticsRequest(
            experiment_id="exp-123",
            run_ids=["  run-1  ", "run-2"],
        )
        assert req.run_ids == ["run-1", "run-2"]

    def test_classify_pbo_risk_levels(self):
        assert classify_pbo_risk(0.00) == "low"
        assert classify_pbo_risk(0.12) == "low"
        assert classify_pbo_risk(0.15) == "low"
        assert classify_pbo_risk(0.151) == "moderate"
        assert classify_pbo_risk(0.35) == "moderate"
        assert classify_pbo_risk(0.351) == "high"
        assert classify_pbo_risk(0.50) == "high"
        assert classify_pbo_risk(0.501) == "severe"
        assert classify_pbo_risk(0.95) == "severe"

    def test_diagnostics_response_json_round_trip(self):
        resp = OverfittingDiagnosticsResponse(
            experiment_id="exp-123",
            experiment_name="Momentum vs Mean Reversion Grid",
            strategy_type="target_weights",
            dataset_id="ds-555",
            snapshot_id="snap-888",
            evaluated_runs_count=50,
            aligned_observations_count=1260,
            n_slices=16,
            total_combinations_count=12870,
            pbo=0.125,
            pbo_risk_level="low",
            best_run_id="run-42",
            best_run_number=42,
            best_nominal_sharpe=2.45,
            expected_max_sharpe=1.28,
            deflated_sharpe_ratio=0.9985,
            is_statistically_significant=True,
            min_backtest_length_years=0.85,
            actual_backtest_length_years=5.0,
            skewness=-0.15,
            kurtosis=3.42,
            degradation_regression=DegradationRegression(
                slope=0.82,
                intercept=0.10,
                r_squared=0.67,
                p_value=0.0001,
                std_err=0.03,
            ),
            combinations_sample=[
                CSCVCombinationsPoint(
                    combination_id=0,
                    selected_run_id="run-42",
                    is_sharpe=2.60,
                    oos_sharpe=2.35,
                    oos_rank=48,
                    relative_rank=48 / 51,
                    is_overfitted=False,
                )
            ],
            rank_distribution=[
                CSCVHistogramBin(
                    bin_start=0.0,
                    bin_end=0.2,
                    count=500,
                    relative_frequency=500 / 12870,
                )
            ],
            runs_summary=[
                RunOverfittingSummary(
                    run_id="run-42",
                    run_number=42,
                    nominal_sharpe=2.45,
                    selection_frequency_is=0.45,
                    mean_oos_sharpe_when_selected=2.30,
                    mean_oos_rank_when_selected=0.88,
                )
            ],
            warnings=[],
            generated_at=datetime.now(timezone.utc),
        )

        json_str = resp.model_dump_json()
        data = json.loads(json_str)
        assert data["pbo"] == 0.125
        assert data["pbo_risk_level"] == "low"
        assert data["deflated_sharpe_ratio"] == 0.9985
        assert data["is_statistically_significant"] is True

        # Deserialization test
        reloaded = OverfittingDiagnosticsResponse.model_validate_json(json_str)
        assert reloaded.experiment_id == resp.experiment_id
        assert reloaded.best_nominal_sharpe == resp.best_nominal_sharpe
        assert len(reloaded.combinations_sample) == 1
        assert reloaded.combinations_sample[0].is_overfitted is False


class TestOverfittingAnalyticalFixtures:
    """
    Validates synthetic return generators and analytical benchmark fixtures.
    """

    def test_bailey_lopez_de_prado_fixture_parameters(self):
        fixture = BaileyLopezDePradoFixture()
        assert fixture.n_trials == 100
        assert fixture.variance_trials == 0.25
        assert fixture.n_observations == 1260
        assert fixture.nominal_sharpe == 1.0
        assert fixture.expected_sr_star_approx > 1.25

    def test_non_gaussian_fixture_parameters(self):
        fixture = NonGaussianFixture()
        assert fixture.skewness < 0.0
        assert fixture.kurtosis > 3.0  # Fat-tailed

    def test_synthetic_white_noise_panel_properties(self):
        panel = generate_synthetic_white_noise_panel(n_observations=1260, n_trials=50, seed=42)
        assert panel.shape == (1260, 50)
        # Check that global mean is close to 0 and std close to 0.01
        assert abs(np.mean(panel)) < 0.001
        assert abs(np.std(panel) - 0.01) < 0.001

    def test_synthetic_alpha_panel_properties(self):
        panel = generate_synthetic_alpha_panel(
            n_observations=1260,
            n_trials=50,
            alpha_strategy_index=0,
            annualized_alpha_sharpe=2.5,
            seed=42,
        )
        assert panel.shape == (1260, 50)
        # Strategy 0 should have significantly higher annualized Sharpe ratio than the others
        sr_0 = np.mean(panel[:, 0]) / np.std(panel[:, 0]) * np.sqrt(252.0)
        sr_others = [
            np.mean(panel[:, i]) / np.std(panel[:, i]) * np.sqrt(252.0)
            for i in range(1, 50)
        ]
        assert sr_0 > 1.5
        assert sr_0 > max(sr_others)

    def test_identical_runs_panel_properties(self):
        panel = generate_identical_runs_panel(n_observations=500, n_trials=10, seed=42)
        assert panel.shape == (500, 10)
        # Cross-sectional variance across columns should be zero (within floating point precision)
        row_vars = np.var(panel, axis=1)
        assert np.max(row_vars) < 1e-12
        assert np.allclose(row_vars, 0.0)
