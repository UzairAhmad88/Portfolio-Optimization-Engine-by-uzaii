"""
Provider-neutral market data adapter interfaces and capability declarations.

Workstream 31.2:
- Decouples the quant engine from specific external vendor schemas.
- Explicit provider capability matrix (raw prices, adjusted close, splits, dividends, announcement timestamps, revisions).
- Never claims complete historical coverage or point-in-time capabilities without verified evidence.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.market_data.corporate_actions import CorporateActionEvent


@dataclass(frozen=True)
class ProviderCapabilities:
    """
    Explicit declared capabilities and coverage limits of a market data provider.
    """
    provider_name: str
    supports_raw_ohlcv: bool = True
    supports_provider_adj_close: bool = False
    supports_splits: bool = False
    supports_dividends: bool = False
    supports_symbol_changes: bool = False
    supports_announcement_timestamps: bool = False  # Crucial for strict Point-in-Time safety
    supports_source_revisions: bool = False
    coverage_markets: list[str] = field(default_factory=lambda: ["US", "PSX"])
    licensing_mode: str = "proprietary_research"
    notes: str = ""


class MarketDataProviderAdapter(ABC):
    """
    Provider-neutral interface for market data ingestion.
    """

    def __init__(self, provider_id: str, capabilities: ProviderCapabilities) -> None:
        self.provider_id = provider_id
        self.capabilities = capabilities

    @abstractmethod
    def fetch_price_bars(
        self,
        ticker: str,
        market: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """
        Fetches price observations for the given asset and date range.
        Must return list of dicts with at minimum:
        {'date': date, 'ticker': str, 'market': str, 'close': float, 'currency': str, ...}
        """
        pass

    @abstractmethod
    def fetch_corporate_actions(
        self,
        ticker: str,
        market: str,
        start_date: date,
        end_date: date,
    ) -> list[CorporateActionEvent]:
        """
        Fetches corporate action events for the given asset and date range.
        """
        pass


class CSVUploadAdapter(MarketDataProviderAdapter):
    """
    Adapter representing market data ingested via user-provided CSV upload.
    Explicitly documents that CSV files provide raw bars and optional provider adjusted closes,
    but cannot guarantee strict point-in-time announcement timestamps unless explicitly provided.
    """

    def __init__(self) -> None:
        caps = ProviderCapabilities(
            provider_name="csv_upload",
            supports_raw_ohlcv=True,
            supports_provider_adj_close=True,
            supports_splits=True,
            supports_dividends=True,
            supports_symbol_changes=False,
            supports_announcement_timestamps=False,  # Unless explicit announcement_date column is supplied
            supports_source_revisions=False,
            coverage_markets=["US", "PSX"],
            licensing_mode="user_supplied",
            notes="User-provided CSV uploads. Strict PIT verification requires explicit announcement_date metadata.",
        )
        super().__init__(provider_id="csv_upload", capabilities=caps)

    def fetch_price_bars(
        self,
        ticker: str,
        market: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        # CSV ingestion is handled via service.register_dataset
        return []

    def fetch_corporate_actions(
        self,
        ticker: str,
        market: str,
        start_date: date,
        end_date: date,
    ) -> list[CorporateActionEvent]:
        return []
