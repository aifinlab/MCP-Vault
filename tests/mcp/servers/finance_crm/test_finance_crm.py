import unittest

from mcpuniverse.mcp.servers.finance_crm.server import build_server
from mcpuniverse.mcp.servers.finance_shared.enterprise_data import (
    get_client_record,
    get_meeting_context,
    list_follow_ups,
    search_clients,
)
from tests.mcp.servers.finance_shared.test_support import (
    clear_finance_world_env,
    configure_finance_world_env,
)


class TestFinanceCrm(unittest.IsolatedAsyncioTestCase):

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
                "search_clients",
                "get_client_record",
                "list_client_interactions",
                "list_meetings",
                "get_meeting_context",
                "list_follow_ups",
            ],
        )

    def test_search_clients(self):
        result = search_clients(segment="wealth")

        self.assertEqual(result["clients"][0]["client_id"], "CLIENT-FS-0001")

    def test_get_client_record(self):
        result = get_client_record("CLIENT-FS-0001")

        self.assertEqual(result["client_name"], "Financial Services Test Client")
        self.assertEqual(result["client_profile"]["risk_profile"], "moderate")

    def test_meeting_and_follow_up_paths(self):
        meeting = get_meeting_context("MTG-FS-0001")
        follow_ups = list_follow_ups(client_id="CLIENT-FS-0001", status="open")

        self.assertEqual(meeting["client_id"], "CLIENT-FS-0001")
        self.assertEqual(follow_ups["follow_ups"][0]["follow_up_id"], "FU-FS-0001")


if __name__ == "__main__":
    unittest.main()
