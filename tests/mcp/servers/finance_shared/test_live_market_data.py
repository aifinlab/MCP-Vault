import os
import unittest
from unittest.mock import patch

from mcpuniverse.mcp.servers.finance_shared.data_loader import (
    clear_finance_data_cache,
    get_market_price,
)
from mcpuniverse.mcp.servers.finance_shared.errors import FinanceDataError
import pandas as pd

from mcpuniverse.mcp.servers.finance_shared.live_market_data import (
    AKShareMarketDataProvider,
    FMPMarketDataProvider,
    resolve_ticker_route,
)


class TestLiveMarketData(unittest.TestCase):

    def tearDown(self):
        for key in [
            "FMP_API_KEY",
            "FINANCE_DATA_MODE",
            "FINANCE_MARKET_DATA_PROVIDER",
            "FINANCE_BENCHMARK_WORLD_ID",
            "FINANCE_TASK_MATERIAL_PATH",
        ]:
            os.environ.pop(key, None)
        clear_finance_data_cache()

    @patch("mcpuniverse.mcp.servers.finance_shared.live_market_data.fetch_json")
    def test_fmp_provider_normalizes_live_market_price(self, fetch_json_mock):
        fetch_json_mock.return_value = [
            {"date": "2026-05-14", "open": 10, "high": 12, "low": 9, "close": 11, "volume": 1000},
            {"date": "2026-05-15", "open": 11, "high": 13, "low": 10, "close": 12, "volume": 1200},
        ]

        provider = FMPMarketDataProvider(api_key="test-key")
        price = provider.get_market_price("aapl", "2026-05-17")

        self.assertEqual(price["ticker"], "AAPL")
        self.assertEqual(price["close"], 12)
        self.assertNotIn("world_id", price)
        self.assertEqual(price["data_source"]["data_source_id"], "live:fmp:market_price:AAPL:2026-05-15")
        self.assertEqual(price["data_source"]["data_source_type"], "live_provider")
        self.assertEqual(price["data_source"]["dataset"], "market_price")

    @patch("mcpuniverse.mcp.servers.finance_shared.live_market_data.fetch_json")
    def test_world_loader_uses_live_provider_in_live_mode(self, fetch_json_mock):
        fetch_json_mock.return_value = [
            {"date": "2026-05-15", "open": 10, "high": 13, "low": 9, "close": 12, "volume": 1000}
        ]
        os.environ["FINANCE_DATA_MODE"] = "live"
        os.environ["FINANCE_MARKET_DATA_PROVIDER"] = "fmp"
        os.environ["FMP_API_KEY"] = "test-key"
        os.environ["FINANCE_BENCHMARK_WORLD_ID"] = "financial_services_seed42"
        clear_finance_data_cache()

        price = get_market_price("AAPL", "2026-05-17")

        self.assertNotIn("world_id", price)
        self.assertEqual(price["data_source"]["data_source_id"], "live:fmp:market_price:AAPL:2026-05-15")

    @patch("mcpuniverse.mcp.servers.finance_shared.external_providers.akshare._load_akshare")
    def test_akshare_provider_normalizes_a_share_market_price(self, load_akshare_mock):
        class FakeAkshare:
            @staticmethod
            def stock_zh_a_hist(**kwargs):
                return pd.DataFrame([
                    {"日期": "2026-05-14", "开盘": 1500, "最高": 1530, "最低": 1490, "收盘": 1510, "成交量": 1000},
                    {"日期": "2026-05-15", "开盘": 1510, "最高": 1540, "最低": 1500, "收盘": 1520, "成交量": 1200},
                ])

            @staticmethod
            def stock_individual_info_em(**kwargs):
                return pd.DataFrame([
                    {"项目": "股票简称", "值": "贵州茅台"},
                    {"项目": "行业", "值": "Consumer Staples"},
                ])

        load_akshare_mock.return_value = FakeAkshare
        provider = AKShareMarketDataProvider(
            instrument={
                "ticker": "600519.SH",
                "market": "CN",
                "exchange": "SSE",
                "currency": "CNY",
                "provider": "akshare",
                "provider_symbol": "600519",
            }
        )

        price = provider.get_market_price("600519.SH", "2026-05-17")

        self.assertEqual(price["ticker"], "600519.SH")
        self.assertEqual(price["close"], 1520.0)
        self.assertEqual(price["currency"], "CNY")
        self.assertEqual(price["provider_symbol"], "600519")
        self.assertEqual(price["data_source"]["data_source_id"], "live:akshare:market_price:600519.SH:2026-05-15")
        self.assertEqual(price["data_source"]["dataset"], "market_price")

    @patch("mcpuniverse.mcp.servers.finance_shared.external_providers.akshare._load_akshare")
    def test_akshare_provider_normalizes_hk_market_price(self, load_akshare_mock):
        class FakeAkshare:
            @staticmethod
            def stock_hk_hist(**kwargs):
                return pd.DataFrame([
                    {"日期": "2026-05-14", "开盘": 474.2, "最高": 479.6, "最低": 458.6, "收盘": 460.2, "成交量": 39339032},
                    {"日期": "2026-05-15", "开盘": 459.0, "最高": 462.6, "最低": 454.2, "收盘": 456.4, "成交量": 26449868},
                ])

            @staticmethod
            def stock_hk_company_profile_em(**kwargs):
                return pd.DataFrame([
                    {"公司名称": "腾讯控股有限公司", "所属行业": "软件服务"},
                ])

        load_akshare_mock.return_value = FakeAkshare
        provider = AKShareMarketDataProvider(
            instrument={
                "ticker": "0700.HK",
                "market": "HK",
                "exchange": "HKEX",
                "currency": "HKD",
                "provider": "akshare",
                "provider_symbol": "00700",
            }
        )

        price = provider.get_market_price("0700.HK", "2026-05-17")

        self.assertEqual(price["ticker"], "0700.HK")
        self.assertEqual(price["close"], 456.4)
        self.assertEqual(price["currency"], "HKD")
        self.assertEqual(price["market"], "HK")
        self.assertEqual(price["provider_symbol"], "00700")
        self.assertEqual(price["data_source"]["data_source_id"], "live:akshare:market_price:0700.HK:2026-05-15")

        company = provider.get_company_fundamentals("0700.HK")
        self.assertEqual(company["company_name"], "腾讯控股有限公司")
        self.assertEqual(company["sector"], "软件服务")
        self.assertEqual(company["currency"], "HKD")
        self.assertEqual(company["market"], "HK")
        self.assertEqual(company["unsupported_fields"], ["financial_statements", "valuation_multiples"])

    def test_ticker_resolver_routes_without_fixture_metadata(self):
        self.assertEqual(resolve_ticker_route("AAPL")["provider"], "fmp")
        self.assertEqual(resolve_ticker_route("600519.SH")["provider_symbol"], "600519")
        self.assertEqual(resolve_ticker_route("000001.SZ")["exchange"], "SZSE")
        self.assertEqual(resolve_ticker_route("0700.HK")["provider_symbol"], "00700")
        with self.assertRaisesRegex(FinanceDataError, "Unsupported ticker"):
            resolve_ticker_route("STRUCT_NOTE_NDX_BUFFER_2027")

if __name__ == "__main__":
    unittest.main()
