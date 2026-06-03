"""Ledger MCP server for financial-services workflows."""
import json

import click
from mcp.server.fastmcp import FastMCP

from mcpuniverse.common.logger import get_logger
from mcpuniverse.mcp.servers.finance_shared.enterprise_data import (
    draft_adjusting_entry as draft_adjusting_entry_payload,
    get_budget_vs_actuals as get_budget_vs_actuals_payload,
    get_journal_entry as get_journal_entry_payload,
    get_journal_source_breakdown as get_journal_source_breakdown_payload,
    get_rollforward_schedule as get_rollforward_schedule_payload,
    get_trial_balance as get_trial_balance_payload,
    list_accrual_candidates as list_accrual_candidates_payload,
    list_gl_transactions as list_gl_transactions_payload,
)


def _json_response(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True)


def build_server(port: int = 8000) -> FastMCP:
    """
    Initializes the finance ledger MCP server.

    :param port: Port for SSE.
    :return: The MCP server.
    """
    mcp = FastMCP("finance_ledger", port=port)

    @mcp.tool()
    def get_trial_balance(entity_id: str, period: str) -> str:
        """
        Get a trusted trial balance.

        Args:
            entity_id: Entity identifier.
            period: Accounting period, e.g. "2026-04".
        """
        return _json_response(get_trial_balance_payload(entity_id=entity_id, period=period))

    @mcp.tool()
    def list_gl_transactions(entity_id: str = "", account_code: str = "", period: str = "") -> str:
        """
        List trusted GL transactions.

        Args:
            entity_id: Optional entity identifier.
            account_code: Optional GL account code.
            period: Optional accounting period.
        """
        return _json_response(
            list_gl_transactions_payload(entity_id=entity_id, account_code=account_code, period=period)
        )

    @mcp.tool()
    def get_journal_entry(journal_entry_id: str) -> str:
        """
        Get one trusted journal entry.

        Args:
            journal_entry_id: Journal entry identifier.
        """
        return _json_response(get_journal_entry_payload(journal_entry_id=journal_entry_id))

    @mcp.tool()
    def list_accrual_candidates(entity_id: str = "", period: str = "") -> str:
        """
        List accrual candidates staged for review.

        Args:
            entity_id: Optional entity identifier.
            period: Optional accounting period.
        """
        return _json_response(list_accrual_candidates_payload(entity_id=entity_id, period=period))

    @mcp.tool()
    def get_rollforward_schedule(entity_id: str, account_code: str, period: str) -> str:
        """
        Get a trusted roll-forward schedule.

        Args:
            entity_id: Entity identifier.
            account_code: GL account code.
            period: Accounting period.
        """
        return _json_response(
            get_rollforward_schedule_payload(entity_id=entity_id, account_code=account_code, period=period)
        )

    @mcp.tool()
    def get_budget_vs_actuals(entity_id: str, period: str) -> str:
        """Get budget-vs-actual variance lines."""
        return _json_response(get_budget_vs_actuals_payload(entity_id=entity_id, period=period))

    @mcp.tool()
    def get_journal_source_breakdown(entity_id: str, period: str) -> str:
        """Get GL activity by journal source."""
        return _json_response(get_journal_source_breakdown_payload(entity_id=entity_id, period=period))

    @mcp.tool()
    def draft_adjusting_entry(
        entity_id: str,
        period: str,
        debit_account: str,
        credit_account: str,
        amount: float,
        memo: str = "",
    ) -> str:
        """Draft an adjusting journal entry without posting it."""
        return _json_response(
            draft_adjusting_entry_payload(
                entity_id=entity_id,
                period=period,
                debit_account=debit_account,
                credit_account=credit_account,
                amount=amount,
                memo=memo,
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
    Starts the finance ledger MCP server.

    :param port: Port for SSE.
    :param transport: The transport type, e.g., `stdio` or `sse`.
    """
    assert transport.lower() in ["stdio", "sse"], "Transport should be `stdio` or `sse`"
    logger = get_logger("Service:finance_ledger")
    logger.info("Starting the finance ledger MCP server")
    mcp = build_server(int(port))
    mcp.run(transport=transport.lower())
