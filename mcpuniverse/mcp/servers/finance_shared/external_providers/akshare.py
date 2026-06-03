"""AKShare provider adapter for live China/Hong Kong market and macro data."""
import math
import re
from datetime import date, datetime
from typing import Any
from urllib.parse import urlencode

from mcpuniverse.mcp.servers.finance_shared.normalizers import normalize_ticker, parse_date

PROVIDER_NAME = "akshare"
CN_MARKET = "CN"
CN_CURRENCY = "CNY"
HK_MARKET = "HK"
HK_CURRENCY = "HKD"
DEFAULT_ADJUST = ""
HK_SYMBOL_LENGTH = 5

AKSHARE_MACRO_SERIES = {
    "CN_CPI": {
        "series_id": "CN_CPI",
        "name": "China Consumer Price Index YoY",
        "region": "CN",
        "frequency": "monthly",
        "unit": "percent",
        "function": "macro_china_cpi",
        "date_fields": ["date", "日期", "月份", "index"],
        "value_fields": ["全国-同比增长", "value", "今值"],
    },
    "CN_GDP": {
        "series_id": "CN_GDP",
        "name": "China GDP YoY",
        "region": "CN",
        "frequency": "quarterly",
        "unit": "percent",
        "function": "macro_china_gdp",
        "date_fields": ["date", "日期", "季度", "index"],
        "value_fields": ["国内生产总值-同比增长", "value", "今值"],
    },
    "CN_PMI": {
        "series_id": "CN_PMI",
        "name": "China Manufacturing PMI",
        "region": "CN",
        "frequency": "monthly",
        "unit": "index",
        "function": "macro_china_pmi",
        "date_fields": ["date", "日期", "月份", "index"],
        "value_fields": ["制造业-指数", "value", "今值"],
    },
    "CN_LPR": {
        "series_id": "CN_LPR",
        "name": "China 1Y Loan Prime Rate",
        "region": "CN",
        "frequency": "monthly",
        "unit": "percent",
        "function": "macro_china_lpr",
        "date_fields": ["TRADE_DATE", "date", "日期", "index"],
        "value_fields": ["LPR1Y", "value", "今值"],
    },
    "CN_M2": {
        "series_id": "CN_M2",
        "name": "China M2 Money Supply YoY",
        "region": "CN",
        "frequency": "monthly",
        "unit": "percent",
        "function": "macro_china_m2_yearly",
        "date_fields": ["date", "日期", "index"],
        "value_fields": ["value", "m2", "今值"],
    },
    "HK_UNEMPLOYMENT": {
        "series_id": "HK_UNEMPLOYMENT",
        "name": "Hong Kong Unemployment Rate",
        "region": "HK",
        "frequency": "monthly",
        "unit": "percent",
        "function": "macro_china_hk_rate_of_unemployment",
        "date_fields": ["时间", "date", "日期", "月份", "index"],
        "value_fields": ["现值", "value", "今值"],
    },
    "HK_GDP": {
        "series_id": "HK_GDP",
        "name": "Hong Kong GDP",
        "region": "HK",
        "frequency": "quarterly",
        "unit": "hundred_million_hkd",
        "function": "macro_china_hk_gbp",
        "date_fields": ["时间", "date", "日期", "季度", "index"],
        "value_fields": ["现值", "value", "今值"],
    },
    "HK_GDP_YOY": {
        "series_id": "HK_GDP_YOY",
        "name": "Hong Kong GDP YoY",
        "region": "HK",
        "frequency": "quarterly",
        "unit": "percent",
        "function": "macro_china_hk_gbp_ratio",
        "date_fields": ["时间", "date", "日期", "季度", "index"],
        "value_fields": ["现值", "value", "今值"],
    },
    "HK_PPI_YOY": {
        "series_id": "HK_PPI_YOY",
        "name": "Hong Kong Manufacturing PPI YoY",
        "region": "HK",
        "frequency": "quarterly",
        "unit": "percent",
        "function": "macro_china_hk_ppi",
        "date_fields": ["时间", "date", "日期", "季度", "index"],
        "value_fields": ["现值", "value", "今值"],
    },
}
CHINA_MACRO_SERIES = AKSHARE_MACRO_SERIES


def provider_symbol(ticker: str, instrument: dict[str, Any] | None = None) -> str:
    """Return an AKShare stock symbol for an internal ticker."""
    if instrument and instrument.get("provider_symbol"):
        return str(instrument["provider_symbol"]).strip()
    normalized_ticker = normalize_ticker(ticker)
    symbol = normalized_ticker.split(".", 1)[0] if "." in normalized_ticker else normalized_ticker
    if _market(ticker, instrument) == HK_MARKET and symbol.isdigit():
        return symbol.zfill(HK_SYMBOL_LENGTH)
    return symbol


def fetch_equity_price_payload(
        ticker: str,
        start_date: str,
        end_date: str,
        instrument: dict[str, Any] | None = None,
        adjust: str = DEFAULT_ADJUST,
) -> dict[str, Any]:
    """Fetch market-specific equity prices and profile data from AKShare."""
    if _market(ticker, instrument) == HK_MARKET:
        return fetch_hk_share_price_payload(ticker, start_date, end_date, instrument, adjust)
    return fetch_a_share_price_payload(ticker, start_date, end_date, instrument, adjust)


def fetch_equity_profile_payload(ticker: str, instrument: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fetch market-specific equity profile data from AKShare."""
    if _market(ticker, instrument) == HK_MARKET:
        return fetch_hk_share_profile_payload(ticker, instrument)
    return fetch_a_share_profile_payload(ticker, instrument)


def fetch_a_share_profile_payload(ticker: str, instrument: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fetch A-share basic profile data from AKShare."""
    akshare = _load_akshare()
    symbol = provider_symbol(ticker, instrument)
    profile_parameters = {"symbol": symbol}
    profile_frame = akshare.stock_individual_info_em(**profile_parameters)
    return {
        "ticker": normalize_ticker(ticker),
        "provider_symbol": symbol,
        "market": CN_MARKET,
        "exchange": instrument.get("exchange", "") if instrument else "",
        "currency": instrument.get("currency", CN_CURRENCY) if instrument else CN_CURRENCY,
        "company_profile_reference": _call_reference("stock_individual_info_em", profile_parameters),
        "company_profile": dataframe_to_records(profile_frame),
    }


def fetch_a_share_price_payload(
        ticker: str,
        start_date: str,
        end_date: str,
        instrument: dict[str, Any] | None = None,
        adjust: str = DEFAULT_ADJUST,
) -> dict[str, Any]:
    """Fetch A-share historical prices and basic profile data from AKShare."""
    akshare = _load_akshare()
    symbol = provider_symbol(ticker, instrument)
    price_parameters = {
        "symbol": symbol,
        "period": "daily",
        "start_date": _compact_date(start_date),
        "end_date": _compact_date(end_date),
        "adjust": adjust,
    }
    profile_parameters = {"symbol": symbol}
    price_frame = akshare.stock_zh_a_hist(**price_parameters)
    profile_frame = akshare.stock_individual_info_em(**profile_parameters)
    return {
        "ticker": normalize_ticker(ticker),
        "provider_symbol": symbol,
        "market": CN_MARKET,
        "exchange": instrument.get("exchange", "") if instrument else "",
        "currency": instrument.get("currency", CN_CURRENCY) if instrument else CN_CURRENCY,
        "historical_prices_reference": _call_reference("stock_zh_a_hist", price_parameters),
        "company_profile_reference": _call_reference("stock_individual_info_em", profile_parameters),
        "historical_prices": dataframe_to_records(price_frame),
        "company_profile": dataframe_to_records(profile_frame),
    }


def fetch_hk_share_price_payload(
        ticker: str,
        start_date: str,
        end_date: str,
        instrument: dict[str, Any] | None = None,
        adjust: str = DEFAULT_ADJUST,
) -> dict[str, Any]:
    """Fetch Hong Kong stock historical prices and basic profile data from AKShare."""
    akshare = _load_akshare()
    symbol = provider_symbol(ticker, instrument)
    price_parameters = {
        "symbol": symbol,
        "period": "daily",
        "start_date": _compact_date(start_date),
        "end_date": _compact_date(end_date),
        "adjust": adjust,
    }
    profile_parameters = {"symbol": symbol}
    price_frame = akshare.stock_hk_hist(**price_parameters)
    profile_frame = akshare.stock_hk_company_profile_em(**profile_parameters)
    return {
        "ticker": normalize_ticker(ticker),
        "provider_symbol": symbol,
        "market": HK_MARKET,
        "exchange": instrument.get("exchange", "HKEX") if instrument else "HKEX",
        "currency": instrument.get("currency", HK_CURRENCY) if instrument else HK_CURRENCY,
        "historical_prices_reference": _call_reference("stock_hk_hist", price_parameters),
        "company_profile_reference": _call_reference("stock_hk_company_profile_em", profile_parameters),
        "historical_prices": dataframe_to_records(price_frame),
        "company_profile": dataframe_to_records(profile_frame),
    }


def fetch_hk_share_profile_payload(ticker: str, instrument: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fetch Hong Kong stock basic profile data from AKShare."""
    akshare = _load_akshare()
    symbol = provider_symbol(ticker, instrument)
    profile_parameters = {"symbol": symbol}
    profile_frame = akshare.stock_hk_company_profile_em(**profile_parameters)
    return {
        "ticker": normalize_ticker(ticker),
        "provider_symbol": symbol,
        "market": HK_MARKET,
        "exchange": instrument.get("exchange", "HKEX") if instrument else "HKEX",
        "currency": instrument.get("currency", HK_CURRENCY) if instrument else HK_CURRENCY,
        "company_profile_reference": _call_reference("stock_hk_company_profile_em", profile_parameters),
        "company_profile": dataframe_to_records(profile_frame),
    }


def normalize_historical_prices(
        ticker: str,
        payload: dict[str, Any] | list[dict[str, Any]],
        start_date: str,
        end_date: str,
) -> list[dict[str, Any]]:
    """Normalize AKShare daily prices into the finance market-data shape."""
    ticker = normalize_ticker(ticker)
    start = parse_date(start_date)
    end = parse_date(end_date)
    if end < start:
        raise ValueError("end_date must be on or after start_date")

    records = []
    price_records = payload.get("historical_prices", payload) if isinstance(payload, dict) else payload
    for price_record in price_records:
        date_value = _date_field(price_record, ["date", "日期", "index"])
        parsed_date = parse_date(date_value)
        if not start <= parsed_date <= end:
            continue
        records.append({
            "date": date_value,
            "open": _required_float(price_record, ["open", "开盘"]),
            "high": _required_float(price_record, ["high", "最高"]),
            "low": _required_float(price_record, ["low", "最低"]),
            "close": _required_float(price_record, ["close", "收盘"]),
            "volume": int(_required_float(price_record, ["volume", "成交量"])),
        })
    if not records:
        raise ValueError(f"No AKShare prices found for {ticker} between {start_date} and {end_date}")
    return sorted(records, key=lambda item: item["date"])


def normalize_company_record(
        ticker: str,
        payload: dict[str, Any],
        as_of_date: str,
        instrument: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize AKShare company metadata into the finance company profile shape."""
    ticker = normalize_ticker(ticker)
    profile = _profile_map(payload.get("company_profile", []))
    instrument = instrument or {}
    return {
        "ticker": ticker,
        "company_name": _first_present(
            profile,
            ["股票简称", "公司名称", "证券简称", "Name", "name"],
            instrument.get("name", ticker),
        ),
        "sector": _first_present(
            profile,
            ["行业", "所属行业", "Sector", "sector"],
            instrument.get("sector", "CN Equity"),
        ),
        "industry": _first_present(profile, ["主营业务", "Industry", "industry"], "AKShare market data"),
        "currency": instrument.get("currency", payload.get("currency", _currency(ticker, instrument))),
        "market": instrument.get("market", payload.get("market", _market(ticker, instrument))),
        "exchange": instrument.get("exchange", payload.get("exchange", "")),
        "provider_symbol": payload.get("provider_symbol", provider_symbol(ticker, instrument)),
        "statements": {},
        "valuation_multiples": {as_of_date: {}},
        "unsupported_fields": ["financial_statements", "valuation_multiples"],
        "sources": [PROVIDER_NAME],
        "source": PROVIDER_NAME,
    }


def fetch_china_macro_payload(series_id: str) -> dict[str, Any]:
    """Fetch a configured macro series from AKShare."""
    normalized_series_id = normalize_macro_series_id(series_id)
    metadata = AKSHARE_MACRO_SERIES[normalized_series_id]
    akshare = _load_akshare()
    function_name = metadata["function"]
    data_frame = getattr(akshare, function_name)()
    return {
        "series_id": normalized_series_id,
        "function": function_name,
        "reference": f"akshare://{function_name}",
        "records": dataframe_to_records(data_frame),
    }


def normalize_china_macro_series(
        series_id: str,
        payload: dict[str, Any],
        start_date: str,
        end_date: str,
) -> dict[str, Any]:
    """Normalize an AKShare macro payload into the common macro shape."""
    normalized_series_id = normalize_macro_series_id(series_id)
    metadata = AKSHARE_MACRO_SERIES[normalized_series_id]
    start = parse_date(start_date)
    end = parse_date(end_date)
    if end < start:
        raise ValueError("end_date must be on or after start_date")

    observations = []
    for record in payload.get("records", []):
        date_value = _date_field(record, metadata["date_fields"])
        parsed_date = parse_date(date_value)
        if not start <= parsed_date <= end:
            continue
        value = _optional_float(record, metadata["value_fields"])
        if value is None:
            continue
        observations.append({"date": date_value, "value": value})
    if not observations:
        raise ValueError(f"No AKShare macro observations found for {normalized_series_id} between {start_date} and {end_date}")
    return {
        "series_id": normalized_series_id,
        "name": metadata["name"],
        "region": metadata["region"],
        "frequency": metadata["frequency"],
        "unit": metadata["unit"],
        "observations": sorted(observations, key=lambda item: item["date"]),
    }


def normalize_macro_series_id(series_id: str) -> str:
    """Normalize and validate an AKShare macro series id."""
    normalized = series_id.strip().upper() if series_id else ""
    if normalized not in AKSHARE_MACRO_SERIES:
        raise ValueError(f"Unsupported AKShare macro series_id: {series_id}")
    return normalized


def dataframe_to_records(data_frame) -> list[dict[str, Any]]:
    """Convert an AKShare pandas object into JSON-serializable records."""
    if data_frame is None:
        raise ValueError("AKShare returned no data")
    if hasattr(data_frame, "to_frame") and not hasattr(data_frame, "columns"):
        data_frame = data_frame.to_frame()
    normalized_frame = data_frame.reset_index()
    if normalized_frame.empty:
        raise ValueError("AKShare returned an empty data frame")
    return [
        {
            str(key): _json_value(value)
            for key, value in record.items()
            if str(key) != "level_0"
        }
        for record in normalized_frame.to_dict(orient="records")
    ]


def _load_akshare():
    """Import AKShare only when this provider is selected."""
    try:
        import akshare
    except ImportError as exc:
        raise RuntimeError("akshare is required for AKShare-backed finance tools") from exc
    return akshare


def _json_value(value):
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")
    return value


def _date_field(record: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = record.get(key)
        if value not in (None, "", "None", "-"):
            return _normalize_date_value(value)
    raise ValueError(f"AKShare record is missing a date field: {keys}")


def _normalize_date_value(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    if "季度" in text:
        match = re.search(r"(\d{4}).*?([1-4])", text)
        if match:
            quarter_month = {"1": "03", "2": "06", "3": "09", "4": "12"}[match.group(2)]
            return f"{match.group(1)}-{quarter_month}-01"
    if "年" in text:
        normalized = (
            text.replace("年", "-")
            .replace("月份", "")
            .replace("月", "")
            .replace("季度", "")
            .replace("Q1", "03")
            .replace("Q2", "06")
            .replace("Q3", "09")
            .replace("Q4", "12")
        )
        parts = [part for part in normalized.split("-") if part]
        if len(parts) >= 2:
            return f"{int(parts[0]):04d}-{int(parts[1]):02d}-01"
    if len(text) == 6 and text.isdigit():
        return f"{text[:4]}-{text[4:]}-01"
    return text[:10]


def _required_float(record: dict[str, Any], keys: list[str]) -> float:
    value = _optional_float(record, keys)
    if value is None:
        raise ValueError(f"AKShare payload is missing required numeric fields: {keys}")
    return value


def _optional_float(record: dict[str, Any], keys: list[str]) -> float | None:
    for key in keys:
        value = record.get(key)
        if value not in (None, "", "None", "-", "."):
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(numeric_value):
                return numeric_value
    return None


def _profile_map(records: list[dict[str, Any]]) -> dict[str, Any]:
    mapped_values = {}
    for record in records:
        item_key = record.get("item") or record.get("项目") or record.get("index")
        item_value = record.get("value") or record.get("值")
        if item_key not in (None, "") and item_value not in (None, ""):
            mapped_values[str(item_key)] = item_value
        for key, value in record.items():
            if value not in (None, ""):
                mapped_values.setdefault(str(key), value)
    return mapped_values


def _first_present(values: dict[str, Any], keys: list[str], default: str) -> str:
    for key in keys:
        value = values.get(key)
        if value not in (None, ""):
            return str(value)
    return str(default)


def _compact_date(date_value: str) -> str:
    return parse_date(date_value).strftime("%Y%m%d")


def _call_reference(function_name: str, parameters: dict[str, Any]) -> str:
    return f"akshare://{function_name}?{urlencode(parameters)}"


def _market(ticker: str, instrument: dict[str, Any] | None = None) -> str:
    market = str((instrument or {}).get("market") or "").strip().upper()
    if market:
        return market
    normalized_ticker = normalize_ticker(ticker)
    if normalized_ticker.endswith(".HK"):
        return HK_MARKET
    return CN_MARKET


def _currency(ticker: str, instrument: dict[str, Any] | None = None) -> str:
    currency = str((instrument or {}).get("currency") or "").strip().upper()
    if currency:
        return currency
    if _market(ticker, instrument) == HK_MARKET:
        return HK_CURRENCY
    return CN_CURRENCY
