"""CRM MCP server for financial-services workflows."""
import json

import click
from mcp.server.fastmcp import FastMCP

from mcpuniverse.common.logger import get_logger
from mcpuniverse.mcp.servers.finance_shared.enterprise_data import (
    get_client_record as get_client_record_payload,
    get_meeting_context as get_meeting_context_payload,
    list_client_interactions as list_client_interactions_payload,
    list_follow_ups as list_follow_ups_payload,
    list_meetings as list_meetings_payload,
    search_clients as search_clients_payload,
)


def _json_response(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True)


def build_server(port: int = 8000) -> FastMCP:
    """
    Initializes the finance CRM MCP server.

    :param port: Port for SSE.
    :return: The MCP server.
    """
    mcp = FastMCP("finance_crm", port=port)

    @mcp.tool()
    def search_clients(query: str = "", segment: str = "", advisor_id: str = "") -> str:
        """
        Search trusted CRM client records.

        Args:
            query: Optional text filter.
            segment: Optional client segment filter.
            advisor_id: Optional advisor identifier.
        """
        return _json_response(search_clients_payload(query=query, segment=segment, advisor_id=advisor_id))

    @mcp.tool()
    def get_client_record(client_id: str) -> str:
        """
        Get one trusted CRM client record.

        Args:
            client_id: Client identifier, e.g. "CLIENT-FS-0001".
        """
        return _json_response(get_client_record_payload(client_id=client_id))

    @mcp.tool()
    def list_client_interactions(client_id: str, start_date: str = "", end_date: str = "") -> str:
        """
        List trusted CRM interactions for a client.

        Args:
            client_id: Client identifier.
            start_date: Optional start date in YYYY-MM-DD format.
            end_date: Optional end date in YYYY-MM-DD format.
        """
        return _json_response(
            list_client_interactions_payload(client_id=client_id, start_date=start_date, end_date=end_date)
        )

    @mcp.tool()
    def list_meetings(client_id: str = "", start_date: str = "", end_date: str = "") -> str:
        """
        List trusted CRM meetings.

        Args:
            client_id: Optional client identifier.
            start_date: Optional start date in YYYY-MM-DD format.
            end_date: Optional end date in YYYY-MM-DD format.
        """
        return _json_response(list_meetings_payload(client_id=client_id, start_date=start_date, end_date=end_date))

    @mcp.tool()
    def get_meeting_context(meeting_id: str) -> str:
        """
        Get trusted CRM context for one meeting.

        Args:
            meeting_id: Meeting identifier.
        """
        return _json_response(get_meeting_context_payload(meeting_id=meeting_id))

    @mcp.tool()
    def list_follow_ups(client_id: str = "", status: str = "") -> str:
        """
        List trusted CRM follow-up records.

        Args:
            client_id: Optional client identifier.
            status: Optional follow-up status.
        """
        return _json_response(list_follow_ups_payload(client_id=client_id, status=status))

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
    Starts the finance CRM MCP server.

    :param port: Port for SSE.
    :param transport: The transport type, e.g., `stdio` or `sse`.
    """
    assert transport.lower() in ["stdio", "sse"], "Transport should be `stdio` or `sse`"
    logger = get_logger("Service:finance_crm")
    logger.info("Starting the finance CRM MCP server")
    mcp = build_server(int(port))
    mcp.run(transport=transport.lower())
