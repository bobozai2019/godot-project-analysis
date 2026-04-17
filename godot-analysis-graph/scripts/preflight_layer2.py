#!/usr/bin/env python3
"""Check whether Layer 0 and Layer 1 artifacts are ready for Layer 2/3."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

LAYER1_REQUIRED = {"project_inventory.json", "scene_parse.json", "script_parse.json", "dependency_extract.json"}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def check_readiness(layer0_dir: Path | str, layer1_dir: Path | str, include_addons: bool = False) -> dict[str, Any]:
    layer0 = Path(layer0_dir)
    layer1 = Path(layer1_dir)
    result: dict[str, Any] = {
        "layer1_ready": True,
        "layer0_semantic_coverage_ready": True,
        "errors": [],
        "warnings": [],
        "missing_layer0_semantics": {},
        "layer1_counts": {},
        "recommendations": [],
    }

    for name in sorted(LAYER1_REQUIRED):
        if not (layer1 / name).exists():
            result["errors"].append(f"missing Layer 1 artifact: {name}")
    if result["errors"]:
        result["layer1_ready"] = False
        return result

    scenes = read_json(layer1 / "scene_parse.json").get("data", {})
    inventory = read_json(layer1 / "project_inventory.json").get("data", {})
    dependencies = read_json(layer1 / "dependency_extract.json").get("data", {}).get("dependencies", [])

    node_count = 0
    missing_semantics: Counter[str] = Counter()
    foundation = {}
    foundation_path = layer0 / "foundation_semantics.json"
    if foundation_path.exists():
        foundation = read_json(foundation_path).get("data", {})
    else:
        result["warnings"].append("Layer 0 foundation_semantics.json is missing; graph can build, but Layer 3 semantic quality will suffer.")

    for scene_path, scene in scenes.items():
        if not include_addons and scene_path.startswith("res://addons/"):
            continue
        for node in scene.get("nodes", []):
            node_count += 1
            if not node.get("node_id"):
                result["errors"].append(f"node without node_id in {scene_path}")
            node_type = node.get("type")
            if node_type and node_type not in foundation and node_type not in {"PackedSceneInstance", "Unknown"}:
                missing_semantics[node_type] += 1

    for dep in dependencies:
        for key in ("source", "target", "type", "evidence"):
            if key not in dep:
                result["errors"].append(f"dependency missing {key}: {dep}")

    result["layer1_counts"] = {
        "scenes": len(inventory.get("scenes", [])),
        "scripts": len(inventory.get("scripts", [])),
        "resources": len(inventory.get("resources", [])),
        "dependencies": len(dependencies),
        "nodes_considered": node_count,
    }
    result["missing_layer0_semantics"] = dict(sorted(missing_semantics.items()))
    if result["errors"]:
        result["layer1_ready"] = False
    if missing_semantics:
        result["layer0_semantic_coverage_ready"] = False
        result["recommendations"].append("Extend Layer 0 semantics for missing node types before Layer 3.")
    if any(path.startswith("res://addons/") for path in inventory.get("scripts", [])):
        result["recommendations"].append("Add an exclude_addons option to Layer 1 for game-focused graphs.")
    if inventory.get("resources", []) and len(inventory.get("resources", [])) > 1000:
        result["recommendations"].append("Add resource filtering or referenced-resource-only mode for smaller graph indexes.")
    return result


def write_report(result: dict[str, Any], output: Path) -> None:
    lines = [
        "# Layer 2 Input Readiness Report",
        "",
        f"- Layer 1 ready for graph: {result['layer1_ready']}",
        f"- Layer 0 semantic coverage ready for Layer 3: {result['layer0_semantic_coverage_ready']}",
        f"- Errors: {len(result['errors'])}",
        f"- Warnings: {len(result['warnings'])}",
        "",
        "## Counts",
        "",
    ]
    for key, value in result["layer1_counts"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Missing Layer 0 Semantics", ""])
    if result["missing_layer0_semantics"]:
        for key, value in result["missing_layer0_semantics"].items():
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- None")
    lines.extend(["", "## Recommendations", ""])
    if result["recommendations"]:
        for item in result["recommendations"]:
            lines.append(f"- {item}")
    else:
        lines.append("- None")
    lines.append("")
    output.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Layer 0/Layer 1 readiness for Layer 2 graph building.")
    parser.add_argument("--layer0", required=True, help="Layer 0 artifact directory.")
    parser.add_argument("--layer1", required=True, help="Layer 1 artifact directory.")
    parser.add_argument("--output-json", help="Optional JSON readiness report path.")
    parser.add_argument("--output-md", help="Optional Markdown readiness report path.")
    parser.add_argument("--include-addons", action="store_true", help="Include addons when checking Layer 0 semantic coverage.")
    args = parser.parse_args()

    result = check_readiness(args.layer0, args.layer1, include_addons=args.include_addons)
    if args.output_json:
        Path(args.output_json).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.output_md:
        write_report(result, Path(args.output_md))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["layer1_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
