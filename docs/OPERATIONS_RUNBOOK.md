# Quantitative Portfolio Optimization Engine — Operations Runbook

- **Document Version:** `v1.0.0`
- **Governing Stage:** Release Packaging, CI & Operational Readiness (Sessions 82–84)
- **Target Environments:** Local Workstation (Windows / Linux / macOS) & Self-Hosted Docker Compose
- **Classification:** Operational Governance & Administration Manual

---

## 1. Document Overview & Operating Standard

This runbook provides actionable, step-by-step procedures for administering, deploying, configuring, troubleshooting, and maintaining the Quantitative Portfolio Optimization Engine (`QPE`).

### Operating Principles
1. **Accuracy Over Assumption:** Instructions in this runbook are concrete procedures. They do not constitute proof of runtime verification where execution was precluded by host environment constraints.
2. **Explicit Trust Boundaries:** Local development and testing use safe defaults; production environments enforce strict fail-closed security and mandatory explicit configuration.
3. **Data Safety First:** Never execute destructive schema migrations, container volume prunes, or database restores without verifying the target database URL and creating a point-in-time snapshot.

---

## Section A: Prerequisites and Environment Setup

### 1. Host Runtime Requirements

| Dependency | Minimum Version | Recommended Version | Scope of Usage |
|---|---|---|---|
| **Python** | 3.11.0 | 3.11.9+ | Backend API, quant calculation engines, and migrations |
| **Node.js** | 20.0.0 LTS | 20.18.0+ | Frontend build, dev server, Vitest, and linter |
| **npm** | 10.0.0 | 10.8.0+ | Frontend package and lockfile management |
| **Docker Engine** | 20.10.0 | 26.0.0+ | Multi-container self-hosted deployment (*optional for local dev*) |
| **Docker Compose** | 2.0.0 | 2.27.0+ | Service orchestration plugin (`docker compose`) |
| **PostgreSQL** | 16.0 | 16.3+ | Relational persistence (*optional; SQLite fallback available*) |
| **Google Chrome / Chromium** | 120.0 | 126.0+ | Headless server-side PDF report rasterization |

### 2. Configuration Files & Environment Separation

The application enforces strict separation across three operational modes:

| Mode (`APP_ENV`) | Database Strategy | JWT Secret Handling | CORS & Cookies | Startup Behavior |
|---|---|---|---|---|
| **`development`** | SQLite (`quant_portfolio.db`) or local PostgreSQL | Falls back to internal dev key if unset | Permissive local origins (`localhost:5173`) | Normal startup |
| **`test`** | Isolated SQLite in-memory / tempfile, or `quant_test_db` | Uses test key | Local origins | Skips external calls |
| **`production`** | PostgreSQL mandatory (`DATABASE_URL`) | **Strictly required** ($\ge 32$ chars); fails closed if invalid | Strict origins, HTTPS cookie secure flag | Fails closed on insecure config |

### 3. Initial Configuration Setup

1. Copy the root environment template:
   ```bash
   cp .env.example .env
   ```
2. Verify critical settings in `.env`:
   - `APP_ENV`: Set to `development` for local work, or `production` for server deployment.
   - `DATABASE_URL`: Configure PostgreSQL or leave commented for SQLite file fallback.
   - `JWT_SECRET_KEY`: Set to a unique, random 256-bit string (see [Section D](#section-d-production-secret-management)).
   - `CORS_ORIGINS`: Restrict to explicit fully-qualified domain names.
   - `CHROME_BIN`: Verify path to system Chromium/Chrome executable.

---

## Section B: Local Development Workflow

### 1. Backend Service Setup (Python 3.11)

```powershell
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Activate virtual environment (Linux/macOS)
# source .venv/bin/activate

# Upgrade package manager and install dependencies in editable mode
python -m pip install --upgrade pip
pip install -e ".[dev]"

# Launch FastAPI development server with auto-reload
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- **Interactive API Documentation:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **API Health Check:** [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)

### 2. Frontend Research Workspace Setup (Node 20)

```bash
# Navigate to frontend directory
cd frontend

# Install clean dependencies using package-lock.json
npm ci

# Start Vite development server
npm run dev
```

- **Frontend Application URL:** [http://localhost:5173](http://localhost:5173)

### 3. Local Test & Build Verification

Always execute test suites before submitting changes:

```powershell
# Backend test suite (from backend/ directory)
pytest -q

# Frontend unit and component tests (from frontend/ directory)
npm test

# Frontend TypeScript typecheck and production build
npm run build

# Frontend linter
npm run lint
```

### 4. Common Local Troubleshooting

| Symptom | Probable Cause | Remediation |
|---|---|---|
| `ModuleNotFoundError: No module named 'app'` | `PYTHONPATH` not set or package not installed in editable mode | Run `pip install -e ".[dev]"` from `backend/` or set `$env:PYTHONPATH="."` |
| `database is locked` (SQLite) | Multiple concurrent write transactions during test execution | Ensure tests use scoped sessions or switch `DATABASE_URL` to PostgreSQL |
| `ChromiumNotFoundException` during PDF export | `CHROME_BIN` unset or points to invalid path | Set `CHROME_BIN` in `.env` to your local Chrome/Chromium executable path |
| Frontend `Port 5173 already in use` | Orphaned Node/Vite process running | Terminate existing process or run `npm run dev -- --port 5174` |

---

## Section C: Docker Deployment

> [!WARNING]
> **Host Verification Limitation Disclosure (Session 82):**  
> On Windows workstations lacking Docker Engine, container image building, live compose startup, and in-container Chromium rasterization have not been directly executed. The procedures below represent verified configuration contracts that must be executed on an authorized Docker-enabled host.

### 1. Architecture Overview

The multi-container stack runs three coordinated services on an isolated bridge network (`quant_portfolio_network`):

```
       [ Client Browser / HTTP Allocator ]
                        │
                        ▼ (Port 80 / FRONTEND_PORT)
             ┌─────────────────────┐
             │   quant_frontend    │ (Nginx 1.27 Alpine)
             │  • Serves SPA bundle│
             │  • Proxies /api/ ───┼──────────┐
             └─────────────────────┘          │
                                              ▼ (Port 8000 Internal)
                                     ┌─────────────────────┐
                                     │   quant_backend     │ (Python 3.11 Slim)
                                     │  • FastAPI REST API │
                                     │  • Headless Chromium│
                                     │  • Alembic Engine   │
                                     └──────────┬──────────┘
                                                │
                                                ▼ (Port 5432 Internal)
                                     ┌─────────────────────┐
                                     │   quant_postgres    │ (PostgreSQL 16 Alpine)
                                     │  • Named Volume:    │
                                     │    quant_pgdata     │
                                     └─────────────────────┘
```

### 2. Deployment Commands

```bash
# 1. Validate Docker Compose syntax and variable substitution
docker compose config

# 2. Build images and start container services in background
docker compose up -d --build

# 3. Check service health status
docker compose ps

# 4. Stream service logs
docker compose logs -f

# 5. Inspect backend application logs specifically
docker compose logs -f backend

# 6. Stop container stack preserving database volume
docker compose down

# CAUTION: The following permanently purges database storage:
# docker compose down -v
```

### 3. Container Resource Limits & Permissions

- **User Namespace:** Backend container executes under unprivileged user `appuser` (`uid 10001:10001`).
- **Privilege Hardening:** All application services define `security_opt: [no-new-privileges:true]`.
- **Ephemeral Scratch:** PDF rendering scratch directory `/app/tmp` is mounted as an in-memory `tmpfs` volume (`size=256M,mode=1777`), preventing disk wear and leakages.
- **Port Isolation:** PostgreSQL (`5432`) and Backend (`8000`) port mappings are bound strictly to `127.0.0.1` on the host, preventing external access.

---

## Section D: Production Secret Management

### 1. Production JWT Security Rules (Session 83 Hardening)

When `APP_ENV=production` or `ENVIRONMENT=production`, the application lifespan handler invokes `validate_jwt_configuration()`. The system **fails closed immediately at startup** under any of the following conditions:

1. `JWT_SECRET_KEY` is empty, unset, or whitespace-only.
2. `JWT_SECRET_KEY` is shorter than **32 characters** (256-bit cryptographic entropy).
3. `JWT_SECRET_KEY` matches any known development default or placeholder string (e.g., `quant_engine_dev_secret_key_...`, `change_me_...`, `password`, `changeme`).

### 2. Generating a Cryptographically Secure Key

Execute the following Python one-liner to generate a compliant 256-bit hexadecimal secret:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Example compliant output format:
`8f7c9e1d2b3a4c5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e`

### 3. Safe Injection into Production Environment

- **Docker Compose:** Place `JWT_SECRET_KEY=<your_generated_key>` in the root `.env` file (ensure `.env` is listed in `.gitignore`).
- **Systemd / Container Orchestrators:** Supply via system environment or secret management vaults (e.g., AWS Secrets Manager, HashiCorp Vault, Kubernetes Secrets).
- **Prohibited Practice:** Never commit secrets to git, hardcode them in YAML files, or pass them on command lines visible in process tables (`ps aux`).

### 4. Secret Rotation & Operational Impact

- **Rotation Effect:** Changing `JWT_SECRET_KEY` immediately invalidates all existing user access tokens. Active users will receive HTTP 401 Unauthorized and must re-authenticate.
- **Planned Rotation Procedure:**
  1. Notify active research operators of the maintenance window.
  2. Generate a new 256-bit secret.
  3. Update `.env` or vault configuration.
  4. Perform rolling restart: `docker compose restart backend`.
  5. Verify health: `curl -I http://127.0.0.1:8000/api/v1/health`.

---

## Section E: Database Operations & Migrations

### 1. Database Identification & Target Safeguards

Before running any migration, backup, or maintenance command, identify the target database:

```bash
# Check current configured DATABASE_URL (without exposing credentials)
python -c "import os; from urllib.parse import urlparse; u = urlparse(os.environ.get('DATABASE_URL', 'sqlite:///./quant_portfolio.db')); print(f'Scheme: {u.scheme}, Host: {u.hostname}, DB: {u.path}')"
```

- **Test Database:** Scheme is `sqlite` (in-memory/temp) or DB name contains `test` (e.g., `quant_test_db`). Safe to wipe.
- **Developer Database:** Local file `quant_portfolio.db` or local PostgreSQL `quant_portfolio_db`. Contains active research datasets.
- **Production Database:** Dedicated host/cluster. Destructive actions strictly prohibited.

### 2. Alembic Migration Lifecycle

The migration chain is managed strictly via Alembic. Current migration head: `e5f6a7b8c9d0`.

```bash
# From backend directory (with .venv active):

# Check current database migration version
alembic current

# Check revision history
alembic history --verbose

# Upgrade database to latest schema revision
alembic upgrade head

# Downgrade by one revision (if reversible migration)
alembic downgrade -1
```

Inside Docker:
```bash
docker compose exec backend alembic current
docker compose exec backend alembic upgrade head
```

> [!IMPORTANT]
> **Schema Initialization Governance (DEF-82-01 Fix):**  
> `app.db.session.init_db()` is invoked only within the FastAPI application startup lifespan. Module-level table creation is strictly forbidden to prevent DDL collisions with Alembic migrations.

### 3. Backup and Disaster Recovery Procedures

#### PostgreSQL Snapshot Backup
```bash
# Create timestamped SQL backup from Docker container
docker compose exec -T postgres pg_dump -U quant_user quant_portfolio_db > "backup_qpe_$(date +%Y%m%d_%H%M%S).sql"

# Host-level backup (if running standalone PostgreSQL)
pg_dump -U quant_user -h localhost -d quant_portfolio_db -F c -b -v -f "backup_qpe_$(date +%Y%m%d_%H%M%S).dump"
```

#### PostgreSQL Database Restore
> [!CAUTION]
> Restoring a database replaces existing tables. Ensure all application services are stopped before restoring.

```bash
# 1. Stop backend service to terminate active database connections
docker compose stop backend

# 2. Restore database from SQL snapshot
docker compose exec -T postgres psql -U quant_user -d quant_portfolio_db < backup_qpe_YYYYMMDD_HHMMSS.sql

# 3. Verify migration revision
docker compose run --rm backend alembic current

# 4. Restart backend service
docker compose start backend
```

---

## Section F: PDF Reporting & Server-Side Chromium

### 1. Architecture & Rendering Mechanics

Server-side reporting generates PDF documents via headless Chromium (`backend/app/reports/renderer.py`):
- Pure presentation templates render semantic HTML + CSS Paged Media (`@page`, `@media print`).
- Chromium is executed via subprocess with `--headless`, `--disable-gpu`, and `--no-sandbox`.
- Temporary rendering artifacts are written to ephemeral scratch storage (`/app/tmp` in Docker) and wiped upon completion.
- Render execution timeout: Hard limit of **25 seconds** per PDF generation request.

### 2. Document Types & Pagination Specifications

| Report Type | REST Endpoint | Expected Page Count | Verification Standard |
|---|---|---|---|
| **Strategy Fact Sheet** | `/api/v1/reports/fact-sheet/{id}/export` | Exactly 1 Page | Compact allocator overview, KPI grid, wealth curve |
| **Institutional Tear Sheet** | `/api/v1/reports/tear-sheet/{id}/export` | Exactly 2 Pages | Comprehensive performance, attribution, and risk tear sheet |
| **Research Diagnostics Annex** | `/api/v1/reports/research-annex/{id}/export` | Exactly 1 Page | Stage 33 PBO, DSR, MinBTL, and CSCV distributions |
| **Unified Institutional Dossier**| `/api/v1/reports/unified/{id}/export` | 2 or 3 Pages | Combined dossier (Fact Sheet + Tear Sheet + optional Annex) |

### 3. Disclosed Operational Boundaries

- **`OBS-34-D-01` (`--no-sandbox`):** Headless Chromium requires `--no-sandbox` inside standard Linux containers because non-privileged containers disable unprivileged user namespaces. Mitigated by executing as non-root `appuser` (`uid 10001`) with `no-new-privileges:true`.
- **`OBS-34-D-02` (Concurrency Semaphore):** Concurrent PDF rendering is bounded to `PDF_MAX_CONCURRENT_RENDERS=2` per container to prevent memory exhaustion from parallel Chromium browser instances.

### 4. Chromium Diagnostics

```bash
# Check Chromium executable inside backend container
docker compose exec backend which chromium
# Expected: /usr/bin/chromium

# Check Chromium version and verify basic execution
docker compose exec backend /usr/bin/chromium --version --no-sandbox

# Test PDF generation endpoint using curl
TOKEN="<your_jwt_token>"
curl -s -X GET "http://localhost:8000/api/v1/reports/fact-sheet/<BACKTEST_ID>/export" \
  -H "Authorization: Bearer $TOKEN" \
  --output test_report.pdf

# Verify PDF header magic bytes (%PDF-)
head -c 5 test_report.pdf
```

---

## Section G: GitHub Actions CI Troubleshooting

### 1. Workflow Architecture (`.github/workflows/ci.yml`)

The CI workflow triggers on pushes to `main` and pull requests targeting `main`. It contains three independent jobs:

```
                  ┌─────────────────────────────────────────┐
                  │          GitHub Actions Workflow        │
                  └────────────────────┬────────────────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        ▼                              ▼                              ▼
┌──────────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐
│    backend-tests     │    │ postgres-integration │    │frontend-build-and-test│
│ • Python 3.11        │    │ • PostgreSQL 16      │    │ • Node.js 20         │
│ • Full pytest suite  │    │   Service Container  │    │ • npm ci             │
│ • SQLite in-memory   │    │ • alembic upgrade    │    │ • oxlint             │
│ • 663+ tests         │    │ • Postgres tests     │    │ • vitest (88 tests)  │
└──────────────────────┘    └──────────────────────┘    │ • vite build (prod)  │
                                                        └──────────────────────┘
```

### 2. Understanding Verification Distinctions

- **Locally Passing:** Tests executed on the developer workstation (e.g., SQLite suite, frontend tests).
- **Service Container Tests:** PostgreSQL integration tests require a running PostgreSQL instance; they skip cleanly locally if PostgreSQL is unavailable and execute inside the GitHub Actions `postgres:16-alpine` service container.
- **Workflow Passing:** Confirmed only when GitHub Actions has executed all three jobs and reported green status on the commit.

### 3. Diagnosing CI Job Failures

1. **`postgres-integration` Health Check Timeout:**
   - If PostgreSQL service fails to start, verify service container options: `--health-cmd pg_isready --health-interval 5s`.
2. **`alembic upgrade head` Failure:**
   - Verify that migration revisions form an unbroken chain from `8993dbd79e8a` through `e5f6a7b8c9d0`.
3. **`frontend-build-and-test` Type Errors:**
   - Run `npx tsc -b` locally in `frontend/` to pinpoint compiler issues before pushing.

---

## Section H: Known Operational Risks & Recovery

| Risk Item | Current Verified Status | Operational Impact | Standard Operating Response |
|---|---|---|---|
| **Docker Runtime Verification** | **Pending on local host** (Conditional Pass) | Live container startup, volume survivability, and Nginx reverse proxy unverified on host without Docker Engine | Execute `docker compose up -d --build` and health check on an authorized Docker-enabled staging host |
| **PostgreSQL Integration Verification** | **Workflow Defined, Remote Run Pending** | Host development relies on SQLite; PostgreSQL path verified via CI workflow configuration | Inspect GitHub Actions `postgres-integration` job logs or execute against local PostgreSQL instance |
| **Production JWT Secret** | **Hardened (Session 83)** | Application will fail closed at startup if `JWT_SECRET_KEY` is missing or $< 32$ chars | Generate 256-bit key via `secrets.token_hex(32)` and supply via `.env` before starting production |
| **Chromium `--no-sandbox`** | **Disclosed Architectural Tradeoff** | Renderer executes without Chrome sandbox inside container | Ensure backend runs as non-root `appuser` (uid 10001) with `no-new-privileges:true` |
| **Render Concurrency Limit** | **Configured (`PDF_MAX_CONCURRENT_RENDERS=2`)** | Rapid parallel export requests may queue or return HTTP 503 | For high-volume export workloads, scale backend container instances horizontally behind a load balancer |
| **Database Storage Persistence** | **Managed via Named Volume** | Executing `docker compose down -v` purges database | Train operators to use `docker compose down` (without `-v`) and maintain regular `pg_dump` backups |
