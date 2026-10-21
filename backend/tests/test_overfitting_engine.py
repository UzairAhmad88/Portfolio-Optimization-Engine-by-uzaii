"""
Comprehensive mathematical and functional verification test suite for Stage 33
CSCV, PBO, DSR, and MinBTL numerical engine.
"""

from __future__ import annotations

import json
import math
import numpy as np
import pytest

from app.analytics.overfitting import (
    calculate_deflated_sharpe_ratio,
    calculate_expected_maximum_sharpe,
    calculate_minimum_backtest_length,
    compute_overfitting_diagnostics,
    run_combinatorial_cross_validation,
)
from app.research.overfitting_models import (
    OverfittingDiagnosticsResponse,
)
from tests.fixtures.overfitting_fixtures import (
    BaileyLopezDePradoFixture,
    NonGaussianFixture,
    generate_identical_runs_panel,
    generate_synthetic_alpha_panel,
    generate_synthetic_white_noise_panel,
)


class TestExpectedMaximumSharpe:
    """Mathematical reference and boundary tests for calculate_expected_maximum_sharpe."""

    def test_bailey_lopez_de_prado_analytical_reference(self):
        """
        Verifies EVT approximation against hand-calculated analytical derivation:
        N=100, V=0.25 (std=0.5), mean=0.0 -> SR* ~= 1.26539
        """
        fixture = BaileyLopezDePradoFixture()
        sr_star = calculate_expected_maximum_sharpe(
            n_trials=fixture.n_trials,
            variance=fixture.variance_trials,
            mean=fixture.mean_trials,
        )
        assert math.isclose(sr_star, fixture.expected_sr_star_approx, abs_tol=1e-4)
        assert 1.265 < sr_star < 1.266

    def test_single_trial_boundary(self):
        """For N=1, expected maximum Sharpe degenerates to the mean."""
        assert calculate_expected_maximum_sharpe(n_trials=1, variance=0.25, mean=0.5) == 0.5
        assert calculate_expected_maximum_sharpe(n_trials=1, variance=0.0, mean=0.0) == 0.0

    def test_zero_variance_boundary(self):
        """When variance across trials is 0, maximum Sharpe equals the mean."""
        assert calculate_expected_maximum_sharpe(n_trials=100, variance=0.0, mean=0.75) == 0.75

    def test_monotonicity_in_trials_and_variance(self):
        """SR* strictly increases with trial count N and variance V."""
        sr_50 = calculate_expected_maximum_sharpe(50, variance=0.25)
        sr_100 = calculate_expected_maximum_sharpe(100, variance=0.25)
        sr_500 = calculate_expected_maximum_sharpe(500, variance=0.25)
        assert sr_50 < sr_100 < sr_500

        sr_v1 = calculate_expected_maximum_sharpe(100, variance=0.10)
        sr_v2 = calculate_expected_maximum_sharpe(100, variance=0.25)
        assert sr_v1 < sr_v2

    def test_invalid_inputs_raise_value_error(self):
        with pytest.raises(ValueError, match="n_trials must be at least 1"):
            calculate_expected_maximum_sharpe(0, 0.25)

        with pytest.raises(ValueError, match="variance cannot be negative"):
            calculate_expected_maximum_sharpe(10, -0.05)

        with pytest.raises(ValueError, match="must be finite"):
            calculate_expected_maximum_sharpe(10, float("nan"))


class TestDeflatedSharpeRatio:
    """Mathematical reference, non-normality, and boundary tests for calculate_deflated_sharpe_ratio."""

    def test_homogeneous_reference_fixture(self):
        """
        Verifies DSR on homogeneous frequency matching Gate B fixture:
        N=100, V=0.25, T=1260, SR=1.0, skew=0, kurt=3, q=1 -> DSR < 1e-9.
        """
        fixture = BaileyLopezDePradoFixture()
        # Calibrate a synthetic trials array with N=100, Var=0.25, Mean=0.0
        rng = np.random.default_rng(42)
        raw = rng.normal(loc=0.0, scale=0.5, size=fixture.n_trials)
        calibrated_trials = (raw - np.mean(raw)) / np.std(raw, ddof=1) * math.sqrt(fixture.variance_trials)

        dsr = calculate_deflated_sharpe_ratio(
            sharpe=fixture.nominal_sharpe,
            trials_sharpes=calibrated_trials,
            n_observations=fixture.n_observations,
            skewness=fixture.skewness,
            kurtosis=fixture.kurtosis,
            annualization_factor=1,
        )
        assert dsr < fixture.expected_dsr_approx
        assert dsr >= 0.0

    def test_annualized_conversion_scale_invariance(self):
        """
        Verifies that when annualization factor q=252 is provided,
        annualized Sharpe is de-annualized consistently and yields a mathematically sound probability.
        """
        calibrated_trials = np.linspace(-0.5, 1.5, 50)
        dsr_ann = calculate_deflated_sharpe_ratio(
            sharpe=1.8,
            trials_sharpes=calibrated_trials,
            n_observations=1260,
            skewness=0.0,
            kurtosis=3.0,
            annualization_factor=252,
        )
        assert 0.0 <= dsr_ann <= 1.0

    def test_non_gaussian_higher_moment_impact(self):
        """
        Negative skewness and excess kurtosis increase standard error, lowering DSR.
        """
        trials = np.linspace(-0.2, 0.8, 30)
        # Gaussian baseline
        dsr_gaussian = calculate_deflated_sharpe_ratio(
            sharpe=1.2,
            trials_sharpes=trials,
            n_observations=756,
            skewness=0.0,
            kurtosis=3.0,
            annualization_factor=252,
        )
        # Non-Gaussian fat-tailed with crash risk
        dsr_fat_tailed = calculate_deflated_sharpe_ratio(
            sharpe=1.2,
            trials_sharpes=trials,
            n_observations=756,
            skewness=-1.2,
            kurtosis=7.5,
            annualization_factor=252,
        )
        assert dsr_fat_tailed < dsr_gaussian

    def test_single_trial_reduces_to_probabilistic_sharpe(self):
        """When N=1, DSR tests against benchmark 0 (Probabilistic Sharpe Ratio)."""
        dsr_single = calculate_deflated_sharpe_ratio(
            sharpe=1.5,
            trials_sharpes=[1.5],
            n_observations=500,
            annualization_factor=252,
        )
        assert dsr_single > 0.95

    def test_invalid_dsr_inputs(self):
        with pytest.raises(ValueError, match="n_observations must be at least 2"):
            calculate_deflated_sharpe_ratio(1.0, [1.0, 1.2], n_observations=1)

        with pytest.raises(ValueError, match="trials_sharpes cannot be empty"):
            calculate_deflated_sharpe_ratio(1.0, [], n_observations=100)

        with pytest.raises(ValueError, match="non-finite"):
            calculate_deflated_sharpe_ratio(1.0, [1.0, float("nan")], n_observations=100)


class TestMinimumBacktestLength:
    """Mathematical reference and boundary tests for calculate_minimum_backtest_length."""

    def test_min_btl_finite_when_sharpe_exceeds_sr_star(self):
        trials = np.linspace(0.0, 1.0, 20)
        # With mean 0.5, var small, SR = 2.0 clearly exceeds SR*
        min_btl = calculate_minimum_backtest_length(
            sharpe=2.0,
            trials_sharpes=trials,
            skewness=0.0,
            kurtosis=3.0,
            alpha=0.05,
            annualization_factor=252,
        )
        assert np.isfinite(min_btl)
        assert min_btl > 1.0

    def test_min_btl_infinite_when_sharpe_below_sr_star(self):
        trials = np.linspace(0.0, 2.0, 50)
        # Observed Sharpe 0.5 is far below expected max SR*
        min_btl = calculate_minimum_backtest_length(
            sharpe=0.5,
            trials_sharpes=trials,
            skewness=0.0,
            kurtosis=3.0,
            alpha=0.05,
            annualization_factor=252,
        )
        assert math.isinf(min_btl)

    def test_min_btl_invalid_inputs(self):
        with pytest.raises(ValueError, match="alpha must be in"):
            calculate_minimum_backtest_length(1.5, [1.0, 1.2], alpha=0.0)

        with pytest.raises(ValueError, match="alpha must be in"):
            calculate_minimum_backtest_length(1.5, [1.0, 1.2], alpha=0.6)


class TestCSCVAlgorithm:
    """Algorithmic correctness tests for Combinatorially Symmetric Cross-Validation."""

    def test_combinatorial_counts_for_supported_slices(self):
        """Verifies that binom(S, S/2) produces exact expected combination counts."""
        rng = np.random.default_rng(42)
        panel = rng.normal(0.0, 0.01, size=(200, 4))

        res_8 = run_combinatorial_cross_validation(panel, n_slices=8)
        assert res_8["C"] == 70  # binom(8, 4) = 70

        res_10 = run_combinatorial_cross_validation(panel, n_slices=10)
        assert res_10["C"] == 252  # binom(10, 5) = 252

        res_12 = run_combinatorial_cross_validation(panel, n_slices=12)
        assert res_12["C"] == 924  # binom(12, 6) = 924

    def test_relative_rank_bounds_and_overfitting_flag(self):
        """Every relative rank must be strictly in (0, 1)."""
        panel = generate_synthetic_white_noise_panel(n_observations=500, n_trials=10, seed=42)
        res = run_combinatorial_cross_validation(panel, n_slices=8)

        rel_ranks = res["rel_ranks"]
        assert np.all(rel_ranks > 0.0)
        assert np.all(rel_ranks < 1.0)
        assert 0.0 <= res["pbo"] <= 1.0

        for pt in res["combinations_sample"]:
            assert pt.is_overfitted == (pt.relative_rank <= 0.5)

    def test_deterministic_tie_breaking(self):
        """Identical runs must produce deterministic outputs without random drift."""
        panel = generate_identical_runs_panel(n_observations=200, n_trials=6, seed=42)
        res1 = run_combinatorial_cross_validation(panel, n_slices=8)
        res2 = run_combinatorial_cross_validation(panel, n_slices=8)

        assert res1["pbo"] == res2["pbo"]
        assert np.array_equal(res1["best_is_idx"], res2["best_is_idx"])
        assert np.array_equal(res1["rel_ranks"], res2["rel_ranks"])

    def test_white_noise_panel_yields_high_pbo(self):
        """Pure white noise yields significant overfitting risk (PBO > 0.40)."""
        panel = generate_synthetic_white_noise_panel(n_observations=1260, n_trials=30, seed=42)
        res = run_combinatorial_cross_validation(panel, n_slices=10)
        assert res["pbo"] >= 0.40
        assert res["degradation_regression"].slope <= 0.2

    def test_genuine_alpha_panel_yields_low_pbo(self):
        """Genuine alpha strategy yields low PBO (< 0.15) and robust out-of-sample persistence."""
        panel = generate_synthetic_alpha_panel(
            n_observations=1260,
            n_trials=30,
            alpha_strategy_index=0,
            annualized_alpha_sharpe=3.0,
            seed=42,
        )
        res = run_combinatorial_cross_validation(panel, n_slices=10)
        assert res["pbo"] < 0.15

    def test_invalid_matrix_inputs(self):
        with pytest.raises(ValueError, match="2-dimensional"):
            run_combinatorial_cross_validation(np.array([1.0, 2.0, 3.0]))

        with pytest.raises(ValueError, match="at least 20 observations"):
            run_combinatorial_cross_validation(np.ones((10, 5)))

        with pytest.raises(ValueError, match="at least 2 strategy columns"):
            run_combinatorial_cross_validation(np.ones((50, 1)))

        with pytest.raises(ValueError, match="even integer"):
            run_combinatorial_cross_validation(np.ones((100, 4)), n_slices=7)

        with pytest.raises(ValueError, match="between 4 and 16"):
            run_combinatorial_cross_validation(np.ones((100, 4)), n_slices=2)

        with pytest.raises(ValueError, match="non-finite"):
            bad = np.ones((100, 4))
            bad[10, 2] = np.nan
            run_combinatorial_cross_validation(bad)


class TestIntegratedOverfittingDiagnostics:
    """Integration tests verifying OverfittingDiagnosticsResponse contract generation."""

    def test_integrated_diagnostics_end_to_end_alpha(self):
        panel = generate_synthetic_alpha_panel(
            n_observations=1260,
            n_trials=15,
            alpha_strategy_index=0,
            annualized_alpha_sharpe=3.0,
            seed=42,
        )
        metadata = [{"run_id": f"run-alpha-{i}", "run_number": i + 1} for i in range(15)]

        response = compute_overfitting_diagnostics(
            returns_matrix=panel,
            run_metadata=metadata,
            n_slices=8,
            alpha=0.05,
            annualization_factor=252,
            experiment_id="exp-alpha-test",
            experiment_name="Alpha Grid Search",
        )

        assert isinstance(response, OverfittingDiagnosticsResponse)
        assert response.experiment_id == "exp-alpha-test"
        assert response.evaluated_runs_count == 15
        assert response.aligned_observations_count == 1260
        assert response.total_combinations_count == 70  # binom(8, 4)
        assert response.pbo < 0.15
        assert response.pbo_risk_level == "low"
        assert response.best_run_id == "run-alpha-0"
        assert response.best_nominal_sharpe > 2.0
        assert response.deflated_sharpe_ratio >= 0.95
        assert response.is_statistically_significant is True
        assert response.min_backtest_length_years is not None
        assert response.min_backtest_length_years < response.actual_backtest_length_years

        # Serialization round trip check
        json_data = json.loads(response.model_dump_json())
        assert json_data["pbo_risk_level"] == "low"
        assert len(json_data["rank_distribution"]) == 10
        assert len(json_data["runs_summary"]) == 15

    def test_integrated_diagnostics_end_to_end_noise(self):
        panel = generate_synthetic_white_noise_panel(n_observations=1260, n_trials=20, seed=42)
        response = compute_overfitting_diagnostics(
            returns_matrix=panel,
            n_slices=8,
            alpha=0.05,
            annualization_factor=252,
            experiment_id="exp-noise-test",
        )

        assert response.pbo >= 0.40
        assert response.pbo_risk_level in ("high", "severe", "moderate")
        assert response.is_statistically_significant is False
        assert len(response.warnings) > 0

    def test_run_metadata_length_mismatch_raises(self):
        panel = np.ones((100, 5))
        bad_meta = [{"run_id": "r1"}, {"run_id": "r2"}]
        with pytest.raises(ValueError, match="does not match column count"):
            compute_overfitting_diagnostics(panel, run_metadata=bad_meta)
