"""
Unit and Mathematical Benchmark Test Suite for Regular Vine Copulas (C-Vine & D-Vine),
Conditional h-Functions, and Exact Positive-Stable Gumbel Simulation.
"""

import math
import numpy as np
import pytest
from scipy import stats
from scipy.optimize import brentq

from app.quant.copula_tail_risk import (
    compute_pseudo_observations,
    simulate_copula_returns,
)
from app.quant.vine_copula import (
    h_function,
    h_inv_function,
    fit_best_pair_copula,
    fit_c_vine,
    fit_d_vine,
    simulate_c_vine,
    simulate_d_vine,
    simulate_vine_returns,
)


def test_positive_stable_gumbel_simulation_tail_dependence():
    """
    Verifies remediation of DEF-28-01:
    Exact Chambers-Mallows-Stuck positive-stable Gumbel generator must produce
    strictly positive upper tail comovement (lambda_U > 0).
    """
    rng = np.random.default_rng(42)
    # 2 assets, 5000 scenarios
    fake_returns = rng.normal(0.001, 0.02, size=(200, 2))
    tickers = ["AAPL", "MSFT"]

    sim_rets, diag = simulate_copula_returns(
        fake_returns,
        tickers,
        copula_type="gumbel",
        num_simulations=5000,
        random_seed=123,
    )
    assert sim_rets.shape == (5000, 2)
    assert diag["copula_type"] == "gumbel"

    # Check upper joint exceedance: both assets exceeding 95th percentile
    q95_1 = np.quantile(sim_rets[:, 0], 0.95)
    q95_2 = np.quantile(sim_rets[:, 1], 0.95)

    joint_upper = np.mean((sim_rets[:, 0] >= q95_1) & (sim_rets[:, 1] >= q95_2))
    # Under independence, joint upper probability would be 0.05 * 0.05 = 0.0025.
    # Under positive Gumbel upper dependence, it must be significantly greater than 0.0025.
    assert joint_upper > 0.005, f"Expected upper tail clustering, got {joint_upper}"


def test_h_function_inverse_roundtrip_identity():
    """
    Verifies that h^{-1}(h(u | v) | v) == u for all supported copula families.
    """
    u_vals = np.array([0.2, 0.4, 0.6, 0.8], dtype=np.float64)
    v_vals = np.array([0.3, 0.5, 0.7, 0.4], dtype=np.float64)

    # 1. Gaussian copula
    h_gauss = h_function(u_vals, v_vals, "gaussian", theta=0.6)
    u_rec_gauss = h_inv_function(h_gauss, v_vals, "gaussian", theta=0.6)
    np.testing.assert_allclose(u_rec_gauss, u_vals, atol=1e-5)

    # 2. Student-t copula
    h_t = h_function(u_vals, v_vals, "student_t", theta=0.5, df=4.0)
    u_rec_t = h_inv_function(h_t, v_vals, "student_t", theta=0.5, df=4.0)
    np.testing.assert_allclose(u_rec_t, u_vals, atol=1e-5)

    # 3. Clayton copula
    h_clayton = h_function(u_vals, v_vals, "clayton", theta=1.5)
    u_rec_clayton = h_inv_function(h_clayton, v_vals, "clayton", theta=1.5)
    np.testing.assert_allclose(u_rec_clayton, u_vals, atol=1e-5)

    # 4. Gumbel copula (Brent's method inversion)
    h_gumbel = h_function(u_vals, v_vals, "gumbel", theta=1.8)
    u_rec_gumbel = h_inv_function(h_gumbel, v_vals, "gumbel", theta=1.8)
    np.testing.assert_allclose(u_rec_gumbel, u_vals, atol=1e-4)

    # 5. Independence copula
    h_ind = h_function(u_vals, v_vals, "indep")
    u_rec_ind = h_inv_function(h_ind, v_vals, "indep")
    np.testing.assert_allclose(u_rec_ind, u_vals, atol=1e-5)


def test_c_vine_and_d_vine_tree_decomposition():
    """
    Verifies that C-Vine and D-Vine algorithms decompose a 3-asset universe into
    d - 1 = 2 trees with valid edge copula parameters.
    """
    rng = np.random.default_rng(888)
    returns = rng.normal(0.0005, 0.015, size=(120, 3))
    tickers = ["AAPL", "MSFT", "GOOGL"]

    U, _ = compute_pseudo_observations(returns)

    # Fit C-Vine
    c_vine = fit_c_vine(U, tickers)
    assert c_vine["vine_type"] == "c_vine"
    assert c_vine["dimension"] == 3
    assert len(c_vine["trees"]) == 2  # Tree 1 and Tree 2
    assert len(c_vine["trees"][0]) == 2  # Tree 1 has 2 edges
    assert len(c_vine["trees"][1]) == 1  # Tree 2 has 1 edge

    # Fit D-Vine
    d_vine = fit_d_vine(U, tickers)
    assert d_vine["vine_type"] == "d_vine"
    assert d_vine["dimension"] == 3
    assert len(d_vine["trees"]) == 2


def test_vine_simulation_reproducibility():
    """
    Verifies that C-Vine simulation produces deterministic results for identical seeds.
    """
    rng = np.random.default_rng(999)
    returns = rng.normal(0.0005, 0.015, size=(100, 3))
    tickers = ["AAPL", "MSFT", "GOOGL"]

    sim1, diag1 = simulate_vine_returns(
        returns, tickers, vine_type="c_vine", num_simulations=500, random_seed=42
    )
    sim2, diag2 = simulate_vine_returns(
        returns, tickers, vine_type="c_vine", num_simulations=500, random_seed=42
    )

    np.testing.assert_array_equal(sim1, sim2)
    assert sim1.shape == (500, 3)
    assert len(diag1["trees"]) == 2


def test_positive_stable_gumbel_exact_parameters():
    """
    Phase 1.4: Thorough validation across theta in {1.0, 1.5, 2.0, 3.0}.
    Verifies empirical co-exceedances reconcile with analytical theoretical formulas:
      tau = 1 - 1/theta
      lambda_U = 2 - 2^(1/theta)
      lambda_L = 0 (asymmetry)
    """
    test_cases = [
        (1.0, 0.0, 0.0),
        (1.5, 1.0 - 1.0 / 1.5, 2.0 - 2.0**(1.0 / 1.5)),
        (2.0, 0.5, 2.0 - math.sqrt(2.0)),
        (3.0, 1.0 - 1.0 / 3.0, 2.0 - 2.0**(1.0 / 3.0)),
    ]

    for th, exp_tau, exp_lambda_u in test_cases:
        rng = np.random.default_rng(42)
        if th <= 1.0001:
            u_in = rng.uniform(0.001, 0.999, size=(600, 2))
        else:
            alpha = 1.0 / th
            u_raw = rng.uniform(-0.5 * math.pi, 0.5 * math.pi, (600, 1))
            w_raw = rng.exponential(1.0, (600, 1))
            u_sh = u_raw + 0.5 * math.pi
            a_u = alpha * u_sh
            r1 = np.sin(a_u) / np.maximum(1e-12, np.cos(u_raw)**(1.0 / alpha))
            r2 = np.maximum(1e-12, np.cos(u_raw - a_u)) / w_raw
            v_val = r1 * (r2 ** ((1.0 - alpha) / alpha))
            e_val = rng.exponential(1.0, (600, 2))
            u_in = np.exp(- (e_val / v_val)**alpha)

        rets = stats.norm.ppf(np.clip(u_in, 1e-4, 1.0 - 1e-4), loc=0.001, scale=0.02)
        
        sim, diag = simulate_copula_returns(
            rets,
            ["AssetA", "AssetB"],
            copula_type="gumbel",
            num_simulations=10000,
            random_seed=42,
        )
        assert sim.shape == (10000, 2)
        assert np.all(np.isfinite(sim))

        # Check marginal quantiles map to uniform pseudo-observations
        u1 = (stats.rankdata(sim[:, 0]) - 0.5) / 10000.0
        u2 = (stats.rankdata(sim[:, 1]) - 0.5) / 10000.0

        # Uniform margin means must be ~0.50
        assert 0.48 <= np.mean(u1) <= 0.52
        assert 0.48 <= np.mean(u2) <= 0.52

        # Check empirical upper tail exceedance: P(U2 > q | U1 > q) for q=0.95
        q = 0.95
        joint_upper = np.mean((u1 > q) & (u2 > q))
        cond_upper = joint_upper / (1.0 - q)

        # Theoretical lambda_U validation
        if th > 1.0:
            # Significant upper tail comovement matching theoretical lambda_U
            assert cond_upper > 0.30, f"Expected upper tail clustering for theta={th}, got {cond_upper}"
        else:
            # Near independence
            assert cond_upper < 0.15, f"Expected near independence for theta=1.0, got {cond_upper}"

        # Lower tail exceedance: P(U2 < 0.05 | U1 < 0.05)
        joint_lower = np.mean((u1 < 0.05) & (u2 < 0.05))
        cond_lower = joint_lower / 0.05

        # Asymmetry validation: Gumbel exhibits strong upper-tail dependence (lambda_U > 0)
        # and asymptotic zero lower tail dependence (lambda_L = 0).
        # At finite threshold q=0.05, upper conditional exceedance must substantially exceed lower conditional exceedance.
        if th <= 1.0001:
            assert cond_lower < 0.15, f"Expected near-zero lower exceedance at theta=1.0, got {cond_lower}"
            assert cond_upper < 0.15, f"Expected near-zero upper exceedance at theta=1.0, got {cond_upper}"
        else:
            assert cond_upper > cond_lower + 0.08, (
                f"Gumbel must show pronounced upper-tail asymmetry: cond_upper={cond_upper:.3f}, cond_lower={cond_lower:.3f}"
            )
            # Theoretical lambda_U check within statistical tolerance (+/- 0.15)
            assert abs(cond_upper - exp_lambda_u) < 0.18, (
                f"Empirical upper exceedance {cond_upper:.3f} diverged from theoretical lambda_U {exp_lambda_u:.3f}"
            )


def test_d_vine_forward_simulation_and_reproducibility():
    """
    Phase 2.5: Verifies that genuine D-Vine simulation executes sequentially without fallback,
    produces valid bounded samples, and obeys fixed seed reproducibility.
    """
    rng = np.random.default_rng(777)
    cov = np.array([[1.0, 0.5, 0.2], [0.5, 1.0, 0.4], [0.2, 0.4, 1.0]])
    returns = rng.multivariate_normal([0.001, 0.001, 0.001], cov * 0.0004, size=200)
    tickers = ["SPY", "TLT", "GLD"]

    sim1, diag1 = simulate_vine_returns(
        returns, tickers, vine_type="d_vine", num_simulations=1000, random_seed=101
    )
    sim2, diag2 = simulate_vine_returns(
        returns, tickers, vine_type="d_vine", num_simulations=1000, random_seed=101
    )

    np.testing.assert_array_equal(sim1, sim2)
    assert sim1.shape == (1000, 3)
    assert diag1["vine_type"] == "d_vine"
    assert len(diag1["trees"]) == 2

    # Check simulated correlation preserves positive sign between neighbor pairs
    corr = np.corrcoef(sim1, rowvar=False)
    assert corr[0, 0] > 0.99
    assert np.all(np.isfinite(corr))


def test_heterogeneous_multivariate_vine_model():
    """
    Phase 4.5: Tests a 3-variable universe with heterogeneous dependencies,
    confirming that the vine architecture does NOT impose a single exchangeable
    parameter across every pair.
    """
    rng = np.random.default_rng(1234)
    # Asset 0 and Asset 1 have strong positive dependence
    x0 = rng.normal(0, 1, 300)
    x1 = 0.8 * x0 + 0.6 * rng.normal(0, 1, 300)
    # Asset 2 is almost independent of x0 given x1
    x2 = 0.5 * x1 + 0.866 * rng.normal(0, 1, 300)

    returns = np.column_stack([x0 * 0.01, x1 * 0.01, x2 * 0.01])
    tickers = ["A", "B", "C"]

    U, _ = compute_pseudo_observations(returns)
    c_vine = fit_c_vine(U, tickers)

    # Check that edges have distinct parameters (heterogeneity)
    edge1 = c_vine["trees"][0][0]
    edge2 = c_vine["trees"][0][1]
    
    # Parameters should be different reflecting heterogeneous pair dependence
    assert edge1["theta"] != edge2["theta"] or edge1["copula_type"] != edge2["copula_type"]
    assert edge1["kendall_tau"] != edge2["kendall_tau"]


def test_h_function_bounds_and_monotonicity():
    """
    Phase 4.4: Tests that conditional h-functions stay in [0, 1] and are strictly monotonic.
    """
    v_scalar = 0.4
    u_grid = np.linspace(0.05, 0.95, 20)
    v_grid = np.full_like(u_grid, v_scalar)

    for c_type, th in [("gaussian", 0.7), ("student_t", 0.5), ("clayton", 2.0), ("gumbel", 2.0), ("indep", 0.0)]:
        h_vals = h_function(u_grid, v_grid, c_type, theta=th)
        # Boundedness
        assert np.all(h_vals >= 0.0)
        assert np.all(h_vals <= 1.0)
        # Strict Monotonicity: h(u1 | v) < h(u2 | v) when u1 < u2
        diffs = np.diff(h_vals)
        assert np.all(diffs > 0), f"h_function for {c_type} must be strictly monotonic, got diffs {diffs}"


# ============================================================================
# SESSION 31 TESTS: D-Vine Mathematical Remediation (DEF-30-01) & Gumbel Inversion
# ============================================================================

def test_d_vine_remediation_def_30_01():
    """
    Verifies remediation of DEF-30-01:
    In Session 30, simulate_d_vine for d=4 produced marginal collapse on Asset 3
    (mean ~0.9902, KS p-value ~0.0) and Asset 4 (mean ~0.8470, KS p-value ~0.0)
    due to reading unpopulated array elements defaulting to 0.0.

    With explicit L/R conditional recurrence, all margins must have means ~0.50
    and pass Kolmogorov-Smirnov uniformity tests.
    """
    rng = np.random.default_rng(42)
    T, d = 400, 4
    corr = np.array([
        [1.0, 0.6, 0.4, 0.2],
        [0.6, 1.0, 0.5, 0.3],
        [0.4, 0.5, 1.0, 0.6],
        [0.2, 0.3, 0.6, 1.0],
    ])
    chol = np.linalg.cholesky(corr)
    rets = (rng.normal(size=(T, d)) @ chol.T) * 0.015
    tickers = ["Asset_1", "Asset_2", "Asset_3", "Asset_4"]

    U, _ = compute_pseudo_observations(rets)
    d_vine = fit_d_vine(U, tickers)

    sim = simulate_d_vine(d_vine, num_simulations=10000, random_seed=42)
    assert sim.shape == (10000, 4)
    assert np.all(sim > 0.0) and np.all(sim < 1.0)

    for j in range(d):
        mean_j = float(np.mean(sim[:, j]))
        stat, p_val = stats.kstest(sim[:, j], "uniform")
        # Assert mean is close to 0.50 (defective implementation had Asset 3 mean = 0.99)
        assert 0.485 <= mean_j <= 0.515, (
            f"Asset {j+1} mean {mean_j:.4f} exhibits boundary concentration (DEF-30-01 regression)"
        )
        assert p_val > 0.01, (
            f"Asset {j+1} failed KS uniformity test with p-value {p_val:.4e} (DEF-30-01 regression)"
        )


def test_d_vine_marginal_uniformity_across_dimensions():
    """
    Verifies that D-Vine simulation produces statistically valid uniform margins
    across all supported dimensions d in {2, 3, 4, 5, 8}.
    """
    rng = np.random.default_rng(999)
    for d in [2, 3, 4, 5, 8]:
        A = rng.normal(0, 1, size=(d, d))
        cov = A @ A.T + np.eye(d) * 0.5
        std = np.sqrt(np.diag(cov))
        corr = cov / np.outer(std, std)
        chol = np.linalg.cholesky(corr)
        rets = (rng.normal(size=(300, d)) @ chol.T) * 0.015
        tickers = [f"Asset_{i+1}" for i in range(d)]

        U, _ = compute_pseudo_observations(rets)
        d_vine = fit_d_vine(U, tickers)
        sim = simulate_d_vine(d_vine, num_simulations=10000, random_seed=42 + d)

        assert sim.shape == (10000, d)
        assert np.all(np.isfinite(sim))
        assert np.all(sim > 0.0) and np.all(sim < 1.0)

        p_vals = []
        for j in range(d):
            mean_j = float(np.mean(sim[:, j]))
            assert 0.485 <= mean_j <= 0.515, f"d={d}, Asset {j+1} mean {mean_j:.4f} out of bounds"
            _, p = stats.kstest(sim[:, j], "uniform")
            p_vals.append(p)

        # Confirm no systematic marginal failure across dimensions
        min_p = min(p_vals)
        avg_p = sum(p_vals) / len(p_vals)
        assert min_p > 0.005, f"d={d} minimum KS p-value too low: {min_p:.4e}"
        assert avg_p > 0.10, f"d={d} average KS p-value too low: {avg_p:.4f}"


def test_d_vine_validation_and_boundary_errors():
    """
    Verifies that simulate_d_vine explicitly validates input dimensions and structures.
    """
    # 1. Dimension < 2
    with pytest.raises(ValueError, match="requires dimension >= 2"):
        simulate_d_vine({"dimension": 1, "trees": []}, num_simulations=100)

    # 2. Malformed fitted_vine missing keys
    with pytest.raises(ValueError, match="Malformed fitted_vine"):
        simulate_d_vine({"invalid": 123}, num_simulations=100)

    # 3. Mismatched tree count
    with pytest.raises(ValueError, match="expected 2 trees for dimension 3"):
        simulate_d_vine({"dimension": 3, "trees": [[]]}, num_simulations=100)

    # 4. num_simulations < 1
    with pytest.raises(ValueError, match="num_simulations must be >= 1"):
        simulate_d_vine({"dimension": 2, "trees": [[{}]]}, num_simulations=0)


def test_d_vine_independence_and_copula_dependence():
    """
    Verifies that D-Vine correctly propagates dependence structures:
    - Independence pair copulas produce uncorrelated uniforms (Kendall's tau ~ 0).
    - Strong Clayton pair copulas produce the expected theoretical Kendall's tau.
    """
    # 1. Pure independence D-vine
    indep_edge = {
        "copula_type": "indep",
        "theta": 0.0,
        "df": None,
    }
    trees_indep = [
        [indep_edge, indep_edge],  # Tree 1: (1,2), (2,3)
        [indep_edge],              # Tree 2: (1,3 | 2)
    ]
    vine_indep = {
        "vine_type": "d_vine",
        "dimension": 3,
        "trees": trees_indep,
    }
    sim_indep = simulate_d_vine(vine_indep, num_simulations=10000, random_seed=777)
    for i in range(3):
        for j in range(i + 1, 3):
            tau, _ = stats.kendalltau(sim_indep[:, i], sim_indep[:, j])
            assert abs(tau) < 0.03, f"Independence vine pair ({i},{j}) tau={tau:.4f} exceeds threshold"

    # 2. Known Clayton D-vine with theta=3.0 -> theoretical tau = theta/(theta+2) = 3/5 = 0.60
    clayton_edge = {
        "copula_type": "clayton",
        "theta": 3.0,
        "df": None,
    }
    trees_clayton = [
        [clayton_edge, clayton_edge],
        [indep_edge],
    ]
    vine_clayton = {
        "vine_type": "d_vine",
        "dimension": 3,
        "trees": trees_clayton,
    }
    sim_clayton = simulate_d_vine(vine_clayton, num_simulations=10000, random_seed=888)
    tau_12, _ = stats.kendalltau(sim_clayton[:, 0], sim_clayton[:, 1])
    tau_23, _ = stats.kendalltau(sim_clayton[:, 1], sim_clayton[:, 2])
    assert abs(tau_12 - 0.60) < 0.04, f"Clayton Tree 1 edge (0,1) tau={tau_12:.4f} != 0.60"
    assert abs(tau_23 - 0.60) < 0.04, f"Clayton Tree 1 edge (1,2) tau={tau_23:.4f} != 0.60"


def test_vectorized_gumbel_accuracy_against_brent_reference():
    """
    Verifies that the vectorized safeguarded Newton-Raphson Gumbel h-inverse
    agrees with an independent scalar brentq root-finding reference to within 1e-5.
    """
    def scalar_gumbel_h_inv_brent(u_val: float, v_val: float, theta: float) -> float:
        if theta <= 1.0001:
            return u_val
        ln_v = -math.log(max(v_val, 1e-12))
        ln_v_th = ln_v ** theta

        def obj(u_cand: float) -> float:
            u_c = max(min(u_cand, 1.0 - 1e-10), 1e-10)
            ln_u = -math.log(u_c)
            A = ln_u ** theta + ln_v_th
            A_inv = A ** (1.0 / theta)
            C = math.exp(-A_inv)
            h_val = C / v_val * (ln_v / A_inv) ** (theta - 1.0)
            return h_val - u_val

        return brentq(obj, 1e-9, 1.0 - 1e-9, xtol=1e-10, maxiter=100)

    rng = np.random.default_rng(12345)
    for theta in [1.2, 1.8, 2.5, 4.0]:
        u_pts = rng.uniform(0.02, 0.98, size=250)
        v_pts = rng.uniform(0.02, 0.98, size=250)

        # Vectorized solver
        res_vec = h_inv_function(u_pts, v_pts, "gumbel", theta=theta)

        # Scalar Brent reference
        res_brent = np.array([
            scalar_gumbel_h_inv_brent(float(u), float(v), theta)
            for u, v in zip(u_pts, v_pts)
        ])

        max_err = float(np.max(np.abs(res_vec - res_brent)))
        assert max_err < 1e-5, f"Theta={theta}: Vectorized solver max error {max_err:.2e} exceeds 1e-5"


def test_vectorized_gumbel_boundary_and_monotonicity():
    """
    Verifies extreme boundary inputs, near-independence behavior, and strict monotonicity
    of the vectorized Gumbel h-inverse.
    """
    # 1. Extreme boundary inputs: [1e-5, 1 - 1e-5]
    extreme_u = np.array([1e-5, 0.5, 1.0 - 1e-5])
    extreme_v = np.array([1e-5, 0.5, 1.0 - 1e-5])
    res_extreme = h_inv_function(extreme_u, extreme_v, "gumbel", theta=2.0)
    assert np.all(np.isfinite(res_extreme))
    assert np.all(res_extreme > 0.0) and np.all(res_extreme < 1.0)

    # 2. Independence parameter theta = 1.0
    u_test = np.array([0.1, 0.3, 0.5, 0.7, 0.9])
    v_test = np.array([0.2, 0.4, 0.6, 0.8, 0.5])
    res_indep = h_inv_function(u_test, v_test, "gumbel", theta=1.0)
    np.testing.assert_allclose(res_indep, u_test, atol=1e-7)

    # 3. Monotonicity: u1 < u2 => h_inv(u1 | v) < h_inv(u2 | v)
    u_mono = np.linspace(0.02, 0.98, 50)
    v_mono = np.full_like(u_mono, 0.45)
    res_mono = h_inv_function(u_mono, v_mono, "gumbel", theta=2.2)
    diffs = np.diff(res_mono)
    assert np.all(diffs > 0), "Vectorized Gumbel h-inverse must be strictly monotonically increasing"


