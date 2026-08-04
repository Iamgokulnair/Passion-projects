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
if [[ ! -x "$UV" ]]; then
  command -v uv >/dev/null 2>&1 && UV="$(command -v uv)" || { no "uv not found — install from https://astral.sh/uv"; exit 1; }
fi
ok "uv $("$UV" --version 2>/dev/null | awk '{print $2}')"

# ---------------------------------------------------------------- venv
if [[ ! -x "$PY" ]]; then
  if [[ $CHECK == 1 ]]; then no "venv missing ($VENV) — run ./setup.sh"; else
    hd "creating venv (python 3.12)"
    "$UV" venv --python 3.12 "$VENV" || exit 1
  fi
fi
[[ -x "$PY" ]] && ok "python $("$PY" -V 2>&1 | awk '{print $2}')  ($VENV)"

# ---------------------------------------------------------------- packages
if [[ "$CHIP" == "apple" ]]; then
  PKGS=(mlx-whisper imageio-ffmpeg "pyannote.audio>=3.1" "numpy<3")
  ASR_MOD="mlx_whisper"
else
  PKGS=(faster-whisper imageio-ffmpeg "pyannote.audio>=3.1" "numpy<3")
  ASR_MOD="faster_whisper"
fi
if [[ $CHECK == 0 && -x "$PY" ]]; then
  hd "installing packages (a few minutes on first run)"
  VIRTUAL_ENV="$VENV" "$UV" pip install --python "$PY" "${PKGS[@]}" || exit 1
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
