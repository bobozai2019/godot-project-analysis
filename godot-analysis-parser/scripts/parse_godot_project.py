#!/usr/bin/env python3
"""Extract Layer 1 static facts from a Godot project."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GENERATOR = "godot-analysis-parser"
SCHEMA_VERSION = "0.1.0"
SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LAYER0 = SKILL_ROOT.parent / "godot-analysis-foundation" / "assets" / "default-layer0"

RESOURCE_EXTENSIONS = {".tres", ".res", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".ogg", ".wav", ".mp3", ".import"}
RESOURCE_PATH_RE = re.compile(r'res://[^"\'\)\n\r]+')
API_NAMES = [
    "Input.is_action_just_pressed",
    "Input.is_action_pressed",
    "Input.get_vector",
    "ResourceLoader.load",
    "change_scene_to_file",
    "change_scene_to_packed",
    "get_nodes_in_group",
    "add_to_group",
    "emit_signal",
    "instantiate",
    "queue_free",
    "add_child",
    "remove_child",
    "connect",
    "disconnect",
    "preload",
    "load",
    "get_node",
    "find_child",
    "get_tree",
    "move_and_slide",
]


def artifact(artifact_type: str, project_root: Path, data: Any) -> dict[str, Any]:
    return {
        "artifact_type": artifact_type,
        "schema_version": SCHEMA_VERSION,
        "generator": GENERATOR,
        "godot_version": "4.x",
        "project_root": str(project_root),
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "data": data,
    }


def res_path(project_root: Path, path: Path) -> str:
    return "res://" + path.relative_to(project_root).as_posix()


def project_path(project_root: Path, res: str) -> Path:
    if not res.startswith("res://"):
        return project_root / res
    return project_root / res.removeprefix("res://")


def load_layer0(layer0_dir: Path | None) -> dict[str, Any]:
    root = layer0_dir or DEFAULT_LAYER0
    path = root / "foundation_semantics.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("data", {})


def parse_project(
    project_root: Path | str,
    output_dir: Path | str,
    layer0_dir: Path | str | None = None,
    exclude_addons: bool = False,
    resource_mode: str = "referenced",
) -> None:
    root = Path(project_root)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if not (root / "project.godot").exists():
        raise FileNotFoundError(f"project.godot not found under {root}")

    foundation = load_layer0(Path(layer0_dir) if layer0_dir else None)
    project_settings = parse_project_godot(root / "project.godot")
    all_files = [
        path
        for path in root.rglob("*")
        if path.is_file()
        and ".godot" not in path.parts
        and not path.is_relative_to(out)
        and not (exclude_addons and "addons" in path.relative_to(root).parts)
    ]
    scenes = sorted(res_path(root, path) for path in all_files if path.suffix == ".tscn")
    scripts = sorted(res_path(root, path) for path in all_files if path.suffix == ".gd")
    all_resources = sorted(res_path(root, path) for path in all_files if path.suffix in RESOURCE_EXTENSIONS)

    scene_data: dict[str, Any] = {}
    script_attachments: list[dict[str, Any]] = []
    scene_dependencies: list[dict[str, Any]] = []
    for scene_res in scenes:
        parsed_scene = parse_scene(root, scene_res, foundation)
        scene_data[scene_res] = parsed_scene
        script_attachments.extend(parsed_scene.pop("_script_dependencies"))
        scene_dependencies.extend(parsed_scene.pop("_scene_dependencies"))

    script_data: dict[str, Any] = {}
    script_dependencies: list[dict[str, Any]] = []
    for script_res in scripts:
        parsed_script = parse_script(root, script_res, foundation)
        script_data[script_res] = parsed_script
        script_dependencies.extend(parsed_script.pop("_dependencies"))

    dependencies = {
        "dependencies": sorted(
            script_attachments + scene_dependencies + script_dependencies + autoload_dependencies(project_settings),
            key=lambda item: (item["source"], item["type"], item["target"]),
        )
    }
    referenced_resources = sorted(
        {
            dep["target"].removeprefix("resource:")
            for dep in dependencies["dependencies"]
            if dep.get("target", "").startswith("resource:")
        }
    )
    if resource_mode == "all":
        resources = all_resources
    elif resource_mode == "referenced":
        resources = [resource for resource in referenced_resources if project_path(root, resource).exists()]
    else:
        raise ValueError(f"unsupported resource_mode: {resource_mode}")
    inventory = {
        "entry_scene": project_settings["entry_scene"],
        "autoloads": project_settings["autoloads"],
        "scenes": scenes,
        "scripts": scripts,
        "resources": resources,
        "inputs": project_settings["inputs"],
        "counts": {
            "scenes": len(scenes),
            "scripts": len(scripts),
            "resources": len(resources),
            "autoloads": len(project_settings["autoloads"]),
        },
        "options": {
            "exclude_addons": exclude_addons,
            "resource_mode": resource_mode,
        },
    }

    write_json(out / "project_inventory.json", artifact("project_inventory", root, inventory))
    write_json(out / "scene_parse.json", artifact("scene_parse", root, scene_data))
    write_json(out / "script_parse.json", artifact("script_parse", root, script_data))
    write_json(out / "dependency_extract.json", artifact("dependency_extract", root, dependencies))
    (out / "parser_report.md").write_text(build_report(inventory, dependencies), encoding="utf-8")


def parse_project_godot(path: Path) -> dict[str, Any]:
    section = ""
    entry_scene = None
    autoloads: list[dict[str, str]] = []
    inputs: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        section_match = re.match(r"\[([^\]]+)\]", line)
        if section_match:
            section = section_match.group(1)
            continue
        if section == "application":
            match = re.match(r'run/main_scene="([^"]+)"', line)
            if match:
                entry_scene = match.group(1)
        elif section == "autoload":
            match = re.match(r'([^=]+)="\*?([^"]+)"', line)
            if match:
                autoloads.append({"name": match.group(1).strip(), "path": match.group(2)})
        elif section == "input" and "=" in line and not line.startswith('"'):
            inputs.append(line.split("=", 1)[0])
    return {"entry_scene": entry_scene, "autoloads": autoloads, "inputs": inputs}


def parse_scene(project_root: Path, scene_res: str, foundation: dict[str, Any]) -> dict[str, Any]:
    path = project_path(project_root, scene_res)
    lines = path.read_text(encoding="utf-8").splitlines()
    ext_resources: dict[str, dict[str, str]] = {}
    nodes: list[dict[str, Any]] = []
    connections: list[dict[str, Any]] = []
    script_deps: list[dict[str, Any]] = []
    scene_deps: list[dict[str, Any]] = []
    current_node: dict[str, Any] | None = None
    node_path_counts: dict[str, int] = {}
    node_path_types: dict[str, str] = {}

    for index, raw in enumerate(lines, start=1):
        line = raw.strip()
        ext_match = re.match(r"\[ext_resource\s+(.+)\]", line)
        if ext_match:
            attrs = parse_tag_attrs(ext_match.group(1))
            if attrs.get("id") and attrs.get("path"):
                ext_resources[attrs["id"]] = {"type": attrs.get("type", "Resource"), "path": attrs["path"], "uid": attrs.get("uid")}
            continue
        node_match = re.match(r"\[node\s+(.+)\]", line)
        if node_match:
            attrs = parse_tag_attrs(node_match.group(1))
            name = attrs.get("name")
            if not name:
                continue
            node_type = attrs.get("type")
            parent = attrs.get("parent")
            instance_id = attrs.get("instance")
            instance = ext_resources.get(instance_id or "", {})
            if not node_type and instance.get("type") == "PackedScene":
                node_type = "PackedSceneInstance"
            node_path = canonical_node_path(name, parent)
            if not node_type and node_path in node_path_types:
                node_type = node_path_types[node_path]
            node_path_counts[node_path] = node_path_counts.get(node_path, 0) + 1
            node_id_path = node_path if node_path_counts[node_path] == 1 else f"{node_path}#{node_path_counts[node_path]}"
            node_path_types[node_path] = node_type or "Unknown"
            current_node = {
                "node_id": f"node:{scene_res}::{node_id_path}",
                "scene_id": f"scene:{scene_res}",
                "name": name,
                "path": node_path,
                "type": node_type or "Unknown",
                "parent": parent_node_id(scene_res, parent),
                "script": None,
                "instance": instance.get("path"),
                "semantic": semantic_for(node_type or "Unknown", foundation),
                "evidence": {"source_path": scene_res, "line": index, "raw": raw},
            }
            nodes.append(current_node)
            if instance.get("path"):
                scene_deps.append(dep(current_node["node_id"], f"scene:{instance['path']}", "instances_scene", raw, scene_res, index))
            continue
        connection_match = re.match(r'\[connection signal="([^"]+)" from="([^"]+)" to="([^"]+)" method="([^"]+)"\]', line)
        if connection_match:
            signal_name, source, target, method = connection_match.groups()
            connections.append({"signal": signal_name, "from": source, "to": target, "method": method, "evidence": {"source_path": scene_res, "line": index, "raw": raw}})
            continue
        if current_node and line.startswith("script = ExtResource"):
            resource_id = re.search(r'ExtResource\("([^"]+)"\)', line)
            if resource_id and resource_id.group(1) in ext_resources:
                script_path = ext_resources[resource_id.group(1)]["path"]
                current_node["script"] = f"script:{script_path}"
                script_deps.append(dep(current_node["node_id"], f"script:{script_path}", "attaches_script", raw, scene_res, index))
        elif current_node and "ExtResource" in line:
            for resource_id in re.findall(r'ExtResource\("([^"]+)"\)', line):
                resource = ext_resources.get(resource_id)
                if resource and resource.get("path"):
                    dep_type = "references_resource"
                    target_prefix = "resource"
                    if resource.get("type") == "PackedScene":
                        dep_type = "references_packed_scene"
                        target_prefix = "scene"
                    scene_deps.append(dep(current_node["node_id"], f"{target_prefix}:{resource['path']}", dep_type, raw, scene_res, index))

    return {
        "scene_id": f"scene:{scene_res}",
        "path": scene_res,
        "ext_resources": ext_resources,
        "nodes": nodes,
        "connections": connections,
        "_script_dependencies": script_deps,
        "_scene_dependencies": scene_deps,
    }


def parse_tag_attrs(raw: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for key, quoted, bare in re.findall(r'([A-Za-z0-9_]+)=("([^"]*)"|[^\s\]]+)', raw):
        value = quoted
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        ext = re.match(r'ExtResource\("([^"]+)"\)', value)
        attrs[key] = ext.group(1) if ext else value
    return attrs


def canonical_node_path(name: str, parent: str | None) -> str:
    if not parent or parent == ".":
        return f"/{name}"
    return "/" + parent.strip("/").removeprefix("./") + f"/{name}"


def parent_node_id(scene_res: str, parent: str | None) -> str | None:
    if not parent or parent == ".":
        return None
    return f"node:{scene_res}::/{parent.strip('/')}"


def parse_script(project_root: Path, script_res: str, foundation: dict[str, Any]) -> dict[str, Any]:
    path = project_path(project_root, script_res)
    lines = path.read_text(encoding="utf-8").splitlines()
    code_lines = [line for line in lines if not line.strip().startswith("#")]
    text = "\n".join(code_lines)
    extends = None
    class_name = None
    signals: list[str] = []
    functions: list[str] = []
    api_usage: list[str] = []
    literal_resource_paths = sorted(set(RESOURCE_PATH_RE.findall(text)))
    dependencies: list[dict[str, Any]] = []

    for index, raw in enumerate(lines, start=1):
        line = raw.strip()
        if line.startswith("#"):
            continue
        extends_match = re.match(r"extends\s+([A-Za-z0-9_\.]+)", line)
        if extends_match:
            extends = extends_match.group(1)
        class_match = re.match(r"class_name\s+([A-Za-z0-9_]+)", line)
        if class_match:
            class_name = class_match.group(1)
        signal_match = re.match(r"signal\s+([A-Za-z0-9_]+)", line)
        if signal_match:
            signals.append(signal_match.group(1))
        func_match = re.match(r"func\s+([A-Za-z0-9_]+)\s*\(", line)
        if func_match:
            functions.append(func_match.group(1))
        for api_name in API_NAMES:
            if api_name in line or (api_name == "emit_signal" and ".emit(" in line) or (api_name == "connect" and ".connect(" in line):
                if api_name not in api_usage:
                    api_usage.append(api_name)
        for resource_path in RESOURCE_PATH_RE.findall(line):
            dependencies.append(dep(f"script:{script_res}", typed_target(resource_path), "references_resource_path", raw, script_res, index))
        for call in ("preload", "load"):
            for resource_path in re.findall(call + r'\("([^"]+)"\)', line):
                dep_type = "preloads" if call == "preload" else "loads"
                dependencies.append(dep(f"script:{script_res}", typed_target(resource_path), dep_type, raw, script_res, index))
        if "change_scene_to_file" in line:
            for resource_path in re.findall(r'change_scene_to_file\("([^"]+)"\)', line):
                dependencies.append(dep(f"script:{script_res}", f"scene:{resource_path}", "transitions_to", raw, script_res, index))
        if ".connect(" in line:
            dependencies.append(dep(f"script:{script_res}", f"signal:{script_res}::connect", "connects_signal", raw, script_res, index))
        if ".emit(" in line or "emit_signal" in line:
            dependencies.append(dep(f"script:{script_res}", f"signal:{script_res}::emit", "emits_signal", raw, script_res, index))

    return {
        "script_id": f"script:{script_res}",
        "path": script_res,
        "extends": extends,
        "class_name": class_name,
        "signals": signals,
        "functions": functions,
        "api_usage": sorted(api_usage),
        "literal_resource_paths": literal_resource_paths,
        "semantic": semantic_for(extends or "", foundation),
        "_dependencies": dependencies,
    }


def typed_target(resource_path: str) -> str:
    if resource_path.endswith(".tscn"):
        return f"scene:{resource_path}"
    if resource_path.endswith(".gd"):
        return f"script:{resource_path}"
    return f"resource:{resource_path}"


def semantic_for(class_name: str, foundation: dict[str, Any]) -> dict[str, Any]:
    value = foundation.get(class_name, {})
    if not value:
        return {}
    return {
        "category": value.get("category"),
        "roles": value.get("roles", []),
        "systems": value.get("systems", []),
        "confidence": value.get("confidence"),
        "source": value.get("source"),
    }


def dep(source: str, target: str, dep_type: str, raw: str, source_path: str, line: int) -> dict[str, Any]:
    return {
        "source": source,
        "target": target,
        "type": dep_type,
        "evidence": {"source_path": source_path, "line": line, "raw": raw.strip()},
    }


def autoload_dependencies(settings: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for item in settings.get("autoloads", []):
        result.append(
            {
                "source": "project:project.godot",
                "target": f"script:{item['path']}",
                "type": "defines_autoload",
                "autoload_name": item["name"],
                "evidence": {"source_path": "res://project.godot", "line": None, "raw": item["path"]},
            }
        )
    return result


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_report(inventory: dict[str, Any], dependencies: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Layer 1 Parser Report",
            "",
            f"- Entry scene: `{inventory.get('entry_scene')}`",
            f"- Scenes: {inventory['counts']['scenes']}",
            f"- Scripts: {inventory['counts']['scripts']}",
            f"- Resources: {inventory['counts']['resources']}",
            f"- Autoloads: {inventory['counts']['autoloads']}",
            f"- Dependencies: {len(dependencies['dependencies'])}",
            "",
            "Layer 1 extracts static facts only. Architecture interpretation belongs to later layers.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract Godot Layer 1 static facts.")
    parser.add_argument("--project", required=True, help="Godot project root containing project.godot.")
    parser.add_argument("--output", required=True, help="Output directory for Layer 1 artifacts.")
    parser.add_argument("--layer0", help="Optional Layer 0 artifact directory for light semantic labels.")
    parser.add_argument("--exclude-addons", action="store_true", help="Exclude res://addons content from Layer 1 inventory and parsing.")
    parser.add_argument(
        "--resource-mode",
        choices=["referenced", "all"],
        default="referenced",
        help="Use only referenced resources by default, or include every discovered resource.",
    )
    args = parser.parse_args()
    parse_project(args.project, args.output, args.layer0, exclude_addons=args.exclude_addons, resource_mode=args.resource_mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
