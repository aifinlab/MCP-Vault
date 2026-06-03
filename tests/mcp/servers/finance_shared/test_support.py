import os
from unittest.mock import patch

from mcpuniverse.mcp.servers.finance_shared.data_loader import clear_finance_data_cache
from tests.mcp.servers.finance_shared.fake_live_provider import FakeLiveMarketDataProvider

WORLD_ID = "financial_services_seed42"


def configure_finance_world_env() -> None:
    os.environ["FINANCE_DATA_MODE"] = "live"
    os.environ["FINANCE_MARKET_DATA_PROVIDER"] = "fmp"
    os.environ["FINANCE_BENCHMARK_WORLD_ID"] = WORLD_ID
    clear_finance_data_cache()


def clear_finance_world_env() -> None:
    for key in [
        "FINANCE_DATA_MODE",
        "FINANCE_MARKET_DATA_PROVIDER",
        "FINANCE_BENCHMARK_WORLD_ID",
        "FINANCE_BENCHMARK_WORLD_ROOT",
        "FINANCE_TASK_MATERIAL_PATH",
        "FINANCE_MACRO_DATA_PROVIDERS",
        "FMP_API_KEY",
        "FRED_API_KEY",
    ]:
        os.environ.pop(key, None)
    clear_finance_data_cache()


def patch_live_market_provider():
    return patch(
        "mcpuniverse.mcp.servers.finance_shared.data_loader.get_live_market_data_provider",
        return_value=FakeLiveMarketDataProvider(),
    )
