import json
import tempfile
import unittest
from pathlib import Path

import recover_architecture
import validate_architecture


class Layer4ProfileTests(unittest.TestCase):
    def test_validate_profile_v2_accepts_current_contract(self):
        profile = {
            "schema_version": "layer4_profile.v2",
            "profile_id": "rpg",
            "profile_layer": "primary",
            "display_name": "RPG",
            "identity_rules": {
                "rpg": {
                    "threshold": 0.5,
                    "summary": "RPG profile",
                    "secondary_types": [],
                    "feature_weights": {"has_inventory": 0.5},
                }
            },
            "feature_rules": {
                "has_inventory": {
                    "positive_terms": ["inventory"],
                    "node_kinds": ["Script"],
                }
            },
            "negative_weights": {},
            "gameplay_loop_templates": {"rpg": ["管理库存"]},
            "module_rules": {"rpg": []},
            "compatible_with": ["story"],
            "suppresses": [],
        }

        recover_architecture.validate_profile_shape(profile)

    def test_validate_profile_v2_rejects_bad_layer(self):
        profile = {
            "profile_id": "bad",
            "profile_layer": "unknown",
            "identity_rules": {},
            "feature_rules": {},
        }

        with self.assertRaises(ValueError):
            recover_architecture.validate_profile_shape(profile)

    def test_load_profiles_reads_json_files_from_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "zeta.json").write_text(
                json.dumps({"profile_id": "zeta", "profile_layer": "primary", "identity_rules": {"zeta": {"feature_weights": {}}}, "feature_rules": {}}),
                encoding="utf-8",
            )
            (root / "alpha.json").write_text(
                json.dumps({"profile_id": "alpha", "profile_layer": "primary", "identity_rules": {"alpha": {"feature_weights": {}}}, "feature_rules": {}}),
                encoding="utf-8",
            )

            profiles = recover_architecture.load_profiles(profile_dir=root)

            self.assertEqual(["alpha", "zeta"], [profile["profile_id"] for profile in profiles])

    def test_validate_architecture_checks_v2_artifacts_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in validate_architecture.REQUIRED_FILES:
                (root / name).write_text("flowchart TD\n" if name.endswith(".mmd") else "{}", encoding="utf-8")
            (root / "architecture_summary.json").write_text(
                json.dumps({
                    "artifact_type": "architecture_summary",
                    "schema_version": "0.1.0",
                    "generator": "test",
                    "godot_version": "4.x",
                    "project_root": "tmp",
                    "generated_at": "2026-04-17T00:00:00+00:00",
                    "data": {
                        "project_overview": {"entry_scene": "res://main.tscn"},
                        "systems": [{"id": "system:ui"}],
                        "project_features": {"observed": {"x": True}},
                        "project_identity": {"primary_type": "x", "confidence": 0.8, "summary": "x", "evidence": [{"x": 1}]},
                        "gameplay_loop": [{"step": 1, "title": "x", "evidence": [{"x": 1}]}],
                        "module_responsibilities": [{"module": "x", "responsibility": "x", "evidence": [{"x": 1}]}],
                        "runtime_narrative": [{"id": "a", "evidence": [{"x": 1}]}, {"id": "b", "evidence": [{"x": 1}]}, {"id": "c", "evidence": [{"x": 1}]}],
                        "core_combat_logic": [{"id": "x", "text": "x", "evidence": [{"x": 1}]}],
                        "player_control_model": {"actions": [{"id": "x", "text": "x", "evidence": [{"x": 1}]}]},
                        "key_dependencies": [{"id": "x", "evidence": [{"x": 1}]}],
                        "architecture_patterns": {},
                        "upstream_readiness": {},
                        "scene_flow_abstraction": {"mermaid": "flowchart TD\n  A[\"A\"]\n  B[\"B\"]\n  A --> B\n"},
                        "module_map": {"mermaid": "flowchart TD\n  A[\"A\"]\n  B[\"B\"]\n  A --> B\n"},
                    },
                }),
                encoding="utf-8",
            )
            for name, kind, key in [
                ("findings.json", "findings", "findings"),
                ("risks.json", "risks", "risks"),
                ("recommendations.json", "recommendations", "recommendations"),
            ]:
                (root / name).write_text(
                    json.dumps({
                        "artifact_type": kind,
                        "schema_version": "0.1.0",
                        "generator": "test",
                        "godot_version": "4.x",
                        "project_root": "tmp",
                        "generated_at": "2026-04-17T00:00:00+00:00",
                        "data": {key: [{"id": "x", "title": "x", "evidence": [{"x": 1}]}]},
                    }),
                    encoding="utf-8",
                )
            (root / "architecture_report.md").write_text("项目概览 项目身份判断 玩家主循环 玩家控制方式 核心玩法逻辑 场景流程 模块关系图 核心模块职责 项目如何工作 系统划分 关键依赖关系 架构模式判断 风险 建议", encoding="utf-8")
            (root / "profile_evaluation.json").write_text(json.dumps({"data": {"evaluations": []}}), encoding="utf-8")

            errors = validate_architecture.validate_artifacts(root)

            self.assertIn("profile_evaluation.json contains no evaluations", errors)


if __name__ == "__main__":
    unittest.main()
