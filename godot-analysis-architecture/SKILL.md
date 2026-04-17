---
name: godot-analysis-architecture
description: Build, inspect, or validate Layer 4 Godot architecture recovery artifacts from Layer 2 graph and Layer 3 semantic outputs. Use when the user asks to create architecture_report.md, architecture_summary.json, findings.json, risks.json, recommendations.json, summarize Godot systems and scene flow, or decide whether earlier Layer 0-Layer 3 outputs need adjustment before human architecture review.
---

# Godot Analysis Architecture

Use this skill for Layer 4 only: architecture recovery reporting from evidence already produced by Layer 2 and Layer 3.

## Quick Start

Build Layer 4 artifacts:

```powershell
python "$env:USERPROFILE\.codex\skills\godot-analysis-architecture\scripts\recover_architecture.py" --layer2 analysis\layer2 --layer3 analysis\layer3 --output analysis\layer4
```

Validate Layer 4 artifacts:

```powershell
python "$env:USERPROFILE\.codex\skills\godot-analysis-architecture\scripts\validate_architecture.py" --input analysis\layer4
```

## Workflow

1. Validate Layer 2 and Layer 3 first.
2. Aggregate system summaries, scene flow, pattern counts, findings, risks, and recommendations.
3. Ensure each finding, risk, and recommendation carries evidence.
4. Report whether earlier layers need adjustment before human review.
5. Do not invent facts that are not traceable to Layer 2 or Layer 3.

## Outputs

- `architecture_report.md`: human-readable Chinese architecture report.
- `architecture_summary.json`: structured overview, project identity, gameplay loop, module responsibilities, systems, scene flow, architecture patterns, readiness.
- `findings.json`: evidence-backed architecture findings.
- `risks.json`: evidence-backed risks.
- `recommendations.json`: evidence-backed recommendations.

## Scope Rules

This skill may:

- Summarize how the project is organized.
- Explain scene flow and system boundaries from evidence.
- Infer project identity, player loop, and module responsibilities when evidence supports the judgment.
- Identify architecture patterns, risks, and review recommendations.
- Flag upstream gaps in Layer 2 or Layer 3.

This skill must not:

- Re-run parser, graph, or semantic analysis unless explicitly requested.
- Add unsupported gameplay claims.
- Treat template text as evidence.
