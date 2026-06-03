"""Transactions MCP server for financial-services workflows."""
import json

import click
from mcp.server.fastmcp import FastMCP

from mcpuniverse.common.logger import get_logger
from mcpuniverse.mcp.servers.finance_shared.transaction_data import (
    get_transaction_detail as get_transaction_detail_payload,
    get_transaction_multiples as get_transaction_multiples_payload,
    search_precedent_transactions as search_precedent_transactions_payload,
    summarize_sector_transactions as summarize_sector_transactions_payload,
)


def _json_response(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True)


def build_server(port: int = 8000) -> FastMCP:
    mcp = FastMCP("finance_transactions", port=port)

    @mcp.tool()
    def search_precedent_transactions(query: str = "", sector: str = "", ticker: str = "") -> str:
        """Search precedent transaction records."""
        return _json_response(search_precedent_transactions_payload(query=query, sector=sector, ticker=ticker))

    @mcp.tool()
    def get_transaction_detail(transaction_id: str) -> str:
        """Get one precedent transaction detail record."""
        return _json_response(get_transaction_detail_payload(transaction_id=transaction_id))

    @mcp.tool()
    def get_transaction_multiples(transaction_id: str) -> str:
        """Get transaction valuation multiples."""
        return _json_response(get_transaction_multiples_payload(transaction_id=transaction_id))

    @mcp.tool()
    def summarize_sector_transactions(sector: str) -> str:
        """Summarize transaction activity for a sector."""
        return _json_response(summarize_sector_transactions_payload(sector=sector))

    return mcp


@click.command()
@click.option("--transport", type=click.Choice(["stdio", "sse"]), default="stdio", help="Transport type")
@click.option("--port", default="8000", help="Port to listen on for SSE")
def main(transport: str, port: str):
    assert transport.lower() in ["stdio", "sse"], "Transport should be `stdio` or `sse`"
    logger = get_logger("Service:finance_transactions")
    logger.info("Starting the finance transactions MCP server")
    build_server(int(port)).run(transport=transport.lower())
