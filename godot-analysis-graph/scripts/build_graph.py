#!/usr/bin/env python3
"""Build Layer 2 relationship graph from Layer 1 Godot artifacts."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GENERATOR = "godot-analysis-graph"
SCHEMA_VERSION = "0.1.0"

EDGE_TYPE_MAP = {
    "attaches_script": "attaches",
    "instances_scene": "instantiates",
    "references_packed_scene": "references",
    "references_resource": "references",
    "references_resource_path": "references",
    "preloads": "references",
    "loads": "references",
    "transitions_to": "transitions_to",
    "connects_signal": "connects",
    "emits_signal": "emits",
    "defines_autoload": "defines_autoload",
}


def read_artifact(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def artifact(artifact_type: str, project_root: str | None, data: Any) -> dict[str, Any]:
    return {
        "artifact_type": artifact_type,
        "schema_version": SCHEMA_VERSION,
        "generator": GENERATOR,
        "godot_version": "4.x",
        "project_root": project_root,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "data": data,
    }


def build_graph(layer1_dir: Path | str, output_dir: Path | str) -> None:
    layer1 = Path(layer1_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    inventory_artifact = read_artifact(layer1 / "project_inventory.json")
    scene_artifact = read_artifact(layer1 / "scene_parse.json")
    script_artifact = read_artifact(layer1 / "script_parse.json")
    dependency_artifact = read_artifact(layer1 / "dependency_extract.json")
    project_root = inventory_artifact.get("project_root")

    inventory = inventory_artifact["data"]
    scenes = scene_artifact["data"]
    scripts = script_artifact["data"]
    dependencies = dependency_artifact["data"]["dependencies"]

    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    add_node(nodes, "project:project.godot", "Project", {"path": "res://project.godot"})

    for scene_path, scene in scenes.items():
        scene_id = scene.get("scene_id") or f"scene:{scene_path}"
        add_node(nodes, scene_id, "Scene", {"path": scene_path, "is_entry": scene_path == inventory.get("entry_scene")})
        for node in scene.get("nodes", []):
            node_id = node["node_id"]
            add_node(
                nodes,
                node_id,
                "Node",
                {
                    "name": node.get("name"),
                    "path": node.get("path"),
                    "node_type": node.get("type"),
                    "scene": scene_id,
                    "script": node.get("script"),
                    "instance": node.get("instance"),
                    "semantic": node.get("semantic", {}),
                    "evidence": node.get("evidence"),
                },
            )
            add_edge(edges, scene_id, node_id, "contains", {"source": "scene_parse"})
            if node.get("parent"):
                add_node(
                    nodes,
                    node["parent"],
                    "Node",
                    {
                        "path": parent_path_from_node_id(node["parent"]),
                        "scene": scene_id,
                        "derived_from_parent_path": True,
                    },
                )
                add_edge(edges, node["parent"], node_id, "contains", {"source": "scene_parse", "relationship": "parent_child"})
            if node.get("script"):
                script_path = node["script"].removeprefix("script:")
                add_node(
                    nodes,
                    node["script"],
                    "Script",
                    {
                        "path": script_path,
                        "discovered_from_scene": True,
                    },
                )
                add_edge(edges, node_id, node["script"], "attaches", {"source": "scene_parse"})
            if node.get("instance"):
                if str(node["instance"]).lower().endswith(".fbx"):
                    add_node(nodes, f"scene:{node['instance']}", "Scene", {"path": node["instance"], "imported_scene": True})
                add_edge(edges, node_id, f"scene:{node['instance']}", "instantiates", {"source": "scene_parse"})
        for connection in scene.get("connections", []):
            signal_id = f"signal:{scene_path}::{connection.get('from')}::{connection.get('signal')}"
            add_node(nodes, signal_id, "Signal", {"scene": scene_id, "signal": connection.get("signal"), "from": connection.get("from")})
            add_edge(edges, f"scene:{scene_path}", signal_id, "contains", {"source": "scene_connection", "evidence": connection.get("evidence")})

    for script_path, script in scripts.items():
        script_id = script.get("script_id") or f"script:{script_path}"
        add_node(
            nodes,
            script_id,
            "Script",
            {
                "path": script_path,
                "extends": script.get("extends"),
                "class_name": script.get("class_name"),
                "signals": script.get("signals", []),
                "functions": script.get("functions", []),
                "api_usage": script.get("api_usage", []),
                "semantic": script.get("semantic", {}),
            },
        )
        for signal_name in script.get("signals", []):
            signal_id = f"signal:{script_path}::{signal_name}"
            add_node(nodes, signal_id, "Signal", {"script": script_id, "signal": signal_name})
            add_edge(edges, script_id, signal_id, "defines_signal", {"source": "script_parse"})

    for resource_path in inventory.get("resources", []):
        add_node(nodes, f"resource:{resource_path}", "Resource", {"path": resource_path})

    for autoload in inventory.get("autoloads", []):
        autoload_id = f"autoload:{autoload['name']}"
        add_node(nodes, autoload_id, "Autoload", {"name": autoload["name"], "path": autoload.get("path")})
        if autoload.get("path"):
            target_id = node_id_for_resource_path(autoload["path"])
            ensure_declared_resource_node(nodes, target_id)
            add_edge(edges, autoload_id, target_id, "references", {"source": "project_inventory"})

    for dependency in dependencies:
        source = normalize_dependency_node_id(dependency["source"])
        target = normalize_dependency_node_id(dependency["target"])
        edge_type = EDGE_TYPE_MAP.get(dependency["type"], dependency["type"])
        ensure_dependency_endpoint(nodes, source)
        ensure_dependency_endpoint(nodes, target)
        metadata = {
            "source_type": dependency["type"],
            "evidence": dependency.get("evidence"),
        }
        add_edge(edges, source, target, edge_type, metadata)

    mark_unresolved(nodes, edges)

    graph = {
        "metadata": {
            "entry_scene": inventory.get("entry_scene"),
            "source_artifacts": ["project_inventory.json", "scene_parse.json", "script_parse.json", "dependency_extract.json"],
        },
        "nodes": sorted(nodes.values(), key=lambda item: item["id"]),
        "edges": sorted(edges.values(), key=lambda item: item["id"]),
    }
    index = build_index(graph)
    stats = build_stats(graph)

    write_json(out / "graph.json", artifact("graph", project_root, graph))
    write_json(out / "graph_index.json", artifact("graph_index", project_root, index))
    write_json(out / "graph_stats.json", artifact("graph_stats", project_root, stats))
    (out / "graph_build_report.md").write_text(build_report(stats), encoding="utf-8")


def add_node(nodes: dict[str, dict[str, Any]], node_id: str, kind: str, properties: dict[str, Any]) -> None:
    if node_id in nodes:
        nodes[node_id]["properties"].update({key: value for key, value in properties.items() if value not in (None, [], {})})
        return
    nodes[node_id] = {"id": node_id, "kind": kind, "properties": {key: value for key, value in properties.items() if value not in (None, [], {})}}


def parent_path_from_node_id(node_id: str) -> str | None:
    if "::" not in node_id:
        return None
    return node_id.split("::", 1)[1]


def node_id_for_resource_path(path: str) -> str:
    lower_path = path.lower()
    if lower_path.endswith(".tscn"):
        return f"scene:{path}"
    if lower_path.endswith((".gd", ".cs")):
        return f"script:{path}"
    return f"resource:{path}"


def normalize_dependency_node_id(node_id: str) -> str:
    if node_id.startswith("script:"):
        path = node_id.removeprefix("script:")
        if path.lower().endswith(".tscn"):
            return f"scene:{path}"
    return node_id


def ensure_declared_resource_node(nodes: dict[str, dict[str, Any]], node_id: str) -> None:
    if node_id.startswith("scene:"):
        add_node(nodes, node_id, "Scene", {"path": node_id.removeprefix("scene:"), "declared_autoload": True})
    elif node_id.startswith("script:"):
        add_node(nodes, node_id, "Script", {"path": node_id.removeprefix("script:"), "declared_autoload": True})
    elif node_id.startswith("resource:"):
        add_node(nodes, node_id, "Resource", {"path": node_id.removeprefix("resource:"), "declared_autoload": True})


def ensure_dependency_endpoint(nodes: dict[str, dict[str, Any]], node_id: str) -> None:
    if node_id in nodes:
        return
    if node_id.startswith("scene:"):
        path = node_id.removeprefix("scene:")
        if path.lower().endswith(".fbx"):
            add_node(nodes, node_id, "Scene", {"path": path, "imported_scene": True})
        else:
            add_node(nodes, node_id, "Scene", {"path": path, "placeholder": True})
    elif node_id.startswith("script:"):
        add_node(nodes, node_id, "Script", {"path": node_id.removeprefix("script:"), "placeholder": True})
    elif node_id.startswith("resource:"):
        add_node(nodes, node_id, "Resource", {"path": node_id.removeprefix("resource:"), "placeholder": True})
    elif node_id.startswith("signal:"):
        add_node(nodes, node_id, "Signal", {"derived_from_dependency": True})
    elif node_id.startswith("project:"):
        add_node(nodes, node_id, "Project", {"path": "res://project.godot"})
    else:
        add_node(nodes, node_id, "Unknown", {"placeholder": True})


def add_edge(edges: dict[str, dict[str, Any]], source: str, target: str, edge_type: str, properties: dict[str, Any]) -> None:
    edge_id = f"{source} -> {edge_type} -> {target}"
    if edge_id in edges:
        existing_evidence = edges[edge_id]["properties"].setdefault("evidence_list", [])
        evidence = properties.get("evidence")
        if evidence and evidence not in existing_evidence:
            existing_evidence.append(evidence)
        return
    properties = {key: value for key, value in properties.items() if value not in (None, [], {})}
    if "evidence" in properties:
        properties["evidence_list"] = [properties.pop("evidence")]
    edges[edge_id] = {"id": edge_id, "source": source, "target": target, "type": edge_type, "properties": properties}


def mark_unresolved(nodes: dict[str, dict[str, Any]], edges: dict[str, dict[str, Any]]) -> None:
    for edge in edges.values():
        source_node = nodes.get(edge["source"])
        target_node = nodes.get(edge["target"])
        unresolved = False
        reasons = []
        if not source_node:
            unresolved = True
            reasons.append("missing_source")
        elif source_node["properties"].get("placeholder"):
            unresolved = True
            reasons.append("placeholder_source")
        if not target_node:
            unresolved = True
            reasons.append("missing_target")
        elif target_node["properties"].get("placeholder"):
            unresolved = True
            reasons.append("placeholder_target")
        if unresolved:
            edge["unresolved"] = True
            edge["unresolved_reason"] = ",".join(reasons)


def build_index(graph: dict[str, Any]) -> dict[str, Any]:
    nodes_by_kind: dict[str, list[str]] = defaultdict(list)
    nodes_by_path: dict[str, str] = {}
    edges_by_type: dict[str, list[str]] = defaultdict(list)
    outgoing: dict[str, list[str]] = defaultdict(list)
    incoming: dict[str, list[str]] = defaultdict(list)
    for node in graph["nodes"]:
        nodes_by_kind[node["kind"]].append(node["id"])
        path = node.get("properties", {}).get("path")
        if path:
            nodes_by_path[path] = node["id"]
    for edge in graph["edges"]:
        edges_by_type[edge["type"]].append(edge["id"])
        outgoing[edge["source"]].append(edge["id"])
        incoming[edge["target"]].append(edge["id"])
    return {
        "nodes_by_kind": sort_lists(nodes_by_kind),
        "nodes_by_path": dict(sorted(nodes_by_path.items())),
        "edges_by_type": sort_lists(edges_by_type),
        "outgoing_edges": sort_lists(outgoing),
        "incoming_edges": sort_lists(incoming),
    }


def sort_lists(mapping: dict[str, list[str]]) -> dict[str, list[str]]:
    return {key: sorted(value) for key, value in sorted(mapping.items())}


def build_stats(graph: dict[str, Any]) -> dict[str, Any]:
    node_kinds = Counter(node["kind"] for node in graph["nodes"])
    edge_types = Counter(edge["type"] for edge in graph["edges"])
    unresolved = [edge for edge in graph["edges"] if edge.get("unresolved")]
    return {
        "nodes": len(graph["nodes"]),
        "edges": len(graph["edges"]),
        "node_kinds": dict(sorted(node_kinds.items())),
        "edge_types": dict(sorted(edge_types.items())),
        "scenes": node_kinds.get("Scene", 0),
        "scripts": node_kinds.get("Script", 0),
        "resources": node_kinds.get("Resource", 0),
        "signals": node_kinds.get("Signal", 0),
        "unresolved_edges": len(unresolved),
    }


def build_report(stats: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Layer 2 Graph Build Report",
            "",
            f"- Nodes: {stats['nodes']}",
            f"- Edges: {stats['edges']}",
            f"- Scenes: {stats['scenes']}",
            f"- Scripts: {stats['scripts']}",
            f"- Resources: {stats['resources']}",
            f"- Signals: {stats['signals']}",
            f"- Unresolved edges: {stats['unresolved_edges']}",
            "",
            "Layer 2 normalizes Layer 1 static facts into a queryable relationship graph. It does not infer systems or architecture.",
            "",
        ]
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Godot Layer 2 relationship graph.")
    parser.add_argument("--layer1", required=True, help="Layer 1 artifact directory.")
    parser.add_argument("--output", required=True, help="Output directory for Layer 2 artifacts.")
    args = parser.parse_args()
    build_graph(args.layer1, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
