# Stage 31 — Gate C: Persistence and Deterministic Adjustments Report
**Quant Portfolio Optimization Engine | US Equities & Pakistan Stock Exchange (PSX)**

## 1. Executive Summary
- **Gate Status:** PASS
- **Approved Scope:** Versioned persistence and deterministic adjustment engine for stock splits, reverse splits, cash dividends, and total returns.
- **Completed Workstream:** Workstream 31.3 (Raw Prices, Adjustment Engine, and Total Returns).

---

## 2. Workstream 31.3: Adjustment Engine (`adjustments.py`)
1. **Unambiguous Price & Return Semantics:**
   - Raw observations ($P_t^{\text{raw}}$) are preserved without destructive mutation.
   - Provider-adjusted prices ($P_t^{\text{adj\_close}}$) are distinguished from system-derived corporate-action adjusted series ($P_t^{\text{adj}}$).
   - Price return (split-adjusted, dividend-exclusive):
     $$r_t^{\text{price}} = \frac{P_t - P_{t-1}/k}{P_{t-1}/k}$$
   - Dividend-inclusive total return (CRSP reinvestment convention):
     $$r_t^{\text{total}} = \frac{P_t + D_t - P_{t-1}/k}{P_{t-1}/k}$$
2. **Deterministic Backward Multipliers:**
   - Stock splits: backward factor $f_{\text{split}} = 1/k$ applied to all prior prices $\tau < t_{\text{ex}}$. Volume is multiplied by $k$.
   - Cash dividends: standard CRSP backward factor $f_{\text{div}} = 1 - (D_t / P_{t-1})$ applied to all prior prices $\tau < t_{\text{ex}}$.
   - Multi-event compounding: $f_{\text{total}} = f_{\text{split}} \times f_{\text{div}}$.
   - Traceability: `AdjustmentPolicy(version="2026.1")`.

---

## 3. Hand-Calculated Numerical Fixtures
| Fixture | Scenario | Input Prices | Event Details | Expected Factor | Expected Adj Close | Expected Return |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Forward Split** | 2-for-1 forward split | Day 1: $100.00<br>Day 2: $50.00 | $k = 2.0$ | Day 1 factor: 0.50<br>Day 2 factor: 1.00 | Day 1: $50.00<br>Day 2: $50.00 | Day 2 price return: 0.00% (eliminates -50% naive shock) |
| **2. Reverse Split** | 1-for-5 reverse split | Day 1: $10.00<br>Day 2: $50.00 | $k = 0.2$ | Day 1 factor: 5.00<br>Day 2 factor: 1.00 | Day 1: $50.00<br>Day 2: $50.00 | Day 2 price return: 0.00% |
| **3. Cash Dividend** | $2.00 cash dividend | Day 1: $100.00<br>Day 2: $98.00 | $D_t = \$2.00$ | Day 1 factor: 0.98<br>Day 2 factor: 1.00 | Day 1: $98.00<br>Day 2: $98.00 | Price return: -2.00%<br>Total return: 0.00% |
| **4. Combined** | Dividend then split | Day 1: $100.00<br>Day 2: $98.00<br>Day 3: $49.00 | Day 2: Div $2.00<br>Day 3: Split 2:1 | Day 1: 0.49<br>Day 2: 0.50<br>Day 3: 1.00 | Day 1: $49.00<br>Day 2: $49.00<br>Day 3: $49.00 | Total return Day 2: 0.00%<br>Total return Day 3: 0.00% |

---

## 4. Database Schema & Migration (`c1d2e3f4a5b6`)
1. **`corporate_actions` Table:**
   - Primary key: `id` (UUID or deterministic `ca_...` SHA-256).
   - Foreign key: `dataset_id` (nullable, cascade on delete).
   - Identity & Event fields: `asset_id`, `ticker`, `market`, `event_type`, `effective_date`, `announcement_date`, `ex_date`, `record_date`, `payment_date`.
   - Economic values: `value` (split ratio or dividend per share), `currency`.
   - Governance & Audit: `source`, `revision_id`, `status`, `is_point_in_time_verified`, `provenance_json`.
   - Indexed on `(asset_id, effective_date)` and `(ticker, market, effective_date)`.
2. **`datasets` Table Extensions:**
   - `point_in_time_status`: `unverified_legacy` (default), `pit_verified`.
   - `calendar_version`: string (e.g. `US-NYSE-2026.1`, `PSX-KHI-2026.1`).
   - `adjustment_policy_version`: string (e.g. `2026.1`).
3. **Repository Operations (`repository.py`):**
   - `save_corporate_actions`: Idempotent persistence with deduplication.
   - `query_corporate_actions`: Filtered queries supporting strict PIT cutoff (`announcement_date <= as_of_date`).
   - `clear_all_datasets`: Cleans corporate actions alongside price bars and datasets for testing isolation.
