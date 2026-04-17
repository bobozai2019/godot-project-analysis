import json
import tempfile
import unittest
from pathlib import Path

import build_foundation
import validate_foundation


class FoundationBuilderTests(unittest.TestCase):
    def test_default_build_writes_required_layer0_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            build_foundation.build_foundation(output_dir=output_dir)

            expected = {
                "foundation_semantics.json",
                "api_semantics.json",
                "pattern_rules.json",
                "role_taxonomy.json",
                "foundation_build_report.md",
            }
            self.assertEqual(expected, {path.name for path in output_dir.iterdir()})

            taxonomy = json.loads((output_dir / "role_taxonomy.json").read_text(encoding="utf-8"))
            semantics = json.loads((output_dir / "foundation_semantics.json").read_text(encoding="utf-8"))
            api = json.loads((output_dir / "api_semantics.json").read_text(encoding="utf-8"))

            self.assertEqual("role_taxonomy", taxonomy["artifact_type"])
            self.assertIn("Gameplay", taxonomy["data"]["systems"])
            self.assertEqual("gameplay_entity", semantics["data"]["CharacterBody2D"]["category"])
            self.assertEqual("scene_transition", api["data"]["change_scene_to_file"]["semantic"])

    def test_default_build_covers_common_3d_and_ui_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            build_foundation.build_foundation(output_dir=output_dir)

            semantics = json.loads((output_dir / "foundation_semantics.json").read_text(encoding="utf-8"))["data"]
            for class_name in [
                "CheckButton",
                "CollisionShape3D",
                "DirectionalLight3D",
                "FileDialog",
                "GPUParticles3D",
                "HSeparator",
                "HSlider",
                "MeshInstance3D",
                "PackedSceneInstance",
                "RichTextLabel",
                "SpinBox",
                "Sprite3D",
                "StaticBody3D",
                "SubViewport",
                "TextureButton",
                "VSeparator",
                "VSplitContainer",
            ]:
                self.assertIn(class_name, semantics)
                self.assertIn(semantics[class_name]["category"], {"ui_element", "presentation", "physics", "core_runtime"})

    def test_validator_rejects_unknown_semantic_category(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            build_foundation.build_foundation(output_dir=output_dir)

            semantics_path = output_dir / "foundation_semantics.json"
            semantics = json.loads(semantics_path.read_text(encoding="utf-8"))
            semantics["data"]["CharacterBody2D"]["category"] = "unknown_category"
            semantics_path.write_text(json.dumps(semantics, indent=2), encoding="utf-8")

            errors = validate_foundation.validate_artifacts(output_dir)

            self.assertTrue(any("unknown_category" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
