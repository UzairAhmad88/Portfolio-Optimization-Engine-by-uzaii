# Local Docker Deployment & Production Packaging Guide

**Stage:** Release Packaging & Operational Readiness (Session 82)
**Target Environment:** Local / Self-Hosted Docker Compose Stack
**Supported Runtimes:** Docker Engine 20.10+ / Docker Compose v2+
**Architecture:** Multi-Container Modular Monolith (PostgreSQL + FastAPI Backend with Headless Chromium + Nginx Frontend)

---

## 1. System Architecture Overview

The local Docker deployment packages the full Quantitative Portfolio Optimization Engine stack into three coordinated container services running on an isolated bridge network (`quant_portfolio_network`):

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

---

## 2. Prerequisites

1. **Docker Engine:** Version 20.10 or higher.
2. **Docker Compose:** Version 2.0 or higher (`docker compose` CLI plugin).
3. **Hardware Resources:**
   - Minimum: 2 CPU cores, 2 GB RAM.
   - Recommended: 4 CPU cores, 4 GB RAM (to accommodate parallel numerical optimizations and concurrent Chromium PDF rasterization).

---

## 3. Quickstart Deployment Workflow

### Step 1: Configure Environment Variables
Copy `.env.example` to `.env` and configure credentials:

```bash
cp .env.example .env
```

> [!CAUTION]
> **Production Security Mandate:** Before deploying to an accessible environment, generate a cryptographically strong 256-bit secret key for `JWT_SECRET_KEY` and update the database password:
> ```bash
> python -c "import secrets; print(secrets.token_hex(32))"
> ```

### Step 2: Build and Launch Services
Build the container images and launch the stack in detached mode:

```bash
docker compose up -d --build
```

### Step 3: Verify Container Health
Inspect running container states and health checks:

```bash
docker compose ps
```

Expected output:
```
NAME                       IMAGE                             COMMAND                  SERVICE    STATUS
quant_portfolio_postgres   postgres:16-alpine                "docker-entrypoint.s…"   postgres   Up (healthy)
quant_portfolio_backend    quant-portfolio-engine-backend    "/app/entrypoint.sh …"   backend    Up (healthy)
quant_portfolio_frontend   quant-portfolio-engine-frontend   "/docker-entrypoint.…"   frontend   Up (healthy)
```

### Step 4: Access the Application
- **Frontend Research Workspace:** [http://localhost](http://localhost) (or `http://localhost:${FRONTEND_PORT}`)
- **Interactive OpenAPI Documentation:** [http://localhost/docs](http://localhost/docs) (or directly via `http://localhost:8000/docs`)
- **Backend Health Check:** [http://localhost/api/v1/health](http://localhost/api/v1/health)

---

## 4. Database Persistence & Migrations

### Persistent Storage
PostgreSQL records, user accounts, market data, and research snapshots are stored in the Docker named volume:
- **Volume Name:** `quant_portfolio_pgdata`
- **Container Path:** `/var/lib/postgresql/data`

> [!IMPORTANT]
> **Data Preservation Rule:** Stopping the stack with `docker compose down` preserves all database tables and uploaded datasets. **Never** use `docker compose down -v` unless you explicitly intend to purge all persistent database records.

### Automated Migrations on Startup
The backend container includes an entrypoint script (`/app/entrypoint.sh`) that probes PostgreSQL connectivity and automatically applies pending Alembic migrations:
```bash
alembic upgrade head
```

### Manual Migration Verification
To verify migration status or manually execute Alembic commands inside the running container:
```bash
# Check current migration revision
docker compose exec backend alembic current

# View migration history
docker compose exec backend alembic history --verbose

# Apply pending revisions manually
docker compose exec backend alembic upgrade head
```

---

## 5. Chromium Server-Side PDF Rendering & Security

### Container Isolation Architecture
The backend container is hardened to execute Chromium safely:
1. **Unprivileged Runtime:** The application runs under user `appuser` (`uid 10001:10001`), completely eliminating root privileges inside the container.
2. **Restricted Privilege Escalation:** Configured with `security_opt: [no-new-privileges:true]` in `docker-compose.yml`.
3. **In-Memory Scratch Storage:** The temporary rendering scratch directory (`/app/tmp`) is mounted as a dedicated `tmpfs` volume (`size=256M,uid=10001,gid=10001,mode=1777`), ensuring rendering artifacts never touch container disk storage and are wiped on reboot.
4. **Network & File Boundaries:** Chromium is invoked with `--disable-background-networking`, `--disable-remote-fonts`, `--disable-sync`, and `--disable-extensions`, rendering static HTML templates without outbound network requests.

### Acknowledged Operational Boundaries
- **`OBS-34-D-01` (`--no-sandbox`):** Chromium runs with `--no-sandbox` because standard Linux container runtimes disable user-namespace sandboxing without elevated capabilities. Isolation relies on the unprivileged container user and Docker's Linux namespace boundaries.
- **`OBS-34-D-02` (Concurrency):** Concurrent renders are bounded by `PDF_MAX_CONCURRENT_RENDERS=2` per container process.

### Testing PDF Generation Inside the Stack
To test server-side PDF export directly from the running stack:
```bash
# Obtain authentication token
TOKEN=$(curl -s -X POST http://localhost/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "researcher@example.com", "password": "password123"}' \
  | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

# Export Strategy Fact Sheet to PDF
curl -s -X GET "http://localhost/api/v1/reports/fact-sheet/<BACKTEST_ID>/export" \
  -H "Authorization: Bearer $TOKEN" \
  --output test_fact_sheet.pdf

# Verify PDF signature header
head -c 5 test_fact_sheet.pdf
# Expected output: %PDF-
```

---

## 6. Operational Diagnostics & Log Inspection

### Viewing Service Logs
```bash
# Stream all logs
docker compose logs -f

# Inspect backend application logs specifically
docker compose logs -f backend

# Inspect Nginx access and error logs
docker compose logs -f frontend

# Inspect PostgreSQL transaction logs
docker compose logs -f postgres
```

### Diagnosing Missing Chromium Dependencies
If PDF export returns HTTP 503 or an error indicating browser execution failure:
```bash
# Verify Chromium binary path inside the container
docker compose exec backend which chromium
# Expected output: /usr/bin/chromium

# Check Chromium version and library linkages
docker compose exec backend /usr/bin/chromium --version --no-sandbox
```

---

## 7. Database Backup & Disaster Recovery

### Creating a Snapshot Backup
Execute `pg_dump` directly against the PostgreSQL container:
```bash
docker compose exec -T postgres pg_dump -U quant_user quant_portfolio_db > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Restoring from Backup
```bash
# Drop active connections and restore
docker compose exec -T postgres psql -U quant_user -d quant_portfolio_db < backup_file.sql
```

---

## 8. Service Lifecycle Commands

| Action | Command |
|---|---|
| **Start Stack in Background** | `docker compose up -d` |
| **Rebuild Images & Start** | `docker compose up -d --build` |
| **Stop Stack (Preserve Data)** | `docker compose stop` |
| **Stop and Remove Containers** | `docker compose down` |
| **Restart a Specific Service** | `docker compose restart backend` |
| **Execute Shell in Backend** | `docker compose exec backend /bin/sh` |
| **Check Port Mappings** | `docker compose port frontend 80` |
| **Inspect System Volumes** | `docker volume ls` |
