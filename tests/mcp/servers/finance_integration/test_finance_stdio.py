import json
import os
import unittest

from dotenv import load_dotenv

from mcpuniverse.mcp.manager import MCPManager


LIVE_FINANCE_ENV = {
    "FINANCE_DATA_MODE": "live",
    "FINANCE_MARKET_DATA_PROVIDER": "fmp",
    "FINANCE_BENCHMARK_WORLD_ID": "financial_services_seed42",
}

LIVE_MACRO_ENV = {
    "FINANCE_MACRO_DATA_PROVIDERS": "fred,akshare",
}

ENTERPRISE_FINANCE_ENV = {
    "FINANCE_DATA_MODE": "live",
    "FINANCE_BENCHMARK_WORLD_ID": "financial_services_seed42",
}

WORLD_FINANCE_ENV = {
    "FINANCE_DATA_MODE": "live",
    "FINANCE_BENCHMARK_WORLD_ID": "financial_services_seed42",
}

LIVE_PROVIDER_UNAVAILABLE_MARKERS = (
    "Provider returned HTTP 429",
    "Failed to fetch provider JSON after",
)


def _require_env_key(key: str) -> None:
    load_dotenv()
    if not os.getenv(key, "").strip():
        raise unittest.SkipTest(f"{key} is required for live finance stdio integration tests")


def _decode_tool_json(output):
    text = output["result"].content[0].text
    if text.startswith("Error executing tool"):
        if any(marker in text for marker in LIVE_PROVIDER_UNAVAILABLE_MARKERS):
            raise unittest.SkipTest(text)
        raise AssertionError(text)
    return json.loads(text)


class TestFinanceStdioIntegration(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        _require_env_key("FMP_API_KEY")

    async def _execute_json_tool(self, server_name, tool_name, arguments):
        previous_env = {key: os.getenv(key) for key in LIVE_FINANCE_ENV}
        os.environ.update(LIVE_FINANCE_ENV)
        manager = MCPManager()
        client = await manager.build_client(server_name=server_name, transport="stdio")
        try:
            output = await client.execute_tool(tool_name=tool_name, arguments=arguments)
            return _decode_tool_json(output)
        finally:
            await client.cleanup()
            for key, value in previous_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    async def test_finance_risk_stdio_call(self):
        result = await self._execute_json_tool(
            "finance-risk",
            "calculate_parametric_var",
            {"account_id": "ACC-FS-0001", "as_of_date": "2026-05-15"},
        )
        self.assertGreater(result["var_amount"], 0)
        self.assertEqual(result["account_id"], "ACC-FS-0001")

    async def test_finance_portfolio_client_context_stdio_call(self):
        result = await self._execute_json_tool(
            "finance-portfolio",
            "get_account_client_context",
            {"account_id": "ACC-FS-0001"},
        )
        self.assertEqual(result["client_id"], "CLIENT-FS-0001")

    async def test_finance_audit_stdio_call(self):
        result = await self._execute_json_tool(
            "finance-audit",
            "get_audit_event",
            {"event_id": "AUD-FS-0001"},
        )
        self.assertEqual(result["outcome"], "draft_recorded")


class TestFinanceMacroStdioIntegration(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        _require_env_key("FRED_API_KEY")

    async def test_finance_macro_stdio_call(self):
        previous_env = {key: os.getenv(key) for key in LIVE_MACRO_ENV}
        os.environ.update(LIVE_MACRO_ENV)
        manager = MCPManager()
        client = await manager.build_client(server_name="finance-macro-data", transport="stdio")
        try:
            output = await client.execute_tool(
                tool_name="get_macro_series",
                arguments={
                    "series_id": "FEDFUNDS",
                    "start_date": "2026-01-01",
                    "end_date": "2026-05-15",
                },
            )
            result = _decode_tool_json(output)
        finally:
            await client.cleanup()
            for key, value in previous_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        self.assertEqual(result["series_id"], "FEDFUNDS")
        self.assertEqual(result["data_source"]["provider"], "fred")


class TestFinanceEnterpriseStdioIntegration(unittest.IsolatedAsyncioTestCase):

    async def _execute_json_tool(self, server_name, tool_name, arguments):
        previous_env = {key: os.getenv(key) for key in ENTERPRISE_FINANCE_ENV}
        os.environ.update(ENTERPRISE_FINANCE_ENV)
        manager = MCPManager()
        client = await manager.build_client(server_name=server_name, transport="stdio")
        try:
            output = await client.execute_tool(tool_name=tool_name, arguments=arguments)
            return _decode_tool_json(output)
        finally:
            await client.cleanup()
            for key, value in previous_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    async def test_finance_crm_stdio_call(self):
        result = await self._execute_json_tool(
            "finance-crm",
            "get_client_record",
            {"client_id": "CLIENT-FS-0001"},
        )
        self.assertEqual(result["client_name"], "Financial Services Test Client")

    async def test_finance_kyc_screening_stdio_call(self):
        result = await self._execute_json_tool(
            "finance-kyc-screening",
            "get_onboarding_packet",
            {"packet_id": "KYC-PACKET-FS-0001"},
        )
        self.assertEqual(result["client_id"], "CLIENT-FS-0001")

    async def test_finance_ledger_stdio_call(self):
        result = await self._execute_json_tool(
            "finance-ledger",
            "get_trial_balance",
            {"entity_id": "ENT-FS-0001", "period": "2026-05"},
        )
        self.assertEqual(result["lines"][0]["account_code"], "1000")

    async def test_finance_subledger_stdio_call(self):
        result = await self._execute_json_tool(
            "finance-subledger",
            "compare_gl_subledger_records",
            {"entity_id": "ENT-FS-0001", "period": "2026-05"},
        )
        self.assertEqual(result["break_count"], 1)

    async def test_finance_nav_stdio_call(self):
        result = await self._execute_json_tool(
            "finance-nav",
            "recompute_capital_account",
            {"statement_id": "LP-STMT-FS-0001"},
        )
        self.assertEqual(result["difference"], 0.0)

    async def test_finance_private_markets_stdio_call(self):
        result = await self._execute_json_tool(
            "finance-private-markets",
            "get_fund_portfolio",
            {"fund_id": "FUND-FS-III"},
        )
        self.assertEqual(result["holdings"][0]["portco_id"], "PC-FS-001")


class TestFinanceWorldStdioIntegration(unittest.IsolatedAsyncioTestCase):

    async def _execute_json_tool(self, server_name, tool_name, arguments):
        previous_env = {key: os.getenv(key) for key in WORLD_FINANCE_ENV}
        os.environ.update(WORLD_FINANCE_ENV)
        manager = MCPManager()
        client = await manager.build_client(server_name=server_name, transport="stdio")
        try:
            output = await client.execute_tool(tool_name=tool_name, arguments=arguments)
            return _decode_tool_json(output)
        finally:
            await client.cleanup()
            for key, value in previous_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    async def test_finance_document_store_stdio_call(self):
        result = await self._execute_json_tool(
            "finance-document-store",
            "get_document",
            {"document_id": "DOC-FS-10K-AAPL-2025"},
        )
        self.assertEqual(result["data_source"]["data_source_type"], "benchmark_world")

    async def test_finance_company_data_stdio_call(self):
        result = await self._execute_json_tool(
            "finance-company-data",
            "get_model_input_pack",
            {"ticker": "AAPL", "model_type": "dcf"},
        )
        self.assertEqual(result["ticker"], "AAPL")
        self.assertEqual(result["data_source"]["provider"], "deterministic")

    async def test_finance_transactions_stdio_call(self):
        result = await self._execute_json_tool(
            "finance-transactions",
            "get_transaction_multiples",
            {"transaction_id": "TXN-FS-0001"},
        )
        self.assertIn("ev_ebitda", result["multiples"])

    async def test_finance_rates_fixed_income_stdio_call(self):
        result = await self._execute_json_tool(
            "finance-rates-fixed-income",
            "bond_price",
            {"identifier": "US91282CJJ18"},
        )
        self.assertEqual(result["bond_id"], "BOND-FS-UST10Y")

    async def test_finance_fx_derivatives_stdio_call(self):
        result = await self._execute_json_tool(
            "finance-fx-derivatives",
            "option_value",
            {"underlying": ".SPX", "strike": 5000.0, "expiry": "2026-08-21", "option_type": "call"},
        )
        self.assertEqual(result["option_id"], "OPT-FS-SPX-5000C-202608")


if __name__ == "__main__":
    unittest.main()
