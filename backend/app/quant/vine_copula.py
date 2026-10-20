"""
Pure Numerical Financial Mathematics Engine for Regular Vine Copulas (C-Vine & D-Vine),
Pair-Copula Constructions (PCC), Conditional h-Functions, and Vine Tail Risk Parity Allocation.

Implements:
1. Conditional Distribution Functions (h-functions) and Inverse h-functions:
   - Gaussian copula h-function & inverse
   - Student-t copula h-function & inverse
   - Clayton copula h-function & inverse
   - Gumbel copula h-function & inverse (via robust root finding)
   - Independence copula h-function & inverse (identity)
2. Pair-Copula Decomposition (PCC) across Trees T_1, ..., T_{d-1}:
   - Canonical Vine (C-Vine): Root/pivot node star structure maximizing Kendall's tau tree weight.
   - D-Vine: Path structure linking ordered asset chains.
   - Automated family selection per tree edge via Akaike Information Criterion (AIC).
3. Sequential Vine Simulation:
   - Probability integral transform sampling from independent uniforms W_1, ..., W_d ~ U(0, 1).
   - Recursive inversion through inverse h-functions.
   - Mapping to empirical or parametric asset return margins.
4. Portfolio Tail Risk Measurement & Tail Risk Parity Allocation on Vine Scenarios.
"""

from __future__ import annotations

import math
from typing import Any, Literal
import numpy as np
from scipy import optimize, stats

from app.quant.copula_tail_risk import (
    compute_pseudo_observations,
    fit_clayton_copula,
    fit_gumbel_copula,
    fit_student_t_copula,
    fit_gaussian_copula,
    compute_portfolio_tail_risk,
    optimize_tail_risk_parity,
)


# ============================================================================
# Conditional Distribution Functions (h-functions) and Inverses
# ============================================================================

def h_function(
    u: np.ndarray,
    v: np.ndarray,
    copula_type: Literal["gaussian", "student_t", "clayton", "gumbel", "indep"],
    theta: float = 0.0,
    df: float = 4.0,
) -> np.ndarray:
    """
    Computes conditional distribution function h(u | v; theta) = P(U <= u | V = v) = dC(u, v)/dv.
    """
    u_c = np.clip(u, 1e-6, 1.0 - 1e-6)
    v_c = np.clip(v, 1e-6, 1.0 - 1e-6)

    if copula_type == "indep" or abs(theta) < 1e-6:
        return u_c

    elif copula_type == "gaussian":
        rho = max(-0.999, min(0.999, theta))
        z_u = stats.norm.ppf(u_c)
        z_v = stats.norm.ppf(v_c)
        denom = math.sqrt(max(1e-12, 1.0 - rho * rho))
        arg = (z_u - rho * z_v) / denom
        return np.clip(stats.norm.cdf(arg), 1e-6, 1.0 - 1e-6)

    elif copula_type == "student_t":
        rho = max(-0.999, min(0.999, theta))
        nu = max(2.1, min(40.0, df))
        t_u = stats.t.ppf(u_c, df=nu)
        t_v = stats.t.ppf(v_c, df=nu)

        # Variance of conditional distribution: (nu + t_v^2) / (nu + 1) * (1 - rho^2)
        v_term = (nu + t_v * t_v) / (nu + 1.0) * (1.0 - rho * rho)
        denom = np.sqrt(np.maximum(1e-12, v_term))
        arg = (t_u - rho * t_v) / denom
        return np.clip(stats.t.cdf(arg, df=nu + 1.0), 1e-6, 1.0 - 1e-6)

    elif copula_type == "clayton":
        th = max(0.01, min(40.0, theta))
        # h(u | v) = v^{-(theta + 1)} * (u^{-theta} + v^{-theta} - 1)^{-(1 + 1/theta)}
        base = np.power(u_c, -th) + np.power(v_c, -th) - 1.0
        base = np.maximum(1e-12, base)
        log_h = -(th + 1.0) * np.log(v_c) - (1.0 + 1.0 / th) * np.log(base)
        return np.clip(np.exp(log_h), 1e-6, 1.0 - 1e-6)

    elif copula_type == "gumbel":
        th = max(1.0, min(40.0, theta))
        if th <= 1.0001:
            return u_c
        x = -np.log(u_c)
        y = -np.log(v_c)
        A = np.power(x, th) + np.power(y, th)
        A = np.maximum(1e-12, A)
        A_inv = np.power(A, 1.0 / th)

        # C(u, v) = exp(-A^{1/th})
        # h(u | v) = C(u, v) / v * (y^{th-1} / A^{1 - 1/th})
        log_c = -A_inv
        log_term = (th - 1.0) * np.log(y) - (1.0 - 1.0 / th) * np.log(A) - np.log(v_c)
        res = np.exp(log_c + log_term)
        return np.clip(res, 1e-6, 1.0 - 1e-6)

    return u_c


def h_inv_function(
    w: np.ndarray,
    v: np.ndarray,
    copula_type: Literal["gaussian", "student_t", "clayton", "gumbel", "indep"],
    theta: float = 0.0,
    df: float = 4.0,
) -> np.ndarray:
    """
    Computes inverse conditional distribution function h^{-1}(w | v; theta) such that h(h^{-1}(w | v) | v) = w.
    """
    w_c = np.clip(w, 1e-6, 1.0 - 1e-6)
    v_c = np.clip(v, 1e-6, 1.0 - 1e-6)

    if copula_type == "indep" or abs(theta) < 1e-6:
        return w_c

    elif copula_type == "gaussian":
        rho = max(-0.999, min(0.999, theta))
        z_w = stats.norm.ppf(w_c)
        z_v = stats.norm.ppf(v_c)
        denom = math.sqrt(max(1e-12, 1.0 - rho * rho))
        z_u = rho * z_v + denom * z_w
        return np.clip(stats.norm.cdf(z_u), 1e-6, 1.0 - 1e-6)

    elif copula_type == "student_t":
        rho = max(-0.999, min(0.999, theta))
        nu = max(2.1, min(40.0, df))
        t_w = stats.t.ppf(w_c, df=nu + 1.0)
        t_v = stats.t.ppf(v_c, df=nu)
        v_term = (nu + t_v * t_v) / (nu + 1.0) * (1.0 - rho * rho)
        denom = np.sqrt(np.maximum(1e-12, v_term))
        t_u = rho * t_v + denom * t_w
        return np.clip(stats.t.cdf(t_u, df=nu), 1e-6, 1.0 - 1e-6)

    elif copula_type == "clayton":
        th = max(0.01, min(40.0, theta))
        # h^{-1}(w | v) = [ 1 + v^{-theta} * ( w^{-theta/(theta + 1)} - 1 ) ]^{-1/theta}
        exp_w = -th / (th + 1.0)
        bracket = 1.0 + np.power(v_c, -th) * (np.power(w_c, exp_w) - 1.0)
        bracket = np.maximum(1e-12, bracket)
        res = np.power(bracket, -1.0 / th)
        return np.clip(res, 1e-6, 1.0 - 1e-6)

    elif copula_type == "gumbel":
        th = max(1.0, min(40.0, theta))
        if th <= 1.0001:
            return w_c

        # Vectorized Safeguarded Newton-Raphson Solver with Bisection Bound Protection
        u = w_c.copy()
        low = np.full_like(w_c, 1e-7)
        high = np.full_like(w_c, 1.0 - 1e-7)
        active = np.ones(len(w_c), dtype=bool)

        for _ in range(25):
            u_act = u[active]
            v_act = v_c[active]
            w_act = w_c[active]

            # Vectorized evaluation of h(u | v)
            x = -np.log(u_act)
            y = -np.log(v_act)
            A = np.power(x, th) + np.power(y, th)
            A = np.maximum(1e-12, A)
            A_inv = np.power(A, 1.0 / th)

            log_h = -A_inv + (th - 1.0) * np.log(y) - (1.0 - 1.0 / th) * np.log(A) - np.log(v_act)
            h_val = np.exp(np.clip(log_h, -50.0, 50.0))
            res = h_val - w_act

            # Check convergence
            conv = np.abs(res) < 1e-6
            act_indices = np.where(active)[0]
            if np.any(conv):
                active[act_indices[conv]] = False
                not_conv = ~conv
                if not np.any(not_conv):
                    break
                u_act = u_act[not_conv]
                v_act = v_act[not_conv]
                w_act = w_act[not_conv]
                res = res[not_conv]
                x = x[not_conv]
                y = y[not_conv]
                A = A[not_conv]
                A_inv = A_inv[not_conv]
                act_indices = act_indices[not_conv]

            # Density c(u, v) = d(h)/du for Newton step
            log_c = (
                -A_inv - np.log(u_act) - np.log(v_act)
                + (th - 1.0) * (np.log(x) + np.log(y))
                - (2.0 - 1.0 / th) * np.log(A)
                + np.log(np.maximum(1e-12, A_inv + th - 1.0))
            )
            c_dens = np.exp(np.clip(log_c, -50.0, 50.0))
            c_dens = np.maximum(1e-8, c_dens)

            # Update search interval bounds
            pos = res > 0
            neg = res < 0
            high[act_indices[pos]] = np.minimum(high[act_indices[pos]], u_act[pos])
            low[act_indices[neg]] = np.maximum(low[act_indices[neg]], u_act[neg])

            # Newton step with bisection safeguard
            delta = res / c_dens
            step = u_act - delta
            bad = (step <= low[act_indices]) | (step >= high[act_indices]) | np.isnan(step)
            step[bad] = 0.5 * (low[act_indices[bad]] + high[act_indices[bad]])
            u[act_indices] = np.clip(step, 1e-7, 1.0 - 1e-7)

        # Failsafe fallback: scalar Brent on any remaining unconverged elements
        if np.any(active):
            rem_idx = np.where(active)[0]
            for idx in rem_idx:
                tgt = float(w_c[idx])
                v_val = float(v_c[idx])

                def obj(u_val: float) -> float:
                    h_arr = h_function(np.array([u_val]), np.array([v_val]), "gumbel", theta=th)
                    return float(h_arr[0]) - tgt

                try:
                    u[idx] = optimize.brentq(obj, 1e-7, 1.0 - 1e-7, xtol=1e-6)
                except Exception:
                    pass

        return np.clip(u, 1e-6, 1.0 - 1e-6)

    return w_c


# ============================================================================
# Pair-Copula Fitting for Single Edge
# ============================================================================

def fit_best_pair_copula(
    u1: np.ndarray,
    u2: np.ndarray,
    families: list[str] | None = None,
) -> dict[str, Any]:
    """
    Fits candidate copulas to a pair (u1, u2) and selects the best model via AIC.
    """
    if families is None:
        families = ["clayton", "gumbel", "student_t", "gaussian", "indep"]

    candidates: list[dict[str, Any]] = []

    # Independence copula baseline
    T = len(u1)
    candidates.append({
        "copula_type": "indep",
        "theta": 0.0,
        "kendall_tau": 0.0,
        "log_likelihood": 0.0,
        "lower_tail_dependence": 0.0,
        "upper_tail_dependence": 0.0,
        "aic": 0.0,
        "bic": 0.0,
    })

    if "clayton" in families:
        try:
            candidates.append(fit_clayton_copula(u1, u2))
        except Exception:
            pass

    if "gumbel" in families:
        try:
            candidates.append(fit_gumbel_copula(u1, u2))
        except Exception:
            pass

    if "student_t" in families:
        try:
            candidates.append(fit_student_t_copula(u1, u2))
        except Exception:
            pass

    if "gaussian" in families:
        try:
            candidates.append(fit_gaussian_copula(u1, u2))
        except Exception:
            pass

    best = min(candidates, key=lambda c: c["aic"])
    return best


# ============================================================================
# Canonical Vine (C-Vine) Architecture
# ============================================================================

def fit_c_vine(
    U: np.ndarray,
    tickers: list[str],
    families: list[str] | None = None,
) -> dict[str, Any]:
    """
    Fits a Canonical Vine (C-Vine) copula to uniform pseudo-observations U of shape (T, d).

    Tree 1: Root node connects to all d - 1 other variables.
    Tree 2: Root of tree 2 connects to d - 2 variables conditioned on tree 1 root.
    Tree m: Root of tree m connects to d - m variables conditioned on earlier roots.

    Note on Tree Selection (DOC-30-01):
        Root variable ordering is selected using a greedy heuristic based on the sum of
        absolute Kendall's tau values in Tree 1. While computationally efficient, this
        heuristic does NOT establish a globally optimal C-vine structure or guarantee
        an optimal tree sequence. Ordering choices may influence pair-copula fits,
        residual conditioning error, computational cost, and tail-dependence representation.
    """
    T, d = U.shape
    if d < 2:
        raise ValueError("C-Vine fitting requires at least 2 variables.")

    # 1. Determine root ordering by sum of absolute Kendall's taus in Tree 1
    tau_matrix = np.zeros((d, d), dtype=np.float64)
    for i in range(d):
        for j in range(i + 1, d):
            tau, _ = stats.kendalltau(U[:, i], U[:, j])
            tau_val = abs(float(tau)) if np.isfinite(tau) else 0.0
            tau_matrix[i, j] = tau_val
            tau_matrix[j, i] = tau_val

    tau_sums = np.sum(tau_matrix, axis=1)
    # Order variables from highest total dependency (pivot) to lowest
    order = list(np.argsort(-tau_sums))
    ordered_tickers = [tickers[idx] for idx in order]

    # Reorder U
    U_ordered = U[:, order]

    trees: list[list[dict[str, Any]]] = []

    # Current conditional data array: shape (d, d, T)
    # V[tree, var, :] holds conditioned pseudo-observations
    V_direct = np.zeros((d, d, T), dtype=np.float64)
    V_indirect = np.zeros((d, d, T), dtype=np.float64)

    for i in range(d):
        V_direct[0, i, :] = U_ordered[:, i]
        V_indirect[0, i, :] = U_ordered[:, i]

    for tree_idx in range(1, d):
        tree_edges: list[dict[str, Any]] = []
        root_idx = tree_idx - 1  # Root of this tree

        v_root = V_direct[tree_idx - 1, root_idx, :]

        for j in range(tree_idx, d):
            v_target = V_indirect[tree_idx - 1, j, :]

            # Fit pair copula between conditioned root and target
            fit_res = fit_best_pair_copula(v_root, v_target, families=families)

            edge_dict = {
                "tree": tree_idx,
                "node_1": ordered_tickers[root_idx],
                "node_2": ordered_tickers[j],
                "conditioned_on": ordered_tickers[:root_idx],
                "copula_type": fit_res["copula_type"],
                "theta": round(float(fit_res["theta"]), 4),
                "df": round(float(fit_res.get("df", 4.0)), 2) if "df" in fit_res else None,
                "kendall_tau": round(float(fit_res["kendall_tau"]), 4),
                "lower_tail_dependence": round(float(fit_res["lower_tail_dependence"]), 4),
                "upper_tail_dependence": round(float(fit_res["upper_tail_dependence"]), 4),
                "aic": round(float(fit_res["aic"]), 2),
            }
            tree_edges.append(edge_dict)

            # Propagate conditional distributions for next tree:
            # h(target | root) -> indirect
            c_type = fit_res["copula_type"]
            th = fit_res["theta"]
            df_val = fit_res.get("df", 4.0)

            # Direct conditioning: h(target | root)
            V_indirect[tree_idx, j, :] = h_function(v_target, v_root, c_type, theta=th, df=df_val)
            # Direct root conditioning: h(root | target)
            V_direct[tree_idx, j, :] = h_function(v_root, v_target, c_type, theta=th, df=df_val)

        trees.append(tree_edges)

    return {
        "vine_type": "c_vine",
        "ordered_tickers": ordered_tickers,
        "ordering_indices": order,
        "dimension": d,
        "trees": trees,
    }


# ============================================================================
# D-Vine Architecture
# ============================================================================

def fit_d_vine(
    U: np.ndarray,
    tickers: list[str],
    families: list[str] | None = None,
) -> dict[str, Any]:
    """
    Fits a D-Vine copula to uniform pseudo-observations U of shape (T, d).
    Tree 1 is a path: (1, 2), (2, 3), ..., (d-1, d).
    Tree m links pairs with conditioning set of size m - 1.

    Note on Tree Selection (DOC-30-01):
        Variable ordering follows the natural input ordering (order = [0, 1, ..., d-1]).
        This does NOT solve the NP-hard maximum-weight Hamiltonian path problem across
        dependence trees. The resulting D-vine is structurally valid but may be sensitive
        to the order in which assets are passed. Users should be aware that ordering affects
        intermediate conditioning error and tail-dependence modeling.
    """
    T, d = U.shape
    if d < 2:
        raise ValueError("D-Vine fitting requires at least 2 variables.")

    # Ordering simply follows input order or sorted by variance
    order = list(range(d))
    ordered_tickers = [tickers[idx] for idx in order]
    U_ordered = U[:, order]

    trees: list[list[dict[str, Any]]] = []

    # V_direct[k, j] and V_indirect[k, j]
    V_dir = np.zeros((d, d, T), dtype=np.float64)
    V_ind = np.zeros((d, d, T), dtype=np.float64)

    for i in range(d):
        V_dir[0, i, :] = U_ordered[:, i]
        V_ind[0, i, :] = U_ordered[:, i]

    for tree_idx in range(1, d):
        tree_edges: list[dict[str, Any]] = []
        for j in range(d - tree_idx):
            v1 = V_ind[tree_idx - 1, j, :]
            v2 = V_dir[tree_idx - 1, j + 1, :]

            fit_res = fit_best_pair_copula(v1, v2, families=families)

            conditioned_nodes = ordered_tickers[j + 1 : j + tree_idx]
            edge_dict = {
                "tree": tree_idx,
                "node_1": ordered_tickers[j],
                "node_2": ordered_tickers[j + tree_idx],
                "conditioned_on": conditioned_nodes,
                "copula_type": fit_res["copula_type"],
                "theta": round(float(fit_res["theta"]), 4),
                "df": round(float(fit_res.get("df", 4.0)), 2) if "df" in fit_res else None,
                "kendall_tau": round(float(fit_res["kendall_tau"]), 4),
                "lower_tail_dependence": round(float(fit_res["lower_tail_dependence"]), 4),
                "upper_tail_dependence": round(float(fit_res["upper_tail_dependence"]), 4),
                "aic": round(float(fit_res["aic"]), 2),
            }
            tree_edges.append(edge_dict)

            c_type = fit_res["copula_type"]
            th = fit_res["theta"]
            df_val = fit_res.get("df", 4.0)

            V_dir[tree_idx, j, :] = h_function(v2, v1, c_type, theta=th, df=df_val)
            V_ind[tree_idx, j, :] = h_function(v1, v2, c_type, theta=th, df=df_val)

        trees.append(tree_edges)

    return {
        "vine_type": "d_vine",
        "ordered_tickers": ordered_tickers,
        "ordering_indices": order,
        "dimension": d,
        "trees": trees,
    }


# ============================================================================
# Sequential Simulation from Fitted Vine Copula
# ============================================================================

def simulate_c_vine(
    fitted_vine: dict[str, Any],
    num_simulations: int = 5000,
    random_seed: int = 42,
) -> np.ndarray:
    """
    Generates M scenarios from a fitted C-Vine copula using sequential probability integral transforms.

    Returns:
        U_sim: (num_simulations, d) float64 array of uniform variables in (0, 1).
    """
    rng = np.random.default_rng(random_seed)
    d = fitted_vine["dimension"]
    trees = fitted_vine["trees"]

    # Independent uniforms: W ~ U(0, 1)
    W = rng.uniform(1e-6, 1.0 - 1e-6, size=(num_simulations, d))
    U_sim = np.zeros((num_simulations, d), dtype=np.float64)

    # First variable is directly W[:, 0]
    U_sim[:, 0] = W[:, 0]

    # Matrix of conditional evaluations during simulation
    V_sim = np.zeros((d, d, num_simulations), dtype=np.float64)
    V_sim[0, 0, :] = U_sim[:, 0]

    for j in range(1, d):
        # We want to find U_sim[:, j] by sequential inverse h-transforms
        val = W[:, j]
        for tree_idx in range(j - 1, -1, -1):
            edge = trees[tree_idx][j - 1 - tree_idx]
            c_type = edge["copula_type"]
            th = edge["theta"]
            df_val = edge.get("df", 4.0)

            v_cond = V_sim[tree_idx, tree_idx, :]
            val = h_inv_function(val, v_cond, c_type, theta=th, df=df_val)

        U_sim[:, j] = val
        V_sim[0, j, :] = val

        # Forward h-transforms to populate V_sim for future conditioning
        for tree_idx in range(1, j + 1):
            edge = trees[tree_idx - 1][j - tree_idx]
            c_type = edge["copula_type"]
            th = edge["theta"]
            df_val = edge.get("df", 4.0)

            v_prev = V_sim[tree_idx - 1, j, :]
            v_root = V_sim[tree_idx - 1, tree_idx - 1, :]
            V_sim[tree_idx, j, :] = h_function(v_prev, v_root, c_type, theta=th, df=df_val)

    return np.clip(U_sim, 1e-6, 1.0 - 1e-6)


def simulate_d_vine(
    fitted_vine: dict[str, Any],
    num_simulations: int = 5000,
    random_seed: int = 42,
) -> np.ndarray:
    """
    Generates M scenarios from a fitted D-Vine copula using sequential probability integral
    transforms (Algorithm 2, Aas et al. 2009).

    Tracks left-moving conditional distributions L[(k, j)] = F(X_j | X_{j+1}, ..., X_{j+k})
    and right-moving conditional distributions R[(k, i)] = F(X_i | X_{i-k}, ..., X_{i-1})
    to ensure exact, uncorrupted conditional state updates without reading unpopulated entries (DEF-30-01).

    Parameters:
        fitted_vine: Dictionary containing fitted D-vine structure with keys 'dimension' and 'trees'.
        num_simulations: Number of Monte Carlo scenarios M to generate (must be >= 1).
        random_seed: Seed for reproducible pseudo-random generation.

    Returns:
        U_sim: (num_simulations, d) float64 array of uniform variables strictly in (0, 1).
    """
    if not isinstance(fitted_vine, dict) or "dimension" not in fitted_vine or "trees" not in fitted_vine:
        raise ValueError("Malformed fitted_vine: must be a dict containing 'dimension' and 'trees'.")

    d = fitted_vine["dimension"]
    trees = fitted_vine["trees"]

    if d < 2:
        raise ValueError(f"D-Vine simulation requires dimension >= 2, got {d}.")
    if len(trees) != d - 1:
        raise ValueError(f"Malformed fitted_vine: expected {d - 1} trees for dimension {d}, got {len(trees)}.")
    if num_simulations < 1:
        raise ValueError(f"num_simulations must be >= 1, got {num_simulations}.")

    rng = np.random.default_rng(random_seed)
    W = rng.uniform(1e-6, 1.0 - 1e-6, size=(num_simulations, d))
    X = np.zeros((num_simulations, d), dtype=np.float64)

    # L[(k, j)] stores left-moving conditional CDFs: F(X_j | X_{j+1}, ..., X_{j+k})
    # R[(k, i)] stores right-moving conditional CDFs: F(X_i | X_{i-k}, ..., X_{i-1})
    L: dict[tuple[int, int], np.ndarray] = {}
    R: dict[tuple[int, int], np.ndarray] = {}

    for i in range(d):
        if i == 0:
            X[:, 0] = W[:, 0]
            L[(0, 0)] = X[:, 0]
            R[(0, 0)] = X[:, 0]
        else:
            # Invert backwards through trees from k = i-1 down to 0
            v = W[:, i].copy()
            for k in range(i - 1, -1, -1):
                tree_idx = k          # 0-indexed tree: 0, 1, ..., d-2
                edge_idx = i - 1 - k  # edge index within tree k
                edge = trees[tree_idx][edge_idx]
                c_type = edge["copula_type"]
                th = edge["theta"]
                df_val = edge.get("df", 4.0)

                # The conditioning variable is L[(k, edge_idx)] = F(X_{edge_idx} | X_{edge_idx+1}, ..., X_{i-1})
                cond_val = L[(k, edge_idx)]
                v = h_inv_function(v, cond_val, c_type, theta=th, df=df_val)

            X[:, i] = v
            L[(0, i)] = X[:, i]
            R[(0, i)] = X[:, i]

            # Forward updates for future variables (k from 0 up to i-1)
            for k in range(i):
                tree_idx = k
                edge_idx = i - 1 - k
                edge = trees[tree_idx][edge_idx]
                c_type = edge["copula_type"]
                th = edge["theta"]
                df_val = edge.get("df", 4.0)

                v_left = L[(k, edge_idx)]
                v_right = R[(k, i)]

                # In fit_d_vine:
                # V_dir = h(v2, v1) where v2 is right, v1 is left -> h(v_right | v_left)
                # V_ind = h(v1, v2) where v1 is left, v2 is right -> h(v_left | v_right)
                R[(k + 1, i)] = h_function(v_right, v_left, c_type, theta=th, df=df_val)
                L[(k + 1, edge_idx)] = h_function(v_left, v_right, c_type, theta=th, df=df_val)

    return np.clip(X, 1e-6, 1.0 - 1e-6)


def simulate_vine_returns(
    returns: np.ndarray,
    tickers: list[str],
    vine_type: Literal["c_vine", "d_vine"] = "c_vine",
    num_simulations: int = 5000,
    random_seed: int = 42,
    marginal_method: Literal["empirical", "student_t"] = "empirical",
) -> tuple[np.ndarray, dict[str, Any]]:
    """
    Simulates multivariate returns using a fitted Regular Vine Copula (C-Vine / D-Vine).
    """
    T, N = returns.shape
    U, marg_info = compute_pseudo_observations(returns, method=marginal_method)

    if vine_type == "c_vine":
        fitted_vine = fit_c_vine(U, tickers)
        U_sim_ordered = simulate_c_vine(fitted_vine, num_simulations=num_simulations, random_seed=random_seed)
    else:
        fitted_vine = fit_d_vine(U, tickers)
        U_sim_ordered = simulate_d_vine(fitted_vine, num_simulations=num_simulations, random_seed=random_seed)

    # Reorder U_sim back to original ticker order
    order = fitted_vine["ordering_indices"]
    U_sim = np.zeros_like(U_sim_ordered)
    for pos, orig_idx in enumerate(order):
        U_sim[:, orig_idx] = U_sim_ordered[:, pos]

    # Marginal Inversion
    simulated_returns = np.zeros((num_simulations, N), dtype=np.float64)
    if marginal_method == "empirical":
        for j in range(N):
            simulated_returns[:, j] = np.quantile(returns[:, j], U_sim[:, j], method="linear")
    else:
        for j in range(N):
            m_info = marg_info["marginals"][j]
            if m_info["method"] == "student_t":
                simulated_returns[:, j] = stats.t.ppf(
                    U_sim[:, j], df=m_info["df"], loc=m_info["loc"], scale=m_info["scale"]
                )
            else:
                simulated_returns[:, j] = np.quantile(returns[:, j], U_sim[:, j], method="linear")

    diagnostics = {
        "vine_type": vine_type,
        "num_simulations": num_simulations,
        "random_seed": random_seed,
        "marginal_method": marginal_method,
        "tickers": tickers,
        "trees": fitted_vine["trees"],
    }

    return simulated_returns, diagnostics
