"""
Session 31 Comprehensive Benchmarking Script
Measures:
1. Per-edge h-inverse timings across all 5 copula families (5,000 scenarios).
2. Gumbel inversion baseline (Brent scalar loop) vs optimized (Vectorized Safeguarded Newton).
3. Full C-Vine and D-Vine simulation across dimensions d in {3, 4, 5, 8} (5,000 scenarios).
4. Configurations with and without Gumbel edges.
5. Numerical accuracy and max error against scalar Brent reference.
"""

import math
import time
import numpy as np
from scipy.optimize import brentq
import sys
import os

sys.path.insert(0, os.path.abspath("backend"))

from app.quant.vine_copula import (
    h_function,
    h_inv_function,
    fit_c_vine,
    fit_d_vine,
    simulate_c_vine,
    simulate_d_vine,
    compute_pseudo_observations,
)


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


def run_benchmarks():
    print("=" * 80)
    print("SESSION 31 NUMERICAL PERFORMANCE AND ACCURACY BENCHMARK REPORT")
    print("=" * 80)
    print(f"Python Version: {sys.version.split()[0]}")
    print(f"NumPy Version:  {np.__version__}")
    print("Platform:       win32")
    print("-" * 80)

    # 1. Per-Edge Inversion Timings across all 5 families (M=5,000)
    print("\n--- 1. PER-EDGE h-INVERSE TIMINGS (M = 5,000 scenarios, 10 repetitions median) ---")
    rng = np.random.default_rng(42)
    M = 5000
    u_eval = rng.uniform(0.01, 0.99, size=M)
    v_eval = rng.uniform(0.01, 0.99, size=M)

    families_to_test = [
        ("indep", 0.0, None),
        ("clayton", 1.8, None),
        ("gaussian", 0.6, None),
        ("student_t", 0.5, 4.0),
        ("gumbel", 2.0, None),
    ]

    for fam, th, df in families_to_test:
        # Warmup
        _ = h_inv_function(u_eval, v_eval, fam, theta=th, df=df)
        times = []
        for _ in range(10):
            t0 = time.perf_counter()
            _ = h_inv_function(u_eval, v_eval, fam, theta=th, df=df)
            times.append((time.perf_counter() - t0) * 1000.0)
        med_t = float(np.median(times))
        print(f"  Family: {fam:10s} | Median Time: {med_t:8.2f} ms")

    # 2. Gumbel Inversion: Baseline Scalar Brent vs Vectorized Safeguarded Newton
    print("\n--- 2. GUMBEL h-INVERSE: SCALAR BRENT VS VECTORIZED NEWTON (M = 5,000) ---")
    thetas = [1.2, 1.8, 2.5, 4.0]
    for th in thetas:
        # Baseline Brent (1 repetition because it takes ~3.7s)
        t0 = time.perf_counter()
        res_brent = np.array([scalar_gumbel_h_inv_brent(float(u), float(v), th) for u, v in zip(u_eval, v_eval)])
        t_brent = (time.perf_counter() - t0) * 1000.0

        # Vectorized Newton (5 repetitions median)
        vec_times = []
        for _ in range(5):
            t0 = time.perf_counter()
            res_vec = h_inv_function(u_eval, v_eval, "gumbel", theta=th)
            vec_times.append((time.perf_counter() - t0) * 1000.0)
        t_vec = float(np.median(vec_times))

        max_err = float(np.max(np.abs(res_vec - res_brent)))
        speedup = t_brent / max(t_vec, 1e-4)

        print(f"  Theta = {th:3.1f} | Brent: {t_brent:8.2f} ms | Vectorized: {t_vec:6.2f} ms | Speedup: {speedup:6.1f}x | Max Err vs Brent: {max_err:.2e}")

    # 3. Full Vine Simulation Benchmarks (M = 5,000 scenarios)
    print("\n--- 3. FULL VINE SIMULATION BENCHMARK (M = 5,000 scenarios, median of 5 runs) ---")
    print(f"{'Dim':>4} | {'Vine Type':>8} | {'Edge Config':>15} | {'Median Time (ms)':>17} | {'Total Edges':>12}")
    print("-" * 65)

    for d in [3, 4, 5, 8]:
        T = 400
        A = rng.normal(0, 1, size=(d, d))
        cov = A @ A.T + np.eye(d) * 0.5
        std = np.sqrt(np.diag(cov))
        corr = cov / np.outer(std, std)
        chol = np.linalg.cholesky(corr)
        rets = (rng.normal(size=(T, d)) @ chol.T) * 0.015
        tickers = [f"Asset_{i+1}" for i in range(d)]
        U, _ = compute_pseudo_observations(rets)

        # Config A: Heterogeneous with all families allowed (including Gumbel)
        c_vine_all = fit_c_vine(U, tickers)
        d_vine_all = fit_d_vine(U, tickers)

        # Config B: Without Gumbel
        c_vine_nog = fit_c_vine(U, tickers, families=["gaussian", "student_t", "clayton", "indep"])
        d_vine_nog = fit_d_vine(U, tickers, families=["gaussian", "student_t", "clayton", "indep"])

        total_edges = d * (d - 1) // 2

        # Benchmark C-Vine All
        times = []
        for _ in range(5):
            t0 = time.perf_counter()
            _ = simulate_c_vine(c_vine_all, num_simulations=5000, random_seed=42)
            times.append((time.perf_counter() - t0) * 1000.0)
        print(f"{d:>4} | {'C-Vine':>8} | {'With Gumbel':>15} | {np.median(times):>14.2f} ms | {total_edges:>12}")

        # Benchmark D-Vine All
        times = []
        for _ in range(5):
            t0 = time.perf_counter()
            _ = simulate_d_vine(d_vine_all, num_simulations=5000, random_seed=42)
            times.append((time.perf_counter() - t0) * 1000.0)
        print(f"{d:>4} | {'D-Vine':>8} | {'With Gumbel':>15} | {np.median(times):>14.2f} ms | {total_edges:>12}")

        # Benchmark D-Vine No Gumbel
        times = []
        for _ in range(5):
            t0 = time.perf_counter()
            _ = simulate_d_vine(d_vine_nog, num_simulations=5000, random_seed=42)
            times.append((time.perf_counter() - t0) * 1000.0)
        print(f"{d:>4} | {'D-Vine':>8} | {'No Gumbel':>15} | {np.median(times):>14.2f} ms | {total_edges:>12}")

    print("=" * 80)
    print("BENCHMARK COMPLETED SUCCESSFULLY")
    print("=" * 80)


if __name__ == "__main__":
    run_benchmarks()
