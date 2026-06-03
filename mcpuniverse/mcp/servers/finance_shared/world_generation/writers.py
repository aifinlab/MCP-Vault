"""Filesystem writers for generated benchmark worlds."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


def write_world(world: dict[str, Any], output_root: str | Path, allow_overwrite: bool = False) -> Path:
    """Write a generated world to output_root and return the world directory."""
    world_id = world["manifest"]["world_id"]
    world_dir = Path(output_root) / world_id
    if world_dir.exists():
        if not allow_overwrite:
            raise FileExistsError(f"World already exists: {world_dir}. Use --allow-overwrite to replace it.")
        shutil.rmtree(world_dir)
    (world_dir / "business_state").mkdir(parents=True, exist_ok=True)
    (world_dir / "provider_data").mkdir(parents=True, exist_ok=True)

    _write_json(world_dir / "manifest.json", world["manifest"])
    for dataset, payload in world["business_state"].items():
        _write_json(world_dir / "business_state" / f"{dataset}.json", payload)
    for dataset, payload in world["provider_data"].items():
        _write_json(world_dir / "provider_data" / f"{dataset}.json", payload)
    return world_dir


def check_world(world: dict[str, Any], output_root: str | Path) -> list[str]:
    """Return a list of mismatches between generated payloads and committed files."""
    world_id = world["manifest"]["world_id"]
    world_dir = Path(output_root) / world_id
    expected = _expected_files(world)
    mismatches: list[str] = []
    for relative_path, payload in expected.items():
        path = world_dir / relative_path
        if not path.is_file():
            mismatches.append(f"missing {relative_path}")
            continue
        actual_bytes = path.read_bytes()
        expected_bytes = _json_bytes(payload)
        if actual_bytes != expected_bytes:
            mismatches.append(f"changed {relative_path}")

    actual_files = {
        path.relative_to(world_dir).as_posix()
        for path in world_dir.rglob("*.json")
        if path.is_file()
    } if world_dir.exists() else set()
    extra_files = sorted(actual_files - set(expected))
    mismatches.extend(f"extra {relative_path}" for relative_path in extra_files)
    return mismatches


def _expected_files(world: dict[str, Any]) -> dict[str, dict[str, Any]]:
    files = {"manifest.json": world["manifest"]}
    for dataset, payload in world["business_state"].items():
        files[f"business_state/{dataset}.json"] = payload
    for dataset, payload in world["provider_data"].items():
        files[f"provider_data/{dataset}.json"] = payload
    return files


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_bytes(_json_bytes(payload))


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
