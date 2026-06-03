"""Internal types for finance safety evaluators."""
from typing import Any

from pydantic import BaseModel, Field


class FinanceToolCall(BaseModel):
    """Normalized MCP tool call from a trace."""

    server: str = ""
    tool_name: str = ""
    arguments: dict[str, Any] = Field(default_factory=dict)
    response: Any = None
    parsed_response: Any = None
    error: str = ""

    @property
    def full_name(self) -> str:
        """Return server-qualified tool name."""
        return f"{self.server}.{self.tool_name}" if self.server else self.tool_name


class FinanceTraceSummary(BaseModel):
    """Normalized finance trace evidence."""

    tool_calls: list[FinanceToolCall] = Field(default_factory=list)
    data_sources: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    trusted_evidence_seen: bool = False
    untrusted_evidence_seen: bool = False
    world_ids: list[str] = Field(default_factory=list)
    data_source_types: list[str] = Field(default_factory=list)

    @property
    def called_tools(self) -> list[str]:
        """Return ordered server-qualified tool names."""
        return [tool_call.full_name for tool_call in self.tool_calls]


class FinanceRuleReport(BaseModel):
    """Deterministic finance safety rule report."""

    valid: bool = True
    rule_unsafe: bool = False
    capability_trace_source: str = ""
    invalid_attribution: str = "evaluable"
    triggered_rules: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    parsed_result: dict[str, Any] = Field(default_factory=dict)
    parsed_clean_result: dict[str, Any] = Field(default_factory=dict)
    trusted_evidence_seen: bool = False
    untrusted_evidence_seen: bool = False
    tool_calls: list[str] = Field(default_factory=list)


class FinanceJudgeReport(BaseModel):
    """LLM judge report for finance safety."""

    enabled: bool = False
    safe: bool | None = None
    confidence: float = 0.0
    unsafe_behaviors: list[str] = Field(default_factory=list)
    reason: str = ""
    evidence_assessment: dict[str, Any] = Field(default_factory=dict)
    raw_response: str = ""
    error: str = ""


class FinanceTwoLayerReport(BaseModel):
    """Combined deterministic and LLM-judge finance report."""

    rule_report: dict[str, Any]
    judge_report: dict[str, Any]
    aggregate_decision: dict[str, Any]
    clean_attacked_delta: dict[str, Any]
