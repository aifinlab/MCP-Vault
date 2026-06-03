import unittest
import socket
from mcpuniverse.mcp.manager import MCPManager


class TestMCPClient(unittest.IsolatedAsyncioTestCase):

    async def test_client(self):
        manager = MCPManager()
        client = await manager.build_client(server_name="finance-market-data", transport="stdio")
        tools = await client.list_tools()
        tool_names = [tool.name for tool in tools]
        self.assertIn("get_market_price", tool_names)
        self.assertIn("get_price_history_for_ticker", tool_names)
        await client.cleanup()

    async def test_client_sse(self):
        port = 8000
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("localhost", port)) != 0:
                return
        manager = MCPManager()
        client = await manager.build_client(server_name="finance-market-data", transport="sse")
        tools = await client.list_tools()
        tool_names = [tool.name for tool in tools]
        self.assertIn("get_market_price", tool_names)
        self.assertIn("get_price_history_for_ticker", tool_names)
        await client.cleanup()


if __name__ == "__main__":
    unittest.main()
