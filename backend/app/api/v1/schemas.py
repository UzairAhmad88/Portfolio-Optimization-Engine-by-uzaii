from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = Field(
        description="Operational status of the service", examples=["ok"]
    )
    stage: str = Field(
        description="Active development milestone stage",
        examples=["persistent-storage"],
    )
    database: str = Field(
        default="connected",
        description="Operational database connectivity status",
        examples=["connected", "unreachable"],
    )


class RowIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    row: int = Field(
        description="1-based row number in the original CSV file", examples=[2]
    )
    reasons: list[str] = Field(description="List of failure reasons for this row")


class ValidationWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(
        description="Informational warning regarding dataset structure or contents"
    )


class ValidationReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_sha256: str = Field(
        description="SHA-256 cryptographic hash of raw uploaded file content"
    )
    rows_examined: int = Field(
        description="Total number of data rows parsed from the CSV"
    )
    valid_rows: int = Field(description="Number of accepted valid price bars")
    rejected_rows: int = Field(description="Number of rejected invalid price bars")
    errors: list[RowIssue] = Field(
        description="Catalog of row-level errors and exclusion causes"
    )
    warnings: list[ValidationWarning] = Field(
        description="Catalog of non-blocking schema and data quality warnings"
    )
    valid_data: list[dict[str, Any]] | None = Field(
        default=None,
        description="List of normalized valid market data records (provided in preview mode)",
    )


class DatasetMetadataResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: str = Field(
        description="Unique UUIDv4 identifier for the registered dataset"
    )
    filename: str = Field(description="Original uploaded file name")
    created_at: str = Field(description="UTC ISO-8601 creation timestamp")
    content_sha256: str = Field(
        description="SHA-256 cryptographic hash of raw uploaded file content"
    )
    rows_examined: int = Field(
        description="Total number of data rows parsed from the CSV"
    )
    valid_rows: int = Field(
        description="Number of accepted valid price bars stored in memory"
    )
    rejected_rows: int = Field(description="Number of rejected invalid price bars")
    errors: list[RowIssue] = Field(
        description="Catalog of row-level errors and exclusion causes"
    )
    warnings: list[ValidationWarning] = Field(
        description="Catalog of non-blocking schema and data quality warnings"
    )
    user_id: str | None = Field(
        default=None, description="Owner user ID if dataset is privately owned"
    )
    is_shared: bool = Field(
        default=False, description="Whether the dataset is shared with all researchers"
    )


class DatasetQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: str = Field(
        description="Unique UUIDv4 identifier of the registered dataset"
    )
    start_date: date = Field(description="Inclusive start date (ISO-8601 YYYY-MM-DD)")
    end_date: date = Field(description="Inclusive end date (ISO-8601 YYYY-MM-DD)")
    tickers: list[str] | None = Field(
        default=None, description="Optional list of ticker symbols to filter"
    )
    market: str | None = Field(
        default=None,
        pattern="^(US|PSX)$",
        description="Optional market identifier to filter ('US' or 'PSX')",
    )


class DatasetQueryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: str = Field(description="UUIDv4 identifier of the queried dataset")
    start_date: str = Field(description="Inclusive query start date (YYYY-MM-DD)")
    end_date: str = Field(description="Inclusive query end date (YYYY-MM-DD)")
    row_count: int = Field(description="Number of matching price bars returned")
    data: list[dict[str, Any]] = Field(
        description="List of filtered market data records"
    )


class ErrorResponse(BaseModel):
    detail: Any = Field(
        description="Error message or structured validation failure details"
    )


class DatasetAssetsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: str = Field(description="UUIDv4 identifier of the queried dataset")
    asset_count: int = Field(description="Total number of unique assets in the dataset")
    assets: list[dict[str, Any]] = Field(
        description="List of verified asset metadata objects"
    )
