"""Benchmark-world transaction data for comps and pitch workflows."""
from __future__ import annotations

import copy
from statistics import median
from typing import Any

from .errors import FinanceRecordNotFoundError
from .normalizers import normalize_ticker
from .world_records import provider_data, record_text, with_source

DATASET = "transactions"


def search_precedent_transactions(
        query: str = "",
        sector: str = "",
        ticker: str = "",
) -> dict[str, Any]:
    """Search precedent M&A and financing transactions."""
    payload = provider_data(DATASET)
    normalized_query = query.strip().lower()
    normalized_sector = sector.strip().lower()
    normalized_ticker = normalize_ticker(ticker) if ticker else ""
    records = []
    for transaction in payload.get("transactions", []):
        tickers = [normalize_ticker(item) for item in transaction.get("tickers", [])]
        if normalized_sector and transaction.get("sector", "").lower() != normalized_sector:
            continue
        if normalized_ticker and normalized_ticker not in tickers:
            continue
        if normalized_query and normalized_query not in record_text(transaction):
            continue
        records.append(_summary(transaction, payload))
    return {"world_id": payload["world_id"], "transactions": records}


def get_transaction_detail(transaction_id: str) -> dict[str, Any]:
    """Return one transaction detail record."""
    transaction, payload = _transaction(transaction_id)
    return with_source(
        transaction,
        payload,
        DATASET,
        "precedent_transaction",
        transaction["transaction_id"],
        transaction,
    )


def get_transaction_multiples(transaction_id: str) -> dict[str, Any]:
    """Return transaction valuation multiples."""
    transaction, payload = _transaction(transaction_id)
    result = {
        "transaction_id": transaction["transaction_id"],
        "target": transaction.get("target", ""),
        "acquirer": transaction.get("acquirer", ""),
        "announcement_date": transaction.get("announcement_date", ""),
        "enterprise_value": transaction.get("enterprise_value"),
        "multiples": copy.deepcopy(transaction.get("multiples", {})),
    }
    return with_source(result, payload, DATASET, "transaction_multiples", transaction["transaction_id"], transaction)


def summarize_sector_transactions(sector: str) -> dict[str, Any]:
    """Summarize transaction activity for a sector."""
    if not sector or not sector.strip():
        raise ValueError("sector is required")
    payload = provider_data(DATASET)
    normalized_sector = sector.strip().lower()
    records = [
        copy.deepcopy(transaction)
        for transaction in payload.get("transactions", [])
        if transaction.get("sector", "").lower() == normalized_sector
    ]
    ev_ebitda_values = [
        float(transaction.get("multiples", {}).get("ev_ebitda"))
        for transaction in records
        if transaction.get("multiples", {}).get("ev_ebitda") is not None
    ]
    result = {
        "sector": sector,
        "transaction_count": len(records),
        "median_ev_ebitda": median(ev_ebitda_values) if ev_ebitda_values else None,
        "transactions": [_summary(record, payload) for record in records],
    }
    return with_source(result, payload, DATASET, "sector_transactions", sector.strip().lower(), records[0] if records else {})


def _transaction(transaction_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if not transaction_id or not transaction_id.strip():
        raise ValueError("transaction_id is required")
    normalized_transaction_id = transaction_id.strip().upper()
    payload = provider_data(DATASET)
    for transaction in payload.get("transactions", []):
        if transaction.get("transaction_id", "").upper() == normalized_transaction_id:
            return copy.deepcopy(transaction), payload
    raise FinanceRecordNotFoundError(f"No transaction found for transaction_id {normalized_transaction_id}")


def _summary(transaction: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "transaction_id": transaction["transaction_id"],
        "target": transaction.get("target", ""),
        "acquirer": transaction.get("acquirer", ""),
        "sector": transaction.get("sector", ""),
        "announcement_date": transaction.get("announcement_date", ""),
        "enterprise_value": transaction.get("enterprise_value"),
        "multiples": copy.deepcopy(transaction.get("multiples", {})),
    }
    return with_source(summary, payload, DATASET, "precedent_transaction", transaction["transaction_id"], transaction)
