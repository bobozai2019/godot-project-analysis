param(
  [string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" })
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$skillsDir = Join-Path $CodexHome "skills"
$skillNames = @(
  "godot-analysis-foundation",
  "godot-analysis-parser",
  "godot-analysis-graph",
  "godot-analysis-semantic",
  "godot-analysis-architecture",
  "godot-project-analysis"
)

New-Item -ItemType Directory -Force -Path $skillsDir | Out-Null

foreach ($skillName in $skillNames) {
  $source = Join-Path $repoRoot $skillName
  $target = Join-Path $skillsDir $skillName

  if (-not (Test-Path $source)) {
    throw "Missing skill directory: $source"
  }

  robocopy $source $target /E /XD __pycache__ /XF *.pyc | Out-Null
  if ($LASTEXITCODE -ge 8) {
    throw "Failed to install $skillName. robocopy exit code: $LASTEXITCODE"
  }
}

Write-Host ""
Write-Host "Installed Godot analysis skills to: $skillsDir"
Write-Host ""
Write-Host "Try:"
Write-Host '  Ask Codex: use godot-project-analysis to analyze D:\godot\project\your-game'
Write-Host ""
Write-Host "Or run directly:"
Write-Host '  python "$env:USERPROFILE\.codex\skills\godot-project-analysis\scripts\run_full_analysis.py" --project "D:\godot\project\your-game"'
