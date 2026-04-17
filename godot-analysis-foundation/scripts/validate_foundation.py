#!/usr/bin/env python3
"""Validate Layer 0 Godot semantic foundation artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_FILES = {
    "foundation_semantics.json",
    "api_semantics.json",
    "pattern_rules.json",
    "role_taxonomy.json",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_artifacts(layer0_dir: Path | str) -> list[str]:
    root = Path(layer0_dir)
    errors: list[str] = []

    for name in sorted(REQUIRED_FILES):
        if not (root / name).exists():
            errors.append(f"missing required artifact: {name}")
    if errors:
        return errors

    taxonomy = read_json(root / "role_taxonomy.json")
    semantics = read_json(root / "foundation_semantics.json")
    api_semantics = read_json(root / "api_semantics.json")
    patterns = read_json(root / "pattern_rules.json")

    for payload_name, payload in {
        "role_taxonomy": taxonomy,
        "foundation_semantics": semantics,
        "api_semantics": api_semantics,
        "pattern_rules": patterns,
    }.items():
        errors.extend(validate_header(payload_name, payload))

    taxonomy_data = taxonomy.get("data", {})
    known_categories = set(taxonomy_data.get("categories", {}).keys())
    known_systems = set(taxonomy_data.get("systems", []))
    known_roles = set(taxonomy_data.get("roles", []))
    known_api_semantics = {
        value.get("semantic") for value in api_semantics.get("data", {}).values() if isinstance(value, dict)
    }

    for class_name, definition in semantics.get("data", {}).items():
        category = definition.get("category")
        if category not in known_categories:
            errors.append(f"{class_name} references unknown category: {category}")
        for role in definition.get("roles", []):
            if role not in known_roles:
                errors.append(f"{class_name} references unknown role: {role}")
        for system in definition.get("systems", []):
            if system not in known_systems:
                errors.append(f"{class_name} references unknown system: {system}")
        errors.extend(validate_confidence(f"class {class_name}", definition))
        errors.extend(validate_source(f"class {class_name}", definition))

    for api_name, definition in api_semantics.get("data", {}).items():
        semantic = definition.get("semantic")
        if not semantic:
            errors.append(f"{api_name} is missing semantic")
        for system in definition.get("systems", []):
            if system not in known_systems:
                errors.append(f"{api_name} references unknown system: {system}")
        errors.extend(validate_confidence(f"api {api_name}", definition))
        errors.extend(validate_source(f"api {api_name}", definition))

    for pattern_name, definition in patterns.get("data", {}).items():
        for system in definition.get("systems", []):
            if system not in known_systems:
                errors.append(f"{pattern_name} references unknown system: {system}")
        for category in definition.get("required_categories", []):
            if category not in known_categories:
                errors.append(f"{pattern_name} references unknown required category: {category}")
        required_category = definition.get("required_category")
        if required_category and required_category not in known_categories:
            errors.append(f"{pattern_name} references unknown required category: {required_category}")
        for api_semantic in definition.get("required_api_semantics", []):
            if api_semantic not in known_api_semantics:
                errors.append(f"{pattern_name} references unknown API semantic: {api_semantic}")
        errors.extend(validate_confidence(f"pattern {pattern_name}", definition))
        errors.extend(validate_source(f"pattern {pattern_name}", definition))

    return errors


def validate_header(expected_artifact_type: str, payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("artifact_type") != expected_artifact_type:
        errors.append(f"{expected_artifact_type} has wrong artifact_type: {payload.get('artifact_type')}")
    if not payload.get("schema_version"):
        errors.append(f"{expected_artifact_type} is missing schema_version")
    if not payload.get("generator"):
        errors.append(f"{expected_artifact_type} is missing generator")
    if "data" not in payload:
        errors.append(f"{expected_artifact_type} is missing data")
    return errors


def validate_confidence(context: str, definition: dict[str, Any]) -> list[str]:
    confidence = definition.get("confidence")
    if not isinstance(confidence, int | float) or not 0 <= confidence <= 1:
        return [f"{context} has invalid confidence: {confidence}"]
    return []


def validate_source(context: str, definition: dict[str, Any]) -> list[str]:
    source = definition.get("source")
    if not isinstance(source, dict) or not source.get("kind") or not source.get("rule_id"):
        return [f"{context} is missing source.kind/source.rule_id"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Godot Layer 0 semantic foundation artifacts.")
    parser.add_argument("--input", required=True, help="Directory containing Layer 0 artifacts.")
    args = parser.parse_args()
    errors = validate_artifacts(Path(args.input))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Layer 0 foundation artifacts are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
