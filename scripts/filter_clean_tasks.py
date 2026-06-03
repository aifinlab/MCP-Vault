"""Run local-MCP-withheld clean task filtering from the command line."""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = "test/financial_services_safety/financial_security_all_attacks.yaml"
DEFAULT_PROBE_CONFIG = "mcpuniverse/benchmark/configs/test/financial_services_safety/clean_task_probe_models.yaml"
DEFAULT_OUTPUT_DIR = "results/clean_task_filter"


def main() -> int:
    """Parse CLI arguments and run the filtering experiment."""
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
        description=(
            "Filter finance safety tasks by withholding the local benchmark MCP "
            "and writing a clean benchmark config."
        ),
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        help=f"Benchmark YAML path or bundled config name. Default: {DEFAULT_CONFIG}",
    )
    parser.add_argument(
        "--probe-config",
        default=DEFAULT_PROBE_CONFIG,
        help=f"YAML file with exactly three `kind: llm` probe configs. Default: {DEFAULT_PROBE_CONFIG}",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Folder for manifest and filtered benchmark YAML. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--judge-confidence-threshold",
        type=float,
        default=0.8,
        help="Minimum judge confidence for semantic equivalence. Default: 0.8",
    )
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> int:
    from mcpuniverse.benchmark.task_filter import CleanTaskFilter

    task_filter = CleanTaskFilter(
        benchmark_config=args.config,
        probe_config=args.probe_config,
        output_dir=args.output_dir,
        judge_confidence_threshold=args.judge_confidence_threshold,
    )
    records = await task_filter.run()
    _print_summary(records, Path(args.output_dir))
    return 0


def _print_summary(records, output_dir: Path) -> None:
    counts = {}
    for record in records:
        counts[record.decision] = counts.get(record.decision, 0) + 1

    print("")
    print("=" * 66)
    print("Local-MCP-Withheld Task Filter")
    print("-" * 66)
    for decision, count in sorted(counts.items()):
        print(f"{decision}: {count}")
    print("-" * 66)
    print(f"Manifest: {output_dir / 'manifest.json'}")
    print(f"Filtered benchmark: {output_dir / 'clean_tasks.yaml'}")
    print(f"Excluded tasks: {output_dir / 'excluded_tasks.json'}")


if __name__ == "__main__":
    raise SystemExit(main())
