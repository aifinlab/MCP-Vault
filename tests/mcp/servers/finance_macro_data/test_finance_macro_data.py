import os
import unittest
from unittest.mock import patch

import pandas as pd

from mcpuniverse.mcp.servers.finance_macro_data.server import build_server
from mcpuniverse.mcp.servers.finance_shared.macro_data import (
    clear_macro_data_cache,
    get_macro_observation,
    get_macro_series,
    search_macro_series,
)


class TestFinanceMacroData(unittest.IsolatedAsyncioTestCase):

    def tearDown(self):
        for key in [
            "FRED_API_KEY",
            "FINANCE_MACRO_DATA_PROVIDERS",
            "FINANCE_LIVE_CACHE_TTL_SECONDS",
        ]:
            os.environ.pop(key, None)
        clear_macro_data_cache()

    async def test_server_tools(self):
        tools = await build_server(port=12345).list_tools()
        self.assertEqual(
            [tool.name for tool in tools],
            [
                "search_macro_series",
                "get_macro_series",
                "get_macro_observation",
            ],
        )

    def test_search_macro_series_uses_catalog_without_api_keys(self):
        result = search_macro_series("cpi")

        series_ids = {record["series_id"] for record in result["series"]}
        self.assertIn("CPIAUCSL", series_ids)
        self.assertIn("CN_CPI", series_ids)
        self.assertNotIn("HK_CPI", series_ids)
        self.assertNotIn("HK_CPI_YOY", series_ids)

    def test_search_macro_series_filters_hk_region(self):
        result = search_macro_series("gdp", region="HK")

        series_ids = {record["series_id"] for record in result["series"]}
        self.assertEqual(series_ids, {"HK_GDP", "HK_GDP_YOY"})

    @patch("mcpuniverse.mcp.servers.finance_shared.macro_data.fetch_json")
    def test_fred_macro_series_normalizes_observations(self, fetch_json_mock):
        os.environ["FRED_API_KEY"] = "test-key"
        fetch_json_mock.return_value = {
            "observations": [
                {"date": "2026-05-13", "value": "."},
                {"date": "2026-05-14", "value": "4.25"},
                {"date": "2026-05-15", "value": "4.30"},
            ]
        }

        result = get_macro_series("FEDFUNDS", "2026-05-13", "2026-05-15")

        self.assertEqual(result["series_id"], "FEDFUNDS")
        self.assertEqual(result["region"], "US")
        self.assertEqual(result["latest"], {"date": "2026-05-15", "value": 4.30})
        self.assertEqual(result["data_source"]["data_source_id"], "live:fred:macro_series:FEDFUNDS:2026-05-15")
        self.assertEqual(result["data_source"]["provider"], "fred")

    @patch("mcpuniverse.mcp.servers.finance_shared.external_providers.akshare._load_akshare")
    def test_akshare_china_macro_series_normalizes_observations(self, load_akshare_mock):
        class FakeAkshare:
            @staticmethod
            def macro_china_cpi():
                return pd.DataFrame([
                    {"月份": "2026年04月份", "全国-同比增长": 1.2},
                    {"月份": "2026年05月份", "全国-同比增长": 1.4},
                ])

        load_akshare_mock.return_value = FakeAkshare

        result = get_macro_series("CN_CPI", "2026-04-01", "2026-05-31")

        self.assertEqual(result["series_id"], "CN_CPI")
        self.assertEqual(result["region"], "CN")
        self.assertEqual(result["latest"], {"date": "2026-05-01", "value": 1.4})
        self.assertEqual(result["data_source"]["data_source_id"], "live:akshare:macro_series:CN_CPI:2026-05-01")
        self.assertEqual(result["data_source"]["provider"], "akshare")

    @patch("mcpuniverse.mcp.servers.finance_shared.external_providers.akshare._load_akshare")
    def test_macro_observation_returns_latest_on_or_before_date(self, load_akshare_mock):
        class FakeAkshare:
            @staticmethod
            def macro_china_pmi():
                return pd.DataFrame([
                    {"月份": "2026年03月份", "制造业-指数": 50.1},
                    {"月份": "2026年04月份", "制造业-指数": 49.9},
                ])

        load_akshare_mock.return_value = FakeAkshare

        result = get_macro_observation("CN_PMI", "2026-04-20")

        self.assertEqual(result["series_id"], "CN_PMI")
        self.assertEqual(result["observation"], {"date": "2026-04-01", "value": 49.9})

    @patch("mcpuniverse.mcp.servers.finance_shared.external_providers.akshare._load_akshare")
    def test_akshare_hk_macro_series_skips_nan_observations(self, load_akshare_mock):
        class FakeAkshare:
            @staticmethod
            def macro_china_hk_rate_of_unemployment():
                return pd.DataFrame([
                    {"时间": "2026年03月", "现值": 3.7},
                    {"时间": "2026年04月", "现值": float("nan")},
                ])

        load_akshare_mock.return_value = FakeAkshare

        result = get_macro_observation("HK_UNEMPLOYMENT", "2026-05-15")

        self.assertEqual(result["series_id"], "HK_UNEMPLOYMENT")
        self.assertEqual(result["region"], "HK")
        self.assertEqual(result["observation"], {"date": "2026-03-01", "value": 3.7})
        self.assertEqual(
            result["data_source"]["data_source_id"],
            "live:akshare:macro_series:HK_UNEMPLOYMENT:2026-03-01",
        )


if __name__ == "__main__":
    unittest.main()
