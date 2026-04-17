import json
import tempfile
import unittest
from pathlib import Path

import build_graph
import preflight_layer2
import validate_graph


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


class BuildGraphTests(unittest.TestCase):
    def test_graph_contains_normalized_entities_edges_and_indexes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layer1 = root / "layer1"
            layer2 = root / "layer2"
            layer1.mkdir()
            (layer1 / "project_inventory.json").write_text(
                json.dumps(
                    artifact(
                        "project_inventory",
                        {
                            "entry_scene": "res://scenes/main.tscn",
                            "autoloads": [],
                            "scenes": ["res://scenes/main.tscn"],
                            "scripts": ["res://scripts/player.gd"],
                            "resources": ["res://assets/player_stats.tres"],
                        },
                    )
                ),
                encoding="utf-8",
            )
            (layer1 / "scene_parse.json").write_text(
                json.dumps(
                    artifact(
                        "scene_parse",
                        {
                            "res://scenes/main.tscn": {
                                "scene_id": "scene:res://scenes/main.tscn",
                                "path": "res://scenes/main.tscn",
                                "nodes": [
                                    {
                                        "node_id": "node:res://scenes/main.tscn::/Main",
                                        "name": "Main",
                                        "path": "/Main",
                                        "type": "Node2D",
                                        "parent": None,
                                        "script": "script:res://scripts/player.gd",
                                        "instance": None,
                                        "semantic": {"category": "gameplay_entity"},
                                    }
                                ],
                                "connections": [],
                            }
                        },
                    )
                ),
                encoding="utf-8",
            )
            (layer1 / "script_parse.json").write_text(
                json.dumps(
                    artifact(
                        "script_parse",
                        {
                            "res://scripts/player.gd": {
                                "script_id": "script:res://scripts/player.gd",
                                "path": "res://scripts/player.gd",
                                "extends": "Node2D",
                                "signals": ["died"],
                                "functions": ["_ready"],
                                "api_usage": ["emit_signal"],
                                "semantic": {"category": "gameplay_entity"},
                            }
                        },
                    )
                ),
                encoding="utf-8",
            )
            (layer1 / "dependency_extract.json").write_text(
                json.dumps(
                    artifact(
                        "dependency_extract",
                        {
                            "dependencies": [
                                {
                                    "source": "node:res://scenes/main.tscn::/Main",
                                    "target": "script:res://scripts/player.gd",
                                    "type": "attaches_script",
                                    "evidence": {"source_path": "res://scenes/main.tscn", "line": 4, "raw": "script = ExtResource(...)"},
                                },
                                {
                                    "source": "script:res://scripts/player.gd",
                                    "target": "signal:res://scripts/player.gd::emit",
                                    "type": "emits_signal",
                                    "evidence": {"source_path": "res://scripts/player.gd", "line": 8, "raw": "died.emit()"},
                                },
                                {
                                    "source": "script:res://scripts/player.gd",
                                    "target": "scene:res://scenes/missing.tscn",
                                    "type": "transitions_to",
                                    "evidence": {"source_path": "res://scripts/player.gd", "line": 9, "raw": "change_scene_to_file(...)"},
                                },
                            ]
                        },
                    )
                ),
                encoding="utf-8",
            )

            build_graph.build_graph(layer1_dir=layer1, output_dir=layer2)

            graph = json.loads((layer2 / "graph.json").read_text(encoding="utf-8"))["data"]
            index = json.loads((layer2 / "graph_index.json").read_text(encoding="utf-8"))["data"]
            stats = json.loads((layer2 / "graph_stats.json").read_text(encoding="utf-8"))["data"]

            node_ids = {node["id"] for node in graph["nodes"]}
            edge_types = {edge["type"] for edge in graph["edges"]}
            self.assertIn("scene:res://scenes/main.tscn", node_ids)
            self.assertIn("node:res://scenes/main.tscn::/Main", node_ids)
            self.assertIn("script:res://scripts/player.gd", node_ids)
            self.assertIn("signal:res://scripts/player.gd::emit", node_ids)
            self.assertIn("contains", edge_types)
            self.assertIn("attaches", edge_types)
            self.assertIn("emits", edge_types)
            self.assertEqual(1, stats["unresolved_edges"])
            self.assertIn("Scene", index["nodes_by_kind"])

            self.assertEqual([], validate_graph.validate_artifacts(layer2))

    def test_preflight_reports_layer_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layer0 = root / "layer0"
            layer1 = root / "layer1"
            layer0.mkdir()
            layer1.mkdir()
            (layer0 / "foundation_semantics.json").write_text(
                json.dumps(artifact("foundation_semantics", {"Node2D": {"category": "gameplay_entity"}})),
                encoding="utf-8",
            )
            (layer1 / "scene_parse.json").write_text(
                json.dumps(
                    artifact(
                        "scene_parse",
                        {
                            "res://scenes/main.tscn": {
                                "nodes": [{"node_id": "node:res://scenes/main.tscn::/Main", "type": "Node2D"}]
                            }
                        },
                    )
                ),
                encoding="utf-8",
            )
            for name, kind, data in [
                ("project_inventory.json", "project_inventory", {"scenes": ["res://scenes/main.tscn"], "scripts": []}),
                ("script_parse.json", "script_parse", {}),
                ("dependency_extract.json", "dependency_extract", {"dependencies": []}),
            ]:
                (layer1 / name).write_text(json.dumps(artifact(kind, data)), encoding="utf-8")

            result = preflight_layer2.check_readiness(layer0, layer1)

            self.assertTrue(result["layer1_ready"])
            self.assertTrue(result["layer0_semantic_coverage_ready"])
            self.assertEqual({}, result["missing_layer0_semantics"])

    def test_graph_resolves_project_autoload_source_and_fbx_scene_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layer1 = root / "layer1"
            layer2 = root / "layer2"
            layer1.mkdir()
            for name, kind, data in [
                (
                    "project_inventory.json",
                    "project_inventory",
                    {
                        "entry_scene": "res://main.tscn",
                        "autoloads": [{"name": "InputManager", "path": "res://shared/input_manager.gd"}],
                        "scenes": ["res://main.tscn"],
                        "scripts": ["res://shared/input_manager.gd"],
                        "resources": [],
                    },
                ),
                (
                    "scene_parse.json",
                    "scene_parse",
                    {
                        "res://main.tscn": {
                            "scene_id": "scene:res://main.tscn",
                            "path": "res://main.tscn",
                            "nodes": [
                                {
                                    "node_id": "node:res://main.tscn::/Sword",
                                    "name": "Sword",
                                    "path": "/Sword",
                                    "type": "PackedSceneInstance",
                                    "parent": None,
                                    "script": None,
                                    "instance": "res://models/sword.fbx",
                                    "semantic": {},
                                }
                            ],
                            "connections": [],
                        }
                    },
                ),
                (
                    "script_parse.json",
                    "script_parse",
                    {
                        "res://shared/input_manager.gd": {
                            "script_id": "script:res://shared/input_manager.gd",
                            "path": "res://shared/input_manager.gd",
                            "extends": "Node",
                            "signals": [],
                            "functions": ["_input"],
                            "api_usage": ["emit_signal"],
                            "semantic": {},
                        }
                    },
                ),
                (
                    "dependency_extract.json",
                    "dependency_extract",
                    {
                        "dependencies": [
                            {
                                "source": "project:project.godot",
                                "target": "script:res://shared/input_manager.gd",
                                "type": "defines_autoload",
                                "evidence": {"source_path": "res://project.godot", "line": None, "raw": "InputManager"},
                            },
                            {
                                "source": "node:res://main.tscn::/Sword",
                                "target": "scene:res://models/sword.fbx",
                                "type": "instances_scene",
                                "evidence": {"source_path": "res://main.tscn", "line": 4, "raw": "instance=ExtResource(...)"},
                            },
                        ]
                    },
                ),
            ]:
                (layer1 / name).write_text(json.dumps(artifact(kind, data)), encoding="utf-8")

            build_graph.build_graph(layer1_dir=layer1, output_dir=layer2)

            graph = json.loads((layer2 / "graph.json").read_text(encoding="utf-8"))["data"]
            stats = json.loads((layer2 / "graph_stats.json").read_text(encoding="utf-8"))["data"]
            nodes = {node["id"]: node for node in graph["nodes"]}

            self.assertIn("project:project.godot", nodes)
            self.assertIn("scene:res://models/sword.fbx", nodes)
            self.assertFalse(nodes["project:project.godot"]["properties"].get("placeholder"))
            self.assertFalse(nodes["scene:res://models/sword.fbx"]["properties"].get("placeholder"))
            self.assertEqual(0, stats["unresolved_edges"])

    def test_scene_attached_csharp_script_is_registered_without_script_parse_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layer1 = root / "layer1"
            layer2 = root / "layer2"
            layer1.mkdir()
            for name, kind, data in [
                (
                    "project_inventory.json",
                    "project_inventory",
                    {
                        "entry_scene": "res://main.tscn",
                        "autoloads": [],
                        "scenes": ["res://main.tscn"],
                        "scripts": [],
                        "resources": [],
                    },
                ),
                (
                    "scene_parse.json",
                    "scene_parse",
                    {
                        "res://main.tscn": {
                            "scene_id": "scene:res://main.tscn",
                            "path": "res://main.tscn",
                            "nodes": [
                                {
                                    "node_id": "node:res://main.tscn::/Main",
                                    "name": "Main",
                                    "path": "/Main",
                                    "type": "Node",
                                    "parent": None,
                                    "script": "script:res://src/Main.cs",
                                    "instance": None,
                                    "semantic": {},
                                }
                            ],
                            "connections": [],
                        }
                    },
                ),
                ("script_parse.json", "script_parse", {}),
                (
                    "dependency_extract.json",
                    "dependency_extract",
                    {
                        "dependencies": [
                            {
                                "source": "node:res://main.tscn::/Main",
                                "target": "script:res://src/Main.cs",
                                "type": "attaches_script",
                                "evidence": {"source_path": "res://main.tscn", "line": 5, "raw": "script = ExtResource(...)"},
                            }
                        ]
                    },
                ),
            ]:
                (layer1 / name).write_text(json.dumps(artifact(kind, data)), encoding="utf-8")

            build_graph.build_graph(layer1_dir=layer1, output_dir=layer2)

            graph = json.loads((layer2 / "graph.json").read_text(encoding="utf-8"))["data"]
            stats = json.loads((layer2 / "graph_stats.json").read_text(encoding="utf-8"))["data"]
            nodes = {node["id"]: node for node in graph["nodes"]}

            self.assertIn("script:res://src/Main.cs", nodes)
            self.assertFalse(nodes["script:res://src/Main.cs"]["properties"].get("placeholder"))
            self.assertEqual("res://src/Main.cs", nodes["script:res://src/Main.cs"]["properties"].get("path"))
            self.assertEqual(0, stats["unresolved_edges"])

    def test_autoload_scene_targets_and_derived_parent_nodes_are_resolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layer1 = root / "layer1"
            layer2 = root / "layer2"
            layer1.mkdir()
            for name, kind, data in [
                (
                    "project_inventory.json",
                    "project_inventory",
                    {
                        "entry_scene": "res://main.tscn",
                        "autoloads": [{"name": "SceneService", "path": "res://services/service.tscn"}],
                        "scenes": ["res://main.tscn", "res://services/service.tscn"],
                        "scripts": [],
                        "resources": [],
                    },
                ),
                (
                    "scene_parse.json",
                    "scene_parse",
                    {
                        "res://main.tscn": {
                            "scene_id": "scene:res://main.tscn",
                            "path": "res://main.tscn",
                            "nodes": [
                                {
                                    "node_id": "node:res://main.tscn::/InheritedParent/Child",
                                    "name": "Child",
                                    "path": "/InheritedParent/Child",
                                    "type": "Label",
                                    "parent": "node:res://main.tscn::/InheritedParent",
                                    "script": None,
                                    "instance": None,
                                    "semantic": {},
                                }
                            ],
                            "connections": [],
                        },
                        "res://services/service.tscn": {
                            "scene_id": "scene:res://services/service.tscn",
                            "path": "res://services/service.tscn",
                            "nodes": [],
                            "connections": [],
                        },
                    },
                ),
                ("script_parse.json", "script_parse", {}),
                (
                    "dependency_extract.json",
                    "dependency_extract",
                    {
                        "dependencies": [
                            {
                                "source": "project:project.godot",
                                "target": "script:res://services/service.tscn",
                                "type": "defines_autoload",
                                "evidence": {"source_path": "res://project.godot", "line": None, "raw": "SceneService"},
                            }
                        ]
                    },
                ),
            ]:
                (layer1 / name).write_text(json.dumps(artifact(kind, data)), encoding="utf-8")

            build_graph.build_graph(layer1_dir=layer1, output_dir=layer2)

            graph = json.loads((layer2 / "graph.json").read_text(encoding="utf-8"))["data"]
            stats = json.loads((layer2 / "graph_stats.json").read_text(encoding="utf-8"))["data"]
            nodes = {node["id"]: node for node in graph["nodes"]}
            edge_ids = {edge["id"] for edge in graph["edges"]}

            self.assertIn("scene:res://services/service.tscn", nodes)
            self.assertNotIn("script:res://services/service.tscn", nodes)
            self.assertIn("node:res://main.tscn::/InheritedParent", nodes)
            self.assertFalse(nodes["node:res://main.tscn::/InheritedParent"]["properties"].get("placeholder"))
            self.assertIn(
                "autoload:SceneService -> references -> scene:res://services/service.tscn",
                edge_ids,
            )
            self.assertIn(
                "project:project.godot -> defines_autoload -> scene:res://services/service.tscn",
                edge_ids,
            )
            self.assertEqual(0, stats["unresolved_edges"])

    def test_autoload_script_declared_in_project_is_known_when_script_parse_excludes_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layer1 = root / "layer1"
            layer2 = root / "layer2"
            layer1.mkdir()
            for name, kind, data in [
                (
                    "project_inventory.json",
                    "project_inventory",
                    {
                        "entry_scene": "res://main.tscn",
                        "autoloads": [{"name": "AddonService", "path": "res://addons/tool/addon_service.gd"}],
                        "scenes": ["res://main.tscn"],
                        "scripts": [],
                        "resources": [],
                    },
                ),
                (
                    "scene_parse.json",
                    "scene_parse",
                    {"res://main.tscn": {"scene_id": "scene:res://main.tscn", "path": "res://main.tscn", "nodes": [], "connections": []}},
                ),
                ("script_parse.json", "script_parse", {}),
                (
                    "dependency_extract.json",
                    "dependency_extract",
                    {
                        "dependencies": [
                            {
                                "source": "project:project.godot",
                                "target": "script:res://addons/tool/addon_service.gd",
                                "type": "defines_autoload",
                                "evidence": {"source_path": "res://project.godot", "line": None, "raw": "AddonService"},
                            }
                        ]
                    },
                ),
            ]:
                (layer1 / name).write_text(json.dumps(artifact(kind, data)), encoding="utf-8")

            build_graph.build_graph(layer1_dir=layer1, output_dir=layer2)

            graph = json.loads((layer2 / "graph.json").read_text(encoding="utf-8"))["data"]
            stats = json.loads((layer2 / "graph_stats.json").read_text(encoding="utf-8"))["data"]
            nodes = {node["id"]: node for node in graph["nodes"]}

            self.assertIn("script:res://addons/tool/addon_service.gd", nodes)
            self.assertFalse(nodes["script:res://addons/tool/addon_service.gd"]["properties"].get("placeholder"))
            self.assertTrue(nodes["script:res://addons/tool/addon_service.gd"]["properties"].get("declared_autoload"))
            self.assertEqual(0, stats["unresolved_edges"])


if __name__ == "__main__":
    unittest.main()
