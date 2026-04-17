# Layer 0 Foundation Reference

Layer 0 converts reusable Godot 4.x knowledge into machine-consumable semantic artifacts. It does not inspect a specific Godot project.

## Purpose

Layer 0 answers:

- What role does a Godot native class usually imply?
- What behavior does a Godot API call usually imply?
- What class/API combinations are useful semantic signals for later analysis?

## MVP Coverage

Class families:

- Core: `Object`, `Node`, `SceneTree`, `PackedScene`, `Resource`
- 2D gameplay and physics: `Node2D`, `CharacterBody2D`, `Area2D`, `RigidBody2D`, `StaticBody2D`, `CollisionShape2D`
- 3D basics: `Node3D`, `CharacterBody3D`, `Area3D`, `Camera3D`
- UI: `Control`, `CanvasLayer`, `Button`, `Label`, `Panel`, `TextureRect`, `ProgressBar`, `LineEdit`, `Container`
- UI containers: `PanelContainer`, `MarginContainer`, `VBoxContainer`, `HBoxContainer`, `GridContainer`, `ScrollContainer`
- Presentation and markers: `AnimationPlayer`, `AudioStreamPlayer`, `Camera2D`, `Sprite2D`, `AnimatedSprite2D`, `TileMap`, `Polygon2D`, `Marker2D`
- Runtime and data: `Timer`, `NavigationAgent2D`, `ConfigFile`, `JSON`

API families:

- Lifecycle: `_ready`, `_process`, `_physics_process`, `_input`, `_unhandled_input`
- Scene/runtime: `instantiate`, `queue_free`, `add_child`, `remove_child`, `change_scene_to_file`, `change_scene_to_packed`
- Signals: `signal`, `emit_signal`, `connect`, `disconnect`
- Groups: `add_to_group`, `get_nodes_in_group`, `call_group`
- Input: `Input.is_action_pressed`, `Input.is_action_just_pressed`
- Resources: `preload`, `load`, `ResourceLoader.load`
- Node lookup: `get_node`, `find_child`, `get_tree`

## Design Rules

- Prefer stable, coarse semantic categories over narrow one-off labels.
- Keep project-specific interpretations out of Layer 0.
- Add source and confidence to every class, API, and pattern entry.
- When a rule is uncertain, lower confidence instead of deleting useful signal.
- Validation must reject references to categories, roles, systems, or API semantics not defined in the taxonomy.

## Downstream Consumption

- Layer 1 may use Layer 0 for light labels while extracting facts.
- Layer 3 is the main consumer and should combine Layer 0 signals with graph evidence.
- Layer 4 should not read Layer 0 directly unless explaining the provenance of Layer 3 decisions.
