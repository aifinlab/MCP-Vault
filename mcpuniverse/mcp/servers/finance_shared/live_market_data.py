"""Live market data providers for finance MCP tools."""
import copy
import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from .constants import (
    AKSHARE_PROVIDER_NAME,
    BASE_CURRENCY,
    FINANCE_LIVE_CACHE_TTL_SECONDS_ENV,
    FINANCE_MARKET_DATA_PROVIDER_ENV,
    FMP_API_KEY_ENV,
    FMP_PROVIDER_NAME,
)
from .errors import FinanceDataError, FinanceRecordNotFoundError
from .external_providers import akshare, fmp
from .external_providers.common import fetch_json, payload_sha256
from .normalizers import normalize_optional_date, normalize_ticker, parse_date
from .schema import derive_live_data_source, make_live_data_source

DEFAULT_PRICE_LOOKBACK_DAYS = 14
DEFAULT_RISK_LOOKBACK_DAYS = 45
DEFAULT_LIVE_CACHE_TTL_SECONDS = 300
TRADING_DAYS_PER_YEAR = 252
FALLBACK_MARKET_BETA = 1.0
US_MARKET = "US"
US_CURRENCY = "USD"
US_EXCHANGE = ""
A_SHARE_EXCHANGE_BY_SUFFIX = {
    "SH": "SSE",
    "SZ": "SZSE",
}
US_TICKER_PATTERN = re.compile(r"^[A-Z][A-Z0-9-]{0,9}$")
A_SHARE_TICKER_PATTERN = re.compile(r"^\d{6}\.(SH|SZ)$")
HK_TICKER_PATTERN = re.compile(r"^\d{1,5}\.HK$")

_LIVE_FETCH_CACHE: dict[str, tuple[float, Any]] = {}


class FMPMarketDataProvider:
    """Fetch live market data from Financial Modeling Prep."""

    provider_name = FMP_PROVIDER_NAME

    def __init__(self, api_key: str):
        if not api_key or not api_key.strip():
            raise FinanceDataError(f"{FMP_API_KEY_ENV} is required when finance live mode uses FMP")
        self._api_key = api_key.strip()

    def get_market_price(self, ticker: str, as_of_date: str | None = None) -> dict[str, Any]:
        """Return the latest FMP close on or before the requested date."""
        ticker = normalize_ticker(ticker)
        end_date = normalize_optional_date(as_of_date) or _today()
        start_date = _shift_date(end_date, -DEFAULT_PRICE_LOOKBACK_DAYS)
        history = self.get_price_history(ticker, start_date, end_date)
        candidates = [
            copy.deepcopy(record)
            for record in history["prices"]
            if parse_date(record["date"]) <= parse_date(end_date)
        ]
        if not candidates:
            raise FinanceRecordNotFoundError(f"No live price record found for {ticker} on or before {end_date}")
        selected = max(candidates, key=lambda record: record["date"])
        data_source = _derive_data_source(
            history["data_source"],
            dataset="market_price",
            data_date=selected["date"],
            ticker=ticker,
        )
        selected["ticker"] = ticker
        selected["currency"] = history["currency"]
        selected["data_source"] = data_source
        return selected

    def get_price_history(self, ticker: str, start_date: str, end_date: str) -> dict[str, Any]:
        """Return inclusive FMP historical close records."""
        ticker = normalize_ticker(ticker)
        start = parse_date(start_date)
        end = parse_date(end_date)
        if end < start:
            raise ValueError("end_date must be on or after start_date")
        url = fmp.historical_price_url(ticker, self._api_key, start_date, end_date)
        payload = _cached_fetch_json(url)
        prices = fmp.normalize_historical_prices(ticker, payload, start_date, end_date)
        if not prices:
            raise FinanceRecordNotFoundError(f"No live price records found for {ticker} between {start_date} and {end_date}")
        latest_date = max(record["date"] for record in prices)
        data_source = _data_source(
            self.provider_name,
            payload,
            dataset="historical_prices",
            data_date=latest_date,
            ticker=ticker,
        )
        return {
            "ticker": ticker,
            "currency": BASE_CURRENCY,
            "prices": prices,
            "data_source": data_source,
        }

    def get_company_fundamentals(self, ticker: str) -> dict[str, Any]:
        """Return normalized FMP profile, statement, and valuation data."""
        ticker = normalize_ticker(ticker)
        payload = {
            "profile": _cached_fetch_json(fmp.profile_url(ticker, self._api_key)),
            "income_statement": _cached_fetch_json(fmp.income_statement_url(ticker, self._api_key)),
            "balance_sheet_statement": _cached_fetch_json(fmp.balance_sheet_statement_url(ticker, self._api_key)),
            "ratios": _cached_fetch_json(fmp.ratios_url(ticker, self._api_key)),
        }
        company = fmp.normalize_company_record(ticker, payload, _today())
        data_source = _data_source(
            self.provider_name,
            payload,
            dataset="company_fundamentals",
            data_date=_today(),
            ticker=ticker,
        )
        company["ticker"] = ticker
        company["data_source"] = data_source
        return company

    def get_live_ticker_risk(self, ticker: str) -> dict[str, Any]:
        """Derive basic risk inputs from recent live price history."""
        ticker = normalize_ticker(ticker)
        end_date = _today()
        start_date = _shift_date(end_date, -DEFAULT_RISK_LOOKBACK_DAYS)
        history = self.get_price_history(ticker, start_date, end_date)
        prices = [float(record["close"]) for record in history["prices"]]
        returns = [
            prices[index] / prices[index - 1] - 1.0
            for index in range(1, len(prices))
            if prices[index - 1] > 0
        ]
        if len(returns) < 2:
            raise FinanceRecordNotFoundError(f"Not enough live prices to derive risk for ticker {ticker}")

        mean_return = sum(returns) / len(returns)
        variance = sum((value - mean_return) ** 2 for value in returns) / (len(returns) - 1)
        annual_volatility = (variance ** 0.5) * (TRADING_DAYS_PER_YEAR ** 0.5)
        company = self.get_company_fundamentals(ticker)
        market_beta = _sector_beta(company.get("sector", ""))
        data_source = _derive_data_source(
            history["data_source"],
            dataset="derived_ticker_risk",
            data_date=history["data_source"]["data_date"],
            ticker=ticker,
        )
        return {
            "ticker": ticker,
            "annual_volatility": round(annual_volatility, 4),
            "market_beta": market_beta,
            "factors": {
                "market_beta": market_beta,
                "size": 0.0,
                "value": 0.0,
                "momentum": 0.0,
            },
            "data_source": data_source,
        }


class AKShareMarketDataProvider:
    """Fetch live China A-share and Hong Kong market data from AKShare."""

    provider_name = AKSHARE_PROVIDER_NAME

    def __init__(self, instrument: dict[str, Any] | None = None):
        self._instrument = copy.deepcopy(instrument or {})

    def get_market_price(self, ticker: str, as_of_date: str | None = None) -> dict[str, Any]:
        """Return the latest AKShare A-share close on or before the requested date."""
        ticker = normalize_ticker(ticker)
        end_date = normalize_optional_date(as_of_date) or _today()
        start_date = _shift_date(end_date, -DEFAULT_PRICE_LOOKBACK_DAYS)
        history = self.get_price_history(ticker, start_date, end_date)
        candidates = [
            copy.deepcopy(record)
            for record in history["prices"]
            if parse_date(record["date"]) <= parse_date(end_date)
        ]
        if not candidates:
            raise FinanceRecordNotFoundError(f"No live price record found for {ticker} on or before {end_date}")
        selected = max(candidates, key=lambda record: record["date"])
        data_source = _derive_data_source(
            history["data_source"],
            dataset="market_price",
            data_date=selected["date"],
            ticker=ticker,
        )
        selected["ticker"] = ticker
        selected["currency"] = history["currency"]
        selected["market"] = history["market"]
        selected["exchange"] = history["exchange"]
        selected["provider_symbol"] = akshare.provider_symbol(ticker, self._instrument)
        selected["data_source"] = data_source
        return selected

    def get_price_history(self, ticker: str, start_date: str, end_date: str) -> dict[str, Any]:
        """Return inclusive AKShare A-share historical close records."""
        ticker = normalize_ticker(ticker)
        start = parse_date(start_date)
        end = parse_date(end_date)
        if end < start:
            raise ValueError("end_date must be on or after start_date")
        payload = akshare.fetch_equity_price_payload(ticker, start_date, end_date, self._instrument)
        prices = akshare.normalize_historical_prices(ticker, payload, start_date, end_date)
        if not prices:
            raise FinanceRecordNotFoundError(f"No live price records found for {ticker} between {start_date} and {end_date}")
        latest_date = max(record["date"] for record in prices)
        data_source = _data_source(
            self.provider_name,
            payload,
            dataset="historical_prices",
            data_date=latest_date,
            ticker=ticker,
        )
        return {
            "ticker": ticker,
            "currency": payload.get("currency", self._instrument.get("currency", akshare.CN_CURRENCY)),
            "market": payload.get("market", self._instrument.get("market", akshare.CN_MARKET)),
            "exchange": payload.get("exchange", self._instrument.get("exchange", "")),
            "provider_symbol": akshare.provider_symbol(ticker, self._instrument),
            "prices": prices,
            "data_source": data_source,
        }

    def get_company_fundamentals(self, ticker: str) -> dict[str, Any]:
        """Return normalized AKShare company metadata."""
        ticker = normalize_ticker(ticker)
        end_date = _today()
        payload = akshare.fetch_equity_profile_payload(ticker, self._instrument)
        company = akshare.normalize_company_record(ticker, payload, end_date, self._instrument)
        data_source = _data_source(
            self.provider_name,
            payload,
            dataset="company_profile",
            data_date=end_date,
            ticker=ticker,
        )
        company["ticker"] = ticker
        company["data_source"] = data_source
        return company

    def get_live_ticker_risk(self, ticker: str) -> dict[str, Any]:
        """Derive basic A-share risk inputs from recent live price history."""
        ticker = normalize_ticker(ticker)
        end_date = _today()
        start_date = _shift_date(end_date, -DEFAULT_RISK_LOOKBACK_DAYS)
        history = self.get_price_history(ticker, start_date, end_date)
        prices = [float(record["close"]) for record in history["prices"]]
        returns = [
            prices[index] / prices[index - 1] - 1.0
            for index in range(1, len(prices))
            if prices[index - 1] > 0
        ]
        if len(returns) < 2:
            raise FinanceRecordNotFoundError(f"Not enough live prices to derive risk for ticker {ticker}")

        mean_return = sum(returns) / len(returns)
        variance = sum((value - mean_return) ** 2 for value in returns) / (len(returns) - 1)
        annual_volatility = (variance ** 0.5) * (TRADING_DAYS_PER_YEAR ** 0.5)
        data_source = _derive_data_source(
            history["data_source"],
            dataset="derived_ticker_risk",
            data_date=history["data_source"]["data_date"],
            ticker=ticker,
        )
        return {
            "ticker": ticker,
            "annual_volatility": round(annual_volatility, 4),
            "market_beta": FALLBACK_MARKET_BETA,
            "factors": {
                "market_beta": FALLBACK_MARKET_BETA,
                "size": 0.0,
                "value": 0.0,
                "momentum": 0.0,
            },
            "data_source": data_source,
        }


def resolve_ticker_route(ticker: str) -> dict[str, str]:
    """Resolve ticker syntax to an internal live data provider route."""
    normalized_ticker = normalize_ticker(ticker)
    if A_SHARE_TICKER_PATTERN.fullmatch(normalized_ticker):
        suffix = normalized_ticker.rsplit(".", 1)[1]
        return {
            "ticker": normalized_ticker,
            "provider": AKSHARE_PROVIDER_NAME,
            "market": akshare.CN_MARKET,
            "exchange": A_SHARE_EXCHANGE_BY_SUFFIX[suffix],
            "currency": akshare.CN_CURRENCY,
            "provider_symbol": normalized_ticker.split(".", 1)[0],
            "product_type": "equity",
        }
    if HK_TICKER_PATTERN.fullmatch(normalized_ticker):
        symbol = normalized_ticker.split(".", 1)[0].zfill(akshare.HK_SYMBOL_LENGTH)
        return {
            "ticker": normalized_ticker,
            "provider": AKSHARE_PROVIDER_NAME,
            "market": akshare.HK_MARKET,
            "exchange": "HKEX",
            "currency": akshare.HK_CURRENCY,
            "provider_symbol": symbol,
            "product_type": "equity",
        }
    if US_TICKER_PATTERN.fullmatch(normalized_ticker):
        provider_name = os.getenv(FINANCE_MARKET_DATA_PROVIDER_ENV, FMP_PROVIDER_NAME).strip().lower()
        if provider_name != FMP_PROVIDER_NAME:
            raise FinanceDataError(f"Unsupported finance market data provider for US ticker {normalized_ticker}: {provider_name}")
        return {
            "ticker": normalized_ticker,
            "provider": FMP_PROVIDER_NAME,
            "market": US_MARKET,
            "exchange": US_EXCHANGE,
            "currency": US_CURRENCY,
            "provider_symbol": normalized_ticker,
            "product_type": "equity",
        }
    raise FinanceDataError(f"Unsupported ticker format for live finance data: {ticker}")


def get_live_market_data_provider(ticker: str | None = None):
    """Return the configured live market data provider."""
    route = resolve_ticker_route(ticker) if ticker else {}
    provider_name = route.get("provider") or os.getenv(FINANCE_MARKET_DATA_PROVIDER_ENV, FMP_PROVIDER_NAME).strip().lower()
    if provider_name == FMP_PROVIDER_NAME:
        return FMPMarketDataProvider(api_key=os.getenv(FMP_API_KEY_ENV, ""))
    if provider_name == AKSHARE_PROVIDER_NAME:
        return AKShareMarketDataProvider(instrument=route)
    raise FinanceDataError(f"Unsupported finance market data provider: {provider_name}")


def clear_live_market_data_cache() -> None:
    """Clear cached live provider payloads."""
    _LIVE_FETCH_CACHE.clear()


def _cached_fetch_json(url: str) -> Any:
    ttl_seconds = int(os.getenv(FINANCE_LIVE_CACHE_TTL_SECONDS_ENV, str(DEFAULT_LIVE_CACHE_TTL_SECONDS)))
    now = time.time()
    cached = _LIVE_FETCH_CACHE.get(url)
    if cached and ttl_seconds > 0 and now - cached[0] <= ttl_seconds:
        return copy.deepcopy(cached[1])
    payload = fetch_json(url)
    _LIVE_FETCH_CACHE[url] = (now, copy.deepcopy(payload))
    return payload


def _data_source(provider_name: str, payload: Any, dataset: str, data_date: str, ticker: str | None = None) -> dict[str, Any]:
    return make_live_data_source(
        provider=provider_name,
        dataset=dataset,
        data_date=data_date,
        ticker=ticker or "",
        payload_sha256=payload_sha256(payload),
    )


def _derive_data_source(source: dict[str, Any], dataset: str, data_date: str, ticker: str | None = None) -> dict[str, Any]:
    return derive_live_data_source(source, dataset=dataset, data_date=data_date, ticker=ticker or "")


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _shift_date(date_value: str, days: int) -> str:
    return (parse_date(date_value) + timedelta(days=days)).date().isoformat()


def _sector_beta(sector: str) -> float:
    sector_key = sector.strip().lower()
    if "technology" in sector_key:
        return 1.15
    if "financial" in sector_key:
        return 1.05
    if "consumer" in sector_key:
        return 1.0
    if "utility" in sector_key or "staples" in sector_key:
        return 0.75
    return FALLBACK_MARKET_BETA
