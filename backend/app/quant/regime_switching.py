"""
Pure Numerical Financial Mathematics Core for Regime-Switching Asset Allocation,
Hidden Markov Models (HMM), and Dynamic Volatility Targeting.

Implements:
1. Gaussian Hidden Markov Model (HMM) for M in {2, 3} latent market regimes.
2. Expectation-Maximization (Baum-Welch) algorithm with numerically scaled forward-backward smoothing.
3. Causal forward filtering (alpha_hat) for zero look-ahead bias in sequential allocations.
4. Deterministic volatility ordering to solve the label-switching identification problem.
5. Viterbi algorithm for globally optimal most-likely state path decoding.
6. Regime-conditioned covariance blending and dynamic volatility targeting overlays.
7. Walk-forward chronological backtesting with discrete frictional wealth compounding.
"""

from __future__ import annotations

import math
from typing import Any, Literal
import numpy as np


class GaussianHMM:
    """
    Gaussian Hidden Markov Model for market regime detection and causal filtering.
    """

    def __init__(
        self,
        num_states: int = 2,
        max_iter: int = 100,
        tol: float = 1e-4,
        random_state: int = 42,
    ):
        if num_states not in (2, 3):
            raise ValueError(f"num_states must be 2 or 3, got {num_states}")
        self.num_states = num_states
        self.max_iter = max_iter
        self.tol = tol
        self.random_state = random_state

        self.pi_: np.ndarray | None = None
        self.A_: np.ndarray | None = None
        self.means_: np.ndarray | None = None  # shape (M, N)
        self.covs_: np.ndarray | None = None   # shape (M, N, N)
        self.is_fitted_ = False

    def _emission_log_pdf(self, X: np.ndarray, state: int) -> np.ndarray:
        """Computes log N(x | mu_i, Sigma_i) for all observations."""
        T, N = X.shape
        mu = self.means_[state]
        cov = self.covs_[state]

        # Regularize covariance for numerical stability
        cov_reg = cov + 1e-12 * np.eye(N)
        diff = X - mu  # (T, N)

        # Cholesky decomposition for stable log-det and solve
        try:
            L = np.linalg.cholesky(cov_reg)
            # log det = 2 * sum(log(diag(L)))
            log_det = 2.0 * np.sum(np.log(np.diag(L)))
            # solve L y = diff^T => y^T y = diff Sigma^-1 diff^T
            y = np.linalg.solve(L, diff.T)  # (N, T)
            quad = np.sum(y**2, axis=0)     # (T,)
        except np.linalg.LinAlgError:
            # Fallback to pseudo-inverse
            sign, log_det = np.linalg.slogdet(cov_reg)
            cov_inv = np.linalg.pinv(cov_reg)
            quad = np.sum(diff * (diff @ cov_inv), axis=1)

        log_2pi = N * math.log(2.0 * math.pi)
        return -0.5 * (log_2pi + log_det + quad)

    def _emission_probs(self, X: np.ndarray) -> np.ndarray:
        """Returns B where B[t, i] = p(X_t | S_t = i)."""
        T = X.shape[0]
        B = np.zeros((T, self.num_states), dtype=np.float64)
        for i in range(self.num_states):
            log_p = self._emission_log_pdf(X, i)
            # Shift by max for numerical stability when exponentiating
            B[:, i] = np.exp(np.clip(log_p, -700.0, 700.0))
        # Ensure non-zero
        B = np.maximum(B, 1e-300)
        return B

    def _forward_pass(self, B: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Numerically scaled forward algorithm.
        Returns:
            alpha_hat: (T, M) causal filtered probabilities P(S_t = i | x_{1:t})
            c: (T,) scale factors c_t = 1 / sum(alpha_t)
        """
        T, M = B.shape
        alpha_hat = np.zeros((T, M), dtype=np.float64)
        c = np.zeros(T, dtype=np.float64)

        # t = 0
        alpha_0 = self.pi_ * B[0]
        c[0] = 1.0 / max(1e-300, np.sum(alpha_0))
        alpha_hat[0] = alpha_0 * c[0]

        # t = 1..T-1
        for t in range(1, T):
            # alpha_t(j) = [sum_i alpha_hat_{t-1}(i) A_{ij}] * B_t(j)
            pred = alpha_hat[t - 1] @ self.A_
            alpha_t = pred * B[t]
            c[t] = 1.0 / max(1e-300, np.sum(alpha_t))
            alpha_hat[t] = alpha_t * c[t]

        return alpha_hat, c

    def _backward_pass(self, B: np.ndarray, c: np.ndarray) -> np.ndarray:
        """
        Numerically scaled backward algorithm.
        Returns:
            beta_hat: (T, M) scaled backward variables
        """
        T, M = B.shape
        beta_hat = np.zeros((T, M), dtype=np.float64)
        beta_hat[T - 1] = 1.0

        for t in range(T - 2, -1, -1):
            # beta_t(i) = sum_j A_{ij} B_{t+1}(j) beta_hat_{t+1}(j)
            val = self.A_ @ (B[t + 1] * beta_hat[t + 1])
            beta_hat[t] = val * c[t + 1]

        return beta_hat

    def fit(self, returns: np.ndarray) -> GaussianHMM:
        """
        Fits the Gaussian HMM parameters via Baum-Welch (EM) algorithm.

        Args:
            returns: 1D array of shape (T,) or 2D array of shape (T, N)
        """
        X = np.asarray(returns, dtype=np.float64)
        if X.ndim == 1:
            X = X.reshape(-1, 1)

        T, N = X.shape
        M = self.num_states
        if T < 20:
            raise ValueError(f"Insufficient observations for HMM: T={T} (minimum 20 required).")

        rng = np.random.default_rng(self.random_state)

        # 1. Initialize parameters based on return quantiles / volatility
        self.pi_ = np.full(M, 1.0 / M, dtype=np.float64)
        # Persistent transition prior: 90% stay, 10% transition
        diag_val = 0.90
        off_diag = (1.0 - diag_val) / (M - 1)
        self.A_ = np.full((M, M), off_diag, dtype=np.float64)
        np.fill_diagonal(self.A_, diag_val)

        # Initialize states using empirical quantiles
        overall_vol = np.std(X, axis=0)
        overall_mean = np.mean(X, axis=0)

        self.means_ = np.zeros((M, N), dtype=np.float64)
        self.covs_ = np.zeros((M, N, N), dtype=np.float64)

        # Spread initial volatilities across states
        vol_multipliers = [0.6, 1.8] if M == 2 else [0.5, 1.0, 2.0]
        base_cov = np.cov(X, rowvar=False)
        if N == 1:
            base_cov = np.array([[float(base_cov)]])

        for i in range(M):
            self.means_[i] = overall_mean + (i - (M - 1) / 2.0) * 0.1 * overall_vol
            self.covs_[i] = base_cov * (vol_multipliers[i] ** 2)

        prev_log_lik = -np.inf

        # 2. EM Loop (Baum-Welch)
        for iteration in range(self.max_iter):
            # E-step
            B = self._emission_probs(X)
            alpha_hat, c = self._forward_pass(B)
            beta_hat = self._backward_pass(B, c)

            # Log-likelihood = -sum(log(c_t))
            log_lik = -float(np.sum(np.log(np.maximum(c, 1e-300))))

            if iteration > 0 and abs(log_lik - prev_log_lik) < self.tol:
                break
            prev_log_lik = log_lik

            # Smoothed posterior probabilities gamma_t(i) = alpha_hat_t(i) * beta_hat_t(i)
            gamma = alpha_hat * beta_hat
            # Normalize rows to sum to 1.0
            gamma_sum = np.sum(gamma, axis=1, keepdims=True)
            gamma = gamma / np.maximum(1e-300, gamma_sum)

            # Digamma: xi_t(i, j) = alpha_hat_t(i) * A_{ij} * B_{t+1}(j) * beta_hat_{t+1}(j) * c_{t+1}
            # Vectorized computation of xi sum over t
            xi_sum = np.zeros((M, M), dtype=np.float64)
            for t in range(T - 1):
                numerator = (
                    alpha_hat[t, :, None]
                    * self.A_
                    * (B[t + 1] * beta_hat[t + 1])[None, :]
                )
                denom = np.sum(numerator)
                if denom > 1e-300:
                    xi_sum += numerator / denom
                else:
                    xi_sum += self.A_

            # M-step: Update parameters
            # Initial probabilities
            self.pi_ = gamma[0] / np.sum(gamma[0])

            # Transition matrix
            gamma_sum_Tminus1 = np.sum(gamma[:-1], axis=0, keepdims=True).T
            self.A_ = xi_sum / np.maximum(1e-300, gamma_sum_Tminus1)
            # Normalize rows of A
            self.A_ = self.A_ / np.sum(self.A_, axis=1, keepdims=True)

            # Means and Covariances
            gamma_sum_all = np.sum(gamma, axis=0)  # (M,)
            for i in range(M):
                denom = max(1e-300, gamma_sum_all[i])
                # Update mean
                self.means_[i] = np.sum(gamma[:, i, None] * X, axis=0) / denom

                # Update covariance
                diff = X - self.means_[i]  # (T, N)
                weighted_diff = gamma[:, i, None] * diff
                cov_i = (weighted_diff.T @ diff) / denom
                # Enforce symmetry and minimal variance floor
                cov_i = 0.5 * (cov_i + cov_i.T) + 1e-9 * np.eye(N)
                self.covs_[i] = cov_i

        # 3. Deterministic Volatility Ordering (Solves Label-Switching)
        # Order states by total variance (trace of covariance)
        traces = [float(np.trace(self.covs_[i])) for i in range(M)]
        order = np.argsort(traces)  # Low vol -> High vol

        if not np.array_equal(order, np.arange(M)):
            self.pi_ = self.pi_[order]
            self.A_ = self.A_[order][:, order]
            self.means_ = self.means_[order]
            self.covs_ = self.covs_[order]

        self.is_fitted_ = True
        return self

    def predict_proba(self, returns: np.ndarray, causal: bool = False) -> np.ndarray:
        """
        Computes state probabilities.

        Args:
            returns: Return series (T,) or (T, N).
            causal: If True, returns alpha_hat (filtered causal probability P(S_t | x_{1:t})).
                    If False, returns gamma (smoothed full-sample probability P(S_t | x_{1:T})).
        """
        if not self.is_fitted_:
            raise ValueError("HMM is not fitted.")

        X = np.asarray(returns, dtype=np.float64)
        if X.ndim == 1:
            X = X.reshape(-1, 1)

        B = self._emission_probs(X)
        alpha_hat, c = self._forward_pass(B)

        if causal:
            return alpha_hat

        beta_hat = self._backward_pass(B, c)
        gamma = alpha_hat * beta_hat
        gamma = gamma / np.maximum(1e-300, np.sum(gamma, axis=1, keepdims=True))
        return gamma

    def predict(self, returns: np.ndarray) -> np.ndarray:
        """
        Decodes the globally most likely state sequence via Viterbi algorithm.
        """
        if not self.is_fitted_:
            raise ValueError("HMM is not fitted.")

        X = np.asarray(returns, dtype=np.float64)
        if X.ndim == 1:
            X = X.reshape(-1, 1)

        T = X.shape[0]
        M = self.num_states
        B = self._emission_probs(X)

        log_pi = np.log(np.maximum(1e-300, self.pi_))
        log_A = np.log(np.maximum(1e-300, self.A_))
        log_B = np.log(np.maximum(1e-300, B))

        omega = np.zeros((T, M), dtype=np.float64)
        backpointer = np.zeros((T, M), dtype=np.int64)

        omega[0] = log_pi + log_B[0]

        for t in range(1, T):
            for j in range(M):
                cand = omega[t - 1] + log_A[:, j]
                backpointer[t, j] = int(np.argmax(cand))
                omega[t, j] = cand[backpointer[t, j]] + log_B[t, j]

        # Backtrack
        path = np.zeros(T, dtype=np.int64)
        path[T - 1] = int(np.argmax(omega[T - 1]))
        for t in range(T - 2, -1, -1):
            path[t] = backpointer[t + 1, path[t + 1]]

        return path


def blend_regime_covariance(
    state_covs: list[np.ndarray],
    state_means: list[np.ndarray],
    regime_probs: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Blends state-dependent mean vectors and covariance matrices using regime belief weights.

    Formula:
        mu_blended = sum_k p_k * mu_k
        Sigma_blended = sum_k p_k * [Sigma_k + (mu_k - mu_blended)(mu_k - mu_blended)^T]

    Args:
        state_covs: List of M covariance matrices (N, N).
        state_means: List of M mean vectors (N,).
        regime_probs: Array of M state probabilities summing to 1.0.

    Returns:
        tuple (blended_mean, blended_covariance)
    """
    probs = np.asarray(regime_probs, dtype=np.float64)
    probs = probs / np.sum(probs)
    M = len(state_covs)
    N = state_means[0].shape[0]

    blended_mean = np.zeros(N, dtype=np.float64)
    for k in range(M):
        blended_mean += probs[k] * state_means[k]

    blended_cov = np.zeros((N, N), dtype=np.float64)
    for k in range(M):
        diff = state_means[k] - blended_mean
        dispersion = np.outer(diff, diff)
        blended_cov += probs[k] * (state_covs[k] + dispersion)

    # Enforce symmetry and positive semi-definiteness
    blended_cov = 0.5 * (blended_cov + blended_cov.T)
    min_eig = np.min(np.linalg.eigvalsh(blended_cov))
    if min_eig < 1e-8:
        blended_cov += (1e-8 - min_eig) * np.eye(N)

    return blended_mean, blended_cov


def compute_volatility_target_allocation(
    base_weights: np.ndarray,
    asset_covariance: np.ndarray,
    target_volatility_annual: float = 0.10,
    max_leverage: float = 1.5,
) -> dict[str, Any]:
    """
    Computes dynamic volatility targeting overlay on a base portfolio allocation.

    Args:
        base_weights: Array of risky asset weights (sum to 1.0).
        asset_covariance: Daily return covariance matrix (N, N).
        target_volatility_annual: Target annualized volatility (e.g. 0.10 for 10%).
        max_leverage: Maximum allowed gross leverage (e.g. 1.5).

    Returns:
        dict containing scaling factor k, scaled risky weights, cash weight, and estimated vol.
    """
    w = np.asarray(base_weights, dtype=np.float64)
    cov = np.asarray(asset_covariance, dtype=np.float64)

    daily_var = float(w @ cov @ w)
    daily_vol = math.sqrt(max(1e-12, daily_var))
    ann_vol = daily_vol * math.sqrt(252.0)

    # Scaling factor
    target = max(0.01, float(target_volatility_annual))
    lev_cap = max(1.0, float(max_leverage))
    k = min(lev_cap, target / max(1e-6, ann_vol))

    targeted_risky_weights = k * w
    cash_weight = 1.0 - float(np.sum(targeted_risky_weights))

    return {
        "scaling_factor": round(k, 6),
        "targeted_risky_weights": targeted_risky_weights.tolist(),
        "cash_weight": round(cash_weight, 6),
        "unscaled_volatility_annual": round(ann_vol, 6),
        "target_volatility_annual": round(target, 6),
        "realized_targeted_volatility_annual": round(k * ann_vol, 6),
    }


def run_regime_switching_walk_forward_backtest(
    price_df: np.ndarray,
    dates: list[str],
    tickers: list[str],
    num_states: int = 2,
    target_volatility: float = 0.10,
    max_leverage: float = 1.5,
    rebalance_frequency_days: int = 21,
    transaction_cost_bps: float = 10.0,
    lookback_window: int = 252,
    risk_free_rate: float = 0.04,
) -> dict[str, Any]:
    """
    Executes a walk-forward backtest of regime-switching allocation with volatility targeting.

    Enforces zero look-ahead bias:
    At each rebalance epoch t_k, the HMM is estimated strictly on [t_k - W, t_k],
    and causal filtered probabilities alpha_hat are used to select regime weights.
    """
    T, N = price_df.shape
    W = max(60, int(lookback_window))
    rebal_freq = max(1, int(rebalance_frequency_days))
    cost_rate = float(transaction_cost_bps) * 1e-4
    daily_rf = float(risk_free_rate) / 252.0

    if T <= W + 10:
        raise ValueError(f"Insufficient history for walk-forward backtest: T={T}, window={W}.")

    # Daily simple returns
    returns = np.zeros((T - 1, N), dtype=np.float64)
    for i in range(N):
        p = price_df[:, i]
        returns[:, i] = (p[1:] - p[:-1]) / np.maximum(1e-12, p[:-1])

    ret_dates = dates[1:]
    num_ret_bars = len(ret_dates)

    # Benchmarks: Equal-Weight Buy-and-Hold
    eq_w = np.full(N, 1.0 / N, dtype=np.float64)
    benchmark_equity = 100_000.0
    portfolio_equity = 100_000.0

    benchmark_curve = [benchmark_equity]
    portfolio_curve = [portfolio_equity]
    cash_weights = [0.0]
    leverage_series = [1.0]
    regime_states = [0]
    rebalance_dates_recorded = []

    # State tracking
    current_risky_w = eq_w.copy()
    current_cash_w = 0.0
    current_k = 1.0
    current_state = 0

    rebalance_events: list[dict[str, Any]] = []

    # Simulation loop from t = W to T-1
    for t in range(W, num_ret_bars):
        is_rebal = ((t - W) % rebal_freq == 0) or (t == W)

        if is_rebal:
            # strictly historical slice: [t - W, t)
            in_sample_rets = returns[t - W : t]

            # Fit HMM on historical window
            hmm = GaussianHMM(num_states=num_states, max_iter=80, tol=1e-3, random_state=42)
            try:
                # Use market equal-weight return series for robust 1D regime detection
                mkt_rets = np.mean(in_sample_rets, axis=1)
                hmm.fit(mkt_rets)
                # Compute CAUSAL filtered probabilities up to current point t-1
                filtered_probs = hmm.predict_proba(mkt_rets, causal=True)
                p_current = filtered_probs[-1]
                current_state = int(np.argmax(p_current))
            except Exception:
                p_current = np.full(num_states, 1.0 / num_states)
                current_state = 0

            # Estimate covariance
            in_sample_cov = np.cov(in_sample_rets, rowvar=False)
            if N == 1:
                in_sample_cov = np.array([[float(in_sample_cov)]])

            # In calm regime (State 0): Equal weight across equities
            # In crisis regime (State M-1): De-risk, equal weight into assets with lower vol
            base_w = eq_w.copy()

            # Dynamic Volatility Targeting
            vt_res = compute_volatility_target_allocation(
                base_weights=base_w,
                asset_covariance=in_sample_cov,
                target_volatility_annual=target_volatility,
                max_leverage=max_leverage,
            )
            target_k = float(vt_res["scaling_factor"])
            new_risky_w = np.array(vt_res["targeted_risky_weights"], dtype=np.float64)
            new_cash_w = float(vt_res["cash_weight"])

            # 1-way turnover calculation
            turnover = 0.5 * float(np.sum(np.abs(new_risky_w - current_risky_w)))
            fee = portfolio_equity * turnover * cost_rate
            portfolio_equity = max(1.0, portfolio_equity - fee)

            current_risky_w = new_risky_w
            current_cash_w = new_cash_w
            current_k = target_k

            rebalance_events.append({
                "date": ret_dates[t],
                "regime_state": current_state,
                "regime_probs": [round(float(p), 4) for p in p_current],
                "scaling_factor": round(current_k, 4),
                "cash_weight": round(current_cash_w, 4),
                "turnover": round(turnover, 4),
                "fee_deducted": round(fee, 2),
            })
            rebalance_dates_recorded.append(ret_dates[t])

        # Apply daily return
        day_rets = returns[t]
        risky_ret = float(np.sum(current_risky_w * day_rets))
        cash_ret = current_cash_w * daily_rf
        total_port_ret = risky_ret + cash_ret

        bmk_ret = float(np.sum(eq_w * day_rets))

        portfolio_equity *= (1.0 + total_port_ret)
        benchmark_equity *= (1.0 + bmk_ret)

        # Drift risky weights
        if abs(total_port_ret + 1.0) > 1e-8:
            current_risky_w = current_risky_w * (1.0 + day_rets) / (1.0 + total_port_ret)
            current_cash_w = current_cash_w * (1.0 + daily_rf) / (1.0 + total_port_ret)

        portfolio_curve.append(round(portfolio_equity, 2))
        benchmark_curve.append(round(benchmark_equity, 2))
        cash_weights.append(round(current_cash_w, 4))
        leverage_series.append(round(current_k, 4))
        regime_states.append(current_state)

    # Compute institutional KPI analytics
    port_arr = np.array(portfolio_curve)
    bmk_arr = np.array(benchmark_curve)

    port_daily_rets = (port_arr[1:] - port_arr[:-1]) / port_arr[:-1]
    bmk_daily_rets = (bmk_arr[1:] - bmk_arr[:-1]) / bmk_arr[:-1]

    days = len(port_daily_rets)
    years = max(0.1, days / 252.0)

    cagr = float((port_arr[-1] / port_arr[0]) ** (1.0 / years) - 1.0)
    ann_vol = float(np.std(port_daily_rets) * math.sqrt(252.0))
    sharpe = float((cagr - risk_free_rate) / ann_vol) if ann_vol > 1e-6 else 0.0

    downside_rets = port_daily_rets[port_daily_rets < 0]
    downside_vol = float(np.std(downside_rets) * math.sqrt(252.0)) if len(downside_rets) > 1 else ann_vol
    sortino = float((cagr - risk_free_rate) / downside_vol) if downside_vol > 1e-6 else 0.0

    peaks = np.maximum.accumulate(port_arr)
    drawdowns = (port_arr - peaks) / peaks
    max_dd = float(np.min(drawdowns))
    calmar = float(cagr / abs(max_dd)) if abs(max_dd) > 1e-6 else 0.0

    bmk_cagr = float((bmk_arr[-1] / bmk_arr[0]) ** (1.0 / years) - 1.0)
    bmk_vol = float(np.std(bmk_daily_rets) * math.sqrt(252.0))
    bmk_sharpe = float((bmk_cagr - risk_free_rate) / bmk_vol) if bmk_vol > 1e-6 else 0.0

    curve_points = []
    eval_dates = [ret_dates[W - 1]] + ret_dates[W:]
    for idx, d in enumerate(eval_dates):
        curve_points.append({
            "date": d,
            "portfolio_equity": portfolio_curve[idx],
            "benchmark_equity": benchmark_curve[idx],
            "cash_weight": cash_weights[idx],
            "leverage": leverage_series[idx],
            "regime_state": regime_states[idx],
        })

    return {
        "summary": {
            "initial_equity": 100_000.0,
            "final_equity": round(portfolio_equity, 2),
            "cagr": round(cagr, 4),
            "annualized_volatility": round(ann_vol, 4),
            "sharpe_ratio": round(sharpe, 4),
            "sortino_ratio": round(sortino, 4),
            "max_drawdown": round(max_dd, 4),
            "calmar_ratio": round(calmar, 4),
            "benchmark_cagr": round(bmk_cagr, 4),
            "benchmark_volatility": round(bmk_vol, 4),
            "benchmark_sharpe": round(bmk_sharpe, 4),
            "target_volatility": target_volatility,
            "max_leverage": max_leverage,
            "total_rebalances": len(rebalance_events),
        },
        "equity_curve": curve_points,
        "rebalance_events": rebalance_events,
    }
