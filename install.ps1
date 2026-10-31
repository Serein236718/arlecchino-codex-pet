# Install Arlecchino pet skins into the Codex / ChatGPT desktop app.
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\install.ps1
#   powershell -ExecutionPolicy Bypass -File .\install.ps1 -Pet arlecchino-chibi

param(
    [string]$Pet = ""
)

$ErrorActionPreference = "Stop"

$root  = Split-Path -Parent $MyInvocation.MyCommand.Path
$srcDir = Join-Path $root "pets"
$destDir = Join-Path $HOME ".codex\pets"

if (-not (Test-Path $srcDir)) {
    throw "pets/ not found next to this script"
}

if (-not (Test-Path $destDir)) {
    New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    Write-Host "created $destDir"
}

if ($Pet -ne "") {
    $targets = @(Join-Path $srcDir $Pet)
    if (-not (Test-Path $targets[0])) {
        throw "unknown pet '$Pet'. available: $((Get-ChildItem $srcDir -Directory).Name -join ', ')"
    }
} else {
    $targets = @(Get-ChildItem $srcDir -Directory | ForEach-Object { $_.FullName })
}

foreach ($t in $targets) {
    $name = Split-Path -Leaf $t
    if (-not (Test-Path (Join-Path $t "pet.json"))) {
        Write-Warning "skip $name (no pet.json)"
        continue
    }
    if (-not (Test-Path (Join-Path $t "spritesheet.webp"))) {
        Write-Warning "skip $name (no spritesheet.webp)"
        continue
    }
    $dst = Join-Path $destDir $name
    if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
    Copy-Item -Recurse -Force $t $dst
    Write-Host "installed $name -> $dst"
}

Write-Host ""
Write-Host "Done. Fully quit the app (tray icon -> Quit, not just minimize) and relaunch."
Write-Host "Then open Settings -> Personalization -> Pets and pick the pet."
