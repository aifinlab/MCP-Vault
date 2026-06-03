import unittest

from mcpuniverse.mcp.servers.finance_rates_fixed_income.server import build_server
from mcpuniverse.mcp.servers.finance_shared.cross_asset_data import (
    bond_future_price,
    bond_price,
    credit_curve,
    fixed_income_risk_analytics,
    inflation_curve,
    interest_rate_curve,
    yieldbook_bond_reference,
    yieldbook_cashflow,
    yieldbook_scenario,
)
from tests.mcp.servers.finance_shared.test_support import (
    clear_finance_world_env,
    configure_finance_world_env,
)


class TestFinanceRatesFixedIncome(unittest.IsolatedAsyncioTestCase):

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
                "bond_price",
                "bond_future_price",
                "interest_rate_curve",
                "credit_curve",
                "inflation_curve",
                "yieldbook_bond_reference",
                "yieldbook_cashflow",
                "yieldbook_scenario",
                "fixed_income_risk_analytics",
            ],
        )

    def test_bond_price_and_future(self):
        bond = bond_price("US91282CJJ18")
        future = bond_future_price("TYc1")

        self.assertEqual(bond["bond_id"], "BOND-FS-UST10Y")
        self.assertEqual(future["ctd_bond_id"], "BOND-FS-UST10Y")

    def test_curves(self):
        rates = interest_rate_curve("USD")
        credit = credit_curve(country="US", issuer_type="Corporate")
        inflation = inflation_curve("USD")

        self.assertEqual(rates["curve_id"], "USD-GOVT-20260515")
        self.assertEqual(credit["curve_id"], "US-CORP-IG-20260515")
        self.assertEqual(inflation["curve_id"], "USD-INFL-20260515")

    def test_yieldbook_and_risk_paths(self):
        reference = yieldbook_bond_reference("US91282CJJ18")
        cashflows = yieldbook_cashflow("US91282CJJ18")
        scenario = yieldbook_scenario("US91282CJJ18")
        risk = fixed_income_risk_analytics("US91282CJJ18")

        self.assertEqual(reference["issuer"], "United States Treasury")
        self.assertEqual(cashflows["bond_id"], "BOND-FS-UST10Y")
        self.assertLess(scenario["scenario_result"]["pnl"], 0)
        self.assertGreater(risk["effective_duration"], 0)


if __name__ == "__main__":
    unittest.main()
