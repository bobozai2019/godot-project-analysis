#!/usr/bin/env python3
"""Build Layer 0 Godot semantic foundation artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GENERATOR = "godot-analysis-foundation"
SCHEMA_VERSION = "0.1.0"


def _source(kind: str, rule_id: str) -> dict[str, str]:
    return {"kind": kind, "rule_id": rule_id}


def _class(category: str, roles: list[str], systems: list[str], confidence: float) -> dict[str, Any]:
    return {
        "category": category,
        "roles": roles,
        "systems": systems,
        "importance": "high" if confidence >= 0.85 else "medium",
        "confidence": confidence,
        "source": _source("manual_rule", f"class.{category}.{len(roles)}"),
    }


def _api(semantic: str, systems: list[str], confidence: float) -> dict[str, Any]:
    return {
        "semantic": semantic,
        "systems": systems,
        "confidence": confidence,
        "source": _source("manual_rule", f"api.{semantic}"),
    }


ROLE_TAXONOMY: dict[str, Any] = {
    "categories": {
        "core_runtime": "Base Godot runtime and tree coordination primitives.",
        "gameplay_entity": "World actor or interactive entity participating in gameplay.",
        "ui_element": "Player-facing interface element or UI layer.",
        "manager": "Global or shared coordinator for flow, state, services, or resources.",
        "data_resource": "Data-bearing resource or external configuration surface.",
        "presentation": "Visual, audio, camera, or animation presentation support.",
        "physics": "Collision, movement, trigger, or physics participation.",
        "navigation": "Pathfinding and navigation support.",
    },
    "systems": [
        "Core",
        "Gameplay",
        "UI",
        "Manager",
        "Data",
        "Audio",
        "Animation",
        "Physics",
        "Navigation",
        "Presentation",
    ],
    "roles": [
        "scene_tree_root",
        "scene_instance",
        "movable_actor",
        "player_candidate",
        "enemy_candidate",
        "trigger_candidate",
        "ui_layer",
        "ui_control",
        "global_service",
        "scene_transition_driver",
        "data_container",
        "animation_driver",
        "audio_emitter",
        "camera_controller",
        "navigation_agent",
        "spawn_marker",
        "layout_container",
        "shape_visual",
        "collision_shape",
    ],
}


FOUNDATION_SEMANTICS: dict[str, Any] = {
    "Object": _class("core_runtime", ["scene_tree_root"], ["Core"], 0.7),
    "Node": _class("core_runtime", ["scene_tree_root", "scene_instance"], ["Core"], 0.9),
    "SceneTree": _class("manager", ["scene_transition_driver"], ["Core", "Manager"], 0.9),
    "PackedScene": _class("data_resource", ["scene_instance"], ["Core", "Data"], 0.9),
    "PackedSceneInstance": _class("presentation", ["scene_instance"], ["Presentation"], 0.75),
    "Resource": _class("data_resource", ["data_container"], ["Data"], 0.9),
    "Node2D": _class("gameplay_entity", ["scene_instance"], ["Gameplay", "Presentation"], 0.8),
    "Node3D": _class("gameplay_entity", ["scene_instance"], ["Gameplay", "Presentation"], 0.8),
    "CharacterBody2D": _class("gameplay_entity", ["movable_actor", "player_candidate", "enemy_candidate"], ["Gameplay", "Physics"], 0.9),
    "CharacterBody3D": _class("gameplay_entity", ["movable_actor", "player_candidate", "enemy_candidate"], ["Gameplay", "Physics"], 0.9),
    "Area2D": _class("physics", ["trigger_candidate"], ["Gameplay", "Physics"], 0.9),
    "Area3D": _class("physics", ["trigger_candidate"], ["Gameplay", "Physics"], 0.9),
    "RigidBody2D": _class("physics", ["movable_actor"], ["Gameplay", "Physics"], 0.8),
    "StaticBody2D": _class("physics", ["scene_instance"], ["Gameplay", "Physics"], 0.8),
    "StaticBody3D": _class("physics", ["scene_instance"], ["Gameplay", "Physics"], 0.8),
    "CollisionShape2D": _class("physics", ["collision_shape"], ["Physics"], 0.8),
    "CollisionShape3D": _class("physics", ["collision_shape"], ["Physics"], 0.8),
    "Control": _class("ui_element", ["ui_control"], ["UI"], 0.95),
    "CanvasLayer": _class("ui_element", ["ui_layer"], ["UI"], 0.95),
    "Button": _class("ui_element", ["ui_control"], ["UI"], 0.95),
    "CheckButton": _class("ui_element", ["ui_control"], ["UI"], 0.9),
    "TextureButton": _class("ui_element", ["ui_control"], ["UI", "Presentation"], 0.9),
    "Label": _class("ui_element", ["ui_control"], ["UI"], 0.9),
    "RichTextLabel": _class("ui_element", ["ui_control"], ["UI"], 0.9),
    "Panel": _class("ui_element", ["ui_control"], ["UI"], 0.85),
    "PanelContainer": _class("ui_element", ["ui_control", "layout_container"], ["UI"], 0.85),
    "TextureRect": _class("ui_element", ["ui_control"], ["UI", "Presentation"], 0.85),
    "ProgressBar": _class("ui_element", ["ui_control"], ["UI"], 0.85),
    "HSlider": _class("ui_element", ["ui_control"], ["UI"], 0.85),
    "SpinBox": _class("ui_element", ["ui_control"], ["UI"], 0.85),
    "LineEdit": _class("ui_element", ["ui_control"], ["UI"], 0.85),
    "FileDialog": _class("ui_element", ["ui_control"], ["UI"], 0.85),
    "Container": _class("ui_element", ["ui_control"], ["UI"], 0.85),
    "MarginContainer": _class("ui_element", ["layout_container"], ["UI"], 0.85),
    "VBoxContainer": _class("ui_element", ["layout_container"], ["UI"], 0.85),
    "HBoxContainer": _class("ui_element", ["layout_container"], ["UI"], 0.85),
    "GridContainer": _class("ui_element", ["layout_container"], ["UI"], 0.85),
    "ScrollContainer": _class("ui_element", ["layout_container"], ["UI"], 0.85),
    "HSeparator": _class("ui_element", ["layout_container"], ["UI"], 0.8),
    "VSeparator": _class("ui_element", ["layout_container"], ["UI"], 0.8),
    "VSplitContainer": _class("ui_element", ["layout_container"], ["UI"], 0.85),
    "SubViewport": _class("core_runtime", ["scene_instance"], ["Core", "Presentation"], 0.8),
    "Timer": _class("manager", ["global_service"], ["Core", "Manager"], 0.75),
    "AnimationPlayer": _class("presentation", ["animation_driver"], ["Animation", "Presentation"], 0.9),
    "AudioStreamPlayer": _class("presentation", ["audio_emitter"], ["Audio", "Presentation"], 0.9),
    "Camera2D": _class("presentation", ["camera_controller"], ["Presentation"], 0.8),
    "Camera3D": _class("presentation", ["camera_controller"], ["Presentation"], 0.8),
    "DirectionalLight3D": _class("presentation", ["scene_instance"], ["Presentation"], 0.75),
    "NavigationAgent2D": _class("navigation", ["navigation_agent"], ["Navigation", "Gameplay"], 0.85),
    "Marker2D": _class("core_runtime", ["spawn_marker"], ["Core", "Gameplay"], 0.75),
    "Polygon2D": _class("presentation", ["shape_visual"], ["Presentation"], 0.75),
    "Sprite2D": _class("presentation", ["scene_instance"], ["Presentation"], 0.75),
    "Sprite3D": _class("presentation", ["scene_instance"], ["Presentation"], 0.75),
    "MeshInstance3D": _class("presentation", ["shape_visual"], ["Presentation"], 0.8),
    "GPUParticles3D": _class("presentation", ["shape_visual"], ["Presentation"], 0.8),
    "AnimatedSprite2D": _class("presentation", ["animation_driver"], ["Animation", "Presentation"], 0.85),
    "TileMap": _class("presentation", ["scene_instance"], ["Gameplay", "Presentation"], 0.75),
    "ConfigFile": _class("data_resource", ["data_container"], ["Data"], 0.85),
    "JSON": _class("data_resource", ["data_container"], ["Data"], 0.75),
}


API_SEMANTICS: dict[str, Any] = {
    "_ready": _api("lifecycle_initialization", ["Core"], 0.85),
    "_process": _api("frame_update", ["Core", "Gameplay"], 0.8),
    "_physics_process": _api("physics_update", ["Gameplay", "Physics"], 0.9),
    "_input": _api("input_handling", ["Gameplay", "UI"], 0.85),
    "_unhandled_input": _api("input_handling", ["Gameplay", "UI"], 0.85),
    "instantiate": _api("dynamic_scene_creation", ["Core", "Gameplay"], 0.95),
    "queue_free": _api("runtime_lifetime_end", ["Core"], 0.9),
    "add_child": _api("runtime_scene_tree_mutation", ["Core"], 0.9),
    "remove_child": _api("runtime_scene_tree_mutation", ["Core"], 0.8),
    "change_scene_to_file": _api("scene_transition", ["Core", "Manager"], 0.95),
    "change_scene_to_packed": _api("scene_transition", ["Core", "Manager"], 0.95),
    "signal": _api("event_contract", ["Core"], 0.8),
    "emit_signal": _api("event_emission", ["Core"], 0.9),
    "connect": _api("event_subscription", ["Core"], 0.9),
    "disconnect": _api("event_subscription_removed", ["Core"], 0.8),
    "add_to_group": _api("group_membership", ["Core"], 0.85),
    "get_nodes_in_group": _api("group_query", ["Core", "Manager"], 0.85),
    "call_group": _api("group_broadcast", ["Core", "Manager"], 0.85),
    "Input.is_action_pressed": _api("continuous_input_query", ["Gameplay"], 0.9),
    "Input.is_action_just_pressed": _api("discrete_input_query", ["Gameplay", "UI"], 0.9),
    "preload": _api("static_resource_reference", ["Core", "Data"], 0.9),
    "load": _api("dynamic_resource_reference", ["Core", "Data"], 0.8),
    "ResourceLoader.load": _api("dynamic_resource_reference", ["Core", "Data"], 0.85),
    "get_node": _api("node_lookup", ["Core"], 0.8),
    "find_child": _api("node_lookup", ["Core"], 0.75),
    "get_tree": _api("scene_tree_access", ["Core", "Manager"], 0.85),
}


PATTERN_RULES: dict[str, Any] = {
    "player_controller_candidate": {
        "description": "Movable character with input polling is likely a player controller.",
        "required_semantics": ["movable_actor"],
        "required_api_semantics": ["continuous_input_query"],
        "systems": ["Gameplay"],
        "confidence": 0.85,
        "source": _source("manual_rule", "pattern.player_controller_candidate"),
    },
    "trigger_system_candidate": {
        "description": "Area node with body-entered signal behavior is likely a trigger system.",
        "required_classes": ["Area2D", "Area3D"],
        "required_api_semantics": ["event_subscription"],
        "systems": ["Gameplay", "Physics"],
        "confidence": 0.8,
        "source": _source("manual_rule", "pattern.trigger_system_candidate"),
    },
    "event_driven_ui": {
        "description": "UI controls connected to emitted gameplay events indicate event-driven UI.",
        "required_categories": ["ui_element"],
        "required_api_semantics": ["event_subscription", "event_emission"],
        "systems": ["UI"],
        "confidence": 0.75,
        "source": _source("manual_rule", "pattern.event_driven_ui"),
    },
    "global_manager": {
        "description": "Autoload-like node or script referenced across systems is likely a manager.",
        "required_category": "manager",
        "required_api_semantics": ["scene_tree_access"],
        "systems": ["Manager"],
        "confidence": 0.7,
        "source": _source("manual_rule", "pattern.global_manager"),
    },
    "dynamic_scene_creation": {
        "description": "PackedScene/resource reference followed by instantiation creates runtime scene flow.",
        "required_api_semantics": ["static_resource_reference", "dynamic_scene_creation"],
        "systems": ["Core", "Gameplay"],
        "confidence": 0.85,
        "source": _source("manual_rule", "pattern.dynamic_scene_creation"),
    },
}


def artifact(artifact_type: str, data: Any) -> dict[str, Any]:
    return {
        "artifact_type": artifact_type,
        "schema_version": SCHEMA_VERSION,
        "generator": GENERATOR,
        "godot_version": "4.x",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "data": data,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_foundation(output_dir: Path | str) -> None:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    write_json(output_path / "role_taxonomy.json", artifact("role_taxonomy", ROLE_TAXONOMY))
    write_json(output_path / "foundation_semantics.json", artifact("foundation_semantics", FOUNDATION_SEMANTICS))
    write_json(output_path / "api_semantics.json", artifact("api_semantics", API_SEMANTICS))
    write_json(output_path / "pattern_rules.json", artifact("pattern_rules", PATTERN_RULES))
    (output_path / "foundation_build_report.md").write_text(build_report(), encoding="utf-8")


def build_report() -> str:
    return "\n".join(
        [
            "# Foundation Build Report",
            "",
            f"- Generator: `{GENERATOR}`",
            f"- Schema version: `{SCHEMA_VERSION}`",
            "- Godot version target: `4.x`",
            f"- Class semantics: {len(FOUNDATION_SEMANTICS)}",
            f"- API semantics: {len(API_SEMANTICS)}",
            f"- Pattern rules: {len(PATTERN_RULES)}",
            "",
            "This MVP foundation is built from manual high-value Godot 4.x rules.",
            "Use official class-reference exports or project-specific patches as future inputs.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Godot Layer 0 semantic foundation artifacts.")
    parser.add_argument("--output", required=True, help="Directory where Layer 0 artifacts are written.")
    args = parser.parse_args()
    build_foundation(Path(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
