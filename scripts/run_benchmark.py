"""Run MCP safety benchmark configs from the command line."""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = "test/financial_security_all_attacks_deepseek-v4-flash.yaml"
DEFAULT_STORE_FOLDER = "results/financial_security_all_attacks"
DEFAULT_TRACE_LOG = "log/financial_security_all_attacks.log"


def main() -> int:
    """Parse command-line arguments and run the benchmark."""
    _prepare_import_path()

    args = _parse_args()
    load_dotenv(REPO_ROOT / ".env")
    os.chdir(REPO_ROOT)

    return asyncio.run(_run(args))


def _prepare_import_path() -> None:
    root = str(REPO_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run an MCP safety benchmark config and store task-level results.",
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        help=f"Benchmark YAML path or bundled config name. Default: {DEFAULT_CONFIG}",
    )
    parser.add_argument(
        "--store-folder",
        default=DEFAULT_STORE_FOLDER,
        help=f"Folder for per-task evaluation JSON files. Default: {DEFAULT_STORE_FOLDER}",
    )
    parser.add_argument(
        "--trace-log",
        default=DEFAULT_TRACE_LOG,
        help=f"File path for trace records. Default: {DEFAULT_TRACE_LOG}",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate a markdown report under log/ after the run.",
    )
    parser.add_argument(
        "--report-dir",
        default="log",
        help="Folder for markdown reports when --report is set. Default: log",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse existing task result files instead of overwriting them.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print MCP tool lists and task prompts through existing verbose callbacks.",
    )
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> int:
    from mcpuniverse.benchmark.report import BenchmarkReport
    from mcpuniverse.benchmark.runner import BenchmarkRunner
    from mcpuniverse.callbacks.handlers.vprint import get_vprint_callbacks
    from mcpuniverse.tracer.collectors import FileCollector

    trace_log = _path_from_repo(args.trace_log)
    store_folder = _path_from_repo(args.store_folder)
    _ensure_parent(trace_log)
    store_folder.mkdir(parents=True, exist_ok=True)

    trace_collector = FileCollector(log_file=str(trace_log))
    callbacks = get_vprint_callbacks() if args.verbose else None
    runner = BenchmarkRunner(args.config)

    results = await runner.run(
        trace_collector=trace_collector,
        callbacks=callbacks,
        store_folder=str(store_folder),
        overwrite=not args.resume,
    )

    report_path = None
    if args.report:
        report_dir = _path_from_repo(args.report_dir)
        report_path = BenchmarkReport(
            runner,
            trace_collector=trace_collector,
            report_folder=report_dir,
        ).dump()

    _print_summary(results)
    print(f"Trace log: {trace_log}")
    print(f"Task results: {store_folder}")
    if args.report:
        print(f"Report: {report_path}")
    return 0


def _path_from_repo(path_text: str) -> Path:
    path = Path(path_text).expanduser()
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def _ensure_parent(path: Path) -> None:
    parent = path.parent
    if str(parent):
        parent.mkdir(parents=True, exist_ok=True)


def _print_summary(results: list[Any]) -> None:
    from mcpuniverse.benchmark.metrics import (
        attack_success_from_evaluation_results,
        evaluate_task_success_under_attack,
    )

    print("")
    print("=" * 66)
    print("Evaluation Result")
    print("-" * 66)
    for benchmark_result in results:
        print(benchmark_result.benchmark.description)
        for task_name, task_result in benchmark_result.task_results.items():
            evaluation_results = task_result["evaluation_results"]
            task_evaluations = evaluation_results[:-1] if len(evaluation_results) > 1 else evaluation_results
            task_passed = all(result.passed for result in task_evaluations)
            task_success_under_attack = (
                evaluate_task_success_under_attack(evaluation_results).passed
                if len(evaluation_results) > 1 else None
            )
            attack_success = (
                attack_success_from_evaluation_results(evaluation_results)
                if len(evaluation_results) > 1 else None
            )
            print(f"{task_name}")
            print(f"  task_passed: {task_passed}")
            print(f"  task_success_under_attack: {task_success_under_attack}")
            print(f"  attack_success: {attack_success}")
            for evaluation_result in evaluation_results:
                print(
                    "  "
                    f"{evaluation_result.config.op}: "
                    f"passed={evaluation_result.passed}"
                    f"{_reason_suffix(evaluation_result.reason)}"
                )
            print("-" * 66)


def _reason_suffix(reason: str) -> str:
    if not reason:
        return ""
    return f", reason={reason}"


if __name__ == "__main__":
    raise SystemExit(main())
