import unittest

from mcpuniverse.mcp.servers.finance_private_markets.server import build_server
from mcpuniverse.mcp.servers.finance_shared.enterprise_data import (
    compare_gp_mark_to_policy,
    get_cap_table,
    get_deal_record,
    get_fund_performance,
    get_fund_portfolio,
    get_portco_kpis,
    get_portco_profile,
    get_valuation_package_summary,
    list_deal_pipeline,
    search_private_companies,
)
from tests.mcp.servers.finance_shared.test_support import (
    clear_finance_world_env,
    configure_finance_world_env,
)


class TestFinancePrivateMarkets(unittest.IsolatedAsyncioTestCase):

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
                "search_private_companies",
                "get_portco_profile",
                "get_portco_kpis",
                "get_fund_portfolio",
                "get_deal_record",
                "list_deal_pipeline",
                "get_valuation_package_summary",
                "get_funding_rounds",
                "get_cap_table",
                "get_fund_performance",
                "get_portco_operating_metrics",
                "compare_gp_mark_to_policy",
            ],
        )

    def test_company_and_fund_paths(self):
        companies = search_private_companies(sector="software")
        profile = get_portco_profile("PC-FS-001")
        portfolio = get_fund_portfolio("FUND-FS-III")
        performance = get_fund_performance("FUND-FS-III")

        self.assertEqual(companies["companies"][0]["portco_id"], "PC-FS-001")
        self.assertEqual(profile["company_name"], "World Software Co")
        self.assertEqual(portfolio["holdings"][0]["portco_id"], "PC-FS-001")
        self.assertGreater(performance["irr"], 0)

    def test_deal_and_valuation_paths(self):
        kpis = get_portco_kpis("PC-FS-001")
        deal = get_deal_record("DEAL-FS-0001")
        pipeline = list_deal_pipeline(stage="initial_screen")
        valuation = get_valuation_package_summary("VAL-PKG-FS-0001")
        cap_table = get_cap_table("PC-FS-001")
        policy_check = compare_gp_mark_to_policy("VAL-PKG-FS-0001")

        self.assertEqual(kpis["kpis"][0]["period"], "2026-05")
        self.assertEqual(deal["stage"], "initial_screen")
        self.assertEqual(pipeline["deals"][0]["deal_id"], "DEAL-FS-0001")
        self.assertEqual(valuation["policy_checks"][0]["status"], "flag")
        self.assertEqual(cap_table["holders"][0]["holder"], "FUND-FS-III")
        self.assertFalse(policy_check["accepted_as_final"])


if __name__ == "__main__":
    unittest.main()
