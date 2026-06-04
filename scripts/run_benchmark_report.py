#!/usr/bin/env python
"""Run the finance benchmark and generate a markdown report in one command."""
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import yaml
from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_CONFIG_ROOT = REPO_ROOT / "mcpuniverse" / "benchmark" / "configs"
DEFAULT_CONFIG = "test/financial_security_all_attacks_deepseek-v4-flash.yaml"
DEFAULT_OUTPUT_ROOT = "results/evaluation_runs"

PROVIDER_ENV_VARS = {
    "aaaapi": ("AAAAPI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "bailian": ("DASHSCOPE_API_KEY",),
    "claude": ("ANTHROPIC_API_KEY",),
    "claude-gateway": ("SALESFORCE_GATEWAY_KEY",),
    "claude_gateway": ("SALESFORCE_GATEWAY_KEY",),
    "deepseek": ("DEEPSEEK_API_KEY",),
    "gemini": ("GEMINI_API_KEY",),
    "grok": ("XAI_API_KEY",),
    "mistral": ("MISTRAL_API_KEY",),
    "ollama": ("OLLAMA_URL",),
    "openai": ("OPENAI_API_KEY",),
    "openai-agent": ("OPENAI_API_KEY",),
    "openai_agent": ("OPENAI_API_KEY",),
    "openrouter": ("OPENROUTER_API_KEY",),
    "qwen": ("QWEN_API_KEY",),
    "xai": ("XAI_API_KEY",),
}


class PipelineError(RuntimeError):
    """Raised when a pipeline precondition or step fails."""


@dataclass(frozen=True)
class CommandStep:
    """One external command in the evaluation pipeline."""

    label: str
    command: list[str]


def main() -> int:
    """Parse CLI arguments and run the report-only pipeline."""
    try:
        args = _parse_args()
        load_dotenv(REPO_ROOT / ".env")
        config_path = resolve_benchmark_config_path(args.config)
        if not args.skip_env_check:
            validate_required_environment([config_path])

        run_dir = build_run_dir(args.output_root, args.run_name)
        ensure_run_directory(run_dir, resume=args.resume, dry_run=args.dry_run)

        step = build_benchmark_step(
            config_path=config_path,
            run_dir=run_dir,
            resume=args.resume,
            verbose=args.verbose,
        )
        execute_step(step, dry_run=args.dry_run)
        print_output_summary(run_dir)
        return 0
    except PipelineError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """Add shared pipeline CLI options."""
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        help=f"Benchmark YAML path or bundled config name. Default: {DEFAULT_CONFIG}",
    )
    parser.add_argument(
        "--output-root",
        default=DEFAULT_OUTPUT_ROOT,
        help=f"Root folder for timestamped evaluation runs. Default: {DEFAULT_OUTPUT_ROOT}",
    )
    parser.add_argument(
        "--run-name",
        default=None,
        help="Run directory name under --output-root. Default: current timestamp.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse existing task result JSON files when the benchmark runner supports it.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print task prompts and available MCP tools through existing callbacks.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned commands without creating output folders or running evaluation steps.",
    )
    parser.add_argument(
        "--skip-env-check",
        action="store_true",
        help="Skip provider API key preflight checks.",
    )


def resolve_benchmark_config_path(config: str | Path) -> Path:
    """Resolve a benchmark config path using the bundled config root."""
    path = Path(config).expanduser()
    candidate_paths = []
    if path.is_absolute():
        candidate_paths.append(path)
    else:
        candidate_paths.append(REPO_ROOT / path)
        candidate_paths.append(BENCHMARK_CONFIG_ROOT / path)

    for candidate_path in candidate_paths:
        if candidate_path.exists():
            return candidate_path

    raise PipelineError(
        "Cannot find benchmark config file: "
        f"{config}. Tried: {', '.join(str(path) for path in candidate_paths)}"
    )


def resolve_path(path_text: str | Path) -> Path:
    """Resolve a repository-relative or absolute path."""
    path = Path(path_text).expanduser()
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def validate_required_environment(config_paths: Iterable[Path]) -> None:
    """Validate provider environment variables referenced by LLM configs."""
    required_env_vars = collect_required_env_vars(config_paths)
    missing_env_vars = [
        env_var for env_var in sorted(required_env_vars)
        if not os.environ.get(env_var, "").strip()
    ]
    if missing_env_vars:
        raise PipelineError(
            "Missing required environment variables for configured LLM providers: "
            f"{', '.join(missing_env_vars)}. Set them in .env or pass --skip-env-check."
        )


def collect_required_env_vars(config_paths: Iterable[Path]) -> set[str]:
    """Collect required environment variables from YAML LLM provider docs."""
    required_env_vars: set[str] = set()
    for config_path in config_paths:
        for document in _load_yaml_documents(config_path):
            if str(document.get("kind", "")).lower() != "llm":
                continue
            spec = document.get("spec", {})
            if not isinstance(spec, dict):
                raise PipelineError(f"LLM spec must be a YAML object: {config_path}")
            config = spec.get("config", {})
            if isinstance(config, dict) and str(config.get("api_key", "")).strip():
                continue
            provider_type = str(spec.get("type", "")).lower().strip()
            if not provider_type:
                raise PipelineError(f"LLM spec is missing provider type: {config_path}")
            if provider_type not in PROVIDER_ENV_VARS:
                raise PipelineError(
                    "Unsupported LLM provider for environment preflight: "
                    f"{provider_type}. Add it to PROVIDER_ENV_VARS or pass --skip-env-check."
                )
            required_env_vars.update(PROVIDER_ENV_VARS[provider_type])
    return required_env_vars


def build_run_dir(output_root: str | Path, run_name: str | None) -> Path:
    """Build the concrete timestamped run directory."""
    resolved_run_name = run_name or datetime.now().strftime("%Y%m%d_%H%M%S")
    if not resolved_run_name.strip():
        raise PipelineError("--run-name must not be empty.")
    if Path(resolved_run_name).name != resolved_run_name:
        raise PipelineError("--run-name must be a single directory name, not a path.")
    return resolve_path(output_root) / resolved_run_name


def ensure_run_directory(run_dir: Path, resume: bool, dry_run: bool) -> None:
    """Create or validate the top-level run directory."""
    if run_dir.exists() and not resume:
        raise PipelineError(f"Output run directory already exists: {run_dir}. Use --resume or a new --run-name.")
    if dry_run:
        return
    run_dir.mkdir(parents=True, exist_ok=resume)


def build_benchmark_step(
        config_path: Path,
        run_dir: Path,
        resume: bool,
        verbose: bool,
) -> CommandStep:
    """Build the existing benchmark runner command."""
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "run_benchmark.py"),
        "--config",
        str(config_path),
        "--store-folder",
        str(run_dir / "benchmark_results"),
        "--trace-log",
        str(run_dir / "logs" / "benchmark.log"),
        "--report",
        "--report-dir",
        str(run_dir / "reports"),
    ]
    if resume:
        command.append("--resume")
    if verbose:
        command.append("--verbose")
    return CommandStep(label="Benchmark and report", command=command)


def execute_step(step: CommandStep, dry_run: bool = False) -> None:
    """Run or print one pipeline command."""
    print("")
    print(f"== {step.label} ==")
    print(_format_command(step.command))
    if dry_run:
        return

    completed_process = subprocess.run(
        step.command,
        cwd=REPO_ROOT,
        env=build_subprocess_environment(),
        check=False,
    )
    if completed_process.returncode != 0:
        raise PipelineError(f"Step failed with exit code {completed_process.returncode}: {step.label}")


def build_subprocess_environment() -> dict[str, str]:
    """Return subprocess environment with repository imports enabled."""
    environment = os.environ.copy()
    existing_pythonpath = environment.get("PYTHONPATH", "")
    pythonpath_parts = [str(REPO_ROOT)]
    if existing_pythonpath:
        pythonpath_parts.append(existing_pythonpath)
    environment["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    return environment


def print_output_summary(run_dir: Path) -> None:
    """Print the standard output artifact locations."""
    print("")
    print("Output directories:")
    print(f"  Run: {run_dir}")
    print(f"  Task results: {run_dir / 'benchmark_results'}")
    print(f"  Trace log: {run_dir / 'logs' / 'benchmark.log'}")
    print(f"  Reports: {run_dir / 'reports'}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the MCP-Vault benchmark and generate a markdown report.",
    )
    add_common_arguments(parser)
    return parser.parse_args()


def _load_yaml_documents(config_path: Path) -> list[dict]:
    with config_path.open("r", encoding="utf-8") as config_file:
        documents = list(yaml.safe_load_all(config_file))
    return [document for document in documents if isinstance(document, dict)]


def _format_command(command: list[str]) -> str:
    return shlex.join(command)


if __name__ == "__main__":
    raise SystemExit(main())
