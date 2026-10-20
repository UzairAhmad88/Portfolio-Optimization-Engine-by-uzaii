# SESSION 15 AUDIT — Portfolio Performance Attribution, Benchmark Analysis & Risk-Adjusted Performance Evaluation

## 1. Audit Context and Objective

This audit establishes the pre-implementation state for **Session 15** of the Quant Portfolio Optimization Engine and Research Dashboard. The objective of Session 15 is to deliver:
1. Mathematically rigorous portfolio performance evaluation relative to a benchmark.
2. Asset-level return contribution analysis.
3. Risk-adjusted performance metrics (Active Return, Tracking Error, Information Ratio, Beta, Jensen's Alpha, Treynor Ratio, Up/Down Capture Ratios).
4. Seamless integration with saved backtests (`BacktestRunModel`) and validated market datasets.
5. Persistent performance reports with tenant isolation.
6. A responsive institutional React 19 / TypeScript workspace (`PerformancePage.tsx`).

All analyses are designed strictly for quantitative research, transparently stating methodology, data provenance, and limitations without presenting past results as guaranteed forecasts.

---

## 2. Repository & Architectural Audit

### 2.1 Database & Migration Graph
- **Current Head:** `f5a6b7c8d9e0` (`create_risk_simulation_runs_table.py` from Session 14).
- **Migration History:**
  1. `0a14be571daa`: `datasets`, `dataset_assets`, `price_bars`.
  2. `7c4a4e92cae9`: `users` table and `user_id` dataset ownership.
  3. `8993dbd79e8a`: `backtest_runs` table with foreign keys and tenant isolation.
  4. `e4f5a6b7c8d9`: `scenario_runs` table.
  5. `f5a6b7c8d9e0`: `risk_simulation_runs` table.
- **Session 15 Migration Target:** New migration `a1b2c3d4e5f6_create_performance_reports_table.py` with down revision `f5a6b7c8d9e0`.

### 2.2 Backtest Persistence Inspection (`BacktestRunModel`)
Inspection of `backend/app/db/models.py` (lines 200–267) reveals the exact contents of saved backtest runs:
- `id`: UUID string.
- `user_id`: ForeignKey to `users.id` (tenant-isolated).
- `dataset_id`: ForeignKey to `datasets.id`.
- `strategy_type`, `rebalance_frequency`, `initial_capital`, `transaction_cost_bps`, `slippage_bps`.
- `strategy_config_json`: Stored target weights and asset universe.
- `summary_metrics_json`: Aggregated metrics (CAGR net/gross, Sharpe, Sortino, Max Drawdown).
- `equity_curve_json`: Daily time-series containing `date`, `portfolio_value_net`, `portfolio_value_gross`, `return_net`, `return_gross`, `drawdown_net`, `drawdown_gross`.
- `rebalance_events_json`: Rebalance events with `date`, `pre_weights`, `post_weights`, `turnover`, and friction costs.
- **Key Finding & Limitation:**
  `equity_curve_json` records daily portfolio-level net and gross returns and values, but does **not** store daily constituent-level asset holdings between rebalance dates. Constituent weights are recorded only at rebalancing events in `rebalance_events_json`. Furthermore, historical backtest runs do not record a benchmark return series. Therefore, benchmark comparison must be performed by evaluating the portfolio return series against a validated benchmark asset from the linked dataset (or a supplied benchmark series), and asset-level contribution can be evaluated using backtest rebalance weights or dataset asset prices.

### 2.3 Market Data & Currency Invariant
- **Market Data Schema:** `dataset_assets` records `market` and `currency`. All price bars are daily adjusted closes.
- **Homogeneous Currency Invariant:** Portfolios and benchmarks must share identical currency (e.g., both USD or both PKR). Multi-currency comparison without FX conversion contracts is strictly rejected with HTTP 422.
- **Observation Alignment:** Missing observations cannot be fabricated or forward-filled. Portfolio and benchmark time-series must be aligned via strict inner join on exact trading dates.

### 2.4 Existing Quant Modules (`backend/app/quant/`)
- `returns.py`: `simple_returns`, `log_returns`, `cumulative_returns`, `annualized_return`.
- `risk.py`: `variance`, `volatility`, `annualized_volatility`, `drawdown_series`, `maximum_drawdown`, `downside_deviation`, `sharpe_ratio`, `sortino_ratio`, `annual_to_periodic_rate`.
- `covariance.py`: `covariance_matrix`, `correlation_matrix`.
- `var_cvar.py`: `calculate_empirical_var_cvar`, `parametric_var_cvar`, `historical_var_cvar`.
- **Identified Gaps (To Implement):**
  1. Active return series $a_t = r_{p,t} - r_{b,t}$.
  2. Annualized Tracking Error ($TE = \operatorname{Std}(a_t)\sqrt{m}$).
  3. Information Ratio ($IR = \frac{\overline{a} \cdot m}{TE}$).
  4. Portfolio Beta ($\beta = \frac{\operatorname{Cov}(r_p, r_b)}{\operatorname{Var}(r_b)}$).
  5. Jensen's Alpha ($\alpha = \overline{r}_p - [r_f + \beta(\overline{r}_b - r_f)]$).
  6. Treynor Ratio ($\frac{\overline{r}_p - r_f}{\beta}$).
  7. Up-Market and Down-Market Capture Ratios.
  8. Asset-level return contribution $c_{i,t} = w_{i,t-1} r_{i,t}$ and multi-period linking.
  9. Brinson attribution conditional audit: verify absence of benchmark constituent weights.

### 2.5 Authentication & Access Control
- JWT authentication (`HS256`) via Bearer token or HttpOnly cookie.
- Tenant isolation enforced across datasets, backtests, scenario runs, and risk simulations.
- Performance analysis endpoints must enforce ownership of referenced backtests and datasets.

### 2.6 Frontend Architecture
- React 19, TypeScript, Vite.
- Design system: Dark institutional theme with CSS variables, Lucide icons, accessible forms, loading states, and SVG charts.
- Current workspaces: Overview, Market Data, Portfolio Definition, Optimization, Efficient Frontier, Risk Analytics, Comparison, Backtesting, Scenario & Stress, Monte Carlo Risk, System Info.
- New workspace: `PerformancePage.tsx` under `'performance'` route.

---

## 3. Reusable Modules vs. Missing Capabilities

| Module | Existing Capability | Missing in Session 15 | Action Plan |
|---|---|---|---|
| `app/quant/returns.py` | Simple, log, cumulative, and annualized returns | Active return series, compounded excess returns | Implement in `app/quant/performance.py` |
| `app/quant/risk.py` | Sharpe, Sortino, volatility, drawdown | Tracking error, Beta, Alpha, Information Ratio, Treynor, Capture Ratios | Implement in `app/quant/performance.py` and reuse existing risk functions |
| `app/quant/portfolio.py` | Weight validation, portfolio return | Single-period & multi-period asset return contribution | Implement pure contribution functions |
| `app/backtesting/` | Walk-forward backtesting, `BacktestRunModel` | Direct benchmark comparative evaluation from saved runs | Build backtest adapter in performance service |
| `app/market_data/` | Clean price bar query, dataset ownership | Benchmark asset price series extraction and date alignment | Build alignment and validation utilities |
| `app/db/models.py` | `BacktestRunModel`, `ScenarioRunModel`, `RiskSimulationRunModel` | `PerformanceReportModel` | Add model and write migration `a1b2c3d4e5f6` |
| API Transport | Fast route handlers with threadpools | Performance analysis and attribution endpoints | Create `app/api/v1/performance_routes.py` |
| Frontend | Institutional theme, SVG chart primitives | Performance comparison, active return, and contribution views | Create `PerformancePage.tsx` and integrate navigation |

---

## 4. Conditional Scope: Brinson Attribution Audit

A critical mandate of Session 15 is to assess whether Brinson-Fachler or Brinson-Hood-Beebower allocation/selection attribution is possible within the repository.
- **Requirement for Brinson Attribution:** Requires **benchmark constituent weights** $w_{b,i}$ and benchmark sector/group returns $R_{b,j}$.
- **Repository Reality:** The existing database stores prices for portfolio constituent assets and single index benchmarks (e.g., SPY). It does **not** store historical constituent weights or sector classifications for external benchmark indices.
- **Decision & Integrity Rule:**
  - In accordance with instructions, we **will not approximate or fabricate benchmark constituent weights**.
  - We **will not claim to compute Brinson allocation or selection attribution**.
  - We will implement **asset-level return contribution analysis** ($c_{i,t} = w_{i,t-1} r_{i,t}$) which is mathematically rigorous, fully supported by existing holdings data, and reconciles to portfolio return.
  - The missing constituent data requirements are explicitly documented in contracts and system architecture.

---

## 5. Risk Assessment & Mitigations

1. **Active Return vs. Compounded Excess Return:**
   - *Risk:* Mixing arithmetic active return difference $R_p - R_b$ with geometric excess return $\frac{1+R_p}{1+R_b}-1$.
   - *Mitigation:* Explicitly calculate and report both metrics with distinct, unambiguous labels.
2. **Benchmark Variance Zero or Insufficient Samples:**
   - *Risk:* Division by zero when computing Beta ($\operatorname{Var}(r_b) = 0$), Tracking Error ($\operatorname{Std}(a_t) = 0$), or Information Ratio.
   - *Mitigation:* Safely detect zero variance or samples $< 3$ observations; return `None` with structured warning flags.
3. **Multi-Period Asset Contribution Reconciliation:**
   - *Risk:* Naively summing periodic asset contributions $\sum_t c_{i,t}$ and claiming they equal compounded cumulative return $R_p$.
   - *Mitigation:* Implement Menchero-style logarithmic linking factors $L_t = \frac{\ln(1+r_{p,t})}{r_{p,t}} \frac{R_p}{\ln(1+R_p)}$ to produce exact additive multi-period contributions that reconcile to total compounded portfolio return.
4. **Currency Incompatibility:**
   - *Risk:* Comparing a portfolio in USD against a benchmark in PKR.
   - *Mitigation:* Enforce strict currency equality check before running any comparative calculations.

---

## 6. Acceptance Criteria

1. Pre-coding contracts documented in `docs/PERFORMANCE_ATTRIBUTION_CONTRACTS.md`.
2. Pure mathematical functions in `app/quant/performance.py` pass independent unit tests against hand-calculated cases.
3. Active returns, tracking error, Information Ratio, Beta, Alpha, and Capture Ratios reconcile to theoretical benchmarks.
4. Asset contributions reconcile to portfolio return within $10^{-6}$ tolerance.
5. Saved backtest runs can be evaluated against designated benchmark assets with tenant isolation enforced.
6. Relational persistence in `performance_reports` verified with Alembic migration `a1b2c3d4e5f6`.
7. React 19 / TypeScript `PerformancePage.tsx` integrates real API calls, SVG charts, and saved reports drawer.
8. 100% test pass rate across backend pytest and frontend Vitest suites with zero regressions.
9. Production build (`npm run build`) succeeds with 0 type errors.
