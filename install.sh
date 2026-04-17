#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODEX_HOME="${CODEX_HOME:-"$HOME/.codex"}"
SKILLS_DIR="$CODEX_HOME/skills"

skills=(
  "godot-analysis-foundation"
  "godot-analysis-parser"
  "godot-analysis-graph"
  "godot-analysis-semantic"
  "godot-analysis-architecture"
  "godot-project-analysis"
)

mkdir -p "$SKILLS_DIR"

for skill in "${skills[@]}"; do
  source="$SCRIPT_DIR/$skill"
  target="$SKILLS_DIR/$skill"
  if [[ ! -d "$source" ]]; then
    echo "Missing skill directory: $source" >&2
    exit 1
  fi
  mkdir -p "$target"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete --exclude '__pycache__/' --exclude '*.pyc' "$source/" "$target/"
  else
    rm -rf "$target"
    cp -R "$source" "$target"
    find "$target" -type d -name '__pycache__' -prune -exec rm -rf {} +
    find "$target" -type f -name '*.pyc' -delete
  fi
done

echo
echo "Installed Godot analysis skills to: $SKILLS_DIR"
echo
echo "Try:"
echo '  Ask Codex: use godot-project-analysis to analyze /path/to/your-game'
