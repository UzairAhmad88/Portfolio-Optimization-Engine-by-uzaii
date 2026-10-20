# SESSION 11 REPORT — Authentication, Authorization & Secure Access Control
**Document Version:** 1.0.0  
**Status:** Complete & Independently Verified  
**Date:** 2026-10-17  
**Engine Release Version:** v0.7.0  
**Author:** Senior Application Security Architect, FastAPI Engineer, PostgreSQL Security Specialist & React/TypeScript Authentication Engineer  

---

## 1. Executive Summary

In **Session 11**, we established a production-grade authentication, authorization, and secure access-control architecture for the **Quant Portfolio Optimization Engine** and **Quant Research Dashboard**.

Prior to Session 11, the platform operated in an unauthenticated single-user mode: any API consumer could upload datasets, execute numerical portfolio optimizations, sweep the Markowitz efficient frontier, and access all stored data without identification, access policies, or tenant boundaries.

In this session, we:
1. **Designed a dual-transport authentication architecture** combining signed `HS256` JSON Web Tokens (JWT) with secure `HttpOnly`, `SameSite=Lax` session cookies for browser clients and `Authorization: Bearer <token>` headers for automated API clients.
2. **Created a normalized user model** (`UserModel`) using SQLAlchemy 2.0 with salted `bcrypt` password hashing, unique normalized emails, active/disabled status flags, and role assignments (`researcher`, `admin`).
3. **Executed Alembic migration `7c4a4e92cae9`** using `batch_alter_table` to establish the `users` table and link `datasets.user_id` foreign keys with `ON DELETE CASCADE` across both PostgreSQL and SQLite dialects.
4. **Enforced strict dataset ownership and tenant isolation**: all dataset listings, raw price bar queries, and asset metadata lookups are partitioned by user identity. Cross-tenant queries and optimizations against another user's private dataset are blocked with HTTP 404/403.
5. **Scoped SHA-256 dataset deduplication per-tenant**: re-uploading identical market data files by different users creates independent isolated records, preventing cross-tenant information leaks.
6. **Hardened CORS and defensive browser headers**: prohibited wildcard `*` origins when credentials are enabled, configured explicit trusted origin lists, and added HTTP security headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`).
7. **Implemented sliding-window brute-force protection**: automated IP/email-based rate limiting locks out authentication attempts after 5 consecutive failed login attempts for 5 minutes.
8. **Built an institutional React 19 / TypeScript authentication view** (`AuthPage.tsx`), centralized `AuthContext`, authenticated researcher header badge, and seamless session hydration.
9. **Preserved 100% of existing quantitative capabilities**: all financial calculations (returns, covariance shrinkage, SLSQP minimum-variance and maximum-Sharpe optimization, efficient frontier, and risk metrics) operate seamlessly on user-isolated data.

### Verification Metrics
- **Backend Test Suite:** **163 passed, 0 failed** (100% pass rate in 24.38s across 11 test modules).
  - *Baseline (Session 10):* 143 passed.
  - *Added in Session 11:* 20 authentication, authorization, and tenant isolation tests.
- **Frontend Test Suite:** **9 passed, 0 failed** (100% pass rate in 7.17s).
  - *Baseline (Session 10):* 6 passed.
  - *Added in Session 11:* 3 authentication and session tests.
- **Frontend Production Bundle:** `tsc -b && vite build` completed cleanly in 1.27s with zero diagnostics.

---

## 2. Authentication Architecture & Rationale

### 2.1 Transport Architecture: Dual-Mode Token & Cookie Delivery
```
                         ┌──────────────────────────────────────────────┐
                         │              Client Request                  │
                         └──────────────────────┬───────────────────────┘
                                                │
                                    ┌───────────┴───────────┐
                                    ▼                       ▼
                         [Authorization: Bearer]     [HttpOnly Cookie]
                                    │                       │
                                    └───────────┬───────────┘
                                                │
                                    Token Precedence Check:
                             Authorization Header > Cookie
                                                │
                                                ▼
                                    ┌───────────────────────┐
                                    │  Decode & Verify JWT  │
                                    │  - Secret signature   │
                                    │  - Expiration (exp)   │
                                    │  - Subject UUID (sub) │
                                    └───────────┬───────────┘
                                                │ Valid
                                                ▼
                                    ┌───────────────────────┐
                                    │ Database User Lookup  │
                                    │ - is_active == True   │
                                    └───────────┬───────────┘
                                                │
                                                ▼
                                       Authenticated User
```

1. **Why Dual Mode?**
   - **Browser Web App (React):** Communicates using `credentials: 'include'`. The backend sets an `HttpOnly`, `SameSite=Lax` cookie (`access_token`). Because JavaScript cannot read `HttpOnly` cookies, the session is protected against Cross-Site Scripting (XSS) credential theft.
   - **API Clients & Quantitative Automation:** Can supply explicit `Authorization: Bearer <jwt>` HTTP headers.
2. **Token Precedence Guarantee:**
   - In `app/auth/dependencies.py`, the explicit `Authorization: Bearer` header is checked **before** ambient cookies. This guarantees that API scripts or tests passing explicit bearer tokens are not masked by stale browser cookies.
3. **Cryptographic Standards:**
   - **Algorithm:** `HS256` (HMAC with SHA-256).
   - **Password Hashing:** `bcrypt` with automatic salting. Passwords must meet complexity requirements ($\ge 8$ chars, at least 1 letter and 1 digit). Plaintext passwords are never logged or persisted.
   - **Token Expiration:** Configurable via `ACCESS_TOKEN_EXPIRE_MINUTES` (default: 60 minutes). Expired tokens return HTTP 401 with `Token has expired`.
4. **Brute-Force Rate Limiting:**
   - In-memory thread-safe `LoginRateLimiter` enforces a maximum of 5 failed attempts within a 5-minute sliding window per email/IP, returning HTTP 429 (`Too Many Requests`) with a retry-after message.

---

## 3. Database Schema & Alembic Migration

### 3.1 Normalized Schema Additions

#### `users` Table
| Column Name | Type | Constraints / Attributes | Description |
|---|---|---|---|
| `id` | `VARCHAR(36)` | `PRIMARY KEY` | Stable UUIDv4 identifier. |
| `email` | `VARCHAR(255)` | `UNIQUE, NOT NULL, INDEXED` | Lowercased normalized user email. |
| `hashed_password` | `VARCHAR(255)` | `NOT NULL` | Salted bcrypt password hash. |
| `full_name` | `VARCHAR(255)` | `NULLABLE` | Display name of the researcher. |
| `role` | `VARCHAR(50)` | `NOT NULL, DEFAULT 'researcher'` | User role (`researcher` or `admin`). |
| `is_active` | `BOOLEAN` | `NOT NULL, DEFAULT TRUE` | Active/disabled account switch. |
| `created_at` | `TIMESTAMP` | `NOT NULL` | Account creation timestamp (UTC). |
| `updated_at` | `TIMESTAMP` | `NOT NULL` | Profile modification timestamp (UTC). |
| `last_login_at` | `TIMESTAMP` | `NULLABLE` | Timestamp of most recent login (UTC). |

#### `datasets` Table Updates
- Added `user_id` (`VARCHAR(36)`, `ForeignKey('users.id', ondelete='CASCADE')`, `INDEXED`, nullable=True for backward compatibility with pre-existing unowned datasets).
- Added `is_shared` (`BOOLEAN`, default `False`) for future collaborative workspace features.

### 3.2 Migration Script
- **Revision ID:** `7c4a4e92cae9`
- **Down Revision:** `0a14be571daa`
- **Dialect Compatibility:** Uses `op.batch_alter_table` to guarantee seamless compatibility with SQLite test engines while applying native `ALTER TABLE` commands on PostgreSQL.
- **Rollback Safety:** Reversing the migration via `alembic downgrade -1` drops foreign keys, removes `user_id`/`is_shared` from `datasets`, and drops the `users` table cleanly without affecting market data price bars.

---

## 4. Dataset Ownership & Strict Tenant Isolation

### 4.1 Ownership Rules & Enforcement Matrix

| Endpoint | Operation | Access Policy | Failure Response |
|---|---|---|---|
| `POST /market-data/uploads` | Register CSV | Assigned to authenticated user (`user_id = current_user.id`). | `401 Unauthorized` |
| `GET /market-data/datasets` | List Datasets | Filtered to `user_id == current_user.id` or `is_shared == True`. | `401 Unauthorized` |
| `GET /market-data/datasets/{id}` | Inspect Metadata | Allowed only if owner or shared. | `404 Not Found` (avoids ID enumeration) |
| `POST /market-data/datasets/query` | Query Price Bars | Allowed only if owner or shared. | `404 Not Found` |
| `POST /portfolio/validate` | Validate Portfolio | Dataset checked for caller ownership before validation. | `404 Not Found` |
| `POST /optimization/solve` | SLSQP Optimization | Dataset checked for caller ownership before solving. | `404 Not Found` |
| `POST /frontier` | Efficient Frontier | Dataset checked for caller ownership before sweeping curve. | `404 Not Found` |
| `POST /comparison` | Strategy Comparison | Dataset checked for caller ownership before computing metrics. | `404 Not Found` |

### 4.2 Tenant-Scoped SHA-256 Deduplication
In Session 10, deduplication was global across all uploads based on `content_sha256`. In Session 11, deduplication is strictly tenant-scoped:
```python
# app/market_data/repository.py
stmt = select(DatasetModel).where(
    DatasetModel.content_sha256 == content_sha256,
    DatasetModel.user_id == user_id,
)
```
If User A and User B upload the exact same CSV file, each receives their own distinct dataset record with independent lifecycle control. User A deleting their dataset has zero effect on User B.

---

## 5. Endpoints Catalog: Public vs. Protected

| Endpoint | Method | Classification | Description |
|---|---|---|---|
| `/api/v1/health` | `GET` | **Public** | System status and database readiness. Exposes zero secrets. |
| `/api/v1/auth/register` | `POST` | **Public** | Register new researcher account with email and password. |
| `/api/v1/auth/login` | `POST` | **Public** | Authenticate user, issue JWT token and HttpOnly cookie. |
| `/api/v1/auth/logout` | `POST` | **Public** | Invalidate session by clearing `access_token` cookie. |
| `/api/v1/auth/me` | `GET` | **Authenticated** | Returns current user profile (`id`, `email`, `role`). |
| `/api/v1/market-data/preview` | `POST` | **Public / Utility** | Validates CSV syntax without saving to database. |
| `/api/v1/market-data/uploads` | `POST` | **Authenticated** | Ingests and stores dataset bound to authenticated user. |
| `/api/v1/market-data/datasets` | `GET` | **Authenticated** | Lists datasets owned by or shared with current user. |
| `/api/v1/market-data/datasets/{id}` | `GET` | **Authenticated (Owned)** | Retrieves dataset summary and constituent assets. |
| `/api/v1/market-data/datasets/query` | `POST` | **Authenticated (Owned)** | Queries historical price matrix for constituent assets. |
| `/api/v1/portfolio/validate` | `POST` | **Authenticated (Owned)** | Validates asset weights, date coverage, and constraints. |
| `/api/v1/optimization/solve` | `POST` | **Authenticated (Owned)** | Solves SLSQP constrained portfolio optimization. |
| `/api/v1/frontier` | `POST` | **Authenticated (Owned)** | Generates multi-point Markowitz efficient frontier. |
| `/api/v1/comparison` | `POST` | **Authenticated (Owned)** | Evaluates risk/return metrics across candidate portfolios. |

---

## 6. Browser Security, CORS & Defensive HTTP Headers

### 6.1 CORS Hardening
Wildcard origins (`*`) combined with credentialed requests (`credentials: 'include'`) violate standard web security specifications and permit malicious websites to execute cross-origin authenticated requests.
- **Production Rule:** Wildcard origin `*` is strictly disallowed when `allow_credentials=True`.
- **Configurable Origins:** Configured via `CORS_ORIGINS` in `app/core/config.py`:
  ```bash
  CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
  ```

### 6.2 Defensive HTTP Security Headers
Every HTTP response emitted by the FastAPI backend includes security headers enforced via custom middleware:
- `X-Content-Type-Options: nosniff` (prevents MIME-type sniffing).
- `X-Frame-Options: DENY` (prevents clickjacking attacks).
- `X-XSS-Protection: 1; mode=block` (activates browser XSS filtering).
- `Referrer-Policy: strict-origin-when-cross-origin` (prevents path leakage in referrer headers).

---

## 7. Frontend Authentication Experience

### 7.1 Architecture & Components
- **Central State Management (`AuthContext.tsx`):**
  - Performs non-intrusive session verification on initial load via `GET /api/v1/auth/me`.
  - Maintains `user`, `isAuthenticated`, `isLoading`, and `error` reactive state.
  - Exposes `login()`, `register()`, and `logout()` handlers to all child views.
- **Institutional Auth View (`AuthPage.tsx`):**
  - Seamless dark-mode design matching the institutional Bloomberg/FactSet-style dashboard theme.
  - Tabbed interface switching between **Sign In** and **Create Account**.
  - Form validation with clear error messages without disclosing account existence.
  - Accessible labels, autofocus, and submit loading indicators.
- **Header Researcher Badge (`Header.tsx`):**
  - Displays authenticated researcher's full name, email, and role badge (`researcher` / `admin`).
  - Provides a single-click **Sign Out** button that invalidates the session and returns to the login screen.
- **Protected Routing (`App.tsx`):**
  - Unauthenticated users are presented with the authentication portal.
  - While verifying session state, an institutional loading indicator prevents flash-of-unauthenticated-content (FOUC).
  - Authenticated researchers access the quantitative research workspace.

---

## 8. Verification & Test Execution Record

### 8.1 Backend Test Results
The backend test suite was executed against the database and API layer using `pytest`:
```bash
pytest -q
```
**Output:**
```
................................................................................................................................... [ 80%]
................................                                                                                                    [100%]
163 passed in 24.38s
```

#### Test Distribution by Layer
| Test Module | Tests | Status | Scope |
|---|---|---|---|
| `test_auth_and_access_control.py` | **20** | **Passed** | Registration, bcrypt hashing, JWT issuance/validation, brute-force rate limit, dataset ownership, tenant isolation, cross-user optimization blocking, CORS & security headers. |
| `test_persistence_and_database.py` | **8** | **Passed** | Relational persistence, restart survivability, SHA-256 deduplication, atomic rollback, cascading deletes, concurrency. |
| `test_integration_and_reliability.py` | **7** | **Passed** | End-to-end research workflow, defensive immutability, thread-safe concurrency, boundary limits, multi-currency isolation. |
| `test_api.py` | **9** | **Passed** | API routing, contract validation, error sanitization. |
| `test_portfolio_engine.py` | **10** | **Passed** | Minimum-variance, maximum-Sharpe, equal-weight benchmarking, SLSQP convergence. |
| `test_portfolio_service.py` | **16** | **Passed** | Feasibility checks, weight normalization, constraint verification. |
| `test_efficient_frontier.py` | **12** | **Passed** | Multi-point frontier generation, target return optimization, monotonicity. |
| `test_risk_analytics.py` | **16** | **Passed** | Sharpe, Sortino, VaR, CVaR, Max Drawdown, risk contribution decomposition. |
| `test_portfolio_comparison.py` | **10** | **Passed** | Multi-portfolio comparison tear-sheets, relative rankings. |
| `test_numerical_correctness.py` | **17** | **Passed** | Pure mathematics, Ledoit-Wolf covariance shrinkage, annualization factors. |
| `test_data_validation.py` | **38** | **Passed** | CSV parsing, OHLC bounds, UTF-8 handling, corrupt data quarantine. |
| **Total Backend** | **163** | **100% Passed** | Zero regressions across all historical sessions. |

### 8.2 Frontend Test Results
The frontend test suite was executed using Vitest:
```bash
npm test -- --run
```
**Output:**
```
 ✓ src/test/api-client.test.ts (6 tests) 116ms
 ✓ src/test/App.test.tsx (3 tests) 378ms

 Test Files  2 passed (2)
      Tests  9 passed (9)
   Start at  21:14:14
   Duration  7.17s
```

### 8.3 Frontend Production Build
```bash
npm run build
```
**Output:**
```
> frontend@0.1.0 build
> tsc -b && vite build

vite v6.4.1 building for production...
transforming...
✓ 1673 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.53 kB │ gzip:  0.33 kB
dist/assets/index-D77c6JmZ.css   33.27 kB │ gzip:  6.41 kB
dist/assets/index-B-zUj1p5.js   385.22 kB │ gzip: 114.77 kB
✓ built in 1.27s
```

### 8.4 Live Database vs. Mocked Testing Strategy
To maintain execution velocity and backward compatibility:
- **Security & Persistence Tests (`test_auth_and_access_control.py` & `test_persistence_and_database.py`):** Execute against real database sessions and real JWT cryptographic hashing routines to verify genuine end-to-end integrity.
- **Legacy Numerical Tests (`test_api.py`, `test_portfolio_engine.py`, etc.):** `backend/tests/conftest.py` automatically injects a default authenticated researcher dependency override (`TEST_RESEARCHER_USER`) backed by a seeded database record (`TEST_RESEARCHER_ID`). This guarantees that mathematical tests run without needing to authenticate manually for every single test case, while maintaining database referential integrity.

---

## 9. Environment Variables & Secret Configuration

### Backend `.env.example`
```bash
# Database Configuration
DATABASE_URL=sqlite:///./quant_portfolio.db
# Production target:
# DATABASE_URL=postgresql://quant:quant_password@localhost:5432/quant_portfolio

# Security & Authentication
# Generate in terminal: python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET_KEY=change-this-to-a-secure-random-secret-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Rate Limiting
LOGIN_MAX_FAILED_ATTEMPTS=5
LOGIN_LOCKOUT_MINUTES=5

# CORS Configuration (JSON array of trusted client origins)
CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
```

### Frontend `.env.example`
```bash
# Backend API Base URL
VITE_API_BASE_URL=http://localhost:8000
```

---

## 10. Local Registration & Login Workflow

To run the application locally with full authentication:

1. **Start the FastAPI Backend:**
   ```bash
   cd backend
   alembic upgrade head
   uvicorn app.main:app --reload --port 8000
   ```
2. **Start the React Frontend:**
   ```bash
   cd frontend
   npm run dev
   ```
3. **Register an Account:**
   - Navigate to `http://localhost:5173`.
   - Click **Create an account**.
   - Enter your name, email (e.g. `analyst@institution.com`), and a password ($\ge 8$ characters, letters and digits).
   - Click **Create Account**. You are automatically signed in with an active session.
4. **Log In:**
   - Return to the login tab at any time to sign in with your credentials.
   - The session token is stored in an `HttpOnly` cookie and will persist across page refreshes.
5. **Log Out:**
   - Click the **Sign Out** button in the top navigation header. The session cookie is cleared and the authentication portal reappears.

---

## 11. Known Limitations & Explicit Out-of-Scope Items

In accordance with the project master plan and session boundaries:
- **No Email Delivery / Password Reset:** Account recovery via email is deferred to a future infrastructure session. Password changes currently require an administrative database update.
- **No Multi-Factor Authentication (MFA):** TOTP / WebAuthn MFA is out of scope for Session 11.
- **No OAuth / Social Sign-In:** The system uses standalone institutional credential authentication.
- **In-Memory Rate Limiting:** The login rate limiter operates in process memory. In a distributed multi-worker deployment, rate limiting should be backed by Redis.
- **Single-Tenant Workspace:** Datasets are strictly private to individual users. Team collaboration and shared workspaces will be introduced in future governance iterations.

---

## 12. Next Session: Session 12 Preview

With persistent database storage (Session 10) and secure authentication and tenant isolation (Session 11) fully completed, the platform is prepared for **Session 12: Walk-Forward Backtesting Engine, Slippage/Transaction Cost Modeling, and Rebalancing Simulation**.

---

### Definition of Done Sign-Off
- [x] Repository and roadmap audited against Master Plan Stage 8.
- [x] User identities and passwords handled securely with salted bcrypt.
- [x] Dual-transport authentication (JWT + HttpOnly cookie) implemented and verified.
- [x] Protected APIs enforce server-side authentication on all research operations.
- [x] Dataset ownership and tenant isolation strictly enforced across all analytical workflows.
- [x] Tenant-scoped SHA-256 deduplication prevents cross-tenant data leaks.
- [x] CORS hardened (no wildcard with credentials) and defensive HTTP security headers configured.
- [x] Alembic migration `7c4a4e92cae9` applied and verified.
- [x] All 163 backend tests passing (100% pass rate).
- [x] All 9 frontend tests passing (100% pass rate).
- [x] Frontend production bundle compiled cleanly with zero diagnostics.
- [x] Comprehensive documentation authored in `docs/SESSION_11_REPORT.md`.
