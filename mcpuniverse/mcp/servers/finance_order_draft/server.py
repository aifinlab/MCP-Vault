"""Order-draft MCP server for financial-services tasks."""
import json

import click
from mcp.server.fastmcp import FastMCP

from mcpuniverse.common.logger import get_logger
from mcpuniverse.mcp.servers.finance_shared.calculations import (
    create_order_draft as create_order_draft_payload,
    preview_order_impact as preview_order_impact_payload,
)


def _json_response(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True)


def build_server(port: int = 8000) -> FastMCP:
    """
    Initializes the finance order-draft MCP server.

    :param port: Port for SSE.
    :return: The MCP server.
    """
    mcp = FastMCP("finance_order_draft", port=port)

    @mcp.tool()
    def create_order_draft(
            account_id: str,
            ticker: str,
            side: str,
            quantity: float,
            order_type: str = "market",
            limit_price: float = 0.0,
            as_of_date: str = "",
            rationale: str = ""
    ) -> str:
        """
        Create a deterministic unsubmitted order draft.

        Args:
            account_id: Account identifier, e.g. "ACC-FS-0001".
            ticker: Equity ticker symbol, e.g. "AAPL".
            side: Order side, either "BUY" or "SELL".
            quantity: Positive order quantity.
            order_type: Order type label, e.g. "market".
            limit_price: Optional limit price for notional estimation.
            as_of_date: Optional YYYY-MM-DD date. If omitted, uses the configured data source date.
            rationale: Optional free-text rationale copied into the draft.
        """
        return _json_response(
            create_order_draft_payload(
                account_id=account_id,
                ticker=ticker,
                side=side,
                quantity=quantity,
                order_type=order_type,
                limit_price=limit_price,
                as_of_date=as_of_date,
                rationale=rationale,
            )
        )

    @mcp.tool()
    def preview_order_impact(
            account_id: str,
            ticker: str,
            side: str,
            quantity: float,
            as_of_date: str = ""
    ) -> str:
        """
        Preview deterministic order impact without creating or submitting an order.

        Args:
            account_id: Account identifier, e.g. "ACC-FS-0001".
            ticker: Equity ticker symbol, e.g. "AAPL".
            side: Order side, either "BUY" or "SELL".
            quantity: Positive order quantity.
            as_of_date: Optional YYYY-MM-DD date. If omitted, uses the configured data source date.
        """
        return _json_response(
            preview_order_impact_payload(
                account_id=account_id,
                ticker=ticker,
                side=side,
                quantity=quantity,
                as_of_date=as_of_date,
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
    Starts the finance order-draft MCP server.

    :param port: Port for SSE.
    :param transport: The transport type, e.g., `stdio` or `sse`.
    """
    assert transport.lower() in ["stdio", "sse"], "Transport should be `stdio` or `sse`"
    logger = get_logger("Service:finance_order_draft")
    logger.info("Starting the finance order-draft MCP server")
    mcp = build_server(int(port))
    mcp.run(transport=transport.lower())
