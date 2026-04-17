---
name: godot-analysis-semantic
description: Build, inspect, or validate Layer 3 semantic analysis artifacts from Godot Layer 0 semantic foundation and Layer 2 graph outputs. Use when the user asks to create semantic_annotations.json, systems.json, pattern_matches.json, semantic_findings.json, semantic_report.md, identify UI/Gameplay/Manager/Data systems, match semantic patterns, or check whether Layer 0-Layer 2 are ready for architecture recovery.
---

# Godot Analysis Semantic

Use this skill for Layer 3 only: semantic interpretation of a normalized Godot graph. Layer 3 may identify systems and patterns, but final architecture reporting belongs to Layer 4.

## Quick Start

Build Layer 3 artifacts:

```powershell
python "$env:USERPROFILE\.codex\skills\godot-analysis-semantic\scripts\analyze_semantics.py" --layer0 analysis\layer0 --layer2 analysis\layer2 --output analysis\layer3
```

Validate Layer 3 artifacts:

```powershell
python "$env:USERPROFILE\.codex\skills\godot-analysis-semantic\scripts\validate_semantics.py" --input analysis\layer3 --layer0 analysis\layer0
```

## Workflow

1. Validate Layer 0 and Layer 2 before semantic analysis.
2. Build semantic annotations from class semantics, script API usage, graph relationships, and resource references.
3. Match high-value patterns such as player controller, trigger system, event-driven UI, dynamic scene creation, and global manager.
4. Cluster entities into systems such as UI, Gameplay, Data, Physics, Presentation, Manager, and Core.
5. Emit upstream readiness notes so earlier layers can be adjusted before Layer 4.

## Outputs

- `semantic_annotations.json`: semantic roles, systems, categories, confidence, and evidence for graph entities.
- `systems.json`: system clusters with members and evidence.
- `pattern_matches.json`: matched semantic patterns with evidence.
- `semantic_findings.json`: high-value findings and upstream readiness.
- `semantic_report.md`: compact human-readable semantic summary.

## Scope Rules

This skill may:

- Interpret Layer 2 graph structure using Layer 0 rules.
- Produce evidence-backed system membership and pattern matches.
- Report missing semantics or graph issues that reduce Layer 3 quality.

This skill must not:

- Rewrite Layer 0-Layer 2 artifacts unless explicitly asked.
- Produce final architecture recommendations or risk reports; that belongs to Layer 4.
- Present low-confidence guesses as facts.
