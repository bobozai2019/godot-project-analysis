# Layer 2 Graph Reference

Layer 2 normalizes Layer 1 facts into a graph. It is structural, not interpretive.

## Required Inputs

From `analysis/layer1/`:

- `project_inventory.json`
- `scene_parse.json`
- `script_parse.json`
- `dependency_extract.json`

Layer 0 is not required to build the graph, but semantic coverage should be checked before Layer 3 uses the graph.

## Graph Rules

- Every scene in Layer 1 becomes a `Scene` node.
- Every parsed scene node becomes a `Node` node.
- Every script becomes a `Script` node.
- Every script-declared signal becomes a `Signal` node.
- Dependency targets not present in Layer 1 become placeholder nodes and produce unresolved edges.
- Every edge should preserve Layer 1 evidence when available.

## Edge Mapping

- `attaches_script` -> `attaches`
- `instances_scene` -> `instantiates`
- `references_packed_scene`, `references_resource`, `references_resource_path`, `preloads`, `loads` -> `references`
- `connects_signal` -> `connects`
- `emits_signal` -> `emits`
- `transitions_to` -> `transitions_to`

## Upstream Readiness Checks

Layer 1 is ready when:

- Scene, node, and script IDs are stable.
- Dependencies include source, target, type, and evidence.
- Root scene and script artifacts validate.

Layer 0 is ready for downstream semantic analysis when:

- Common node types in Layer 1 have taxonomy entries.
- Missing semantics are either intentional or documented.
