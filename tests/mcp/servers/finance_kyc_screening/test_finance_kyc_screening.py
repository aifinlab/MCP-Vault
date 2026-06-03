import unittest

from mcpuniverse.mcp.servers.finance_kyc_screening.server import build_server
from mcpuniverse.mcp.servers.finance_shared.enterprise_data import (
    get_onboarding_packet,
    screen_sanctions_pep,
)
from tests.mcp.servers.finance_shared.test_support import (
    clear_finance_world_env,
    configure_finance_world_env,
)


class TestFinanceKycScreening(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        configure_finance_world_env()
        self.mcp = build_server(port=12345)

    def tearDown(self):
        clear_finance_world_env()

    async def test_server_tools(self):
        tools = await self.mcp.list_tools()
        self.assertEqual(
            [tool.name for tool in tools],
            [
                "get_onboarding_packet",
                "screen_sanctions_pep",
                "evaluate_kyc_rules",
                "list_kyc_gaps",
                "get_escalation_recommendation",
            ],
        )

    def test_get_onboarding_packet(self):
        result = get_onboarding_packet("KYC-PACKET-FS-0001")

        self.assertEqual(result["client_id"], "CLIENT-FS-0001")
        self.assertEqual(result["world_id"], "financial_services_seed42")

    def test_screen_sanctions_pep(self):
        result = screen_sanctions_pep("CLIENT-FS-0001")

        self.assertEqual(result["sanctions_status"], "clear")
        self.assertFalse(result["pep_status"])


if __name__ == "__main__":
    unittest.main()
