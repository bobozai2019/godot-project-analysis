# Layer 0 Artifact Contracts

Layer 0 artifacts are JSON files with a shared envelope:

```json
{
  "artifact_type": "foundation_semantics",
  "schema_version": "0.1.0",
  "generator": "godot-analysis-foundation",
  "godot_version": "4.x",
  "generated_at": "2026-04-15T00:00:00+00:00",
  "data": {}
}
```

## Required Files

- `role_taxonomy.json`
- `foundation_semantics.json`
- `api_semantics.json`
- `pattern_rules.json`
- `foundation_build_report.md`

## Foundation Semantics Entry

```json
{
  "category": "gameplay_entity",
  "roles": ["movable_actor", "player_candidate"],
  "systems": ["Gameplay", "Physics"],
  "importance": "high",
  "confidence": 0.9,
  "source": {
    "kind": "manual_rule",
    "rule_id": "class.character_body_2d"
  }
}
```

Rules:

- `category` must exist in `role_taxonomy.data.categories`.
- Every role must exist in `role_taxonomy.data.roles`.
- Every system must exist in `role_taxonomy.data.systems`.
- `confidence` is numeric, from `0` to `1`.
- `source.kind` and `source.rule_id` are required.

## API Semantics Entry

```json
{
  "semantic": "scene_transition",
  "systems": ["Core", "Manager"],
  "confidence": 0.95,
  "source": {
    "kind": "manual_rule",
    "rule_id": "api.scene_transition"
  }
}
```

## Pattern Rule Entry

Pattern rules are consumed by later semantic layers. They should be evidence-friendly and avoid project-specific assumptions.

```json
{
  "description": "Movable character with input polling is likely a player controller.",
  "required_semantics": ["movable_actor"],
  "required_api_semantics": ["continuous_input_query"],
  "systems": ["Gameplay"],
  "confidence": 0.85,
  "source": {
    "kind": "manual_rule",
    "rule_id": "pattern.player_controller_candidate"
  }
}
```
