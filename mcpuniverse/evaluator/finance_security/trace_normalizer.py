"""Normalize finance MCP traces into evidence summaries."""
import json
from typing import Any

from .types import FinanceToolCall, FinanceTraceSummary


def normalize_trace_records(trace_records: Any) -> FinanceTraceSummary:
    """Normalize raw trace records into finance tool/evidence summaries."""
    summary = FinanceTraceSummary()
    for trace_record in _list_values(trace_records):
        for data_record in _record_values(trace_record):
            data = _data_payload(data_record)
            if not isinstance(data, dict) or data.get("type") != "tool":
                continue
            tool_call = _normalize_tool_call(data)
            summary.tool_calls.append(tool_call)
            _collect_sources_from_payload(tool_call.parsed_response, summary)
    return summary


def _normalize_tool_call(data: dict[str, Any]) -> FinanceToolCall:
    response = data.get("response")
    return FinanceToolCall(
        server=str(data.get("server", "")),
        tool_name=str(data.get("tool_name", "")),
        arguments=_dict_value(data.get("arguments")),
        response=response,
        parsed_response=parse_tool_response(response),
        error=str(data.get("error", "")),
    )


def parse_tool_response(response: Any) -> Any:
    """Parse common MCP response shapes without executing embedded text."""
    if response is None:
        return None
    if hasattr(response, "model_dump"):
        response = response.model_dump(mode="json")
    if hasattr(response, "content"):
        response = {"content": response.content}
    if isinstance(response, dict):
        if "content" in response:
            content = response.get("content") or []
            if content:
                first_item = content[0]
                if hasattr(first_item, "text"):
                    return _parse_json_text(first_item.text)
                if isinstance(first_item, dict) and "text" in first_item:
                    return _parse_json_text(first_item["text"])
        return response
    if isinstance(response, list):
        return [parse_tool_response(item) for item in response]
    if isinstance(response, str):
        return _parse_json_text(response)
    return response


def _parse_json_text(text: str) -> Any:
    stripped_text = text.strip().strip("`").strip()
    if stripped_text.startswith("json"):
        stripped_text = stripped_text[4:].strip()
    if not stripped_text:
        return ""
    try:
        return json.loads(stripped_text)
    except json.JSONDecodeError:
        return text


def _collect_sources_from_payload(payload: Any, summary: FinanceTraceSummary) -> None:
    if isinstance(payload, dict):
        data_source = payload.get("data_source")
        if isinstance(data_source, dict):
            _append_data_source(summary, data_source)
        for nested_data_source in payload.get("data_sources", []):
            if isinstance(nested_data_source, dict):
                _append_data_source(summary, nested_data_source)
        evidence = payload.get("evidence")
        if isinstance(evidence, dict):
            _append_evidence(summary, evidence)
        elif isinstance(evidence, list):
            for evidence_record in evidence:
                if isinstance(evidence_record, dict):
                    _append_evidence(summary, evidence_record)
        for value in payload.values():
            _collect_sources_from_payload(value, summary)
    elif isinstance(payload, list):
        for item in payload:
            _collect_sources_from_payload(item, summary)


def _append_evidence(summary: FinanceTraceSummary, evidence_record: dict[str, Any]) -> None:
    _append_unique_dict(summary.evidence, evidence_record, "evidence_id")
    data_source = evidence_record.get("data_source")
    if isinstance(data_source, dict):
        _append_data_source(summary, data_source)
    trust_level = str(evidence_record.get("source_trust_level", "")).lower()
    if "untrusted" in trust_level:
        summary.untrusted_evidence_seen = True
    if "trusted" in trust_level and "untrusted" not in trust_level:
        summary.trusted_evidence_seen = True


def _append_data_source(summary: FinanceTraceSummary, data_source: dict[str, Any]) -> None:
    _append_unique_dict(summary.data_sources, data_source, "data_source_id")
    world_id = str(data_source.get("world_id", "")).strip()
    if world_id and world_id not in summary.world_ids:
        summary.world_ids.append(world_id)
    data_source_type = str(data_source.get("data_source_type", "")).strip()
    if data_source_type and data_source_type not in summary.data_source_types:
        summary.data_source_types.append(data_source_type)


def _append_unique_dict(records: list[dict[str, Any]], record: dict[str, Any], key: str) -> None:
    record_key = record.get(key)
    if record_key and any(existing.get(key) == record_key for existing in records):
        return
    records.append(record)


def _record_values(trace_record: Any) -> list[Any]:
    if isinstance(trace_record, dict):
        return _list_values(trace_record.get("records", []))
    return _list_values(getattr(trace_record, "records", []))


def _data_payload(data_record: Any) -> Any:
    if isinstance(data_record, dict):
        return data_record.get("data", data_record)
    return getattr(data_record, "data", data_record)


def _list_values(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
