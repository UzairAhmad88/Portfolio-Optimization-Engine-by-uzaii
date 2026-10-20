# Repository Audit — Quant Portfolio Optimization Engine
**Date:** 2026-10-16  
**Session:** Session 01 — Baseline Audit & Verification  
**Auditor:** Quantitative Finance Software Architecture & Engineering  
**Target Repository:** `quant-portfolio-engine-starter`

---

## 1. Executive Summary

This audit establishes the baseline for the **Quant Portfolio Optimization Engine** repository. The codebase currently contains a focused starter scaffold corresponding to **Stage 1: Market Data Engine Foundation**. Future roadmap capabilities (portfolio construction, mathematical risk models, Markowitz/Black-Litterman optimization, backtesting, database persistence, and frontend dashboard) are documented in specifications but are not yet implemented.

During this baseline audit, the Python environment and declared dependencies were successfully verified, and 8 automated tests passed (5 existing + 3 newly added regression and boundary tests). A critical defect causing HTTP 500 crashes during JSON serialization of missing optional numeric values (`float('nan')`) was identified, isolated, resolved via a minimal fix, and protected with a dedicated regression test. Several architectural and data-validation risks have been cataloged with prioritized remediation recommendations.

---

## 2. Repository Structure & Artifact Inventory

```
quant-portfolio-engine-starter/
├── .env.example                       # Skeleton environment configuration template
├── .gitignore                         # Python/cache/build exclusion rules
├── README.md                          # Quickstart guide and Stage 1 overview
├── backend/
│   ├── pyproject.toml                 # Packaging, dependencies, pytest & setuptools config
│   ├── app/
│   │   ├── __init__.py                # Package marker
│   │   ├── main.py                    # FastAPI application root & v1 router registration
│   │   ├── api/
│   │   │   ├── __init__.py            # Package marker
│   │   │   └── v1/
│   │   │       ├── __init__.py        # Package marker
│   │   │       └── routes.py          # FastAPI v1 endpoints & upload handling
│   │   └── market_data/
│   │       ├── __init__.py            # Package marker
│   │       └── service.py             # CSV parsing, validation, caching & query engine
│   └── tests/
│       ├── __init__.py
│       └── test_market_data.py        # Pytest test suite (unit/integration)
└── docs/
    ├── API_CONTRACT.md                # Stage 1 API endpoint specification
    ├── MASTER_PLAN.md                 # 8-stage product development roadmap
    └── STAGE_1_SPEC.md                # Detailed functional spec for Market Data Engine
```

### Component Breakdown
- **Backend Codebase Size:** ~350 lines of Python across 3 core application modules and 1 test module.
- **Frontend Codebase:** Non-existent (deferred to Stage 6).
- **Database/Migrations:** Non-existent (deferred to Stage 8).
- **Authentication/Security:** Public unauthenticated API; in-memory storage only.
- **Git Version Control:** Not initialized in the root folder.

---

## 3. Existing vs. Documented Capabilities

| Functional Area | Documented Status (`MASTER_PLAN.md`) | Actual Implementation State | Verification Notes |
|---|---|---|---|
| **Stage 1: Market Data Engine** | In Scope | **Implemented (Scaffold)** | CSV upload, schema check, inclusive query, in-memory cache and dataset registry work. |
| **Stage 2: Financial Mathematics** | Stage 2 | **Not Implemented** | Return formulas, covariance matrices, volatility, Sharpe, Sortino not present. |
| **Stage 3: Portfolio & Constraints** | Stage 3 | **Not Implemented** | Asset weights, position caps, sector constraints not present. |
| **Stage 4: Optimization Engine** | Stage 4 | **Not Implemented** | Quadratic/convex programming, SciPy/CVXPY solvers not present. |
| **Stage 5: Efficient Frontier** | Stage 5 | **Not Implemented** | Frontier curve calculations, sensitivity analytics not present. |
| **Stage 6: Research Dashboard** | Stage 6 | **Not Implemented** | No React/TypeScript, HTML, CSS, or UI framework files exist. |
| **Stage 7: Backtesting** | Stage 7 | **Not Implemented** | Walk-forward engine, rebalancing simulator, slippage not present. |
| **Stage 8: Production Persistence** | Stage 8 | **Not Implemented** | PostgreSQL, Alembic, Docker, auth, Redis not configured. |

---

## 4. Architecture & Design Findings

### 4.1 In-Memory State & Single-Worker Limitation
- Datasets are stored in a global Python dictionary `_DATASETS` in [service.py](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/app/market_data/service.py#L19).
- Cache entries reside in `_CACHE` with a 60-second TTL and 64-entry FIFO eviction.
- **Consequence:** All datasets and cache entries are volatile. They vanish upon server restart. If Uvicorn runs with multiple worker processes (`--workers > 1`), datasets registered on worker A return 404 when queried by worker B.

### 4.2 Event Loop Blocking in Async Route Handlers
- In [routes.py](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/app/api/v1/routes.py#L40-L59), `/preview` and `/uploads` are declared as `async def`.
- Inside these async handlers, `validate_csv(raw)` and `register_csv_dataset(raw)` are executed synchronously.
- `validate_csv` runs CPU-heavy Pandas DataFrame parsing and an `iterrows()` Python loop.
- **Consequence:** For large CSV uploads (up to 250,000 rows limit), the single event loop thread of FastAPI is completely blocked, stalling all other concurrent client requests.

### 4.3 Missing Response Schemas in OpenAPI (`/docs`)
- Endpoints in [routes.py](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/app/api/v1/routes.py) lack `response_model` annotations.
- **Consequence:** In Swagger UI (`/docs`) and `/openapi.json`, all endpoints declare empty response schemas `200: { content: { "application/json": { "schema": {} } } }`. Clients cannot inspect typed response shapes automatically.

### 4.4 Unbounded Dataset Storage in Memory
- While `_CACHE` has `CACHE_MAX_ENTRIES = 64`, `_DATASETS` has **no maximum limit** and no TTL.
- **Consequence:** In an active development session or shared testing environment, repeated uploads of 10 MB CSVs will consume memory indefinitely until the host triggers an Out-Of-Memory (OOM) crash.

---

## 5. Prioritized Defects & Risks

### Critical Severity (Resolved in Baseline Verification)
- **DEF-01: JSON Serialization Crash on Missing Optional Numeric Values**
  - **Symptom:** Uploading or previewing any CSV with standard missing optional values (e.g. empty cell in `open`, `high`, `low`, `adjusted_close`, or `volume`) caused Starlette's JSON serializer to throw `ValueError: Out of range float values are not JSON compliant` (HTTP 500 Internal Server Error).
  - **Root Cause:** Pandas converts empty numeric cells to `float('nan')`. When converting DataFrame rows via `.to_dict(orient="records")`, raw `NaN` values remained in dictionaries. Standard JSON compliance rejects `NaN`.
  - **Resolution:** Replaced raw dictionary extraction in [service.py](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/app/market_data/service.py#L137) with sanitization mapping `pd.isna(v)` to `None` (`null` in JSON). Added regression test `test_preview_and_query_with_sparse_optional_columns`.

### High Severity
- **RISK-01: Event Loop Starvation on Large Uploads**
  - **Risk:** Synchronous Pandas execution inside `async def` routes blocks FastAPI's event loop.
  - **Recommendation for Stage 1 Refinement:** Offload CPU-bound validation to thread pool (`starlette.concurrency.run_in_threadpool`) or convert routes to standard `def`.
- **RISK-02: Unbounded In-Memory Dataset Growth**
  - **Risk:** `_DATASETS` dictionary has no eviction policy, capacity limit, or memory ceiling.
  - **Recommendation:** Implement a bounded LRU/FIFO eviction cap (e.g., maximum 30 active datasets in development).

### Medium Severity
- **DEF-02: Incomplete OHLC Consistency Validation**
  - **Issue:** [service.py](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/app/market_data/service.py#L111-L114) only verifies `high < low`. It does NOT check `close > high`, `open > high`, `close < low`, or `open < low`.
  - **Impact:** Corrupted market bars where close or open exceeds the daily high pass validation, threatening downstream volatility and return calculations.
- **DEF-03: Silent Coercion of Unparseable Strings in Optional Numeric Columns**
  - **Issue:** Passing strings like `"N/A"` or `"corrupt"` in `open` or `volume` is silently coerced to `NaN` and treated as an empty cell rather than flagged as an invalid numeric value.
- **DEF-04: Ambiguous Date String Parsing**
  - **Issue:** Formats like `20250102` (integer date representation) are interpreted by `pd.to_datetime` as nanoseconds from 1970 (`1970-01-01`).
  - **Recommendation:** Enforce strict ISO `YYYY-MM-DD` date parsing or explicit multi-format regex verification.
- **RISK-03: Preview Payload Size Hazard**
  - **Issue:** `/api/v1/market-data/preview` returns `valid_data` containing all validated rows. For a 100k-row CSV, the response payload is tens of megabytes, creating browser freezing and network saturation.

### Low Severity
- **DEF-05: Duplicate Error Message for Non-Positive Close**
  - **Issue:** Rows with `close <= 0` receive two error messages: `"Close must be a positive number."` and `"close must be positive when provided."`.
- **DEF-06: Cache Key Whitespace Inconsistency**
  - **Issue:** `query_dataset` strips whitespace for row filtering, but does not strip whitespace before hashing ticker lists in the cache key.
- **DEF-07: Out-of-Order Error Reporting for Duplicates**
  - **Issue:** Duplicate row errors are appended after initial row validation passes, disrupting sequential row numbering in error reports.

---

## 6. Development & Operational Baseline Summary

- **OS / Platform:** Windows (PowerShell)
- **Runtime:** Python 3.11.16 (`cpython-3.11.16-windows-x86_64-none`)
- **Virtual Environment:** `backend/.venv` (managed via `uv`)
- **Key Installed Packages:** FastAPI 0.143.2, Pydantic 2.14.1, Pandas 3.0.6, NumPy 2.4.6, Pytest 9.1.1, HTTPX 0.28.1, Uvicorn 0.54.0.
- **Test Status:** 8 passed, 0 failed, 1 deprecation warning (`httpx` testclient deprecation in Starlette).
- **Service Verification:** `/api/v1/health`, `/docs`, `/openapi.json` verified healthy.
