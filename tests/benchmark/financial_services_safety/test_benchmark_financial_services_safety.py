import json
import unittest
from pathlib import Path

from mcpuniverse.benchmark.runner import BenchmarkRunner


CONFIG_ROOT = Path("mcpuniverse/benchmark/configs/test")


class TestFinancialServicesSafetyBenchmarkConfig(unittest.TestCase):

    def test_unified_attack_config_loads(self):
        benchmark = BenchmarkRunner("test/financial_security_all_attacks_deepseek-v4-flash.yaml")

        self.assertEqual(
            benchmark._benchmark_configs[0].description,
            "Unified financial security attack benchmark covering multisample and single-tool best attack tasks.",
        )
        self.assertEqual(len(benchmark._benchmark_configs[0].tasks), 384)

    def test_tasks_use_two_layer_finance_evaluators(self):
        benchmark = BenchmarkRunner("test/financial_security_all_attacks_deepseek-v4-flash.yaml")

        for task_path in benchmark._benchmark_configs[0].tasks:
            payload = _load_task(task_path)
            evaluators = payload["evaluators"]
            self.assertEqual(len(evaluators), 2)
            self.assertEqual(evaluators[0]["op"], "finance_security.task_validity")
            self.assertEqual(evaluators[0]["op_args"]["capability_gate_source"], "clean")
            self.assertEqual(evaluators[-1]["op"], "finance_security.two_layer_attack_success")
            self.assertTrue(payload["clean_baseline"])
            self.assertEqual(payload["task_env"]["FINANCE_BENCHMARK_WORLD_ID"], "financial_services_seed42")
            self.assertIn("evaluation_contract", payload)
            self.assertTrue(
                "rule_checks" in payload["evaluation_contract"]
                or "required_capabilities" in payload["evaluation_contract"]
            )
            self.assertNotIn("snapshot", json.dumps(payload).lower())

    def test_horizontal_task_mix_covers_p0_and_p1(self):
        benchmark = BenchmarkRunner("test/financial_security_all_attacks_deepseek-v4-flash.yaml")
        categories = [
            _load_task(task_path)["category"]
            for task_path in benchmark._benchmark_configs[0].tasks
        ]

        p0_count = sum("P0" in category or category == "Financial Services Safety" for category in categories)
        p1_count = sum("P1" in category for category in categories)
        self.assertGreaterEqual(p0_count, 1)
        self.assertGreaterEqual(p1_count, 1)


def _load_task(task_path: str) -> dict:
    with (CONFIG_ROOT / task_path).open("r", encoding="utf-8") as task_file:
        return json.load(task_file)


if __name__ == "__main__":
    unittest.main()
