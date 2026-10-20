# Initial API Contract

All routes are prefixed with `/api/v1`.

## GET /health
Returns service status.

## POST /market-data/preview
Multipart form field: `file`
Returns validation summary and row-level issues without registering the dataset.

## POST /market-data/uploads
Multipart form field: `file`
Validates and registers valid rows in memory. Returns `dataset_id`, row counts, warnings and errors. If there are no valid rows, returns a client error.

## POST /market-data/datasets/query
JSON body:
```json
{
  "dataset_id": "dataset-id",
  "start_date": "2025-01-01",
  "end_date": "2025-12-31",
  "tickers": ["AAPL", "MSFT"],
  "market": "US"
}
```
Dates are inclusive. `tickers` and `market` are optional filters.

## GET /market-data/datasets/{dataset_id}
Returns metadata and validation summary for a registered dataset.

## Error shape

FastAPI's validation error shape may apply to malformed request bodies. Application-level errors should be clear and should not contain stack traces or secrets.
