#!/usr/bin/env python3
"""Validate Layer 1 parser artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_FILES = {
    "project_inventory.json",
    "scene_parse.json",
    "script_parse.json",
    "dependency_extract.json",
    "parser_report.md",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_artifacts(layer1_dir: Path | str) -> list[str]:
    root = Path(layer1_dir)
    errors: list[str] = []
    for name in sorted(REQUIRED_FILES):
        if not (root / name).exists():
            errors.append(f"missing required artifact: {name}")
    if errors:
        return errors

    inventory = read_json(root / "project_inventory.json")
    scenes = read_json(root / "scene_parse.json")
    scripts = read_json(root / "script_parse.json")
    dependencies = read_json(root / "dependency_extract.json")

    for expected, payload in {
        "project_inventory": inventory,
        "scene_parse": scenes,
        "script_parse": scripts,
        "dependency_extract": dependencies,
    }.items():
        errors.extend(validate_header(expected, payload))

    scene_ids = set()
    node_ids = set()
    for scene_path, scene in scenes.get("data", {}).items():
        expected_scene_id = f"scene:{scene_path}"
        if scene.get("scene_id") != expected_scene_id:
            errors.append(f"{scene_path} has mismatched scene_id")
        if scene.get("scene_id") in scene_ids:
            errors.append(f"duplicate scene_id: {scene.get('scene_id')}")
        scene_ids.add(scene.get("scene_id"))
        for node in scene.get("nodes", []):
            node_id = node.get("node_id")
            if not node_id:
                errors.append(f"{scene_path} has node without node_id")
            elif node_id in node_ids:
                errors.append(f"duplicate node_id: {node_id}")
            node_ids.add(node_id)

    script_ids = set()
    for script_path, script in scripts.get("data", {}).items():
        expected_script_id = f"script:{script_path}"
        if script.get("script_id") != expected_script_id:
            errors.append(f"{script_path} has mismatched script_id")
        if script.get("script_id") in script_ids:
            errors.append(f"duplicate script_id: {script.get('script_id')}")
        script_ids.add(script.get("script_id"))

    known_targets = scene_ids | script_ids | node_ids
    for dependency in dependencies.get("data", {}).get("dependencies", []):
        for key in ("source", "target", "type", "evidence"):
            if key not in dependency:
                errors.append(f"dependency missing {key}: {dependency}")
        target = dependency.get("target")
        if target and target.startswith(("scene:", "script:", "node:")) and target not in known_targets:
            # Resource paths, signal pseudo-nodes, and future graph nodes are allowed to be resolved by Layer 2.
            if not target.startswith("signal:"):
                dependency["unresolved"] = True

    return errors


def validate_header(expected_artifact_type: str, payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("artifact_type") != expected_artifact_type:
        errors.append(f"{expected_artifact_type} has wrong artifact_type: {payload.get('artifact_type')}")
    for key in ("schema_version", "generator", "project_root", "generated_at", "data"):
        if key not in payload:
            errors.append(f"{expected_artifact_type} is missing {key}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Godot Layer 1 parser artifacts.")
    parser.add_argument("--input", required=True, help="Directory containing Layer 1 artifacts.")
    args = parser.parse_args()
    errors = validate_artifacts(Path(args.input))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Layer 1 parser artifacts are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
