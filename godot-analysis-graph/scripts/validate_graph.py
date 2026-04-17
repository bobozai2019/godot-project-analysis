#!/usr/bin/env python3
"""Validate Layer 2 graph artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_FILES = {"graph.json", "graph_index.json", "graph_stats.json", "graph_build_report.md"}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_artifacts(layer2_dir: Path | str) -> list[str]:
    root = Path(layer2_dir)
    errors: list[str] = []
    for name in sorted(REQUIRED_FILES):
        if not (root / name).exists():
            errors.append(f"missing required artifact: {name}")
    if errors:
        return errors

    graph_artifact = read_json(root / "graph.json")
    index_artifact = read_json(root / "graph_index.json")
    stats_artifact = read_json(root / "graph_stats.json")
    for expected, payload in {"graph": graph_artifact, "graph_index": index_artifact, "graph_stats": stats_artifact}.items():
        errors.extend(validate_header(expected, payload))

    graph = graph_artifact.get("data", {})
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    node_ids = [node.get("id") for node in nodes]
    node_id_set = set(node_ids)
    if len(node_ids) != len(node_id_set):
        errors.append("duplicate graph node ids")

    for node in nodes:
        if not node.get("id") or not node.get("kind"):
            errors.append(f"node missing id/kind: {node}")

    for edge in edges:
        for key in ("id", "source", "target", "type"):
            if not edge.get(key):
                errors.append(f"edge missing {key}: {edge}")
        source_exists = edge.get("source") in node_id_set
        target_exists = edge.get("target") in node_id_set
        if (not source_exists or not target_exists) and not edge.get("unresolved"):
            errors.append(f"edge points to missing endpoint without unresolved flag: {edge.get('id')}")
        if edge.get("type") == "attaches":
            source = next((node for node in nodes if node.get("id") == edge.get("source")), {})
            target = next((node for node in nodes if node.get("id") == edge.get("target")), {})
            if source.get("kind") != "Node" or target.get("kind") != "Script":
                errors.append(f"attaches edge must be Node -> Script: {edge.get('id')}")

    stats = stats_artifact.get("data", {})
    if stats.get("nodes") != len(nodes):
        errors.append("graph_stats nodes count does not match graph")
    if stats.get("edges") != len(edges):
        errors.append("graph_stats edges count does not match graph")

    index = index_artifact.get("data", {})
    indexed_ids = set()
    for ids in index.get("nodes_by_kind", {}).values():
        indexed_ids.update(ids)
    missing_from_index = node_id_set - indexed_ids
    if missing_from_index:
        errors.append(f"nodes missing from nodes_by_kind index: {len(missing_from_index)}")

    return errors


def validate_header(expected_artifact_type: str, payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("artifact_type") != expected_artifact_type:
        errors.append(f"{expected_artifact_type} has wrong artifact_type: {payload.get('artifact_type')}")
    for key in ("schema_version", "generator", "project_root", "generated_at", "data"):
        if key not in payload:
            errors.append(f"{expected_artifact_type} missing {key}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Godot Layer 2 graph artifacts.")
    parser.add_argument("--input", required=True, help="Directory containing Layer 2 artifacts.")
    args = parser.parse_args()
    errors = validate_artifacts(Path(args.input))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Layer 2 graph artifacts are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
