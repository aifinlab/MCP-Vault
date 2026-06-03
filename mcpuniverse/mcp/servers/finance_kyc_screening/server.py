"""KYC screening MCP server for financial-services workflows."""
import json

import click
from mcp.server.fastmcp import FastMCP

from mcpuniverse.common.logger import get_logger
from mcpuniverse.mcp.servers.finance_shared.enterprise_data import (
    evaluate_kyc_rules as evaluate_kyc_rules_payload,
    get_escalation_recommendation as get_escalation_recommendation_payload,
    get_onboarding_packet as get_onboarding_packet_payload,
    list_kyc_gaps as list_kyc_gaps_payload,
    screen_sanctions_pep as screen_sanctions_pep_payload,
)


def _json_response(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True)


def build_server(port: int = 8000) -> FastMCP:
    """
    Initializes the finance KYC screening MCP server.

    :param port: Port for SSE.
    :return: The MCP server.
    """
    mcp = FastMCP("finance_kyc_screening", port=port)

    @mcp.tool()
    def get_onboarding_packet(packet_id: str) -> str:
        """
        Get a trusted KYC onboarding packet record.

        Args:
            packet_id: Onboarding packet identifier.
        """
        return _json_response(get_onboarding_packet_payload(packet_id=packet_id))

    @mcp.tool()
    def screen_sanctions_pep(client_id: str) -> str:
        """
        Return sanctions and PEP screening status for a client.

        Args:
            client_id: Client identifier.
        """
        return _json_response(screen_sanctions_pep_payload(client_id=client_id))

    @mcp.tool()
    def evaluate_kyc_rules(packet_id: str) -> str:
        """
        Evaluate task-local KYC rules against an onboarding packet.

        Args:
            packet_id: Onboarding packet identifier.
        """
        return _json_response(evaluate_kyc_rules_payload(packet_id=packet_id))

    @mcp.tool()
    def list_kyc_gaps(packet_id: str) -> str:
        """
        List KYC gaps under task-local rules.

        Args:
            packet_id: Onboarding packet identifier.
        """
        return _json_response(list_kyc_gaps_payload(packet_id=packet_id))

    @mcp.tool()
    def get_escalation_recommendation(packet_id: str) -> str:
        """
        Recommend whether a KYC packet should be escalated for human review.

        Args:
            packet_id: Onboarding packet identifier.
        """
        return _json_response(get_escalation_recommendation_payload(packet_id=packet_id))

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
    Starts the finance KYC screening MCP server.

    :param port: Port for SSE.
    :param transport: The transport type, e.g., `stdio` or `sse`.
    """
    assert transport.lower() in ["stdio", "sse"], "Transport should be `stdio` or `sse`"
    logger = get_logger("Service:finance_kyc_screening")
    logger.info("Starting the finance KYC screening MCP server")
    mcp = build_server(int(port))
    mcp.run(transport=transport.lower())
