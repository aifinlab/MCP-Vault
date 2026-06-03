import unittest

from mcpuniverse.mcp.servers.finance_fx_derivatives.server import build_server
from mcpuniverse.mcp.servers.finance_shared.cross_asset_data import (
    equity_vol_surface,
    fx_forward_curve,
    fx_forward_price,
    fx_spot_price,
    fx_vol_surface,
    ir_swap,
    option_template_list,
    option_value,
)
from tests.mcp.servers.finance_shared.test_support import (
    clear_finance_world_env,
    configure_finance_world_env,
)


class TestFinanceFxDerivatives(unittest.IsolatedAsyncioTestCase):

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
                "fx_spot_price",
                "fx_forward_price",
                "fx_forward_curve",
                "fx_vol_surface",
                "equity_vol_surface",
                "option_template_list",
                "option_value",
                "ir_swap",
            ],
        )

    def test_fx_paths(self):
        spot = fx_spot_price("USDJPY")
        forward = fx_forward_price("USDJPY", tenor="3M")
        curve = fx_forward_curve("USDJPY")
        vol = fx_vol_surface("USDJPY")

        self.assertEqual(spot["currency_pair"], "USDJPY")
        self.assertEqual(forward["tenor"], "3M")
        self.assertEqual(curve["points"][0]["tenor"], "1M")
        self.assertEqual(vol["surface"][0]["tenor"], "1M")

    def test_derivatives_paths(self):
        surface = equity_vol_surface(".SPX")
        templates = option_template_list(".SPX")
        option = option_value(".SPX", strike=5000.0, expiry="2026-08-21", option_type="call")
        swap = ir_swap("USD")

        self.assertEqual(surface["underlying"], ".SPX")
        self.assertEqual(templates["templates"][0]["option_type"], "call")
        self.assertEqual(option["option_id"], "OPT-FS-SPX-5000C-202608")
        self.assertEqual(swap["index"], "SOFR")


if __name__ == "__main__":
    unittest.main()
