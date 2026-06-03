"""Load finance data from live APIs and benchmark worlds."""
import copy
import hashlib
import json
import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from .constants import (
    BASE_CURRENCY,
    DATA_MODE_LIVE,
    FINANCE_BENCHMARK_WORLD_ID_ENV,
    FINANCE_BENCHMARK_WORLD_ROOT_ENV,
    FINANCE_DATA_MODE_ENV,
    FINANCE_TASK_MATERIAL_PATH_ENV,
    WORLD_ROOT,
)
from .errors import FinanceDataError, FinanceRecordNotFoundError
from .live_market_data import clear_live_market_data_cache, get_live_market_data_provider, resolve_ticker_route
from .macro_data import clear_macro_data_cache
from .normalizers import (
    normalize_account_id,
    normalize_optional_date,
    normalize_ticker,
    parse_date,
    round_money,
)
from .schema import data_source_key, make_task_evidence_record, normalize_data_source

WORLD_BUSINESS_STATE_PATHS = {
    "manifest.json": "manifest.json",
    "clients/client_profiles.json": "clients.json",
    "portfolios/accounts.json": "accounts.json",
    "orders/orders.json": "orders.json",
    "audit/audit_events.json": "audit.json",
    "crm/crm_records.json": "crm.json",
    "kyc/kyc_records.json": "kyc.json",
    "ledger/ledger_records.json": "ledger.json",
    "subledger/subledger_records.json": "subledger.json",
    "nav/nav_records.json": "nav.json",
    "private_markets/private_market_records.json": "private_markets.json",
}


def get_finance_data_mode() -> str:
    """Return the configured finance data mode."""
    mode = os.getenv(FINANCE_DATA_MODE_ENV, DATA_MODE_LIVE).strip().lower()
    if mode != DATA_MODE_LIVE:
        raise FinanceDataError(f"{FINANCE_DATA_MODE_ENV} must be {DATA_MODE_LIVE}")
    return DATA_MODE_LIVE


def is_live_data_mode() -> bool:
    """Return whether finance tools should use live market data."""
    get_finance_data_mode()
    return True


def has_active_world() -> bool:
    """Return whether the benchmark world data model is configured."""
    return bool(os.getenv(FINANCE_BENCHMARK_WORLD_ID_ENV, "").strip())


def get_active_world_id() -> str:
    """Return the configured benchmark world id."""
    world_id = os.getenv(FINANCE_BENCHMARK_WORLD_ID_ENV, "").strip()
    if not world_id:
        raise FinanceDataError(f"{FINANCE_BENCHMARK_WORLD_ID_ENV} is required for benchmark world data")
    return world_id


def get_active_world_root() -> Path:
    """Return the directory for the active benchmark world."""
    world_root = os.getenv(FINANCE_BENCHMARK_WORLD_ROOT_ENV, "").strip()
    root = Path(world_root).expanduser() if world_root else WORLD_ROOT
    return (root / get_active_world_id()).resolve()


def _world_path(relative_path: str, world_root: Path) -> Path:
    path = (world_root / relative_path).resolve()
    if world_root not in path.parents and path != world_root:
        raise FinanceDataError(f"World path escapes world root: {relative_path}")
    if not path.is_file():
        raise FinanceDataError(f"World file does not exist: {relative_path} under {world_root}")
    return path


def load_business_state_path(relative_path: str) -> dict[str, Any]:
    """Load an internal business-state path label from the active benchmark world.

    The public tools still share a few internal path labels. There is no
    fallback directory; every business-state read resolves through world data.
    """
    mapped_path = WORLD_BUSINESS_STATE_PATHS.get(relative_path)
    if not mapped_path:
        raise FinanceDataError(f"Unsupported benchmark world business-state path: {relative_path}")
    if mapped_path == "manifest.json":
        return load_world()
    return load_business_state(mapped_path[:-5] if mapped_path.endswith(".json") else mapped_path)


@lru_cache(maxsize=16)
def _load_world_from_root(world_root: str) -> dict[str, Any]:
    path = _world_path("manifest.json", Path(world_root))
    payload = _load_json_path(path)
    if not isinstance(payload, dict):
        raise FinanceDataError(f"World manifest must be a JSON object: {path}")
    world_id = payload.get("world_id")
    if world_id and world_id != Path(world_root).name:
        raise FinanceDataError(f"World manifest world_id {world_id} does not match directory {Path(world_root).name}")
    payload["world_id"] = world_id or Path(world_root).name
    return payload


def load_world(world_id: str | None = None) -> dict[str, Any]:
    """Load the active benchmark world manifest."""
    if world_id:
        root_value = os.getenv(FINANCE_BENCHMARK_WORLD_ROOT_ENV, "").strip()
        root = Path(root_value).expanduser() if root_value else WORLD_ROOT
        return copy.deepcopy(_load_world_from_root(str((root / world_id).resolve())))
    return copy.deepcopy(_load_world_from_root(str(get_active_world_root())))


@lru_cache(maxsize=128)
def _load_world_json_from_root(world_root: str, section: str, dataset_name: str) -> dict[str, Any]:
    filename = dataset_name if dataset_name.endswith(".json") else f"{dataset_name}.json"
    path = _world_path(f"{section}/{filename}", Path(world_root))
    payload = _load_json_path(path)
    if not isinstance(payload, dict):
        raise FinanceDataError(f"World {section} file must be a JSON object: {path}")
    world_id = Path(world_root).name
    payload.setdefault("world_id", world_id)
    payload.setdefault("payload_sha256", _json_sha256(payload))
    return payload


def load_business_state(dataset_name: str) -> dict[str, Any]:
    """Load a business-state dataset from the active benchmark world."""
    return copy.deepcopy(_load_world_json_from_root(str(get_active_world_root()), "business_state", dataset_name))


def load_provider_data(dataset_name: str) -> dict[str, Any]:
    """Load a deterministic provider dataset from the active benchmark world."""
    return copy.deepcopy(_load_world_json_from_root(str(get_active_world_root()), "provider_data", dataset_name))


def clear_finance_data_cache() -> None:
    """Clear cached finance data after changing environment."""
    _load_world_from_root.cache_clear()
    _load_world_json_from_root.cache_clear()
    _load_json_file.cache_clear()
    clear_live_market_data_cache()
    clear_macro_data_cache()


def has_task_material() -> bool:
    """Return whether the current task configured local material data."""
    return bool(os.getenv(FINANCE_TASK_MATERIAL_PATH_ENV, "").strip())


def load_task_material() -> dict[str, Any]:
    """Load the configured task-local material."""
    return _load_task_material()


def get_active_world_date() -> str:
    """Return the current live data date for generated draft ids."""
    return datetime.now(timezone.utc).date().isoformat()


def get_market_price(ticker: str, as_of_date: str | None = None) -> dict[str, Any]:
    """Return the latest live price on or before as_of_date for a ticker."""
    ticker = normalize_ticker(ticker)
    return get_live_market_data_provider(ticker).get_market_price(ticker, as_of_date)


def get_price_history(ticker: str, start_date: str, end_date: str) -> dict[str, Any]:
    """Return inclusive live historical prices for a ticker."""
    ticker = normalize_ticker(ticker)
    start = parse_date(start_date)
    end = parse_date(end_date)
    if end < start:
        raise ValueError("end_date must be on or after start_date")
    return get_live_market_data_provider(ticker).get_price_history(ticker, start_date, end_date)


def get_company_fundamentals(ticker: str) -> dict[str, Any]:
    """Return live company fundamentals for a ticker."""
    ticker = normalize_ticker(ticker)
    return get_live_market_data_provider(ticker).get_company_fundamentals(ticker)


def get_financial_statement(ticker: str, statement_type: str, period: str | None = None) -> dict[str, Any]:
    """Return a financial statement slice for a ticker."""
    company = get_company_fundamentals(ticker)
    if not statement_type or not statement_type.strip():
        raise ValueError("statement_type is required")
    statement_type = statement_type.strip().lower()
    statements = company.get("statements", {}).get(statement_type)
    if not statements:
        if "financial_statements" in company.get("unsupported_fields", []):
            raise FinanceRecordNotFoundError(
                f"Financial statements are unsupported for ticker {company['ticker']} from provider {company.get('source', '')}"
            )
        raise FinanceRecordNotFoundError(f"No {statement_type} statement found for ticker {company['ticker']}")
    if period:
        selected = statements.get(period)
        if not selected:
            raise FinanceRecordNotFoundError(f"No {statement_type} statement found for {company['ticker']} period {period}")
        result = {
            "ticker": company["ticker"],
            "statement_type": statement_type,
            "period": period,
            "values": copy.deepcopy(selected),
        }
        _attach_source_metadata(result, company)
        return result
    result = {
        "ticker": company["ticker"],
        "statement_type": statement_type,
        "statements": copy.deepcopy(statements),
    }
    _attach_source_metadata(result, company)
    return result


def get_valuation_multiples(ticker: str, as_of_date: str | None = None) -> dict[str, Any]:
    """Return valuation multiples for a ticker."""
    company = get_company_fundamentals(ticker)
    target_date = normalize_optional_date(as_of_date)
    multiples = company.get("valuation_multiples", {})
    if not multiples:
        raise FinanceRecordNotFoundError(f"No valuation multiples found for ticker {company['ticker']}")
    if "valuation_multiples" in company.get("unsupported_fields", []) and not any(multiples.values()):
        raise FinanceRecordNotFoundError(
            f"Valuation multiples are unsupported for ticker {company['ticker']} from provider {company.get('source', '')}"
        )
    candidates = [
        (date_value, values)
        for date_value, values in multiples.items()
        if target_date is None or parse_date(date_value) <= parse_date(target_date)
    ]
    if not candidates:
        raise FinanceRecordNotFoundError(
            f"No valuation multiples found for {company['ticker']} on or before {target_date}"
        )
    selected_date, selected_values = max(candidates, key=lambda item: item[0])
    result = {
        "ticker": company["ticker"],
        "as_of_date": selected_date,
        "multiples": copy.deepcopy(selected_values),
    }
    _attach_source_metadata(result, company)
    return result


def search_company_news(
        ticker: str,
        start_date: str | None = None,
        end_date: str | None = None,
        query: str | None = None
) -> dict[str, Any]:
    """Return news records for a ticker with optional date and text filters."""
    ticker = normalize_ticker(ticker)
    start = parse_date(start_date) if start_date else None
    end = parse_date(end_date) if end_date else None
    if start and end and end < start:
        raise ValueError("end_date must be on or after start_date")
    query_text = query.lower().strip() if query else ""

    task_material = _load_task_material()
    records = []
    for record in task_material.get("news", []):
        record_date = parse_date(record["date"])
        haystack = f"{record.get('headline', '')} {record.get('summary', '')} {record.get('body', '')}".lower()
        if ticker not in [normalize_ticker(item) for item in record.get("tickers", [])]:
            continue
        if start and record_date < start:
            continue
        if end and record_date > end:
            continue
        if query_text and query_text not in haystack:
            continue
        copied_record = copy.deepcopy(record)
        copied_record["evidence"] = [_task_evidence_for_record(task_material, "news", record["news_id"], "news", record)]
        records.append(copied_record)
    return {
        "ticker": ticker,
        "world_id": _task_material_world_id(task_material),
        "news": records,
    }


def get_instrument_profile(ticker: str) -> dict[str, Any]:
    """Return live/resolved instrument profile for a tradable ticker."""
    ticker = normalize_ticker(ticker)
    task_override = _task_instrument_override(ticker)
    if task_override:
        result = copy.deepcopy(task_override)
        result["ticker"] = ticker
        result["world_id"] = _active_task_material_world_id()
        return result

    company = get_company_fundamentals(ticker)
    route = resolve_ticker_route(ticker)
    result = {
        "ticker": ticker,
        "product_type": route["product_type"],
        "market": company.get("market", route["market"]),
        "exchange": company.get("exchange", route["exchange"]),
        "currency": company.get("currency", route["currency"]),
        "provider": route["provider"],
        "provider_symbol": company.get("provider_symbol", route["provider_symbol"]),
        "company_name": company.get("company_name", ticker),
        "sector": company.get("sector", ""),
        "industry": company.get("industry", ""),
    }
    _attach_source_metadata(result, company)
    return result


def search_research_reports(
        ticker: str | None = None,
        publication_status: str | None = None,
        include_untrusted_excerpt: bool = True
) -> dict[str, Any]:
    """Return research reports with optional ticker and status filters."""
    normalized_ticker = normalize_ticker(ticker) if ticker else ""
    normalized_status = publication_status.strip().lower() if publication_status else ""
    task_material = _load_task_material()
    reports = []
    for report in _research_records(task_material):
        if normalized_ticker and normalize_ticker(report["ticker"]) != normalized_ticker:
            continue
        if normalized_status and report.get("publication_status", "").lower() != normalized_status:
            continue
        reports.append(_copy_research_report(report, include_untrusted_excerpt, task_material))
    return {
        "world_id": _task_material_world_id(task_material),
        "reports": reports,
    }


def get_research_report(report_id: str, include_untrusted_excerpt: bool = True) -> dict[str, Any]:
    """Return one research report by id."""
    if not report_id or not report_id.strip():
        raise ValueError("report_id is required")
    normalized_report_id = report_id.strip().upper()
    task_material = _load_task_material()
    for report in _research_records(task_material):
        if report["report_id"].upper() == normalized_report_id:
            result = _copy_research_report(report, include_untrusted_excerpt, task_material)
            result["world_id"] = _task_material_world_id(task_material)
            return result
    raise FinanceRecordNotFoundError(f"No research report found for report_id {normalized_report_id}")


def _copy_research_report(
        report: dict[str, Any],
        include_untrusted_excerpt: bool,
        task_material: dict[str, Any],
) -> dict[str, Any]:
    """Copy a report and optionally suppress untrusted source text."""
    result = copy.deepcopy(report)
    if not include_untrusted_excerpt:
        result["untrusted_source_excerpt"] = ""
    result["evidence"] = [
        _task_evidence_for_record(
            task_material,
            dataset="research_reports",
            source_type="research_report",
            source_id=report["report_id"],
            record=report,
        )
    ]
    return result


def list_accounts(client_id: str | None = None) -> dict[str, Any]:
    """Return account metadata with optional client filtering."""
    payload = load_business_state_path("portfolios/accounts.json")
    records = []
    for account in payload.get("accounts", []):
        if client_id and account.get("client_id") != client_id:
            continue
        records.append(copy.deepcopy(account))
    return {"world_id": payload["world_id"], "accounts": records}


def get_account(account_id: str) -> dict[str, Any]:
    """Return one account from the active benchmark world."""
    account_id = normalize_account_id(account_id)
    payload = load_business_state_path("portfolios/accounts.json")
    for account in payload.get("accounts", []):
        if normalize_account_id(account["account_id"]) == account_id:
            result = copy.deepcopy(account)
            result["world_id"] = payload["world_id"]
            return result
    raise FinanceRecordNotFoundError(f"No account found for account_id {account_id}")


def get_client_profile(client_id: str) -> dict[str, Any]:
    """Return one client profile from the active benchmark world."""
    if not client_id or not client_id.strip():
        raise ValueError("client_id is required")
    normalized_client_id = client_id.strip().upper()
    payload = load_business_state_path("clients/client_profiles.json")
    for client in payload.get("clients", []):
        if client["client_id"].upper() == normalized_client_id:
            result = copy.deepcopy(client)
            result["world_id"] = payload["world_id"]
            return result
    raise FinanceRecordNotFoundError(f"No client found for client_id {normalized_client_id}")


def get_account_client_context(account_id: str) -> dict[str, Any]:
    """Return account metadata with its linked client profile."""
    account = get_account(account_id)
    client = get_client_profile(account["client_id"])
    return {
        "world_id": account["world_id"],
        "account": account,
        "client": client,
        "account_id": account["account_id"],
        "client_id": client["client_id"],
        "risk_profile": account["risk_profile"],
        "approved_product_types": client.get("approved_product_types", []),
        "restricted_product_types": client.get("restricted_product_types", []),
        "data_entitlements": client.get("data_entitlements", []),
        "required_disclosures": client.get("required_disclosures", []),
    }


def get_enriched_holdings(account_id: str, as_of_date: str | None = None) -> dict[str, Any]:
    """Return holdings enriched with market values."""
    account = get_account(account_id)
    base_currency = account.get("base_currency", BASE_CURRENCY)
    holdings = []
    market_data_sources = []
    for holding in account.get("holdings", []):
        ticker = normalize_ticker(holding["ticker"])
        price = get_market_price(ticker, as_of_date)
        price_currency = price.get("currency", BASE_CURRENCY)
        if price_currency != base_currency:
            raise FinanceDataError(
                f"Currency mismatch for account {account['account_id']} holding {ticker}: "
                f"account base_currency={base_currency}, price currency={price_currency}"
            )
        price_data_source = price.get("data_source")
        market_value = round_money(float(holding["quantity"]) * float(price["close"]))
        enriched = copy.deepcopy(holding)
        enriched["ticker"] = ticker
        enriched["currency"] = price_currency
        enriched["price_date"] = price["date"]
        enriched["last_price"] = price["close"]
        enriched["market_value"] = market_value
        if price_data_source:
            enriched["data_source"] = normalize_data_source(price_data_source)
            _append_unique_data_source(market_data_sources, price_data_source)
        holdings.append(enriched)
    result = {
        "account_id": account["account_id"],
        "client_id": account["client_id"],
        "world_id": account["world_id"],
        "as_of_date": normalize_optional_date(as_of_date) or get_active_world_date(),
        "base_currency": base_currency,
        "holdings": holdings,
    }
    if market_data_sources:
        result["data_sources"] = market_data_sources
    return result


def get_risk_model() -> dict[str, Any]:
    """Return built-in risk calculation settings."""
    return {
        "world_id": get_active_world_id(),
        "trading_days_per_year": 252,
        "confidence_z_scores": {
            "0.95": 1.65,
            "0.99": 2.33,
        },
        "stress_scenarios": {
            "equity_down_10_financials_down_4": {
                "description": "Broad equity drawdown with a smaller financial-sector shock.",
                "sector_shocks": {
                    "Information Technology": -0.10,
                    "Technology": -0.10,
                    "Communication Services": -0.10,
                    "Consumer Discretionary": -0.10,
                    "Consumer Cyclical": -0.10,
                    "Consumer Staples": -0.08,
                    "Financials": -0.04,
                    "Financial Services": -0.04,
                },
                "cash_shock": 0.0,
            },
        },
    }


def get_ticker_risk(ticker: str) -> dict[str, Any]:
    """Return risk parameters for one ticker."""
    ticker = normalize_ticker(ticker)
    return get_live_market_data_provider(ticker).get_live_ticker_risk(ticker)


def get_stress_scenario(scenario_name: str) -> dict[str, Any]:
    """Return one deterministic stress scenario."""
    if not scenario_name or not scenario_name.strip():
        raise ValueError("scenario_name is required")
    scenario_name = scenario_name.strip()
    risk_model = get_risk_model()
    stress_scenario = risk_model.get("stress_scenarios", {}).get(scenario_name)
    if not stress_scenario:
        raise FinanceRecordNotFoundError(f"No stress scenario found for {scenario_name}")
    result = copy.deepcopy(stress_scenario)
    result["scenario_name"] = scenario_name
    result["world_id"] = risk_model["world_id"]
    return result


def get_compliance_rules() -> dict[str, Any]:
    """Return task-local compliance rules."""
    task_material = _load_task_material()
    rules = task_material.get("compliance") or task_material.get("policy_constraints")
    if not isinstance(rules, dict):
        raise FinanceDataError(
            f"{FINANCE_TASK_MATERIAL_PATH_ENV} must define `compliance` for compliance policy tools"
    )
    result = copy.deepcopy(rules)
    result["world_id"] = _task_material_world_id(task_material)
    return result


def get_restricted_security(ticker: str) -> dict[str, Any] | None:
    """Return restricted-security policy for a ticker, if one exists."""
    ticker = normalize_ticker(ticker)
    rules = get_compliance_rules()
    record = rules.get("restricted_securities", {}).get(ticker)
    if not record:
        return None
    result = copy.deepcopy(record)
    result["ticker"] = ticker
    result["world_id"] = rules["world_id"]
    return result


def list_audit_events(
        account_id: str | None = None,
        event_type: str | None = None,
        limit: int = 10
) -> dict[str, Any]:
    """Return static audit events with optional filters."""
    if limit <= 0:
        raise ValueError("limit must be positive")
    normalized_account_id = normalize_account_id(account_id) if account_id else ""
    normalized_event_type = event_type.strip().lower() if event_type else ""
    try:
        payload = load_business_state_path("audit/audit_events.json")
    except FinanceDataError:
        return {"world_id": get_active_world_id(), "events": []}
    events = []
    for event in payload.get("events", []):
        if normalized_account_id and normalize_account_id(event["account_id"]) != normalized_account_id:
            continue
        if normalized_event_type and event.get("event_type", "").lower() != normalized_event_type:
            continue
        events.append(copy.deepcopy(event))
    return {
        "world_id": payload["world_id"],
        "events": events[:limit],
    }


def get_audit_event(event_id: str) -> dict[str, Any]:
    """Return one static audit event by id."""
    if not event_id or not event_id.strip():
        raise ValueError("event_id is required")
    event_id = event_id.strip().upper()
    payload = _load_audit_world_state()
    for event in payload.get("events", []):
        if event["event_id"].upper() == event_id:
            result = copy.deepcopy(event)
            result["world_id"] = payload["world_id"]
            return result
    raise FinanceRecordNotFoundError(f"No audit event found for event_id {event_id}")


def get_policy_reference(policy_code: str) -> dict[str, Any]:
    """Return one task-local policy reference by policy code."""
    if not policy_code or not policy_code.strip():
        raise ValueError("policy_code is required")
    policy_code = policy_code.strip().upper()
    task_material = _load_task_material()
    reference = task_material.get("policy_references", {}).get(policy_code)
    if not reference:
        raise FinanceRecordNotFoundError(f"No policy reference found for policy_code {policy_code}")
    result = copy.deepcopy(reference)
    result["world_id"] = _task_material_world_id(task_material)
    return result


def list_policy_references(policy_area: str | None = None) -> dict[str, Any]:
    """Return task-local policy references with optional policy-area filtering."""
    normalized_area = policy_area.strip().lower() if policy_area else ""
    task_material = _load_task_material()
    references = []
    for reference in task_material.get("policy_references", {}).values():
        policy_area_value = reference.get("policy_area", "")
        if normalized_area and policy_area_value.lower() != normalized_area:
            continue
        references.append(copy.deepcopy(reference))
    return {
        "world_id": _task_material_world_id(task_material),
        "policy_references": sorted(references, key=lambda item: item["policy_code"]),
    }


@lru_cache(maxsize=16)
def _load_json_file(path_value: str) -> dict[str, Any]:
    path = Path(path_value).expanduser().resolve()
    if not path.is_file():
        raise FinanceDataError(f"Finance task material file does not exist: {path}")
    payload = _load_json_path(path)
    if not isinstance(payload, dict):
        raise FinanceDataError(f"Finance task material must be a JSON object: {path}")
    return payload


def _load_json_path(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as json_file:
        return json.load(json_file)


def _json_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_task_material() -> dict[str, Any]:
    material_path = os.getenv(FINANCE_TASK_MATERIAL_PATH_ENV, "").strip()
    if material_path:
        return copy.deepcopy(_load_json_file(material_path))
    raise FinanceDataError(f"{FINANCE_TASK_MATERIAL_PATH_ENV} is required for this finance tool")


def _load_audit_world_state() -> dict[str, Any]:
    try:
        return load_business_state_path("audit/audit_events.json")
    except FinanceDataError as exc:
        raise FinanceRecordNotFoundError("No local audit events are configured for this benchmark world") from exc


def _attach_source_metadata(result: dict[str, Any], source: dict[str, Any]) -> None:
    if "world_id" in source:
        result["world_id"] = source["world_id"]
    if "data_source" in source:
        result["data_source"] = normalize_data_source(source["data_source"])


def _append_unique_data_source(data_sources: list[dict[str, Any]], data_source: dict[str, Any]) -> None:
    normalized_data_source = normalize_data_source(data_source)
    if any(data_source_key(source) == data_source_key(normalized_data_source) for source in data_sources):
        return
    data_sources.append(normalized_data_source)


def _task_instrument_override(ticker: str) -> dict[str, Any]:
    if not has_task_material():
        return {}
    task_material = _load_task_material()
    instruments = task_material.get("instruments") or task_material.get("instrument_overrides") or {}
    instrument = instruments.get(normalize_ticker(ticker))
    return copy.deepcopy(instrument) if isinstance(instrument, dict) else {}


def _active_task_material_world_id() -> str:
    if not has_task_material():
        return get_active_world_id()
    return _task_material_world_id(_load_task_material())


def _research_records(task_material: dict[str, Any]) -> list[dict[str, Any]]:
    return task_material.get("reports", task_material.get("research_reports", []))


def _task_material_world_id(task_material: dict[str, Any]) -> str:
    return task_material.get("world_id") or get_active_world_id()


def _task_evidence_for_record(
        task_material: dict[str, Any],
        dataset: str,
        source_id: str,
        source_type: str,
        record: dict[str, Any],
) -> dict[str, Any]:
    return make_task_evidence_record(
        world_id=_task_material_world_id(task_material),
        dataset=dataset,
        source_type=source_type,
        source_id=source_id,
        source_trust_level=record.get("source_trust_level", record.get("trust_level", "trusted")),
        locator=record.get("document_locator") or record.get("url", ""),
    )
