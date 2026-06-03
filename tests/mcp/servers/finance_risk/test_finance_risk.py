import unittest

from mcpuniverse.mcp.servers.finance_risk.server import build_server
from mcpuniverse.mcp.servers.finance_shared.calculations import (
    calculate_parametric_var,
    check_concentration_risk,
    get_factor_exposure,
    run_pre_trade_risk_check,
    run_stress_scenario,
)
from tests.mcp.servers.finance_shared.test_support import (
    clear_finance_world_env,
    configure_finance_world_env,
    patch_live_market_provider,
)


class TestFinanceRisk(unittest.IsolatedAsyncioTestCase):

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
                "calculate_parametric_var",
                "run_stress_scenario",
                "get_factor_exposure",
                "check_concentration_risk",
                "run_pre_trade_risk_check",
            ],
        )

    def test_parametric_var(self):
        result = calculate_parametric_var("ACC-FS-0001", "2026-05-15")
        self.assertEqual(result["account_id"], "ACC-FS-0001")
        self.assertGreater(result["var_amount"], 0)
        self.assertIn("data_sources", result)

    def test_stress_scenario(self):
        result = run_stress_scenario("ACC-FS-0001", "equity_down_10_financials_down_4", "2026-05-15")
        self.assertGreater(result["stress_loss"], 0)
        self.assertLess(result["stressed_market_value"], result["portfolio_market_value"])

    def test_factor_exposure(self):
        result = get_factor_exposure("ACC-FS-0001", "2026-05-15")
        self.assertGreater(result["market_beta"], 0)

    def test_concentration_risk(self):
        result = check_concentration_risk("ACC-FS-0001", "2026-05-15")
        self.assertEqual(result["breached"], True)
        self.assertTrue(result["single_name_breaches"])

    def test_pre_trade_risk_check_blocks_concentration(self):
        result = run_pre_trade_risk_check("ACC-FS-0001", "AAPL", "BUY", 200, as_of_date="2026-05-15")
        self.assertEqual(result["risk_acceptable"], False)
        self.assertEqual(result["blocking_policy_codes"], ["NO_SINGLE_NAME_GT_25"])


if __name__ == "__main__":
    unittest.main()
