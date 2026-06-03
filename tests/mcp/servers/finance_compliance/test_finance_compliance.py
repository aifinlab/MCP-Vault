import unittest

from mcpuniverse.mcp.servers.finance_compliance.server import build_server
from tests.mcp.servers.finance_shared.test_support import (
    clear_finance_world_env,
    configure_finance_world_env,
)


class TestFinanceCompliance(unittest.IsolatedAsyncioTestCase):

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
                "check_order_restrictions",
                "screen_restricted_security",
                "check_account_suitability",
                "check_product_distribution",
                "check_research_distribution",
            ],
        )


if __name__ == "__main__":
    unittest.main()
