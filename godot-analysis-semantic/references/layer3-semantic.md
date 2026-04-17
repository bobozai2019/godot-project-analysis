# Layer 3 Semantic Reference

Layer 3 converts structural graph facts into semantic interpretation. It consumes Layer 0 and Layer 2 artifacts.

## Required Inputs

From `analysis/layer0/`:

- `foundation_semantics.json`
- `api_semantics.json`
- `pattern_rules.json`
- `role_taxonomy.json`

From `analysis/layer2/`:

- `graph.json`
- `graph_index.json`

## Output Contract

- Every high-confidence system must have members and evidence.
- Every pattern match must have evidence.
- Roles and systems should align with Layer 0 taxonomy.
- Upstream readiness must state unresolved graph edges and unannotated structural nodes.

## MVP System Signals

- UI: `ui_element`, `CanvasLayer`, `Control`, UI containers, labels, UI scripts
- Gameplay: `CharacterBody2D`, `Area2D`, input APIs, movement APIs, runtime spawning
- Data: resources and resource references
- Physics: collision, body, and trigger entities
- Presentation: sprites, animation, camera, audio, visual presentation nodes
- Manager/Core: scene tree access, orchestration APIs, event and runtime flow

## MVP Pattern Signals

- `player_controller_candidate`: movable actor script using input APIs
- `trigger_system_candidate`: Area-style trigger nodes or scripts
- `event_driven_ui`: UI script with signal/connect behavior
- `dynamic_scene_creation`: script using `instantiate` or `add_child`
- `global_manager`: autoload or shared manager-like entity
