import unittest
import pytest
from mcpuniverse.mcp.manager import MCPManager


class TestGateway(unittest.IsolatedAsyncioTestCase):

    @pytest.mark.skip
    async def test_connection(self):
        manager = MCPManager()
        client = await manager.build_client(server_name="finance-market-data", transport="sse")
        tools = await client.list_tools()
        print(tools)
        r = await client.execute_tool(
            "get_market_price", arguments={"ticker": "AAPL", "as_of_date": "2026-05-15"})
        print(r)
        await client.cleanup()


if __name__ == "__main__":
    unittest.main()
