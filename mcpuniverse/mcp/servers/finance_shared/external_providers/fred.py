"""FRED provider adapter for live macro data."""
from typing import Any
from urllib.parse import urlencode

from mcpuniverse.mcp.servers.finance_shared.normalizers import parse_date

PROVIDER_NAME = "fred"
FRED_SEARCH_URL = "https://api.stlouisfed.org/fred/series/search"
FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"

FRED_MACRO_SERIES = {
    "FEDFUNDS": {
        "series_id": "FEDFUNDS",
        "name": "Federal Funds Effective Rate",
        "region": "US",
        "frequency": "monthly",
        "unit": "percent",
    },
    "CPIAUCSL": {
        "series_id": "CPIAUCSL",
        "name": "Consumer Price Index for All Urban Consumers",
        "region": "US",
        "frequency": "monthly",
        "unit": "index",
    },
    "UNRATE": {
        "series_id": "UNRATE",
        "name": "Unemployment Rate",
        "region": "US",
        "frequency": "monthly",
        "unit": "percent",
    },
    "DGS10": {
        "series_id": "DGS10",
        "name": "Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity",
        "region": "US",
        "frequency": "daily",
        "unit": "percent",
    },
    "T10Y2Y": {
        "series_id": "T10Y2Y",
        "name": "10-Year Treasury Constant Maturity Minus 2-Year Treasury Constant Maturity",
        "region": "US",
        "frequency": "daily",
        "unit": "percent",
    },
}


def series_search_url(search_text: str, api_key: str) -> str:
    """Return a FRED series search URL."""
    return _provider_url(
        FRED_SEARCH_URL,
        {
            "search_text": search_text,
            "api_key": api_key,
            "file_type": "json",
        },
    )


def series_observations_url(series_id: str, api_key: str, start_date: str, end_date: str) -> str:
    """Return a FRED series observations URL."""
    normalized_series_id = normalize_series_id(series_id)
    return _provider_url(
        FRED_OBSERVATIONS_URL,
        {
            "series_id": normalized_series_id,
            "api_key": api_key,
            "file_type": "json",
            "observation_start": start_date,
            "observation_end": end_date,
        },
    )


def normalize_search_results(payload: dict[str, Any], query: str, allowed_series: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize FRED search results into macro series metadata."""
    query_text = query.strip().lower()
    allowed_ids = set(allowed_series)
    results = []
    for record in payload.get("seriess", []):
        series_id = str(record.get("id", "")).upper()
        if series_id not in allowed_ids:
            continue
        name = str(record.get("title") or allowed_series[series_id]["name"])
        if query_text and query_text not in f"{series_id} {name}".lower():
            continue
        metadata = allowed_series[series_id]
        results.append({
            "series_id": series_id,
            "name": name,
            "region": metadata["region"],
            "frequency": metadata["frequency"],
            "unit": metadata["unit"],
            "provider": PROVIDER_NAME,
        })
    return results


def normalize_observations(series_id: str, payload: dict[str, Any], start_date: str, end_date: str) -> dict[str, Any]:
    """Normalize FRED observations into the common macro shape."""
    normalized_series_id = normalize_series_id(series_id)
    metadata = FRED_MACRO_SERIES[normalized_series_id]
    start = parse_date(start_date)
    end = parse_date(end_date)
    if end < start:
        raise ValueError("end_date must be on or after start_date")
    observations = []
    for observation in payload.get("observations", []):
        date_value = observation["date"]
        parsed_date = parse_date(date_value)
        if not start <= parsed_date <= end:
            continue
        raw_value = observation.get("value")
        if raw_value in (None, ".", ""):
            continue
        observations.append({
            "date": date_value,
            "value": float(raw_value),
        })
    if not observations:
        raise ValueError(f"No FRED observations found for {normalized_series_id} between {start_date} and {end_date}")
    return {
        "series_id": normalized_series_id,
        "name": metadata["name"],
        "region": metadata["region"],
        "frequency": metadata["frequency"],
        "unit": metadata["unit"],
        "observations": observations,
    }


def normalize_series_id(series_id: str) -> str:
    """Normalize and validate a FRED series id."""
    normalized = series_id.strip().upper() if series_id else ""
    if normalized not in FRED_MACRO_SERIES:
        raise ValueError(f"Unsupported FRED macro series_id: {series_id}")
    return normalized


def _provider_url(base_url: str, params: dict[str, Any]) -> str:
    return f"{base_url}?{urlencode(params)}"
