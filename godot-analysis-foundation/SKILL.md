---
name: godot-analysis-foundation
description: Build, inspect, or validate Layer 0 Godot 4.x semantic foundation artifacts for a multi-layer Godot architecture recovery harness. Use when the user asks for Godot class/API semantics, role taxonomy, pattern rules, or reusable foundation artifacts such as foundation_semantics.json, api_semantics.json, pattern_rules.json, role_taxonomy.json, or foundation_build_report.md.
---

# Godot Analysis Foundation

Use this skill for Layer 0 only: the reusable Godot semantic foundation. Do not analyze a concrete project here; project parsing belongs to later parser/graph/semantic layers.

## Quick Start

Use the bundled default foundation when a project only needs the standard Godot 4.x Layer 0 base:

```powershell
Copy-Item "$env:USERPROFILE\.codex\skills\godot-analysis-foundation\assets\default-layer0" -Destination analysis\layer0 -Recurse -Force
```

Build the MVP foundation artifacts:

```powershell
python "$env:USERPROFILE\.codex\skills\godot-analysis-foundation\scripts\build_foundation.py" --output analysis/layer0
```

Validate an existing Layer 0 artifact directory:

```powershell
python "$env:USERPROFILE\.codex\skills\godot-analysis-foundation\scripts\validate_foundation.py" --input analysis/layer0
```

## Workflow

1. Confirm the target Godot version. Default to `4.x` when the project does not specify one.
2. Prefer copying `assets/default-layer0/` into the project when the bundled MVP foundation is sufficient.
3. Rebuild `analysis/layer0/` only when changing the default rules or generating a project-specific variant.
4. Preserve the artifact contract described in `references/artifact-contracts.md`.
5. Use `references/layer0-foundation.md` before changing semantic coverage or rule meaning.
6. Run `validate_foundation.py` before claiming the foundation is usable downstream.

## Outputs

The Layer 0 directory must contain:

- `foundation_semantics.json`: Godot class to semantic category, roles, systems, confidence, and source.
- `api_semantics.json`: Godot API names to behavioral semantics and affected systems.
- `pattern_rules.json`: reusable rule fragments for later semantic analysis.
- `role_taxonomy.json`: allowed categories, roles, and systems.
- `foundation_build_report.md`: concise build summary and known scope.

The same files are bundled at `assets/default-layer0/` as the reusable default foundation.

## Scope Rules

This skill may:

- Create or refresh Layer 0 artifacts.
- Extend Godot class/API semantic coverage.
- Tighten taxonomy, confidence, source, and pattern-rule validation.
- Explain how Layer 0 should be consumed by Layer 1 or Layer 3.

This skill must not:

- Parse `.tscn`, `.gd`, `.tres`, or `project.godot` files from a real project.
- Produce graph, semantic-analysis, or architecture-report artifacts.
- Infer a specific game's architecture from project files.

## Implementation Notes

The current builder is intentionally manual-rule first. Treat official Godot class-reference dumps, project-specific patches, and generated summaries as future inputs, not as required for the MVP foundation.
