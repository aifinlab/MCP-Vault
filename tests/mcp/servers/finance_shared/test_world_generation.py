import json
import re
import tempfile
import unittest
import inspect
from pathlib import Path

import mcpuniverse.mcp.servers.finance_shared.data_loader as data_loader
from mcpuniverse.mcp.servers.finance_shared.constants import WORLD_ROOT
from mcpuniverse.mcp.servers.finance_shared.world_generation import (
    build_world,
    check_world,
    load_world_config,
    write_world,
)


CONFIG_PATH = Path("mcpuniverse/mcp/servers/finance_shared/world_configs/financial_services_seed42.yaml")
TASK_ROOT = Path("mcpuniverse/benchmark/configs/test/financial_security_tasks")
CONFIG_SHA = "test_config_sha"
ATTACK_ONLY_REFERENCE_KEYS = frozenset({
    "data_tampering",
    "evaluation_contract",
    "FINANCE_TASK_ATTACK_TEXT",
    "reports",
    "mcp_server_additions",
    "mcp_server_modifications",
    "task_material",
    "wrong_arguments_intent_injection",
    "wrong_function_intent_injection",
})


class TestFinanceWorldGeneration(unittest.TestCase):

    def test_same_config_and_seed_generate_identical_world(self):
        config = load_world_config(CONFIG_PATH)

        first = build_world(config, CONFIG_SHA)
        second = build_world(config, CONFIG_SHA)

        self.assertEqual(_canonical_json(first), _canonical_json(second))

    def test_different_seed_changes_generated_world(self):
        config = load_world_config(CONFIG_PATH)
        changed_config = config.model_copy(update={"seed": config.seed + 1})

        first = build_world(config, CONFIG_SHA)
        second = build_world(changed_config, CONFIG_SHA)

        self.assertNotEqual(_canonical_json(first["business_state"]["accounts"]), _canonical_json(second["business_state"]["accounts"]))

    def test_manifest_lists_existing_generated_datasets(self):
        config = load_world_config(CONFIG_PATH)
        world = build_world(config, CONFIG_SHA)
        manifest = world["manifest"]

        self.assertEqual(set(manifest["business_state"]), set(world["business_state"]))
        self.assertEqual(set(manifest["provider_data"]), set(world["provider_data"]))

    def test_generated_world_contains_no_legacy_snapshot_terms(self):
        config = load_world_config(CONFIG_PATH)
        world = build_world(config, CONFIG_SHA)
        payload = json.dumps(world)

        for legacy_term in ["snapshot_id", "external_snapshot", "market_snapshot", "instrument_master"]:
            self.assertNotIn(legacy_term, payload)

    def test_committed_seed42_world_matches_config(self):
        config = load_world_config(CONFIG_PATH)
        world = build_world(config, _actual_config_sha())

        self.assertEqual(check_world(world, WORLD_ROOT), [])

    def test_current_financial_services_tasks_reference_existing_world_objects(self):
        config = load_world_config(CONFIG_PATH)
        world = build_world(config, CONFIG_SHA)
        world_strings = _collect_strings(world)
        referenced_ids = _collect_task_reference_ids()

        missing = sorted(reference for reference in referenced_ids if reference not in world_strings)
        self.assertEqual(missing, [])

    def test_generated_accounts_are_single_currency(self):
        config = load_world_config(CONFIG_PATH)
        world = build_world(config, CONFIG_SHA)

        for account in world["business_state"]["accounts"]["accounts"]:
            for holding in account["holdings"]:
                self.assertEqual(_currency_for_ticker(holding["ticker"]), account["base_currency"])

    def test_write_world_rejects_existing_output_without_overwrite(self):
        config = load_world_config(CONFIG_PATH)
        world = build_world(config, CONFIG_SHA)

        with tempfile.TemporaryDirectory() as temp_dir:
            write_world(world, temp_dir)
            with self.assertRaises(FileExistsError):
                write_world(world, temp_dir)

    def test_runtime_loader_does_not_import_world_generation(self):
        self.assertNotIn("world_generation", inspect.getsource(data_loader))


def _actual_config_sha() -> str:
    import hashlib

    return hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest()


def _canonical_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _collect_strings(payload) -> set[str]:
    strings = set()
    if isinstance(payload, dict):
        for value in payload.values():
            strings.update(_collect_strings(value))
    elif isinstance(payload, list):
        for value in payload:
            strings.update(_collect_strings(value))
    elif isinstance(payload, str):
        strings.add(payload)
    return strings


def _collect_task_reference_ids() -> set[str]:
    patterns = [
        r"ACC-FS-\d{4}",
        r"CLIENT-FS-\d{4}",
        r"DOC-FS-[A-Z0-9-]+",
        r"ENT-FS-\d{4}",
        r"BRK-FS-\d{4}",
        r"FUND-FS-[A-Z0-9-]+",
        r"VAL-PKG-FS-\d{4}",
        r"US[0-9A-Z]{10}",
        r"TXN-FS-\d{4}",
        r"BOND-FS-[A-Z0-9]+",
        r"USD[A-Z]{3}",
    ]
    combined = re.compile("|".join(f"({pattern})" for pattern in patterns))
    references: set[str] = set()
    for task_path in TASK_ROOT.glob("*.json"):
        task_config = json.loads(task_path.read_text(encoding="utf-8"))
        text = json.dumps(_drop_attack_only_fields(task_config), sort_keys=True)
        references.update(match.group(0) for match in combined.finditer(text))
    return references


def _drop_attack_only_fields(payload):
    if isinstance(payload, dict):
        return {
            key: _drop_attack_only_fields(value)
            for key, value in payload.items()
            if key not in ATTACK_ONLY_REFERENCE_KEYS
        }
    if isinstance(payload, list):
        return [_drop_attack_only_fields(value) for value in payload]
    return payload


def _currency_for_ticker(ticker: str) -> str:
    if ticker.endswith(".SH") or ticker.endswith(".SZ"):
        return "CNY"
    if ticker.endswith(".HK"):
        return "HKD"
    return "USD"


if __name__ == "__main__":
    unittest.main()
