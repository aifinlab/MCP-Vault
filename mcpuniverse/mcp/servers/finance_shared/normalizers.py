"""Normalization helpers for finance MCP servers."""
from datetime import datetime

from .constants import DATE_FORMAT


def normalize_ticker(ticker: str) -> str:
    """Normalize ticker symbols while rejecting empty identifiers."""
    if not ticker or not ticker.strip():
        raise ValueError("ticker is required")
    return ticker.strip().upper()


def normalize_account_id(account_id: str) -> str:
    """Normalize account identifiers while rejecting empty identifiers."""
    if not account_id or not account_id.strip():
        raise ValueError("account_id is required")
    return account_id.strip().upper()


def parse_date(date_value: str) -> datetime:
    """Parse an ISO date used by finance data sources."""
    if not date_value or not date_value.strip():
        raise ValueError("date is required")
    return datetime.strptime(date_value.strip(), DATE_FORMAT)


def normalize_optional_date(date_value: str | None) -> str | None:
    """Normalize an optional ISO date and preserve explicit absence."""
    if date_value is None or date_value == "":
        return None
    parsed = parse_date(date_value)
    return parsed.strftime(DATE_FORMAT)


def round_money(value: float) -> float:
    """Round money values consistently for tool output."""
    return round(float(value), 2)
