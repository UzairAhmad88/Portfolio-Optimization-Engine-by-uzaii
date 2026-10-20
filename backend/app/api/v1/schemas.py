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
    point_in_time_status: str = Field(
        default="unverified_legacy", description="Point-in-time verification certification status"
    )
    calendar_version: str | None = Field(
        default=None, description="Exchange calendar version applied to dataset"
    )
    adjustment_policy_version: str | None = Field(
        default=None, description="Corporate action adjustment policy version"
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


class CorporateActionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: str | None = Field(default=None, description="Associated dataset UUID")
    asset_id: str = Field(description="Stable economic asset identifier")
    ticker: str = Field(description="Security ticker symbol")
    market: str = Field(pattern="^(US|PSX)$", description="Market identifier")
    event_type: str = Field(description="Type: stock_split, reverse_split, cash_dividend, symbol_change, complex_unsupported")
    effective_date: date = Field(description="Economic effective date")
    announcement_date: date | None = Field(default=None, description="Filing/announcement date for PIT cutoff")
    ex_date: date | None = Field(default=None, description="Ex-dividend/split date")
    record_date: date | None = Field(default=None, description="Record date")
    payment_date: date | None = Field(default=None, description="Payment date")
    value: float = Field(gt=0, description="Event magnitude (split ratio or dividend per share)")
    currency: str = Field(min_length=3, max_length=3, description="Currency code (USD, PKR)")
    source: str = Field(default="researcher_upload", description="Data provenance/source identifier")
    revision_id: str | None = Field(default=None, description="Revision or correction hash")
    is_point_in_time_verified: bool = Field(default=False, description="Whether announcement date is verified")
    provenance_metadata: dict[str, Any] | None = Field(default=None, description="Additional provenance audit fields")


class CorporateActionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    dataset_id: str | None
    asset_id: str
    ticker: str
    market: str
    event_type: str
    effective_date: str
    announcement_date: str | None
    ex_date: str | None
    record_date: str | None
    payment_date: str | None
    value: float
    currency: str
    source: str
    revision_id: str | None
    status: str
    is_point_in_time_verified: bool
    created_at: str


class QualityAuditResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy_version: str
    is_valid: bool
    total_findings: int
    error_count: int
    warning_count: int
    info_count: int
    findings: list[dict[str, Any]]


class ExchangeCalendarResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    market: str
    calendar_id: str
    version: str
    timezone: str
    sessions: list[str]
    holidays: list[dict[str, str]]
