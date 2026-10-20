# Quant Portfolio Engine — Development Starter

A staged, API-first quantitative finance project. This starter deliberately implements **Stage 1: Market Data Engine foundation** only. The broader portfolio optimization roadmap is documented, but optimization, financial metrics, backtesting, and the frontend are intentionally deferred until the data foundation is accepted.

## Current scope

- Python 3.11+
- FastAPI + Pydantic
- CSV-first ingestion for US and PSX market identifiers
- Required columns: `date,ticker,market,close,currency`
- Optional columns: `open,high,low,adjusted_close,volume`
- Custom inclusive date-range filtering
- Validation report with errors and warnings
- In-memory dataset registry and bounded TTL cache (development-only)
- Pytest starter tests and API docs

> This is a development scaffold, not a production-ready financial system. In-memory datasets/cache are lost on restart. PostgreSQL, authentication, external data vendors, portfolio calculations, optimization, and UI are later stages.

## Quick start (Windows PowerShell)

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

If `py` is unavailable, use `uv` or the Python executable installed on your machine:

```powershell
# Using uv (fastest on Windows)
uv venv .venv --python 3.11
.\.venv\Scripts\Activate.ps1

# Or using standard python
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Open:
- API docs: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/api/v1/health

Run tests:

```powershell
pytest -q
```

## CSV format

```csv
date,ticker,market,close,currency,adjusted_close,volume
2025-01-02,AAPL,US,243.85,USD,243.85,1200000
2025-01-02,ABC,PSX,125.50,PKR,125.50,250000
```

The values above are illustrative examples only, not current or investment data. For this starter, dates are parsed as dates, prices must be positive, volume must be non-negative, and duplicate `(date, market, ticker)` keys are reported.

## Initial API endpoints

- `GET /api/v1/health`
- `POST /api/v1/market-data/preview` — validate an uploaded CSV and return a report
- `POST /api/v1/market-data/uploads` — validate and register a dataset in memory
- `POST /api/v1/market-data/datasets/query` — filter a registered dataset by tickers and inclusive date range
- `GET /api/v1/market-data/datasets/{dataset_id}` — retrieve dataset metadata

All uploaded data should be treated as untrusted. Enforce deployment-level request limits before exposing this service publicly.

## Development principles

1. Inspect and preserve existing code before integrating this scaffold into another repository.
2. Add tests with every behavior change.
3. Keep market-data code independent from API routes.
4. Never silently fabricate missing market prices.
5. Record validation outcomes and warnings.
6. Use consistent market, currency, timezone, and date conventions.
7. Do not implement portfolio optimization until the Market Data Engine is tested and accepted.

## Roadmap

See `docs/MASTER_PLAN.md` for the full staged delivery plan and `docs/STAGE_1_SPEC.md` for the implementation contract.
