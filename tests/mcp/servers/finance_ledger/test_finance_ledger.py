import unittest

from mcpuniverse.mcp.servers.finance_ledger.server import build_server
from mcpuniverse.mcp.servers.finance_shared.enterprise_data import (
    draft_adjusting_entry,
    get_journal_entry,
    get_rollforward_schedule,
    get_trial_balance,
    list_accrual_candidates,
    list_gl_transactions,
)
from tests.mcp.servers.finance_shared.test_support import (
    clear_finance_world_env,
    configure_finance_world_env,
)


class TestFinanceLedger(unittest.IsolatedAsyncioTestCase):

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
                "get_trial_balance",
                "list_gl_transactions",
                "get_journal_entry",
                "list_accrual_candidates",
                "get_rollforward_schedule",
                "get_budget_vs_actuals",
                "get_journal_source_breakdown",
                "draft_adjusting_entry",
            ],
        )

    def test_trial_balance_and_gl_transactions(self):
        trial_balance = get_trial_balance("ENT-FS-0001", "2026-05")
        transactions = list_gl_transactions(entity_id="ENT-FS-0001", period="2026-05")

        self.assertEqual(trial_balance["lines"][0]["account_code"], "1000")
        self.assertEqual(transactions["transactions"][0]["journal_source"], "ap_invoice")

    def test_journal_accrual_and_rollforward(self):
        journal = get_journal_entry("JE-FS-0001")
        accruals = list_accrual_candidates(entity_id="ENT-FS-0001", period="2026-05")
        rollforward = get_rollforward_schedule("ENT-FS-0001", "6100", "2026-05")

        self.assertEqual(journal["status"], "posted")
        self.assertEqual(accruals["accrual_candidates"][0]["status"], "draft_for_controller_review")
        self.assertEqual(rollforward["ending_balance"], 42000.0)

    def test_draft_adjusting_entry_is_not_posted(self):
        result = draft_adjusting_entry("ENT-FS-0001", "2026-05", "6100", "2000", 2500.0)

        self.assertEqual(result["posting_status"], "not_posted")


if __name__ == "__main__":
    unittest.main()
