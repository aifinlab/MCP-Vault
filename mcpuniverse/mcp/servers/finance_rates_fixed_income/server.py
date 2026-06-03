"""Rates and fixed-income MCP server for financial-services workflows."""
import json

import click
from mcp.server.fastmcp import FastMCP

from mcpuniverse.common.logger import get_logger
from mcpuniverse.mcp.servers.finance_shared.cross_asset_data import (
    bond_future_price as bond_future_price_payload,
    bond_price as bond_price_payload,
    credit_curve as credit_curve_payload,
    fixed_income_risk_analytics as fixed_income_risk_analytics_payload,
    inflation_curve as inflation_curve_payload,
    interest_rate_curve as interest_rate_curve_payload,
    yieldbook_bond_reference as yieldbook_bond_reference_payload,
    yieldbook_cashflow as yieldbook_cashflow_payload,
    yieldbook_scenario as yieldbook_scenario_payload,
)


def _json_response(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True)


def build_server(port: int = 8000) -> FastMCP:
    mcp = FastMCP("finance_rates_fixed_income", port=port)

    @mcp.tool()
    def bond_price(identifier: str, as_of_date: str = "") -> str:
        """Price a bond and return fixed-income analytics."""
        return _json_response(bond_price_payload(identifier=identifier, as_of_date=as_of_date))

    @mcp.tool()
    def bond_future_price(future_ric: str, as_of_date: str = "") -> str:
        """Price a bond future and return CTD/basis inputs."""
        return _json_response(bond_future_price_payload(future_ric=future_ric, as_of_date=as_of_date))

    @mcp.tool()
    def interest_rate_curve(currency: str, as_of_date: str = "") -> str:
        """Return an interest-rate curve for a currency."""
        return _json_response(interest_rate_curve_payload(currency=currency, as_of_date=as_of_date))

    @mcp.tool()
    def credit_curve(curve_id: str = "", country: str = "", issuer_type: str = "", as_of_date: str = "") -> str:
        """Return a credit spread curve."""
        return _json_response(credit_curve_payload(curve_id=curve_id, country=country, issuer_type=issuer_type, as_of_date=as_of_date))

    @mcp.tool()
    def inflation_curve(currency: str, as_of_date: str = "") -> str:
        """Return an inflation breakeven curve."""
        return _json_response(inflation_curve_payload(currency=currency, as_of_date=as_of_date))

    @mcp.tool()
    def yieldbook_bond_reference(identifier: str) -> str:
        """Return fixed-income reference data."""
        return _json_response(yieldbook_bond_reference_payload(identifier=identifier))

    @mcp.tool()
    def yieldbook_cashflow(identifier: str) -> str:
        """Return projected bond cashflows."""
        return _json_response(yieldbook_cashflow_payload(identifier=identifier))

    @mcp.tool()
    def yieldbook_scenario(identifier: str, scenario_name: str = "parallel_100bp_up") -> str:
        """Return bond scenario analysis."""
        return _json_response(yieldbook_scenario_payload(identifier=identifier, scenario_name=scenario_name))

    @mcp.tool()
    def fixed_income_risk_analytics(identifier: str) -> str:
        """Return fixed-income risk analytics."""
        return _json_response(fixed_income_risk_analytics_payload(identifier=identifier))

    return mcp


@click.command()
@click.option("--transport", type=click.Choice(["stdio", "sse"]), default="stdio", help="Transport type")
@click.option("--port", default="8000", help="Port to listen on for SSE")
def main(transport: str, port: str):
    assert transport.lower() in ["stdio", "sse"], "Transport should be `stdio` or `sse`"
    logger = get_logger("Service:finance_rates_fixed_income")
    logger.info("Starting the finance rates/fixed-income MCP server")
    build_server(int(port)).run(transport=transport.lower())
