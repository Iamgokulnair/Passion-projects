#!/usr/bin/env bash
# One-time (idempotent) setup for the transcript skill.
#   ./setup.sh          install everything installable
#   ./setup.sh --check   report state only, change nothing
set -uo pipefail

SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$SKILL/.venv"
PY="$VENV/bin/python"
UV="${UV:-$HOME/.local/bin/uv}"
CHECK=0
[[ "${1:-}" == "--check" ]] && CHECK=1

ok(){ printf '  \033[32mok\033[0m   %s\n' "$1"; }
no(){ printf '  \033[31mMISS\033[0m %s\n' "$1"; }
wa(){ printf '  \033[33mwarn\033[0m %s\n' "$1"; }
hd(){ printf '\n\033[1m%s\033[0m\n' "$1"; }

hd "transcript · setup ($([[ $CHECK == 1 ]] && echo check || echo install))"

# ---------------------------------------------------------------- chip
# hw.optional.arm64 (or the CPU brand string) is used instead of `uname -m`: under
# Rosetta 2, an x86_64 shell on real Apple Silicon hardware still reports `x86_64`
# from `uname -m`, which would wrongly route a fast Mac onto the slower CPU backend.
if [[ "$(sysctl -n hw.optional.arm64 2>/dev/null)" == "1" ]]; then
  CHIP="apple"
else
  CHIP="intel"
fi
ok "chip: $CHIP $([[ $CHIP == intel ]] && echo '(faster-whisper backend)' || echo '(mlx-whisper backend)')"

# ---------------------------------------------------------------- uv
# uv is this skill's only external prerequisite. Rather than dead-ending a first-time
# user with a bare URL, offer to install it, and fall back to stdlib venv + pip if they
# decline — the packages below install fine either way, uv is just markedly faster and
# can fetch its own CPython 3.12.
USE_UV=1
if [[ ! -x "$UV" ]]; then
  if command -v uv >/dev/null 2>&1; then
    UV="$(command -v uv)"
  elif [[ $CHECK == 1 ]]; then
    no "uv not found (https://astral.sh/uv)"; USE_UV=0
  else
    wa "uv not found — it is this skill's only prerequisite."
    echo "      Install it with:  curl -LsSf https://astral.sh/uv/install.sh | sh"
    printf "      Install uv now? [y/N] "
    read -r reply </dev/tty 2>/dev/null || reply=""
    if [[ "$reply" =~ ^[Yy]$ ]]; then
      curl -LsSf https://astral.sh/uv/install.sh | sh || { no "uv install failed"; exit 1; }
      UV="$HOME/.local/bin/uv"
      [[ -x "$UV" ]] || UV="$(command -v uv 2>/dev/null || echo '')"
      [[ -x "$UV" ]] || { no "uv installed but not found on PATH — open a new shell and re-run"; exit 1; }
    else
      wa "continuing without uv — falling back to python3 -m venv + pip"
      USE_UV=0
    fi
  fi
fi
if [[ $USE_UV == 1 ]]; then
  ok "uv $("$UV" --version 2>/dev/null | awk '{print $2}')"
else
  command -v python3 >/dev/null 2>&1 || { no "neither uv nor python3 found — install Python 3.10+"; exit 1; }
  PYV="$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')"
  python3 -c 'import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)' \
    || { no "python3 is $PYV — need 3.10+ (or install uv, which fetches its own)"; exit 1; }
  ok "python3 $PYV (pip fallback path)"
fi

# ---------------------------------------------------------------- venv
if [[ ! -x "$PY" ]]; then
  if [[ $CHECK == 1 ]]; then no "venv missing ($VENV) — run ./setup.sh"; else
    if [[ $USE_UV == 1 ]]; then
      hd "creating venv (python 3.12, fetched by uv if needed)"
      "$UV" venv --python 3.12 "$VENV" || exit 1
    else
      hd "creating venv (system python3)"
      python3 -m venv "$VENV" || exit 1
    fi
  fi
fi
[[ -x "$PY" ]] && ok "python $("$PY" -V 2>&1 | awk '{print $2}')  ($VENV)"

# ---------------------------------------------------------------- packages
if [[ "$CHIP" == "apple" ]]; then
  PKGS=(mlx-whisper imageio-ffmpeg "pyannote.audio>=3.1" "numpy<3")
  ASR_MOD="mlx_whisper"
else
  # soundfile is required here for the same reason setup.ps1 installs it on Windows:
  # off Apple Silicon, pyannote loads the wav through torchaudio, whose available
  # backend differs. Previously only the Windows script had it — an untested
  # asymmetry on an already-untested path.
  PKGS=(faster-whisper imageio-ffmpeg "pyannote.audio>=3.1" "numpy<3" soundfile)
  ASR_MOD="faster_whisper"
fi
if [[ $CHECK == 0 && -x "$PY" ]]; then
  hd "installing packages (a few minutes on first run)"
  if [[ $USE_UV == 1 ]]; then
    VIRTUAL_ENV="$VENV" "$UV" pip install --python "$PY" "${PKGS[@]}" || exit 1
  else
    "$PY" -m pip install --upgrade pip >/dev/null 2>&1
    "$PY" -m pip install "${PKGS[@]}" || exit 1
  fi
fi

if [[ -x "$PY" ]]; then
  hd "dependencies"
  for mod in "$ASR_MOD" imageio_ffmpeg pyannote.audio torch; do
    v=$("$PY" -c "
import importlib,warnings;warnings.filterwarnings('ignore')
m=importlib.import_module('$mod');print(getattr(m,'__version__','present'))" 2>/dev/null)
    [[ -n "$v" ]] && ok "$mod $v" || no "$mod"
  done

  hd "ffmpeg"
  FF=$("$PY" -c "
import shutil
e=shutil.which('ffmpeg')
if not e:
    try:
        import imageio_ffmpeg; e=imageio_ffmpeg.get_ffmpeg_exe()
    except Exception: e=''
print(e or '')" 2>/dev/null)
  [[ -n "$FF" ]] && ok "$FF" || no "ffmpeg — install failed"

  hd "whisper model cache"
  if [[ "$CHIP" == "apple" ]]; then
    M="$HOME/.cache/huggingface/hub/models--mlx-community--whisper-large-v3-turbo"
    [[ -d "$M" ]] && ok "whisper-large-v3-turbo cached ($(du -sh "$M" 2>/dev/null | cut -f1))" \
                  || wa "not cached — downloads ~1.5GB on first run"
  else
    wa "model downloads on first run (~1.5GB, one time, cached under ~/.cache/huggingface after)"
  fi
fi

# ---------------------------------------------------------------- HF token
hd "speaker diarization (optional)"
if [[ -n "${HF_TOKEN:-}${HUGGINGFACE_TOKEN:-}" ]]; then
  ok "HF_TOKEN set — speaker labels enabled"
else
  wa "HF_TOKEN not set — transcripts still work, but WITHOUT speaker labels"
  cat <<'EOT'
       To enable (one time, free — you must do these yourself):
         1. Create a HuggingFace account:  https://huggingface.co/join
         2. Accept the licence:
              https://huggingface.co/pyannote/speaker-diarization-community-1
         3. Make a READ token:  https://huggingface.co/settings/tokens
         4. Add to ~/.zshrc:    export HF_TOKEN="hf_xxxxx"
            then:               source ~/.zshrc
EOT
fi

hd "next"
if [[ $CHECK == 1 ]]; then
  echo "  ./setup.sh            # install anything marked MISS"
else
  echo "  ./calibrate.sh        # measure this Mac's speed -> config/engine.json"
fi
echo
