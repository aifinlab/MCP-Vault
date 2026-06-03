import os
import tempfile
import unittest
from pathlib import Path

from mcpuniverse.mcp.servers.finance_shared.data_loader import (
    FinanceDataError,
    load_business_state_path,
    load_business_state,
    load_provider_data,
    load_world,
)
from mcpuniverse.mcp.servers.finance_shared.schema import (
    BENCHMARK_WORLD_SOURCE_TYPE,
    STANDARD_SOURCE_TRUST_LEVELS,
    make_world_evidence_record,
)
from tests.mcp.servers.finance_shared.test_support import (
    WORLD_ID,
    clear_finance_world_env,
    configure_finance_world_env,
)


class TestBenchmarkWorldLoader(unittest.TestCase):

    def setUp(self):
        configure_finance_world_env()

    def tearDown(self):
        clear_finance_world_env()

    def test_load_world_manifest_and_datasets(self):
        manifest = load_world()
        accounts = load_business_state("accounts")
        documents = load_provider_data("source_documents")

        self.assertEqual(manifest["world_id"], WORLD_ID)
        self.assertEqual(accounts["world_id"], WORLD_ID)
        self.assertEqual(documents["world_id"], WORLD_ID)
        self.assertIn("payload_sha256", accounts)
        self.assertIn("payload_sha256", documents)

    def test_internal_business_paths_map_to_world_business_state(self):
        accounts = load_business_state_path("portfolios/accounts.json")

        self.assertEqual(accounts["world_id"], WORLD_ID)
        self.assertEqual(accounts["accounts"][0]["account_id"], "ACC-FS-0001")

    def test_missing_world_raises_clear_error(self):
        os.environ["FINANCE_BENCHMARK_WORLD_ID"] = "missing_world"

        with self.assertRaisesRegex(FinanceDataError, "World file does not exist"):
            load_world()

    def test_bad_world_manifest_raises_clear_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            world_root = Path(temp_dir) / "bad_world"
            world_root.mkdir()
            (world_root / "manifest.json").write_text("[]", encoding="utf-8")
            os.environ["FINANCE_BENCHMARK_WORLD_ID"] = "bad_world"
            os.environ["FINANCE_BENCHMARK_WORLD_ROOT"] = temp_dir

            with self.assertRaisesRegex(FinanceDataError, "World manifest must be a JSON object"):
                load_world()

    def test_world_evidence_uses_standard_schema(self):
        accounts = load_business_state("accounts")
        evidence = make_world_evidence_record(
            world_id=accounts["world_id"],
            dataset="accounts",
            source_type="account",
            source_id="ACC-FS-0001",
            source_trust_level="trusted_internal_system",
            payload_sha256=accounts["payload_sha256"],
            authoritative=True,
        )

        self.assertEqual(evidence["data_source"]["data_source_type"], BENCHMARK_WORLD_SOURCE_TYPE)
        self.assertEqual(evidence["data_source"]["world_id"], WORLD_ID)
        self.assertIn(evidence["source_trust_level"], STANDARD_SOURCE_TRUST_LEVELS)
        self.assertTrue(evidence["authoritative"])


if __name__ == "__main__":
    unittest.main()
