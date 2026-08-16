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
# uv is this skill's only external prerequisite. Offer to install it rather than
# dead-ending a first-time user, and fall back to stdlib venv + pip if declined.
USE_UV=1
if [[ ! -x "$UV" ]]; then
  if command -v uv >/dev/null 2>&1; then
    UV="$(command -v uv)"
  elif [[ $CHECK == 1 ]]; then
    no "uv not found (https://astral.sh/uv)"; USE_UV=0
  else
    wa "uv not found -- it is this skill's only prerequisite."
    echo "      Install it with:  curl -LsSf https://astral.sh/uv/install.sh | sh"
    printf "      Install uv now? [y/N] "
    read -r reply </dev/tty 2>/dev/null || reply=""
    if [[ "$reply" =~ ^[Yy]$ ]]; then
      curl -LsSf https://astral.sh/uv/install.sh | sh || { no "uv install failed"; exit 1; }
      UV="$HOME/.local/bin/uv"
      [[ -x "$UV" ]] || UV="$(command -v uv 2>/dev/null || echo '')"
      [[ -x "$UV" ]] || { no "uv installed but not on PATH -- open a new shell and re-run"; exit 1; }
    else
      wa "continuing without uv -- falling back to python3 -m venv + pip"
      USE_UV=0
    fi
  fi
fi
if [[ $USE_UV == 1 ]]; then
  ok "uv $("$UV" --version 2>/dev/null | awk '{print $2}')"
else
  command -v python3 >/dev/null 2>&1 || { no "neither uv nor python3 found -- install Python 3.10+"; exit 1; }
  PYV="$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')"
  python3 -c 'import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)' \
    || { no "python3 is $PYV -- need 3.10+ (or install uv, which fetches its own)"; exit 1; }
  ok "python3 $PYV (pip fallback path)"
fi

# ---------------------------------------------------------------- venv
if [[ ! -x "$PY" ]]; then
  if [[ $CHECK == 1 ]]; then no "venv missing ($VENV) -- run ./setup.sh"; else
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
# tinycss2 and Pillow were installed but never imported by any script (verified by
# grep across scripts/*.py) -- dropped rather than shipping dead install weight.
PKGS=(python-pptx beautifulsoup4 playwright)
if [[ $CHECK == 0 && -x "$PY" ]]; then
  hd "installing packages (a minute or two on first run)"
  if [[ $USE_UV == 1 ]]; then
    VIRTUAL_ENV="$VENV" "$UV" pip install --python "$PY" "${PKGS[@]}" || exit 1
  else
    "$PY" -m pip install --upgrade pip >/dev/null 2>&1
    "$PY" -m pip install "${PKGS[@]}" || exit 1
  fi
fi

if [[ -x "$PY" ]]; then
  hd "dependencies"
  for mod in pptx bs4 playwright; do
    v=$("$PY" -c "
import importlib,warnings;warnings.filterwarnings('ignore')
m=importlib.import_module('$mod');print(getattr(m,'__version__','present'))" 2>/dev/null)
    [[ -n "$v" ]] && ok "$mod $v" || no "$mod"
  done

  hd "playwright chromium (computed-style extraction, gradient rasterization)"
  CHROMIUM_OK=1
  if [[ $CHECK == 0 ]]; then
    if ! "$PY" -m playwright install chromium; then
      CHROMIUM_OK=0
      wa "chromium install failed -- parse_html.py falls back to degraded bs4-only mode"
      wa "(that mode loses computed styles, backgrounds, and every rasterized panel)"
    fi
  fi
  CHROMIUM_CACHE="${PLAYWRIGHT_BROWSERS_PATH:-$HOME/Library/Caches/ms-playwright}"
  [[ "$(uname)" == "Linux" && -z "${PLAYWRIGHT_BROWSERS_PATH:-}" ]] && CHROMIUM_CACHE="$HOME/.cache/ms-playwright"
  if compgen -G "$CHROMIUM_CACHE/chromium-*" > /dev/null 2>&1; then
    ok "chromium cached ($(du -sh "$CHROMIUM_CACHE" 2>/dev/null | cut -f1))"
    # Presence on disk is not the same as "it launches". Prove it.
    if "$PY" -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); b.close()" >/dev/null 2>&1; then
      ok "chromium launches"
    else
      CHROMIUM_OK=0
      no "chromium is downloaded but will not launch"
      if [[ "$(uname)" == "Linux" ]]; then
        wa "on Linux this is almost always missing system libraries. Fix with:"
        echo "      sudo \"$PY\" -m playwright install-deps chromium"
      fi
    fi
  else
    CHROMIUM_OK=0
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
