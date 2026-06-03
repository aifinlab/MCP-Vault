import unittest

from mcpuniverse.mcp.servers.finance_audit.server import build_server
from mcpuniverse.mcp.servers.finance_shared.data_loader import (
    get_audit_event,
    list_audit_events,
)
from tests.mcp.servers.finance_shared.test_support import (
    clear_finance_world_env,
    configure_finance_world_env,
)


class TestFinanceAudit(unittest.IsolatedAsyncioTestCase):

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
                "list_audit_events",
                "get_audit_event",
                "explain_policy_reference",
                "list_policy_references",
                "explain_decision_context",
            ],
        )

    def test_list_audit_events(self):
        result = list_audit_events(account_id="ACC-FS-0001", event_type="order_review")
        self.assertEqual(result["events"][0]["event_id"], "AUD-FS-0001")

    def test_get_audit_event(self):
        result = get_audit_event("AUD-FS-0001")
        self.assertEqual(result["outcome"], "draft_recorded")


if __name__ == "__main__":
    unittest.main()
