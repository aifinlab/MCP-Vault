import unittest

from mcpuniverse.mcp.servers.finance_shared.enterprise_data import (
    compare_gl_subledger_records,
    get_trade_lifecycle,
    list_subledger_positions,
    list_subledger_transactions,
    trace_recon_break,
)
from mcpuniverse.mcp.servers.finance_subledger.server import build_server
from tests.mcp.servers.finance_shared.test_support import (
    clear_finance_world_env,
    configure_finance_world_env,
)


class TestFinanceSubledger(unittest.IsolatedAsyncioTestCase):

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
                "list_subledger_positions",
                "list_subledger_transactions",
                "get_trade_lifecycle",
                "compare_gl_subledger_records",
                "trace_recon_break",
            ],
        )

    def test_positions_transactions_and_lifecycle(self):
        positions = list_subledger_positions(asset_class="fixed_income")
        transactions = list_subledger_transactions(asset_class="fixed_income")
        lifecycle = get_trade_lifecycle("TRD-FI-FS-0001")

        self.assertEqual(positions["positions"][0]["security_id"], "US91282CJJ18")
        self.assertEqual(transactions["transactions"][0]["trade_id"], "TRD-FI-FS-0001")
        self.assertEqual(lifecycle["status"], "settled")

    def test_reconciliation_paths(self):
        comparison = compare_gl_subledger_records("ENT-FS-0001", "2026-05")
        break_trace = trace_recon_break("BRK-FS-0001")

        self.assertEqual(comparison["break_count"], 1)
        self.assertEqual(break_trace["break_id"], "BRK-FS-0001")


if __name__ == "__main__":
    unittest.main()
