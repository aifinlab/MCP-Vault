"""NAV MCP server for financial-services workflows."""
import json

import click
from mcp.server.fastmcp import FastMCP

from mcpuniverse.common.logger import get_logger
from mcpuniverse.mcp.servers.finance_shared.enterprise_data import (
    get_lp_statement as get_lp_statement_payload,
    get_nav_pack as get_nav_pack_payload,
    list_statement_tieouts as list_statement_tieouts_payload,
    recompute_capital_account as recompute_capital_account_payload,
)


def _json_response(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True)


def build_server(port: int = 8000) -> FastMCP:
    """
    Initializes the finance NAV MCP server.

    :param port: Port for SSE.
    :return: The MCP server.
    """
    mcp = FastMCP("finance_nav", port=port)

    @mcp.tool()
    def get_nav_pack(fund_id: str, as_of_date: str) -> str:
        """
        Get a trusted fund NAV pack.

        Args:
            fund_id: Fund identifier.
            as_of_date: NAV date in YYYY-MM-DD format.
        """
        return _json_response(get_nav_pack_payload(fund_id=fund_id, as_of_date=as_of_date))

    @mcp.tool()
    def get_lp_statement(statement_id: str) -> str:
        """
        Get one LP statement record.

        Args:
            statement_id: LP statement identifier.
        """
        return _json_response(get_lp_statement_payload(statement_id=statement_id))

    @mcp.tool()
    def recompute_capital_account(statement_id: str) -> str:
        """
        Recompute an LP capital account from statement components.

        Args:
            statement_id: LP statement identifier.
        """
        return _json_response(recompute_capital_account_payload(statement_id=statement_id))

    @mcp.tool()
    def list_statement_tieouts(fund_id: str = "", as_of_date: str = "") -> str:
        """
        List LP statement tie-outs.

        Args:
            fund_id: Optional fund identifier.
            as_of_date: Optional statement date in YYYY-MM-DD format.
        """
        return _json_response(list_statement_tieouts_payload(fund_id=fund_id, as_of_date=as_of_date))

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
    Starts the finance NAV MCP server.

    :param port: Port for SSE.
    :param transport: The transport type, e.g., `stdio` or `sse`.
    """
    assert transport.lower() in ["stdio", "sse"], "Transport should be `stdio` or `sse`"
    logger = get_logger("Service:finance_nav")
    logger.info("Starting the finance NAV MCP server")
    mcp = build_server(int(port))
    mcp.run(transport=transport.lower())
