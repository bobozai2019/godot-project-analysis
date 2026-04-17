import json
import tempfile
import unittest
from pathlib import Path

import parse_godot_project
import validate_layer1


class ParseGodotProjectTests(unittest.TestCase):
    def test_parser_extracts_scene_script_and_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "scenes").mkdir()
            (project / "scripts").mkdir()
            (project / "addons" / "plugin").mkdir(parents=True)
            (project / "assets").mkdir()
            (project / "project.godot").write_text(
                '\n'.join([
                    'config_version=5',
                    '',
                    '[application]',
                    'run/main_scene="res://scenes/main.tscn"',
                    '',
                    '[autoload]',
                    'GameState="*res://scripts/game_state.gd"',
                ]),
                encoding="utf-8",
            )
            (project / "scenes" / "main.tscn").write_text(
                '\n'.join([
                    '[gd_scene load_steps=2 format=3]',
                    '[ext_resource type="Script" uid="uid://player" path="res://scripts/player.gd" id="1_player"]',
                    '[ext_resource type="Resource" path="res://assets/player_stats.tres" id="2_stats"]',
                    '',
                    '[node name="Main" type="Node2D" unique_id=1]',
                    '[node name="Player" type="CharacterBody2D" parent="." unique_id=2]',
                    'script = ExtResource("1_player")',
                    'stats = ExtResource("2_stats")',
                ]),
                encoding="utf-8",
            )
            (project / "scripts" / "player.gd").write_text(
                '\n'.join([
                    'extends CharacterBody2D',
                    'class_name PlayerController',
                    'signal health_changed(current: int)',
                    'func _physics_process(delta: float) -> void:',
                    '\tif Input.is_action_just_pressed("attack"):',
                    '\t\thealth_changed.emit(1)',
                ]),
                encoding="utf-8",
            )
            (project / "scripts" / "game_state.gd").write_text("extends Node\n", encoding="utf-8")
            (project / "assets" / "player_stats.tres").write_text("[gd_resource type=\"Resource\" format=3]\n", encoding="utf-8")
            (project / "assets" / "unused.tres").write_text("[gd_resource type=\"Resource\" format=3]\n", encoding="utf-8")
            (project / "addons" / "plugin" / "plugin.gd").write_text("extends Node\n", encoding="utf-8")

            output = project / "analysis" / "layer1"
            parse_godot_project.parse_project(project_root=project, output_dir=output, exclude_addons=True)

            inventory = json.loads((output / "project_inventory.json").read_text(encoding="utf-8"))["data"]
            scenes = json.loads((output / "scene_parse.json").read_text(encoding="utf-8"))["data"]
            scripts = json.loads((output / "script_parse.json").read_text(encoding="utf-8"))["data"]
            deps = json.loads((output / "dependency_extract.json").read_text(encoding="utf-8"))["data"]

            self.assertEqual("res://scenes/main.tscn", inventory["entry_scene"])
            self.assertIn("res://scripts/player.gd", inventory["scripts"])
            self.assertNotIn("res://addons/plugin/plugin.gd", inventory["scripts"])
            self.assertIn("res://assets/player_stats.tres", inventory["resources"])
            self.assertNotIn("res://assets/unused.tres", inventory["resources"])
            self.assertEqual("GameState", inventory["autoloads"][0]["name"])
            self.assertEqual("CharacterBody2D", scripts["res://scripts/player.gd"]["extends"])
            self.assertIn("Input.is_action_just_pressed", scripts["res://scripts/player.gd"]["api_usage"])
            self.assertEqual("gameplay_entity", scenes["res://scenes/main.tscn"]["nodes"][1]["semantic"].get("category"))
            self.assertTrue(any(dep["type"] == "attaches_script" for dep in deps["dependencies"]))

            errors = validate_layer1.validate_artifacts(output)
            self.assertEqual([], errors)

    def test_parser_keeps_duplicate_scene_paths_unique(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "models").mkdir()
            (project / "project.godot").write_text(
                '\n'.join([
                    'config_version=5',
                    '',
                    '[application]',
                    'run/main_scene="res://models/imported_model.tscn"',
                ]),
                encoding="utf-8",
            )
            (project / "models" / "imported_model.tscn").write_text(
                '\n'.join([
                    '[gd_scene load_steps=2 format=3]',
                    '[ext_resource type="PackedScene" path="res://models/imported_model.fbx" id="1_model"]',
                    '',
                    '[node name="ImportedModel" instance=ExtResource("1_model")]',
                    '',
                    '[node name="ImportedModel" parent="." index="0"]',
                ]),
                encoding="utf-8",
            )
            (project / "models" / "imported_model.fbx").write_text("", encoding="utf-8")

            output = project / "analysis" / "layer1"
            parse_godot_project.parse_project(project_root=project, output_dir=output, resource_mode="referenced")

            scenes = json.loads((output / "scene_parse.json").read_text(encoding="utf-8"))["data"]
            nodes = scenes["res://models/imported_model.tscn"]["nodes"]
            node_ids = [node["node_id"] for node in nodes]

            self.assertEqual(2, len(nodes))
            self.assertEqual(len(node_ids), len(set(node_ids)))
            self.assertEqual("PackedSceneInstance", nodes[1]["type"])
            self.assertEqual([], validate_layer1.validate_artifacts(output))

    def test_parser_ignores_resource_paths_inside_comments(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "scripts").mkdir()
            (project / "project.godot").write_text(
                '\n'.join([
                    'config_version=5',
                    '',
                    '[application]',
                    'run/main_scene="res://main.tscn"',
                ]),
                encoding="utf-8",
            )
            (project / "main.tscn").write_text('[gd_scene format=3]\n[node name="Main" type="Node"]\n', encoding="utf-8")
            (project / "scripts" / "menu.gd").write_text(
                '\n'.join([
                    'extends Node',
                    '# old scene was res://missing/old_menu.tscn',
                    'func go():',
                    '\tget_tree().change_scene_to_file("res://main.tscn")',
                ]),
                encoding="utf-8",
            )

            output = project / "analysis" / "layer1"
            parse_godot_project.parse_project(project_root=project, output_dir=output)

            scripts = json.loads((output / "script_parse.json").read_text(encoding="utf-8"))["data"]
            deps = json.loads((output / "dependency_extract.json").read_text(encoding="utf-8"))["data"]["dependencies"]
            self.assertNotIn("res://missing/old_menu.tscn", scripts["res://scripts/menu.gd"]["literal_resource_paths"])
            self.assertFalse(any(dep["target"] == "scene:res://missing/old_menu.tscn" for dep in deps))

    def test_parser_keeps_resource_paths_with_spaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "scripts").mkdir()
            (project / "assets" / "music").mkdir(parents=True)
            (project / "project.godot").write_text(
                '\n'.join([
                    'config_version=5',
                    '',
                    '[application]',
                    'run/main_scene="res://main.tscn"',
                ]),
                encoding="utf-8",
            )
            (project / "main.tscn").write_text('[gd_scene format=3]\n[node name="Main" type="Node"]\n', encoding="utf-8")
            (project / "scripts" / "jukebox.gd").write_text(
                '\n'.join([
                    'extends Node',
                    'const MUSIC = "res://assets/music/Apple Cider.mp3"',
                    'func play():',
                    '\tload("res://assets/music/Apple Cider.mp3")',
                ]),
                encoding="utf-8",
            )
            (project / "assets" / "music" / "Apple Cider.mp3").write_text("", encoding="utf-8")

            output = project / "analysis" / "layer1"
            parse_godot_project.parse_project(project_root=project, output_dir=output)

            scripts = json.loads((output / "script_parse.json").read_text(encoding="utf-8"))["data"]
            deps = json.loads((output / "dependency_extract.json").read_text(encoding="utf-8"))["data"]["dependencies"]

            self.assertIn("res://assets/music/Apple Cider.mp3", scripts["res://scripts/jukebox.gd"]["literal_resource_paths"])
            self.assertFalse(any(dep["target"] == "resource:res://assets/music/Apple" for dep in deps))
            self.assertTrue(any(dep["target"] == "resource:res://assets/music/Apple Cider.mp3" for dep in deps))


if __name__ == "__main__":
    unittest.main()
