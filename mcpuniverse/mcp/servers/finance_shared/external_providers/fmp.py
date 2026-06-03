"""Financial Modeling Prep provider adapter for live finance data."""
from typing import Any
from urllib.parse import urlencode

from mcpuniverse.mcp.servers.finance_shared.normalizers import normalize_ticker, parse_date

PROVIDER_NAME = "fmp"
FMP_BASE_URL = "https://financialmodelingprep.com/stable"


def historical_price_url(ticker: str, api_key: str, start_date: str, end_date: str) -> str:
    """Return a FMP historical end-of-day price URL."""
    return _provider_url(
        "historical-price-eod/full",
        {
            "symbol": normalize_ticker(ticker),
            "from": start_date,
            "to": end_date,
            "apikey": api_key,
        },
    )


def profile_url(ticker: str, api_key: str) -> str:
    """Return a FMP company profile URL."""
    return _provider_url("profile", {"symbol": normalize_ticker(ticker), "apikey": api_key})


def income_statement_url(ticker: str, api_key: str) -> str:
    """Return a FMP annual income statement URL."""
    return _provider_url(
        "income-statement",
        {"symbol": normalize_ticker(ticker), "period": "annual", "limit": 1, "apikey": api_key},
    )


def balance_sheet_statement_url(ticker: str, api_key: str) -> str:
    """Return a FMP annual balance sheet statement URL."""
    return _provider_url(
        "balance-sheet-statement",
        {"symbol": normalize_ticker(ticker), "period": "annual", "limit": 1, "apikey": api_key},
    )


def ratios_url(ticker: str, api_key: str) -> str:
    """Return a FMP annual ratios URL."""
    return _provider_url(
        "ratios",
        {"symbol": normalize_ticker(ticker), "period": "annual", "limit": 1, "apikey": api_key},
    )


def normalize_historical_prices(
        ticker: str,
        payload: dict[str, Any] | list[dict[str, Any]],
        start_date: str,
        end_date: str
) -> list[dict[str, Any]]:
    """Normalize FMP historical prices into the finance market-data shape."""
    ticker = normalize_ticker(ticker)
    start = parse_date(start_date)
    end = parse_date(end_date)
    if end < start:
        raise ValueError("end_date must be on or after start_date")

    records = []
    for price_record in _records_from_payload(payload, "historical"):
        date_value = price_record["date"]
        parsed_date = parse_date(date_value)
        if not start <= parsed_date <= end:
            continue
        records.append({
            "date": date_value,
            "open": float(price_record["open"]),
            "high": float(price_record["high"]),
            "low": float(price_record["low"]),
            "close": float(price_record["close"]),
            "volume": int(price_record.get("volume", 0)),
        })
    if not records:
        raise ValueError(f"No FMP prices found for {ticker} between {start_date} and {end_date}")
    return sorted(records, key=lambda item: item["date"])


def normalize_company_record(ticker: str, payload: dict[str, Any], as_of_date: str) -> dict[str, Any]:
    """Normalize FMP company payloads into the finance fundamentals shape."""
    ticker = normalize_ticker(ticker)
    profile_record = _first_record(payload["profile"], "profile")
    income_record = _first_record(payload["income_statement"], "income statement")
    balance_sheet_record = _first_record(payload["balance_sheet_statement"], "balance sheet statement")
    ratio_record = _optional_first_record(payload.get("ratios", []))
    fiscal_year = _fiscal_year(income_record)
    period_key = f"FY{fiscal_year}"
    return {
        "ticker": ticker,
        "company_name": profile_record.get("companyName", ticker),
        "sector": profile_record.get("sector", "Unknown"),
        "industry": profile_record.get("industry", "Unknown"),
        "statements": {
            "income": {
                period_key: {
                    "revenue": _required_float(income_record, "revenue"),
                    "gross_profit": _required_float(income_record, "grossProfit"),
                    "operating_income": _required_float(income_record, "operatingIncome"),
                    "net_income": _required_float(income_record, "netIncome"),
                }
            },
            "balance_sheet": {
                period_key: {
                    "cash_and_equivalents": _first_numeric(
                        balance_sheet_record,
                        ["cashAndCashEquivalents", "cashAndShortTermInvestments"],
                    ),
                    "total_assets": _required_float(balance_sheet_record, "totalAssets"),
                    "total_debt": _required_float(balance_sheet_record, "totalDebt"),
                    "total_equity": _first_numeric(
                        balance_sheet_record,
                        ["totalStockholdersEquity", "totalEquity"],
                    ),
                }
            },
        },
        "valuation_multiples": {
            as_of_date: _valuation_multiples(ratio_record),
        },
        "sources": [PROVIDER_NAME],
        "source": PROVIDER_NAME,
    }


def _provider_url(endpoint: str, params: dict[str, Any]) -> str:
    """Build a stable FMP endpoint URL."""
    return f"{FMP_BASE_URL}/{endpoint}?{urlencode(params)}"


def _records_from_payload(payload: dict[str, Any] | list[dict[str, Any]], list_key: str) -> list[dict[str, Any]]:
    """Return list records from either direct-list or wrapped FMP payloads."""
    if isinstance(payload, list):
        return payload
    if list_key in payload and isinstance(payload[list_key], list):
        return payload[list_key]
    if "data" in payload and isinstance(payload["data"], list):
        return payload["data"]
    raise ValueError(f"FMP payload is missing list records under {list_key}")


def _first_record(payload: dict[str, Any] | list[dict[str, Any]], label: str) -> dict[str, Any]:
    """Return the first record from a required FMP payload."""
    records = _records_from_payload(payload, "data")
    if not records:
        raise ValueError(f"FMP {label} payload is empty")
    return records[0]


def _optional_first_record(payload: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    """Return the first record from an optional FMP payload."""
    try:
        records = _records_from_payload(payload, "data")
    except ValueError:
        return {}
    if not records:
        return {}
    return records[0]


def _fiscal_year(income_record: dict[str, Any]) -> str:
    """Extract the annual fiscal year used by the normalized statement."""
    if income_record.get("calendarYear"):
        return str(income_record["calendarYear"])
    if income_record.get("fiscalYear"):
        return str(income_record["fiscalYear"])
    if income_record.get("date"):
        return str(income_record["date"])[:4]
    raise ValueError("FMP income statement payload is missing a fiscal year")


def _valuation_multiples(ratio_record: dict[str, Any]) -> dict[str, float]:
    """Normalize valuation multiples from FMP ratios."""
    multiples = {
        "price_to_earnings": _first_numeric(ratio_record, ["priceEarningsRatio", "peRatio"], optional=True),
        "price_to_book": _first_numeric(ratio_record, ["priceToBookRatio"], optional=True),
        "price_to_sales": _first_numeric(ratio_record, ["priceToSalesRatio"], optional=True),
        "ev_to_ebitda": _first_numeric(
            ratio_record,
            ["enterpriseValueMultiple", "enterpriseValueOverEBITDA"],
            optional=True,
        ),
        "dividend_yield": _first_numeric(ratio_record, ["dividendYield"], optional=True),
    }
    return {key: value for key, value in multiples.items() if value is not None}


def _first_numeric(record: dict[str, Any], keys: list[str], optional: bool = False) -> float | None:
    """Return the first parseable numeric field for a provider alias set."""
    for key in keys:
        value = record.get(key)
        if value not in (None, "", "None", "-"):
            return float(value)
    if optional:
        return None
    raise ValueError(f"FMP payload is missing required numeric fields: {keys}")


def _required_float(record: dict[str, Any], key: str) -> float:
    """Return a required numeric field."""
    return _first_numeric(record, [key])
