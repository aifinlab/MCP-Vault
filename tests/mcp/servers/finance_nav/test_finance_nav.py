import unittest

from mcpuniverse.mcp.servers.finance_nav.server import build_server
from mcpuniverse.mcp.servers.finance_shared.enterprise_data import (
    get_lp_statement,
    get_nav_pack,
    list_statement_tieouts,
    recompute_capital_account,
)
from tests.mcp.servers.finance_shared.test_support import (
    clear_finance_world_env,
    configure_finance_world_env,
)


class TestFinanceNav(unittest.IsolatedAsyncioTestCase):

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
                "get_nav_pack",
                "get_lp_statement",
                "recompute_capital_account",
                "list_statement_tieouts",
            ],
        )

    def test_nav_pack_and_lp_statement(self):
        nav_pack = get_nav_pack("FUND-FS-III", "2026-05-15")
        statement = get_lp_statement("LP-STMT-FS-0001")

        self.assertEqual(nav_pack["net_asset_value"], 120000000.0)
        self.assertEqual(statement["fund_id"], "FUND-FS-III")

    def test_recompute_and_tieouts(self):
        recomputed = recompute_capital_account("LP-STMT-FS-0001")
        tieouts = list_statement_tieouts("FUND-FS-III", "2026-05-15")

        self.assertEqual(recomputed["difference"], 0.0)
        self.assertEqual(tieouts["tieouts"][0]["difference"], 0.0)


if __name__ == "__main__":
    unittest.main()
