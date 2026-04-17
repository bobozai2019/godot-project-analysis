---
name: godot-project-analysis
description: Use when Codex needs to run or coordinate the full Godot project analysis pipeline, analyze a Godot project path, rerun selected Layer 0-Layer 4 stages, validate generated artifacts, or drive the installed Godot analysis skills from one user request.
---

# Godot Project Analysis

Use this as the user-facing entry point for the Godot analysis harness. It coordinates the five layer skills without duplicating their detailed rules.

## Quick Start

Run the full pipeline:

```powershell
python "$env:USERPROFILE\.codex\skills\godot-project-analysis\scripts\run_full_analysis.py" --project "D:\godot\project\my-game"
```

Run into a specific output directory:

```powershell
python "$env:USERPROFILE\.codex\skills\godot-project-analysis\scripts\run_full_analysis.py" --project "D:\godot\project\my-game" --output "analysis\my_game"
```

Rerun from Layer 4 using existing Layer 2 and Layer 3 artifacts:

```powershell
python "$env:USERPROFILE\.codex\skills\godot-project-analysis\scripts\run_full_analysis.py" --project "D:\godot\project\my-game" --output "analysis\my_game" --start-layer 4
```

## Workflow

1. Resolve the Godot project path and output directory.
2. Prepare Layer 0 foundation artifacts from the bundled foundation assets, or rebuild them when requested.
3. Run Layer 1 parser and validate parser artifacts.
4. Run Layer 2 preflight, graph build, and graph validation.
5. Run Layer 3 semantic analysis and validation.
6. Run Layer 4 architecture recovery with bundled profile assets when available.
7. Run Layer 4 validation and quality gate.
8. Report the generated artifact paths and any failed command.

## Layer Ownership

- Layer 0 foundation: `godot-analysis-foundation`
- Layer 1 parser: `godot-analysis-parser`
- Layer 2 graph: `godot-analysis-graph`
- Layer 3 semantic: `godot-analysis-semantic`
- Layer 4 architecture: `godot-analysis-architecture`

## Rules

- Keep Layer 1-Layer 3 domain-neutral. They may expose raw names, tokens, and facts, but must not decide game domains.
- Layer 4 is the only layer that may perform domain or genre inference.
- Prefer the bundled Layer 4 profile directory from `godot-analysis-architecture/assets/layer4_profiles`.
- Do not invent missing evidence; tell the user which upstream artifact needs attention.

## References

- For artifact paths and contracts, read `references/artifact-map.md`.
- For orchestration behavior and command options, read `references/pipeline-contract.md`.
