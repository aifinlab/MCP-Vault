import unittest

from mcpuniverse.mcp.servers.finance_portfolio.server import build_server
from mcpuniverse.mcp.servers.finance_shared.data_loader import (
    get_account_client_context,
    get_client_profile,
    get_enriched_holdings,
)
from tests.mcp.servers.finance_shared.test_support import (
    clear_finance_world_env,
    configure_finance_world_env,
    patch_live_market_provider,
)


class TestFinancePortfolio(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        configure_finance_world_env()
        self.provider_patch = patch_live_market_provider()
        self.provider_patch.start()
        self.mcp = build_server(port=12345)

    def tearDown(self):
        self.provider_patch.stop()
        clear_finance_world_env()

    async def test_server_tools(self):
        tools = await self.mcp.list_tools()
        self.assertEqual(
            [tool.name for tool in tools],
            [
                "list_client_accounts",
                "get_account_profile",
                "get_client_profile",
                "get_account_client_context",
                "get_account_holdings",
                "get_portfolio_summary",
                "get_sector_exposure",
                "get_position_concentration",
                "get_tax_lots",
                "find_tax_loss_harvesting_candidates",
                "check_wash_sale_window",
                "get_model_portfolio",
                "generate_rebalance_proposal",
            ],
        )

    def test_enriched_holdings(self):
        holdings = get_enriched_holdings("ACC-FS-0001", "2026-05-15")
        self.assertEqual(holdings["account_id"], "ACC-FS-0001")
        self.assertEqual(holdings["holdings"][0]["market_value"], 21518.0)
        self.assertEqual(holdings["world_id"], "financial_services_seed42")
        self.assertIn("data_sources", holdings)

    def test_client_profile_lookup(self):
        client = get_client_profile("CLIENT-FS-0001")
        self.assertEqual(client["risk_profile"], "moderate")
        self.assertIn("equity", client["approved_product_types"])

    def test_account_client_context(self):
        context = get_account_client_context("ACC-FS-0001")
        self.assertEqual(context["client_id"], "CLIENT-FS-0001")
        self.assertEqual(context["risk_profile"], "moderate")


if __name__ == "__main__":
    unittest.main()
