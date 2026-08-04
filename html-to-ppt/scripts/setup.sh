#!/usr/bin/env bash
# One-time (idempotent) setup for the html-to-ppt skill.
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

hd "html-to-ppt . setup ($([[ $CHECK == 1 ]] && echo check || echo install))"

# ---------------------------------------------------------------- uv
if [[ ! -x "$UV" ]]; then
  command -v uv >/dev/null 2>&1 && UV="$(command -v uv)" || { no "uv not found -- install from https://astral.sh/uv"; exit 1; }
fi
ok "uv $("$UV" --version 2>/dev/null | awk '{print $2}')"

# ---------------------------------------------------------------- venv
if [[ ! -x "$PY" ]]; then
  if [[ $CHECK == 1 ]]; then no "venv missing ($VENV) -- run ./setup.sh"; else
    hd "creating venv (python 3.12)"
    "$UV" venv --python 3.12 "$VENV" || exit 1
  fi
fi
[[ -x "$PY" ]] && ok "python $("$PY" -V 2>&1 | awk '{print $2}')  ($VENV)"

# ---------------------------------------------------------------- packages
PKGS=(python-pptx beautifulsoup4 tinycss2 Pillow playwright)
if [[ $CHECK == 0 && -x "$PY" ]]; then
  hd "installing packages (a minute or two on first run)"
  VIRTUAL_ENV="$VENV" "$UV" pip install --python "$PY" "${PKGS[@]}" || exit 1
fi

if [[ -x "$PY" ]]; then
  hd "dependencies"
  for mod in pptx bs4 tinycss2 PIL playwright; do
    v=$("$PY" -c "
import importlib,warnings;warnings.filterwarnings('ignore')
m=importlib.import_module('$mod');print(getattr(m,'__version__','present'))" 2>/dev/null)
    [[ -n "$v" ]] && ok "$mod $v" || no "$mod"
  done

  hd "playwright chromium (computed-style extraction, gradient rasterization)"
  if [[ $CHECK == 0 ]]; then
    "$PY" -m playwright install chromium || wa "chromium install failed -- parse_html.py will fall back to degraded bs4-only mode"
  fi
  CHROMIUM_CACHE="$HOME/Library/Caches/ms-playwright"
  [[ "$(uname)" == "Linux" ]] && CHROMIUM_CACHE="$HOME/.cache/ms-playwright"
  if compgen -G "$CHROMIUM_CACHE/chromium-*" > /dev/null 2>&1; then
    ok "chromium cached ($(du -sh "$CHROMIUM_CACHE" 2>/dev/null | cut -f1))"
  else
    wa "chromium not cached -- downloads ~150-300MB on first install, one time"
  fi
fi

# ---------------------------------------------------------------- LibreOffice (optional, recommended)
hd "LibreOffice (optional, strongly recommended -- powers the visual Perceive Gate)"
LO=""
for candidate in soffice libreoffice "/Applications/LibreOffice.app/Contents/MacOS/soffice"; do
  if command -v "$candidate" >/dev/null 2>&1; then LO="$(command -v "$candidate")"; break; fi
  [[ -x "$candidate" ]] && { LO="$candidate"; break; }
done
if [[ -n "$LO" ]]; then
  ok "$LO"
else
  wa "not found -- the pipeline still runs without it, but the Perceive Gate degrades to"
  wa "geometry-only checks (no visual render, misses contrast/chart-integrity/gradient-legibility)"
  cat <<'EOT'
       To enable (one time, free):
         macOS:    brew install --cask libreoffice
         Windows:  winget install TheDocumentFoundation.LibreOffice
EOT
fi

hd "next"
if [[ $CHECK == 1 ]]; then
  echo "  ./setup.sh                                    # install anything marked MISS"
else
  echo "  .venv/bin/python scripts/convert.py examples/sample.html   # end-to-end smoke test"
fi
echo
