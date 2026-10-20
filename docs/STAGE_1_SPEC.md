# Stage 1 Specification — Market Data Engine

## Goal

Convert raw historical price CSVs into validated, standardized datasets that later quantitative modules can consume.

## In scope

- CSV upload and preview
- Required and optional schema
- US and PSX market identifiers
- Custom inclusive date-range queries
- Data-quality errors and warnings
- Dataset metadata and in-memory registration
- Small bounded in-process TTL cache
- API docs and tests

## Out of scope

- Automated internet downloads or vendor APIs
- Live or intraday feeds
- PostgreSQL persistence
- Financial returns or risk calculations
- Portfolio optimization or recommendations
- Authentication and multi-tenant permissions
- Frontend dashboard

## Canonical schema

Required:
- `date`: parseable date, normalized to ISO date
- `ticker`: non-empty normalized string
- `market`: `US` or `PSX`
- `close`: positive numeric value
- `currency`: non-empty uppercase currency code

Optional:
- `open`, `high`, `low`, `adjusted_close`: positive numeric when supplied
- `volume`: non-negative numeric when supplied

## Validation policy

- Missing required columns: reject dataset.
- Unparseable dates: report row-level error.
- Unsupported market: report row-level error.
- Non-positive price: report row-level error.
- Negative volume: report row-level error.
- Duplicate `(date, market, ticker)`: report duplicate rows; do not silently choose a row.
- OHLC consistency: where all relevant fields are present, flag impossible high/low relationships.
- Missing optional fields: warning, not automatic imputation.
- Date range: start date must be <= end date; filter inclusively.
- Invalid rows are excluded from the normalized valid dataset and are included in the validation report.
- The API must not expose server tracebacks to clients.

## Cache policy

The starter uses a bounded, process-local TTL cache for preview/query responses. Cache keys must include file content and query parameters. This is not a distributed cache and is not durable. Cache invalidation and maximum entries/TTL must be configurable.

## Dataset persistence

This starter registers datasets in process memory only. Dataset IDs may become unavailable after a restart. PostgreSQL and durable object storage are deferred to a later stage.

## Acceptance criteria

1. Valid CSV uploads return a dataset ID and metadata.
2. Invalid schemas return a clear 4xx response.
3. Row-level issues identify row numbers and reasons.
4. Date filtering is inclusive.
5. Unsupported markets and invalid prices are not accepted as valid rows.
6. API schema is available through `/docs`.
7. Automated tests cover success and common failures.
8. README explains local setup and known limitations.
