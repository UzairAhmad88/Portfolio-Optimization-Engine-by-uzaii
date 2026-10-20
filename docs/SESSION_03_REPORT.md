# Session 03 Report — Market Data Engine Hardening & Typed API Contracts
**Project:** Quant Portfolio Optimization Engine  
**Session:** Session 03 (Engine Hardening & Contracts)  
**Date:** 2026-10-16  
**Status:** Completed & Verified  

---

## 1. Baseline Test Results Before Changes

Prior to making any modifications in Session 03, the existing test suite established in Session 01 was executed:
- **Command:** `pytest -v`
- **Result:** **8 passed, 0 failed** in 4.35s (1 Starlette deprecation warning regarding httpx testclient).
- **Verified Tests:**
  - `test_health`
  - `test_preview_valid_csv`
  - `test_upload_and_query_inclusive_dates`
  - `test_invalid_price_is_reported_and_excluded`
  - `test_missing_required_column_rejected`
  - `test_preview_and_query_with_sparse_optional_columns`
  - `test_query_missing_dataset_returns_404`
  - `test_query_invalid_date_range_returns_422`

---

## 2. Issues Confirmed During Inspection

Inspection of the baseline code confirmed all five architectural deficiencies identified in Session 02:

1. **Event-Loop Blocking in Async Route Handlers:**
   - In `backend/app/api/v1/routes.py`, `preview_csv` and `upload_csv` were declared as `async def` but invoked synchronous, CPU-bound Pandas validation (`validate_csv` and `register_csv_dataset`) directly on the main asyncio thread. Under heavy uploads or high concurrency, this starved the event loop.
2. **Unbounded In-Memory Dataset Registry:**
   - In `backend/app/market_data/service.py`, `_DATASETS` was a standard unbounded Python dictionary with no capacity ceiling, TTL, or eviction policy. Repeated 10 MB CSV uploads posed a critical Out-of-Memory (OOM) risk.
3. **Incomplete OHLC Consistency Validation:**
   - `validate_csv` only checked `high < low`. It failed to validate `high >= max(open, close)` and `low <= min(open, close)`, permitting structurally corrupt price bars (e.g. `close > high` or `open < low`) to pass into accepted datasets.
4. **Silent Coercion of Malformed Numeric Strings:**
   - `pd.to_numeric(..., errors="coerce")` converted unparseable strings (e.g. `open="corrupt"` or `volume="bad_data"`) directly to `NaN`. In conjunction with the Session 01 NaN sanitization, invalid text in optional columns was silently transformed into `null` rather than rejected as a row-level data error. Non-finite values (`inf`, `-inf`) were similarly unflagged.
5. **Missing OpenAPI Response Models:**
   - Routes in `routes.py` lacked Pydantic `response_model` annotations. In Swagger UI (`/docs`) and `/openapi.json`, all 200 responses showed empty schema definitions (`{}`), hindering client integration.
6. **Duplicate Validation Error Messages:**
   - Rows with non-positive close prices (`close <= 0`) received two duplicate error messages: `"Close must be a positive number."` and `"close must be positive when provided."`.

---

## 3. Files Changed and Reason for Each Change

| File Path | Nature of Change | Architectural Rationale |
|---|---|---|
| [`backend/app/api/v1/schemas.py`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/app/api/v1/schemas.py) | **Created** | Formulated typed Pydantic v2 schemas: `HealthResponse`, `ValidationReportResponse`, `DatasetMetadataResponse`, `DatasetQueryResponse`, `RowIssue`, `ValidationWarning`, and `ErrorResponse`. |
| [`backend/app/market_data/service.py`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/app/market_data/service.py) | **Modified** | Implemented bounded LRU dataset registry with thread locking (`threading.RLock`), complete OHLC checks ($High \ge \max(Open, Close)$, $Low \le \min(Open, Close)$), non-finite number rejection, explicit malformed numeric string detection, and error row sorting. |
| [`backend/app/api/v1/routes.py`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/app/api/v1/routes.py) | **Modified** | Offloaded CSV validation and registration to worker threadpool via `run_in_threadpool`, added typed `response_model` declarations to all endpoints, and guaranteed cleanup of uploaded files via `try ... finally: await file.close()`. |
| [`backend/tests/test_validation_engine.py`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/tests/test_validation_engine.py) | **Created** | Added 20 comprehensive unit tests covering minimal/complete OHLC, invalid OHLC bounds, non-numeric values, non-finite infinity, duplicates, and missing columns. |
| [`backend/tests/test_dataset_registry.py`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/tests/test_dataset_registry.py) | **Created** | Added 6 tests verifying capacity limits, LRU eviction order, recency refresh on access, 404 handling, and multi-threaded concurrency safety. |
| [`backend/tests/test_api_contracts.py`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/tests/test_api_contracts.py) | **Created** | Added 6 tests verifying OpenAPI schema response models, threadpool dispatching, 413 upload size limits, and 415 extension validation. |

---

## 4. Thread-Pool Execution Strategy (Objective A)

- **Worker Thread Offloading:** In `backend/app/api/v1/routes.py`, `preview_csv` and `upload_csv` use Starlette's `run_in_threadpool`:
  ```python
  return await run_in_threadpool(validate_csv, raw)
  ...
  result = await run_in_threadpool(register_csv_dataset, raw, filename=...)
  ```
- **Asynchronous Isolation:** By dispatching the CPU-intensive Pandas parsing and iteration to the AnyIO worker threadpool, FastAPI's main event loop remains non-blocking and instantly responsive to concurrent requests (such as `/health` probes and dataset queries).
- **Synchronous Routes:** `query_market_data` and `dataset_metadata` remain standard synchronous functions (`def`), which FastAPI natively dispatches to its worker threadpool.
- **Resource Cleanup:** Uploaded files are closed deterministically in `_read_upload`:
  ```python
  try:
      data = await file.read(max_bytes + 1)
      ...
  finally:
      await file.close()
  ```

---

## 5. Registry Capacity and Eviction Policy (Objective B)

- **Capacity Policy:** Configured with a default limit of **30 datasets** (`DEFAULT_DATASET_CAPACITY = 30`).
- **Data Structure & Eviction:** Backed by `collections.OrderedDict` protected by a reentrant thread lock (`threading.RLock`).
  - When capacity is reached, the least-recently-used dataset is evicted via `_DATASETS.popitem(last=False)`.
  - When a dataset is registered, it is placed at the most recent end via `_DATASETS.move_to_end(dataset_id)`.
- **Recency Refresh:** Accessing a dataset via `get_dataset_metadata(dataset_id)` or `query_dataset(...)` invokes `_DATASETS.move_to_end(dataset_id)`, actively preventing actively researched datasets from being evicted.
- **Thread Safety:** All registry and cache mutations are synchronized under `_DATASETS_LOCK` and `_CACHE_LOCK`, verified under multi-threaded concurrency testing.
- **Management Utilities:** Provided `get_dataset_registry_capacity()`, `set_dataset_registry_capacity(int)`, `get_dataset_registry_size()`, and `clear_dataset_registry()` for runtime administration and test fixtures.

---

## 6. CSV Validation Rules Added and Corrected (Objective C)

1. **Complete OHLC Consistency:**
   - When all relevant columns are present, the engine enforces:
     - $High \ge Low - 10^{-7}$ (`"High cannot be lower than low."`)
     - $High \ge Close - 10^{-7}$ (`"High cannot be lower than close."`)
     - $High \ge Open - 10^{-7}$ (`"High cannot be lower than open."`)
     - $Low \le Close + 10^{-7}$ (`"Low cannot be higher than close."`)
     - $Low \le Open + 10^{-7}$ (`"Low cannot be higher than open."`)
   - Omitted optional columns (such as `open` or `high`) do not trigger false-positive validation errors.
2. **Strict Numeric Parsing & Non-Finite Detection:**
   - Distinguishes empty cells (legitimate missing optional values accepted as `None`) from unparseable text.
   - Non-numeric strings in optional columns (e.g. `open="corrupt"`) are rejected with row-level error: `f"{col} must be a valid number when provided."`.
   - Non-finite numeric values (`inf`, `-inf`) are explicitly rejected with: `f"{col} must be a finite number."`.
3. **Price & Volume Boundary Integrity:**
   - Non-positive prices ($P \le 0$) rejected with: `f"{col} must be positive when provided."`.
   - Fixed duplicate error message: `close <= 0` generates exactly one `"Close must be a positive number."` reason.
   - Negative volume ($V < 0$) rejected with: `"Volume must be non-negative."`.
4. **Sorted Error Reporting:**
   - All error entries are sorted sequentially by row number (`errors.sort(key=lambda x: x["row"])`), ensuring duplicate observation errors and column format errors appear in ascending order.
5. **Cache Key Whitespace Normalization:**
   - Ticker lists are stripped and normalized prior to cache key generation (`[t.strip().upper() for t in tickers]`), eliminating redundant cache misses caused by whitespace differences.

---

## 7. Response Models and OpenAPI Schema Coverage (Objective D)

All version 1 endpoints now have explicit, typed Pydantic response models:

| Route Path | Method | Pydantic Response Model | Status Codes Documented |
|---|---|---|---|
| `/api/v1/health` | `GET` | `HealthResponse` | 200 |
| `/api/v1/market-data/preview` | `POST` | `ValidationReportResponse` | 200, 400, 413, 415 |
| `/api/v1/market-data/uploads` | `POST` | `DatasetMetadataResponse` | 200, 400, 413, 415, 422 |
| `/api/v1/market-data/datasets/query` | `POST` | `DatasetQueryResponse` | 200, 404, 422 |
| `/api/v1/market-data/datasets/{dataset_id}` | `GET` | `DatasetMetadataResponse` | 200, 404 |

Verified via Swagger UI (`/docs`) and `/openapi.json` with 100% typed reference coverage.

---

## 8. Test Suite Execution & Results (Objective E)

The test suite was expanded from **8 tests to 40 tests** covering all newly hardened layers:

```
============================= test session starts =============================
platform win32 -- Python 3.11.16, pytest-9.1.1, pluggy-1.7.0
rootdir: D:\Quants\Projects\quant-portfolio-engine-starter\backend
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.15.1
collected 40 items

tests/test_api_contracts.py::test_openapi_schema_contains_typed_response_models PASSED [  2%]
tests/test_api_contracts.py::test_preview_endpoint_invokes_threadpool PASSED [  5%]
tests/test_api_contracts.py::test_upload_endpoint_invokes_threadpool PASSED [  7%]
tests/test_api_contracts.py::test_upload_non_csv_extension_returns_415 PASSED [ 10%]
tests/test_api_contracts.py::test_upload_file_exceeding_10mb_returns_413 PASSED [ 12%]
tests/test_api_contracts.py::test_dataset_metadata_endpoint_retrieves_registered_data PASSED [ 15%]
tests/test_dataset_registry.py::test_registry_default_capacity PASSED    [ 17%]
tests/test_dataset_registry.py::test_registry_capacity_limit_and_lru_eviction PASSED [ 20%]
tests/test_dataset_registry.py::test_registry_access_refreshes_recency PASSED [ 22%]
tests/test_dataset_registry.py::test_query_dataset_refreshes_recency PASSED [ 25%]
tests/test_dataset_registry.py::test_unknown_dataset_id_raises_not_found PASSED [ 27%]
tests/test_dataset_registry.py::test_concurrent_registrations_and_reads PASSED [ 30%]
tests/test_market_data.py::test_health PASSED                            [ 32%]
tests/test_market_data.py::test_preview_valid_csv PASSED                 [ 35%]
tests/test_market_data.py::test_upload_and_query_inclusive_dates PASSED  [ 37%]
tests/test_market_data.py::test_invalid_price_is_reported_and_excluded PASSED [ 40%]
tests/test_market_data.py::test_missing_required_column_rejected PASSED  [ 42%]
tests/test_market_data.py::test_preview_and_query_with_sparse_optional_columns PASSED [ 45%]
tests/test_market_data.py::test_query_missing_dataset_returns_404 PASSED [ 47%]
tests/test_market_data.py::test_query_invalid_date_range_returns_422 PASSED [ 50%]
tests/test_validation_engine.py::test_valid_minimal_csv PASSED           [ 52%]
tests/test_validation_engine.py::test_valid_complete_ohlc_csv PASSED     [ 55%]
tests/test_validation_engine.py::test_invalid_high_lower_than_low PASSED [ 57%]
tests/test_validation_engine.py::test_invalid_high_lower_than_close PASSED [ 60%]
tests/test_validation_engine.py::test_invalid_high_lower_than_open PASSED [ 62%]
tests/test_validation_engine.py::test_invalid_low_higher_than_close PASSED [ 65%]
tests/test_validation_engine.py::test_invalid_low_higher_than_open PASSED [ 67%]
tests/test_validation_engine.py::test_non_numeric_in_required_field PASSED [ 70%]
tests/test_validation_engine.py::test_non_numeric_in_optional_field PASSED [ 72%]
tests/test_validation_engine.py::test_non_numeric_in_volume PASSED       [ 75%]
tests/test_validation_engine.py::test_non_finite_price_infinity PASSED   [ 77%]
tests/test_validation_engine.py::test_non_finite_volume_infinity PASSED  [ 80%]
tests/test_validation_engine.py::test_negative_and_zero_price_no_duplicate_error PASSED [ 82%]
tests/test_validation_engine.py::test_negative_volume PASSED             [ 85%]
tests/test_validation_engine.py::test_legitimate_missing_optional_values_allowed PASSED [ 87%]
tests/test_validation_engine.py::test_duplicate_observations_excluded_with_sorted_row_numbers PASSED [ 90%]
tests/test_validation_engine.py::test_invalid_date_format PASSED         [ 92%]
tests/test_validation_engine.py::test_unsupported_market_identifier PASSED [ 95%]
tests/test_validation_engine.py::test_missing_required_column_raises_value_error PASSED [ 97%]
tests/test_validation_engine.py::test_empty_and_whitespace_csv_raises_value_error PASSED [100%]

======================== 40 passed, 1 warning in 6.59s ========================
```

---

## 9. Static Code Quality & Linting Verification

- **Ruff Linter:** Executed `ruff check app tests`. Output: **"All checks passed!"** (Zero lint or import errors).
- **Python Byte-Compilation:** Executed `python -m compileall app tests`. Output: 100% clean compilation, zero syntax errors.
- **Application Startup Verification:** Tested `uvicorn app.main:app` via TestClient:
  - `/api/v1/health` $\rightarrow$ HTTP 200 OK
  - `/docs` $\rightarrow$ HTTP 200 OK
  - `/openapi.json` $\rightarrow$ HTTP 200 OK

---

## 10. Remaining Limitations & Operational Boundaries

1. **Volatile Process Memory:**
   - The dataset registry and TTL cache remain process-local in memory. Datasets are lost on process termination and cannot be shared across multi-process Uvicorn workers (`--workers > 1`). Durable PostgreSQL storage is deferred to Stage 8.
2. **Preview Payload Size:**
   - While `_read_upload` caps incoming uploads at 10 MB and 250,000 rows, `/api/v1/market-data/preview` returns all valid rows in `valid_data`. For very large files, network payload pagination may be introduced in a future session.
3. **No External Live Market Feeds:**
   - The engine strictly operates on uploaded historical CSV files. Streaming and vendor APIs remain deferred.

---

## 11. API Compatibility Assessment

- **Zero Breaking Changes:** All existing endpoint URLs, HTTP methods, request bodies, query filters, and response fields remain fully compatible with the existing API contract.
- **Contract Additions:** Added typed Pydantic models for OpenAPI documentation and response validation; added HTTP 413, 415, and 422 documentation in OpenAPI metadata.

---

## 12. Recommended Next Session (Session 04 Scope)

With the Market Data Engine fully hardened, thread-isolated, memory-bounded, and typed, the project is ready to advance to **Stage 2: Financial Mathematics Core**:
1. Implement pure numerical return calculators in `app/quant/math.py` (Simple returns $R_t$, Logarithmic returns $r_t$).
2. Implement sample and annualized volatility using market-specific trading days (252 for US, 250 for PSX).
3. Implement sample covariance and correlation matrices with symmetry and positive semi-definiteness assertions.
4. Implement drawdown analytics, Maximum Drawdown (MDD), and peak-to-trough duration.
5. Implement annualized Sharpe and Sortino ratios with parameterized risk-free rates.
6. Reconcile all calculation engines against independent hand-calculated numerical benchmark test fixtures.
