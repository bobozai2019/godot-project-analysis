#!/usr/bin/env python3
"""Validate Layer 3 semantic artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_FILES = {
    "semantic_annotations.json",
    "systems.json",
    "pattern_matches.json",
    "semantic_findings.json",
    "semantic_report.md",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_artifacts(layer3_dir: Path | str, layer0_dir: Path | str | None = None) -> list[str]:
    root = Path(layer3_dir)
    errors: list[str] = []
    for name in sorted(REQUIRED_FILES):
        if not (root / name).exists():
            errors.append(f"missing required artifact: {name}")
    if errors:
        return errors

    annotations_artifact = read_json(root / "semantic_annotations.json")
    systems_artifact = read_json(root / "systems.json")
    patterns_artifact = read_json(root / "pattern_matches.json")
    findings_artifact = read_json(root / "semantic_findings.json")
    for expected, payload in {
        "semantic_annotations": annotations_artifact,
        "systems": systems_artifact,
        "pattern_matches": patterns_artifact,
        "semantic_findings": findings_artifact,
    }.items():
        errors.extend(validate_header(expected, payload))

    known_roles = None
    known_systems = None
    if layer0_dir:
        taxonomy_path = Path(layer0_dir) / "role_taxonomy.json"
        if taxonomy_path.exists():
            taxonomy = read_json(taxonomy_path).get("data", {})
            known_roles = set(taxonomy.get("roles", []))
            known_systems = set(taxonomy.get("systems", []))

    annotations = annotations_artifact.get("data", {})
    for entity_id, annotation in annotations.items():
        if "confidence" not in annotation or not 0 <= annotation["confidence"] <= 1:
            errors.append(f"{entity_id} has invalid confidence")
        if not annotation.get("evidence"):
            errors.append(f"{entity_id} annotation missing evidence")
        if known_roles is not None:
            for role in annotation.get("semantic_roles", []):
                if role.endswith("_relationship") or role in {"runtime_factory", "event_subscriber", "event_emitter"}:
                    continue
                if role not in known_roles:
                    errors.append(f"{entity_id} references unknown role: {role}")
        if known_systems is not None:
            for system in annotation.get("systems", []):
                if system not in known_systems:
                    errors.append(f"{entity_id} references unknown system: {system}")

    systems = systems_artifact.get("data", {}).get("systems", [])
    if not systems:
        errors.append("systems.json contains no systems")
    for system in systems:
        if not system.get("members"):
            errors.append(f"system has no members: {system.get('id')}")
        if not system.get("evidence"):
            errors.append(f"system has no evidence: {system.get('id')}")
        if known_systems is not None and system.get("kind") not in known_systems:
            errors.append(f"system kind is not in taxonomy: {system.get('kind')}")

    for match in patterns_artifact.get("data", {}).get("pattern_matches", []):
        if not match.get("evidence"):
            errors.append(f"pattern match missing evidence: {match.get('id')}")
        if not 0 <= match.get("confidence", -1) <= 1:
            errors.append(f"pattern match invalid confidence: {match.get('id')}")

    for finding in findings_artifact.get("data", {}).get("findings", []):
        if not finding.get("evidence"):
            errors.append(f"finding missing evidence: {finding.get('id')}")
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
    parser = argparse.ArgumentParser(description="Validate Godot Layer 3 semantic artifacts.")
    parser.add_argument("--input", required=True, help="Layer 3 artifact directory.")
    parser.add_argument("--layer0", help="Optional Layer 0 artifact directory for taxonomy checks.")
    args = parser.parse_args()
    errors = validate_artifacts(args.input, args.layer0)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Layer 3 semantic artifacts are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
