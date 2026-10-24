# SESSION 97 REPORT — STAGING DEPLOYMENT BLUEPRINT & RELEASE CANDIDATE REVALIDATION

**Project:** Quantitative Portfolio Optimization Engine (`QPE`)  
**Repository:** `https://github.com/UzairAhmad88/Portfolio-Optimization-Engine-by-uzaii`  
**Branch:** `main`  
**Application Version:** `1.0.0`  
**Current Baseline Commit SHA:** [`2f3843d9e49d524e5db75da44e955cfc75737f59`](https://github.com/UzairAhmad88/Portfolio-Optimization-Engine-by-uzaii/commit/2f3843d9e49d524e5db75da44e955cfc75737f59)  
**Proposed Release Target SHA:** [`2f3843d9e49d524e5db75da44e955cfc75737f59`](https://github.com/UzairAhmad88/Portfolio-Optimization-Engine-by-uzaii/commit/2f3843d9e49d524e5db75da44e955cfc75737f59)  
**Exact-Target Remote CI Run:** [Run ID `40128394775`](https://github.com/UzairAhmad88/Portfolio-Optimization-Engine-by-uzaii/actions/runs/40128394775) (100% Success across all 4 jobs)  
**Session Objective:** Prepare a secure, reproducible staging deployment blueprint for QPE, and revalidate the release candidate following the security-hardening commits delivered in Session 96.  
**Overall Verdict:** **STAGING BLUEPRINT READY — DEPLOYMENT NOT EXECUTED**  
**Governance & Release Gate Status:** **ZERO TAGS CREATED, ZERO RELEASES PUBLISHED, ZERO DEPLOYMENTS EXECUTED**  

---

## 1. Executive Summary & Purpose

Session 97 acts as a comprehensive deployment architecture and release candidate reassessment phase for the **Quantitative Portfolio Optimization Engine (`QPE`) v1.0.0**.

Following the successful remediation of finding `OPS-95-02` in Session 96 (which eliminated default PostgreSQL credentials, added fail-closed database/JWT preflight validation, quoted Compose variable expansions, and added 39 regression tests), this session establishes:
1. **Release Candidate Revalidation:** A formal reassessment of the release target updating the proposed commit from `36909be` (Session 93 baseline) to `2f3843d` (hardened baseline), supported by verified 100% green CI evidence across all 4 automated workflow jobs.
2. **Staging Deployment Blueprint:** A concrete, reproducible staging deployment architecture defining network topology, external TLS reverse proxy requirements, forwarding headers, environment contracts, database migration/backup procedures, and container telemetry.
3. **Staging Smoke-Test Checklist:** A 13-point operational verification checklist with defined actions, expected results, evidence to collect, and failure procedures to guide an authorized operator upon provisioning a staging host.
4. **Unresolved Risk Register:** An updated operational risk classification categorizing remaining considerations into staging prerequisites, production prerequisites, and post-release improvements.

> [!IMPORTANT]
> **Strict Governance Boundary:** This session performs architectural planning, validation documentation, and test design only. No external infrastructure was provisioned, no staging environment was deployed, no Git tag was created, and no release was published.

---

## 2. Phase A — Repository Baseline Verification

The live Git repository state was inspected on `main`:

| Parameter | Observed Command Telemetry | Audit Status |
|---|---|:---:|
| **Working Tree & Branch** | `git status --short --branch` -> `## main...origin/main` | **PRISTINE & SYNCHRONIZED** |
| **Local HEAD SHA** | `git rev-parse HEAD` -> `2f3843d9e49d524e5db75da44e955cfc75737f59` | **VERIFIED** |
| **Remote origin/main SHA** | `git rev-parse origin/main` -> `2f3843d9e49d524e5db75da44e955cfc75737f59` | **VERIFIED** |
| **Formatting & Whitespace** | `git diff --check` -> *(0 errors, 0 warnings)* | **CLEAN** |
| **Local Git Tags** | `git tag -l` -> *(empty)* | **PRISTINE (0 Tags)** |
| **Remote Git Tags** | `git ls-remote --tags origin` -> *(empty)* | **PRISTINE (0 Tags)** |
| **GitHub Releases** | GitHub REST API `/repos/.../releases` -> `0` | **PRISTINE (0 Releases)** |
| **Latest Remote CI Run** | Run ID [`40128394775`](https://github.com/UzairAhmad88/Portfolio-Optimization-Engine-by-uzaii/actions/runs/40128394775) on `2f3843d` | **100% SUCCESS (4/4 jobs)** |

---

## 3. Phase B — Release Candidate Revalidation

### 3.1 Transition from Previous Proposal (`36909be`) to Hardened Target (`2f3843d`)

The release candidate proposed in Session 93 and Session 95 was commit `36909bea417384800fa9d1cf228894235a52b278`. That target predated the Session 96 security-hardening remediation.

The newly evaluated and verified proposed release candidate target is:
**`2f3843d9e49d524e5db75da44e955cfc75737f59`**

### 3.2 Audit of Inclusions in Target SHA

An audit of the commit range `36909be..2f3843d` confirms the target includes all security, packaging, and testing improvements:

1. **Elimination of Compose Insecure Password Fallback:**
   - In [`docker-compose.yml`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/docker-compose.yml#L8), `${POSTGRES_PASSWORD:-quant_password}` was replaced with `"${POSTGRES_PASSWORD:?ERROR: POSTGRES_PASSWORD must be explicitly provided in environment or .env file}"`.
   - In backend service definition, `DATABASE_URL` interpolation was wrapped in double quotes and enforces non-empty `POSTGRES_PASSWORD`.
2. **Fail-Closed Database Credential Preflight:**
   - In [`backend/app/db/session.py`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/app/db/session.py#L42-L103), `validate_database_configuration()` enforces mandatory `DATABASE_URL`, rejects SQLite in production, rejects missing/empty passwords, rejects 14 known insecure passwords, and enforces minimum 8-character length.
3. **Unified Startup Boundary Validation:**
   - In [`backend/app/auth/security.py`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/app/auth/security.py#L92-L102), `validate_production_configuration()` unites JWT secret validation and database credential checks.
   - In [`backend/app/main.py`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/app/main.py#L35-L42), the FastAPI `lifespan` handler calls `validate_production_configuration()` before database connection or accepting requests.
   - In [`backend/entrypoint.sh`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/entrypoint.sh#L10-L16), container preflight validates configuration before probing PostgreSQL or executing Alembic migrations.
4. **39 Dedicated Regression Tests:**
   - In [`backend/tests/test_production_configuration_hardening.py`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/backend/tests/test_production_configuration_hardening.py), all 39 tests pass locally and in CI.
5. **YAML Parser Quotation & Test Headroom:**
   - `docker-compose.yml` uses quoted `${...}` parameters to ensure strict YAML compliance.
   - `backend/tests/test_pdf_renderer.py` test timeout was aligned to 45.0s for CI cold-start stability.
6. **Metadata & Release Notes Synchronization:**
   - Version metadata remains strictly synchronized at `1.0.0` across all 8 manifest locations:
     - `backend/pyproject.toml` (`version = "1.0.0"`)
     - `backend/uv.lock` (`name = "backend", version = "1.0.0"`)
     - `frontend/package.json` (`"version": "1.0.0"`)
     - `frontend/package-lock.json` (`"version": "1.0.0"`)
     - `backend/app/main.py` (`FastAPI(version="1.0.0")`)
     - `backend/app/reports/pdf_templates.py` (`PLATFORM_VERSION = "1.0.0"`)
     - `README.md` (`Version 1.0.0`)
     - `docs/OPERATIONS_RUNBOOK.md` (`Version 1.0.0`)

### 3.3 GitHub Actions CI Evidence (Exact Target SHA)

Workflow run telemetry for target commit [`2f3843d`](https://github.com/UzairAhmad88/Portfolio-Optimization-Engine-by-uzaii/commit/2f3843d9e49d524e5db75da44e955cfc75737f59):
- **Workflow Run URL:** [`https://github.com/UzairAhmad88/Portfolio-Optimization-Engine-by-uzaii/actions/runs/40128394775`](https://github.com/UzairAhmad88/Portfolio-Optimization-Engine-by-uzaii/actions/runs/40128394775)
- **Run ID:** `40128394775`
- **Trigger:** Push to `main`
- **Overall Status:** **`100% SUCCESS (4/4 jobs passed)`**

| Job Name | Duration | Conclusion | Observed Output & Scope |
|---|:---:|:---:|---|
| **Frontend Build, Lint & Test (Node 24)** | 23s | `success` | Clean `npm ci`, 0 oxlint errors, 88 Vitest tests passed, Vite production build clean |
| **PostgreSQL Integration & Migration (PostgreSQL 16)** | 55s | `success` | Applied Alembic migrations to head (`e5f6a7b8c9d0`), 7 PostgreSQL tests passed |
| **Docker Compose Runtime Verification (Docker / PostgreSQL 16)** | 1m 51s | `success` | 3-tier container stack started, healthchecks 200, Alembic migrations verified, auth verified, Chromium PDF rendering verified, volume restart persistence verified |
| **Backend Test Suite (Python 3.11)** | 2m 11s | `success` | **702 passed tests**, 0 failures (including 39 production configuration hardening tests) |

---

## 4. Phase C — Staging Architecture & Deployment Contract

### 4.1 Topology & Network Architecture

```
                          INTERNET / ALLOCATORS
                                    │
                                    ▼ HTTPS (TCP 443)
                  ┌───────────────────────────────────┐
                  │    UPSTREAM REVERSE PROXY / ALB   │
                  │ (Cloudflare / AWS ALB / Edge Nginx│
                  │  - Terminates TLS with valid SSL  │
                  │  - Enforces HSTS & modern ciphers │
                  │  - Forwards X-Forwarded-Proto=https
                  └─────────────────┬─────────────────┘
                                    │ HTTP (TCP 80)
                                    ▼
       ┌─────────────────────────────────────────────────────────────┐
       │ HOST VIRTUAL MACHINE / STAGING SERVER                       │
       │                                                             │
       │   ┌───────────────────────────────────────────────────────┐ │
       │   │ FRONTEND CONTAINER (quant_portfolio_frontend)         │ │
       │   │ - Nginx 1.27 Alpine                                   │ │
       │   │ - Listens on 0.0.0.0:80 (or ${FRONTEND_PORT:-80})     │ │
       │   │ - Serves pre-built React 19 SPA static assets         │ │
       │   │ - Proxies /api/ to backend:8000                       │ │
       │   │ - Health check: GET /healthz                          │ │
       │   └───────────────────────┬───────────────────────────────┘ │
       │                           │ internal bridge (quant_network) │
       │                           ▼                                 │
       │   ┌───────────────────────────────────────────────────────┐ │
       │   │ BACKEND CONTAINER (quant_portfolio_backend)           │ │
       │   │ - Python 3.11-slim / FastAPI / Uvicorn                │ │
       │   │ - Listens on 8000 inside network                      │ │
       │   │ - Bound to loopback on host (127.0.0.1:8000:8000)     │ │
       │   │ - Non-root user (appuser, UID 10001)                  │ │
       │   │ - Tmpfs RAM disk (/app/tmp:size=256M) for PDF tasks   │ │
       │   │ - Concurrency semaphore N=2 for Chromium export       │ │
       │   │ - Preflight configuration validation at entrypoint    │ │
       │   │ - Health check: GET /api/v1/health                    │ │
       │   └───────────────────────┬───────────────────────────────┘ │
       │                           │ internal bridge (quant_network) │
       │                           ▼                                 │
       │   ┌───────────────────────────────────────────────────────┐ │
       │   │ DATABASE CONTAINER (quant_portfolio_postgres)         │ │
       │   │ - PostgreSQL 16 Alpine                                │ │
       │   │ - Listens on 5432 inside network                      │ │
       │   │ - Bound to loopback on host (127.0.0.1:5432:5432)     │ │
       │   │ - Named volume persistence (quant_pgdata)             │ │
       │   │ - Health check: pg_isready -U quant_user              │ │
       │   └───────────────────────────────────────────────────────┘ │
       └─────────────────────────────────────────────────────────────┘
```

### 4.2 Network & TLS Specification
- **External HTTPS Termination:** The upstream proxy must terminate TLS (Port 443) using TLS 1.2/1.3 and forward plaintext HTTP traffic to the staging host port 80.
- **Forwarding Headers:** Upstream proxy must inject:
  - `Host: <staging-domain>`
  - `X-Real-IP: <client-ip>`
  - `X-Forwarded-For: <client-ip>`
  - `X-Forwarded-Proto: https`
- **Loopback Port Isolation:**
  - Database port `5432` is bound strictly to `127.0.0.1:5432:5432` on the host, preventing public access.
  - Direct backend port `8000` is bound strictly to `127.0.0.1:8000:8000` on the host for local operator inspection.
  - Public ingress is restricted to port 80 on the frontend container.
- **DNS & CORS Configuration:**
  - DNS A/CNAME record points to the upstream proxy (e.g., `staging-qpe.internal.firm`).
  - Backend `CORS_ORIGINS` environment variable must be set to `https://staging-qpe.internal.firm`.
- **Health Endpoints:**
  - Nginx health probe: `GET /healthz` -> returns HTTP 200 `OK`.
  - Backend health probe: `GET /api/v1/health` -> returns HTTP 200 with database connection status:
    ```json
    {"status": "healthy", "database": "connected", "version": "1.0.0"}
    ```
  - PostgreSQL health probe: `pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}`.

---

### 4.3 Environment Variable Contract

Every variable consumed across services, its required format, sensitivity, and validation behavior:

| Variable | Consuming Service(s) | Default / Example Value | Sensitivity | Production Validation Rule |
|---|---|---|:---:|---|
| `POSTGRES_USER` | `postgres`, `backend` | `quant_user` | Low | Non-empty string. |
| `POSTGRES_PASSWORD` | `postgres`, `backend` | *(Must be supplied)* | **CRITICAL** | **Fail-Closed.** Compose halts if omitted. `app.db.session` fails closed if empty, $< 8$ chars, or in 14-entry blacklist. |
| `POSTGRES_DB` | `postgres`, `backend` | `quant_portfolio_db` | Low | Alphanumeric database name. |
| `APP_ENV` | `backend` | `production` | Low | Set to `production` in staging to enforce strict secret validation. |
| `DATABASE_URL` | `backend` | `postgresql+psycopg://...` | **HIGH** | **Fail-Closed.** Mandatory under `APP_ENV=production`. Must use PostgreSQL scheme; SQLite rejected. |
| `JWT_SECRET_KEY` | `backend` | *(Must be supplied)* | **CRITICAL** | **Fail-Closed.** Mandatory under `APP_ENV=production`. Minimum 32 chars (256-bit entropy); development placeholders rejected. |
| `CORS_ORIGINS` | `backend` | `https://staging.domain.com` | Medium | Comma-separated list of allowed origins. Wildcards (`*`) rejected. |
| `PDF_MAX_CONCURRENT_RENDERS` | `backend` | `2` | Low | Bounded integer semaphore permit count (recommended `2` for $\le 4\text{GB}$ RAM hosts). |
| `RUN_MIGRATIONS` | `backend` | `true` | Low | If `true`, `entrypoint.sh` runs `alembic upgrade head` before starting Uvicorn. |
| `FRONTEND_PORT` | `frontend` | `80` | Low | External host port mapped to container port 80. |
| `CHROME_BIN` | `backend` | `/usr/bin/chromium` | Low | Absolute path to Chromium binary in container. |
| `CHROMIUM_PATH` | `backend` | `/usr/bin/chromium` | Low | Fallback path to Chromium binary. |

### 4.4 Secret Generation & Injection Standard
- **Cryptographic Generation Commands:**
  ```bash
  # Generate 256-bit JWT secret (64-char hex):
  python -c "import secrets; print(secrets.token_hex(32))"

  # Generate 192-bit Database password (32-char urlsafe):
  python -c "import secrets; print(secrets.token_urlsafe(24))"
  ```
- **Injection Method:**
  - Place variables into `.env` on the staging host.
  - Set strict filesystem permissions: `chmod 600 .env` (readable strictly by the deployment user).
  - Confirm `.env` is listed in `.gitignore`.
  - **PROHIBITION:** Real credentials must never be committed to Git or embedded in Dockerfiles.
- **Rotation Protocols:**
  - *JWT Rotation:* Updating `JWT_SECRET_KEY` invalidates active tokens; users must re-authenticate. Requires `docker compose restart backend`.
  - *Database Password Rotation:* Execute `ALTER USER quant_user WITH PASSWORD '...';` in PostgreSQL, update `POSTGRES_PASSWORD` and `DATABASE_URL` in `.env`, and run `docker compose restart backend`.

---

### 4.5 Database Deployment & Lifecycle Contract

1. **Database Engine:** PostgreSQL 16 Alpine (`postgres:16-alpine`).
2. **Schema & Migration Order:**
   - Head revision: `e5f6a7b8c9d0`.
   - Executed automatically by `backend/entrypoint.sh` via `alembic upgrade head` after verifying database connection.
3. **Pre-Migration Backup Requirement:**
   - Before applying migrations or deploying new code, operators must take a snapshot backup:
     ```bash
     docker compose exec -T postgres pg_dump -U quant_user -Fc quant_portfolio_db > pre_deploy_backup_$(date +%Y%m%d_%H%M%S).dump
     ```
4. **Sandbox Restore Test:**
   - Verify backup integrity by testing restore into a temporary database:
     ```bash
     docker compose exec postgres createdb -U quant_user quant_portfolio_restore_test
     docker compose exec -T postgres pg_restore -U quant_user -d quant_portfolio_restore_test < backup.dump
     docker compose exec postgres dropdb -U quant_user quant_portfolio_restore_test
     ```
5. **Persistence & Ownership:**
   - Named Docker volume `quant_pgdata` mapped to `/var/lib/postgresql/data`.
   - Persists across container rebuilds, restarts, and removals (unless `docker compose down -v` is explicitly called).

---

### 4.6 Operations & Telemetry

1. **Dependency & Startup Sequence:**
   - `postgres` starts first. Healthcheck probes `pg_isready`.
   - `backend` starts only after `postgres` is `service_healthy`. Entrypoint validates secrets, probes DB, runs Alembic migrations, then starts Uvicorn.
   - `frontend` starts only after `backend` is `service_healthy`.
2. **Resource Allocation (Minimum Staging Host Sizing):**
   - **vCPU:** 2 vCPUs minimum (recommended 4 vCPUs).
   - **RAM:** 4 GB RAM minimum (recommended 8 GB RAM).
   - **Disk:** 40 GB SSD (for Docker images, build cache, and database volume).
3. **Rollback Procedure:**
   - If deployment fails, roll back to prior Git SHA:
     ```bash
     git checkout <previous-stable-sha>
     docker compose build
     docker compose up -d
     ```
   - If database schema requires rollback:
     ```bash
     docker compose exec backend alembic downgrade <previous-revision>
     # Or restore from pre-deployment pg_dump backup
     ```

---

## 5. Phase D — Staging Smoke-Test Checklist

The following 13-point operational test suite must be executed sequentially by an authorized operator once a staging environment is provisioned:

```
[ ] TEST 01: Preflight Secret & Environment Validation
[ ] TEST 02: Compose Configuration Syntax Validation
[ ] TEST 03: HTTPS Certificate & Edge Proxy Redirect Verification
[ ] TEST 04: Service Health & Readiness Probes
[ ] TEST 05: Authentication & Protected Route Access Control
[ ] TEST 06: Database Migration & Schema Integrity
[ ] TEST 07: Small Portfolio Calculation & Optimization
[ ] TEST 08: Chronological Out-of-Sample Backtest Smoke Test
[ ] TEST 09: Multi-Page Headless Chromium PDF Export & Verification
[ ] TEST 10: Input Validation & Error Sanitization (Zero Traceback Leakage)
[ ] TEST 11: Database Backup Creation & Sandbox Restore Drill
[ ] TEST 12: Container Logs & Process Resource Inspection
[ ] TEST 13: Controlled Container Restart & State Persistence Drill
```

### Detailed Test Specifications

#### Test 01: Preflight Secret & Environment Validation
- **Action:** Execute the offline configuration validator on the staging host:
  ```bash
  docker compose run --rm --no-deps backend python -c "from app.auth.security import validate_production_configuration; validate_production_configuration(); print('Preflight OK')"
  ```
- **Expected Result:** Exits with code 0 and prints `Preflight OK`.
- **Evidence:** Terminal output showing zero runtime errors.
- **Failure Response:** Check `.env` for missing `JWT_SECRET_KEY`, weak passwords ($< 8$ chars), or placeholder strings.

#### Test 02: Compose Configuration Syntax Validation
- **Action:** Validate Compose interpolation and YAML syntax:
  ```bash
  docker compose config --quiet
  ```
- **Expected Result:** Exits with code 0 without outputting warnings or syntax errors.
- **Evidence:** Zero output, exit code 0.
- **Failure Response:** Check for unquoted `${...}` variables or missing environment variables.

#### Test 03: HTTPS Certificate & Edge Proxy Redirect Verification
- **Action:** Probe staging domain over HTTP and HTTPS:
  ```bash
  curl -I http://staging-qpe.internal.firm
  curl -I https://staging-qpe.internal.firm
  ```
- **Expected Result:** HTTP request returns `301/308 Moved Permanently` redirecting to `https://`. HTTPS request returns HTTP 200 with valid TLS certificate and defensive headers (`X-Content-Type-Options`, `X-Frame-Options`).
- **Evidence:** Output of response headers showing SSL issuer and HTTP 200.
- **Failure Response:** Verify edge reverse proxy TLS certificate renewal and port 80 forwarding rule.

#### Test 04: Service Health & Readiness Probes
- **Action:** Request public and backend health endpoints:
  ```bash
  curl -fsS https://staging-qpe.internal.firm/healthz
  curl -fsS https://staging-qpe.internal.firm/api/v1/health
  ```
- **Expected Result:** `/healthz` returns `OK`. `/api/v1/health` returns:
  ```json
  {"status": "healthy", "database": "connected", "version": "1.0.0"}
  ```
- **Evidence:** JSON payload confirming `"database": "connected"`.
- **Failure Response:** Check backend logs (`docker compose logs backend`) for database connectivity issues.

#### Test 05: Authentication & Protected Route Access Control
- **Action:** Request protected route without token, register test user, and log in:
  ```bash
  # 1. Unauthenticated request should fail with 401
  curl -s -o /dev/null -w "%{http_code}" https://staging-qpe.internal.firm/api/v1/auth/me
  # 2. Register test researcher
  curl -s -X POST https://staging-qpe.internal.firm/api/v1/auth/register \
    -H "Content-Type: application/json" \
    -d '{"email": "stage_test@quant.local", "password": "StagePassword123!", "full_name": "Stage Tester"}'
  # 3. Log in and retrieve JWT access token
  curl -s -X POST https://staging-qpe.internal.firm/api/v1/auth/login \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=stage_test@quant.local&password=StagePassword123!"
  ```
- **Expected Result:** Step 1 returns `401`. Step 2 returns `201 Created`. Step 3 returns `200 OK` with JSON containing `access_token` and `token_type: "bearer"`.
- **Evidence:** HTTP status codes and issued token payload.
- **Failure Response:** Inspect user table in database and bcrypt hashing logs.

#### Test 06: Database Migration & Schema Integrity
- **Action:** Check current Alembic revision inside backend container:
  ```bash
  docker compose exec backend alembic current
  ```
- **Expected Result:** Outputs current revision matching `e5f6a7b8c9d0 (head)`.
- **Evidence:** Terminal output showing migration head.
- **Failure Response:** Run `docker compose exec backend alembic upgrade head` and review migration errors.

#### Test 07: Small Portfolio Calculation & Optimization
- **Action:** Execute mean-variance optimization request via authenticated REST API:
  ```bash
  curl -s -X POST https://staging-qpe.internal.firm/api/v1/portfolio/optimize \
    -H "Authorization: Bearer <TOKEN>" \
    -H "Content-Type: application/json" \
    -d '{"expected_returns": [0.12, 0.08, 0.05], "cov_matrix": [[0.04, 0.01, 0.005], [0.01, 0.025, 0.002], [0.005, 0.002, 0.01]], "target_return": 0.08, "asset_names": ["EQUITY", "BOND", "COMMODITY"]}'
  ```
- **Expected Result:** Returns HTTP 200 with optimal allocation weights summing to $1.0 \pm 10^{-6}$ and solver status `"optimal"`.
- **Evidence:** JSON response containing weights array and risk/return metrics.
- **Failure Response:** Check SLSQP solver output in backend logs.

#### Test 08: Chronological Out-of-Sample Backtest Smoke Test
- **Action:** Upload a small synthetic price dataset and run walk-forward backtest.
- **Expected Result:** Backtest executes chronologically without look-ahead bias; returns cumulative return series, Sharpe ratio, drawdown profile, and turnover metrics.
- **Evidence:** Backtest run record with UUID and non-empty equity curve series.
- **Failure Response:** Verify dataset validation errors in `POST /api/v1/datasets/upload`.

#### Test 09: Multi-Page Headless Chromium PDF Export & Verification
- **Action:** Request a compiled PDF report generation:
  ```bash
  curl -s -X POST https://staging-qpe.internal.firm/api/v1/reporting/export/dossier/unified \
    -H "Authorization: Bearer <TOKEN>" \
    -H "Content-Type: application/json" \
    -d '{"backtest_id": "<BACKTEST_UUID>", "title": "Staging Fact Sheet", "include_annex": true}' \
    --output staging_test_dossier.pdf
  ```
- **Expected Result:** Returns binary PDF stream beginning with `%PDF-`, size $> 10\text{KB}$, with exactly 3 pages (Tear Sheet + Research Annex).
- **Evidence:** `pypdf` page count verification or PDF header inspection (`head -c 5 staging_test_dossier.pdf`).
- **Failure Response:** Check Chromium logs in backend container and tmpfs permissions (`/app/tmp`).

#### Test 10: Input Validation & Error Sanitization (Zero Traceback Leakage)
- **Action:** Send malformed JSON and out-of-range numerical parameters:
  ```bash
  curl -s -X POST https://staging-qpe.internal.firm/api/v1/portfolio/optimize \
    -H "Authorization: Bearer <TOKEN>" \
    -H "Content-Type: application/json" \
    -d '{"expected_returns": "invalid_type"}'
  ```
- **Expected Result:** Returns HTTP 422 Unprocessable Content. Unhandled server errors return HTTP 500 with generic JSON `{"detail": "An unexpected internal server error occurred."}` without Python stack trace.
- **Evidence:** HTTP 422/500 JSON response confirming no stack trace or internal path leakage.
- **Failure Response:** Verify FastAPI exception handler in `backend/app/main.py`.

#### Test 11: Database Backup Creation & Sandbox Restore Drill
- **Action:** Run a live backup and restore drill:
  ```bash
  docker compose exec -T postgres pg_dump -U quant_user -Fc quant_portfolio_db > /tmp/staging_test.dump
  docker compose exec postgres createdb -U quant_user quant_restore_drill
  docker compose exec -T postgres pg_restore -U quant_user -d quant_restore_drill < /tmp/staging_test.dump
  docker compose exec postgres dropdb -U quant_user quant_restore_drill
  rm /tmp/staging_test.dump
  ```
- **Expected Result:** `pg_dump` and `pg_restore` execute with exit code 0.
- **Evidence:** Output of restore command showing zero fatal errors.
- **Failure Response:** Check PostgreSQL container disk space and user permissions.

#### Test 12: Container Logs & Process Resource Inspection
- **Action:** Inspect container stdout/stderr logs and resource usage:
  ```bash
  docker compose logs --tail=50
  docker stats --no-stream
  ```
- **Expected Result:** Logs contain zero Python tracebacks, zero fatal database errors, and resource consumption is within expected boundaries (backend memory $< 500\text{MB}$ at idle).
- **Evidence:** Captured stdout from `docker stats`.
- **Failure Response:** Investigate any container restarting or consuming $> 90\%$ CPU.

#### Test 13: Controlled Container Restart & State Persistence Drill
- **Action:** Restart database and backend containers, then verify data persistence:
  ```bash
  docker compose restart postgres backend
  curl -fsS https://staging-qpe.internal.firm/api/v1/health
  # Verify previously registered test user can still log in
  curl -s -X POST https://staging-qpe.internal.firm/api/v1/auth/login \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=stage_test@quant.local&password=StagePassword123!"
  ```
- **Expected Result:** Services restart smoothly, healthcheck returns HTTP 200, and user credentials persist.
- **Evidence:** Successful login returning HTTP 200 after container restart.
- **Failure Response:** Check named volume `quant_pgdata` mapping in `docker-compose.yml`.

---

## 6. Phase E — Unresolved Operational Risk Review

Reassessment of the operational risks identified in Session 95 following Session 96 hardening:

| Finding ID | Description | Classification | Justification & Action Plan |
|---|---|:---:|---|
| **`OPS-95-01`** | Upstream Reverse Proxy TLS Termination | **Staging Prerequisite & Production Prerequisite** | In-container Nginx binds port 80. Cleartext HTTP exposure across the public internet leaks credentials. Upstream reverse proxy terminating TLS (Port 443) is mandatory before external staging access. *Not a release blocker* because QPE is containerized software intended to run behind an edge proxy. |
| **`OPS-95-02`** | Default PostgreSQL Password Fallback | **RESOLVED** | Remediated in Session 96 (`docker-compose.yml`, `backend/app/db/session.py`, `backend/entrypoint.sh`). Verified in CI. |
| **`OPS-95-03`** | Automated PostgreSQL Backup Daemon | **Staging Prerequisite (Drill) & Production Prerequisite (Automation)** | Manual backup commands (`pg_dump -Fc`) are documented. A pre-migration backup drill is required for staging. An automated daily snapshot or cron daemon is required before accepting production capital/research. |
| **`OPS-95-05`** | Container Cgroup Resource Limits | **Staging Prerequisite (Recommended) & Production Prerequisite (Mandatory)** | Unbounded containers risk host memory exhaustion during concurrent Chromium PDF renders or large Monte Carlo simulations. Bounded semaphore ($N=2$) and tmpfs (256MB) mitigate risk in-container; cgroup limits (`mem_limit: 2g`, `cpus: 2.0`) should be applied via a Compose production overlay. |
| **`OPS-95-04`** | Ingress Rate Limiting | **Production Prerequisite** | In-memory login rate limiter (`LoginRateLimiter`) protects authentication. Broad API ingress rate limiting should be enforced at the edge proxy (ALB / Cloudflare WAF) for production. |
| **`OPS-95-06`** | Multi-Instance Rate Limiter Consistency | **Post-Release Improvement** | Single-container deployments use in-memory rate limiting. Scaling to $K > 1$ backend instances horizontally requires a shared Redis cluster for rate limiting. Not required for single-container staging or v1.0.0. |
| **`OBS-34-D-01`** | Chromium Sandbox Flag (`--no-sandbox`) | **Post-Release Improvement / Accepted Boundary** | Documented operational limitation. Non-root user execution (UID 10001), container isolation, and HTML entity escaping provide sufficient defense-in-depth. Decoupling into an isolated microservice is a candidate for v1.1+. |
| **`OPS-95-07`** | Centralized Logging & Metric Alerting | **Production Prerequisite** | Health endpoints (`/healthz`, `/api/v1/health`) provide telemetry. Centralized log forwarding (Grafana Loki, Datadog, AWS CloudWatch) and uptime alerting are mandatory for production hosting. |

---

## 7. Phase F — Verification & Documentation Synchronizations

1. [`docs/SESSION_97_STAGING_DEPLOYMENT_BLUEPRINT.md`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/docs/SESSION_97_STAGING_DEPLOYMENT_BLUEPRINT.md): Authored this blueprint.
2. [`docs/MASTER_PLAN.md`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/docs/MASTER_PLAN.md): Updated to record Session 97 scope, target SHA revalidation, staging architecture, and smoke-test readiness.
3. [`docs/RELEASE_NOTES_v1.0.0.md`](file:///d:/Quants/Projects/quant-portfolio-engine-starter/docs/RELEASE_NOTES_v1.0.0.md): Reviewed and confirmed accurate. Staging and production deployments are strictly documented as pending external host provisioning.
4. **Clean Worktree & Diff Check:** `git diff --check` confirmed clean with zero whitespace or line-ending errors.

---

## 8. Final Report & Mandatory Governance Statement

| Requirement | Audit Finding / Verdict | Evidence & Details |
|---|---|---|
| **Current Baseline SHA** | `2f3843d9e49d524e5db75da44e955cfc75737f59` | Clean `main` branch synchronized with `origin/main` |
| **Proposed Release Target SHA** | `2f3843d9e49d524e5db75da44e955cfc75737f59` | Revalidated candidate incorporating Session 96 security hardening |
| **Exact-Target Remote CI Status** | **100% SUCCESS** | Run ID [`40128394775`](https://github.com/UzairAhmad88/Portfolio-Optimization-Engine-by-uzaii/actions/runs/40128394775) on `2f3843d` (4/4 jobs green) |
| **Staging Prerequisites Defined** | **COMPLETE** | Edge TLS proxy, DNS, CORS, and backup drill procedures documented |
| **Smoke-Test Readiness** | **COMPLETE** | 13-point actionable test suite defined with actions, expected results, and responses |
| **Session 96 Hardening Included** | **YES** | Target includes fail-closed DB/JWT validation, Compose quoting, and 39 tests |
| **Release Tag Created** | **NO** | Zero Git tags exist (`git tag -l` is empty; `git ls-remote --tags` is empty) |
| **GitHub Release Published** | **NO** | Zero releases published on GitHub REST API (`releases: 0`) |
| **Staging/Production Deployment Done** | **NO** | No external infrastructure provisioned; preparation and blueprinting only |
| **Recommended Next Step** | **OWNER DECISION GATE** | Await Project Owner directive to provision staging host or authorize release |

### Overall Verdict:
### **`STAGING BLUEPRINT READY — DEPLOYMENT NOT EXECUTED`**
