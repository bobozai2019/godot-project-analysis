# Godot Analysis Pipeline Contract

The orchestrator script is intentionally thin: each layer script remains the source of truth for that layer.

## Inputs

- `--project`: Godot project directory containing `project.godot`.
- `--output`: optional output directory. Defaults to `analysis/<project_slug>`.
- `--start-layer`: optional first layer to run, `0` through `4`.
- `--profile-dir`: optional Layer 4 profile directory. Defaults to the architecture skill bundled assets.
- `--exclude-addons`: pass through to Layer 1 parser.
- `--resource-mode`: `referenced` or `all`, passed through to Layer 1 parser.

## Behavior

- Layer 0 uses bundled default artifacts when available.
- `--rebuild-layer0` forces Layer 0 generation through the foundation builder.
- Validation runs after each layer unless `--skip-validation` is passed.
- A failed command stops the pipeline and returns a non-zero exit code.

## Common Reruns

- Full pipeline: `--start-layer 0`
- Reparse project after source changes: `--start-layer 1`
- Rebuild graph after parser improvements: `--start-layer 2`
- Recompute semantics after Layer 3 changes: `--start-layer 3`
- Rebuild reports/profile inference only: `--start-layer 4`
