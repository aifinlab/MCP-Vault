"""Market-data MCP server for financial-services tasks."""
import json

import click
from mcp.server.fastmcp import FastMCP

from mcpuniverse.common.logger import get_logger
from mcpuniverse.mcp.servers.finance_shared.data_loader import (
    get_company_fundamentals,
    get_financial_statement,
    get_instrument_profile as get_instrument_profile_payload,
    get_market_price as get_market_price_payload,
    get_price_history,
    get_valuation_multiples,
)


def _json_response(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True)


def build_server(port: int = 8000) -> FastMCP:
    """
    Initializes the finance market-data MCP server.

    :param port: Port for SSE.
    :return: The MCP server.
    """
    mcp = FastMCP("finance_market_data", port=port)

    @mcp.tool()
    def get_market_price(ticker: str, as_of_date: str = "") -> str:
        """
        Get the latest available close price on or before as_of_date.

        Args:
            ticker: Equity ticker symbol, e.g. "MSFT".
            as_of_date: Optional YYYY-MM-DD date. If omitted, uses the configured data source date.
        """
        return _json_response(get_market_price_payload(ticker=ticker, as_of_date=as_of_date))

    @mcp.tool()
    def get_price_history_for_ticker(ticker: str, start_date: str, end_date: str) -> str:
        """
        Get inclusive historical close-price records.

        Args:
            ticker: Equity ticker symbol, e.g. "MSFT".
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format.
        """
        return _json_response(get_price_history(ticker=ticker, start_date=start_date, end_date=end_date))

    @mcp.tool()
    def get_company_profile(ticker: str) -> str:
        """
        Get company profile, sector, industry, statements, and valuation data.

        Args:
            ticker: Equity ticker symbol, e.g. "MSFT".
        """
        return _json_response(get_company_fundamentals(ticker=ticker))

    @mcp.tool()
    def get_instrument_profile(ticker: str) -> str:
        """
        Get live/resolved market metadata for a tradable ticker.

        Args:
            ticker: Tradable ticker symbol, e.g. "AAPL", "600519.SH", or "0700.HK".
        """
        return _json_response(get_instrument_profile_payload(ticker=ticker))

    @mcp.tool()
    def get_financial_statement_slice(ticker: str, statement_type: str, period: str = "") -> str:
        """
        Get a financial-statement slice for a ticker.

        Args:
            ticker: Equity ticker symbol, e.g. "MSFT".
            statement_type: Statement family, e.g. "income" or "balance_sheet".
            period: Optional period key, e.g. "FY2025". If omitted, returns all available periods.
        """
        return _json_response(
            get_financial_statement(ticker=ticker, statement_type=statement_type, period=period)
        )

    @mcp.tool()
    def get_valuation_multiples_for_ticker(ticker: str, as_of_date: str = "") -> str:
        """
        Get valuation multiples on or before as_of_date.

        Args:
            ticker: Equity ticker symbol, e.g. "MSFT".
            as_of_date: Optional YYYY-MM-DD date. If omitted, uses the latest available date.
        """
        return _json_response(get_valuation_multiples(ticker=ticker, as_of_date=as_of_date))

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
    Starts the finance market-data MCP server.

    :param port: Port for SSE.
    :param transport: The transport type, e.g., `stdio` or `sse`.
    """
    assert transport.lower() in ["stdio", "sse"], "Transport should be `stdio` or `sse`"
    logger = get_logger("Service:finance_market_data")
    logger.info("Starting the finance market-data MCP server")
    mcp = build_server(int(port))
    mcp.run(transport=transport.lower())
