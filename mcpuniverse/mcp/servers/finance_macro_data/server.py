"""Macro-data MCP server for financial-services tasks."""
import json

import click
from mcp.server.fastmcp import FastMCP

from mcpuniverse.common.logger import get_logger
from mcpuniverse.mcp.servers.finance_shared.macro_data import (
    get_macro_observation as get_macro_observation_payload,
    get_macro_series as get_macro_series_payload,
    search_macro_series as search_macro_series_payload,
)


def _json_response(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True)


def build_server(port: int = 8000) -> FastMCP:
    """
    Initializes the finance macro-data MCP server.

    :param port: Port for SSE.
    :return: The MCP server.
    """
    mcp = FastMCP("finance_macro_data", port=port)

    @mcp.tool()
    def search_macro_series(query: str, region: str = "") -> str:
        """
        Search configured live macro series metadata.

        Args:
            query: Case-insensitive search text, e.g. "CPI" or "rate".
            region: Optional region filter, either "US" or "CN".
        """
        return _json_response(search_macro_series_payload(query=query, region=region))

    @mcp.tool()
    def get_macro_series(series_id: str, start_date: str, end_date: str) -> str:
        """
        Get live macro observations for a configured series.

        Args:
            series_id: Macro series id, e.g. "FEDFUNDS" or "CN_CPI".
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format.
        """
        return _json_response(
            get_macro_series_payload(series_id=series_id, start_date=start_date, end_date=end_date)
        )

    @mcp.tool()
    def get_macro_observation(series_id: str, as_of_date: str = "") -> str:
        """
        Get the latest live macro observation on or before as_of_date.

        Args:
            series_id: Macro series id, e.g. "FEDFUNDS" or "CN_CPI".
            as_of_date: Optional YYYY-MM-DD date. If omitted, uses the current UTC date.
        """
        return _json_response(get_macro_observation_payload(series_id=series_id, as_of_date=as_of_date))

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
    Starts the finance macro-data MCP server.

    :param port: Port for SSE.
    :param transport: The transport type, e.g., `stdio` or `sse`.
    """
    assert transport.lower() in ["stdio", "sse"], "Transport should be `stdio` or `sse`"
    logger = get_logger("Service:finance_macro_data")
    logger.info("Starting the finance macro-data MCP server")
    mcp = build_server(int(port))
    mcp.run(transport=transport.lower())
