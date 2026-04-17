import json
import tempfile
import unittest
from pathlib import Path

import recover_architecture
import validate_architecture


def artifact(kind, data):
    return {
        "artifact_type": kind,
        "schema_version": "0.1.0",
        "generator": "test",
        "godot_version": "4.x",
        "project_root": "tmp",
        "generated_at": "2026-04-15T00:00:00+00:00",
        "data": data,
    }


def write_layer_inputs(root: Path, graph: dict, stats: dict | None = None):
    layer2 = root / "layer2"
    layer3 = root / "layer3"
    layer2.mkdir()
    layer3.mkdir()
    stats = stats or {
        "nodes": len(graph.get("nodes", [])),
        "edges": len(graph.get("edges", [])),
        "scenes": 1,
        "scripts": 1,
        "resources": 0,
        "signals": 0,
        "unresolved_edges": 0,
    }
    systems = {
        "systems": [
            {"id": "system:ui", "kind": "UI", "members": ["node:alpha_panel"], "confidence": 0.8, "evidence": [{"raw": "alpha"}]},
            {"id": "system:gameplay", "kind": "Gameplay", "members": ["script:alpha"], "confidence": 0.75, "evidence": [{"raw": "alpha"}]},
        ]
    }
    patterns = {
        "pattern_matches": [
            {"id": "pattern:ui", "pattern_id": "event_driven_ui", "entity_id": "script:alpha", "confidence": 0.76, "evidence": ["connect"]}
        ]
    }
    semantic_findings = {
        "findings": [{"id": "finding:ui", "title": "UI system detected", "kind": "UI", "confidence": 0.8, "evidence": ["node:alpha_panel"]}],
        "upstream_readiness": {"layer2_graph_ready": True, "unresolved_edges": 0, "unannotated_structural_nodes": 0, "recommendations": []},
    }
    annotations = {
        "node:alpha_panel": {"systems": ["UI"], "semantic_roles": ["ui_layer"], "confidence": 0.8, "evidence": [{"raw": "alpha"}]},
        "script:alpha": {"systems": ["Gameplay"], "semantic_roles": ["runtime"], "confidence": 0.75, "evidence": [{"raw": "alpha"}]},
    }
    (layer2 / "graph.json").write_text(json.dumps(artifact("graph", graph)), encoding="utf-8")
    (layer2 / "graph_stats.json").write_text(json.dumps(artifact("graph_stats", stats)), encoding="utf-8")
    for name, kind, data in [
        ("systems.json", "systems", systems),
        ("pattern_matches.json", "pattern_matches", patterns),
        ("semantic_findings.json", "semantic_findings", semantic_findings),
        ("semantic_annotations.json", "semantic_annotations", annotations),
    ]:
        (layer3 / name).write_text(json.dumps(artifact(kind, data)), encoding="utf-8")
    return layer2, layer3


def alpha_graph():
    return {
        "metadata": {"entry_scene": "res://alpha/main.tscn"},
        "nodes": [
            {"id": "scene:res://alpha/main.tscn", "kind": "Scene", "properties": {"path": "res://alpha/main.tscn", "is_entry": True}},
            {"id": "node:alpha_panel", "kind": "Node", "properties": {"path": "/AlphaPanel", "name": "AlphaPanel"}},
            {"id": "node:alpha_noise", "kind": "Node", "properties": {"path": "/AlphaNoise", "name": "AlphaNoise"}},
            {"id": "script:alpha", "kind": "Script", "properties": {"path": "res://alpha/alpha_driver.gd", "functions": ["run_alpha"], "api_usage": ["connect"]}},
        ],
        "edges": [
            {"id": "edge:entry-alpha", "source": "scene:res://alpha/main.tscn", "target": "node:alpha_panel", "type": "contains", "properties": {"evidence_list": [{"raw": "alpha panel"}]}},
            {"id": "edge:alpha-script", "source": "node:alpha_panel", "target": "script:alpha", "type": "attaches", "properties": {"evidence_list": [{"raw": "script"}]}},
        ],
    }


def alpha_profile(path: Path):
    profile = {
        "profile_id": "alpha_profile",
        "identity_rules": {
            "alpha_project": {
                "threshold": 0.5,
                "summary": "外部 profile 识别出的 Alpha 项目。",
                "secondary_types": ["alpha_loop"],
            }
        },
        "feature_rules": {
            "has_alpha_panel": {
                "positive_terms": ["alpha"],
                "required_context": ["panel"],
                "negative_context": ["noise"],
                "node_kinds": ["Node", "Script", "Scene"],
                "weights": {"alpha_project": 0.6},
                "max_evidence": 4,
            }
        },
        "gameplay_loop_templates": {
            "alpha_project": [
                {
                    "title": "执行 Alpha 决策",
                    "player_action": "玩家触发 Alpha 面板中的主要选择。",
                    "system_response": "Alpha 运行层接收选择并推进状态。",
                    "evidence_features": ["has_alpha_panel"],
                }
            ]
        },
        "player_control_templates": {
            "alpha_project": {
                "ui_controls": [
                    {
                        "title": "Alpha UI 控制入口",
                        "text": "Alpha 面板承担主要操作入口。",
                        "evidence_features": ["has_alpha_panel"],
                    }
                ]
            }
        },
        "core_gameplay_logic_templates": {
            "alpha_project": [
                {
                    "title": "Alpha 核心运行链路",
                    "text": "Alpha 面板和 Alpha 脚本共同构成核心运行链路。",
                    "evidence_features": ["has_alpha_panel"],
                }
            ]
        },
        "module_rules": {
            "alpha_project": [
                {
                    "module": "Alpha Runtime",
                    "responsibility": "承载 Alpha 外部 profile 定义的运行职责",
                    "system": "Gameplay/UI",
                    "terms": ["alpha"],
                    "exclude_terms": ["noise"],
                }
            ]
        },
        "scene_flow_rules": {
            "alpha_project": [
                {"source": "Entry", "target": "AlphaPanel", "label": "opens"},
                {"source": "AlphaPanel", "target": "AlphaRuntime", "label": "drives"}
            ]
        },
        "module_map_rules": {
            "alpha_project": [
                {"source": "Alpha Runtime", "target": "UI", "label": "updates"}
            ]
        },
        "forbidden_report_terms": ["forbidden_alpha_term"]
    }
    path.write_text(json.dumps(profile), encoding="utf-8")
    return path


def profile_dir(root: Path):
    profiles = root / "profiles"
    profiles.mkdir()
    alpha_profile(profiles / "alpha.json")
    beta = {
        "profile_id": "beta",
        "profile_layer": "modifier",
        "display_name": "Beta",
        "identity_rules": {
            "beta": {
                "threshold": 0.4,
                "summary": "Beta modifier",
                "secondary_types": ["beta_layer"],
                "feature_weights": {"has_alpha_panel": 1.0},
            }
        },
        "feature_rules": {
            "has_alpha_panel": {
                "positive_terms": ["alpha"],
                "required_context": ["panel"],
                "node_kinds": ["Node", "Script", "Scene"],
            }
        },
        "negative_weights": {},
        "gameplay_loop_templates": {"beta": ["处理 Beta 修饰步骤"]},
        "module_rules": {"beta": []},
        "compatible_with": ["alpha_profile"],
        "suppresses": [],
    }
    (profiles / "beta.json").write_text(json.dumps(beta), encoding="utf-8")
    return profiles


class ArchitectureRecoveryTests(unittest.TestCase):
    def test_evaluate_profile_uses_v2_feature_weights(self):
        graph = {
            "nodes": [
                {"id": "script:res://src/inventory.gd", "kind": "Script", "properties": {"path": "res://src/inventory.gd"}},
                {"id": "script:res://src/stats.gd", "kind": "Script", "properties": {"path": "res://src/stats.gd"}},
            ],
            "edges": [],
        }
        profile = {
            "profile_id": "rpg",
            "profile_layer": "primary",
            "identity_rules": {
                "rpg": {
                    "threshold": 0.5,
                    "feature_weights": {"has_inventory": 0.5, "has_stats": 0.5},
                }
            },
            "feature_rules": {
                "has_inventory": {"positive_terms": ["inventory"], "node_kinds": ["Script"]},
                "has_stats": {"positive_terms": ["stats"], "node_kinds": ["Script"]},
            },
            "negative_weights": {},
        }

        result = recover_architecture.evaluate_profile(graph, profile)

        self.assertEqual("rpg", result["profile_id"])
        self.assertEqual(1.0, result["normalized_score"])
        self.assertEqual(["has_inventory", "has_stats"], [item["feature"] for item in result["matched_features"]])

    def test_evaluate_profile_applies_negative_weights_from_matching_features(self):
        graph = {
            "nodes": [
                {"id": "script:res://src/card.gd", "kind": "Script", "properties": {"path": "res://src/card.gd"}},
                {"id": "script:res://src/inventory.gd", "kind": "Script", "properties": {"path": "res://src/inventory.gd"}},
            ],
            "edges": [],
        }
        profile = {
            "profile_id": "rpg",
            "profile_layer": "primary",
            "identity_rules": {
                "rpg": {
                    "threshold": 0.5,
                    "feature_weights": {"has_inventory": 1.0},
                }
            },
            "feature_rules": {
                "has_inventory": {"positive_terms": ["inventory"], "node_kinds": ["Script"]},
                "has_card_loop": {"positive_terms": ["card"], "node_kinds": ["Script"]},
            },
            "negative_weights": {"has_card_loop": -0.25},
        }

        result = recover_architecture.evaluate_profile(graph, profile)

        self.assertEqual(0.75, result["raw_score"])
        self.assertEqual("has_card_loop", result["negative_matches"][0]["feature"])

    def test_evaluate_profile_disqualifies_missing_required_features(self):
        graph = {
            "nodes": [
                {"id": "script:res://src/grid.gd", "kind": "Script", "properties": {"path": "res://src/grid.gd"}},
            ],
            "edges": [],
        }
        profile = {
            "profile_id": "tactical",
            "profile_layer": "primary",
            "identity_rules": {
                "tactical": {
                    "threshold": 0.5,
                    "feature_weights": {"has_grid": 0.5, "has_command": 0.5},
                    "required_features": ["has_command"],
                }
            },
            "feature_rules": {
                "has_grid": {"positive_terms": ["grid"], "node_kinds": ["Script"]},
                "has_command": {"positive_terms": ["command"], "node_kinds": ["Script"]},
            },
            "negative_weights": {},
        }

        result = recover_architecture.evaluate_profile(graph, profile)

        self.assertTrue(result["disqualified"])
        self.assertEqual(0.0, result["normalized_score"])

    def test_select_project_identity_returns_primary_modifier_and_flavor(self):
        profiles = [
            {"profile_id": "rpg", "compatible_with": ["survival", "story"], "suppresses": []},
            {"profile_id": "survival", "compatible_with": ["rpg"], "suppresses": []},
            {"profile_id": "story", "compatible_with": ["rpg"], "suppresses": []},
        ]
        evaluations = [
            {"profile_id": "rpg", "profile_layer": "primary", "normalized_score": 0.8, "confidence": 0.75, "threshold": 0.5, "summary": "RPG", "secondary_types": []},
            {"profile_id": "survival", "profile_layer": "modifier", "normalized_score": 0.55, "confidence": 0.52, "threshold": 0.45, "summary": "Survival", "secondary_types": []},
            {"profile_id": "story", "profile_layer": "flavor", "normalized_score": 0.5, "confidence": 0.48, "threshold": 0.4, "summary": "Story", "secondary_types": []},
        ]

        identity = recover_architecture.select_project_identity(evaluations, profiles)

        self.assertEqual("rpg", identity["primary"]["genre"])
        self.assertEqual(["survival"], [item["genre"] for item in identity["modifiers"]])
        self.assertEqual(["story"], [item["genre"] for item in identity["flavors"]])

    def test_select_project_identity_outputs_candidates_for_close_primary_scores(self):
        profiles = [
            {"profile_id": "rpg", "compatible_with": [], "suppresses": []},
            {"profile_id": "card", "compatible_with": [], "suppresses": []},
        ]
        evaluations = [
            {"profile_id": "rpg", "profile_layer": "primary", "normalized_score": 0.81, "confidence": 0.75, "threshold": 0.5, "summary": "RPG", "secondary_types": []},
            {"profile_id": "card", "profile_layer": "primary", "normalized_score": 0.76, "confidence": 0.72, "threshold": 0.5, "summary": "Card", "secondary_types": []},
        ]

        identity = recover_architecture.select_project_identity(evaluations, profiles)

        self.assertEqual(["rpg", "card"], [item["genre"] for item in identity["primary_candidates"]])

    def test_recovery_without_profile_does_not_infer_specific_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layer2, layer3 = write_layer_inputs(root, alpha_graph())
            layer4 = root / "layer4"

            recover_architecture.recover(layer2_dir=layer2, layer3_dir=layer3, output_dir=layer4)

            summary = json.loads((layer4 / "architecture_summary.json").read_text(encoding="utf-8"))["data"]
            report = (layer4 / "architecture_report.md").read_text(encoding="utf-8")
            self.assertEqual("unknown", summary["project_identity"]["primary_type"])
            self.assertEqual({}, summary["project_features"]["observed"])
            self.assertNotIn("alpha_project", report)
            self.assertEqual([], validate_architecture.validate_artifacts(layer4))

    def test_recovery_uses_external_profile_for_identity_and_narrative(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layer2, layer3 = write_layer_inputs(root, alpha_graph())
            profile_path = alpha_profile(root / "alpha_profile.json")
            layer4 = root / "layer4"

            recover_architecture.recover(layer2_dir=layer2, layer3_dir=layer3, output_dir=layer4, profile_path=profile_path)

            summary = json.loads((layer4 / "architecture_summary.json").read_text(encoding="utf-8"))["data"]
            report = (layer4 / "architecture_report.md").read_text(encoding="utf-8")
            scene_flow = (layer4 / "scene_flow.mmd").read_text(encoding="utf-8")
            module_map = (layer4 / "module_map.mmd").read_text(encoding="utf-8")
            self.assertEqual("alpha_project", summary["project_identity"]["primary_type"])
            self.assertTrue(summary["project_features"]["observed"]["has_alpha_panel"])
            self.assertTrue(summary["project_identity"]["score_breakdown"]["alpha_project"] >= 0.5)
            self.assertEqual(["AlphaPanel"], [item["path"].strip("/") for item in summary["project_features"]["evidence"]["has_alpha_panel"]])
            self.assertIn("执行 Alpha 决策", [item["title"] for item in summary["gameplay_loop"]])
            self.assertEqual("Alpha Runtime", summary["module_responsibilities"][0]["module"])
            self.assertTrue(summary["scene_flow_abstraction"]["mermaid"].startswith("flowchart TD"))
            self.assertTrue(scene_flow.startswith("flowchart TD"))
            self.assertTrue(module_map.startswith("flowchart TD"))
            self.assertIn("```mermaid", report)
            self.assertEqual([], validate_architecture.validate_artifacts(layer4))

    def test_profile_forbidden_terms_create_report_quality_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            graph = alpha_graph()
            graph["nodes"].append({"id": "node:forbidden", "kind": "Node", "properties": {"path": "/forbidden_alpha_term", "name": "forbidden_alpha_term"}})
            layer2, layer3 = write_layer_inputs(root, graph)
            profile_path = alpha_profile(root / "alpha_profile.json")
            layer4 = root / "layer4"

            recover_architecture.recover(layer2_dir=layer2, layer3_dir=layer3, output_dir=layer4, profile_path=profile_path)

            summary = json.loads((layer4 / "architecture_summary.json").read_text(encoding="utf-8"))["data"]
            self.assertIn("forbidden_alpha_term", " ".join(summary["report_quality"]["evidence_noise_warnings"]))

    def test_recovery_with_profile_dir_writes_v2_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layer2, layer3 = write_layer_inputs(root, alpha_graph())
            profiles = profile_dir(root)
            layer4 = root / "layer4"

            recover_architecture.recover(layer2_dir=layer2, layer3_dir=layer3, output_dir=layer4, profile_dir=profiles)

            summary = json.loads((layer4 / "architecture_summary.json").read_text(encoding="utf-8"))["data"]
            evaluation = json.loads((layer4 / "profile_evaluation.json").read_text(encoding="utf-8"))["data"]
            identity = json.loads((layer4 / "project_identity.json").read_text(encoding="utf-8"))["data"]
            report = (layer4 / "architecture_report.md").read_text(encoding="utf-8")
            self.assertEqual(2, len(evaluation["evaluations"]))
            self.assertEqual("alpha_project", summary["project_identity"]["primary_type"])
            self.assertEqual("alpha_project", summary["project_identity_v2"]["primary"]["genre"])
            self.assertEqual(["beta"], [item["genre"] for item in identity["modifiers"]])
            self.assertIn("处理 Beta 修饰步骤", [item["title"] for item in summary["gameplay_loop"]])
            self.assertIn("主类型", report)
            self.assertIn("修饰类型", report)
            self.assertTrue((layer4 / "gameplay_loop.json").exists())
            self.assertTrue((layer4 / "module_responsibilities.json").exists())
            self.assertEqual([], validate_architecture.validate_artifacts(layer4))


if __name__ == "__main__":
    unittest.main()
