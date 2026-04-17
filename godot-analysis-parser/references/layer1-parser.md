# Layer 1 Parser Reference

Layer 1 extracts static project facts and writes replayable artifacts. It should not explain architecture.

## Input

- Godot project root containing `project.godot`
- Optional Layer 0 directory for class semantic labels

## Extraction Targets

- Project inventory: scenes, scripts, resources, autoloads, input actions, main scene
- Scene facts: `[ext_resource]`, `[node]`, script assignments, instanced PackedScenes, `[connection]`
- Script facts: `extends`, `class_name`, `signal`, `func`, high-value API usage, literal `res://` paths
- Dependency facts: scene instances, script attachments, resource references, autoload definitions, signal connect/emit evidence

## ID Rules

- Scene: `scene:res://scenes/main.tscn`
- Script: `script:res://scripts/player.gd`
- Node: `node:res://scenes/main.tscn::/Root/Child`
- Resource: `resource:res://assets/player_stats.tres`
- Signal pseudo-node: `signal:res://scripts/player.gd::emit`

## Evidence Rules

Every dependency should include:

```json
{
  "source_path": "res://scripts/player.gd",
  "line": 12,
  "raw": "health_changed.emit(current_health, stats.max_health)"
}
```

## Known MVP Limits

- No full GDScript AST.
- No precise cross-function data flow.
- Dynamic paths are extracted only when visible as string literals or scene ext resources.
- Addons are included unless downstream config filters them.
