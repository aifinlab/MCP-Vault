#!/usr/bin/env python
"""Build deterministic finance benchmark worlds from YAML config."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from mcpuniverse.mcp.servers.finance_shared.constants import WORLD_ROOT
from mcpuniverse.mcp.servers.finance_shared.world_generation import (
    build_world,
    check_world,
    load_world_config,
    write_world,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a deterministic finance benchmark world.")
    parser.add_argument("--config", required=True, help="Path to the world YAML config.")
    parser.add_argument("--output-root", default=str(WORLD_ROOT), help="Directory that contains generated world folders.")
    parser.add_argument("--allow-overwrite", action="store_true", help="Replace an existing generated world directory.")
    parser.add_argument("--check", action="store_true", help="Verify that committed world files match the generated output.")
    args = parser.parse_args()

    config_path = Path(args.config)
    config = load_world_config(config_path)
    world = build_world(config, _sha256_file(config_path))

    output_root = Path(args.output_root)
    if args.check:
        mismatches = check_world(world, output_root)
        if mismatches:
            print("Generated world does not match committed files:", file=sys.stderr)
            for mismatch in mismatches:
                print(f"  - {mismatch}", file=sys.stderr)
            return 1
        print(f"World {config.world_id} matches {config_path}")
        return 0

    world_dir = write_world(world, output_root, allow_overwrite=args.allow_overwrite)
    print(f"Wrote world {config.world_id} to {world_dir}")
    return 0


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
