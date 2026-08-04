# One-time (idempotent) setup for the html-to-ppt skill on Windows.
#   .\setup.ps1          install everything installable
#   .\setup.ps1 -Check   report state only, change nothing
#
# If Windows blocks this script from running ("this file came from another computer"),
# it was downloaded as a ZIP rather than `git clone`d -- run:
#   Unblock-File .\scripts\setup.ps1
# first, or use `git clone` instead of the GitHub "Download ZIP" button.

param([switch]$Check)

$ErrorActionPreference = "Stop"

$Skill = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Venv  = Join-Path $Skill ".venv"
$Py    = Join-Path $Venv "Scripts\python.exe"

function Ok($msg)   { Write-Host "  ok   $msg" -ForegroundColor Green }
function NoGo($msg) { Write-Host "  MISS $msg" -ForegroundColor Red }
function Warn($msg) { Write-Host "  warn $msg" -ForegroundColor Yellow }
function Head($msg) { Write-Host "`n$msg" -ForegroundColor White }

Head "html-to-ppt . setup ($(if ($Check) {'check'} else {'install'}))"

# ---------------------------------------------------------------- uv
$UvPath = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $UvPath) {
    $Candidate = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
    if (Test-Path $Candidate) { $UvPath = $Candidate }
}
if (-not $UvPath) {
    NoGo "uv not found -- install it first:"
    Write-Host '       powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'
    exit 1
}
Ok "uv $(& $UvPath --version 2>$null)"

# ---------------------------------------------------------------- venv
if (-not (Test-Path $Py)) {
    if ($Check) {
        NoGo "venv missing ($Venv) -- run .\setup.ps1"
    } else {
        Head "creating venv (python 3.12)"
        & $UvPath venv --python 3.12 $Venv
        if ($LASTEXITCODE -ne 0) { exit 1 }
    }
}
if (Test-Path $Py) { Ok "python $(& $Py -V 2>&1)  ($Venv)" }

# ---------------------------------------------------------------- packages
$Pkgs = @("python-pptx", "beautifulsoup4", "tinycss2", "Pillow", "playwright")
if (-not $Check -and (Test-Path $Py)) {
    Head "installing packages (a minute or two on first run)"
    & $UvPath pip install --python $Py @Pkgs
    if ($LASTEXITCODE -ne 0) { exit 1 }
}

if (Test-Path $Py) {
    Head "dependencies"
    foreach ($mod in @("pptx", "bs4", "tinycss2", "PIL", "playwright")) {
        $v = & $Py -c "
import importlib,warnings;warnings.filterwarnings('ignore')
m=importlib.import_module('$mod');print(getattr(m,'__version__','present'))" 2>$null
        if ($v) { Ok "$mod $v" } else { NoGo "$mod" }
    }

    Head "playwright chromium (computed-style extraction, gradient rasterization)"
    if (-not $Check) {
        & $Py -m playwright install chromium
        if ($LASTEXITCODE -ne 0) { Warn "chromium install failed -- parse_html.py will fall back to degraded bs4-only mode" }
    }
    $ChromiumCache = Join-Path $env:USERPROFILE "AppData\Local\ms-playwright"
    if (Test-Path $ChromiumCache) {
        Ok "chromium cache present ($ChromiumCache)"
    } else {
        Warn "chromium not cached -- downloads ~150-300MB on first install, one time"
    }
}

# ---------------------------------------------------------------- LibreOffice (optional, recommended)
Head "LibreOffice (optional, strongly recommended -- powers the visual Perceive Gate)"
$LoCandidates = @(
    "C:\Program Files\LibreOffice\program\soffice.exe",
    "C:\Program Files (x86)\LibreOffice\program\soffice.exe"
)
$LoPath = $null
$LoCmd = (Get-Command soffice -ErrorAction SilentlyContinue).Source
if ($LoCmd) { $LoPath = $LoCmd }
if (-not $LoPath) {
    foreach ($c in $LoCandidates) { if (Test-Path $c) { $LoPath = $c; break } }
}
if ($LoPath) {
    Ok $LoPath
} else {
    Warn "not found -- the pipeline still runs without it, but the Perceive Gate degrades to"
    Warn "geometry-only checks (no visual render, misses contrast/chart-integrity/gradient-legibility)"
    Write-Host "       To enable (one time, free): winget install TheDocumentFoundation.LibreOffice"
}

# ---------------------------------------------------------------- optional PowerPoint COM enhancement
Head "PowerPoint COM automation (optional, off by default)"
Write-Host "       Higher-fidelity render than LibreOffice IF PowerPoint is installed and licensed here."
Write-Host "       Not required -- LibreOffice above is the primary cross-platform path. To enable:"
Write-Host "         .venv\Scripts\python.exe -m pip install pywin32"

Head "next"
if ($Check) {
    Write-Host "  .\setup.ps1                                                       # install anything marked MISS"
} else {
    Write-Host "  .venv\Scripts\python.exe scripts\convert.py examples\sample.html   # end-to-end smoke test"
}
Write-Host ""
