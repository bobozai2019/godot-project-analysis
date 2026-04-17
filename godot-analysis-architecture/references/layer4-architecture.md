# Layer 4 Architecture Reference

Layer 4 turns Layer 2 graph structure and Layer 3 semantic interpretation into human-facing architecture recovery artifacts.

## Required Inputs

From `analysis/layer2/`:

- `graph.json`
- `graph_stats.json`

From `analysis/layer3/`:

- `semantic_annotations.json`
- `systems.json`
- `pattern_matches.json`
- `semantic_findings.json`

## Evidence Rules

- Findings must include evidence from systems, patterns, semantic findings, or graph edges.
- Risks must include an observed reason, even for low severity.
- Recommendations must cite the risk, pattern, or readiness state that caused them.
- If upstream readiness has recommendations, Layer 4 must surface them.

## MVP Report Sections

- 项目概览
- 系统划分
- 场景流程
- 架构模式判断
- 关键发现
- 风险
- 建议
- 上游流程状态
