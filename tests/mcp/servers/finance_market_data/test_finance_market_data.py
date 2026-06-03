import unittest

from mcpuniverse.mcp.servers.finance_market_data.server import build_server
from mcpuniverse.mcp.servers.finance_shared.data_loader import (
    get_instrument_profile,
    get_market_price,
    get_valuation_multiples,
)
from tests.mcp.servers.finance_shared.test_support import (
    clear_finance_world_env,
    configure_finance_world_env,
    patch_live_market_provider,
)

class TestFinanceMarketData(unittest.IsolatedAsyncioTestCase):

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
                "get_market_price",
                "get_price_history_for_ticker",
                "get_company_profile",
                "get_instrument_profile",
                "get_financial_statement_slice",
                "get_valuation_multiples_for_ticker",
            ],
        )

    def test_live_price_lookup(self):
        price = get_market_price("aapl", "2026-05-15")
        self.assertEqual(price["ticker"], "AAPL")
        self.assertEqual(price["close"], 215.18)
        self.assertIn("data_source", price)

    def test_a_share_price_lookup_uses_cny_market_data(self):
        price = get_market_price("600519.SH", "2026-05-15")
        self.assertEqual(price["ticker"], "600519.SH")
        self.assertEqual(price["close"], 1520.0)
        self.assertEqual(price["currency"], "CNY")
        self.assertEqual(price["data_source"]["provider"], "akshare")

    def test_hk_share_price_lookup_uses_hkd_market_data(self):
        price = get_market_price("0700.HK", "2026-05-15")
        self.assertEqual(price["ticker"], "0700.HK")
        self.assertEqual(price["close"], 456.4)
        self.assertEqual(price["currency"], "HKD")
        self.assertEqual(price["data_source"]["provider"], "akshare")

    def test_live_valuation_lookup(self):
        multiples = get_valuation_multiples("MSFT", "2026-05-15")
        self.assertEqual(multiples["multiples"]["price_to_earnings"], 31.4)

    def test_live_instrument_lookup(self):
        instrument = get_instrument_profile("AAPL")
        self.assertEqual(instrument["product_type"], "equity")
        self.assertEqual(instrument["provider"], "fmp")

if __name__ == "__main__":
    unittest.main()
