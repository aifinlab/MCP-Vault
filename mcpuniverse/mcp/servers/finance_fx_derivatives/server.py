"""FX and derivatives MCP server for financial-services workflows."""
import json

import click
from mcp.server.fastmcp import FastMCP

from mcpuniverse.common.logger import get_logger
from mcpuniverse.mcp.servers.finance_shared.cross_asset_data import (
    equity_vol_surface as equity_vol_surface_payload,
    fx_forward_curve as fx_forward_curve_payload,
    fx_forward_price as fx_forward_price_payload,
    fx_spot_price as fx_spot_price_payload,
    fx_vol_surface as fx_vol_surface_payload,
    ir_swap as ir_swap_payload,
    option_template_list as option_template_list_payload,
    option_value as option_value_payload,
)


def _json_response(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True)


def build_server(port: int = 8000) -> FastMCP:
    mcp = FastMCP("finance_fx_derivatives", port=port)

    @mcp.tool()
    def fx_spot_price(currency_pair: str, as_of_date: str = "") -> str:
        """Return FX spot pricing."""
        return _json_response(fx_spot_price_payload(currency_pair=currency_pair, as_of_date=as_of_date))

    @mcp.tool()
    def fx_forward_price(currency_pair: str, tenor: str = "3M", as_of_date: str = "") -> str:
        """Return FX forward pricing."""
        return _json_response(fx_forward_price_payload(currency_pair=currency_pair, tenor=tenor, as_of_date=as_of_date))

    @mcp.tool()
    def fx_forward_curve(currency_pair: str, as_of_date: str = "") -> str:
        """Return an FX forward curve."""
        return _json_response(fx_forward_curve_payload(currency_pair=currency_pair, as_of_date=as_of_date))

    @mcp.tool()
    def fx_vol_surface(currency_pair: str, as_of_date: str = "") -> str:
        """Return an FX volatility surface."""
        return _json_response(fx_vol_surface_payload(currency_pair=currency_pair, as_of_date=as_of_date))

    @mcp.tool()
    def equity_vol_surface(underlying: str, as_of_date: str = "") -> str:
        """Return an equity/index volatility surface."""
        return _json_response(equity_vol_surface_payload(underlying=underlying, as_of_date=as_of_date))

    @mcp.tool()
    def option_template_list(underlying: str) -> str:
        """List available option templates for an underlying."""
        return _json_response(option_template_list_payload(underlying=underlying))

    @mcp.tool()
    def option_value(underlying: str, strike: float = 0.0, expiry: str = "", option_type: str = "call") -> str:
        """Value an option and return Greeks."""
        return _json_response(option_value_payload(underlying=underlying, strike=strike, expiry=expiry, option_type=option_type))

    @mcp.tool()
    def ir_swap(currency: str, tenor: str = "", index: str = "", as_of_date: str = "") -> str:
        """Return interest-rate swap pricing."""
        return _json_response(ir_swap_payload(currency=currency, tenor=tenor, index=index, as_of_date=as_of_date))

    return mcp


@click.command()
@click.option("--transport", type=click.Choice(["stdio", "sse"]), default="stdio", help="Transport type")
@click.option("--port", default="8000", help="Port to listen on for SSE")
def main(transport: str, port: str):
    assert transport.lower() in ["stdio", "sse"], "Transport should be `stdio` or `sse`"
    logger = get_logger("Service:finance_fx_derivatives")
    logger.info("Starting the finance FX/derivatives MCP server")
    build_server(int(port)).run(transport=transport.lower())
