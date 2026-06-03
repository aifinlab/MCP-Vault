"""Risk MCP server for financial-services tasks."""
import json

import click
from mcp.server.fastmcp import FastMCP

from mcpuniverse.common.logger import get_logger
from mcpuniverse.mcp.servers.finance_shared.calculations import (
    calculate_parametric_var as calculate_parametric_var_payload,
    check_concentration_risk as check_concentration_risk_payload,
    get_factor_exposure as get_factor_exposure_payload,
    run_pre_trade_risk_check as run_pre_trade_risk_check_payload,
    run_stress_scenario as run_stress_scenario_payload,
)


def _json_response(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True)


def build_server(port: int = 8000) -> FastMCP:
    """
    Initializes the finance risk MCP server.

    :param port: Port for SSE.
    :return: The MCP server.
    """
    mcp = FastMCP("finance_risk", port=port)

    @mcp.tool()
    def calculate_parametric_var(
            account_id: str,
            as_of_date: str = "",
            confidence_level: float = 0.95
    ) -> str:
        """
        Calculate one-day parametric VaR from built-in risk settings and live market inputs.

        Args:
            account_id: Account identifier, e.g. "ACC-FS-0001".
            as_of_date: Optional YYYY-MM-DD date. If omitted, uses the configured data source date.
            confidence_level: Supported confidence level, e.g. 0.95.
        """
        return _json_response(
            calculate_parametric_var_payload(
                account_id=account_id,
                as_of_date=as_of_date,
                confidence_level=confidence_level,
            )
        )

    @mcp.tool()
    def run_stress_scenario(account_id: str, scenario_name: str, as_of_date: str = "") -> str:
        """
        Run a deterministic stress scenario against account holdings.

        Args:
            account_id: Account identifier, e.g. "ACC-FS-0001".
            scenario_name: Scenario key, e.g. "equity_down_10_financials_down_4".
            as_of_date: Optional YYYY-MM-DD date. If omitted, uses the configured data source date.
        """
        return _json_response(
            run_stress_scenario_payload(
                account_id=account_id,
                scenario_name=scenario_name,
                as_of_date=as_of_date,
            )
        )

    @mcp.tool()
    def get_factor_exposure(account_id: str, as_of_date: str = "") -> str:
        """
        Calculate portfolio factor exposure for an account.

        Args:
            account_id: Account identifier, e.g. "ACC-FS-0001".
            as_of_date: Optional YYYY-MM-DD date. If omitted, uses the configured data source date.
        """
        return _json_response(get_factor_exposure_payload(account_id=account_id, as_of_date=as_of_date))

    @mcp.tool()
    def check_concentration_risk(account_id: str, as_of_date: str = "") -> str:
        """
        Check single-name and sector concentration risk.

        Args:
            account_id: Account identifier, e.g. "ACC-FS-0001".
            as_of_date: Optional YYYY-MM-DD date. If omitted, uses the configured data source date.
        """
        return _json_response(check_concentration_risk_payload(account_id=account_id, as_of_date=as_of_date))

    @mcp.tool()
    def run_pre_trade_risk_check(
            account_id: str,
            ticker: str,
            side: str,
            quantity: float,
            as_of_date: str = "",
            limit_price: float = 0.0
    ) -> str:
        """
        Run pre-trade risk checks for an unsubmitted order.

        Args:
            account_id: Account identifier, e.g. "ACC-FS-0001".
            ticker: Tradable symbol, e.g. "AAPL".
            side: Order side, either "BUY" or "SELL".
            quantity: Positive order quantity.
            as_of_date: Optional YYYY-MM-DD date. If omitted, uses the configured data source date.
            limit_price: Optional limit price for notional estimation.
        """
        return _json_response(
            run_pre_trade_risk_check_payload(
                account_id=account_id,
                ticker=ticker,
                side=side,
                quantity=quantity,
                as_of_date=as_of_date,
                limit_price=limit_price,
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
    Starts the finance risk MCP server.

    :param port: Port for SSE.
    :param transport: The transport type, e.g., `stdio` or `sse`.
    """
    assert transport.lower() in ["stdio", "sse"], "Transport should be `stdio` or `sse`"
    logger = get_logger("Service:finance_risk")
    logger.info("Starting the finance risk MCP server")
    mcp = build_server(int(port))
    mcp.run(transport=transport.lower())
