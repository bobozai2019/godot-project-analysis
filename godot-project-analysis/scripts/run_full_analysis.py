#!/usr/bin/env python3
"""Coordinate the Godot Layer 0-Layer 4 analysis pipeline."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


SKILL_NAMES = {
    "foundation": "godot-analysis-foundation",
    "parser": "godot-analysis-parser",
    "graph": "godot-analysis-graph",
    "semantic": "godot-analysis-semantic",
    "architecture": "godot-analysis-architecture",
}


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def skills_dir() -> Path:
    return skill_root().parent


def sibling_skill(name: str) -> Path:
    path = skills_dir() / name
    if not path.exists():
        raise FileNotFoundError(f"Required skill is missing: {path}")
    return path


def script_path(skill_name: str, script_name: str) -> Path:
    path = sibling_skill(skill_name) / "scripts" / script_name
    if not path.exists():
        raise FileNotFoundError(f"Required script is missing: {path}")
    return path


def slugify_project(project: Path) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", project.name.strip()).strip("_").lower()
    return slug or "godot_project"


def run_command(command: list[str], label: str) -> None:
    print(f"\n== {label} ==")
    print(" ".join(f'"{part}"' if " " in part else part for part in command))
    completed = subprocess.run(command)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def copy_default_layer0(output_dir: Path) -> bool:
    default_dir = sibling_skill(SKILL_NAMES["foundation"]) / "assets" / "default-layer0"
    if not default_dir.exists():
        return False
    output_dir.mkdir(parents=True, exist_ok=True)
    for source in default_dir.iterdir():
        if source.is_file():
            shutil.copy2(source, output_dir / source.name)
    return True


def default_profile_dir() -> Path | None:
    profile_dir = sibling_skill(SKILL_NAMES["architecture"]) / "assets" / "layer4_profiles"
    return profile_dir if profile_dir.exists() else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Godot Layer 0-Layer 4 analysis pipeline.")
    parser.add_argument("--project", required=True, help="Godot project root containing project.godot.")
    parser.add_argument("--output", help="Output directory. Defaults to analysis/<project_slug>.")
    parser.add_argument("--start-layer", type=int, choices=[0, 1, 2, 3, 4], default=0)
    parser.add_argument("--profile-dir", help="Optional Layer 4 profile directory.")
    parser.add_argument("--exclude-addons", action="store_true", help="Exclude res://addons during Layer 1 parsing.")
    parser.add_argument("--resource-mode", choices=["referenced", "all"], default="referenced")
    parser.add_argument("--rebuild-layer0", action="store_true", help="Build Layer 0 instead of copying bundled assets.")
    parser.add_argument("--skip-validation", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project = Path(args.project).resolve()
    if not project.exists():
        raise SystemExit(f"Project path does not exist: {project}")
    if not (project / "project.godot").exists():
        raise SystemExit(f"Not a Godot project root, missing project.godot: {project}")

    output = Path(args.output).resolve() if args.output else (Path.cwd() / "analysis" / slugify_project(project)).resolve()
    layer0 = output / "layer0"
    layer1 = output / "layer1"
    layer2 = output / "layer2"
    layer3 = output / "layer3"
    layer4 = output / "layer4"
    output.mkdir(parents=True, exist_ok=True)

    profile_dir = Path(args.profile_dir).resolve() if args.profile_dir else default_profile_dir()

    if args.start_layer <= 0:
        if args.rebuild_layer0 or not copy_default_layer0(layer0):
            run_command(
                [sys.executable, str(script_path(SKILL_NAMES["foundation"], "build_foundation.py")), "--output", str(layer0)],
                "Layer 0 foundation",
            )
        if not args.skip_validation:
            run_command(
                [sys.executable, str(script_path(SKILL_NAMES["foundation"], "validate_foundation.py")), "--input", str(layer0)],
                "Validate Layer 0",
            )

    if args.start_layer <= 1:
        command = [
            sys.executable,
            str(script_path(SKILL_NAMES["parser"], "parse_godot_project.py")),
            "--project",
            str(project),
            "--output",
            str(layer1),
            "--layer0",
            str(layer0),
            "--resource-mode",
            args.resource_mode,
        ]
        if args.exclude_addons:
            command.append("--exclude-addons")
        run_command(command, "Layer 1 parser")
        if not args.skip_validation:
            run_command(
                [sys.executable, str(script_path(SKILL_NAMES["parser"], "validate_layer1.py")), "--input", str(layer1)],
                "Validate Layer 1",
            )

    if args.start_layer <= 2:
        layer2.mkdir(parents=True, exist_ok=True)
        run_command(
            [
                sys.executable,
                str(script_path(SKILL_NAMES["graph"], "preflight_layer2.py")),
                "--layer0",
                str(layer0),
                "--layer1",
                str(layer1),
                "--output-json",
                str(layer2 / "input_readiness.json"),
                "--output-md",
                str(layer2 / "input_readiness_report.md"),
            ],
            "Layer 2 preflight",
        )
        run_command(
            [sys.executable, str(script_path(SKILL_NAMES["graph"], "build_graph.py")), "--layer1", str(layer1), "--output", str(layer2)],
            "Layer 2 graph",
        )
        if not args.skip_validation:
            run_command(
                [sys.executable, str(script_path(SKILL_NAMES["graph"], "validate_graph.py")), "--input", str(layer2)],
                "Validate Layer 2",
            )

    if args.start_layer <= 3:
        run_command(
            [
                sys.executable,
                str(script_path(SKILL_NAMES["semantic"], "analyze_semantics.py")),
                "--layer0",
                str(layer0),
                "--layer2",
                str(layer2),
                "--output",
                str(layer3),
            ],
            "Layer 3 semantic",
        )
        if not args.skip_validation:
            run_command(
                [
                    sys.executable,
                    str(script_path(SKILL_NAMES["semantic"], "validate_semantics.py")),
                    "--input",
                    str(layer3),
                    "--layer0",
                    str(layer0),
                ],
                "Validate Layer 3",
            )

    if args.start_layer <= 4:
        command = [
            sys.executable,
            str(script_path(SKILL_NAMES["architecture"], "recover_architecture.py")),
            "--layer2",
            str(layer2),
            "--layer3",
            str(layer3),
            "--output",
            str(layer4),
        ]
        if profile_dir:
            command.extend(["--profile-dir", str(profile_dir)])
        run_command(command, "Layer 4 architecture")
        if not args.skip_validation:
            run_command(
                [sys.executable, str(script_path(SKILL_NAMES["architecture"], "validate_architecture.py")), "--input", str(layer4)],
                "Validate Layer 4",
            )
            run_command(
                [
                    sys.executable,
                    str(script_path(SKILL_NAMES["architecture"], "quality_gate_architecture.py")),
                    "--layer3",
                    str(layer3),
                    "--layer4",
                    str(layer4),
                ],
                "Layer 4 quality gate",
            )

    print("\nGodot analysis complete.")
    print(f"Output: {output}")
    print(f"Report: {layer4 / 'architecture_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
