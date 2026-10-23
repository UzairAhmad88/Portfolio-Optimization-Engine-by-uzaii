# Stage 34 Gate D: Secure Server-Side PDF Rendering Pipeline & Export Dispatcher

**Status:** IMPLEMENTED — Awaiting Independent Review & Acceptance
**Branch:** `main`
**Base Commit:** `22a4284`
**Delivery Scope:** Server-side PDF rendering architecture, sandboxed headless browser pipeline, authenticated REST export endpoints, pypdf physical pagination verification, security boundaries, and frontend PDF download integration.

---

## 1. Executive Summary

Stage 34 Gate D implements an institutional-grade, secure server-side PDF rendering engine and export dispatcher for the Quantitative Portfolio Optimization Engine.

Extending the canonical domain contracts of Gate A, the analytical aggregation service of Gate B, and the print media styling and vector visualizations of Gate C, Gate D enables authenticated users to generate and download publication-ready PDF documents directly from the backend API or via the frontend report viewer.

The backend acts as the single source of truth for all quantitative calculations, executive KPIs, benchmark relative attributions, monthly returns, asset allocations, risk disclosures, and Stage 32 cryptographic dataset provenance digests. The PDF rendering engine performs presentation-only formatting without independently computing, modifying, or fabricating financial metrics.

---

## 2. Rendering Engine Selection & Architecture Rationale

### Evaluation: Headless Chromium vs. WeasyPrint

During architecture reconnaissance, two candidate server-side rendering strategies were evaluated:

| Criterion | Headless Chromium / Edge (`--headless=new`) | WeasyPrint (HTML2PDF via Cairo/Pango) | Decision Rationale |
| :--- | :--- | :--- | :--- |
| **CSS Paged Media Fidelity** | Full native support for `@page { size: letter portrait; margin: 10mm 12mm; }`, page breaks (`break-after: page`, `page-break-after: always`), and print media queries. | Strong `@page` support, but variable CSS Flexbox and SVG rendering edge cases. | **Chromium Selected** |
| **Vector SVG Rendering** | Native Blink SVG rendering engine with 100% fidelity to on-screen previews for multi-series NAV curves, gradient fills, and scatter/histogram overlays. | Limited support for complex SVG filters, clipping paths, and font metrics. | **Chromium Selected** |
| **Windows & Linux Compatibility** | Standard binary present out-of-the-box on developer Windows workstations (`chrome.exe`, `msedge.exe`) and easily packaged on Linux via standard container packages (`chromium` / `chromium-browser`). | Requires external C-libraries (Cairo, Pango, GDK-PixBuf, libffi) which are notoriously brittle to install and maintain on Windows workstations. | **Chromium Selected** |
| **Performance & Resource Footprint** | Extremely fast rendering (~500ms–1.5s per document) with explicit `--headless=new` and compositor flags. Process concurrency is bounded via a semaphore. | Pure-Python wrapper over C-libraries, but slower on complex SVGs with high point counts. | **Chromium Selected** |
| **Zero Heavy Python Bundles** | Zero heavy runtime Python packages required; interacts via a hardened subprocess execution. Combined with pure-Python `pypdf` for structural verification. | Requires installing heavy C-extension wheels and system runtime DLLs. | **Chromium Selected** |

### Decision
**Headless Chromium (`--headless=new`)** was chosen as the primary rendering engine, utilizing available Chromium/Chrome/Edge binaries on the host system. `pypdf` (`pypdf==6.21.2`) was selected as the zero-native-dependency Python library for PDF structural validation, `%PDF-` signature verification, and physical page count inspection.

---

## 3. Sandboxing & Secure Rendering Boundary

Because report metadata (portfolio names, strategy tags, warning notes, user identifiers) could contain untrusted input, the rendering boundary enforces strict multi-layered security controls:

1. **HTML Entity Escaping:**
   - All user-controlled text, titles, symbols, warnings, and provenance metadata are escaped using `html.escape(quote=True)` prior to injection into HTML templates.
2. **Deterministic Trusted Application Templates:**
   - The renderer does not accept user-supplied HTML or URLs. All layouts are constructed from fixed, deterministic application templates defined in `backend/app/reports/pdf_templates.py`.
3. **Subprocess Sandboxing Flags:**
   - Headless Chromium runs with hardened security and isolation flags:
     - `--headless=new`: Modern, secure Chromium headless architecture.
     - `--disable-gpu`: Eliminates hardware acceleration vulnerabilities.
     - `--no-sandbox`: Required for isolated container/local environments.
     - `--disable-background-networking`: Disables telemetry and network requests.
     - `--disable-default-apps`: Disables default extension loading.
     - `--disable-extensions`: Prevents browser extensions from executing.
     - `--disable-sync`: Prevents account sync or cloud connections.
     - `--no-first-run`: Prevents setup wizards.
     - `--no-pdf-header-footer`: Suppresses default browser headers/footers (dates, URLs, page numbers) to preserve institutional layout.
     - `--run-all-compositor-stages-before-draw`: Ensures full layout completion and vector SVG rasterization before printing.
4. **Network & File Isolation:**
   - The rendering process is provided HTML via an isolated temporary file located inside a dedicated `tempfile.TemporaryDirectory`. No remote network requests or SSRF calls are permitted.
5. **Bounded Concurrency & Timeouts:**
   - A threading `BoundedSemaphore(3)` restricts concurrent browser rendering processes to a maximum of 3 simultaneous jobs, preventing CPU or memory exhaustion (Denial of Service).
   - Execution is bounded by a strict 25-second timeout (`subprocess.run(..., timeout=25)`). If rendering times out, the subprocess is terminated and a structured `PDFRenderingError` is raised.
6. **Guaranteed Ephemeral Cleanup:**
   - Temporary HTML and PDF files reside in an ephemeral temporary directory managed by a `try ... finally` block, ensuring complete deletion on both successful export and unexpected failures.
7. **Safe Content-Disposition & Headers:**
   - Export endpoints emit sanitized ASCII filenames: `attachment; filename="<sanitized_name>.pdf"`.
   - Headers include `Content-Type: application/pdf` and `X-Content-Type-Options: nosniff`.

---

## 4. API Endpoints & Authorization Contracts

Export endpoints are integrated into `backend/app/api/v1/reporting_routes.py` and require cryptographic JWT authentication (`get_current_active_user`).

### Endpoint Specifications

| Endpoint | Method | Path Parameters | Description | Intended Page Target |
| :--- | :--- | :--- | :--- | :--- |
| `/api/v1/reports/fact-sheet/{backtest_id}/export`<br>*(alias: `/export/fact-sheet/{id}`)* | `GET` | `backtest_id: int` | Generates a 1-Page Strategy Fact Sheet PDF for the specified backtest. | **Exactly 1 Page** |
| `/api/v1/reports/tear-sheet/{backtest_id}/export`<br>*(alias: `/export/tear-sheet/{id}`)* | `GET` | `backtest_id: int` | Generates a 2-Page Institutional Tear Sheet PDF for the specified backtest. | **Exactly 2 Pages** |
| `/api/v1/reports/research-annex/{experiment_id}/export`<br>*(alias: `/export/research-annex/{id}`)* | `POST` | `experiment_id: int` | Generates a 1-Page Research Diagnostics Annex PDF for the specified experiment run. | **Exactly 1 Page** |
| `/api/v1/reports/unified/{backtest_id}/export`<br>*(alias: `/export/unified/{id}`)* | `GET` | `backtest_id: int` | Generates a Unified Dossier PDF (2 Pages without annex, up to 3 Pages when linked annex exists). Supports `?include_annex=true&experiment_id=<id>`. | **2 or 3 Pages** |

### Authorization & Multi-Tenant Isolation
- **Tenant Verification:** The backend verifies that the requested backtest or experiment belongs to `current_user.id` or that `current_user.role == "admin"`.
- **Anti-Enumeration Protection:** If a resource does not exist or belongs to another tenant, the endpoint returns `HTTP 404 Not Found` (never `403 Forbidden`), preventing malicious enumeration of resource IDs.
- **Fail-Closed Execution:** Authorization errors are never caught or converted into partial reports. Unauthenticated calls fail with `HTTP 401 Unauthorized`.

---

## 5. Physical PDF Pagination & Layout Verification

Unlike DOM-based screen tests, Gate D validates actual physical page counts parsed directly from rendered PDF byte streams using `pypdf.PdfReader`.

### Verification Results Across Fixtures

| Report Type | Fixture / Scenario | Rendered Size | Actual Physical Pages | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Strategy Fact Sheet** | Baseline Fact Sheet Payload | ~111 KB | **1 Page** | Passed |
| **Strategy Fact Sheet** | Worst-Case Fixture (Large Monthly Matrix, Multi-Asset Allocation, Warnings) | ~114 KB | **1 Page** | Passed |
| **Institutional Tear Sheet** | Baseline Tear Sheet Payload | ~151 KB | **2 Pages** | Passed |
| **Institutional Tear Sheet** | Worst-Case Fixture (Extreme Downsampling, Deep Drawdown, Full TCA) | ~153 KB | **2 Pages** | Passed |
| **Research Diagnostics Annex**| Baseline Research Diagnostics Payload | ~96 KB | **1 Page** | Passed |
| **Research Diagnostics Annex**| High Overfitting Fixture (100 Trials, Degraded OLS) | ~98 KB | **1 Page** | Passed |
| **Unified Institutional Report** | Fact Sheet + Tear Sheet (No Annex Linked) | ~156 KB | **2 Pages** | Passed |
| **Unified Institutional Report** | Complete Dossier (Tear Sheet + Research Annex Linked) | ~207 KB | **3 Pages** | Passed |

---

## 6. Frontend Integration

The frontend client in `frontend/src/api/client.ts` was extended with typed PDF blob download handlers:

- `exportStrategyFactSheetPdf(backtestId: number): Promise<Blob>`
- `exportInstitutionalTearSheetPdf(backtestId: number): Promise<Blob>`
- `exportResearchDiagnosticsAnnexPdf(experimentId: number, request: ResearchAnnexRequest): Promise<Blob>`
- `exportUnifiedInstitutionalReportPdf(backtestId: number, options?: { includeAnnex?: boolean; experimentId?: number }): Promise<Blob>`

In `frontend/src/components/reports/InstitutionalReportViewer.tsx`, an institutional **"📥 Export PDF"** button was added to the toolbar alongside the existing "🖨️ Print / Save as PDF" button. When clicked, the viewer triggers the authenticated backend PDF rendering endpoint, creates an ephemeral object URL (`URL.createObjectURL(blob)`), triggers a client-side download, and cleans up the URL.

---

## 7. Verification & Test Evidence

### Test Suite Results

1. **PDF Renderer & Template Engine Tests (`backend/tests/test_pdf_renderer.py`):**
   - 9 passed in 15.35s.
   - Covers: Chromium discovery, `%PDF-` signature validation, exact page counts (1, 2, 3), HTML escaping of malicious script tags, concurrent rendering safety across multiple threads, and timeout failure handling.
2. **Authenticated Export API Tests (`backend/tests/test_reporting_export_api.py`):**
   - 9 passed in 14.63s.
   - Covers: Authenticated PDF download, unauthenticated `401 Unauthorized` rejection, non-owner `404 Not Found` isolation, admin override authorization, nonexistent backtest handling, unified export with and without annex, Content-Disposition headers, and sanitized filenames.
3. **Full Stage 34 Backend Regression Suite:**
   - 53 passed across 5 test suites (`test_reporting_contracts.py`, `test_reporting_assembler.py`, `test_reporting_api.py`, `test_pdf_renderer.py`, `test_reporting_export_api.py`) in 33.95s.
4. **Full Frontend Test Suite:**
   - 88 passed across 5 test suites in 73.59s.
5. **Frontend Production Build:**
   - Vite 8 built successfully in 1.34s with zero compilation errors.
6. **Frontend Lint:**
   - `npm run lint` completed with 0 errors (52 pre-existing warnings in older modules).
7. **Git Whitespace & Formatting:**
   - `git diff --check` passed cleanly with exit code 0.

---

## 8. Runtime & Deployment Requirements

### Host Environment Requirements
- **Python:** 3.11+ with packages defined in `backend/pyproject.toml` (includes `pypdf>=6.21.0`).
- **Browser Binary:** Any modern Chromium-based binary:
  - Windows: Google Chrome (`C:\Program Files\Google\Chrome\Application\chrome.exe`) or Microsoft Edge (`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`).
  - Linux / Container: `chromium` or `chromium-browser` (`apt-get install -y chromium`).
  - Custom binary path can be explicitly configured via the `CHROME_BIN` environment variable.
- **Memory & CPU:** Bounded concurrency semaphore limits simultaneous browser invocations to 3 processes. Recommended allocation: $\ge 2$ CPU cores and $\ge 2\text{ GB}$ available RAM.

---

## 9. Security Assumptions & Operational Boundaries

1. **Local Browser Binary Trust:** The host environment is assumed to maintain an up-to-date, patched Chromium binary.
2. **Database Trust Boundary:** The PDF export endpoint retrieves canonical data from the application database. If the database itself is tampered with by a superuser, the report will reflect that state; Stage 32 cryptographic manifest digests ensure tampering is visible in the provenance footer.
3. **No Direct User HTML:** Under no circumstances should arbitrary HTML strings be passed to `render_html_to_pdf`. All HTML must originate from the strictly defined, escaped template functions in `pdf_templates.py`.

---

## 10. Status & Scope Boundary

- **Gate D Status:** IMPLEMENTED.
- **Stage 34 Status:** In Progress (Gates A, B, C accepted; Gate D implemented awaiting owner review; Gate E planned).
- **Gate E:** Has NOT been started.
