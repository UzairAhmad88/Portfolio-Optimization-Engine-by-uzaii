# Session 02 Report — Requirements & System Architecture
**Project:** Quant Portfolio Optimization Engine  
**Session:** Session 02 (Architecture & Specification Baseline)  
**Date:** 2026-10-16  
**Status:** Completed & Ready for Review  

---

## 1. Executive Summary

In **Session 02**, we translated the high-level business vision and quantitative finance roadmap into an explicit, implementable system specification without altering application behavior or introducing unapproved code. 

We established five formal architectural artifacts:
1. `docs/REQUIREMENTS_SPEC.md` — 50 Functional Requirements (categorized as Current, Next, Later) and 14 Non-Functional Requirements.
2. `docs/SYSTEM_ARCHITECTURE.md` — Modular Monolith architecture, layer decomposition, Mermaid diagrams, concurrency model, and 5 Architecture Decision Records (ADRs).
3. `docs/FINANCIAL_DATA_CONTRACTS.md` — Canonical data schemas, OHLC consistency, US vs. PSX cross-market rules, annualization conventions (252 vs. 250), and mathematical contracts.
4. `docs/TEST_STRATEGY.md` — 7-layer testing pyramid, formal mathematical invariants, benchmark datasets, and CI quality gates.
5. `docs/SESSION_02_REPORT.md` — This comprehensive session audit report.

No application code was modified in this session, preserving the 8 passing tests established in Session 01.

---

## 2. Files Inspected & Verified

The following files across the repository were inspected and evaluated:
- `README.md` — Quickstart, environment requirements, and project scope.
- `docs/MASTER_PLAN.md` — 8-stage product lifecycle.
- `docs/STAGE_1_SPEC.md` — Functional specifications for the Market Data Engine.
- `docs/API_CONTRACT.md` — Existing v1 REST endpoint shapes.
- `docs/REPOSITORY_AUDIT.md` — Baseline audit, technical risks, and defect log.
- `docs/DEVELOPMENT_STANDARDS.md` — Architecture, quantitative correctness, HCI, and testing standards.
- `docs/SESSION_01_REPORT.md` — Baseline verification status and test logs.
- `backend/app/main.py` — FastAPI application initialization and router mounting.
- `backend/app/api/v1/routes.py` — Route definitions, request schemas, and upload handlers.
- `backend/app/market_data/service.py` — CSV validation, caching, dataset registration, and querying logic.
- `backend/tests/test_market_data.py` — 8 automated tests (5 original + 3 regression/boundary tests).
- `backend/pyproject.toml` — Build system, declared dependencies, and pytest configuration.

---

## 3. Documents Created or Changed

| Document | Nature of Change | Summary of Content |
|---|---|---|
| [`docs/REQUIREMENTS_SPEC.md`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/docs/REQUIREMENTS_SPEC.md) | **Created** | Comprehensive user workflows (1–10), 50 numbered Functional Requirements with lifecycle status (`Current`, `Next`, `Later`), and 14 measurable Non-Functional Requirements. |
| [`docs/SYSTEM_ARCHITECTURE.md`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/docs/SYSTEM_ARCHITECTURE.md) | **Created** | Modular Monolith justification, C4 System Context Diagram, Layered Component Diagram, Sequence Data Flow, Async Threadpool Concurrency Model, Storage Evolution Path, and 5 ADRs. |
| [`docs/FINANCIAL_DATA_CONTRACTS.md`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/docs/FINANCIAL_DATA_CONTRACTS.md) | **Created** | Canonical price bar schema, complete OHLC rules, zero-imputation policy, US (252) vs PSX (250) annualization conventions, simple vs log return rules, and solver infeasibility contracts. |
| [`docs/TEST_STRATEGY.md`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/docs/TEST_STRATEGY.md) | **Created** | 7-layer testing pyramid, formal mathematical invariants table (`INV-001` through `INV-009`), synthetic and real-world benchmark datasets, and CI quality gates. |
| [`docs/SESSION_02_REPORT.md`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/docs/SESSION_02_REPORT.md) | **Created** | Session summary, decisions made, open questions, implementation conflicts, and recommended Session 03 scope. |

---

## 4. Key Architectural Decisions Made

1. **Modular Monolith Over Microservices (ADR-01):**
   - Retaining a single cohesive backend package avoids high-overhead network serialization of dense $T \times N$ return matrices and simplifies mathematical testing and reproducibility.
2. **Worker Threadpool for CPU-Bound Analytics (ADR-02):**
   - Wrapping heavy Pandas parsing, covariance estimations, and mathematical solvers in `starlette.concurrency.run_in_threadpool` guarantees that FastAPI's `asyncio` event loop is never blocked.
3. **Decoupled Quantitative Core as a Pure Library:**
   - Code in `app/quant/` is strictly prohibited from importing web frameworks (`fastapi`, `starlette`, `pydantic`). Mathematical algorithms take and return pure NumPy arrays, Pandas DataFrames, or standard dataclasses.
4. **Market-Specific Annualization Conventions:**
   - Formalized 252 trading days for US equities and 250 trading days for PSX equities. Hardcoded magic numbers are forbidden.
5. **Strict Zero-Imputation Policy:**
   - The engine will never forward-fill or synthesize missing market prices during ingestion. Missing data is highlighted through explicit warnings, and multi-asset alignment uses documented intersection policies.
6. **Stateless Jobs & Cryptographic Provenance:**
   - Every analytical execution produces a parameter manifest containing the input dataset SHA-256 digest, date range, formula options, and solver version, enabling $100\%$ deterministic replay.
7. **Phased Storage Evolution (ADR-05):**
   - Process-local bounded in-memory storage for Stages 1–5; lightweight SQLite for Stage 6–7 local research; PostgreSQL + SQLAlchemy 2.0 for Stage 8 production.

---

## 5. Identified Conflicts with Existing Implementation

The architectural audit revealed specific discrepancies between the current Stage 1 scaffold and our target architecture. These are cataloged for resolution in future sessions:

1. **Async Route Event Loop Blocking (High Priority):**
   - *Conflict:* `/api/v1/market-data/preview` and `/uploads` in [routes.py](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/app/api/v1/routes.py#L40-L59) are `async def` functions calling synchronous, CPU-intensive Pandas routines (`validate_csv`).
   - *Remediation:* Offload to `run_in_threadpool` or declare routes as standard `def`.
2. **Unbounded Dataset Memory Accumulation (High Priority):**
   - *Conflict:* `_DATASETS` in [service.py](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/app/market_data/service.py#L19) has no maximum capacity, TTL, or eviction policy, creating OOM vulnerability under repeated uploads.
   - *Remediation:* Add a capacity limiter (e.g. max 30 datasets) with FIFO/LRU eviction.
3. **Incomplete OHLC Consistency Checking (Medium Priority):**
   - *Conflict:* [service.py](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/app/market_data/service.py#L111-L114) only verifies `high < low`. It does not verify `close > high`, `open > high`, `close < low`, or `open < low`.
   - *Remediation:* Add complete OHLC relationship assertions in `validate_csv`.
4. **Silent Coercion of Unparseable Strings in Optional Numeric Columns (Medium Priority):**
   - *Conflict:* `pd.to_numeric(..., errors="coerce")` silently converts non-numeric strings (e.g. `open="invalid"`) to `NaN` without recording a row error.
   - *Remediation:* Distinguish between empty/missing cells (valid optional `None`) and corrupted non-numeric text (row error).
5. **Missing Pydantic Response Models in Routes (Medium Priority):**
   - *Conflict:* Routes in [routes.py](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/app/api/v1/routes.py) lack `response_model` declarations, rendering Swagger `/docs` schemas empty (`{}`).
   - *Remediation:* Define typed Pydantic models for all responses.

---

## 6. Open Questions & Areas of Uncertainty

1. **Cross-Market Portfolio Currency Alignment:**
   - *Uncertainty:* When a portfolio combines US (USD) and PSX (PKR) assets, should the engine require an uploaded historical FX rate series (`USD/PKR`), or allow the user to optimize in local returns with a documented currency-risk disclaimer?
   - *Recommended Default:* Default to single-market portfolios (`US` or `PSX`). For cross-market universes, require an explicit base currency and FX conversion table in Stage 3.
2. **Solver Dependency Licensing (SciPy vs. CVXPY):**
   - *Uncertainty:* SciPy (BSD license) is already available and handles standard Mean-Variance and Max Sharpe (SLSQP). CVXPY simplifies complex cone programming but introduces additional solver dependencies (OSQP, ECOS, SCS).
   - *Recommended Default:* Implement Stage 4 optimization using pure SciPy SLSQP first; introduce CVXPY only if advanced conic constraints (e.g. transaction cost regularization, L1 sparsity) are approved.
3. **Large Preview Response Payload:**
   - *Uncertainty:* `/api/v1/market-data/preview` returns `valid_data` containing all validated rows. For a 250,000-row file, this generates a 20–50 MB JSON response.
   - *Recommended Default:* Cap preview data payload to the first 100 rows with an explicit `"preview_truncated": true` flag in the response metadata.

---

## 7. Completion Gate Verification

- [x] All five required deliverables created and verified for internal consistency.
- [x] Functional and Non-Functional Requirements uniquely identified and mapped to lifecycle phases.
- [x] Modular Monolith architecture, boundaries, and concurrency patterns defined with Mermaid diagrams.
- [x] Financial contracts, OHLC consistency rules, and US/PSX conventions documented.
- [x] 7-layer testing strategy and mathematical invariants cataloged.
- [x] Existing implementation code preserved with zero behavioral changes.
- [x] Existing 8 automated tests remain completely passing.
- [x] Strict stopping condition observed (no premature implementation of Stage 2+).

---

## 8. Recommended Next Session (Session 03 Scope)

Now that the system architecture and requirements baseline are established, **Session 03** should focus on **Hardening the Market Data Engine & Establishing Typed Contracts**:
1. **Remediate High-Priority Architecture Conflicts:**
   - Wrap CPU-bound CSV parsing in `run_in_threadpool` to protect FastAPI's event loop.
   - Introduce bounded capacity (max 30 datasets with LRU eviction) to `_DATASETS`.
2. **Refine Market Data Quality Engine:**
   - Implement complete OHLC consistency validation ($High \ge \max(Open, Close)$ and $Low \le \min(Open, Close)$).
   - Reject unparseable strings in optional numeric columns rather than silently coercing them.
   - Fix duplicate error message on `close <= 0`.
3. **Declare Typed Pydantic Response Models:**
   - Add explicit response schemas (`ValidationReportResponse`, `DatasetMetadataResponse`, `DatasetQueryResponse`) to all v1 endpoints to make OpenAPI `/docs` fully self-documenting.
4. **Expand Test Coverage:**
   - Add automated integration tests verifying these hardened boundary conditions.
