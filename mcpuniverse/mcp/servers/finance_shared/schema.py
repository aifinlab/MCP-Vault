"""Shared response schema helpers for finance MCP tools."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

LIVE_PROVIDER_SOURCE_TYPE = "live_provider"
BENCHMARK_WORLD_SOURCE_TYPE = "benchmark_world"
TASK_MATERIAL_SOURCE_TYPE = "task_material"

TRUSTED_INTERNAL_SYSTEM = "trusted_internal_system"
TRUSTED_LIVE_PROVIDER = "trusted_live_provider"
TRUSTED_REGULATORY_FILING = "trusted_regulatory_filing"
TRUSTED_DETERMINISTIC_PROVIDER = "trusted_deterministic_provider"
TASK_POLICY_CONTRACT = "task_policy_contract"
UNTRUSTED_DOCUMENT = "untrusted_document"
UNTRUSTED_RESEARCH = "untrusted_research"
UNTRUSTED_EMAIL = "untrusted_email"
UNTRUSTED_COUNTERPARTY = "untrusted_counterparty"
UNTRUSTED_GP_PACKAGE = "untrusted_gp_package"
MIXED_TRUST = "mixed"

STANDARD_SOURCE_TRUST_LEVELS = {
    TRUSTED_INTERNAL_SYSTEM,
    TRUSTED_LIVE_PROVIDER,
    TRUSTED_REGULATORY_FILING,
    TRUSTED_DETERMINISTIC_PROVIDER,
    TASK_POLICY_CONTRACT,
    UNTRUSTED_DOCUMENT,
    UNTRUSTED_RESEARCH,
    UNTRUSTED_EMAIL,
    UNTRUSTED_COUNTERPARTY,
    UNTRUSTED_GP_PACKAGE,
    MIXED_TRUST,
}


def make_live_data_source(
        provider: str,
        dataset: str,
        data_date: str,
        payload_sha256: str,
        ticker: str = "",
        series_id: str = "",
) -> dict[str, Any]:
    """Build the canonical live-provider data source object."""
    data_source = {
        "data_source_id": _live_data_source_id(provider, dataset, data_date, ticker=ticker, series_id=series_id),
        "data_source_type": LIVE_PROVIDER_SOURCE_TYPE,
        "provider": provider,
        "dataset": dataset,
        "data_date": data_date,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "payload_sha256": payload_sha256,
    }
    if ticker:
        data_source["ticker"] = ticker
    if series_id:
        data_source["series_id"] = series_id
    return data_source


def derive_live_data_source(
        source: dict[str, Any],
        dataset: str,
        data_date: str,
        ticker: str = "",
        series_id: str = "",
) -> dict[str, Any]:
    """Create a derived live data source while preserving retrieval metadata."""
    data_source = normalize_data_source(source)
    resolved_ticker = ticker or data_source.get("ticker", "")
    resolved_series_id = series_id or data_source.get("series_id", "")
    data_source["data_source_id"] = _live_data_source_id(
        data_source["provider"],
        dataset,
        data_date,
        ticker=resolved_ticker,
        series_id=resolved_series_id,
    )
    data_source["data_source_type"] = LIVE_PROVIDER_SOURCE_TYPE
    data_source["dataset"] = dataset
    data_source["data_date"] = data_date
    if resolved_ticker:
        data_source["ticker"] = resolved_ticker
    if resolved_series_id:
        data_source["series_id"] = resolved_series_id
    return data_source


def make_task_material_data_source(world_id: str, dataset: str) -> dict[str, Any]:
    """Build the canonical task-material data source object."""
    return {
        "data_source_id": f"{TASK_MATERIAL_SOURCE_TYPE}:{world_id}:{dataset}",
        "data_source_type": TASK_MATERIAL_SOURCE_TYPE,
        "world_id": world_id,
        "dataset": dataset,
    }


def make_world_data_source(
        world_id: str,
        dataset: str,
        payload_sha256: str,
        provider: str = "deterministic",
) -> dict[str, Any]:
    """Build the canonical benchmark-world data source object."""
    return {
        "data_source_id": f"benchmark_world:{world_id}:{dataset}",
        "data_source_type": BENCHMARK_WORLD_SOURCE_TYPE,
        "world_id": world_id,
        "dataset": dataset,
        "provider": provider,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "payload_sha256": payload_sha256,
    }


def make_evidence_record(
        evidence_type: str,
        source_type: str,
        source_id: str,
        source_trust_level: str,
        data_source: dict[str, Any],
        locator: str = "",
        authoritative: bool = False,
        citation: str = "",
) -> dict[str, Any]:
    """Build one canonical evidence record."""
    source_trust_level = normalize_source_trust_level(source_trust_level)
    normalized_data_source = normalize_data_source(data_source)
    evidence = {
        "evidence_id": _evidence_id(normalized_data_source, source_id),
        "evidence_type": evidence_type,
        "source_id": source_id,
        "source_type": source_type,
        "source_trust_level": source_trust_level,
        "authoritative": authoritative,
        "data_source": normalized_data_source,
    }
    if locator:
        evidence["locator"] = locator
    if citation:
        evidence["citation"] = citation
    return evidence


def make_business_evidence_record(
        world_id: str,
        dataset: str,
        source_type: str,
        source_id: str,
        source_trust_level: str = TRUSTED_INTERNAL_SYSTEM,
) -> dict[str, Any]:
    """Build evidence for a trusted local business-system record."""
    return make_world_evidence_record(
        world_id=world_id,
        dataset=dataset,
        source_type=source_type,
        source_id=source_id,
        source_trust_level=source_trust_level,
        payload_sha256="",
        provider="deterministic",
        authoritative=True,
    )


def make_task_evidence_record(
        world_id: str,
        dataset: str,
        source_type: str,
        source_id: str,
        source_trust_level: str,
        locator: str = "",
) -> dict[str, Any]:
    """Build evidence for task-local documents or policy contracts."""
    return make_evidence_record(
        evidence_type="task_record",
        source_type=source_type,
        source_id=source_id,
        source_trust_level=source_trust_level,
        data_source=make_task_material_data_source(world_id=world_id, dataset=dataset),
        locator=locator,
    )


def make_world_evidence_record(
        world_id: str,
        dataset: str,
        source_type: str,
        source_id: str,
        source_trust_level: str,
        payload_sha256: str,
        provider: str = "deterministic",
        locator: str = "",
        authoritative: bool = False,
        citation: str = "",
) -> dict[str, Any]:
    """Build evidence for benchmark-world business/provider records."""
    return make_evidence_record(
        evidence_type="world_record",
        source_type=source_type,
        source_id=source_id,
        source_trust_level=source_trust_level,
        data_source=make_world_data_source(
            world_id=world_id,
            dataset=dataset,
            payload_sha256=payload_sha256,
            provider=provider,
        ),
        locator=locator,
        authoritative=authoritative,
        citation=citation,
    )


def normalize_data_source(data_source: dict[str, Any]) -> dict[str, Any]:
    """Normalize legacy source objects into the canonical finance schema."""
    normalized = copy.deepcopy(data_source)
    if "data_source_id" not in normalized and normalized.get("id"):
        normalized["data_source_id"] = normalized["id"]
    normalized.pop("id", None)
    if "data_source_type" not in normalized:
        mode = normalized.pop("mode", "")
        normalized["data_source_type"] = LIVE_PROVIDER_SOURCE_TYPE if mode == "live" else mode
    return normalized


def validate_source_trust_level(source_trust_level: str) -> None:
    """Validate the standard finance source trust vocabulary."""
    if source_trust_level not in STANDARD_SOURCE_TRUST_LEVELS:
        raise ValueError(f"Unsupported source_trust_level: {source_trust_level}")


def normalize_source_trust_level(source_trust_level: str) -> str:
    """Normalize legacy trust labels into the standard finance vocabulary."""
    normalized = (source_trust_level or "").strip().lower()
    aliases = {
        "trusted": TRUSTED_DETERMINISTIC_PROVIDER,
        "trusted_internal": TRUSTED_INTERNAL_SYSTEM,
        "trusted_internal_model": TRUSTED_INTERNAL_SYSTEM,
        "trusted_company_release": TRUSTED_LIVE_PROVIDER,
        "trusted_company_transcript": TRUSTED_LIVE_PROVIDER,
        "trusted_consensus_dataset": TRUSTED_DETERMINISTIC_PROVIDER,
        "untrusted": UNTRUSTED_DOCUMENT,
        "untrusted_external_text": UNTRUSTED_DOCUMENT,
        "unapproved_draft": UNTRUSTED_RESEARCH,
        "unapproved_draft_untrusted": UNTRUSTED_RESEARCH,
        "gp_provided_untrusted": UNTRUSTED_GP_PACKAGE,
    }
    normalized = aliases.get(normalized, normalized)
    validate_source_trust_level(normalized)
    return normalized


def data_source_key(data_source: dict[str, Any]) -> str:
    """Return the canonical unique key for a data source."""
    normalized = normalize_data_source(data_source)
    return normalized.get("data_source_id", "")


def collect_evidence(*payloads: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect and deduplicate canonical evidence records from payloads."""
    evidence_records = []
    seen = set()
    for payload in payloads:
        for record in _evidence_list(payload.get("evidence")):
            evidence_id = record.get("evidence_id")
            if evidence_id in seen:
                continue
            seen.add(evidence_id)
            evidence_records.append(record)
    return evidence_records


def _evidence_list(evidence: Any) -> list[dict[str, Any]]:
    if not evidence:
        return []
    if isinstance(evidence, dict):
        return [copy.deepcopy(evidence)]
    return [copy.deepcopy(record) for record in evidence]


def _live_data_source_id(provider: str, dataset: str, data_date: str, ticker: str = "", series_id: str = "") -> str:
    if ticker:
        return f"live:{provider}:{dataset}:{ticker}:{data_date}"
    if series_id:
        return f"live:{provider}:{dataset}:{series_id}:{data_date}"
    return f"live:{provider}:{dataset}:{data_date}"


def _evidence_id(data_source: dict[str, Any], source_id: str) -> str:
    return f"{data_source['data_source_id']}:{source_id}"
