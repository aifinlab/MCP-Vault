import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_SCRIPT = REPO_ROOT / "scripts" / "run_benchmark_report.py"
FULL_SCRIPT = REPO_ROOT / "scripts" / "run_full_benchmark_pipeline.py"


class TestEvaluationPipelineScripts(unittest.TestCase):

    def test_report_only_dry_run_builds_benchmark_report_command(self):
        with tempfile.TemporaryDirectory() as output_root:
            result = _run_script(
                REPORT_SCRIPT,
                "--dry-run",
                "--skip-env-check",
                "--output-root",
                output_root,
                "--run-name",
                "report_only",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("run_benchmark.py", result.stdout)
        self.assertIn("--report", result.stdout)
        self.assertIn("benchmark_results", result.stdout)
        self.assertIn("logs/benchmark.log", result.stdout)
        self.assertIn("reports", result.stdout)

    def test_full_pipeline_dry_run_builds_world_filter_and_benchmark_commands(self):
        with tempfile.TemporaryDirectory() as output_root:
            result = _run_script(
                FULL_SCRIPT,
                "--dry-run",
                "--skip-env-check",
                "--output-root",
                output_root,
                "--run-name",
                "full_pipeline",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("build_finance_world.py", result.stdout)
        self.assertIn("filter_clean_tasks.py", result.stdout)
        self.assertIn("run_benchmark.py", result.stdout)
        self.assertIn("benign_filter/clean_tasks.yaml", result.stdout)

    def test_full_pipeline_skip_filter_uses_original_config(self):
        with tempfile.TemporaryDirectory() as output_root:
            result = _run_script(
                FULL_SCRIPT,
                "--dry-run",
                "--skip-env-check",
                "--skip-filter",
                "--probe-config",
                str(Path(output_root) / "missing_probe.yaml"),
                "--output-root",
                output_root,
                "--run-name",
                "skip_filter",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("filter_clean_tasks.py", result.stdout)
        self.assertNotIn("benign_filter/clean_tasks.yaml", result.stdout)
        self.assertIn("financial_security_all_attacks_deepseek-v4-flash.yaml", result.stdout)

    def test_missing_provider_env_var_fails_preflight(self):
        with tempfile.TemporaryDirectory() as folder:
            config_path = Path(folder) / "openai_benchmark.yaml"
            config_path.write_text(
                "\n".join([
                    "kind: llm",
                    "spec:",
                    "  name: llm-1",
                    "  type: openai",
                    "  config:",
                    "    model_name: gpt-4.1",
                    "---",
                    "kind: benchmark",
                    "spec:",
                    "  description: Test benchmark",
                    "  agent: agent-1",
                    "  tasks: []",
                ]),
                encoding="utf-8",
            )
            result = _run_script(
                REPORT_SCRIPT,
                "--dry-run",
                "--config",
                str(config_path),
                "--output-root",
                folder,
                "--run-name",
                "missing_env",
                env_updates={"OPENAI_API_KEY": ""},
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("OPENAI_API_KEY", result.stderr)


def _run_script(script: Path, *args: str, env_updates: dict[str, str] | None = None):
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(REPO_ROOT)
    if env_updates:
        environment.update(env_updates)
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


if __name__ == "__main__":
    unittest.main()
