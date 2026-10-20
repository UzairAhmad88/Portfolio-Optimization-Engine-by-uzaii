# Development Standards & Engineering Guidelines
**Quant Portfolio Optimization Engine**  
**Status:** Mandatory Engineering Policy  
**Effective Date:** 2026-10-16  

---

## 1. Architectural Principles

### 1.1 Modular Monolith First
- Maintain a single cohesive repository organized as a modular monolith. Do not prematurely split into microservices, distributed actors, or multi-repo structures.
- Strict layered boundary enforcement:
  - **Transport / API Layer (`app/api`):** Route definitions, HTTP serialization, status codes, query parsing, request/response DTOs. Zero financial or data processing logic in routes.
  - **Domain / Services Layer (`app/market_data`, `app/analytics`, etc.):** Orchestration, caching, input sanitation, dataset registration.
  - **Quantitative Core (`app/quant` or equivalent):** Pure mathematical, statistical, and optimization functions. Must depend only on NumPy, Pandas, SciPy, or CVXPY, completely decoupled from FastAPI and HTTP concepts.
  - **Persistence Layer (`app/db` / future):** Repository patterns, SQL models, migrations.

### 1.2 Typed API Contracts & Versioning
- All endpoints must reside under versioned prefixes (e.g., `/api/v1/`).
- Every endpoint must specify explicit Pydantic `response_model` classes. Untyped dictionary returns (`dict`) are forbidden.
- OpenAPI schemas generated at `/docs` and `/openapi.json` must be self-documenting with explicit field descriptions and validation constraints.

### 1.3 Asynchronous Execution Safety
- Do not execute blocking CPU-intensive calculations (such as Pandas data validation, matrix inversions, Monte Carlo simulations, or quadratic programming solvers) directly inside `async def` route handlers.
- CPU-bound routines must be scheduled onto the worker threadpool via `run_in_threadpool` or handled by synchronous route definitions (`def`) to preserve event loop responsiveness.

---

## 2. Quantitative Correctness & Mathematical Integrity

### 2.1 Backend Calculation Authority
- All financial, statistical, and portfolio calculations must reside in thoroughly tested backend Python modules. Never perform statistical calculations in frontend JavaScript/TypeScript.

### 2.2 Transparent Conventions & Assumptions
- **Return Conventions:** Explicitly document whether returns are arithmetic ($R_t = \frac{P_t - P_{t-1}}{P_{t-1}}$) or geometric/logarithmic ($r_t = \ln(P_t / P_{t-1})$).
- **Annualization Factors:** Explicitly parameterize trading day conventions. Never hardcode magic numbers:
  - US Equities: 252 trading days per annum.
  - PSX (Pakistan Stock Exchange): 250 trading days per annum.
  - Cryptocurrencies (if ever added): 365 days.
- **Risk-Free Rate:** Document source, compounding frequency, and duration matching for Sharpe/Sortino ratios.
- **Timezone & Calendar Awareness:** Respect exchange-specific trading calendars and settlement holidays. Do not assume identical trading days between US and PSX markets.

### 2.3 Strict Missing-Data & Quality Policy
- **Never silently fabricate, forward-fill, backward-fill, or impute missing prices** without explicit user opt-in and audit tracking.
- Missing dates, price gaps, and non-trading days must be detected, highlighted, and reported in validation metadata.
- Data alignment across multi-asset portfolios must use explicit intersection or union policies with documented drop/fill rules.

### 2.4 Solver Robustness & Infeasibility Handling
- Optimization solvers (SciPy, CVXPY) can encounter numerical instability, ill-conditioned covariance matrices, non-positive semi-definite (PSD) matrices, or conflicting constraints.
- Infeasible problems or solver non-convergence must be treated as **first-class domain results**, not unhandled 500 exceptions. Return structured diagnostic information explaining why constraints could not be satisfied.
- Always verify covariance matrices with eigenvalue decomposition ($\lambda_i \ge 0$) or apply shrinkage/regularization (e.g., Ledoit-Wolf) when asset count approaches observation count ($N \approx T$).

---

## 3. Human-Computer Interaction (HCI) & UI/UX Standards

### 3.1 Visual Direction & Professional Tone
- **Institutional Aesthetic:** Use sleek, high-contrast, professional data-dense styling inspired by Bloomberg Terminal, FactSet, and modern quantitative research platforms.
- Avoid toy aesthetics, playful gradients, or cartoonish graphics. Use dark/light institutional palettes (e.g., deep slate, midnight navy, neutral gray, high-contrast crisp text).
- Monospace font families for numerical tables and ticker symbols to ensure clean tabular alignment.

### 3.2 Information Architecture & User Control
- **Task-Oriented Workflow:** Guide users logically from Data Ingestion $\rightarrow$ Data Quality Review $\rightarrow$ Asset Selection $\rightarrow$ Constraint Definition $\rightarrow$ Optimization $\rightarrow$ Risk/Frontier Inspection $\rightarrow$ Report Export.
- **Explicit User Feedback:** Every user action must trigger unambiguous UI feedback. Progress bars and spinner states for calculations taking $> 200\text{ ms}$.
- **Five Standard Component States:** Every view, widget, and table must handle all 5 states:
  1. *Loading / Processing State* (skeletons or progress indicators).
  2. *Empty State* (actionable guidance on how to populate data).
  3. *Validation / Warning State* (non-blocking notices, e.g. missing optional fields).
  4. *Error State* (actionable resolution message, retry controls).
  5. *Success / Populated State* (clean, formatted results).

### 3.3 Data Presentation & Financial Formatting
- Currency numbers must display standard currency symbols or ISO codes with exact decimal precision (e.g., `$1,234.50` or `PKR 125.50`).
- Percentages must display the `%` symbol and standard 2-decimal precision (e.g., `+12.45%`).
- Charts must have complete legends, unit labels, axis ranges, tooltips showing exact values on hover, and clear date stamps.
- **No Fictional Data:** Never display placeholder synthetic returns as live or verified market data. Clearly watermark sample/sandbox datasets.

### 3.4 Accessibility (a11y)
- Maintain minimum WCAG 2.1 AA contrast ratios (4.5:1 for normal text, 3:1 for large text and interactive components).
- Ensure keyboard navigability for all interactive elements, modal dialogs, and table filters.
- Screen-reader accessible form labels, ARIA attributes for live regions, and semantic HTML table structures.

---

## 4. Testing, Quality Assurance & Change Management

### 4.1 Test Hierarchy & Coverage Requirements
- **Unit Tests:** Every mathematical function, parser, and validator must have isolated unit tests.
- **Integration Tests:** Every FastAPI endpoint must have end-to-end HTTP integration tests verifying:
  - Happy path with full schema.
  - Happy path with minimal required schema.
  - Edge cases (boundary dates, zero/negative inputs, empty fields).
  - Validation failures (4xx errors with explicit, helpful error shapes).
  - Missing resources (404 handling).
- **Numerical Benchmark Tests:** Calculation modules in Stage 2+ must validate results against independent, hand-calculated or academic standard benchmark test cases (tolerance: $10^{-6}$ or specified epsilon).

### 4.2 Change Management Rules
- Never alter behavior without adding or updating corresponding tests.
- Never declare a session complete without running the entire test suite and confirming zero regressions.
- Preserve existing valid code; refactor only with explicit justification and evidence.

---

## 5. Security & Operational Safety

### 5.1 Credential & Secret Management
- Never commit secrets, API keys, passwords, or production tokens to source control.
- Configuration must load from environment variables via Pydantic Settings. Provide `.env.example` with benign default names.

### 5.2 Input Validation & Request Limiting
- Treat all external uploads as hostile. Enforce:
  - File size limits (currently 10 MB).
  - Row count limits (currently 250,000 rows).
  - Strict file extension and MIME type validation.
  - CSV bomb / entity expansion safeguards.

### 5.3 Information Disclosure Prevention
- Server tracebacks and internal stack traces must **never** be exposed in API error responses.
- Catch internal errors, log detailed diagnostics with request correlation IDs to backend logs, and return sanitized, human-readable error summaries to clients.
