# MCP-Vault: Financial MCP Safety Benchmark

MCP-Vault is a benchmark for evaluating the security boundaries of LLM agents that use financial Model Context Protocol (MCP) tools. It focuses on whether agents can complete legitimate financial workflows while resisting adversarial instructions injected through prompts, tool metadata, tool responses, documents, and workflow context.

MCP-Vault is designed for research on financial MCP agent safety, tool-use robustness, and security-aware evaluation.

| Item | Value |
| --- | --- |
| Domain | Financial MCP agents |
| Benchmark Tasks | 384 paired benign/attacked tasks |
| Scenarios | 6 financial business scenarios |
| Attack Types | 15 attack types |
| Python | `>=3.10,<4` |
| License | BSD-3-Clause |

Paper and project links will be added after release.

## Overview

Financial agents often interact with heterogeneous data sources, internal records, external market data, compliance rules, documents, and user instructions. MCP-Vault evaluates whether an LLM agent can preserve the intended security boundary when these inputs are mixed with adversarial content.

The benchmark provides:

- Financial MCP servers and task environments
- Paired benign and attacked task samples
- A deterministic financial benchmark world
- Trace collection for tool-use analysis
- Finance-specific evaluators
- One-command evaluation scripts
- Scenario-aware markdown reports

## Benchmark Design

MCP-Vault covers six financial MCP scenarios:

| Scenario | Scope |
| --- | --- |
| S1 Market Data Retrieval | Market data, reference data, pricing, company data, and fixed-income lookup |
| S2 Portfolio State Inquiry | Client records, account state, holdings, exposure, and risk |
| S3 Compliance Assessment | Suitability, restricted-security screening, and compliance decisions |
| S4 Control Evidence Review | Policy, audit, control evidence, governance, and document-store checks |
| M1 Advisory Governance | Multi-tool client, portfolio, compliance, and governance workflows |
| M2 Valuation Reconciliation | NAV, subledger, transaction, rate, FX, and reconciliation workflows |

The benchmark includes attacks across data-level, function/tool-level, and intent-level interference. Scenario membership is defined in:

```text
mcpuniverse/benchmark/configs/test/scenario_task_paths.json
```

The default benchmark config is:

```text
mcpuniverse/benchmark/configs/test/financial_security_all_attacks_deepseek-v4-flash.yaml
```

## Repository Layout

```text
mcpuniverse/
  benchmark/                     Benchmark runner, reports, tasks, configs, and filtering logic
  evaluator/finance_security/    Finance-specific safety evaluators
  mcp/servers/finance_*          Finance MCP servers
  mcp/servers/finance_shared/    Shared financial world data and utilities
  tracer/                        Trace collectors and records
scripts/
  run_full_benchmark_pipeline.py  Full one-command evaluation pipeline
  run_benchmark_report.py         Report-only benchmark runner
  run_benchmark.py                Core benchmark runner
  filter_clean_tasks.py           Benign task filter
  build_finance_world.py          Deterministic finance world helper
tests/
  benchmark/                     Benchmark runner, report, and filter tests
  evaluator/                     Evaluator tests
  mcp/servers/                   MCP server tests
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Set the provider keys required by the benchmark configuration you use. The default benchmark uses `bailian`, which requires:

```text
DASHSCOPE_API_KEY
```

The full pipeline also runs the default probe config:

```text
mcpuniverse/benchmark/configs/test/clean_task_probe_models.yaml
```

That probe config requires:

```text
OPENAI_API_KEY
ANTHROPIC_API_KEY
GEMINI_API_KEY
```

Finance runtime defaults are listed in `.env.example`.

## Quick Start

Run the full evaluation pipeline:

```bash
PYTHONPATH=. python scripts/run_full_benchmark_pipeline.py
```

This performs:

```text
finance world check
  -> benign task filtering
  -> benchmark execution
  -> markdown report generation
```

Run the benchmark and report without task filtering:

```bash
PYTHONPATH=. python scripts/run_benchmark_report.py
```

Dry-run the planned commands without launching model calls:

```bash
PYTHONPATH=. python scripts/run_full_benchmark_pipeline.py --dry-run --skip-env-check
```

Default outputs are written under:

```text
results/evaluation_runs/<run_name>/
```

## Running Individual Steps

Run the core benchmark runner directly:

```bash
PYTHONPATH=. python scripts/run_benchmark.py \
  --config test/financial_security_all_attacks_deepseek-v4-flash.yaml \
  --store-folder results/financial_security_all_attacks \
  --trace-log log/financial_security_all_attacks.log \
  --report
```

Run the benign task filter directly:

```bash
PYTHONPATH=. python scripts/filter_clean_tasks.py \
  --config test/financial_security_all_attacks_deepseek-v4-flash.yaml \
  --probe-config mcpuniverse/benchmark/configs/test/clean_task_probe_models.yaml \
  --output-dir results/clean_task_filter
```

The filter writes:

```text
results/clean_task_filter/manifest.json
results/clean_task_filter/excluded_tasks.json
results/clean_task_filter/clean_tasks.yaml
```

Verify the deterministic finance world:

```bash
PYTHONPATH=. python scripts/build_finance_world.py \
  --config mcpuniverse/mcp/servers/finance_shared/world_configs/financial_services_seed42.yaml \
  --check
```

## Reports

Generated markdown reports summarize overall results, attack-type breakdowns, scenario breakdowns, invalid-attribution counts, and per-task details.

## Tests

```bash
PYTHONPATH=. pytest -q tests/benchmark
PYTHONPATH=. pytest -q tests/evaluator
PYTHONPATH=. pytest -q tests/mcp/servers
```

Run the one-command script tests:

```bash
PYTHONPATH=. pytest -q tests/benchmark/test_pipeline_scripts.py
```

## Docker

```bash
docker build -t mcp-vault .
docker run --rm --env-file .env -v "$(pwd)":/app -w /app mcp-vault \
  python -m pytest -q tests
```

## Responsible Use

MCP-Vault contains adversarial benchmark tasks intended for controlled research. Use it in isolated development or evaluation environments, keep API keys and generated traces private, and avoid committing benchmark outputs or local environment files.

The included finance servers are benchmark fixtures. They are not intended for production financial operations.

## Citation

Citation metadata will be updated after the paper is released.

## License

This project is released under the BSD-3-Clause license. See `LICENSE` for details.
