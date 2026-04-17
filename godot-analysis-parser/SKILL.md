---
name: godot-analysis-parser
description: Extract, inspect, or validate Layer 1 static facts from a Godot 4.x project. Use when the user asks to parse project.godot, .tscn scenes, .gd scripts, autoloads, scene-script attachments, resource references, signals, API usage, or to produce project_inventory.json, scene_parse.json, script_parse.json, dependency_extract.json, and parser_report.md for the Godot architecture recovery harness.
---

# Godot Analysis Parser

Use this skill for Layer 1 only: static fact extraction from a concrete Godot project. Keep architecture interpretation out of this layer.

## Quick Start

Extract Layer 1 artifacts:

```powershell
python "$env:USERPROFILE\.codex\skills\godot-analysis-parser\scripts\parse_godot_project.py" --project D:\path\to\godot-project --output analysis\layer1 --layer0 analysis\layer0 --exclude-addons --resource-mode referenced
```

Validate Layer 1 artifacts:

```powershell
python "$env:USERPROFILE\.codex\skills\godot-analysis-parser\scripts\validate_layer1.py" --input analysis\layer1
```

## Workflow

1. Ensure the target project contains `project.godot`.
2. Ensure Layer 0 exists if semantic labels are desired. Use `godot-analysis-foundation` default artifacts when needed.
3. Run `parse_godot_project.py` with `--project`, `--output`, and optionally `--layer0`.
4. Prefer `--exclude-addons` for game-focused analysis unless plugin architecture is the target.
5. Prefer `--resource-mode referenced` for compact downstream graphs; use `--resource-mode all` only for full asset inventory analysis.
6. Validate with `validate_layer1.py`.
7. Treat unresolved dynamic references as Layer 2 follow-up work, not Layer 1 failures.

## Outputs

Layer 1 writes:

- `project_inventory.json`: entry scene, scenes, scripts, resources, autoloads, input actions, counts.
- `scene_parse.json`: scene ext resources, nodes, node paths, attached scripts, instanced scenes, scene connections.
- `script_parse.json`: extends, class_name, signals, functions, API usage, literal resource paths, light Layer 0 semantic labels.
- `dependency_extract.json`: static dependencies with evidence.
- `parser_report.md`: compact extraction summary.

## Scope Rules

This skill may:

- Parse `.tscn`, `.gd`, `.tres`, `.res`, and `project.godot` static references.
- Use Layer 0 class semantics for light labels.
- Extract evidence-backed dependencies for Layer 2.

This skill must not:

- Infer systems, architecture, risk, or design intent.
- Perform full control-flow or data-flow analysis.
- Treat dynamic unresolved references as hard failures unless the user asks for strict mode.
