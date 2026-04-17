import json
import tempfile
import unittest
from pathlib import Path

import analyze_semantics
import validate_semantics


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


class SemanticAnalyzerTests(unittest.TestCase):
    def test_domain_words_alone_do_not_drive_system_classification(self):
        node = {
            "id": "script:res://src/cards/CombatEnemyDeck.cs",
            "kind": "Script",
            "properties": {
                "path": "res://src/cards/CombatEnemyDeck.cs",
                "extends": "",
                "class_name": "",
                "functions": [],
            },
        }

        semantics = analyze_semantics.infer_fallback_semantics(node)

        self.assertEqual(["Core"], semantics["systems"])
        self.assertNotIn("UI", semantics["systems"])
        self.assertNotIn("Gameplay", semantics["systems"])

    def test_control_node_still_classifies_as_ui(self):
        node = {
            "id": "node:res://scenes/main.tscn::/Panel",
            "kind": "Node",
            "properties": {
                "path": "/Panel",
                "node_type": "Button",
            },
        }

        semantics = analyze_semantics.infer_fallback_semantics(node)

        self.assertIn("UI", semantics["systems"])
        self.assertIn("ui_element", semantics["categories"])

    def test_physics_node_still_classifies_as_gameplay(self):
        node = {
            "id": "node:res://scenes/main.tscn::/Actor",
            "kind": "Node",
            "properties": {
                "path": "/Actor",
                "node_type": "CharacterBody2D",
            },
        }

        semantics = analyze_semantics.infer_fallback_semantics(node)

        self.assertIn("Gameplay", semantics["systems"])

    def test_semantic_analyzer_identifies_systems_and_patterns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layer0 = root / "layer0"
            layer2 = root / "layer2"
            layer3 = root / "layer3"
            layer0.mkdir()
            layer2.mkdir()
            foundation = {
                "CharacterBody2D": {
                    "category": "gameplay_entity",
                    "roles": ["movable_actor", "player_candidate"],
                    "systems": ["Gameplay", "Physics"],
                    "confidence": 0.9,
                    "source": {"kind": "manual_rule", "rule_id": "class.character_body_2d"},
                },
                "CanvasLayer": {
                    "category": "ui_element",
                    "roles": ["ui_layer"],
                    "systems": ["UI"],
                    "confidence": 0.95,
                    "source": {"kind": "manual_rule", "rule_id": "class.canvas_layer"},
                },
                "Resource": {
                    "category": "data_resource",
                    "roles": ["data_container"],
                    "systems": ["Data"],
                    "confidence": 0.9,
                    "source": {"kind": "manual_rule", "rule_id": "class.resource"},
                },
            }
            taxonomy = {
                "categories": {"gameplay_entity": "", "ui_element": "", "data_resource": ""},
                "roles": ["movable_actor", "player_candidate", "ui_layer", "ui_control", "data_container", "scene_instance", "global_service", "shape_visual"],
                "systems": ["Gameplay", "Physics", "UI", "Data", "Manager", "Presentation", "Core"],
            }
            api = {
                "Input.is_action_just_pressed": {"semantic": "discrete_input_query", "systems": ["Gameplay"], "confidence": 0.9},
                "emit_signal": {"semantic": "event_emission", "systems": ["Core"], "confidence": 0.9},
                "connect": {"semantic": "event_subscription", "systems": ["Core"], "confidence": 0.9},
            }
            pattern_rules = {
                "player_controller_candidate": {"systems": ["Gameplay"], "confidence": 0.85},
                "event_driven_ui": {"systems": ["UI"], "confidence": 0.75},
            }
            for name, kind, data in [
                ("foundation_semantics.json", "foundation_semantics", foundation),
                ("role_taxonomy.json", "role_taxonomy", taxonomy),
                ("api_semantics.json", "api_semantics", api),
                ("pattern_rules.json", "pattern_rules", pattern_rules),
            ]:
                (layer0 / name).write_text(json.dumps(artifact(kind, data)), encoding="utf-8")

            graph = {
                "metadata": {"entry_scene": "res://main.tscn"},
                "nodes": [
                    {"id": "node:player", "kind": "Node", "properties": {"node_type": "CharacterBody2D", "semantic": foundation["CharacterBody2D"]}},
                    {
                        "id": "script:player",
                        "kind": "Script",
                        "properties": {
                            "extends": "CharacterBody2D",
                            "api_usage": ["Input.is_action_just_pressed", "emit_signal"],
                            "signals": ["health_changed"],
                            "semantic": foundation["CharacterBody2D"],
                        },
                    },
                    {"id": "node:hud", "kind": "Node", "properties": {"node_type": "CanvasLayer", "semantic": foundation["CanvasLayer"]}},
                    {"id": "node:hud_instance", "kind": "Node", "properties": {"node_type": "PackedSceneInstance", "instance": "res://hud.tscn"}},
                    {"id": "scene:res://hud.tscn", "kind": "Scene", "properties": {"path": "res://hud.tscn"}},
                    {"id": "script:hud", "kind": "Script", "properties": {"extends": "CanvasLayer", "api_usage": ["connect"], "semantic": foundation["CanvasLayer"]}},
                    {"id": "resource:stats", "kind": "Resource", "properties": {"path": "res://stats.tres"}},
                    {"id": "node:imported_weapon", "kind": "Node", "properties": {"node_type": "Unknown", "scene": "scene:res://shared/resources/weapons/sword.tscn", "path": "/Sword"}},
                    {"id": "script:command", "kind": "Script", "properties": {"path": "res://shared/scripts/commands/command.gd", "class_name": "Command", "extends": "RefCounted"}},
                    {"id": "script:style", "kind": "Script", "properties": {"path": "res://game_core/game_ui/style/CapsuleStyleBox.gd", "class_name": "CapsuleStyleBox", "extends": "StyleBox"}},
                    {"id": "script:utils", "kind": "Script", "properties": {"path": "res://shared/scripts/utills/CircularLinkedList.gd", "class_name": "CircularLinkedList"}},
                ],
                "edges": [
                    {"id": "e1", "source": "node:player", "target": "script:player", "type": "attaches", "properties": {}},
                    {"id": "e2", "source": "node:hud", "target": "script:hud", "type": "attaches", "properties": {}},
                    {"id": "e2b", "source": "node:hud_instance", "target": "scene:res://hud.tscn", "type": "instantiates", "properties": {}},
                    {"id": "e2c", "source": "scene:res://hud.tscn", "target": "node:hud", "type": "contains", "properties": {}},
                    {"id": "e3", "source": "script:hud", "target": "script:player", "type": "connects", "properties": {"evidence_list": [{"raw": "connect"}]}},
                    {"id": "e4", "source": "node:player", "target": "resource:stats", "type": "references", "properties": {"evidence_list": [{"raw": "stats"}]}},
                ],
            }
            (layer2 / "graph.json").write_text(json.dumps(artifact("graph", graph)), encoding="utf-8")
            (layer2 / "graph_index.json").write_text(json.dumps(artifact("graph_index", {})), encoding="utf-8")

            analyze_semantics.analyze(layer0_dir=layer0, layer2_dir=layer2, output_dir=layer3)

            annotations = json.loads((layer3 / "semantic_annotations.json").read_text(encoding="utf-8"))["data"]
            systems = json.loads((layer3 / "systems.json").read_text(encoding="utf-8"))["data"]["systems"]
            patterns = json.loads((layer3 / "pattern_matches.json").read_text(encoding="utf-8"))["data"]["pattern_matches"]

            self.assertIn("Gameplay", annotations["script:player"]["systems"])
            self.assertNotIn("UI", annotations["script:player"]["systems"])
            self.assertIn("UI", annotations["node:hud_instance"]["systems"])
            self.assertEqual(["scene_instance"], annotations["node:hud_instance"]["semantic_roles"])
            self.assertIn("ui_layer", annotations["node:hud_instance"]["contained_roles"])
            self.assertIn("Presentation", annotations["node:imported_weapon"]["systems"])
            self.assertIn("Core", annotations["script:command"]["systems"])
            self.assertIn("UI", annotations["script:style"]["systems"])
            self.assertIn("Core", annotations["script:utils"]["systems"])
            self.assertTrue(any(system["kind"] == "UI" for system in systems))
            self.assertTrue(any(system["kind"] == "Data" for system in systems))
            self.assertTrue(any(match["pattern_id"] == "player_controller_candidate" for match in patterns))
            self.assertTrue(any(match["pattern_id"] == "event_driven_ui" for match in patterns))
            self.assertEqual([], validate_semantics.validate_artifacts(layer3, layer0))

    def test_semantic_analyzer_applies_layer0_by_node_type_and_script_extends(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layer0 = root / "layer0"
            layer2 = root / "layer2"
            layer3 = root / "layer3"
            layer0.mkdir()
            layer2.mkdir()
            foundation = {
                "CPUParticles2D": {
                    "category": "presentation",
                    "roles": ["animation_driver"],
                    "systems": ["Animation", "Presentation"],
                    "confidence": 0.85,
                    "source": {"kind": "manual_rule", "rule_id": "class.cpu_particles_2d"},
                },
                "Control": {
                    "category": "ui_element",
                    "roles": ["ui_control"],
                    "systems": ["UI"],
                    "confidence": 0.9,
                    "source": {"kind": "manual_rule", "rule_id": "class.control"},
                },
            }
            taxonomy = {
                "categories": {"presentation": "", "ui_element": ""},
                "roles": ["animation_driver", "ui_control"],
                "systems": ["Animation", "Presentation", "UI"],
            }
            for name, kind, data in [
                ("foundation_semantics.json", "foundation_semantics", foundation),
                ("role_taxonomy.json", "role_taxonomy", taxonomy),
                ("api_semantics.json", "api_semantics", {}),
                ("pattern_rules.json", "pattern_rules", {}),
            ]:
                (layer0 / name).write_text(json.dumps(artifact(kind, data)), encoding="utf-8")

            graph = {
                "metadata": {"entry_scene": "res://main.tscn"},
                "nodes": [
                    {"id": "node:vfx", "kind": "Node", "properties": {"node_type": "CPUParticles2D"}},
                    {"id": "script:ui", "kind": "Script", "properties": {"path": "res://src/UI.cs", "extends": "Control"}},
                ],
                "edges": [],
            }
            (layer2 / "graph.json").write_text(json.dumps(artifact("graph", graph)), encoding="utf-8")
            (layer2 / "graph_index.json").write_text(json.dumps(artifact("graph_index", {})), encoding="utf-8")

            analyze_semantics.analyze(layer0_dir=layer0, layer2_dir=layer2, output_dir=layer3)

            annotations = json.loads((layer3 / "semantic_annotations.json").read_text(encoding="utf-8"))["data"]
            self.assertIn("Presentation", annotations["node:vfx"]["systems"])
            self.assertIn("animation_driver", annotations["node:vfx"]["semantic_roles"])
            self.assertIn("UI", annotations["script:ui"]["systems"])
            self.assertIn("ui_control", annotations["script:ui"]["semantic_roles"])

    def test_semantic_analyzer_fallback_annotates_csharp_and_unknown_scene_nodes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layer0 = root / "layer0"
            layer2 = root / "layer2"
            layer3 = root / "layer3"
            layer0.mkdir()
            layer2.mkdir()
            taxonomy = {
                "categories": {"core_runtime": "", "ui_element": ""},
                "roles": ["global_service", "ui_control"],
                "systems": ["Core", "UI"],
            }
            for name, kind, data in [
                ("foundation_semantics.json", "foundation_semantics", {}),
                ("role_taxonomy.json", "role_taxonomy", taxonomy),
                ("api_semantics.json", "api_semantics", {}),
                ("pattern_rules.json", "pattern_rules", {}),
            ]:
                (layer0 / name).write_text(json.dumps(artifact(kind, data)), encoding="utf-8")

            graph = {
                "metadata": {"entry_scene": "res://main.tscn"},
                "nodes": [
                    {"id": "script:res://src/Core/Combat/NCombat.cs", "kind": "Script", "properties": {"path": "res://src/Core/Combat/NCombat.cs"}},
                    {"id": "node:res://ui.tscn::/ButtonContainer", "kind": "Node", "properties": {"node_type": "Unknown", "path": "/ButtonContainer"}},
                    {"id": "node:res://ui.tscn::/ButtonContainer/Frame", "kind": "Node", "properties": {"path": "/ButtonContainer/Frame"}},
                ],
                "edges": [],
            }
            (layer2 / "graph.json").write_text(json.dumps(artifact("graph", graph)), encoding="utf-8")
            (layer2 / "graph_index.json").write_text(json.dumps(artifact("graph_index", {})), encoding="utf-8")

            analyze_semantics.analyze(layer0_dir=layer0, layer2_dir=layer2, output_dir=layer3)

            annotations = json.loads((layer3 / "semantic_annotations.json").read_text(encoding="utf-8"))["data"]
            self.assertIn("Core", annotations["script:res://src/Core/Combat/NCombat.cs"]["systems"])
            self.assertNotIn("Gameplay", annotations["script:res://src/Core/Combat/NCombat.cs"]["systems"])
            self.assertIn("UI", annotations["node:res://ui.tscn::/ButtonContainer"]["systems"])
            self.assertIn("UI", annotations["node:res://ui.tscn::/ButtonContainer/Frame"]["systems"])


if __name__ == "__main__":
    unittest.main()
