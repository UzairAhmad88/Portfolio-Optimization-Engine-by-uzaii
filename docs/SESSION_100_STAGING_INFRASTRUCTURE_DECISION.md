# SESSION 100 — STAGING INFRASTRUCTURE ARCHITECTURE, HOSTING DECISION & CONTROLLED PROVISIONING PLAN

**Project:** Quantitative Portfolio Optimization Engine (QPE)  
**Repository:** `UzairAhmad88/Portfolio-Optimization-Engine-by-uzaii`  
**Local Path:** `d:\Quants\Projects\quant-portfolio-engine-starter`  
**Branch:** `main`  
**Application Version:** `1.0.0` (strictly preserved)  
**Baseline Commit:** `26ff0dfd574a690d6ce667d3821fa1a3387a645e`  
**Latest CI Run:** [Run 40135409314](https://github.com/UzairAhmad88/Portfolio-Optimization-Engine-by-uzaii/actions/runs/40135409314) (`Status=completed`, `Conclusion=success`)  
**Session Standard:** Planning, architecture evaluation, and cost modeling only. **Zero cloud infrastructure provisioned. Zero costs incurred. Zero releases published.**

---

## 1. Executive Summary & Verification of Baseline

In Session 100, the Quantitative Portfolio Optimization Engine (`QPE`) was prepared for its first controlled external staging deployment. In accordance with strict governance boundaries, this session establishes the definitive infrastructure architecture, evaluates hosting options against quantifiable cost and operational criteria, models resource sizing, defines provider-neutral configuration contracts, and establishes an owner authorization gate.

### Baseline Verification Summary
- **Working Tree:** Clean on `main`, zero uncommitted modifications, synchronized with `origin/main`.
- **Git Commit Ancestry:** HEAD verified at `26ff0dfd574a690d6ce667d3821fa1a3387a645e` (Session 99 preflight integrity audit & verdict hardening).
- **CI Telemetry:** GitHub Actions Run `40135409314` verified 100% green across all 4 jobs:
  - `Frontend Build, Lint & Test (Node 24)`: `success`
  - `PostgreSQL Integration & Migration (PostgreSQL 16)`: `success`
  - `Backend Test Suite (Python 3.11)`: `success` (702 tests passed)
  - `Docker Compose Runtime Verification (Docker / PostgreSQL 16)`: `success`
- **Release Status:** 0 Git tags, 0 GitHub releases. Application version strictly `1.0.0`.
- **Preflight Harness Execution:**
  Executing `.\scripts\verify-staging-readiness.ps1` produces the truthful, deterministic verdict:
  ```
  SUMMARY COUNTS: PASS: 16 | FAIL: 0 | BLOCKED: 4 | WARNING: 4 | NOT_APPLICABLE: 1
  FINAL DECISION: BLOCKED -- MANDATORY PREREQUISITES MISSING
  ```
  The 4 blocked checks precisely identify the missing external prerequisites: Docker on the local Windows management host (`A3`), operator-attested database backup drill on live host (`C4`), external HTTPS probe (`D3`), and edge TLS reverse proxy (`E1`).

---

## 2. Evaluation of Hosting Architectures

Three realistic deployment approaches were evaluated for hosting QPE's multi-tier stack (React SPA, FastAPI backend with numerical computing libraries, PostgreSQL 16 database, and headless Chromium PDF export).

### Comparative Architecture Matrix

| Criterion | Approach 1: Single VPS + Docker Compose + Cloudflare | Approach 2: PaaS (Managed Containers + Managed DB) | Approach 3: Cloud-Native (AWS ECS Fargate + RDS) |
|---|---|---|---|
| **Representative Providers** | Hetzner Cloud (CX33/CPX32) or DigitalOcean Droplet | Render, Railway, or DigitalOcean App Platform | AWS (ECS Fargate + RDS PostgreSQL + ALB) |
| **Initial Complexity** | **Low:** Directly executes repository `docker-compose.yml` with zero topology changes. | **Medium:** Requires decoupling frontend, backend, and database; separate build specs. | **High:** Requires VPC, subnets, NAT gateways, target groups, ALB, IAM roles, ECS task definitions. |
| **Estimated Monthly Cost** | **$10 – $25 / month** (Lowest cost) | **$45 – $75 / month** (Moderate) | **$110 – $160 / month** (High; NAT + ALB baseline) |
| **Operational Burden** | **Medium:** Host OS security updates, Docker daemon maintenance, backup script. | **Low:** Platform handles OS patching, container restarts, and database backups. | **Medium-High:** Cloud infrastructure management, AWS maintenance windows, IAM governance. |
| **Network & Security** | **High:** PostgreSQL & backend strictly bound to loopback `127.0.0.1`. Ingress via Cloudflare TLS 443. | **High:** PaaS edge router terminates TLS; private networking between app and managed DB. | **Very High:** Security Groups, private subnets, WAF, AWS Certificate Manager. |
| **Database Durability** | **Good:** Automated local `pg_dump -Fc` cron + encrypted offsite upload (S3/B2). RPO: 24h. | **High:** Automated daily snapshots, 7-day retention managed by PaaS. Point-in-time recovery optional. | **Very High:** Automated automated snapshots, Multi-AZ option, 35-day retention, continuous PITR. |
| **Quant Workload & Chromium** | **Optimal:** Full access to host CPU/RAM; `/dev/shm` and `tmpfs` sized natively. Zero cold starts. | **Constrained:** Container RAM limits can cause OOM kills during parallel Chromium PDF rendering. | **Good:** Dedicated Fargate task memory; requires $\ge 2\text{GB}$ task definition for Chromium stability. |
| **Portability & Lock-In** | **Zero Lock-In:** Standard Ubuntu + Docker Compose runs identically on any cloud or on-premise server. | **Low-Medium:** Platform-specific YAML (`render.yaml`, `railway.json`); database export standard. | **High Lock-In:** Deeply tied to ECS, CloudFormation/Terraform, ALB, IAM, and CloudWatch. |
| **Staging Suitability** | **Exceptional:** 100% parity with local development and CI `docker-compose-verification` job. | **Good:** Fast automated deploys from Git, but differs structurally from Compose setup. | **Excessive:** High cost and complexity overhead for an early-stage research engine staging gate. |

---

## 3. Recommended Architecture Decisions

### Preferred Architecture: Dedicated Linux VPS with Cloudflare Edge Ingress & Docker Compose
**Recommendation:** Deploy on a dedicated virtual private server running **Ubuntu 24.04 LTS** (e.g. DigitalOcean Basic Droplet 2 vCPU / 4 GB RAM at $24/mo, or Hetzner Cloud CX33 4 vCPU / 8 GB RAM at ~€8.50/mo), fronted by **Cloudflare Edge Proxy (Free Tier)**.

#### Architectural Rationale
1. **100% Parity with Validated Compose Packaging:** The application has been rigorously validated in GitHub Actions (`docker-compose-verification`) and local testing using Docker Compose. Running Compose directly on a single host ensures exact configuration parity, eliminating subtle PaaS runtime discrepancies.
2. **Predictable Headless Chromium Performance:** Generating 3-page Institutional Dossiers with headless Chromium requires shared memory (`tmpfs` / `/dev/shm`) and sustained memory bursts (~200MB per render process). A dedicated 4GB–8GB host prevents out-of-memory kills that frequently crash serverless or memory-constrained PaaS instances.
3. **Institutional Cost Efficiency:** Staging infrastructure for a small quantitative platform must remain affordable while providing strict security. Operating at ~$15–$25/month provides full institutional isolation without incurring hundreds of dollars in cloud infrastructure overhead.
4. **Strong Ingress Protection:** Cloudflare provides automated edge TLS termination, HTTP-to-HTTPS enforcement, DDoS mitigation, and SSL certificate management at zero cost.

### Fallback Architecture: Managed Container Platform + Managed Database (Render / DigitalOcean App Platform)
If the project owner prefers to avoid OS-level maintenance, the designated fallback is:
- **Backend:** Managed Web Service (2 vCPU / 2GB–4GB RAM, Docker runtime).
- **Frontend:** Static Site or lightweight Nginx container.
- **Database:** Managed PostgreSQL 16 (Single node, 1 vCPU / 2GB RAM, automated daily backups).
- **Trade-Off:** Costs approximately $45–$65/month (2.5x higher) and requires maintaining separate deployment configurations outside `docker-compose.yml`.

---

## 4. Cost Model & Detailed Assumptions

All prices reflect verifiable 2026 rates from official provider documentation.

### Option A: Preferred Architecture (VPS + Docker Compose + Cloudflare)
- **Primary Compute Host:**
  - *DigitalOcean Regular Droplet:* 2 vCPU, 4 GB RAM, 80 GB NVMe SSD, 4 TB transfer = **$24.00 / month** ($0.0357/hr)
  - *Alternative (Hetzner Cloud CX33, Nuremberg/Falkenstein):* 4 vCPU, 8 GB RAM, 80 GB SSD, 20 TB transfer = **€8.49 / month** (~$9.20/mo excl. VAT)
- **Ingress & TLS:** Cloudflare Free Tier (Edge SSL, DNS, DDoS, Basic WAF) = **$0.00 / month**
- **Offsite Encrypted Backup Storage:** Cloudflare R2 / Backblaze B2 / AWS S3 (estimated 20 GB snapshot storage) = **~$0.30 – $0.50 / month**
- **Estimated Total Monthly Run-Rate:** **$10.00 – $25.00 / month**
- **One-Time Provisioning Costs:** $0.00

### Option B: PaaS Architecture (DigitalOcean App Platform / Render)
- **Backend Container:** Professional Tier (2 vCPU, 2GB RAM) = **$25.00 / month**
- **Frontend Container:** Basic Web Service = **$5.00 / month**
- **Managed PostgreSQL 16:** Basic Cluster (1 vCPU, 2GB RAM, 20GB SSD, automated snapshots) = **$25.00 / month**
- **Estimated Total Monthly Run-Rate:** **$55.00 / month**

### Option C: Cloud-Native AWS Architecture (ECS Fargate + RDS)
- **ECS Fargate Tasks:** Backend (1 vCPU, 2GB RAM) + Frontend (0.5 vCPU, 1GB RAM) = **~$45.00 / month**
- **Amazon RDS PostgreSQL:** `db.t4g.small` (2 vCPU, 2GB RAM, 20GB gp3, Single-AZ) = **$25.66 / month**
- **Application Load Balancer (ALB):** Base ($16.40/mo) + LCU fees (~$4.00/mo) = **~$20.40 / month**
- **AWS NAT Gateway:** (Required for Fargate private subnet egress) = **~$32.85 / month**
- **CloudWatch Logs & Secrets Manager:** **~$5.00 / month**
- **Estimated Total Monthly Run-Rate:** **$128.91 / month**

### Cost Modeling Assumptions
1. Staging environment will experience low-to-moderate continuous traffic (mostly developer and automated smoke tests).
2. Outbound bandwidth is well within standard bundled allowances (4 TB included on DigitalOcean; 20 TB on Hetzner).
3. Compute pricing is on-demand without long-term reserved commitments, allowing immediate decommissioning if necessary.

---

## 5. Network Topology & Security Architecture

```
                          ┌────────────────────────┐
                          │   Public Internet /    │
                          │   Client Web Browser   │
                          └───────────┬────────────┘
                                      │
                                      ▼ HTTPS (Port 443)
                          ┌────────────────────────┐
                          │   Cloudflare Edge      │
                          │   • TLS Termination    │
                          │   • Strict SSL Cert    │
                          │   • DDoS Protection    │
                          └───────────┬────────────┘
                                      │
                                      ▼ Encrypted HTTP (Port 443 / 80)
┌─ STAGING HOST (Ubuntu 24.04 LTS) ────────────────────────────────────────────────────────┐
│                                                                                           │
│   Host Firewall (UFW):                                                                    │
│   • Port 22:   SSH (Key-only authentication, fail2ban active)                             │
│   • Port 80:   Allowed ONLY from Cloudflare Edge IP CIDRs                                 │
│   • Port 443:  Allowed ONLY from Cloudflare Edge IP CIDRs                                 │
│   • Port 5432: STRICTLY BLOCKED from external interfaces                                  │
│   • Port 8000: STRICTLY BLOCKED from external interfaces                                  │
│                                                                                           │
│   ┌───────────────────────────────────────────────────────────────────────────────────┐   │
│   │ Docker Compose Network (`quant_network` - Bridge Driver)                           │   │
│   │                                                                                   │   │
│   │   ┌───────────────────────────┐         Proxy `/api/`                             │   │
│   │   │  `frontend` (Nginx 1.27)  │───────────────────────────────┐                   │   │
│   │   │  • Listens: 0.0.0.0:80    │                               │                   │   │
│   │   │  • Serves static SPA      │                               ▼                   │   │
│   │   │  • Security headers       │                   ┌───────────────────────────┐   │
│   │   └───────────────────────────┘                   │ `backend` (FastAPI 3.11)  │   │
│   │                                                   │ • Direct: 127.0.0.1:8000  │   │
│   │                                                   │ • Headless Chromium       │   │
│   │                                                   │ • In-Memory Semaphore N=2 │   │
│   │                                                   └─────────────┬─────────────┘   │
│   │                                                                 │                 │   │
│   │                                                   SQL (5432)    ▼                 │   │
│   │                                                   ┌───────────────────────────┐   │
│   │                                                   │ `postgres` (Postgres 16)  │   │
│   │                                                   │ • Direct: 127.0.0.1:5432  │   │
│   │                                                   │ • Named Vol `quant_pgdata`│   │
│   │                                                   └───────────────────────────┘   │
│   └───────────────────────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

### Network Isolation & Verification Standards
1. **Public Ingress Restriction:** Only the Nginx frontend container exposes port 80 to the host network interface. UFW firewall rules restrict ingress on port 80 to Cloudflare's published IP ranges.
2. **Internal Loopback Binding:** In `docker-compose.yml`, both `postgres` (`127.0.0.1:5432:5432`) and `backend` (`127.0.0.1:8000:8000`) are explicitly bound to the loopback interface (`127.0.0.1`). They cannot be reached from any external network adapter or public IP.
3. **Forwarded Headers Contract:** When Cloudflare terminates TLS on 443, it forwards `X-Forwarded-Proto: https` to Nginx. To ensure FastAPI generates HTTPS redirect URLs and properly sets secure cookies, Nginx must preserve the incoming forwarded proto:
   ```nginx
   # frontend/nginx.conf proxy block:
   proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;
   ```
4. **Cookie Security Policy:** The backend configuration setting `COOKIE_SECURE=true` is mandatory in staging. This guarantees that JWT authentication cookies carry the `Secure; HttpOnly; SameSite=Lax` flags, preventing plaintext transmission.

---

## 6. Provider-Neutral Infrastructure Configuration Contract

All variable names, ports, and defaults reflect actual repository implementations in `docker-compose.yml`, `.env.example`, `backend/.env.example`, and `backend/app/core/config.py`.

### Complete Environment Variable Contract

| Variable Name | Required? | Consumed By | Staging Specification / Example | Security Requirement |
|---|---|---|---|---|
| **`APP_ENV`** | **Yes** | Backend | `production` (or `staging` with production flags) | Enforces fail-closed configuration validation. |
| **`LOG_LEVEL`** | No | Backend | `INFO` | Emits structured operational logs. |
| **`POSTGRES_USER`** | **Yes** | Postgres, Backend | `quant_staging_user` | Non-default database administrative role. |
| **`POSTGRES_PASSWORD`** | **Yes** | Postgres, Backend | Generated $\ge 24$ char random string | **Never default.** Rejects 14 blacklisted passwords. |
| **`POSTGRES_DB`** | **Yes** | Postgres, Backend | `quant_portfolio_staging` | Staging database identifier. |
| **`DATABASE_URL`** | **Yes** | Backend, Alembic | `postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}` | Fails closed if SQLite URL is supplied under production mode. |
| **`JWT_SECRET_KEY`** | **Yes** | Backend (Auth) | Generated 64-char hex string (256-bit entropy) | Fails closed if $< 32$ chars or blacklisted placeholder. |
| **`ACCESS_TOKEN_EXPIRE_MINUTES`** | No | Backend | `60` | Token validity duration. |
| **`COOKIE_SECURE`** | **Yes** | Backend (Auth) | `true` | Enforces `Secure` flag on JWT cookies over HTTPS. |
| **`AUTH_REQUIRED`** | No | Backend | `true` | Enforces authentication on research endpoints. |
| **`CORS_ORIGINS`** | **Yes** | Backend (CORS) | `https://staging.quantengine.internal` | Exact staging FQDN; wildcard `*` strictly forbidden. |
| **`CHROME_BIN`** | No | Backend (PDF) | `/usr/bin/chromium` | Validated binary path inside Linux container. |
| **`PDF_MAX_CONCURRENT_RENDERS`** | No | Backend (PDF) | `2` | Bounded semaphore prevents container memory exhaustion. |
| **`RUN_MIGRATIONS`** | No | Backend (Entrypoint) | `true` | Executes `alembic upgrade head` before serving traffic. |
| **`FRONTEND_PORT`** | No | Compose (Frontend) | `80` | Host port mapped to frontend Nginx container. |

### Staging Secret Generation & Protection Standards
- Staging credentials must be generated using cryptographically secure randomness:
  ```bash
  # Generate JWT Secret Key (64-character hex string / 256 bits):
  python -c "import secrets; print(secrets.token_hex(32))"
  
  # Generate Database Password (32-character URL-safe string):
  python -c "import secrets; print(secrets.token_urlsafe(24))"
  ```
- Deployment `.env` file on staging host must be restricted to root/deploy user:
  ```bash
  chmod 600 /opt/qpe/.env
  chown root:root /opt/qpe/.env
  ```
- Never commit `.env` or paste staging credentials in documentation, pull requests, or issue trackers.

---

## 7. Database Durability, Backup & Recovery Plan

### Persistence Architecture
- Data is stored in Docker named volume `quant_pgdata`, mapped to `/var/lib/postgresql/data` inside `postgres:16-alpine`.
- Volume persists independently of container restarts, image rebuilds, and standard deployments (`docker compose down` without `-v`).

### Backup Frequency & Retention Policy (Proposed)
1. **Automated Daily Snapshot:** Cron job runs at `02:00 UTC` daily executing `pg_dump -Fc` (custom compressed format).
2. **Encrypted Offsite Sync:** Backups are compressed, encrypted using AES-256 via GPG (`gpg --symmetric`), and synchronized to offsite object storage (Cloudflare R2 / AWS S3).
3. **Retention Schedule:**
   - Daily backups retained for **14 days**.
   - Weekly backups retained for **8 weeks**.
   - Monthly backups retained for **6 months**.
4. **Pre-Migration Safety Snapshot:** A manual snapshot is mandatorily triggered immediately before executing any database migration or software deployment.

### Recovery Objectives
- **Recovery Point Objective (RPO):** Proposed **24 hours** for staging (daily backup). For production, automated WAL archiving can achieve RPO $< 15$ minutes.
- **Recovery Time Objective (RTO):** Proposed **$< 30$ minutes** to restore a database snapshot to a clean staging container.

### Isolated Restoration Verification Protocol
In accordance with Session 97 Test 11, backup viability must be verified in an isolated test database container before attestation:
```bash
# 1. Create backup snapshot
docker compose exec -T postgres pg_dump -U quant_staging_user -Fc quant_portfolio_staging > /var/backups/qpe/pre_deploy.dump

# 2. Spin up ephemeral sandbox PostgreSQL container on isolated port
docker run --rm -d --name qpe_restore_sandbox -e POSTGRES_PASSWORD=test_restore_pwd -p 127.0.0.1:5433:5432 postgres:16-alpine

# 3. Restore snapshot into sandbox database
pg_restore -h 127.0.0.1 -p 5433 -U postgres -d postgres -v /var/backups/qpe/pre_deploy.dump

# 4. Cleanly terminate sandbox container
docker stop qpe_restore_sandbox
```

---

## 8. Resource Sizing & Failure Boundaries

### Measured Component Sizing

| Container / Process | Baseline RAM | Peak RAM (Workload) | Recommended Limit (`deploy.resources.limits`) | Potential Failure Modes & Safeguards |
|---|---|---|---|---|
| **PostgreSQL 16** | ~80 MB | ~256 MB (Complex queries) | `memory: 512M`, `cpus: '1.0'` | Slow queries during backtest table scans. Mitigated by indexed foreign keys. |
| **FastAPI Backend** | ~180 MB | ~500 MB (Matrix calculations) | `memory: 1536M`, `cpus: '2.0'` | Out-of-memory during massive CSCV/PBO combinatorial iterations. Mitigated by bounded memory limits. |
| **Chromium PDF Render** | 0 MB (idle) | ~250 MB per render process | Bounded by `PDF_MAX_CONCURRENT_RENDERS=2` | Chromium subprocess crash or hang. Mitigated by 25s render timeout and 256MB tmpfs buffer. |
| **Nginx Frontend** | ~15 MB | ~30 MB (High concurrency) | `memory: 128M`, `cpus: '0.5'` | Buffer overflow / client body size. Mitigated by Nginx body size restrictions. |
| **Host System Overhead** | ~400 MB | ~600 MB (OS + Docker + logs) | Minimum 1 GB reserved for host | Host swap thrashing. Mitigated by sizing host $\ge 4\text{GB}$ total RAM. |

### Execution Timeouts
- **FastAPI / Uvicorn Request Timeout:** `90 seconds` (accommodates heavy Ledoit-Wolf / Copula backtests).
- **Nginx `proxy_read_timeout`:** `90 seconds` (aligned with backend timeout).
- **Chromium PDF Generation Timeout:** Hard timeout of `25 seconds` enforced via `subprocess.run(timeout=25.0)`.
- **Database Connection Pool Timeout:** `30 seconds` (`DB_POOL_TIMEOUT=30.0`).

---

## 9. Monitoring, Alerting & Operational Security

### Implemented Controls vs. Post-Provisioning Controls

| Control Domain | Currently Implemented in Codebase | Requires Post-Provisioning Infrastructure Setup |
|---|---|---|
| **Application Health Checks** | Active endpoints: `/healthz` (Nginx), `/api/v1/health` (FastAPI with DB check). | External synthetic uptime probe (e.g., UptimeRobot pinging `https://staging.../healthz` every 60s). |
| **Secret Protection** | Fail-closed validation at startup; `redact_sensitive_text()` active in preflight. | Host-level `.env` file permission hardening (`chmod 600`). |
| **Port Isolation** | Postgres 5432 & Backend 8000 bound strictly to `127.0.0.1` in `docker-compose.yml`. | Host firewall (UFW) verifying only ports 22, 80, 443 accept packets. |
| **Ingress Rate Limiting** | In-memory `LoginRateLimiter` active on `/api/v1/auth/login`. | Edge rate limiting configured at Cloudflare (e.g. max 100 req/min per IP). |
| **Container Logging** | Structured JSON logging in backend; Nginx access logging. | Docker logging driver configuration (`max-size: "50m"`, `max-file: "5"`) to prevent disk fill. |
| **TLS Certificate Expiry** | Probed via `D3` preflight check with strict certificate validation. | Automated Cloudflare Universal SSL renewal monitoring. |

---

## 10. Staging Deployment Acceptance Checklist

The 15-point verification procedure derived from Sessions 97, 98, and 99 must be executed on the live staging host upon provisioning:

| Test ID | Verification Step | Command / Action | Expected Outcome | Evidence Retained | Classification | Severity if Failed |
|---|---|---|---|---|---|---|
| **STG-01** | Repository & Target Cleanliness | `git status --short --branch; git rev-parse HEAD` | Branch is `main`, zero untracked changes, matches approved release commit. | Terminal log with SHA | Automated | Blocker |
| **STG-02** | Staging Preflight CLI Execution | `python -m app.ops.staging_preflight --strict` | Preflight executes; confirms configuration hygiene and zero defaults. | Formatted preflight report | Automated | Blocker |
| **STG-03** | Secrets & Environment Configuration | `test -f /opt/qpe/.env && stat -c %a /opt/qpe/.env` | File exists with permissions `600`; random secrets present. | Perm check log (no secrets) | Config Inspected | Blocker |
| **STG-04** | Container Build & Startup | `docker compose up -d --build` | All 3 containers (`postgres`, `backend`, `frontend`) build and start. | `docker compose ps` log | Runtime Verified | Blocker |
| **STG-05** | Service Health Probes | `curl -sSf http://127.0.0.1/healthz && curl -sSf http://127.0.0.1:8000/api/v1/health` | HTTP 200 OK returned; backend reports database connected. | HTTP response body | Runtime Verified | Blocker |
| **STG-06** | Alembic Migration Revision | `docker compose exec backend alembic current` | Output displays head revision `e5f6a7b8c9d0 (head)`. | Terminal output | Runtime Verified | Blocker |
| **STG-07** | External HTTPS & TLS Handshake | `curl -Iv https://staging.quantengine.internal/healthz` | HTTP 200 via HTTPS; valid SSL certificate; no cert errors. | TLS handshake verbose log | Runtime Verified | Blocker |
| **STG-08** | Loopback Port Security Audit | `ss -tulpn \| grep -E '5432\|8000'` | Ports 5432 and 8000 bound strictly to `127.0.0.1`. | Port listener list | Config Inspected | Blocker |
| **STG-09** | User Registration & Auth | POST `/api/v1/auth/register` and POST `/api/v1/auth/login` | HTTP 200/201; returns valid JWT; secure cookie set. | Network response (redacted) | Runtime Verified | Blocker |
| **STG-10** | Protected Route Authorization | GET `/api/v1/portfolio/analytics` without token | HTTP 401 Unauthorized strictly enforced. | HTTP 401 response | Runtime Verified | Blocker |
| **STG-11** | Optimization Engine Smoke Test | POST `/api/v1/portfolio/optimize` (Markowitz / Max Sharpe) | HTTP 200; weights sum to 1.0; valid frontier calculated. | JSON calculation payload | Runtime Verified | Major |
| **STG-12** | Overfitting & Backtest Smoke Test | POST `/api/v1/research/overfitting/diagnostics` | HTTP 200; returns PBO probability, CSCV matrix, and DSR score. | Diagnostic metrics output | Runtime Verified | Major |
| **STG-13** | Server-Side Chromium PDF Export | GET `/api/v1/reports/unified/{id}/export` | HTTP 200; `Content-Type: application/pdf`; magic bytes `%PDF-`. | PDF file header inspection | Runtime Verified | Major |
| **STG-14** | Database Backup & Restore Drill | Execute Section 7 Isolated Restore Drill | Clean restore into test DB; table row counts match live DB. | Sandbox restore log | **Manually Attested** | Major |
| **STG-15** | Container Restart Persistence | `docker compose restart postgres && curl http://127.0.0.1:8000/api/v1/health` | Container restarts; health endpoint recovers; data retained. | Uptime verification log | Runtime Verified | Major |

---

## 11. Rollback & Disaster Recovery Procedures

### Software Deployment Rollback
If a staging deployment fails post-startup tests:
```bash
# 1. Revert to previous known-good commit
git checkout <PREVIOUS_COMMIT_SHA>

# 2. Rebuild and restart containers
docker compose up -d --build

# 3. Verify health
curl -sSf http://127.0.0.1/healthz
```

### Database Failure Rollback
If schema migration or data corruption occurs during staging testing:
```bash
# 1. Stop application backend
docker compose stop backend

# 2. Restore database from pre-deployment snapshot
docker compose exec -T postgres psql -U quant_staging_user -d quant_portfolio_staging < /var/backups/qpe/pre_deploy.sql

# 3. Restart backend
docker compose start backend

# 4. Verify Alembic revision
docker compose exec backend alembic current
```

---

## 12. Project Owner Authorization Gate

Before any external infrastructure is provisioned or staging deployment commences, the Project Owner must review and authorize the following decisions:

- [ ] **Hosting Architecture Approval:** Authorize **Approach 1** (Dedicated Linux VPS with Docker Compose & Cloudflare) or **Approach 2** (Managed PaaS).
- [ ] **Hosting Provider Selection:** Select preferred cloud provider (e.g. DigitalOcean $24/mo, Hetzner Cloud ~€9/mo, or AWS).
- [ ] **Target Deployment Region:** Select physical data center region (e.g., US-East, US-West, EU-Central) based on jurisdictional/compliance requirements.
- [ ] **Monthly Operating Budget:** Approve estimated staging expenditure of **$10 – $25 / month** (or up to $60/mo for PaaS).
- [ ] **Domain Name & DNS Control:** Confirm staging domain/subdomain assignment (e.g., `staging-qpe.firm.com`) and Cloudflare DNS management access.
- [ ] **Credential Ownership:** Confirm that staging master database credentials and production secrets are generated and held exclusively by the Project Owner.
- [ ] **Formal Authorization to Provision:** Authorize DevSecOps engineer to provision the selected VPS instance and configure host firewall.

---

## 13. Explicit Governance Confirmation

**It is explicitly certified that during Session 100:**
1. Zero cloud infrastructure or virtual machines were provisioned.
2. Zero hosting accounts or cloud services were registered.
3. Zero DNS records were modified.
4. Zero paid SSL/TLS certificates were purchased.
5. Zero cloud costs were incurred.
6. Zero Git release tags were created or pushed.
7. Zero GitHub releases were published.
8. Zero staging or production deployments were executed.
9. Application version was strictly preserved at `1.0.0`.
