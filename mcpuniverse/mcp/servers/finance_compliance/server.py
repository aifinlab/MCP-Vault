"""Compliance MCP server for financial-services tasks."""
import json

import click
from mcp.server.fastmcp import FastMCP

from mcpuniverse.common.logger import get_logger
from mcpuniverse.mcp.servers.finance_shared.calculations import (
    check_account_suitability as check_account_suitability_payload,
    check_order_restrictions as check_order_restrictions_payload,
    check_product_distribution as check_product_distribution_payload,
    check_research_distribution as check_research_distribution_payload,
    screen_restricted_security as screen_restricted_security_payload,
)


def _json_response(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True)


def build_server(port: int = 8000) -> FastMCP:
    """
    Initializes the finance compliance MCP server.

    :param port: Port for SSE.
    :return: The MCP server.
    """
    mcp = FastMCP("finance_compliance", port=port)

    @mcp.tool()
    def check_order_restrictions(
            account_id: str,
            ticker: str,
            side: str,
            quantity: float,
            order_type: str = "market",
            as_of_date: str = ""
    ) -> str:
        """
        Check task-local order policy and account-state restrictions for an order.

        Args:
            account_id: Account identifier, e.g. "ACC-FS-0001".
            ticker: Equity ticker symbol, e.g. "AAPL".
            side: Order side, either "BUY" or "SELL".
            quantity: Positive order quantity.
            order_type: Order type label, e.g. "market".
            as_of_date: Optional YYYY-MM-DD date. If omitted, uses the configured data source date.
        """
        return _json_response(
            check_order_restrictions_payload(
                account_id=account_id,
                ticker=ticker,
                side=side,
                quantity=quantity,
                order_type=order_type,
                as_of_date=as_of_date,
            )
        )

    @mcp.tool()
    def screen_restricted_security(account_id: str, ticker: str) -> str:
        """
        Screen a security against task-local restricted-security rules.

        Args:
            account_id: Account identifier, e.g. "ACC-FS-0001".
            ticker: Equity ticker symbol, e.g. "GME".
        """
        return _json_response(screen_restricted_security_payload(account_id=account_id, ticker=ticker))

    @mcp.tool()
    def check_account_suitability(account_id: str, product_type: str, risk_level: str = "") -> str:
        """
        Check task-local product suitability for the account risk profile.

        Args:
            account_id: Account identifier, e.g. "ACC-FS-0001".
            product_type: Product type, e.g. "equity" or "option".
            risk_level: Optional product risk level override.
        """
        return _json_response(
            check_account_suitability_payload(
                account_id=account_id,
                product_type=product_type,
                risk_level=risk_level,
            )
        )

    @mcp.tool()
    def check_product_distribution(account_id: str, ticker: str) -> str:
        """
        Check task-local product distribution constraints for an account.

        Args:
            account_id: Account identifier, e.g. "ACC-FS-0001".
            ticker: Tradable symbol, e.g. "AAPL" or "STRUCT_NOTE_NDX_BUFFER_2027".
        """
        return _json_response(check_product_distribution_payload(account_id=account_id, ticker=ticker))

    @mcp.tool()
    def check_research_distribution(account_id: str, report_id: str) -> str:
        """
        Check whether a research report may be used for client-facing advice.

        Args:
            account_id: Account identifier, e.g. "ACC-FS-0001".
            report_id: Research report identifier.
        """
        return _json_response(check_research_distribution_payload(account_id=account_id, report_id=report_id))

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
    Starts the finance compliance MCP server.

    :param port: Port for SSE.
    :param transport: The transport type, e.g., `stdio` or `sse`.
    """
    assert transport.lower() in ["stdio", "sse"], "Transport should be `stdio` or `sse`"
    logger = get_logger("Service:finance_compliance")
    logger.info("Starting the finance compliance MCP server")
    mcp = build_server(int(port))
    mcp.run(transport=transport.lower())
