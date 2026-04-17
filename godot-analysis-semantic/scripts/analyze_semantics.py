#!/usr/bin/env python3
"""Build Layer 3 semantic artifacts from Layer 0 and Layer 2."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GENERATOR = "godot-analysis-semantic"
SCHEMA_VERSION = "0.1.0"
CORE_SYSTEMS = ["UI", "Gameplay", "Manager", "Data", "Physics", "Presentation", "Animation", "Audio", "Core"]
UI_NODE_TYPES = {
    "Control",
    "Button",
    "Label",
    "Panel",
    "PanelContainer",
    "Container",
    "HBoxContainer",
    "VBoxContainer",
    "ScrollContainer",
    "TextureRect",
    "NinePatchRect",
    "CanvasLayer",
    "LineEdit",
    "TextEdit",
    "CheckBox",
    "OptionButton",
    "TabContainer",
    "SubViewportContainer",
}
GAMEPLAY_NODE_TYPES = {
    "Area2D",
    "CharacterBody2D",
    "RigidBody2D",
    "StaticBody2D",
    "CollisionShape2D",
    "CollisionPolygon2D",
    "RayCast2D",
    "NavigationAgent2D",
}
PRESENTATION_NODE_TYPES = {
    "Sprite2D",
    "AnimatedSprite2D",
    "AnimationPlayer",
    "TextureRect",
    "MeshInstance3D",
    "Node3D",
    "Camera2D",
    "Camera3D",
    "Light2D",
    "PointLight2D",
    "AudioStreamPlayer",
    "AudioStreamPlayer2D",
    "AudioStreamPlayer3D",
}


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


def analyze(layer0_dir: Path | str, layer2_dir: Path | str, output_dir: Path | str, confidence_threshold: float = 0.6) -> None:
    layer0 = Path(layer0_dir)
    layer2 = Path(layer2_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    foundation = read_artifact(layer0 / "foundation_semantics.json")["data"]
    api_semantics = read_artifact(layer0 / "api_semantics.json")["data"]
    pattern_rules = read_artifact(layer0 / "pattern_rules.json")["data"]
    taxonomy = read_artifact(layer0 / "role_taxonomy.json")["data"]
    graph_artifact = read_artifact(layer2 / "graph.json")
    graph = graph_artifact["data"]
    project_root = graph_artifact.get("project_root")

    annotations = build_annotations(graph, foundation, api_semantics)
    pattern_matches = match_patterns(graph, annotations, pattern_rules, confidence_threshold)
    systems = build_systems(graph, annotations, pattern_matches, confidence_threshold)
    findings = build_findings(graph, systems, pattern_matches, annotations)
    readiness = check_upstream_readiness(graph, annotations, taxonomy)

    write_json(out / "semantic_annotations.json", artifact("semantic_annotations", project_root, annotations))
    write_json(out / "systems.json", artifact("systems", project_root, {"systems": systems}))
    write_json(out / "pattern_matches.json", artifact("pattern_matches", project_root, {"pattern_matches": pattern_matches}))
    write_json(out / "semantic_findings.json", artifact("semantic_findings", project_root, {"findings": findings, "upstream_readiness": readiness}))
    (out / "semantic_report.md").write_text(build_report(systems, pattern_matches, findings, readiness), encoding="utf-8")


def build_annotations(graph: dict[str, Any], foundation: dict[str, Any], api_semantics: dict[str, Any]) -> dict[str, Any]:
    annotations: dict[str, Any] = {}
    attached_script_by_node = {
        edge["source"]: edge["target"] for edge in graph.get("edges", []) if edge.get("type") == "attaches"
    }
    node_by_id = {node["id"]: node for node in graph.get("nodes", [])}

    for node in graph.get("nodes", []):
        props = node.get("properties", {})
        semantic = dict(props.get("semantic", {}))
        foundation_semantic = {}
        if node["kind"] == "Node" and props.get("node_type"):
            foundation_semantic = foundation.get(props["node_type"], {})
        elif node["kind"] == "Script" and props.get("extends"):
            foundation_semantic = foundation.get(props["extends"], {})
        if foundation_semantic:
            semantic = merge_semantics(semantic, foundation_semantic)
        systems = set(semantic.get("systems", []))
        roles = set(semantic.get("roles", []))
        categories = set()
        if semantic.get("category"):
            categories.add(semantic["category"])

        if node["kind"] == "Resource":
            categories.add("data_resource")
            roles.add("data_container")
            systems.add("Data")
            semantic.setdefault("confidence", 0.7)
        if node["kind"] == "Script":
            api_usage = props.get("api_usage", [])
            api_behavior = []
            for api_name in api_usage:
                value = api_semantics.get(api_name)
                if value:
                    api_behavior.append(value.get("semantic"))
                    systems.update(specific_api_systems(api_name, value, systems))
            if api_behavior:
                semantic["api_semantics"] = sorted(set(filter(None, api_behavior)))
            if "instantiate" in api_usage or "add_child" in api_usage:
                roles.add("runtime_factory")
            if "connect" in api_usage:
                roles.add("event_subscriber")
            if "emit_signal" in api_usage:
                roles.add("event_emitter")

        attached_script = attached_script_by_node.get(node["id"])
        if attached_script and attached_script in node_by_id:
            script_annotation_source = node_by_id[attached_script].get("properties", {}).get("semantic", {})
            systems.update(script_annotation_source.get("systems", []))

        if not (systems or roles or categories):
            fallback = infer_fallback_semantics(node)
            categories.update(fallback.get("categories", []))
            roles.update(fallback.get("roles", []))
            systems.update(fallback.get("systems", []))
            if fallback.get("confidence"):
                semantic["confidence"] = fallback["confidence"]

        if systems or roles or categories:
            annotations[node["id"]] = {
                "kind": node["kind"],
                "categories": sorted(categories),
                "semantic_roles": sorted(roles),
                "systems": sorted(systems),
                "confidence": semantic.get("confidence", 0.65),
                "evidence": evidence_for_node(node),
            }

    propagate_instance_semantics(graph, annotations)

    for edge in graph.get("edges", []):
        if edge.get("type") in {"connects", "emits", "instantiates", "references"}:
            systems = set()
            if edge["type"] in {"connects", "emits"}:
                systems.add("Core")
            if edge["type"] == "instantiates":
                systems.add("Gameplay")
            if edge["type"] == "references" and edge.get("target", "").startswith("resource:"):
                systems.add("Data")
            annotations[edge["id"]] = {
                "kind": "Edge",
                "categories": [edge["type"]],
                "semantic_roles": [f"{edge['type']}_relationship"],
                "systems": sorted(systems),
                "confidence": 0.65,
                "evidence": edge.get("properties", {}).get("evidence_list", []) or [{"source": "graph_edge", "edge_id": edge["id"]}],
            }
    return annotations


def merge_semantics(primary: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    merged = dict(fallback)
    merged.update(primary)
    merged["systems"] = sorted(set(fallback.get("systems", [])) | set(primary.get("systems", [])))
    merged["roles"] = sorted(set(fallback.get("roles", [])) | set(primary.get("roles", [])))
    if "category" not in merged and fallback.get("category"):
        merged["category"] = fallback["category"]
    if "confidence" not in primary and fallback.get("confidence") is not None:
        merged["confidence"] = fallback["confidence"]
    return merged


def infer_fallback_semantics(node: dict[str, Any]) -> dict[str, Any]:
    props = node.get("properties", {})
    path = str(props.get("path", ""))
    scene = str(props.get("scene", ""))
    class_name = str(props.get("class_name", ""))
    extends = str(props.get("extends", ""))
    functions = " ".join(str(function) for function in props.get("functions", []))
    node_type = str(props.get("node_type", ""))
    haystack = f"{node.get('id', '')} {path} {scene} {class_name} {extends} {functions}".lower()

    if node.get("kind") == "Node" and node_type in UI_NODE_TYPES:
        return {
            "categories": ["ui_element"],
            "roles": ["ui_control"],
            "systems": ["UI"],
            "confidence": 0.62,
        }

    if node.get("kind") == "Node" and node_type in GAMEPLAY_NODE_TYPES:
        return {
            "categories": ["gameplay_entity"],
            "roles": ["scene_instance"],
            "systems": ["Gameplay", "Physics"],
            "confidence": 0.62,
        }

    if node.get("kind") == "Node" and node_type in PRESENTATION_NODE_TYPES:
        return {
            "categories": ["presentation"],
            "roles": ["shape_visual"],
            "systems": ["Presentation"],
            "confidence": 0.6,
        }

    if node.get("kind") == "Node" and props.get("node_type") == "Unknown":
        if has_neutral_ui_path(haystack) or any(term in haystack for term in ("button", "label", "container", "frame", "highlight", "portrait", "icon", "panel")):
            return {
                "categories": ["ui_element"],
                "roles": ["ui_control"],
                "systems": ["UI"],
                "confidence": 0.55,
            }
        if any(term in haystack for term in ("/resources/", "weapon", "shield", "body", "model", ".fbx")):
            return {
                "categories": ["presentation"],
                "roles": ["scene_instance"],
                "systems": ["Presentation"],
                "confidence": 0.6,
            }
        return {
            "categories": ["core_runtime"],
            "roles": ["scene_instance"],
            "systems": ["Core"],
            "confidence": 0.45,
        }

    if node.get("kind") == "Node" and not props.get("node_type"):
        if has_neutral_ui_path(haystack) or any(term in haystack for term in ("button", "label", "container", "frame", "highlight", "portrait", "icon", "panel")):
            return {
                "categories": ["ui_element"],
                "roles": ["ui_control"],
                "systems": ["UI"],
                "confidence": 0.52,
            }
        return {
            "categories": ["core_runtime"],
            "roles": ["scene_instance"],
            "systems": ["Core"],
            "confidence": 0.42,
        }

    if node.get("kind") == "Script":
        if extends == "StyleBox" or "/style/" in haystack or "stylebox" in haystack:
            return {
                "categories": ["ui_element", "presentation"],
                "roles": ["ui_control"],
                "systems": ["UI", "Presentation"],
                "confidence": 0.65,
            }
        if has_neutral_manager_name(haystack):
            return {
                "categories": ["manager"],
                "roles": ["global_service"],
                "systems": ["Manager", "Core"],
                "confidence": 0.62,
            }
        if "/commands/" in haystack or class_name == "Command" or "execute" in haystack:
            return {
                "categories": ["core_runtime"],
                "roles": ["global_service"],
                "systems": ["Core", "Gameplay"],
                "confidence": 0.62,
            }
        if "gpu_terrain" in haystack or "terrain_renderer" in haystack:
            return {
                "categories": ["presentation"],
                "roles": ["shape_visual"],
                "systems": ["Presentation"],
                "confidence": 0.62,
            }
        if "/utils/" in haystack or "/utills/" in haystack or "linkedlist" in haystack or "utils" in haystack:
            return {
                "categories": ["core_runtime"],
                "roles": ["global_service"],
                "systems": ["Core"],
                "confidence": 0.6,
            }
        if extends == "RefCounted":
            return {
                "categories": ["core_runtime"],
                "roles": ["global_service"],
                "systems": ["Core"],
                "confidence": 0.6,
            }
        if path.lower().endswith(".cs"):
            systems = {"Core"}
            categories = {"core_runtime"}
            roles = {"global_service"}
            api_usage = set(props.get("api_usage", []))
            if has_neutral_ui_path(haystack) or any(term in haystack for term in ("button", "panel", "label")):
                systems.add("UI")
                categories.add("ui_element")
                roles.add("ui_control")
            if any(api in api_usage for api in ("Input.is_action_just_pressed", "Input.is_action_pressed", "Input.get_vector", "move_and_slide")):
                systems.add("Gameplay")
            if any(term in haystack for term in ("vfx", "visual", "animation", "background", "spine")):
                systems.add("Presentation")
                categories.add("presentation")
            if any(term in haystack for term in ("audio", "fmod", "music", "sound")):
                systems.add("Audio")
            return {
                "categories": sorted(categories),
                "roles": sorted(roles),
                "systems": sorted(systems),
                "confidence": 0.5,
            }
        if path:
            return {
                "categories": ["core_runtime"],
                "roles": ["global_service"],
                "systems": ["Core"],
                "confidence": 0.45,
            }

    return {}


def has_neutral_ui_path(haystack: str) -> bool:
    return any(term in haystack for term in ("/ui/", "/uis/", "/screen", "/screens/", "/menu", "/menus/"))


def has_neutral_manager_name(haystack: str) -> bool:
    return any(term in haystack for term in ("manager", "service", "registry", "controller", "resolver", "executor", "system"))


def specific_api_systems(api_name: str, value: dict[str, Any], existing_systems: set[str]) -> set[str]:
    semantic = value.get("semantic")
    if semantic in {"dynamic_scene_creation", "runtime_scene_tree_mutation", "continuous_input_query", "discrete_input_query"}:
        return {"Gameplay"}
    if semantic in {"static_resource_reference", "dynamic_resource_reference"}:
        return {"Data"}
    if semantic in {"event_emission", "event_subscription", "event_contract"}:
        return {"Core"} if "UI" in existing_systems else set()
    return set()


def propagate_instance_semantics(graph: dict[str, Any], annotations: dict[str, Any]) -> None:
    scene_members = defaultdict(list)
    for edge in graph.get("edges", []):
        if edge.get("type") == "contains" and edge.get("source", "").startswith("scene:"):
            scene_members[edge["source"]].append(edge["target"])
    for edge in graph.get("edges", []):
        if edge.get("type") != "instantiates" or not edge.get("source", "").startswith("node:"):
            continue
        instance_id = edge["source"]
        target_scene = edge["target"]
        systems = set()
        roles = set()
        categories = set()
        evidence = edge.get("properties", {}).get("evidence_list", [])
        for member in scene_members.get(target_scene, []):
            member_annotation = annotations.get(member, {})
            systems.update(member_annotation.get("systems", []))
            roles.update(member_annotation.get("semantic_roles", []))
            categories.update(member_annotation.get("categories", []))
        if systems or roles or categories:
            annotations[instance_id] = {
                "kind": "Node",
                "categories": sorted(categories),
                "semantic_roles": ["scene_instance"],
                "contained_roles": sorted(roles),
                "systems": sorted(systems),
                "confidence": 0.72,
                "evidence": evidence or [{"source": "instantiated_scene", "scene": target_scene}],
            }


def evidence_for_node(node: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = node.get("properties", {}).get("evidence")
    return [evidence] if evidence else [{"source": "graph", "node_id": node["id"]}]


def match_patterns(
    graph: dict[str, Any],
    annotations: dict[str, Any],
    pattern_rules: dict[str, Any],
    confidence_threshold: float,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    outgoing = defaultdict(list)
    incoming = defaultdict(list)
    for edge in graph.get("edges", []):
        outgoing[edge["source"]].append(edge)
        incoming[edge["target"]].append(edge)

    for node in graph.get("nodes", []):
        node_id = node["id"]
        props = node.get("properties", {})
        annotation = annotations.get(node_id, {})
        roles = set(annotation.get("semantic_roles", []))
        systems = set(annotation.get("systems", []))
        api_usage = set(props.get("api_usage", []))

        if node["kind"] == "Script" and "movable_actor" in roles and (
            "Input.is_action_just_pressed" in api_usage or "Input.is_action_pressed" in api_usage or "Input.get_vector" in api_usage
        ):
            add_pattern(matches, "player_controller_candidate", node_id, ["movable actor", "input API"], pattern_rules, 0.88)

        if node["kind"] == "Node" and props.get("node_type") in {"Area2D", "Area3D"}:
            add_pattern(matches, "trigger_system_candidate", node_id, ["Area/trigger semantic"], pattern_rules, 0.78)
        if node["kind"] == "Script" and props.get("extends") in {"Area2D", "Area3D"}:
            add_pattern(matches, "trigger_system_candidate", node_id, ["Area/trigger semantic"], pattern_rules, 0.78)

        if node["kind"] == "Script" and ("connect" in api_usage or incoming[node_id] or outgoing[node_id]):
            if "UI" in systems or props.get("extends") in {"CanvasLayer", "Control"}:
                add_pattern(matches, "event_driven_ui", node_id, ["UI script", "signal/connect relationship"], pattern_rules, 0.76)

        if node["kind"] == "Script" and ("instantiate" in api_usage or "add_child" in api_usage):
            add_pattern(matches, "dynamic_scene_creation", node_id, ["runtime instantiation API"], pattern_rules, 0.82)

        if node["kind"] == "Autoload" or ("Manager" in systems and len(incoming[node_id]) >= 2):
            add_pattern(matches, "global_manager", node_id, ["shared manager-like node"], pattern_rules, 0.7)

    return [match for match in matches if match["confidence"] >= confidence_threshold]


def add_pattern(
    matches: list[dict[str, Any]],
    pattern_id: str,
    entity_id: str,
    evidence: list[str],
    pattern_rules: dict[str, Any],
    confidence: float,
) -> None:
    rule = pattern_rules.get(pattern_id, {})
    matches.append(
        {
            "id": f"pattern:{pattern_id}:{entity_id}",
            "pattern_id": pattern_id,
            "entity_id": entity_id,
            "systems": rule.get("systems", []),
            "confidence": max(confidence, rule.get("confidence", 0) if isinstance(rule.get("confidence"), (int, float)) else 0),
            "evidence": evidence,
        }
    )


def build_systems(
    graph: dict[str, Any],
    annotations: dict[str, Any],
    pattern_matches: list[dict[str, Any]],
    confidence_threshold: float,
) -> list[dict[str, Any]]:
    members_by_system: dict[str, set[str]] = defaultdict(set)
    evidence_by_system: dict[str, list[Any]] = defaultdict(list)
    confidence_by_system: dict[str, list[float]] = defaultdict(list)
    for entity_id, annotation in annotations.items():
        if annotation.get("kind") == "Edge":
            continue
        for system in annotation.get("systems", []):
            if system in CORE_SYSTEMS:
                members_by_system[system].add(entity_id)
                evidence_by_system[system].extend(annotation.get("evidence", [])[:1])
                confidence_by_system[system].append(annotation.get("confidence", 0.65))

    for match in pattern_matches:
        for system in match.get("systems", []):
            members_by_system[system].add(match["entity_id"])
            evidence_by_system[system].append({"pattern_id": match["pattern_id"], "entity_id": match["entity_id"]})
            confidence_by_system[system].append(match.get("confidence", 0.65))

    systems = []
    for system, members in sorted(members_by_system.items()):
        if not members:
            continue
        confidence = sum(confidence_by_system[system]) / max(len(confidence_by_system[system]), 1)
        if confidence < confidence_threshold:
            continue
        systems.append(
            {
                "id": f"system:{system.lower()}",
                "name": system,
                "kind": system,
                "members": sorted(members),
                "confidence": round(confidence, 3),
                "evidence": evidence_by_system[system][:10],
            }
        )
    return systems


def build_findings(
    graph: dict[str, Any],
    systems: list[dict[str, Any]],
    pattern_matches: list[dict[str, Any]],
    annotations: dict[str, Any],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    systems_by_kind = {system["kind"]: system for system in systems}
    if "UI" in systems_by_kind:
        findings.append(finding("finding:ui_system", "UI system detected", "UI", systems_by_kind["UI"]["members"][:8], 0.85))
    if "Gameplay" in systems_by_kind:
        findings.append(
            finding("finding:gameplay_system", "Gameplay entities and scripts detected", "Gameplay", systems_by_kind["Gameplay"]["members"][:8], 0.86)
        )
    if "Data" in systems_by_kind:
        findings.append(finding("finding:data_resources", "Data/resource usage detected", "Data", systems_by_kind["Data"]["members"][:8], 0.78))
    for pattern_id in sorted({match["pattern_id"] for match in pattern_matches}):
        members = [match["entity_id"] for match in pattern_matches if match["pattern_id"] == pattern_id]
        findings.append(finding(f"finding:pattern:{pattern_id}", f"Pattern matched: {pattern_id}", "Pattern", members, 0.75))
    return findings


def finding(finding_id: str, title: str, kind: str, evidence: list[str], confidence: float) -> dict[str, Any]:
    return {"id": finding_id, "title": title, "kind": kind, "confidence": confidence, "evidence": evidence}


def check_upstream_readiness(graph: dict[str, Any], annotations: dict[str, Any], taxonomy: dict[str, Any]) -> dict[str, Any]:
    graph_nodes = graph.get("nodes", [])
    unannotated_structural = [
        node["id"]
        for node in graph_nodes
        if node["kind"] in {"Node", "Script", "Resource"} and node["id"] not in annotations
    ]
    missing_core_systems = [system for system in ["UI", "Gameplay", "Data"] if system not in taxonomy.get("systems", [])]
    return {
        "layer2_graph_ready": not any(edge.get("unresolved") for edge in graph.get("edges", [])),
        "unresolved_edges": sum(1 for edge in graph.get("edges", []) if edge.get("unresolved")),
        "unannotated_structural_nodes": len(unannotated_structural),
        "unannotated_samples": unannotated_structural[:10],
        "missing_core_systems_in_taxonomy": missing_core_systems,
        "recommendations": recommendations_for(unannotated_structural, missing_core_systems),
    }


def recommendations_for(unannotated: list[str], missing_systems: list[str]) -> list[str]:
    recommendations = []
    if unannotated:
        recommendations.append("Consider extending Layer 0 semantics for unannotated node/script/resource types.")
    if missing_systems:
        recommendations.append("Add missing core systems to Layer 0 role_taxonomy before semantic analysis.")
    return recommendations


def build_report(
    systems: list[dict[str, Any]],
    pattern_matches: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    readiness: dict[str, Any],
) -> str:
    lines = [
        "# Layer 3 Semantic Report",
        "",
        "## Systems",
        "",
    ]
    for system in systems:
        lines.append(f"- {system['name']}: {len(system['members'])} members, confidence {system['confidence']}")
    lines.extend(["", "## Pattern Matches", ""])
    for pattern_id in sorted({match["pattern_id"] for match in pattern_matches}):
        count = sum(1 for match in pattern_matches if match["pattern_id"] == pattern_id)
        lines.append(f"- {pattern_id}: {count}")
    lines.extend(["", "## Findings", ""])
    for item in findings:
        lines.append(f"- {item['title']} ({item['kind']}, confidence {item['confidence']})")
    lines.extend(["", "## Upstream Readiness", ""])
    lines.append(f"- Layer 2 graph ready: {readiness['layer2_graph_ready']}")
    lines.append(f"- Unresolved edges: {readiness['unresolved_edges']}")
    lines.append(f"- Unannotated structural nodes: {readiness['unannotated_structural_nodes']}")
    if readiness["recommendations"]:
        for rec in readiness["recommendations"]:
            lines.append(f"- Recommendation: {rec}")
    else:
        lines.append("- Recommendations: None")
    lines.append("")
    return "\n".join(lines)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Godot Layer 3 semantic artifacts.")
    parser.add_argument("--layer0", required=True, help="Layer 0 artifact directory.")
    parser.add_argument("--layer2", required=True, help="Layer 2 artifact directory.")
    parser.add_argument("--output", required=True, help="Output directory for Layer 3 artifacts.")
    parser.add_argument("--confidence-threshold", type=float, default=0.6)
    args = parser.parse_args()
    analyze(args.layer0, args.layer2, args.output, args.confidence_threshold)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
