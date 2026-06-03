import unittest

from mcpuniverse.mcp.servers.finance_shared.transaction_data import (
    get_transaction_detail,
    get_transaction_multiples,
    search_precedent_transactions,
    summarize_sector_transactions,
)
from mcpuniverse.mcp.servers.finance_transactions.server import build_server
from tests.mcp.servers.finance_shared.test_support import (
    clear_finance_world_env,
    configure_finance_world_env,
)


class TestFinanceTransactions(unittest.IsolatedAsyncioTestCase):

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
                "search_precedent_transactions",
                "get_transaction_detail",
                "get_transaction_multiples",
                "summarize_sector_transactions",
            ],
        )

    def test_transaction_detail_and_multiples(self):
        detail = get_transaction_detail("TXN-FS-0001")
        multiples = get_transaction_multiples("TXN-FS-0001")

        self.assertEqual(detail["transaction_id"], "TXN-FS-0001")
        self.assertIn("ev_ebitda", multiples["multiples"])

    def test_search_and_summarize_sector_transactions(self):
        transactions = search_precedent_transactions(sector="software")
        summary = summarize_sector_transactions("software")

        self.assertEqual(transactions["transactions"][0]["transaction_id"], "TXN-FS-0001")
        self.assertGreater(summary["transaction_count"], 0)


if __name__ == "__main__":
    unittest.main()
