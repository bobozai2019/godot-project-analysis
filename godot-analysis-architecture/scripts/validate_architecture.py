#!/usr/bin/env python3
"""Validate Layer 4 architecture recovery artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_FILES = {
    "architecture_report.md",
    "architecture_summary.json",
    "findings.json",
    "module_map.mmd",
    "risks.json",
    "recommendations.json",
    "scene_flow.mmd",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_artifacts(layer4_dir: Path | str) -> list[str]:
    root = Path(layer4_dir)
    errors: list[str] = []
    for name in sorted(REQUIRED_FILES):
        if not (root / name).exists():
            errors.append(f"missing required artifact: {name}")
    if errors:
        return errors

    summary_artifact = read_json(root / "architecture_summary.json")
    findings_artifact = read_json(root / "findings.json")
    risks_artifact = read_json(root / "risks.json")
    recommendations_artifact = read_json(root / "recommendations.json")
    for expected, payload in {
        "architecture_summary": summary_artifact,
        "findings": findings_artifact,
        "risks": risks_artifact,
        "recommendations": recommendations_artifact,
    }.items():
        errors.extend(validate_header(expected, payload))

    summary = summary_artifact.get("data", {})
    if not summary.get("project_overview", {}).get("entry_scene"):
        errors.append("architecture_summary missing project_overview.entry_scene")
    if not summary.get("systems"):
        errors.append("architecture_summary contains no systems")
    features = summary.get("project_features", {})
    identity = summary.get("project_identity", {})
    if identity.get("primary_type") != "unknown" and not features.get("observed"):
        errors.append("architecture_summary missing project_features.observed")
    for key in ("primary_type", "confidence", "summary", "evidence"):
        if key not in identity:
            errors.append(f"architecture_summary project_identity missing {key}")
    if identity and identity.get("primary_type") != "unknown" and len(identity.get("evidence", [])) < 1:
        errors.append("architecture_summary project_identity must include evidence items")
    if len(summary.get("gameplay_loop", [])) < 1:
        errors.append("architecture_summary gameplay_loop must contain at least 1 item")
    for item in summary.get("gameplay_loop", []):
        if not item.get("title") or not item.get("evidence"):
            errors.append(f"gameplay_loop item missing title/evidence: {item.get('step')}")
    if len(summary.get("module_responsibilities", [])) < 1:
        errors.append("architecture_summary module_responsibilities must contain at least 1 item")
    for item in summary.get("module_responsibilities", []):
        if not item.get("module") or not item.get("responsibility") or not item.get("evidence"):
            errors.append(f"module_responsibilities item missing module/responsibility/evidence: {item.get('module')}")
    if len(summary.get("runtime_narrative", [])) < 3:
        errors.append("architecture_summary runtime_narrative must contain at least 3 items")
    for item in summary.get("runtime_narrative", []):
        if not item.get("evidence"):
            errors.append(f"runtime_narrative item missing evidence: {item.get('id')}")
    if len(summary.get("core_combat_logic", [])) < 1:
        errors.append("architecture_summary core_combat_logic must contain at least 1 item")
    for item in summary.get("core_combat_logic", []):
        if not item.get("text") or not item.get("evidence"):
            errors.append(f"core_combat_logic item missing text/evidence: {item.get('id')}")
    control_model = summary.get("player_control_model", {})
    if identity.get("primary_type") != "unknown" and not control_model:
        errors.append("architecture_summary missing player_control_model")
    if identity.get("primary_type") != "unknown" and not any(control_model.get(group) for group in ("movement", "selection", "actions", "ui_controls")):
        errors.append("architecture_summary player_control_model must contain at least one control group")
    for group in ("movement", "selection", "actions", "ui_controls"):
        for item in control_model.get(group, []):
            if not item.get("text") or not item.get("evidence"):
                errors.append(f"player_control_model {group} item missing text/evidence: {item.get('id')}")
    if len(summary.get("key_dependencies", [])) < 1:
        errors.append("architecture_summary key_dependencies must contain at least 1 item")
    for item in summary.get("key_dependencies", []):
        if not item.get("evidence"):
            errors.append(f"key_dependencies item missing evidence: {item.get('id')}")
    if "architecture_patterns" not in summary:
        errors.append("architecture_summary missing architecture_patterns")
    if "upstream_readiness" not in summary:
        errors.append("architecture_summary missing upstream_readiness")
    if not summary.get("scene_flow_abstraction", {}).get("mermaid", "").startswith("flowchart TD"):
        errors.append("architecture_summary scene_flow_abstraction.mermaid must start with flowchart TD")
    if not summary.get("module_map", {}).get("mermaid", "").startswith("flowchart TD"):
        errors.append("architecture_summary module_map.mermaid must start with flowchart TD")
    if not (root / "scene_flow.mmd").read_text(encoding="utf-8").startswith("flowchart TD"):
        errors.append("scene_flow.mmd must start with flowchart TD")
    if not (root / "module_map.mmd").read_text(encoding="utf-8").startswith("flowchart TD"):
        errors.append("module_map.mmd must start with flowchart TD")

    for collection_name, artifact_name in [
        ("findings", "findings.json"),
        ("risks", "risks.json"),
        ("recommendations", "recommendations.json"),
    ]:
        items = read_json(root / artifact_name).get("data", {}).get(collection_name, [])
        if not items:
            errors.append(f"{artifact_name} has no {collection_name}")
        for item in items:
            if not item.get("id") or not item.get("title"):
                errors.append(f"{artifact_name} item missing id/title: {item}")
            if "evidence" not in item or not item["evidence"]:
                errors.append(f"{artifact_name} item missing evidence: {item.get('id')}")

    report = (root / "architecture_report.md").read_text(encoding="utf-8")
    for section in ["项目概览", "项目身份判断", "玩家主循环", "玩家控制方式", "核心玩法逻辑", "场景流程", "模块关系图", "核心模块职责", "项目如何工作", "系统划分", "关键依赖关系", "架构模式判断", "风险", "建议"]:
        if section not in report:
            errors.append(f"architecture_report.md missing section: {section}")
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
    parser = argparse.ArgumentParser(description="Validate Godot Layer 4 architecture artifacts.")
    parser.add_argument("--input", required=True, help="Layer 4 artifact directory.")
    args = parser.parse_args()
    errors = validate_artifacts(args.input)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Layer 4 architecture artifacts are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
