#!/usr/bin/env python3
"""Strict quality gate for enhanced Layer 4 architecture recovery."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_REPORT_SECTIONS = [
    "项目概览",
    "项目身份判断",
    "玩家主循环",
    "玩家控制方式",
    "核心玩法逻辑",
    "场景流程",
    "模块关系图",
    "核心模块职责",
    "项目如何工作",
    "系统划分",
    "场景流程",
    "关键依赖关系",
    "架构模式判断",
    "风险",
    "建议",
    "上游流程状态",
]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_gate(layer3_dir: Path, layer4_dir: Path) -> list[str]:
    failures: list[str] = []
    report = (layer4_dir / "architecture_report.md").read_text(encoding="utf-8")
    summary = read_json(layer4_dir / "architecture_summary.json")["data"]
    findings = read_json(layer4_dir / "findings.json")["data"]["findings"]
    risks = read_json(layer4_dir / "risks.json")["data"]["risks"]
    recommendations = read_json(layer4_dir / "recommendations.json")["data"]["recommendations"]
    annotations = read_json(layer3_dir / "semantic_annotations.json")["data"]

    for section in REQUIRED_REPORT_SECTIONS:
        if section not in report:
            failures.append(f"report missing section: {section}")

    features = summary.get("project_features", {})
    identity = summary.get("project_identity", {})
    if identity.get("primary_type") != "unknown" and not features.get("observed"):
        failures.append("project_features.observed is missing")
    if not identity.get("primary_type") or "confidence" not in identity or not identity.get("summary"):
        failures.append("project_identity is incomplete")
    if identity.get("primary_type") != "unknown" and len(identity.get("evidence", [])) < 1:
        failures.append("project_identity has no evidence items")

    gameplay_loop = summary.get("gameplay_loop", [])
    if len(gameplay_loop) < 1:
        failures.append("gameplay_loop has fewer than 1 item")
    for item in gameplay_loop:
        if not item.get("title") or not item.get("evidence"):
            failures.append(f"gameplay_loop item lacks title/evidence: {item.get('step')}")

    modules = summary.get("module_responsibilities", [])
    if len(modules) < 1:
        failures.append("module_responsibilities has fewer than 1 item")
    for item in modules:
        if not item.get("module") or not item.get("responsibility") or not item.get("evidence"):
            failures.append(f"module responsibility lacks module/responsibility/evidence: {item.get('module')}")

    narrative = summary.get("runtime_narrative", [])
    if len(narrative) < 3:
        failures.append("runtime_narrative has fewer than 3 items")
    for item in narrative:
        if not item.get("text") or not item.get("evidence"):
            failures.append(f"runtime_narrative item lacks text/evidence: {item.get('id')}")

    combat_logic = summary.get("core_combat_logic", [])
    if len(combat_logic) < 1:
        failures.append("core_combat_logic has fewer than 1 item")
    for item in combat_logic:
        if not item.get("text") or not item.get("evidence"):
            failures.append(f"core_combat_logic item lacks text/evidence: {item.get('id')}")

    control_model = summary.get("player_control_model", {})
    if identity.get("primary_type") != "unknown" and not control_model:
        failures.append("player_control_model is empty")
    if identity.get("primary_type") != "unknown" and not any(control_model.get(group) for group in ("movement", "selection", "actions", "ui_controls")):
        failures.append("player_control_model has no recognized control groups")
    for group in ("movement", "selection", "actions", "ui_controls"):
        for item in control_model.get(group, []):
            if not item.get("text") or not item.get("evidence"):
                failures.append(f"player_control_model {group} item lacks text/evidence: {item.get('id')}")

    dependencies = summary.get("key_dependencies", [])
    if len(dependencies) < 1:
        failures.append("key_dependencies has fewer than 1 item")
    for item in dependencies:
        if not item.get("description") or not item.get("evidence"):
            failures.append(f"key_dependency lacks description/evidence: {item.get('id')}")

    for collection_name, items in [("findings", findings), ("risks", risks), ("recommendations", recommendations)]:
        if not items:
            failures.append(f"{collection_name} is empty")
        for item in items:
            if not item.get("evidence"):
                failures.append(f"{collection_name} item missing evidence: {item.get('id')}")

    readiness = summary.get("upstream_readiness", {})
    if not readiness.get("ready_for_human_review"):
        if readiness.get("layer2_unresolved_edges", 0) > 0 or not summary.get("systems"):
            failures.append("upstream_readiness.ready_for_human_review is false")
    if not summary.get("scene_flow_abstraction", {}).get("mermaid", "").startswith("flowchart TD"):
        failures.append("scene_flow_abstraction.mermaid is missing or invalid")
    if not summary.get("module_map", {}).get("mermaid", "").startswith("flowchart TD"):
        failures.append("module_map.mermaid is missing or invalid")

    profile_evaluation_path = layer4_dir / "profile_evaluation.json"
    if profile_evaluation_path.exists():
        evaluations = read_json(profile_evaluation_path).get("data", {}).get("evaluations", [])
        if not evaluations:
            failures.append("profile_evaluation has no evaluations")
        project_identity_path = layer4_dir / "project_identity.json"
        if not project_identity_path.exists():
            failures.append("project_identity.json is missing for multi-profile output")
        else:
            identity_v2 = read_json(project_identity_path).get("data", {})
            if not identity_v2.get("primary") and not identity_v2.get("primary_candidates"):
                failures.append("project_identity has neither primary nor primary_candidates")
        if "project_identity_v2" not in summary:
            failures.append("architecture_summary missing project_identity_v2 for multi-profile output")

    for entity_id, annotation in annotations.items():
        if "scene_instance" in annotation.get("semantic_roles", []) and annotation.get("contained_roles"):
            if annotation.get("semantic_roles") != ["scene_instance"]:
                failures.append(f"scene instance mixes contained roles into semantic_roles: {entity_id}")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Run strict Layer 4 quality gate.")
    parser.add_argument("--layer3", required=True, help="Layer 3 artifact directory.")
    parser.add_argument("--layer4", required=True, help="Layer 4 artifact directory.")
    args = parser.parse_args()
    failures = run_gate(Path(args.layer3), Path(args.layer4))
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("Layer 4 quality gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
