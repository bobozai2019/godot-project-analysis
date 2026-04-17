#!/usr/bin/env python3
"""Build Layer 4 architecture recovery artifacts from Layer 2 and Layer 3."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GENERATOR = "godot-analysis-architecture"
SCHEMA_VERSION = "0.1.0"


def read_artifact(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def artifact(kind: str, project_root: str | None, data: Any) -> dict[str, Any]:
    return {
        "artifact_type": kind,
        "schema_version": SCHEMA_VERSION,
        "generator": GENERATOR,
        "godot_version": "4.x",
        "project_root": project_root,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "data": data,
    }


def recover(
    layer2_dir: Path | str,
    layer3_dir: Path | str,
    output_dir: Path | str,
    profile_path: Path | str | None = None,
    profile_dir: Path | str | None = None,
) -> None:
    layer2 = Path(layer2_dir)
    layer3 = Path(layer3_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    graph_artifact = read_artifact(layer2 / "graph.json")
    graph_stats_artifact = read_artifact(layer2 / "graph_stats.json")
    systems_artifact = read_artifact(layer3 / "systems.json")
    patterns_artifact = read_artifact(layer3 / "pattern_matches.json")
    findings_artifact = read_artifact(layer3 / "semantic_findings.json")
    annotations_artifact = read_artifact(layer3 / "semantic_annotations.json")

    graph = graph_artifact["data"]
    stats = graph_stats_artifact["data"]
    systems = systems_artifact["data"]["systems"]
    patterns = patterns_artifact["data"]["pattern_matches"]
    semantic_findings = findings_artifact["data"]
    annotations = annotations_artifact["data"]
    project_root = graph_artifact.get("project_root")
    profiles = load_profiles(profile_path=profile_path, profile_dir=profile_dir)
    profile_evaluations = [evaluate_profile(graph, profile) for profile in profiles] if profile_dir else []
    project_identity_v2 = select_project_identity(profile_evaluations, profiles) if profile_dir else None
    profile = selected_profile_for_identity(project_identity_v2, profiles) if project_identity_v2 else profiles[0]

    summary = build_summary(graph, stats, systems, patterns, semantic_findings, annotations, profile)
    if project_identity_v2:
        summary["project_identity_v2"] = project_identity_v2
        summary["project_identity"] = legacy_identity_from_v2(project_identity_v2, summary["project_identity"])
        summary["gameplay_loop"] = merge_v2_gameplay_loop(summary["gameplay_loop"], project_identity_v2, profile_evaluations, profiles)
    findings = build_findings(summary, systems, patterns, semantic_findings)
    risks = build_risks(summary, graph, systems, semantic_findings)
    recommendations = build_recommendations(risks, summary)
    readiness = assess_upstream_readiness(summary, semantic_findings, graph)
    summary["upstream_readiness"] = readiness
    report = build_report(summary, findings, risks, recommendations)

    write_json(out / "architecture_summary.json", artifact("architecture_summary", project_root, summary))
    write_json(out / "findings.json", artifact("findings", project_root, {"findings": findings}))
    write_json(out / "risks.json", artifact("risks", project_root, {"risks": risks}))
    write_json(out / "recommendations.json", artifact("recommendations", project_root, {"recommendations": recommendations}))
    if project_identity_v2:
        write_json(out / "profile_evaluation.json", artifact("profile_evaluation", project_root, {"evaluations": profile_evaluations}))
        write_json(out / "project_identity.json", artifact("project_identity", project_root, project_identity_v2))
        write_json(out / "gameplay_loop.json", artifact("gameplay_loop", project_root, {"steps": summary.get("gameplay_loop", [])}))
        write_json(out / "module_responsibilities.json", artifact("module_responsibilities", project_root, {"modules": summary.get("module_responsibilities", [])}))
    (out / "architecture_report.md").write_text(report, encoding="utf-8")
    (out / "scene_flow.mmd").write_text(summary.get("scene_flow_abstraction", {}).get("mermaid", "flowchart TD\n"), encoding="utf-8")
    (out / "module_map.mmd").write_text(summary.get("module_map", {}).get("mermaid", "flowchart TD\n"), encoding="utf-8")


def load_profile(profile_path: Path | str | None) -> dict[str, Any]:
    if not profile_path:
        return {"profile_id": "generic", "profile_layer": "primary", "feature_rules": {}, "identity_rules": {}}
    profile = json.loads(Path(profile_path).read_text(encoding="utf-8"))
    validate_profile_shape(profile)
    return profile


def load_profiles(profile_path: Path | str | None = None, profile_dir: Path | str | None = None) -> list[dict[str, Any]]:
    if profile_dir:
        root = Path(profile_dir)
        profiles = []
        for path in sorted(root.glob("*.json")):
            profile = json.loads(path.read_text(encoding="utf-8"))
            validate_profile_shape(profile)
            profiles.append(profile)
        if not profiles:
            raise ValueError(f"No Layer4 profiles found in {root}")
        return profiles
    return [load_profile(profile_path)]


def validate_profile_shape(profile: dict[str, Any]) -> None:
    if not isinstance(profile, dict):
        raise ValueError("Layer4 profile must be a JSON object.")
    for key in ("profile_id", "feature_rules", "identity_rules"):
        if key not in profile:
            raise ValueError(f"Layer4 profile missing {key}.")
    if not isinstance(profile.get("feature_rules"), dict):
        raise ValueError("Layer4 profile feature_rules must be an object.")
    if not isinstance(profile.get("identity_rules"), dict):
        raise ValueError("Layer4 profile identity_rules must be an object.")
    layer = profile.get("profile_layer", "primary")
    if layer not in {"primary", "modifier", "flavor"}:
        raise ValueError(f"Layer4 profile has invalid profile_layer: {layer}")
    if "compatible_with" in profile and not isinstance(profile["compatible_with"], list):
        raise ValueError("Layer4 profile compatible_with must be a list.")
    if "suppresses" in profile and not isinstance(profile["suppresses"], list):
        raise ValueError("Layer4 profile suppresses must be a list.")


def build_summary(
    graph: dict[str, Any],
    stats: dict[str, Any],
    systems: list[dict[str, Any]],
    patterns: list[dict[str, Any]],
    semantic_findings: dict[str, Any],
    annotations: dict[str, Any],
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profile = profile or {"profile_id": "generic", "feature_rules": {}, "identity_rules": {}}
    entry_scene = graph.get("metadata", {}).get("entry_scene")
    system_summary = [
        {
            "id": system["id"],
            "kind": system["kind"],
            "member_count": len(system.get("members", [])),
            "confidence": system.get("confidence", 0),
            "evidence": system.get("evidence", [])[:5],
        }
        for system in systems
    ]
    scene_flow = build_scene_flow(graph)
    key_dependencies = build_key_dependencies(graph, annotations)
    pattern_counts = Counter(pattern["pattern_id"] for pattern in patterns)
    architecture_patterns = {
        "event_driven": pattern_counts.get("event_driven_ui", 0) > 0 or count_edges(graph, "connects") > 0,
        "data_driven": has_system(systems, "Data") and count_edges(graph, "references") > 0,
        "manager_centric": has_system(systems, "Manager") and system_size(systems, "Manager") >= 3,
        "dynamic_scene_creation": pattern_counts.get("dynamic_scene_creation", 0) > 0 or count_edges(graph, "instantiates") > 0,
        "ui_gameplay_signal_bridge": pattern_counts.get("event_driven_ui", 0) > 0,
    }
    project_features = build_project_features(graph, systems, patterns, {}, profile)
    project_identity = infer_project_identity(project_features, profile)
    player_control_model = build_player_control_model(graph, systems, patterns, annotations, key_dependencies, profile, project_identity, project_features)
    gameplay_loop = build_gameplay_loop(graph, scene_flow, project_features, player_control_model, key_dependencies, profile, project_identity)
    core_combat_logic = build_core_combat_logic(graph, systems, patterns, annotations, key_dependencies, profile, project_identity, project_features)
    module_responsibilities = build_module_responsibilities(graph, annotations, profile, project_identity)
    scene_flow_abstraction = build_scene_flow_abstraction(scene_flow, profile, project_identity, project_features)
    module_map = build_module_map(module_responsibilities, profile, project_identity)
    report_quality = build_report_quality(graph, profile, project_identity, scene_flow_abstraction, module_map)
    return {
        "project_overview": {
            "entry_scene": entry_scene,
            "node_count": stats.get("nodes"),
            "edge_count": stats.get("edges"),
            "scene_count": stats.get("scenes"),
            "script_count": stats.get("scripts"),
            "resource_count": stats.get("resources"),
            "unresolved_edges": stats.get("unresolved_edges", 0),
        },
        "systems": system_summary,
        "scene_flow": scene_flow,
        "key_dependencies": key_dependencies,
        "project_features": project_features,
        "project_identity": project_identity,
        "gameplay_loop": gameplay_loop,
        "module_responsibilities": module_responsibilities,
        "runtime_narrative": build_runtime_narrative(entry_scene, scene_flow, system_summary, key_dependencies, pattern_counts),
        "core_combat_logic": core_combat_logic,
        "core_gameplay_logic": core_combat_logic,
        "player_control_model": player_control_model,
        "scene_flow_abstraction": scene_flow_abstraction,
        "module_map": module_map,
        "report_quality": report_quality,
        "architecture_patterns": architecture_patterns,
        "pattern_counts": dict(sorted(pattern_counts.items())),
        "semantic_readiness": semantic_findings.get("upstream_readiness", {}),
        "top_entities": top_entities(annotations),
    }


def build_scene_flow(graph: dict[str, Any]) -> dict[str, Any]:
    flows = []
    for edge in graph.get("edges", []):
        if edge.get("type") in {"instantiates", "transitions_to"} and edge.get("target", "").startswith("scene:"):
            flows.append(
                {
                    "source": edge["source"],
                    "target": edge["target"],
                    "type": edge["type"],
                    "evidence": edge.get("properties", {}).get("evidence_list", []) or [{"edge_id": edge["id"]}],
                }
            )
    return {"entry_scene": graph.get("metadata", {}).get("entry_scene"), "flows": flows}


def build_key_dependencies(graph: dict[str, Any], annotations: dict[str, Any]) -> list[dict[str, Any]]:
    dependency_priority = {"instantiates": 0, "attaches": 1, "connects": 2, "references": 3, "emits": 4}
    node_lookup = {node["id"]: node for node in graph.get("nodes", [])}
    dependencies = []
    for edge in graph.get("edges", []):
        if edge.get("type") not in dependency_priority:
            continue
        source_label = label_for(edge["source"], node_lookup)
        target_label = label_for(edge["target"], node_lookup)
        source_systems = annotations.get(edge["source"], {}).get("systems", [])
        target_systems = annotations.get(edge["target"], {}).get("systems", [])
        dependencies.append(
            {
                "id": edge["id"],
                "type": edge["type"],
                "source": edge["source"],
                "target": edge["target"],
                "source_label": source_label,
                "target_label": target_label,
                "source_systems": source_systems,
                "target_systems": target_systems,
                "description": describe_dependency(edge["type"], source_label, target_label),
                "evidence": edge.get("properties", {}).get("evidence_list", []) or [{"edge_id": edge["id"]}],
            }
        )
    dependencies.sort(key=lambda item: (dependency_priority.get(item["type"], 99), item["source"], item["target"]))
    return dependencies[:20]


def label_for(entity_id: str, node_lookup: dict[str, dict[str, Any]]) -> str:
    node = node_lookup.get(entity_id, {})
    props = node.get("properties", {})
    return props.get("path") or props.get("name") or props.get("node_type") or entity_id


def describe_dependency(edge_type: str, source_label: str, target_label: str) -> str:
    verbs = {
        "instantiates": "instantiates scene",
        "attaches": "uses script",
        "connects": "subscribes to signal/behavior",
        "references": "references data or asset",
        "emits": "emits signal",
    }
    return f"{source_label} {verbs.get(edge_type, edge_type)} {target_label}"


def build_runtime_narrative(
    entry_scene: str | None,
    scene_flow: dict[str, Any],
    systems: list[dict[str, Any]],
    key_dependencies: list[dict[str, Any]],
    pattern_counts: Counter,
) -> list[dict[str, Any]]:
    narrative = []
    flow_evidence = []
    if scene_flow.get("flows"):
        flow_evidence = scene_flow["flows"][:3]
    narrative.append(
        {
            "id": "runtime:entry_flow",
            "title": "项目从入口场景装配运行对象",
            "text": f"项目从 `{entry_scene}` 进入，并通过场景实例化装配主要运行对象。",
            "evidence": flow_evidence or [{"entry_scene": entry_scene}],
        }
    )
    gameplay = next((system for system in systems if system["kind"] == "Gameplay"), None)
    if gameplay:
        narrative.append(
            {
                "id": "runtime:gameplay_core",
                "title": "Gameplay 系统承载主要运行逻辑",
                "text": f"Gameplay 系统包含 {gameplay['member_count']} 个成员，是交互、状态推进和运行时对象处理的主要运行层。",
                "evidence": gameplay.get("evidence", [])[:5],
            }
        )
    ui = next((system for system in systems if system["kind"] == "UI"), None)
    if ui:
        narrative.append(
            {
                "id": "runtime:ui_layer",
                "title": "UI 系统作为玩家可见状态层",
                "text": f"UI 系统包含 {ui['member_count']} 个成员，主要承担 HUD、状态面板、暂停和结果显示。",
                "evidence": ui.get("evidence", [])[:5],
            }
        )
    if pattern_counts.get("event_driven_ui", 0) > 0:
        narrative.append(
            {
                "id": "runtime:event_bridge",
                "title": "UI 与 Gameplay 通过事件连接",
                "text": "语义模式显示 UI 与 Gameplay 之间存在事件驱动连接，适合用信号契约描述跨系统通信。",
                "evidence": [dep for dep in key_dependencies if dep["type"] == "connects"][:5] or [{"event_driven_ui": pattern_counts["event_driven_ui"]}],
            }
        )
    if pattern_counts.get("dynamic_scene_creation", 0) > 0:
        narrative.append(
            {
                "id": "runtime:dynamic_creation",
                "title": "运行时会动态创建场景对象",
                "text": f"检测到 {pattern_counts['dynamic_scene_creation']} 个动态场景创建模式，说明项目在运行中创建对象或切换运行实体。",
                "evidence": [dep for dep in key_dependencies if dep["type"] == "instantiates"][:5] or [{"dynamic_scene_creation": pattern_counts["dynamic_scene_creation"]}],
            }
        )
    return [item for item in narrative if item.get("evidence")]


def build_core_combat_logic(
    graph: dict[str, Any],
    systems: list[dict[str, Any]],
    patterns: list[dict[str, Any]],
    annotations: dict[str, Any],
    key_dependencies: list[dict[str, Any]],
    profile: dict[str, Any] | None = None,
    project_identity: dict[str, Any] | None = None,
    project_features: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    del patterns, annotations
    logic = render_profile_section(profile or {}, project_identity or {}, project_features or {}, "core_gameplay_logic_templates")
    if logic:
        return logic
    gameplay = next((system for system in systems if system.get("kind") == "Gameplay"), None)
    if gameplay:
        return [{
            "id": "core:gameplay_system",
            "title": "Gameplay 系统承载核心运行逻辑",
            "text": "当前未提供外部项目类型 profile，因此只基于 Layer3 系统划分给出通用核心逻辑判断。",
            "evidence": gameplay.get("evidence", [])[:5],
        }]
    if key_dependencies:
        return [{
            "id": "core:key_dependencies",
            "title": "关键依赖构成运行链路",
            "text": "场景实例、脚本挂载、资源引用和信号连接组成当前可恢复的运行链路。",
            "evidence": key_dependencies[:5],
        }]
    if graph.get("nodes"):
        return [{
            "id": "core:structural_nodes",
            "title": "结构节点提供最低限度的架构证据",
            "text": "当前只有通用图结构证据，无法在无外部 profile 的情况下推断更具体的玩法语义。",
            "evidence": evidence_for_nodes(graph.get("nodes", [])[:5]),
        }]
    return []


def build_player_control_model(
    graph: dict[str, Any],
    systems: list[dict[str, Any]],
    patterns: list[dict[str, Any]],
    annotations: dict[str, Any],
    key_dependencies: list[dict[str, Any]],
    profile: dict[str, Any] | None = None,
    project_identity: dict[str, Any] | None = None,
    project_features: dict[str, Any] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    del systems, annotations, key_dependencies
    model = {"movement": [], "selection": [], "actions": [], "ui_controls": []}
    for item in render_profile_section(profile or {}, project_identity or {}, project_features or {}, "player_control_templates"):
        group = item.pop("group", "ui_controls")
        model.setdefault(group, []).append(item)
    if not any(model.values()):
        input_candidates = [match for match in patterns if match.get("pattern_id") == "player_controller_candidate"]
        input_nodes = find_input_scripts(graph)
        if input_candidates or input_nodes:
            model["actions"].append({
                "id": "control:generic_input",
                "title": "存在输入或控制候选",
                "text": "在没有外部 profile 的情况下，只能确认项目存在输入处理或玩家控制候选，不能推断具体操作语义。",
                "evidence": input_candidates[:3] or evidence_for_nodes(input_nodes[:5]),
            })
    return {name: items for name, items in model.items() if items}


def build_project_features(
    graph: dict[str, Any],
    systems: list[dict[str, Any]],
    patterns: list[dict[str, Any]],
    player_control_model: dict[str, list[dict[str, Any]]],
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    del systems, patterns, player_control_model
    feature_rules = (profile or {}).get("feature_rules", {})
    observed: dict[str, bool] = {}
    evidence: dict[str, list[Any]] = {}
    negative_evidence: dict[str, list[Any]] = {}
    scores: defaultdict[str, float] = defaultdict(float)
    for feature, rule in feature_rules.items():
        matches, excluded = match_feature_rule(graph, rule)
        observed[feature] = bool(matches)
        evidence[feature] = evidence_for_nodes(matches[: int(rule.get("max_evidence", 8))]) if matches else []
        if excluded:
            negative_evidence[feature] = evidence_for_nodes(excluded[: int(rule.get("max_negative_evidence", 5))])
        if matches:
            for identity_type, weight in rule.get("weights", {}).items():
                scores[identity_type] += float(weight)
    return {
        "observed": observed,
        "evidence": evidence,
        "negative_evidence": negative_evidence,
        "scores": {key: round(value, 3) for key, value in sorted(scores.items())},
        "confidence_notes": confidence_notes_for_features(observed, profile or {}),
    }


def evaluate_profile(graph: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    profile_id = profile.get("profile_id", "unknown")
    identity_type, identity = identity_rule_for_profile(profile)
    feature_weights = feature_weights_for_profile(profile)
    matched_features = []
    missing_features = []
    negative_matches = []
    raw_score = 0.0
    total_positive_weight = sum(float(value) for value in feature_weights.values()) or 1.0
    feature_results: dict[str, list[dict[str, Any]]] = {}

    for feature, rule in profile.get("feature_rules", {}).items():
        matches, _excluded = match_feature_rule(graph, rule)
        feature_results[feature] = evidence_for_nodes(matches[: int(rule.get("max_evidence", 8))]) if matches else []

    for feature, weight in feature_weights.items():
        evidence = feature_results.get(feature, [])
        if evidence:
            raw_score += float(weight)
            matched_features.append({"feature": feature, "score": float(weight), "evidence": evidence})
        else:
            missing_features.append(feature)

    for feature, penalty in profile.get("negative_weights", {}).items():
        evidence = feature_results.get(feature, [])
        if evidence:
            raw_score += float(penalty)
            negative_matches.append({"feature": feature, "score": float(penalty), "evidence": evidence})

    missing_required = [feature for feature in identity.get("required_features", []) if not feature_results.get(feature)]
    disqualified = bool(missing_required)
    normalized_score = 0.0 if disqualified else max(0.0, min(1.0, raw_score / total_positive_weight))
    coverage_factor = len(matched_features) / max(1, len(feature_weights))
    evidence_quality_factor = evidence_quality_for_matches(matched_features)
    confidence = max(0.0, min(0.95, normalized_score * evidence_quality_factor * (0.75 + 0.25 * coverage_factor)))

    return {
        "profile_id": profile_id,
        "identity_type": identity_type,
        "profile_layer": profile.get("profile_layer", "primary"),
        "display_name": profile.get("display_name", profile_id),
        "raw_score": round(raw_score, 3),
        "normalized_score": round(normalized_score, 3),
        "matched_features": matched_features,
        "missing_features": missing_features,
        "negative_matches": negative_matches,
        "missing_required_features": missing_required,
        "disqualified": disqualified,
        "confidence": round(confidence, 3),
        "threshold": float(identity.get("threshold", 0.5)),
        "summary": identity.get("summary", ""),
        "secondary_types": identity.get("secondary_types", []),
    }


def feature_weights_for_profile(profile: dict[str, Any]) -> dict[str, float]:
    identity_type, identity = identity_rule_for_profile(profile)
    identity_weights = identity.get("feature_weights", {})
    if identity_weights:
        return {feature: float(weight) for feature, weight in identity_weights.items()}
    weights: dict[str, float] = {}
    for feature, rule in profile.get("feature_rules", {}).items():
        value = rule.get("weights", {}).get(identity_type)
        if value is not None:
            weights[feature] = float(value)
    return weights


def identity_rule_for_profile(profile: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    profile_id = profile.get("profile_id", "unknown")
    identity_rules = profile.get("identity_rules", {})
    if profile_id in identity_rules:
        return profile_id, identity_rules[profile_id]
    if identity_rules:
        identity_type = next(iter(identity_rules))
        return identity_type, identity_rules[identity_type]
    return profile_id, {}


def evidence_quality_for_matches(matched_features: list[dict[str, Any]]) -> float:
    evidence_count = sum(len(item.get("evidence", [])) for item in matched_features)
    if evidence_count <= 1:
        return 0.7
    if evidence_count <= 3:
        return 0.85
    return 1.0


def select_project_identity(evaluations: list[dict[str, Any]], profiles: list[dict[str, Any]]) -> dict[str, Any]:
    profile_lookup = {profile.get("profile_id"): profile for profile in profiles}
    passing = [item for item in evaluations if item.get("normalized_score", 0) >= item.get("threshold", 0.5)]
    primary_candidates = sorted(
        [item for item in passing if item.get("profile_layer", "primary") == "primary"],
        key=lambda item: (item.get("normalized_score", 0), item.get("confidence", 0)),
        reverse=True,
    )
    if not primary_candidates:
        return {
            "primary": None,
            "primary_candidates": [],
            "modifiers": [],
            "flavors": [],
            "hybrid_summary": "未找到达到阈值的主类型 profile。",
        }

    primary = profile_choice(primary_candidates[0])
    close_primaries = [
        profile_choice(item)
        for item in primary_candidates
        if primary["score"] - float(item.get("normalized_score", 0)) < 0.08
    ]
    modifiers = [
        profile_choice(item)
        for item in passing
        if item.get("profile_layer") == "modifier" and profiles_compatible(primary.get("profile_id"), item.get("profile_id"), profile_lookup)
    ]
    flavors = [profile_choice(item) for item in passing if item.get("profile_layer") == "flavor"]
    selected = apply_suppression([primary] + modifiers + flavors, profile_lookup)
    primary = next((item for item in selected if item["layer"] == "primary"), primary)
    modifiers = [item for item in selected if item["layer"] == "modifier"]
    flavors = [item for item in selected if item["layer"] == "flavor"]
    summary_bits = [primary["genre"]] + [item["genre"] for item in modifiers] + [item["genre"] for item in flavors]
    return {
        "primary": primary,
        "primary_candidates": close_primaries if len(close_primaries) > 1 else [],
        "modifiers": modifiers,
        "flavors": flavors,
        "hybrid_summary": "该项目更像是 " + " + ".join(summary_bits) + " 的组合。",
    }


def profile_choice(evaluation: dict[str, Any]) -> dict[str, Any]:
    return {
        "genre": evaluation.get("identity_type") or evaluation.get("profile_id"),
        "profile_id": evaluation.get("profile_id"),
        "layer": evaluation.get("profile_layer", "primary"),
        "score": float(evaluation.get("normalized_score", 0)),
        "confidence": float(evaluation.get("confidence", 0)),
        "summary": evaluation.get("summary", ""),
        "secondary_types": evaluation.get("secondary_types", []),
    }


def profiles_compatible(primary_id: str | None, candidate_id: str | None, profile_lookup: dict[str, dict[str, Any]]) -> bool:
    if not primary_id or not candidate_id:
        return False
    primary = profile_lookup.get(primary_id, {})
    candidate = profile_lookup.get(candidate_id, {})
    return candidate_id in primary.get("compatible_with", []) or primary_id in candidate.get("compatible_with", [])


def apply_suppression(selected: list[dict[str, Any]], profile_lookup: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    kept = list(selected)
    for item in list(selected):
        suppresses = set(profile_lookup.get(item.get("profile_id"), {}).get("suppresses", []))
        for other in list(kept):
            if other.get("profile_id") not in suppresses and other["genre"] not in suppresses:
                continue
            loser = other if item["confidence"] >= other["confidence"] else item
            if loser in kept:
                kept.remove(loser)
    return kept


def selected_profile_for_identity(project_identity_v2: dict[str, Any] | None, profiles: list[dict[str, Any]]) -> dict[str, Any]:
    if not project_identity_v2 or not project_identity_v2.get("primary"):
        return profiles[0] if profiles else {"profile_id": "generic", "profile_layer": "primary", "feature_rules": {}, "identity_rules": {}}
    selected_id = project_identity_v2["primary"].get("profile_id")
    return next((profile for profile in profiles if profile.get("profile_id") == selected_id), profiles[0])


def legacy_identity_from_v2(project_identity_v2: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    primary = project_identity_v2.get("primary") or {}
    if not primary:
        return fallback
    secondary_types = list(fallback.get("secondary_types", []))
    secondary_types.extend(item["genre"] for item in project_identity_v2.get("modifiers", []))
    secondary_types.extend(item["genre"] for item in project_identity_v2.get("flavors", []))
    return {
        **fallback,
        "primary_type": primary.get("genre", fallback.get("primary_type", "unknown")),
        "secondary_types": sorted(set(secondary_types)),
        "confidence": round(float(primary.get("confidence", fallback.get("confidence", 0))), 3),
        "summary": project_identity_v2.get("hybrid_summary") or fallback.get("summary", ""),
    }


def merge_v2_gameplay_loop(
    base_loop: list[dict[str, Any]],
    project_identity_v2: dict[str, Any],
    evaluations: list[dict[str, Any]],
    profiles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    profile_lookup = {profile.get("profile_id"): profile for profile in profiles}
    evaluation_lookup = {item.get("profile_id"): item for item in evaluations}
    merged = list(base_loop)
    existing_titles = {item.get("title") for item in merged}
    selected = []
    if project_identity_v2.get("primary"):
        selected.append(project_identity_v2["primary"])
    selected.extend(project_identity_v2.get("modifiers", []))
    selected.extend(project_identity_v2.get("flavors", []))
    for choice in selected:
        profile = profile_lookup.get(choice.get("profile_id"), {})
        evaluation = evaluation_lookup.get(choice.get("profile_id"), {})
        evidence = evidence_from_evaluation(evaluation)
        if not evidence:
            continue
        identity_type = choice.get("genre")
        for template in profile.get("gameplay_loop_templates", {}).get(identity_type, []):
            item = normalize_loop_template(template, evidence)
            if item["title"] in existing_titles:
                continue
            item["step"] = len(merged) + 1
            merged.append(item)
            existing_titles.add(item["title"])
    return merged


def evidence_from_evaluation(evaluation: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = []
    for feature in evaluation.get("matched_features", []):
        evidence.extend(feature.get("evidence", []))
    return evidence


def normalize_loop_template(template: Any, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    if isinstance(template, str):
        return {
            "title": template,
            "player_action": template,
            "system_response": template,
            "evidence": evidence[:5],
        }
    item = dict(template)
    item.setdefault("title", item.get("text", "Profile step"))
    item.setdefault("player_action", item.get("text", item["title"]))
    item.setdefault("system_response", item.get("text", item["title"]))
    item.setdefault("evidence", evidence[:5])
    return item


def confidence_notes_for_features(observed: dict[str, bool], profile: dict[str, Any]) -> list[str]:
    if not profile.get("feature_rules"):
        return ["No external Layer4 profile supplied; project-specific feature inference is disabled."]
    return [f"{feature}: {'matched' if matched else 'not matched'}" for feature, matched in sorted(observed.items())]


def infer_project_identity(project_features: dict[str, Any], profile: dict[str, Any] | None = None) -> dict[str, Any]:
    identity_rules = (profile or {}).get("identity_rules", {})
    evidence_by_feature = project_features.get("evidence", {})
    scores = project_features.get("scores", {})
    if not identity_rules or not scores:
        return {
            "primary_type": "unknown",
            "secondary_types": [],
            "confidence": 0.45,
            "summary": "未提供外部项目类型 profile，Layer4 不进行特定领域身份判定。",
            "evidence": [],
            "counter_evidence": [],
            "score_breakdown": scores,
        }
    primary_type, score = max(scores.items(), key=lambda item: item[1])
    rule = identity_rules.get(primary_type, {})
    threshold = float(rule.get("threshold", 0.5))
    if score < threshold:
        return {
            "primary_type": "unknown",
            "secondary_types": [],
            "confidence": round(min(score, 0.95), 3),
            "summary": "外部 profile 的得分未达到项目类型判定阈值。",
            "evidence": [],
            "counter_evidence": [{"score": score, "threshold": threshold}],
            "score_breakdown": scores,
        }
    evidence: list[Any] = []
    for feature in rule.get("feature_weights", {}):
        evidence.extend(evidence_by_feature.get(feature, [])[:3])
    if not evidence:
        for matched_evidence in evidence_by_feature.values():
            evidence.extend(matched_evidence[:3])
    return {
        "primary_type": primary_type,
        "secondary_types": sorted(set(rule.get("secondary_types", []))),
        "confidence": round(min(score, 0.95), 3),
        "summary": rule.get("summary", f"外部 profile 将项目判定为 {primary_type}。"),
        "evidence": evidence[:10],
        "counter_evidence": [],
        "score_breakdown": scores,
    }


def build_gameplay_loop(
    graph: dict[str, Any],
    scene_flow: dict[str, Any],
    project_features: dict[str, Any],
    player_control_model: dict[str, list[dict[str, Any]]],
    key_dependencies: list[dict[str, Any]],
    profile: dict[str, Any] | None = None,
    project_identity: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    loop: list[dict[str, Any]] = []
    entry_scene = scene_flow.get("entry_scene") or graph.get("metadata", {}).get("entry_scene")
    if entry_scene:
        loop.append({
            "step": len(loop) + 1,
            "title": "进入项目入口",
            "player_action": "从入口场景开始运行。",
            "system_response": f"项目加载 `{entry_scene}` 并准备后续场景或 UI。",
            "evidence": [{"entry_scene": entry_scene}],
        })
    for item in render_profile_section(profile or {}, project_identity or {}, project_features, "gameplay_loop_templates"):
        loop.append({
            "step": len(loop) + 1,
            "title": item["title"],
            "player_action": item.get("player_action", ""),
            "system_response": item.get("system_response", item.get("text", "")),
            "evidence": item.get("evidence", []),
        })
    if len(loop) > 1:
        return loop
    flows = scene_flow.get("flows", [])
    if flows:
        loop.append(loop_item(len(loop) + 1, "进入主要场景", "通过入口或流程切换进入主要运行场景。", "场景流显示项目会实例化或切换到后续场景。", flows[:5]))
    for group, title in [("movement", "执行输入控制"), ("selection", "选择交互对象"), ("actions", "执行主要操作"), ("ui_controls", "查看界面反馈")]:
        if player_control_model.get(group):
            loop.append(loop_item(len(loop) + 1, title, "触发项目中的可交互行为。", "相关脚本处理输入并更新运行状态。", player_control_model[group]))
    if len(loop) < 2:
        for dep in key_dependencies[: 2 - len(loop)]:
            loop.append(loop_item(len(loop) + 1, "执行关键依赖流程", "触发项目中的关键脚本或场景关系。", dep.get("description", "系统执行关键依赖。"), [dep]))
    return loop


def loop_item(step: int, title: str, player_action: str, system_response: str, evidence: list[Any]) -> dict[str, Any]:
    return {
        "step": step,
        "title": title,
        "player_action": player_action,
        "system_response": system_response,
        "evidence": evidence,
    }


def match_feature_rule(graph: dict[str, Any], rule: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    positive_terms = [str(term).lower() for term in rule.get("positive_terms", [])]
    required_context = [str(term).lower() for term in rule.get("required_context", [])]
    negative_context = [str(term).lower() for term in rule.get("negative_context", [])]
    node_kinds = set(rule.get("node_kinds", ["Node", "Script", "Scene", "Resource", "Signal", "Autoload"]))
    matches: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for node in graph.get("nodes", []):
        if node.get("kind") not in node_kinds:
            continue
        haystack = searchable_node(node)
        if positive_terms and not any(term in haystack for term in positive_terms):
            continue
        if required_context and not all(term in haystack for term in required_context):
            continue
        if negative_context and any(term in haystack for term in negative_context):
            excluded.append(node)
            continue
        matches.append(node)
    return matches, excluded


def render_profile_section(
    profile: dict[str, Any],
    project_identity: dict[str, Any],
    project_features: dict[str, Any],
    section_name: str,
) -> list[dict[str, Any]]:
    identity_type = project_identity.get("primary_type", "unknown")
    section = profile.get(section_name, {})
    if section_name == "player_control_templates":
        templates = []
        grouped = section.get(identity_type, {}) if isinstance(section.get(identity_type, {}), dict) else {}
        for group, items in grouped.items():
            for item in items:
                rendered = render_profile_item(item, project_features)
                rendered["group"] = group
                templates.append(rendered)
        return [item for item in templates if item.get("evidence")]
    items = section.get(identity_type, []) if isinstance(section, dict) else []
    return [item for item in (render_profile_item(item, project_features) for item in items) if item.get("evidence")]


def render_profile_item(item: dict[str, Any], project_features: dict[str, Any]) -> dict[str, Any]:
    rendered = dict(item)
    rendered.setdefault("id", f"profile:{slugify(rendered.get('title', 'item'))}")
    evidence = []
    for feature in rendered.pop("evidence_features", []):
        evidence.extend(project_features.get("evidence", {}).get(feature, []))
    rendered["evidence"] = evidence[: int(rendered.pop("max_evidence", 8))]
    return rendered


def build_scene_flow_abstraction(
    scene_flow: dict[str, Any],
    profile: dict[str, Any],
    project_identity: dict[str, Any],
    project_features: dict[str, Any],
) -> dict[str, Any]:
    del project_features
    identity_type = project_identity.get("primary_type", "unknown")
    rule_edges = profile.get("scene_flow_rules", {}).get(identity_type, [])
    if rule_edges:
        return {"edges": rule_edges, "mermaid": render_mermaid(rule_edges)}
    edges = []
    entry_scene = scene_flow.get("entry_scene")
    if entry_scene:
        edges.append({"source": "Entry", "target": short_label(entry_scene), "label": "loads"})
    for flow in scene_flow.get("flows", [])[:8]:
        edges.append({"source": short_label(flow["source"]), "target": short_label(flow["target"]), "label": flow["type"]})
    return {"edges": edges, "mermaid": render_mermaid(edges)}


def build_module_map(
    module_responsibilities: list[dict[str, Any]],
    profile: dict[str, Any],
    project_identity: dict[str, Any],
) -> dict[str, Any]:
    identity_type = project_identity.get("primary_type", "unknown")
    rule_edges = profile.get("module_map_rules", {}).get(identity_type, [])
    if rule_edges:
        return {"edges": rule_edges, "mermaid": render_mermaid(rule_edges)}
    edges = [{"source": item["module"], "target": item.get("system", "Core"), "label": "belongs_to"} for item in module_responsibilities[:10]]
    return {"edges": edges, "mermaid": render_mermaid(edges)}


def build_report_quality(
    graph: dict[str, Any],
    profile: dict[str, Any],
    project_identity: dict[str, Any],
    scene_flow_abstraction: dict[str, Any],
    module_map: dict[str, Any],
) -> dict[str, Any]:
    warnings = []
    full_text = " ".join(searchable_node(node) for node in graph.get("nodes", []))
    for term in profile.get("forbidden_report_terms", []):
        if str(term).lower() in full_text:
            warnings.append(f"forbidden evidence term matched: {term}")
    return {
        "profile_id": profile.get("profile_id", "generic"),
        "identity_type": project_identity.get("primary_type", "unknown"),
        "has_scene_flow_mermaid": scene_flow_abstraction.get("mermaid", "").startswith("flowchart TD"),
        "has_module_map_mermaid": module_map.get("mermaid", "").startswith("flowchart TD"),
        "evidence_noise_warnings": warnings,
    }


def render_mermaid(edges: list[dict[str, Any]]) -> str:
    lines = ["flowchart TD"]
    if not edges:
        lines.append("  Empty[No recovered flow]")
        return "\n".join(lines) + "\n"
    ids: dict[str, str] = {}
    for edge in edges:
        for label in (edge.get("source", "Source"), edge.get("target", "Target")):
            ids.setdefault(label, f"N{len(ids) + 1}")
    for label, node_id in ids.items():
        lines.append(f"  {node_id}[\"{escape_mermaid_label(label)}\"]")
    for edge in edges:
        source = ids[edge.get("source", "Source")]
        target = ids[edge.get("target", "Target")]
        label = escape_mermaid_label(edge.get("label", "flows"))
        lines.append(f"  {source} -- \"{label}\" --> {target}")
    return "\n".join(lines) + "\n"


def escape_mermaid_label(value: Any) -> str:
    return str(value).replace('"', "'").replace("\n", " ")


def slugify(value: Any) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value)).strip("_") or "item"


def short_label(value: Any) -> str:
    text = str(value).replace("scene:", "").replace("script:", "").replace("node:", "")
    return Path(text).name if "/" in text else text


def build_module_responsibilities(
    graph: dict[str, Any],
    annotations: dict[str, Any],
    profile: dict[str, Any] | None = None,
    project_identity: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    responsibilities = []
    identity_type = (project_identity or {}).get("primary_type", "unknown")
    for rule in (profile or {}).get("module_rules", {}).get(identity_type, []):
        terms = rule.get("terms", [])
        matches = find_entities(graph, terms, kinds={"Script", "Node", "Scene", "Autoload"})
        if rule.get("exclude_terms"):
            excluded_terms = [str(term).lower() for term in rule.get("exclude_terms", [])]
            matches = [node for node in matches if not any(term in searchable_node(node) for term in excluded_terms)]
        if not matches:
            continue
        confidence = max((annotations.get(node["id"], {}).get("confidence", 0.68) for node in matches), default=0.68)
        responsibilities.append(
            {
                "module": rule.get("module", terms[0] if terms else "Profile Module"),
                "responsibility": rule.get("responsibility", "外部 profile 定义的模块职责"),
                "system": rule.get("system", "Core"),
                "confidence": round(confidence, 3),
                "evidence": evidence_for_nodes(matches[:5]),
            }
        )

    if len(responsibilities) < 3:
        seen_modules = {item["module"] for item in responsibilities}
        for node in graph.get("nodes", []):
            if node.get("kind") != "Script":
                continue
            props = node.get("properties", {})
            path = props.get("path", node["id"])
            module = Path(path).stem if isinstance(path, str) else node["id"]
            if module in seen_modules:
                continue
            annotation = annotations.get(node["id"], {})
            systems = annotation.get("systems", ["Core"])
            responsibilities.append(
                {
                    "module": module,
                    "responsibility": "项目脚本模块",
                    "system": "/".join(systems[:2]),
                    "confidence": round(annotation.get("confidence", 0.6), 3),
                    "evidence": evidence_for_nodes([node]),
                }
            )
            seen_modules.add(module)
            if len(responsibilities) >= 3:
                break
    return responsibilities


def find_script_nodes(graph: dict[str, Any], terms: list[str]) -> list[dict[str, Any]]:
    return find_entities(graph, terms, kinds={"Script"})


def find_input_scripts(graph: dict[str, Any]) -> list[dict[str, Any]]:
    scripts = []
    for node in graph.get("nodes", []):
        if node.get("kind") != "Script":
            continue
        props = node.get("properties", {})
        signals = " ".join(str(signal) for signal in props.get("signals", []))
        functions = " ".join(str(function) for function in props.get("functions", []))
        haystack = f"{node.get('id', '')} {props.get('path', '')} {signals} {functions}".lower()
        if "input_manager" in haystack or "_input" in haystack or "mouse_" in haystack or "key_" in haystack:
            scripts.append(node)
    return scripts


def find_entities(graph: dict[str, Any], terms: list[str], kinds: set[str] | None = None) -> list[dict[str, Any]]:
    results = []
    lowered_terms = [term.lower() for term in terms]
    for node in graph.get("nodes", []):
        if kinds and node.get("kind") not in kinds:
            continue
        haystack = " ".join(
            str(value)
            for value in [
                node.get("id"),
                node.get("kind"),
                node.get("properties", {}).get("path"),
                node.get("properties", {}).get("name"),
                node.get("properties", {}).get("node_type"),
                node.get("properties", {}).get("class_name"),
            ]
        ).lower()
        if any(term in haystack for term in lowered_terms):
            results.append(node)
    return results


def evidence_for_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence = []
    for node in nodes:
        props = node.get("properties", {})
        item: dict[str, Any] = {"node_id": node.get("id"), "kind": node.get("kind")}
        if props.get("path"):
            item["path"] = props["path"]
        if props.get("api_usage"):
            item["api_usage"] = props["api_usage"]
        if props.get("evidence"):
            item["evidence"] = props["evidence"]
        evidence.append(item)
    return evidence


def collect_api_usage(nodes: list[dict[str, Any]]) -> set[str]:
    apis: set[str] = set()
    for node in nodes:
        apis.update(str(api) for api in node.get("properties", {}).get("api_usage", []))
    return apis


def searchable(item: dict[str, Any], node_lookup: dict[str, dict[str, Any]]) -> str:
    if "source" in item or "target" in item:
        parts = [
            item.get("source", ""),
            item.get("target", ""),
            item.get("source_label", ""),
            item.get("target_label", ""),
            item.get("description", ""),
        ]
        for entity_id in [item.get("source"), item.get("target")]:
            node = node_lookup.get(entity_id or "", {})
            props = node.get("properties", {})
            parts.extend([props.get("path", ""), props.get("name", ""), props.get("node_type", ""), props.get("class_name", "")])
        return " ".join(str(part) for part in parts).lower()
    props = item.get("properties", {})
    return " ".join(str(part) for part in [item.get("id", ""), props.get("path", ""), props.get("name", ""), props.get("node_type", "")]).lower()


def searchable_node(node: dict[str, Any]) -> str:
    props = node.get("properties", {})
    return " ".join(
        str(part)
        for part in [
            node.get("id", ""),
            node.get("kind", ""),
            props.get("path", ""),
            props.get("name", ""),
            props.get("node_type", ""),
            props.get("class_name", ""),
        ]
    ).lower()


def build_findings(
    summary: dict[str, Any],
    systems: list[dict[str, Any]],
    patterns: list[dict[str, Any]],
    semantic_findings: dict[str, Any],
) -> list[dict[str, Any]]:
    findings = []
    for system in systems:
        if system["kind"] in {"Gameplay", "UI", "Data"}:
            findings.append(
                {
                    "id": f"finding:system:{system['kind'].lower()}",
                    "title": f"{system['kind']} system recovered",
                    "kind": "system",
                    "confidence": system.get("confidence", 0),
                    "evidence": system.get("evidence", [])[:5] or system.get("members", [])[:5],
                    "details": {"member_count": len(system.get("members", []))},
                }
            )
    for pattern_id, count in summary["pattern_counts"].items():
        matches = [pattern for pattern in patterns if pattern["pattern_id"] == pattern_id]
        findings.append(
            {
                "id": f"finding:pattern:{pattern_id}",
                "title": f"Architecture pattern observed: {pattern_id}",
                "kind": "pattern",
                "confidence": max((match.get("confidence", 0) for match in matches), default=0.7),
                "evidence": matches[:5],
                "details": {"match_count": count},
            }
        )
    for item in semantic_findings.get("findings", [])[:5]:
        findings.append(
            {
                "id": f"finding:semantic:{item['id']}",
                "title": item["title"],
                "kind": "semantic",
                "confidence": item.get("confidence", 0.7),
                "evidence": item.get("evidence", []),
                "details": {"source": "Layer3"},
            }
        )
    return dedupe_by_id(findings)


def build_risks(summary: dict[str, Any], graph: dict[str, Any], systems: list[dict[str, Any]], semantic_findings: dict[str, Any]) -> list[dict[str, Any]]:
    risks = []
    if summary["project_overview"].get("unresolved_edges", 0) > 0:
        risks.append(
            {
                "id": "risk:unresolved_edges",
                "title": "Unresolved graph dependencies may hide runtime flow",
                "severity": "medium",
                "evidence": [{"unresolved_edges": summary["project_overview"]["unresolved_edges"]}],
            }
        )
    dynamic_count = summary["pattern_counts"].get("dynamic_scene_creation", 0)
    if dynamic_count >= 2:
        risks.append(
            {
                "id": "risk:dynamic_creation_scattered",
                "title": "Runtime scene creation appears in multiple places",
                "severity": "low",
                "evidence": [{"dynamic_scene_creation_matches": dynamic_count}],
            }
        )
    if summary["architecture_patterns"]["event_driven"] and count_edges(graph, "connects") == 0:
        risks.append(
            {
                "id": "risk:event_flow_unclear",
                "title": "Event-driven behavior inferred without explicit graph connect edges",
                "severity": "low",
                "evidence": [{"pattern_counts": summary["pattern_counts"]}],
            }
        )
    readiness = semantic_findings.get("upstream_readiness", {})
    if readiness.get("recommendations"):
        risks.append(
            {
                "id": "risk:upstream_semantic_gaps",
                "title": "Semantic upstream readiness has recommendations",
                "severity": "medium",
                "evidence": readiness.get("recommendations", []),
            }
        )
    if not risks:
        risks.append(
            {
                "id": "risk:none_high_confidence",
                "title": "No high-confidence structural risks found in Layer 4 MVP checks",
                "severity": "info",
                "evidence": [{"unresolved_edges": summary["project_overview"].get("unresolved_edges", 0)}],
            }
        )
    return risks


def build_recommendations(risks: list[dict[str, Any]], summary: dict[str, Any]) -> list[dict[str, Any]]:
    recommendations = []
    if any(risk["id"] == "risk:dynamic_creation_scattered" for risk in risks):
        recommendations.append(
            {
                "id": "recommendation:centralize_runtime_spawning",
                "title": "Keep runtime scene creation behind clear spawning APIs",
                "priority": "medium",
                "evidence": [{"dynamic_scene_creation": summary["pattern_counts"].get("dynamic_scene_creation", 0)}],
            }
        )
    if summary["architecture_patterns"].get("event_driven"):
        recommendations.append(
            {
                "id": "recommendation:document_signal_contracts",
                "title": "Document signal contracts between UI and gameplay scripts",
                "priority": "medium",
                "evidence": [{"event_driven": True, "connect_edges": summary["architecture_patterns"].get("ui_gameplay_signal_bridge")}],
            }
        )
    if any(risk["id"] == "risk:upstream_semantic_gaps" for risk in risks):
        recommendations.append(
            {
                "id": "recommendation:fix_upstream_readiness",
                "title": "Address upstream semantic readiness before relying on architecture conclusions",
                "priority": "high",
                "evidence": [risk for risk in risks if risk["id"] == "risk:upstream_semantic_gaps"],
            }
        )
    if not recommendations:
        recommendations.append(
            {
                "id": "recommendation:proceed_to_review",
                "title": "Use the report as a baseline for manual architecture review",
                "priority": "low",
                "evidence": [{"layer4_mvp": "no blocking recommendations"}],
            }
        )
    return recommendations


def assess_upstream_readiness(summary: dict[str, Any], semantic_findings: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    semantic_ready = semantic_findings.get("upstream_readiness", {})
    recommendations = list(semantic_ready.get("recommendations", []))
    if summary["project_overview"].get("unresolved_edges", 0):
        recommendations.append("Re-run Layer 2 after resolving graph unresolved edges.")
    if not summary.get("systems"):
        recommendations.append("Layer 3 produced no systems; check Layer 0 semantics and Layer 2 graph completeness.")
    return {
        "ready_for_human_review": not recommendations,
        "layer2_unresolved_edges": summary["project_overview"].get("unresolved_edges", 0),
        "layer3_unannotated_structural_nodes": semantic_ready.get("unannotated_structural_nodes", 0),
        "recommendations": recommendations,
    }


def build_report(summary: dict[str, Any], findings: list[dict[str, Any]], risks: list[dict[str, Any]], recommendations: list[dict[str, Any]]) -> str:
    overview = summary["project_overview"]
    lines = [
        "# Godot Architecture Recovery Report",
        "",
        "## 项目概览",
        "",
        f"- 入口场景: `{overview.get('entry_scene')}`",
        f"- 规模: {overview.get('scene_count')} scenes, {overview.get('script_count')} scripts, {overview.get('resource_count')} resources",
        f"- 图规模: {overview.get('node_count')} nodes, {overview.get('edge_count')} edges, unresolved {overview.get('unresolved_edges')}",
        "",
        "## 项目身份判断",
        "",
    ]
    identity = summary.get("project_identity", {})
    identity_v2 = summary.get("project_identity_v2")
    if identity_v2 and identity_v2.get("primary"):
        primary = identity_v2["primary"]
        lines.append(f"- 主类型: `{primary.get('genre')}` (score {primary.get('score')}, confidence {primary.get('confidence')})")
        if identity_v2.get("modifiers"):
            lines.append(f"- 修饰类型: {', '.join(item.get('genre', '') for item in identity_v2.get('modifiers', []))}")
        if identity_v2.get("flavors"):
            lines.append(f"- 风格类型: {', '.join(item.get('genre', '') for item in identity_v2.get('flavors', []))}")
        if identity_v2.get("primary_candidates"):
            lines.append(f"- 主类型候选: {', '.join(item.get('genre', '') for item in identity_v2.get('primary_candidates', []))}")
        lines.append(f"- 判断: {identity_v2.get('hybrid_summary')}")
    else:
        lines.append(f"- 类型: `{identity.get('primary_type')}`")
        lines.append(f"- 置信度: {identity.get('confidence')}")
        lines.append(f"- 判断: {identity.get('summary')}")
    if identity.get("secondary_types"):
        lines.append(f"- 次级标签: {', '.join(identity.get('secondary_types', []))}")
    lines.extend([
        "",
        "## 玩家主循环",
        "",
    ])
    for item in summary.get("gameplay_loop", []):
        lines.append(f"- {item['step']}. **{item['title']}**: {item['player_action']} -> {item['system_response']}")
    lines.extend([
        "",
        "## 玩家控制方式",
        "",
    ])
    control_titles = {
        "movement": "移动控制",
        "selection": "选择/指向控制",
        "actions": "动作控制",
        "ui_controls": "UI 控制",
    }
    for group, items in summary.get("player_control_model", {}).items():
        lines.append(f"- {control_titles.get(group, group)}")
        for item in items:
            lines.append(f"  - **{item['title']}**: {item['text']}")
    lines.extend([
        "",
        "## 核心玩法逻辑",
        "",
    ])
    for item in summary.get("core_combat_logic", []):
        lines.append(f"- **{item['title']}**: {item['text']}")
    lines.extend([
        "",
        "## 场景流程",
        "",
        "```mermaid",
        summary.get("scene_flow_abstraction", {}).get("mermaid", "flowchart TD\n").rstrip(),
        "```",
        "",
        "## 模块关系图",
        "",
        "```mermaid",
        summary.get("module_map", {}).get("mermaid", "flowchart TD\n").rstrip(),
        "```",
    ])
    lines.extend([
        "",
        "## 核心模块职责",
        "",
    ])
    for item in summary.get("module_responsibilities", []):
        lines.append(f"- **{item['module']}**: {item['responsibility']} ({item['system']}, confidence {item['confidence']})")
    lines.extend([
        "",
        "## 项目如何工作",
        "",
    ])
    for item in summary.get("runtime_narrative", []):
        lines.append(f"- **{item['title']}**: {item['text']}")
    lines.extend([
        "",
        "## 系统划分",
        "",
    ])
    for system in summary["systems"]:
        lines.append(f"- {system['kind']}: {system['member_count']} members, confidence {system['confidence']}")
    lines.extend(["", "## 关键依赖关系", ""])
    for dep in summary.get("key_dependencies", [])[:12]:
        lines.append(f"- {dep['description']} (`{dep['type']}`)")
    lines.extend(["", "## 架构模式判断", ""])
    for name, enabled in summary["architecture_patterns"].items():
        lines.append(f"- {name}: {enabled}")
    lines.extend(["", "## 关键发现", ""])
    for item in findings[:8]:
        lines.append(f"- {item['title']} (confidence {item['confidence']})")
    lines.extend(["", "## 风险", ""])
    for risk in risks:
        lines.append(f"- [{risk['severity']}] {risk['title']}")
    lines.extend(["", "## 建议", ""])
    for rec in recommendations:
        lines.append(f"- [{rec['priority']}] {rec['title']}")
    lines.extend(["", "## 上游流程状态", ""])
    readiness = summary["upstream_readiness"]
    lines.append(f"- Ready for human review: {readiness['ready_for_human_review']}")
    if readiness["recommendations"]:
        for rec in readiness["recommendations"]:
            lines.append(f"- Upstream recommendation: {rec}")
    else:
        lines.append("- No upstream adjustments required by Layer 4.")
    lines.append("")
    return "\n".join(lines)


def count_edges(graph: dict[str, Any], edge_type: str) -> int:
    return sum(1 for edge in graph.get("edges", []) if edge.get("type") == edge_type)


def has_system(systems: list[dict[str, Any]], kind: str) -> bool:
    return any(system.get("kind") == kind for system in systems)


def system_size(systems: list[dict[str, Any]], kind: str) -> int:
    for system in systems:
        if system.get("kind") == kind:
            return len(system.get("members", []))
    return 0


def top_entities(annotations: dict[str, Any]) -> list[dict[str, Any]]:
    ranked = sorted(
        (
            {"id": entity_id, "systems": value.get("systems", []), "roles": value.get("semantic_roles", []), "confidence": value.get("confidence", 0)}
            for entity_id, value in annotations.items()
            if value.get("kind") != "Edge"
        ),
        key=lambda item: (len(item["systems"]), item["confidence"]),
        reverse=True,
    )
    return ranked[:15]


def dedupe_by_id(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = {}
    for item in items:
        result[item["id"]] = item
    return list(result.values())


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Godot Layer 4 architecture recovery artifacts.")
    parser.add_argument("--layer2", required=True, help="Layer 2 artifact directory.")
    parser.add_argument("--layer3", required=True, help="Layer 3 artifact directory.")
    parser.add_argument("--output", required=True, help="Output directory for Layer 4 artifacts.")
    parser.add_argument("--profile", help="Optional external Layer 4 domain/profile JSON.")
    parser.add_argument("--profile-dir", help="Optional directory of Layer 4 profile JSON files for multi-profile evaluation.")
    args = parser.parse_args()
    recover(args.layer2, args.layer3, args.output, profile_path=args.profile, profile_dir=args.profile_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
