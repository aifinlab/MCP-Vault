"""Helpers for benchmark-world business and deterministic-provider records."""
from __future__ import annotations

import copy
import json
from typing import Any

from .data_loader import load_business_state, load_provider_data
from .schema import make_world_data_source, make_world_evidence_record


DETERMINISTIC_PROVIDER = "deterministic"


def business_state(dataset_name: str) -> dict[str, Any]:
    """Load a benchmark-world business-state dataset."""
    return load_business_state(dataset_name)


def provider_data(dataset_name: str) -> dict[str, Any]:
    """Load a benchmark-world deterministic provider dataset."""
    return load_provider_data(dataset_name)


def payload_data_source(
        payload: dict[str, Any],
        dataset_name: str,
        provider: str = DETERMINISTIC_PROVIDER,
) -> dict[str, Any]:
    """Return the canonical data source for a world dataset payload."""
    return make_world_data_source(
        world_id=payload["world_id"],
        dataset=dataset_name,
        payload_sha256=payload["payload_sha256"],
        provider=provider,
    )


def record_evidence(
        payload: dict[str, Any],
        dataset_name: str,
        source_type: str,
        source_id: str,
        record: dict[str, Any] | None = None,
        default_trust_level: str = "trusted_deterministic_provider",
        provider: str = DETERMINISTIC_PROVIDER,
        authoritative: bool = True,
) -> list[dict[str, Any]]:
    """Return one canonical evidence record for a world record."""
    record = record or {}
    return [
        make_world_evidence_record(
            world_id=payload["world_id"],
            dataset=dataset_name,
            source_type=source_type,
            source_id=source_id,
            source_trust_level=record.get("source_trust_level", default_trust_level),
            payload_sha256=payload["payload_sha256"],
            provider=provider,
            locator=record.get("locator", record.get("url", "")),
            authoritative=bool(record.get("authoritative", authoritative)),
            citation=record.get("citation", ""),
        )
    ]


def with_source(
        result: dict[str, Any],
        payload: dict[str, Any],
        dataset_name: str,
        source_type: str,
        source_id: str,
        record: dict[str, Any] | None = None,
        default_trust_level: str = "trusted_deterministic_provider",
        provider: str = DETERMINISTIC_PROVIDER,
        authoritative: bool = True,
) -> dict[str, Any]:
    """Attach world id, data source, and evidence to a result."""
    result = copy.deepcopy(result)
    result["world_id"] = payload["world_id"]
    result["data_source"] = payload_data_source(payload, dataset_name, provider=provider)
    result["evidence"] = record_evidence(
        payload=payload,
        dataset_name=dataset_name,
        source_type=source_type,
        source_id=source_id,
        record=record,
        default_trust_level=default_trust_level,
        provider=provider,
        authoritative=authoritative,
    )
    return result


def record_text(record: dict[str, Any]) -> str:
    """Return a lower-case text representation for simple search filters."""
    return json.dumps(record, sort_keys=True, default=str).lower()


def copy_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deep-copy a list of JSON records."""
    return [copy.deepcopy(record) for record in records]
