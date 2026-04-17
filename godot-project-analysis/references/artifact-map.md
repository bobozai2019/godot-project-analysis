# Godot Analysis Artifact Map

Default output layout:

```text
analysis/<project_slug>/
  layer0/
    foundation_semantics.json
    api_semantics.json
    pattern_rules.json
    role_taxonomy.json
    foundation_build_report.md
  layer1/
    project_inventory.json
    scene_parse.json
    script_parse.json
    dependency_extract.json
    parser_report.md
  layer2/
    input_readiness.json
    input_readiness_report.md
    graph.json
    graph_index.json
    graph_stats.json
    graph_build_report.md
  layer3/
    semantic_annotations.json
    systems.json
    pattern_matches.json
    semantic_findings.json
    semantic_report.md
  layer4/
    architecture_summary.json
    architecture_report.md
    findings.json
    risks.json
    recommendations.json
    profile_evaluation.json
    project_identity.json
    gameplay_loop.json
    module_responsibilities.json
```

Layer 4 v2 artifacts appear when a profile directory is available.
