"""Benchmark-world cross-asset deterministic provider data."""
from __future__ import annotations

import copy
from typing import Any

from .errors import FinanceRecordNotFoundError
from .world_records import provider_data, with_source

FIXED_INCOME_DATASET = "fixed_income"
RATES_DATASET = "rates_curves"
FX_DATASET = "fx"
DERIVATIVES_DATASET = "derivatives"


def bond_price(identifier: str, as_of_date: str = "") -> dict[str, Any]:
    bond, payload = _record_by_any_id(FIXED_INCOME_DATASET, "bonds", identifier)
    result = copy.deepcopy(bond.get("pricing", {}))
    result.update({
        "identifier": identifier,
        "bond_id": bond["bond_id"],
        "as_of_date": as_of_date or bond.get("as_of_date", ""),
    })
    return with_source(result, payload, FIXED_INCOME_DATASET, "bond_price", bond["bond_id"], bond)


def bond_future_price(future_ric: str, as_of_date: str = "") -> dict[str, Any]:
    future, payload = _record_by_field(FIXED_INCOME_DATASET, "bond_futures", "future_ric", future_ric)
    result = copy.deepcopy(future)
    result["as_of_date"] = as_of_date or future.get("as_of_date", "")
    return with_source(result, payload, FIXED_INCOME_DATASET, "bond_future_price", future["future_ric"], future)


def interest_rate_curve(currency: str, as_of_date: str = "") -> dict[str, Any]:
    return _curve("interest_rate_curves", "currency", currency, "interest_rate_curve", as_of_date)


def credit_curve(curve_id: str = "", country: str = "", issuer_type: str = "", as_of_date: str = "") -> dict[str, Any]:
    payload = provider_data(RATES_DATASET)
    for curve in payload.get("credit_curves", []):
        if curve_id and curve.get("curve_id", "").upper() != curve_id.upper():
            continue
        if country and curve.get("country", "").upper() != country.upper():
            continue
        if issuer_type and curve.get("issuer_type", "").lower() != issuer_type.lower():
            continue
        result = copy.deepcopy(curve)
        result["as_of_date"] = as_of_date or curve.get("as_of_date", "")
        return with_source(result, payload, RATES_DATASET, "credit_curve", curve["curve_id"], curve)
    raise FinanceRecordNotFoundError("No credit curve found for requested filters")


def inflation_curve(currency: str, as_of_date: str = "") -> dict[str, Any]:
    return _curve("inflation_curves", "currency", currency, "inflation_curve", as_of_date)


def yieldbook_bond_reference(identifier: str) -> dict[str, Any]:
    bond, payload = _record_by_any_id(FIXED_INCOME_DATASET, "bonds", identifier)
    result = copy.deepcopy(bond.get("reference", {}))
    result["bond_id"] = bond["bond_id"]
    return with_source(result, payload, FIXED_INCOME_DATASET, "bond_reference", bond["bond_id"], bond)


def yieldbook_cashflow(identifier: str) -> dict[str, Any]:
    bond, payload = _record_by_any_id(FIXED_INCOME_DATASET, "bonds", identifier)
    result = {
        "bond_id": bond["bond_id"],
        "cashflows": copy.deepcopy(bond.get("cashflows", [])),
    }
    return with_source(result, payload, FIXED_INCOME_DATASET, "bond_cashflow", bond["bond_id"], bond)


def yieldbook_scenario(identifier: str, scenario_name: str = "parallel_100bp_up") -> dict[str, Any]:
    bond, payload = _record_by_any_id(FIXED_INCOME_DATASET, "bonds", identifier)
    scenarios = bond.get("scenarios", {})
    if scenario_name not in scenarios:
        raise FinanceRecordNotFoundError(f"No scenario {scenario_name} for bond {bond['bond_id']}")
    result = {
        "bond_id": bond["bond_id"],
        "scenario_name": scenario_name,
        "scenario_result": copy.deepcopy(scenarios[scenario_name]),
    }
    return with_source(result, payload, FIXED_INCOME_DATASET, "bond_scenario", bond["bond_id"], bond)


def fixed_income_risk_analytics(identifier: str) -> dict[str, Any]:
    bond, payload = _record_by_any_id(FIXED_INCOME_DATASET, "bonds", identifier)
    result = copy.deepcopy(bond.get("risk_analytics", {}))
    result["bond_id"] = bond["bond_id"]
    return with_source(result, payload, FIXED_INCOME_DATASET, "fixed_income_risk", bond["bond_id"], bond)


def fx_spot_price(currency_pair: str, as_of_date: str = "") -> dict[str, Any]:
    record, payload = _record_by_field(FX_DATASET, "spot_rates", "currency_pair", currency_pair.upper())
    result = copy.deepcopy(record)
    result["as_of_date"] = as_of_date or record.get("as_of_date", "")
    return with_source(result, payload, FX_DATASET, "fx_spot_price", record["currency_pair"], record)


def fx_forward_price(currency_pair: str, tenor: str = "3M", as_of_date: str = "") -> dict[str, Any]:
    pair = currency_pair.upper()
    payload = provider_data(FX_DATASET)
    for record in payload.get("forward_points", []):
        if record.get("currency_pair", "").upper() == pair and record.get("tenor", "").upper() == tenor.upper():
            result = copy.deepcopy(record)
            result["as_of_date"] = as_of_date or record.get("as_of_date", "")
            return with_source(result, payload, FX_DATASET, "fx_forward_price", f"{pair}:{tenor}", record)
    raise FinanceRecordNotFoundError(f"No FX forward found for {pair} tenor {tenor}")


def fx_forward_curve(currency_pair: str, as_of_date: str = "") -> dict[str, Any]:
    record, payload = _record_by_field(FX_DATASET, "forward_curves", "currency_pair", currency_pair.upper())
    result = copy.deepcopy(record)
    result["as_of_date"] = as_of_date or record.get("as_of_date", "")
    return with_source(result, payload, FX_DATASET, "fx_forward_curve", record["currency_pair"], record)


def fx_vol_surface(currency_pair: str, as_of_date: str = "") -> dict[str, Any]:
    record, payload = _record_by_field(FX_DATASET, "vol_surfaces", "currency_pair", currency_pair.upper())
    result = copy.deepcopy(record)
    result["as_of_date"] = as_of_date or record.get("as_of_date", "")
    return with_source(result, payload, FX_DATASET, "fx_vol_surface", record["currency_pair"], record)


def equity_vol_surface(underlying: str, as_of_date: str = "") -> dict[str, Any]:
    record, payload = _record_by_field(DERIVATIVES_DATASET, "equity_vol_surfaces", "underlying", underlying.upper())
    result = copy.deepcopy(record)
    result["as_of_date"] = as_of_date or record.get("as_of_date", "")
    return with_source(result, payload, DERIVATIVES_DATASET, "equity_vol_surface", record["underlying"], record)


def option_template_list(underlying: str) -> dict[str, Any]:
    record, payload = _record_by_field(DERIVATIVES_DATASET, "option_templates", "underlying", underlying.upper())
    return with_source(copy.deepcopy(record), payload, DERIVATIVES_DATASET, "option_templates", record["underlying"], record)


def option_value(underlying: str, strike: float = 0.0, expiry: str = "", option_type: str = "call") -> dict[str, Any]:
    payload = provider_data(DERIVATIVES_DATASET)
    normalized_underlying = underlying.upper()
    normalized_expiry = expiry.strip()
    normalized_type = option_type.strip().lower()
    for record in payload.get("option_values", []):
        if record.get("underlying", "").upper() != normalized_underlying:
            continue
        if normalized_expiry and record.get("expiry", "") != normalized_expiry:
            continue
        if strike and float(record.get("strike", 0.0)) != float(strike):
            continue
        if normalized_type and record.get("option_type", "").lower() != normalized_type:
            continue
        return with_source(copy.deepcopy(record), payload, DERIVATIVES_DATASET, "option_value", record["option_id"], record)
    raise FinanceRecordNotFoundError(f"No option value found for {underlying}")


def ir_swap(currency: str, tenor: str = "", index: str = "", as_of_date: str = "") -> dict[str, Any]:
    payload = provider_data(RATES_DATASET)
    normalized_currency = currency.upper()
    for record in payload.get("ir_swaps", []):
        if record.get("currency", "").upper() != normalized_currency:
            continue
        if tenor and record.get("tenor", "").upper() != tenor.upper():
            continue
        if index and record.get("index", "").upper() != index.upper():
            continue
        result = copy.deepcopy(record)
        result["as_of_date"] = as_of_date or record.get("as_of_date", "")
        return with_source(result, payload, RATES_DATASET, "ir_swap", f"{record['currency']}:{record['tenor']}", record)
    raise FinanceRecordNotFoundError(f"No IR swap found for {currency} tenor {tenor}")


def _curve(collection: str, field: str, value: str, source_type: str, as_of_date: str = "") -> dict[str, Any]:
    payload = provider_data(RATES_DATASET)
    for curve in payload.get(collection, []):
        if curve.get(field, "").upper() == value.upper():
            result = copy.deepcopy(curve)
            result["as_of_date"] = as_of_date or curve.get("as_of_date", "")
            return with_source(result, payload, RATES_DATASET, source_type, curve["curve_id"], curve)
    raise FinanceRecordNotFoundError(f"No {source_type} found for {value}")


def _record_by_any_id(dataset: str, collection: str, identifier: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if not identifier or not identifier.strip():
        raise ValueError("identifier is required")
    normalized = identifier.strip().upper()
    payload = provider_data(dataset)
    for record in payload.get(collection, []):
        identifiers = {
            str(record.get(key, "")).upper()
            for key in ("bond_id", "isin", "cusip", "ric")
            if record.get(key)
        }
        if normalized in identifiers:
            return copy.deepcopy(record), payload
    raise FinanceRecordNotFoundError(f"No {collection} record found for identifier {normalized}")


def _record_by_field(dataset: str, collection: str, field: str, value: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if not value or not str(value).strip():
        raise ValueError(f"{field} is required")
    normalized = str(value).strip().upper()
    payload = provider_data(dataset)
    for record in payload.get(collection, []):
        if str(record.get(field, "")).upper() == normalized:
            return copy.deepcopy(record), payload
    raise FinanceRecordNotFoundError(f"No {collection} record found for {field} {normalized}")
