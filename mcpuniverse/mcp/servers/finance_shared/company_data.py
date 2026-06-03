"""Benchmark-world company data for modeling and research workflows."""
from __future__ import annotations

import copy
from typing import Any

from .errors import FinanceRecordNotFoundError
from .normalizers import normalize_ticker
from .world_records import provider_data, record_text, with_source

DATASET = "company_data"


def search_companies(query: str = "", sector: str = "", market: str = "") -> dict[str, Any]:
    """Search deterministic company records."""
    payload = provider_data(DATASET)
    normalized_query = query.strip().lower()
    normalized_sector = sector.strip().lower()
    normalized_market = market.strip().upper()
    records = []
    for company in payload.get("companies", []):
        if normalized_sector and company.get("sector", "").lower() != normalized_sector:
            continue
        if normalized_market and company.get("market", "").upper() != normalized_market:
            continue
        if normalized_query and normalized_query not in record_text(company):
            continue
        records.append(_company_summary(company, payload))
    return {"world_id": payload["world_id"], "companies": records}


def get_standardized_financials(ticker: str, statement_type: str = "", period: str = "") -> dict[str, Any]:
    """Return standardized historical financial statements for a company."""
    company, payload = _company(ticker)
    statements = copy.deepcopy(company.get("standardized_financials", {}))
    normalized_statement_type = statement_type.strip().lower()
    if normalized_statement_type:
        statements = {normalized_statement_type: statements.get(normalized_statement_type, {})}
    if period:
        statements = {
            key: {period: value.get(period, {})}
            for key, value in statements.items()
        }
    result = {
        "ticker": company["ticker"],
        "company_name": company.get("company_name", ""),
        "currency": company.get("currency", ""),
        "statement_type": normalized_statement_type,
        "period": period,
        "standardized_financials": statements,
    }
    return with_source(result, payload, DATASET, "company_financials", company["ticker"], company)


def get_segment_financials(ticker: str, period: str = "") -> dict[str, Any]:
    """Return segment-level financials for a company."""
    company, payload = _company(ticker)
    records = [
        copy.deepcopy(record)
        for record in company.get("segment_financials", [])
        if not period or record.get("period") == period
    ]
    result = {"ticker": company["ticker"], "period": period, "segments": records}
    return with_source(result, payload, DATASET, "segment_financials", company["ticker"], company)


def get_capital_structure(ticker: str, as_of_date: str = "") -> dict[str, Any]:
    """Return capital structure inputs for valuation workflows."""
    company, payload = _company(ticker)
    result = copy.deepcopy(company.get("capital_structure", {}))
    result["ticker"] = company["ticker"]
    if as_of_date:
        result["requested_as_of_date"] = as_of_date
    return with_source(result, payload, DATASET, "capital_structure", company["ticker"], company)


def get_wacc_inputs(ticker: str, as_of_date: str = "") -> dict[str, Any]:
    """Return WACC inputs for DCF workflows."""
    company, payload = _company(ticker)
    result = copy.deepcopy(company.get("wacc_inputs", {}))
    result["ticker"] = company["ticker"]
    if as_of_date:
        result["requested_as_of_date"] = as_of_date
    return with_source(result, payload, DATASET, "wacc_inputs", company["ticker"], company)


def get_model_input_pack(ticker: str, model_type: str = "") -> dict[str, Any]:
    """Return a compact modeling input pack for DCF/LBO/3-statement/comps workflows."""
    company, payload = _company(ticker)
    result = {
        "ticker": company["ticker"],
        "company_name": company.get("company_name", ""),
        "model_type": model_type,
        "currency": company.get("currency", ""),
        "standardized_financials": copy.deepcopy(company.get("standardized_financials", {})),
        "segment_financials": copy.deepcopy(company.get("segment_financials", [])),
        "capital_structure": copy.deepcopy(company.get("capital_structure", {})),
        "wacc_inputs": copy.deepcopy(company.get("wacc_inputs", {})),
        "valuation_multiples": copy.deepcopy(company.get("valuation_multiples", {})),
        "consensus": copy.deepcopy(company.get("consensus", {})),
        "model_assumptions": copy.deepcopy(company.get("model_assumptions", {})),
    }
    return with_source(result, payload, DATASET, "model_input_pack", company["ticker"], company)


def _company(ticker: str) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_ticker = normalize_ticker(ticker)
    payload = provider_data(DATASET)
    for company in payload.get("companies", []):
        if normalize_ticker(company.get("ticker", "")) == normalized_ticker:
            return copy.deepcopy(company), payload
    raise FinanceRecordNotFoundError(f"No company data found for ticker {normalized_ticker}")


def _company_summary(company: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "ticker": company["ticker"],
        "company_name": company.get("company_name", ""),
        "sector": company.get("sector", ""),
        "industry": company.get("industry", ""),
        "market": company.get("market", ""),
        "currency": company.get("currency", ""),
    }
    return with_source(summary, payload, DATASET, "company_profile", company["ticker"], company)
