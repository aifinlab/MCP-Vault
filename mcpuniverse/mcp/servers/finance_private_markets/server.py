"""Private-markets MCP server for financial-services workflows."""
import json

import click
from mcp.server.fastmcp import FastMCP

from mcpuniverse.common.logger import get_logger
from mcpuniverse.mcp.servers.finance_shared.enterprise_data import (
    compare_gp_mark_to_policy as compare_gp_mark_to_policy_payload,
    get_cap_table as get_cap_table_payload,
    get_deal_record as get_deal_record_payload,
    get_fund_performance as get_fund_performance_payload,
    get_fund_portfolio as get_fund_portfolio_payload,
    get_funding_rounds as get_funding_rounds_payload,
    get_portco_operating_metrics as get_portco_operating_metrics_payload,
    get_portco_kpis as get_portco_kpis_payload,
    get_portco_profile as get_portco_profile_payload,
    get_valuation_package_summary as get_valuation_package_summary_payload,
    list_deal_pipeline as list_deal_pipeline_payload,
    search_private_companies as search_private_companies_payload,
)


def _json_response(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True)


def build_server(port: int = 8000) -> FastMCP:
    """
    Initializes the finance private-markets MCP server.

    :param port: Port for SSE.
    :return: The MCP server.
    """
    mcp = FastMCP("finance_private_markets", port=port)

    @mcp.tool()
    def search_private_companies(query: str = "", sector: str = "", stage: str = "") -> str:
        """
        Search trusted private-company records.

        Args:
            query: Optional text filter.
            sector: Optional sector filter.
            stage: Optional company stage filter.
        """
        return _json_response(search_private_companies_payload(query=query, sector=sector, stage=stage))

    @mcp.tool()
    def get_portco_profile(portco_id: str) -> str:
        """
        Get one portfolio-company profile.

        Args:
            portco_id: Portfolio company identifier.
        """
        return _json_response(get_portco_profile_payload(portco_id=portco_id))

    @mcp.tool()
    def get_portco_kpis(portco_id: str, period: str = "") -> str:
        """
        Get private-company KPIs.

        Args:
            portco_id: Portfolio company identifier.
            period: Optional reporting period.
        """
        return _json_response(get_portco_kpis_payload(portco_id=portco_id, period=period))

    @mcp.tool()
    def get_fund_portfolio(fund_id: str) -> str:
        """
        Get one private-market fund portfolio.

        Args:
            fund_id: Fund identifier.
        """
        return _json_response(get_fund_portfolio_payload(fund_id=fund_id))

    @mcp.tool()
    def get_deal_record(deal_id: str) -> str:
        """
        Get one private-market deal record.

        Args:
            deal_id: Deal identifier.
        """
        return _json_response(get_deal_record_payload(deal_id=deal_id))

    @mcp.tool()
    def list_deal_pipeline(stage: str = "") -> str:
        """
        List private-market deal pipeline records.

        Args:
            stage: Optional deal stage filter.
        """
        return _json_response(list_deal_pipeline_payload(stage=stage))

    @mcp.tool()
    def get_valuation_package_summary(package_id: str) -> str:
        """
        Get a GP valuation package summary.

        Args:
            package_id: Valuation package identifier.
        """
        return _json_response(get_valuation_package_summary_payload(package_id=package_id))

    @mcp.tool()
    def get_funding_rounds(portco_id: str) -> str:
        """Get funding rounds for one private company."""
        return _json_response(get_funding_rounds_payload(portco_id=portco_id))

    @mcp.tool()
    def get_cap_table(portco_id: str) -> str:
        """Get cap table data for one private company."""
        return _json_response(get_cap_table_payload(portco_id=portco_id))

    @mcp.tool()
    def get_fund_performance(fund_id: str) -> str:
        """Get fund-level performance metrics."""
        return _json_response(get_fund_performance_payload(fund_id=fund_id))

    @mcp.tool()
    def get_portco_operating_metrics(portco_id: str, period: str = "") -> str:
        """Get private-company operating metrics."""
        return _json_response(get_portco_operating_metrics_payload(portco_id=portco_id, period=period))

    @mcp.tool()
    def compare_gp_mark_to_policy(package_id: str) -> str:
        """Compare GP-reported marks to valuation policy checks."""
        return _json_response(compare_gp_mark_to_policy_payload(package_id=package_id))

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
    Starts the finance private-markets MCP server.

    :param port: Port for SSE.
    :param transport: The transport type, e.g., `stdio` or `sse`.
    """
    assert transport.lower() in ["stdio", "sse"], "Transport should be `stdio` or `sse`"
    logger = get_logger("Service:finance_private_markets")
    logger.info("Starting the finance private-markets MCP server")
    mcp = build_server(int(port))
    mcp.run(transport=transport.lower())
