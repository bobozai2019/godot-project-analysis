---
name: godot-analysis-graph
description: Build, inspect, or validate Layer 2 Godot relationship graph artifacts from Layer 1 parser outputs. Use when the user asks to create graph.json, graph_index.json, graph_stats.json, normalize Scene/Node/Script/Resource/Signal relationships, validate Layer 1 readiness for graph building, or prepare graph inputs for Layer 3 semantic analysis.
---

# Godot Analysis Graph

Use this skill for Layer 2 only: graph construction from Layer 1 static facts. Do not infer systems, risks, or architecture here.

## Quick Start

Build Layer 2 artifacts:

```powershell
python "$env:USERPROFILE\.codex\skills\godot-analysis-graph\scripts\build_graph.py" --layer1 analysis\layer1 --output analysis\layer2
```

Check whether Layer 0/Layer 1 are ready for Layer 2 and later Layer 3:

```powershell
python "$env:USERPROFILE\.codex\skills\godot-analysis-graph\scripts\preflight_layer2.py" --layer0 analysis\layer0 --layer1 analysis\layer1 --output-json analysis\layer2\input_readiness.json --output-md analysis\layer2\input_readiness_report.md
```

Validate Layer 2 artifacts:

```powershell
python "$env:USERPROFILE\.codex\skills\godot-analysis-graph\scripts\validate_graph.py" --input analysis\layer2
```

## Workflow

1. Validate Layer 1 before graph building.
2. Check Layer 0 semantic coverage when the graph will feed Layer 3.
3. Build `graph.json`, `graph_index.json`, `graph_stats.json`, and `graph_build_report.md`.
4. Treat `unresolved` edges as explicit graph facts, not silent failures.
5. Recommend upstream fixes when Layer 1 lacks stable IDs, evidence, or useful filtering.

## Outputs

- `graph.json`: normalized nodes and edges.
- `graph_index.json`: indexes by node kind, path, edge type, incoming, and outgoing edge.
- `graph_stats.json`: node/edge counts, kind/type distributions, unresolved count.
- `graph_build_report.md`: compact build summary.
- `input_readiness.json` / `input_readiness_report.md`: optional upstream readiness report.

## Node Kinds

Layer 2 may emit `Scene`, `Node`, `Script`, `Resource`, `Signal`, `Autoload`, `Project`, and `Unknown` nodes.

## Edge Types

Layer 2 normalizes Layer 1 dependency names into graph edge names such as `contains`, `attaches`, `instantiates`, `references`, `connects`, `emits`, `transitions_to`, and `defines_signal`.

## Scope Rules

This skill may:

- Build and validate a queryable relationship graph.
- Preserve evidence from Layer 1 dependencies.
- Mark missing endpoints with `unresolved`.
- Report whether Layer 0/Layer 1 need adjustment before Layer 3.

This skill must not:

- Interpret systems such as UI, Gameplay, or Manager.
- Hide unresolved relationships.
- Mutate Layer 0 or Layer 1 artifacts unless the user explicitly asks.
