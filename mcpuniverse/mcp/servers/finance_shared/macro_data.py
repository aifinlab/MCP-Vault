"""Live macro data helpers for finance MCP tools."""
import copy
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from .constants import (
    AKSHARE_PROVIDER_NAME,
    FINANCE_LIVE_CACHE_TTL_SECONDS_ENV,
    FINANCE_MACRO_DATA_PROVIDERS_ENV,
    FRED_API_KEY_ENV,
    FRED_PROVIDER_NAME,
)
from .errors import FinanceDataError, FinanceRecordNotFoundError
from .external_providers import akshare, fred
from .external_providers.common import fetch_json, payload_sha256
from .normalizers import normalize_optional_date, parse_date
from .schema import make_live_data_source

DEFAULT_MACRO_CACHE_TTL_SECONDS = 300
DEFAULT_MACRO_LOOKBACK_DAYS = 1825
_MACRO_FETCH_CACHE: dict[str, tuple[float, Any]] = {}


def search_macro_series(query: str = "", region: str = "") -> dict[str, Any]:
    """Search the configured macro series catalog."""
    query_text = (query or "").strip().lower()
    normalized_region = _normalize_region(region)
    series = []
    catalog = _macro_catalog()
    fred_search_results = _search_fred_series(query) if query_text and FRED_PROVIDER_NAME in _enabled_macro_providers() else {}
    for metadata in catalog.values():
        if normalized_region and metadata["region"] != normalized_region:
            continue
        candidate = fred_search_results.get(metadata["series_id"], metadata)
        haystack = f"{candidate['series_id']} {candidate['name']}".lower()
        if query_text and query_text not in haystack:
            continue
        series.append(copy.deepcopy(candidate))
    return {
        "query": query or "",
        "region": normalized_region,
        "series": sorted(series, key=lambda item: item["series_id"]),
    }


def get_macro_series(series_id: str, start_date: str, end_date: str) -> dict[str, Any]:
    """Return a live macro series between start_date and end_date."""
    normalized_series_id = _normalize_series_id(series_id)
    start = parse_date(start_date)
    end = parse_date(end_date)
    if end < start:
        raise ValueError("end_date must be on or after start_date")
    metadata = _macro_catalog()[normalized_series_id]
    provider_name = metadata["provider"]
    if provider_name == FRED_PROVIDER_NAME:
        payload = _fetch_fred_observations(normalized_series_id, start_date, end_date)
        series = fred.normalize_observations(normalized_series_id, payload, start_date, end_date)
    elif provider_name == AKSHARE_PROVIDER_NAME:
        payload = akshare.fetch_china_macro_payload(normalized_series_id)
        series = akshare.normalize_china_macro_series(normalized_series_id, payload, start_date, end_date)
    else:
        raise FinanceDataError(f"Unsupported macro data provider: {provider_name}")

    latest = series["observations"][-1]
    data_source = _macro_data_source(
        provider_name=provider_name,
        payload=payload,
        series_id=normalized_series_id,
        data_date=latest["date"],
    )
    series["latest"] = latest
    series["data_source"] = data_source
    return series


def get_macro_observation(series_id: str, as_of_date: str | None = None) -> dict[str, Any]:
    """Return the latest macro observation on or before as_of_date."""
    end_date = normalize_optional_date(as_of_date) or _today()
    start_date = _shift_date(end_date, -DEFAULT_MACRO_LOOKBACK_DAYS)
    series = get_macro_series(series_id=series_id, start_date=start_date, end_date=end_date)
    if not series["observations"]:
        raise FinanceRecordNotFoundError(f"No macro observation found for {series_id} on or before {end_date}")
    result = {
        "series_id": series["series_id"],
        "name": series["name"],
        "region": series["region"],
        "frequency": series["frequency"],
        "unit": series["unit"],
        "as_of_date": end_date,
        "observation": series["latest"],
        "data_source": series["data_source"],
    }
    return result


def clear_macro_data_cache() -> None:
    """Clear cached macro provider payloads."""
    _MACRO_FETCH_CACHE.clear()


def _macro_catalog() -> dict[str, dict[str, Any]]:
    providers = _enabled_macro_providers()
    catalog = {}
    if FRED_PROVIDER_NAME in providers:
        for series_id, metadata in fred.FRED_MACRO_SERIES.items():
            catalog[series_id] = {**metadata, "provider": FRED_PROVIDER_NAME}
    if AKSHARE_PROVIDER_NAME in providers:
        for series_id, metadata in akshare.AKSHARE_MACRO_SERIES.items():
            catalog[series_id] = {**metadata, "provider": AKSHARE_PROVIDER_NAME}
    return catalog


def _enabled_macro_providers() -> set[str]:
    raw_value = os.getenv(FINANCE_MACRO_DATA_PROVIDERS_ENV, f"{FRED_PROVIDER_NAME},{AKSHARE_PROVIDER_NAME}")
    providers = {item.strip().lower() for item in raw_value.split(",") if item.strip()}
    unknown = providers - {FRED_PROVIDER_NAME, AKSHARE_PROVIDER_NAME}
    if unknown:
        raise FinanceDataError(f"Unsupported finance macro data providers: {sorted(unknown)}")
    return providers


def _normalize_series_id(series_id: str) -> str:
    normalized = series_id.strip().upper() if series_id else ""
    if normalized not in _macro_catalog():
        raise FinanceRecordNotFoundError(f"Unsupported macro series_id: {series_id}")
    return normalized


def _normalize_region(region: str) -> str:
    normalized = (region or "").strip().upper()
    if normalized and normalized not in {"US", "CN", "HK"}:
        raise ValueError("region must be US, CN, HK, or empty")
    return normalized


def _fetch_fred_observations(series_id: str, start_date: str, end_date: str) -> dict[str, Any]:
    api_key = os.getenv(FRED_API_KEY_ENV, "").strip()
    if not api_key:
        raise FinanceDataError(f"{FRED_API_KEY_ENV} is required for FRED macro data")
    url = fred.series_observations_url(series_id, api_key, start_date, end_date)
    return _cached_fetch_json(url)


def _search_fred_series(query: str) -> dict[str, dict[str, Any]]:
    api_key = os.getenv(FRED_API_KEY_ENV, "").strip()
    if not api_key:
        return {}
    payload = _cached_fetch_json(fred.series_search_url(query, api_key))
    results = fred.normalize_search_results(payload, query, fred.FRED_MACRO_SERIES)
    return {record["series_id"]: record for record in results}


def _cached_fetch_json(url: str) -> Any:
    ttl_seconds = int(os.getenv(FINANCE_LIVE_CACHE_TTL_SECONDS_ENV, str(DEFAULT_MACRO_CACHE_TTL_SECONDS)))
    now = datetime.now(timezone.utc).timestamp()
    cached = _MACRO_FETCH_CACHE.get(url)
    if cached and ttl_seconds > 0 and now - cached[0] <= ttl_seconds:
        return copy.deepcopy(cached[1])
    payload = fetch_json(url)
    _MACRO_FETCH_CACHE[url] = (now, copy.deepcopy(payload))
    return payload


def _macro_data_source(provider_name: str, payload: Any, series_id: str, data_date: str) -> dict[str, Any]:
    return make_live_data_source(
        provider=provider_name,
        dataset="macro_series",
        data_date=data_date,
        series_id=series_id,
        payload_sha256=payload_sha256(payload),
    )


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _shift_date(date_value: str, days: int) -> str:
    return (parse_date(date_value) + timedelta(days=days)).date().isoformat()
