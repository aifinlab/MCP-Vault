"""Subledger MCP server for financial-services workflows."""
import json

import click
from mcp.server.fastmcp import FastMCP

from mcpuniverse.common.logger import get_logger
from mcpuniverse.mcp.servers.finance_shared.enterprise_data import (
    compare_gl_subledger_records as compare_gl_subledger_records_payload,
    get_trade_lifecycle as get_trade_lifecycle_payload,
    list_subledger_positions as list_subledger_positions_payload,
    list_subledger_transactions as list_subledger_transactions_payload,
    trace_recon_break as trace_recon_break_payload,
)


def _json_response(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True)


def build_server(port: int = 8000) -> FastMCP:
    """
    Initializes the finance subledger MCP server.

    :param port: Port for SSE.
    :return: The MCP server.
    """
    mcp = FastMCP("finance_subledger", port=port)

    @mcp.tool()
    def list_subledger_positions(as_of_date: str = "", asset_class: str = "") -> str:
        """
        List trusted subledger positions.

        Args:
            as_of_date: Optional position date in YYYY-MM-DD format.
            asset_class: Optional asset class filter.
        """
        return _json_response(list_subledger_positions_payload(as_of_date=as_of_date, asset_class=asset_class))

    @mcp.tool()
    def list_subledger_transactions(trade_date: str = "", asset_class: str = "") -> str:
        """
        List trusted subledger transactions.

        Args:
            trade_date: Optional trade date in YYYY-MM-DD format.
            asset_class: Optional asset class filter.
        """
        return _json_response(list_subledger_transactions_payload(trade_date=trade_date, asset_class=asset_class))

    @mcp.tool()
    def get_trade_lifecycle(trade_id: str) -> str:
        """
        Get one trusted trade lifecycle.

        Args:
            trade_id: Trade identifier.
        """
        return _json_response(get_trade_lifecycle_payload(trade_id=trade_id))

    @mcp.tool()
    def compare_gl_subledger_records(entity_id: str, period: str, asset_class: str = "") -> str:
        """
        Compare trusted GL and subledger records.

        Args:
            entity_id: Entity identifier.
            period: Accounting period.
            asset_class: Optional asset class filter.
        """
        return _json_response(
            compare_gl_subledger_records_payload(entity_id=entity_id, period=period, asset_class=asset_class)
        )

    @mcp.tool()
    def trace_recon_break(break_id: str) -> str:
        """
        Trace a reconciliation break to source GL/subledger records.

        Args:
            break_id: Reconciliation break identifier.
        """
        return _json_response(trace_recon_break_payload(break_id=break_id))

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
    Starts the finance subledger MCP server.

    :param port: Port for SSE.
    :param transport: The transport type, e.g., `stdio` or `sse`.
    """
    assert transport.lower() in ["stdio", "sse"], "Transport should be `stdio` or `sse`"
    logger = get_logger("Service:finance_subledger")
    logger.info("Starting the finance subledger MCP server")
    mcp = build_server(int(port))
    mcp.run(transport=transport.lower())
