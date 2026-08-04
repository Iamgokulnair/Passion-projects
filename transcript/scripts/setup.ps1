# One-time (idempotent) setup for the transcript skill on Windows.
#   .\setup.ps1          install everything installable
#   .\setup.ps1 -Check   report state only, change nothing
#
# Mirrors setup.sh's logic for the non-Apple-Silicon backend (faster-whisper instead
# of mlx-whisper). Diarization (pyannote/torch) is identical on every platform.
#
# If Windows blocks this script from running ("this file came from another computer"),
# it was downloaded as a ZIP rather than `git clone`d — run:
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

Head "transcript . setup ($(if ($Check) {'check'} else {'install'}))"

# ---------------------------------------------------------------- uv
# (Avoids the ?? null-coalescing operator -- Windows still ships PowerShell 5.1 by
# default, which doesn't have it; PowerShell 7 is an opt-in separate install.)
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
# faster-whisper is the non-Apple-Silicon ASR backend (CTranslate2, CPU by default;
# GPU needs a manual CUDA/cuDNN install -- out of scope for this script, see README).
# soundfile is pinned defensively: torchaudio's default backend differs on Windows.
$Pkgs = @("faster-whisper", "imageio-ffmpeg", "pyannote.audio>=3.1", "numpy<3", "soundfile")
if (-not $Check -and (Test-Path $Py)) {
    Head "installing packages (a few minutes on first run)"
    & $UvPath pip install --python $Py @Pkgs
    if ($LASTEXITCODE -ne 0) { exit 1 }
}

if (Test-Path $Py) {
    Head "dependencies"
    foreach ($mod in @("faster_whisper", "imageio_ffmpeg", "pyannote.audio", "torch", "soundfile")) {
        $v = & $Py -c "
import importlib,warnings;warnings.filterwarnings('ignore')
m=importlib.import_module('$mod');print(getattr(m,'__version__','present'))" 2>$null
        if ($v) { Ok "$mod $v" } else { NoGo "$mod" }
    }

    Head "ffmpeg"
    $Ff = & $Py -c "
import shutil
e=shutil.which('ffmpeg') or shutil.which('ffmpeg.exe')
if not e:
    try:
        import imageio_ffmpeg; e=imageio_ffmpeg.get_ffmpeg_exe()
    except Exception: e=''
print(e or '')" 2>$null
    if ($Ff) { Ok $Ff } else { NoGo "ffmpeg -- install failed" }

    Head "whisper model cache"
    Warn "model downloads on first run (~1.5GB, one time, cached under $env:USERPROFILE\.cache\huggingface after)"
}

# ---------------------------------------------------------------- HF token
Head "speaker diarization (optional)"
if ($env:HF_TOKEN -or $env:HUGGINGFACE_TOKEN) {
    Ok "HF_TOKEN set -- speaker labels enabled"
} else {
    Warn "HF_TOKEN not set -- transcripts still work, but WITHOUT speaker labels"
    Write-Host @"
       To enable (one time, free -- you must do these yourself):
         1. Create a HuggingFace account:  https://huggingface.co/join
         2. Accept the licence:
              https://huggingface.co/pyannote/speaker-diarization-community-1
         3. Make a READ token:  https://huggingface.co/settings/tokens
         4. Set it for this session AND persist it (both are needed --
            setx alone will not show up in the current window):
              `$env:HF_TOKEN = "hf_xxxxx"
              setx HF_TOKEN "hf_xxxxx"
"@
}

Head "next"
if ($Check) {
    Write-Host "  .\setup.ps1                                  # install anything marked MISS"
} else {
    Write-Host "  .venv\Scripts\python.exe scripts\transcribe.py <file>   # each run prints its own realtime factor"
}
Write-Host ""
