from unittest.mock import patch
import unittest

from mcpuniverse.mcp.servers.finance_order_draft.server import build_server
from mcpuniverse.mcp.servers.finance_shared.calculations import (
    create_order_draft,
)
from tests.mcp.servers.finance_shared.test_support import (
    clear_finance_world_env,
    configure_finance_world_env,
)


class TestFinanceOrderDraft(unittest.IsolatedAsyncioTestCase):

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
                "create_order_draft",
                "preview_order_impact",
            ],
        )

    def test_create_order_draft_never_submits_when_policy_calls_are_mocked(self):
        impact = {
            "account_id": "ACC-FS-0001",
            "world_id": "financial_services_seed42",
            "as_of_date": "2026-05-17",
            "ticker": "AAPL",
            "side": "BUY",
            "quantity": 1.0,
            "estimated_price": 300.23,
            "estimated_notional": 300.23,
            "data_source": {
                "data_source_id": "live:fmp:market_price:AAPL:2026-05-15",
                "data_source_type": "live_provider",
                "provider": "fmp",
                "dataset": "market_price",
                "ticker": "AAPL",
                "data_date": "2026-05-15",
            },
        }
        compliance = {
            "allowed": False,
            "requires_review": False,
            "violations": [],
            "warnings": [],
            "blocking_policy_codes": ["NO_SINGLE_NAME_GT_25"],
            "required_disclosures": [],
        }
        risk = {"blocking_policy_codes": []}

        impact_patch = patch(
            "mcpuniverse.mcp.servers.finance_shared.calculations.get_order_impact",
            return_value=impact,
        )
        compliance_patch = patch(
            "mcpuniverse.mcp.servers.finance_shared.calculations.check_order_restrictions",
            return_value=compliance,
        )
        risk_patch = patch(
            "mcpuniverse.mcp.servers.finance_shared.calculations.run_pre_trade_risk_check",
            return_value=risk,
        )

        with impact_patch, compliance_patch, risk_patch:
            result = create_order_draft("ACC-FS-0001", "AAPL", "BUY", 1)

        self.assertEqual(result["execution_status"], "not_submitted")
        self.assertEqual(result["world_id"], "financial_services_seed42")
        self.assertEqual(result["data_source"]["data_source_id"], "live:fmp:market_price:AAPL:2026-05-15")


if __name__ == "__main__":
    unittest.main()
