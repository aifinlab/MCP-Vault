"""Audit MCP server for financial-services tasks."""
import json

import click
from mcp.server.fastmcp import FastMCP

from mcpuniverse.common.logger import get_logger
from mcpuniverse.mcp.servers.finance_shared.calculations import (
    explain_decision_context as explain_decision_context_payload,
)
from mcpuniverse.mcp.servers.finance_shared.data_loader import (
    get_audit_event as get_audit_event_payload,
    get_policy_reference,
    list_audit_events as list_audit_events_payload,
    list_policy_references as list_policy_references_payload,
)


def _json_response(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True)


def build_server(port: int = 8000) -> FastMCP:
    """
    Initializes the finance audit MCP server.

    :param port: Port for SSE.
    :return: The MCP server.
    """
    mcp = FastMCP("finance_audit", port=port)

    @mcp.tool()
    def list_audit_events(account_id: str = "", event_type: str = "", limit: int = 10) -> str:
        """
        List local business audit events with optional filters.

        Args:
            account_id: Optional account identifier, e.g. "ACC-FS-0001".
            event_type: Optional event type, e.g. "policy_check".
            limit: Maximum number of events to return.
        """
        return _json_response(
            list_audit_events_payload(
                account_id=account_id,
                event_type=event_type,
                limit=limit,
            )
        )

    @mcp.tool()
    def get_audit_event(event_id: str) -> str:
        """
        Get one local business audit event by id.

        Args:
            event_id: Audit event identifier, e.g. "AUD-20260515-SYN-0001".
        """
        return _json_response(get_audit_event_payload(event_id=event_id))

    @mcp.tool()
    def explain_policy_reference(policy_code: str) -> str:
        """
        Explain a task-local policy reference by policy code.

        Args:
            policy_code: Policy code, e.g. "NO_SINGLE_NAME_GT_25".
        """
        return _json_response(get_policy_reference(policy_code=policy_code))

    @mcp.tool()
    def list_policy_references(policy_area: str = "") -> str:
        """
        List task-local policy references with optional policy-area filtering.

        Args:
            policy_area: Optional policy area, e.g. "trading", "suitability", or "research".
        """
        return _json_response(list_policy_references_payload(policy_area=policy_area or None))

    @mcp.tool()
    def explain_decision_context(account_id: str, ticker: str = "", policy_code: str = "") -> str:
        """
        Explain account state and task-local policy evidence for a decision.

        Args:
            account_id: Account identifier, e.g. "ACC-FS-0001".
            ticker: Optional tradable symbol, e.g. "AAPL".
            policy_code: Optional policy code, e.g. "NO_SINGLE_NAME_GT_25".
        """
        return _json_response(
            explain_decision_context_payload(
                account_id=account_id,
                ticker=ticker,
                policy_code=policy_code,
            )
        )

    return mcp


@click.command()
@click.option(
    "--transport",
    type=click.Choice(["stdio", "sse"]),
    default="stdio",
    help="Transport type",
)
@click.option("--port", default="8000", help="Port to listen on for SSE")
def main(transport: str, port: str):
    """
    Starts the finance audit MCP server.

    :param port: Port for SSE.
    :param transport: The transport type, e.g., `stdio` or `sse`.
    """
    assert transport.lower() in ["stdio", "sse"], "Transport should be `stdio` or `sse`"
    logger = get_logger("Service:finance_audit")
    logger.info("Starting the finance audit MCP server")
    mcp = build_server(int(port))
    mcp.run(transport=transport.lower())
