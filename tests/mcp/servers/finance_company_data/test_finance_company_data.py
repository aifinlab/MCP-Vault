import unittest

from mcpuniverse.mcp.servers.finance_company_data.server import build_server
from mcpuniverse.mcp.servers.finance_shared.company_data import (
    get_model_input_pack,
    get_standardized_financials,
    search_companies,
)
from tests.mcp.servers.finance_shared.test_support import (
    clear_finance_world_env,
    configure_finance_world_env,
)


class TestFinanceCompanyData(unittest.IsolatedAsyncioTestCase):

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
                "search_companies",
                "get_standardized_financials",
                "get_segment_financials",
                "get_capital_structure",
                "get_wacc_inputs",
                "get_model_input_pack",
            ],
        )

    def test_search_companies_filters_market(self):
        result = search_companies(market="HK")

        tickers = {company["ticker"] for company in result["companies"]}
        self.assertEqual(tickers, {"0700.HK", "9988.HK"})

    def test_get_standardized_financials(self):
        result = get_standardized_financials("AAPL", statement_type="income_statement", period="FY2025")

        self.assertEqual(result["ticker"], "AAPL")
        self.assertEqual(result["statement_type"], "income_statement")
        self.assertIn("FY2025", result["standardized_financials"]["income_statement"])
        self.assertEqual(result["data_source"]["dataset"], "company_data")

    def test_get_model_input_pack(self):
        result = get_model_input_pack("AAPL", model_type="dcf")

        self.assertEqual(result["ticker"], "AAPL")
        self.assertEqual(result["model_type"], "dcf")
        self.assertIn("wacc_inputs", result)


if __name__ == "__main__":
    unittest.main()
