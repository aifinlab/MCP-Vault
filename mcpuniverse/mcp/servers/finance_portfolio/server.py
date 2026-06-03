"""Portfolio MCP server for financial-services tasks."""
import json
from collections import defaultdict

import click
from mcp.server.fastmcp import FastMCP

from mcpuniverse.common.logger import get_logger
from mcpuniverse.mcp.servers.finance_shared.data_loader import (
    get_account,
    get_account_client_context as get_account_client_context_payload,
    get_client_profile as get_client_profile_payload,
    get_company_fundamentals,
    get_enriched_holdings,
    list_accounts,
)
from mcpuniverse.mcp.servers.finance_shared.normalizers import round_money
from mcpuniverse.mcp.servers.finance_shared.portfolio_extensions import (
    check_wash_sale_window as check_wash_sale_window_payload,
    find_tax_loss_harvesting_candidates as find_tax_loss_harvesting_candidates_payload,
    generate_rebalance_proposal as generate_rebalance_proposal_payload,
    get_model_portfolio as get_model_portfolio_payload,
    get_tax_lots as get_tax_lots_payload,
)
from mcpuniverse.mcp.servers.finance_shared.schema import data_source_key, normalize_data_source


def _json_response(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True)


def _portfolio_totals(account_id: str, as_of_date: str = "") -> dict:
    holdings_payload = get_enriched_holdings(account_id=account_id, as_of_date=as_of_date)
    account = get_account(account_id)
    invested_market_value = sum(float(holding["market_value"]) for holding in holdings_payload["holdings"])
    cash = float(account.get("cash", 0.0))
    total_market_value = invested_market_value + cash
    if total_market_value <= 0:
        raise ValueError(f"Account {account_id} has non-positive total market value")
    return {
        "account": account,
        "holdings_payload": holdings_payload,
        "cash": round_money(cash),
        "invested_market_value": round_money(invested_market_value),
        "total_market_value": round_money(total_market_value),
    }


def _attach_data_sources(result: dict, *sources: dict) -> dict:
    data_sources = []
    for source in sources:
        if source.get("data_source"):
            _append_data_source(data_sources, source["data_source"])
        for data_source in source.get("data_sources", []):
            _append_data_source(data_sources, data_source)
    if data_sources:
        result["data_sources"] = data_sources
    return result


def _append_data_source(data_sources: list[dict], data_source: dict) -> None:
    normalized_data_source = normalize_data_source(data_source)
    if any(data_source_key(source) == data_source_key(normalized_data_source) for source in data_sources):
        return
    data_sources.append(normalized_data_source)


def build_server(port: int = 8000) -> FastMCP:
    """
    Initializes the finance portfolio MCP server.

    :param port: Port for SSE.
    :return: The MCP server.
    """
    mcp = FastMCP("finance_portfolio", port=port)

    @mcp.tool()
    def list_client_accounts(client_id: str = "") -> str:
        """
        List benchmark-world accounts, optionally filtered by client id.

        Args:
            client_id: Optional client identifier, e.g. "CLIENT-FS-0001".
        """
        return _json_response(list_accounts(client_id=client_id or None))

    @mcp.tool()
    def get_account_profile(account_id: str) -> str:
        """
        Get static account metadata, risk profile, cash, and raw holdings.

        Args:
            account_id: Account identifier, e.g. "ACC-FS-0001".
        """
        return _json_response(get_account(account_id=account_id))

    @mcp.tool()
    def get_client_profile(client_id: str) -> str:
        """
        Get KYC, AML, suitability, product approval, and data entitlement metadata for a client.

        Args:
            client_id: Client identifier, e.g. "CLIENT-FS-0001".
        """
        return _json_response(get_client_profile_payload(client_id=client_id))

    @mcp.tool()
    def get_account_client_context(account_id: str) -> str:
        """
        Get account metadata joined to its linked client profile.

        Args:
            account_id: Account identifier, e.g. "ACC-FS-0001".
        """
        return _json_response(get_account_client_context_payload(account_id=account_id))

    @mcp.tool()
    def get_account_holdings(account_id: str, as_of_date: str = "") -> str:
        """
        Get account holdings enriched with configured market prices and market values.

        Args:
            account_id: Account identifier, e.g. "ACC-FS-0001".
            as_of_date: Optional YYYY-MM-DD date. If omitted, uses the configured data source date.
        """
        return _json_response(get_enriched_holdings(account_id=account_id, as_of_date=as_of_date))

    @mcp.tool()
    def get_portfolio_summary(account_id: str, as_of_date: str = "") -> str:
        """
        Get total market value, invested value, cash, and position weights for an account.

        Args:
            account_id: Account identifier, e.g. "ACC-FS-0001".
            as_of_date: Optional YYYY-MM-DD date. If omitted, uses the configured data source date.
        """
        totals = _portfolio_totals(account_id=account_id, as_of_date=as_of_date)
        positions = []
        for holding in totals["holdings_payload"]["holdings"]:
            positions.append({
                "ticker": holding["ticker"],
                "quantity": holding["quantity"],
                "market_value": holding["market_value"],
                "portfolio_weight": round(float(holding["market_value"]) / totals["total_market_value"], 6),
            })
        result = {
            "account_id": totals["account"]["account_id"],
            "client_id": totals["account"]["client_id"],
            "world_id": totals["holdings_payload"]["world_id"],
            "as_of_date": totals["holdings_payload"]["as_of_date"],
            "base_currency": totals["holdings_payload"]["base_currency"],
            "cash": totals["cash"],
            "invested_market_value": totals["invested_market_value"],
            "total_market_value": totals["total_market_value"],
            "positions": positions,
        }
        return _json_response(_attach_data_sources(result, totals["holdings_payload"]))

    @mcp.tool()
    def get_sector_exposure(account_id: str, as_of_date: str = "") -> str:
        """
        Get sector exposure for account holdings using configured company fundamentals.

        Args:
            account_id: Account identifier, e.g. "ACC-FS-0001".
            as_of_date: Optional YYYY-MM-DD date. If omitted, uses the configured data source date.
        """
        totals = _portfolio_totals(account_id=account_id, as_of_date=as_of_date)
        exposures = defaultdict(float)
        company_sources = []
        for holding in totals["holdings_payload"]["holdings"]:
            company = get_company_fundamentals(holding["ticker"])
            exposures[company["sector"]] += float(holding["market_value"])
            if company.get("data_source"):
                _append_data_source(company_sources, company["data_source"])
        sector_exposures = [
            {
                "sector": sector,
                "market_value": round_money(market_value),
                "portfolio_weight": round(market_value / totals["total_market_value"], 6),
            }
            for sector, market_value in sorted(exposures.items())
        ]
        result = {
            "account_id": totals["account"]["account_id"],
            "world_id": totals["holdings_payload"]["world_id"],
            "as_of_date": totals["holdings_payload"]["as_of_date"],
            "sector_exposures": sector_exposures,
        }
        company_source_payload = {"data_sources": company_sources}
        return _json_response(_attach_data_sources(result, totals["holdings_payload"], company_source_payload))

    @mcp.tool()
    def get_position_concentration(account_id: str, as_of_date: str = "") -> str:
        """
        Get single-name concentration weights for account holdings.

        Args:
            account_id: Account identifier, e.g. "ACC-FS-0001".
            as_of_date: Optional YYYY-MM-DD date. If omitted, uses the configured data source date.
        """
        totals = _portfolio_totals(account_id=account_id, as_of_date=as_of_date)
        concentrations = [
            {
                "ticker": holding["ticker"],
                "market_value": holding["market_value"],
                "portfolio_weight": round(float(holding["market_value"]) / totals["total_market_value"], 6),
            }
            for holding in totals["holdings_payload"]["holdings"]
        ]
        result = {
            "account_id": totals["account"]["account_id"],
            "world_id": totals["holdings_payload"]["world_id"],
            "as_of_date": totals["holdings_payload"]["as_of_date"],
            "concentrations": sorted(concentrations, key=lambda item: item["portfolio_weight"], reverse=True),
        }
        return _json_response(_attach_data_sources(result, totals["holdings_payload"]))

    @mcp.tool()
    def get_tax_lots(account_id: str, ticker: str = "") -> str:
        """
        Get account tax lots.

        Args:
            account_id: Account identifier.
            ticker: Optional ticker filter.
        """
        return _json_response(get_tax_lots_payload(account_id=account_id, ticker=ticker))

    @mcp.tool()
    def find_tax_loss_harvesting_candidates(account_id: str, min_loss_amount: float = 0.0) -> str:
        """
        Find tax-loss harvesting candidates.

        Args:
            account_id: Account identifier.
            min_loss_amount: Optional absolute loss threshold.
        """
        return _json_response(
            find_tax_loss_harvesting_candidates_payload(account_id=account_id, min_loss_amount=min_loss_amount)
        )

    @mcp.tool()
    def check_wash_sale_window(account_id: str, ticker: str, as_of_date: str = "") -> str:
        """
        Check wash-sale window for a ticker.

        Args:
            account_id: Account identifier.
            ticker: Ticker to check.
            as_of_date: Optional as-of date.
        """
        return _json_response(check_wash_sale_window_payload(account_id=account_id, ticker=ticker, as_of_date=as_of_date))

    @mcp.tool()
    def get_model_portfolio(account_id: str) -> str:
        """
        Get target model portfolio for an account.

        Args:
            account_id: Account identifier.
        """
        return _json_response(get_model_portfolio_payload(account_id=account_id))

    @mcp.tool()
    def generate_rebalance_proposal(account_id: str, as_of_date: str = "") -> str:
        """
        Generate a draft rebalance proposal without submitting orders.

        Args:
            account_id: Account identifier.
            as_of_date: Optional as-of date.
        """
        return _json_response(generate_rebalance_proposal_payload(account_id=account_id, as_of_date=as_of_date))

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
    Starts the finance portfolio MCP server.

    :param port: Port for SSE.
    :param transport: The transport type, e.g., `stdio` or `sse`.
    """
    assert transport.lower() in ["stdio", "sse"], "Transport should be `stdio` or `sse`"
    logger = get_logger("Service:finance_portfolio")
    logger.info("Starting the finance portfolio MCP server")
    mcp = build_server(int(port))
    mcp.run(transport=transport.lower())
