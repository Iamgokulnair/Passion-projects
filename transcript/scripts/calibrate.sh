#!/usr/bin/env bash
# Measure THIS Mac's actual transcription speed and write config/engine.json.
# Nothing in this skill should quote a runtime that isn't grounded here.
#
#   ./calibrate.sh                 # uses a public sample clip (needs network once)
#   ./calibrate.sh /path/to/media  # better: calibrate on your own typical recording
set -uo pipefail

SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$SKILL/.venv/bin/python"
CFG="$SKILL/config/engine.json"
MODEL="${MODEL:-mlx-community/whisper-large-v3-turbo}"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

[[ -x "$PY" ]] || { echo "venv missing — run ./setup.sh first"; exit 1; }

printf '\n\033[1mtranscript · calibration\033[0m\n'

SRC="${1:-}"
if [[ -z "$SRC" ]]; then
  echo "  no sample given — fetching a short public clip"
  YTDLP="${YTDLP:-$HOME/.local/bin/yt-dlp}"
  [[ -x "$YTDLP" ]] || { echo "  yt-dlp not found. Pass your own file: ./calibrate.sh <media>"; exit 1; }
  # No -x/--audio-format: that needs ffmpeg on PATH under the name `ffmpeg`, which
  # imageio's binary isn't. transcribe.py decodes whatever container arrives anyway.
  "$YTDLP" -f "bestaudio/best" -o "$TMP/sample.%(ext)s" --quiet --no-warnings \
           "https://www.youtube.com/watch?v=8S0FDjFBj8o" || {
    echo "  download failed. Pass your own file: ./calibrate.sh <media>"; exit 1; }
  SRC="$(find "$TMP" -name 'sample.*' | head -1)"
  [[ -n "$SRC" ]] || { echo "  nothing downloaded. Pass your own file: ./calibrate.sh <media>"; exit 1; }
fi
[[ -f "$SRC" ]] || { echo "  not found: $SRC"; exit 1; }
echo "  sample: $SRC"

# ---- ASR-only timing (no diarization: we want the GPU lane in isolation) -----
echo "  running ASR benchmark..."
"$PY" "$SKILL/scripts/transcribe.py" "$SRC" --out "$TMP/out" --no-diarize --model "$MODEL" \
  || { echo "  benchmark failed"; exit 1; }

MAN="$(find "$TMP/out" -name '*.manifest.json' | head -1)"
[[ -f "$MAN" ]] || { echo "  no manifest produced"; exit 1; }

"$PY" - "$MAN" "$CFG" "$MODEL" <<'PYEOF'
import json, sys, time, platform, subprocess

man  = json.load(open(sys.argv[1]))
cfg_p, model = sys.argv[2], sys.argv[3]

rtf  = man["asr_realtime_factor"]
dur  = man["duration_sec"]

def chip():
    try:
        return subprocess.run(["sysctl","-n","machdep.cpu.brand_string"],
                              capture_output=True, text=True).stdout.strip()
    except Exception:
        return platform.machine()

cfg = {
    "measured_on": time.strftime("%Y-%m-%d"),
    "machine": chip(),
    "model": model,
    "asr_realtime_factor": rtf,
    "sample_duration_sec": round(dur, 1),
    "note": "asr_realtime_factor = seconds of audio processed per second of wall-clock, "
            "ASR lane only. Diarization runs concurrently on CPU and is normally hidden "
            "beneath this. Regenerate with ./calibrate.sh after any model change.",
}
json.dump(cfg, open(cfg_p, "w"), indent=2)

W, G = "\033[33m", "\033[32m"; R = "\033[0m"
print(f"\n  measured: {G}{rtf:.1f}x realtime{R} on {cfg['machine']}")
print(f"  written:  {cfg_p}\n")

# fixed overhead: decode + model load + write. Measured share of this run, floored.
overhead = max(30.0, man["wall_sec"] - man["asr_sec"])

print("  \033[1mProjected wall-clock on this machine\033[0m")
print("  " + "-"*54)
print(f"  {'input':<10} {'ASR':>9} {'+overhead':>11} {'total':>10}   {'vs budget':>10}")
print("  " + "-"*54)
budgets = {1800: ("5-6 min", 6*60), 7200: ("20-25 min", 25*60)}
for secs, label in ((1800,"30 min"),(3600,"1 h"),(5400,"90 min"),(7200,"2 h")):
    asr   = secs / rtf
    total = asr + overhead
    verdict = ""
    if secs in budgets:
        name, cap = budgets[secs]
        verdict = f"{G}OK{R} <{name}" if total <= cap else f"{W}OVER{R} {name}"
    print(f"  {label:<10} {asr/60:>7.1f}m {overhead/60:>10.1f}m {total/60:>8.1f}m   {verdict:>10}")
print("  " + "-"*54)
if rtf < 6:
    print(f"\n  {W}Below target.{R} Retry with a faster model:")
    print("     MODEL=mlx-community/distil-whisper-large-v3 ./calibrate.sh")
print()
PYEOF
