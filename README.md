# Quantitative Portfolio Optimization Engine (QPE)

- **Version:** `0.7.0`
- **License:** Proprietary / Research License
- **Architecture:** API-First Modular Monolith (FastAPI + React 19 / TypeScript + PostgreSQL / SQLite)
- **CI Status:** GitHub Actions Workflow Configured (`.github/workflows/ci.yml`) — *Remote verification pending*

---

## 1. Project Purpose & Core Capabilities

The **Quantitative Portfolio Optimization Engine (`QPE`)** is an API-first quantitative finance and portfolio research platform. It provides institutional researchers and portfolio managers with mathematically rigorous tools for data ingestion, point-in-time corporate action adjustments, portfolio optimization under explicit linear and quadratic constraints, out-of-sample walk-forward backtesting with realistic market friction, multiple-testing overfitting diagnostics, and publication-grade server-side PDF reporting.

### Key Capabilities
- **Market Data Engine & Trading Calendars:** Ingestion and validation for US and PSX equities; trading calendars (`USCalendar`, `PSXCalendar`) with statutory exchange holidays and gazetted Islamic lunar holiday tables; missing session anomaly detection.
- **Point-in-Time Data Integrity & Corporate Actions:** Backward split ($1/k$) and cash dividend ($1 - D_t/P_{t-1}$) adjustment factors; strict temporal anti-leakage cutoffs; mathematical separation between price returns and dividend-inclusive total returns.
- **Immutable Research Snapshots:** Merkle-inspired hierarchical SHA-256 manifest digests (manifest schema 1.2 with 8-decimal precision and currency binding); frozen observation payloads with zero price drift under operational database mutations.
- **Portfolio Optimization Suite:** SLSQP constrained mean-variance (Markowitz), minimum variance, maximum Sharpe, robust optimization with box and ellipsoidal return uncertainty, Ledoit-Wolf covariance shrinkage, Bayesian Black-Litterman view blending, Equal Risk Contribution (ERC) with convex log-barrier solver, and Hierarchical Risk Parity (HRP).
- **Out-of-Sample Walk-Forward Backtesting:** Expanding-window historical simulations modeling discrete simple returns, multiplicative compounding, weight drift, multi-frequency rebalancing (`daily`, `weekly`, `monthly`, `quarterly`), basis-point transaction costs, and execution slippage.
- **Attribution & Tail Risk Analytics:** Menchero (2000) multi-period logarithmic linking for exact additive asset contribution; tracking error, Beta, Jensen's Alpha; parametric and empirical Value-at-Risk (VaR) and Expected Shortfall (CVaR).
- **Backtest Overfitting Diagnostics (Stage 33):** Deflated Sharpe Ratio (DSR), Minimum Backtest Length (MinBTL), and Combinatorially Symmetric Cross-Validation (CSCV) estimating Probability of Backtest Overfitting (PBO).
- **Institutional PDF Export Engine (Stage 34):** CSS Paged Media server-side rendering producing 1-page Strategy Fact Sheets, 2-page Institutional Tear Sheets, and Research Diagnostics Annexes via headless Chromium.

---

## 2. Technology Stack

### Backend
- **Language & Runtime:** Python 3.11+
- **API Framework:** FastAPI 0.115+, Pydantic v2
- **Numerical & Scientific Computation:** NumPy 2.x, pandas 2.2+, SciPy 1.13+ (SLSQP solver)
- **Database & Migrations:** PostgreSQL 16+ via SQLAlchemy 2.0 and psycopg v3; SQLite 3 (local file/in-memory fallback); Alembic 1.13+
- **Security & Cryptography:** PyJWT (HS256 with explicit algorithm enforcement), bcrypt
- **PDF Processing:** Headless Chromium via subprocess, PyPDF 6.21+

### Frontend
- **Framework & Language:** React 19, TypeScript 6.0, Vite 8
- **UI Architecture:** Custom design system (CSS variables, dark theme, responsive grid)
- **Data Visualization:** Zero-dependency accessible SVG vector graphics (efficient frontiers, equity curves, drawdown waterfalls, CSCV scatter plots)
- **Testing & Tooling:** Vitest 5, Testing Library, oxlint

---

## 3. High-Level Architecture & Responsibilities

```
                                [ Operator / Browser ]
                                          │
                                          ▼
                      ┌───────────────────────────────────────┐
                      │          Nginx Reverse Proxy          │
                      │          (Port 80 / Port 5173)        │
                      └───────────────────┬───────────────────┘
                                          │
                  ┌───────────────────────┴───────────────────────┐
                  ▼                                               ▼
     ┌────────────────────────┐                     ┌───────────────────────────┐
     │  Frontend SPA (React)  │                     │   FastAPI Backend (8000)  │
     │  • Interactive Labs    │                     │  • API Authentication     │
     │  • SVG Vector Charts   │                     │  • Quant Calculation Core │
     │  • Report Previews     │                     │  • Headless Chromium PDF  │
     │  • Client Validation   │                     │  • Alembic Schema Manager │
     └────────────────────────┘                     └─────────────┬─────────────┘
                                                                  │
                                                                  ▼
                                                    ┌───────────────────────────┐
                                                    │   Relational Persistence  │
                                                    │  • PostgreSQL 16 (Prod)   │
                                                    │  • SQLite Fallback (Dev)  │
                                                    └───────────────────────────┘
```

- **Backend Responsibility:** All financial mathematics, risk models, data deduplication, user authentication, tenant isolation, and physical PDF generation reside strictly in Python modules.
- **Frontend Responsibility:** Data presentation, interactive parameter controls, accessible vector SVG visualization, and client-side view state. No financial calculations are performed in frontend TypeScript.

---

## 4. Quick Start (Local Development)

### Prerequisites
- Python 3.11+
- Node.js 20+ and npm 10+
- Google Chrome or Chromium (for server-side PDF export)

### Step 1: Backend Setup

```powershell
# Navigate to backend directory
cd backend

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1    # On Windows
# source .venv/bin/activate       # On Linux/macOS

# Install dependencies in editable mode
python -m pip install --upgrade pip
pip install -e ".[dev]"

# Start FastAPI development server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- **Interactive API Documentation (Swagger):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health Check Endpoint:** [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)

### Step 2: Frontend Setup

```bash
# In a separate terminal, navigate to frontend directory
cd frontend

# Install dependencies
npm ci

# Launch Vite development server
npm run dev
```

- **Application Workspace:** [http://localhost:5173](http://localhost:5173)

---

## 5. Database Strategy & Migrations

The engine supports dual database backends without code divergence:

1. **Local Development / Offline Testing:** Uses SQLite file fallback (`quant_portfolio.db`) or in-memory SQLite when `DATABASE_URL` is unset or configured as `sqlite:///...`.
2. **PostgreSQL Integration / Production:** Uses PostgreSQL 16 with connection pooling (`psycopg` v3 driver) via `DATABASE_URL=postgresql+psycopg://...`.

### Database Migrations
Database tables are managed via Alembic:
```bash
# Run pending migrations to head (current revision: e5f6a7b8c9d0)
alembic upgrade head

# Inspect current schema revision
alembic current
```

---

## 6. Authentication & Production Security Hardening

The engine implements cookie-based and bearer-token JWT authentication with tenant isolation:
- **Development Mode (`APP_ENV=development`):** Falls back to an internal development signing key if `JWT_SECRET_KEY` is not provided.
- **Production Mode (`APP_ENV=production`):** **Strictly fails closed at application startup** if `JWT_SECRET_KEY` is missing, shorter than 32 characters (256 bits), or matches a known development placeholder.
- **Token Decoding:** Enforces explicit algorithm `HS256`, preventing algorithm confusion attacks.

To generate a compliant production secret key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 7. Local Docker Deployment

The application includes a multi-container Docker Compose configuration (`docker-compose.yml`) orchestrating:
1. `quant_portfolio_postgres`: PostgreSQL 16 Alpine with named volume persistence (`quant_pgdata`).
2. `quant_portfolio_backend`: Python 3.11 with headless Chromium, non-root `appuser`, and in-memory `tmpfs` scratch space.
3. `quant_portfolio_frontend`: Nginx 1.27 Alpine serving the production SPA and proxying `/api/` traffic.

```bash
# 1. Configure environment
cp .env.example .env

# 2. Build and launch services
docker compose up -d --build

# 3. Check health
docker compose ps

# 4. Stop stack preserving database storage
docker compose down
```

For complete deployment instructions, see [docs/LOCAL_DOCKER_DEPLOYMENT.md](docs/LOCAL_DOCKER_DEPLOYMENT.md).

---

## 8. Automated Testing & Quality Checks

Run the verification test suites locally before submitting changes:

```powershell
# Run full backend test suite (660+ tests)
cd backend
pytest -q

# Run frontend test suite (88 tests)
cd ../frontend
npm test

# Run frontend TypeScript typecheck and production build
npm run build

# Run frontend linter
npm run lint
```

---

## 9. Continuous Integration (GitHub Actions)

The repository defines an automated CI workflow in `.github/workflows/ci.yml` with three parallel jobs:
1. **`backend-tests`:** Executes full backend pytest suite on Python 3.11 with SQLite.
2. **`postgres-integration`:** Spins up an ephemeral `postgres:16-alpine` service container, runs `alembic upgrade head`, and tests PostgreSQL ACID transactions, migration state, and connection pooling.
3. **`frontend-build-and-test`:** Sets up Node.js 20, verifies clean `npm ci`, runs `oxlint`, executes all Vitest tests, and compiles the production bundle.

---

## 10. Operational Governance & Known Disclosures

See [docs/OPERATIONS_RUNBOOK.md](docs/OPERATIONS_RUNBOOK.md) for full administrative runbooks and disaster recovery procedures.

### Current Disclosures
- **Docker Host Verification (Conditional Pass):** Docker Engine is unavailable on the local Windows development workstation; live container image builds and startup have been verified statically and in CI workflow definitions, but remain to be observed on a Docker-enabled host.
- **Chromium Sandbox (`OBS-34-D-01`):** Server-side PDF export runs Chromium with `--no-sandbox` inside containers, relying on container user namespaces (`appuser`, uid 10001) and Docker security options (`no-new-privileges:true`) for process isolation.
- **Rendering Concurrency (`OBS-34-D-02`):** Server-side PDF generation is bounded to `PDF_MAX_CONCURRENT_RENDERS=2` to prevent memory exhaustion under concurrent workloads.
