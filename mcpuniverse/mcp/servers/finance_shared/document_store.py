"""Benchmark-world document store for financial-services workflows."""
from __future__ import annotations

import copy
from typing import Any

from .errors import FinanceRecordNotFoundError
from .normalizers import normalize_ticker
from .world_records import provider_data, record_text, with_source

DATASET = "source_documents"


def search_documents(
        query: str = "",
        folder_path: str = "",
        source_type: str = "",
        ticker: str = "",
) -> dict[str, Any]:
    """Search benchmark-world source documents."""
    payload = provider_data(DATASET)
    normalized_query = query.strip().lower()
    normalized_folder = folder_path.strip().lower()
    normalized_source_type = source_type.strip().lower()
    normalized_ticker = normalize_ticker(ticker) if ticker else ""
    records = []
    for document in payload.get("documents", []):
        if normalized_folder and not document.get("folder_path", "").lower().startswith(normalized_folder):
            continue
        if normalized_source_type and document.get("source_type", "").lower() != normalized_source_type:
            continue
        if normalized_ticker and normalized_ticker not in [normalize_ticker(item) for item in document.get("tickers", [])]:
            continue
        if normalized_query and normalized_query not in record_text(document):
            continue
        records.append(_summary(document, payload))
    return {
        "world_id": payload["world_id"],
        "documents": records,
    }


def list_folder(folder_path: str = "") -> dict[str, Any]:
    """List documents under a benchmark-world folder."""
    payload = provider_data(DATASET)
    normalized_folder = folder_path.strip().lower()
    records = [
        _summary(document, payload)
        for document in payload.get("documents", [])
        if not normalized_folder or document.get("folder_path", "").lower().startswith(normalized_folder)
    ]
    return {
        "world_id": payload["world_id"],
        "folder_path": folder_path,
        "documents": records,
    }


def get_document(document_id: str, include_untrusted_text: bool = True) -> dict[str, Any]:
    """Return one benchmark-world source document."""
    normalized_document_id = _required_id(document_id, "document_id")
    payload = provider_data(DATASET)
    for document in payload.get("documents", []):
        if document.get("document_id", "").upper() == normalized_document_id:
            result = copy.deepcopy(document)
            if not include_untrusted_text and "untrusted_text" in result:
                result["untrusted_text"] = ""
            return with_source(
                result,
                payload,
                DATASET,
                source_type=document.get("source_type", "document"),
                source_id=document["document_id"],
                record=document,
                default_trust_level=document.get("source_trust_level", "untrusted_document"),
                authoritative=document.get("source_trust_level", "").startswith("trusted"),
            )
    raise FinanceRecordNotFoundError(f"No document found for document_id {normalized_document_id}")


def get_document_metadata(document_id: str) -> dict[str, Any]:
    """Return metadata for one source document without full text."""
    document = get_document(document_id=document_id, include_untrusted_text=False)
    metadata = {
        key: value
        for key, value in document.items()
        if key not in {"body", "text", "untrusted_text"}
    }
    return metadata


def _summary(document: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "document_id": document["document_id"],
        "title": document.get("title", ""),
        "folder_path": document.get("folder_path", ""),
        "source_type": document.get("source_type", ""),
        "source_trust_level": document.get("source_trust_level", ""),
        "date": document.get("date", ""),
        "tickers": document.get("tickers", []),
    }
    return with_source(
        summary,
        payload,
        DATASET,
        source_type=document.get("source_type", "document"),
        source_id=document["document_id"],
        record=document,
        default_trust_level=document.get("source_trust_level", "untrusted_document"),
        authoritative=document.get("source_trust_level", "").startswith("trusted"),
    )


def _required_id(value: str, name: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip().upper()
