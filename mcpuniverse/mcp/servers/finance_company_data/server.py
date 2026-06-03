"""Company-data MCP server for financial-services workflows."""
import json

import click
from mcp.server.fastmcp import FastMCP

from mcpuniverse.common.logger import get_logger
from mcpuniverse.mcp.servers.finance_shared.company_data import (
    get_capital_structure as get_capital_structure_payload,
    get_model_input_pack as get_model_input_pack_payload,
    get_segment_financials as get_segment_financials_payload,
    get_standardized_financials as get_standardized_financials_payload,
    get_wacc_inputs as get_wacc_inputs_payload,
    search_companies as search_companies_payload,
)


def _json_response(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True)


def build_server(port: int = 8000) -> FastMCP:
    mcp = FastMCP("finance_company_data", port=port)

    @mcp.tool()
    def search_companies(query: str = "", sector: str = "", market: str = "") -> str:
        """Search deterministic company records."""
        return _json_response(search_companies_payload(query=query, sector=sector, market=market))

    @mcp.tool()
    def get_standardized_financials(ticker: str, statement_type: str = "", period: str = "") -> str:
        """Get standardized financial statements for a ticker."""
        return _json_response(get_standardized_financials_payload(ticker=ticker, statement_type=statement_type, period=period))

    @mcp.tool()
    def get_segment_financials(ticker: str, period: str = "") -> str:
        """Get segment-level financials for a ticker."""
        return _json_response(get_segment_financials_payload(ticker=ticker, period=period))

    @mcp.tool()
    def get_capital_structure(ticker: str, as_of_date: str = "") -> str:
        """Get capital structure inputs for a ticker."""
        return _json_response(get_capital_structure_payload(ticker=ticker, as_of_date=as_of_date))

    @mcp.tool()
    def get_wacc_inputs(ticker: str, as_of_date: str = "") -> str:
        """Get WACC inputs for a ticker."""
        return _json_response(get_wacc_inputs_payload(ticker=ticker, as_of_date=as_of_date))

    @mcp.tool()
    def get_model_input_pack(ticker: str, model_type: str = "") -> str:
        """Get a compact modeling input pack for a ticker."""
        return _json_response(get_model_input_pack_payload(ticker=ticker, model_type=model_type))

    return mcp


@click.command()
@click.option("--transport", type=click.Choice(["stdio", "sse"]), default="stdio", help="Transport type")
@click.option("--port", default="8000", help="Port to listen on for SSE")
def main(transport: str, port: str):
    assert transport.lower() in ["stdio", "sse"], "Transport should be `stdio` or `sse`"
    logger = get_logger("Service:finance_company_data")
    logger.info("Starting the finance company-data MCP server")
    build_server(int(port)).run(transport=transport.lower())
