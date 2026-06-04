#!/usr/bin/env python
"""Run the full MCP-Vault benchmark pipeline in one command."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from run_benchmark_report import (
    REPO_ROOT,
    CommandStep,
    PipelineError,
    add_common_arguments,
    build_benchmark_step,
    build_run_dir,
    ensure_run_directory,
    execute_step,
    print_output_summary,
    resolve_benchmark_config_path,
    resolve_path,
    validate_required_environment,
)


DEFAULT_PROBE_CONFIG = "mcpuniverse/benchmark/configs/test/clean_task_probe_models.yaml"
DEFAULT_WORLD_CONFIG = (
    "mcpuniverse/mcp/servers/finance_shared/world_configs/financial_services_seed42.yaml"
)
DEFAULT_JUDGE_CONFIDENCE_THRESHOLD = 0.8


def main() -> int:
    """Parse CLI arguments and run the full evaluation pipeline."""
    try:
        args = _parse_args()
        load_dotenv(REPO_ROOT / ".env")

        benchmark_config_path = resolve_benchmark_config_path(args.config)
        probe_config_path = resolve_path(args.probe_config)
        world_config_path = resolve_path(args.world_config)
        if not args.skip_filter:
            _validate_existing_file(probe_config_path, "--probe-config")
        if not args.skip_world_check:
            _validate_existing_file(world_config_path, "--world-config")

        if not args.skip_env_check:
            env_config_paths = [benchmark_config_path]
            if not args.skip_filter:
                env_config_paths.append(probe_config_path)
            validate_required_environment(env_config_paths)

        run_dir = build_run_dir(args.output_root, args.run_name)
        ensure_run_directory(run_dir, resume=args.resume, dry_run=args.dry_run)

        _run_pipeline(
            args=args,
            benchmark_config_path=benchmark_config_path,
            probe_config_path=probe_config_path,
            world_config_path=world_config_path,
            run_dir=run_dir,
        )
        print_output_summary(run_dir)
        if not args.skip_filter:
            print(f"  Benign filter: {run_dir / 'benign_filter'}")
        return 0
    except PipelineError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run world validation, benign task filtering, benchmark execution, "
            "and markdown report generation."
        ),
    )
    add_common_arguments(parser)
    parser.add_argument(
        "--probe-config",
        default=DEFAULT_PROBE_CONFIG,
        help=f"Probe model YAML used by benign filtering. Default: {DEFAULT_PROBE_CONFIG}",
    )
    parser.add_argument(
        "--world-config",
        default=DEFAULT_WORLD_CONFIG,
        help=f"Finance benchmark world YAML config. Default: {DEFAULT_WORLD_CONFIG}",
    )
    parser.add_argument(
        "--judge-confidence-threshold",
        type=float,
        default=DEFAULT_JUDGE_CONFIDENCE_THRESHOLD,
        help=f"Semantic equivalence judge confidence threshold. Default: {DEFAULT_JUDGE_CONFIDENCE_THRESHOLD}",
    )
    parser.add_argument(
        "--skip-world-check",
        action="store_true",
        help="Skip deterministic finance world validation.",
    )
    parser.add_argument(
        "--skip-filter",
        action="store_true",
        help="Skip benign filtering and run the benchmark on the original config.",
    )
    return parser.parse_args()


def _run_pipeline(
        args: argparse.Namespace,
        benchmark_config_path: Path,
        probe_config_path: Path,
        world_config_path: Path,
        run_dir: Path,
) -> None:
    if not args.skip_world_check:
        execute_step(_build_world_check_step(world_config_path), dry_run=args.dry_run)

    benchmark_input_config = benchmark_config_path
    if not args.skip_filter:
        filter_dir = run_dir / "benign_filter"
        clean_tasks_path = filter_dir / "clean_tasks.yaml"
        if clean_tasks_path.exists() and args.resume:
            print("")
            print("== Benign task filter ==")
            print(f"Reusing existing filtered benchmark: {clean_tasks_path}")
        else:
            if filter_dir.exists() and not args.dry_run:
                raise PipelineError(
                    "Benign filter output directory already exists without reusable clean_tasks.yaml: "
                    f"{filter_dir}"
                )
            execute_step(
                _build_filter_step(
                    benchmark_config_path=benchmark_config_path,
                    probe_config_path=probe_config_path,
                    filter_dir=filter_dir,
                    judge_confidence_threshold=args.judge_confidence_threshold,
                ),
                dry_run=args.dry_run,
            )
            if not args.dry_run and not clean_tasks_path.exists():
                raise PipelineError(f"Benign filter did not write expected file: {clean_tasks_path}")
        benchmark_input_config = clean_tasks_path

    execute_step(
        build_benchmark_step(
            config_path=benchmark_input_config,
            run_dir=run_dir,
            resume=args.resume,
            verbose=args.verbose,
        ),
        dry_run=args.dry_run,
    )


def _build_world_check_step(world_config_path: Path) -> CommandStep:
    return CommandStep(
        label="Finance world check",
        command=[
            sys.executable,
            str(REPO_ROOT / "scripts" / "build_finance_world.py"),
            "--config",
            str(world_config_path),
            "--check",
        ],
    )


def _build_filter_step(
        benchmark_config_path: Path,
        probe_config_path: Path,
        filter_dir: Path,
        judge_confidence_threshold: float,
) -> CommandStep:
    return CommandStep(
        label="Benign task filter",
        command=[
            sys.executable,
            str(REPO_ROOT / "scripts" / "filter_clean_tasks.py"),
            "--config",
            str(benchmark_config_path),
            "--probe-config",
            str(probe_config_path),
            "--output-dir",
            str(filter_dir),
            "--judge-confidence-threshold",
            str(judge_confidence_threshold),
        ],
    )


def _validate_existing_file(path: Path, option_name: str) -> None:
    if not path.exists():
        raise PipelineError(f"{option_name} file does not exist: {path}")
    if not path.is_file():
        raise PipelineError(f"{option_name} must point to a file: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
