---
name: transcript
user-invocable: true
description: >-
  Turn any local video or audio file into a full text transcript, entirely on this machine.
  A local Otter: point it at a recording with no subtitles and get back timestamped text,
  subtitles, and a readable speaker-labelled document. Domain-agnostic — meetings, lectures,
  interviews, training sessions, podcasts, calls, in any language. Runs offline on
  mlx-whisper (Apple Silicon, fast/measured path) or faster-whisper (Windows/Intel Mac/Linux);
  audio never leaves the machine. Use for "/transcript",
  "transcribe this video", "get me the transcript of this recording", "what was said in
  this file", "convert this MP4 to text", "subtitle this video", "this video has no
  captions". NOT for summarising or analysing a transcript that already exists (that is
  ordinary downstream work), and NOT for burning captions onto video (see /embedded-captions).
---

# transcript

Any recording in → a faithful transcript out. Nothing leaves this machine.

> **`$SKILL` = the directory this `SKILL.md` file sits in.** Substitute that path when you run
> the commands below. Never use a remembered absolute path — this skill is installed to a
> different location on every machine.

```bash
"$SKILL/.venv/bin/python" "$SKILL/scripts/transcribe.py" <file-or-folder>       # macOS/Linux
```
```powershell
& "$SKILL\.venv\Scripts\python.exe" "$SKILL\scripts\transcribe.py" <file-or-folder>   # Windows
```

**First run ever?** → `scripts/setup.sh` (macOS/Linux) or `scripts/setup.ps1` (Windows).
See `SETUP.md`. Requires [`uv`](https://astral.sh/uv) — the setup script installs everything else.

---

## What it does

| Stage | Detail |
|---|---|
| Decode | ffmpeg → 16 kHz mono WAV. Any container ffmpeg reads |
| Transcribe | `mlx-whisper` (Apple Silicon) or `faster-whisper` (Windows/Intel Mac/Linux), turbo model. Language auto-detected |
| Diarize | `pyannote` on the CPU **in parallel** — so speaker labels cost ~no extra time |
| Merge | Each segment gets the speaker whose turns overlap it most. Pure interval maths |
| Write | Six files, all verbatim ASR |

**No model ever rewrites the words.** The `.md` is built by deterministic grouping of
consecutive same-speaker segments. What Whisper heard is what you get — which is the whole
point of a transcript.

## Outputs

Written alongside the source unless `--out` is given.

| File | Use |
|---|---|
| `<name>.txt` | `[00:00:00] text` per line — the main artifact |
| `<name>.md` | Readable doc, speaker turns as paragraphs |
| `<name>.srt` / `.vtt` | Subtitles, for re-attaching to the video |
| `<name>.json` | `{file, duration_sec, language, segments[{start,end,text,speaker}]}` |
| `<name>.manifest.json` | model, language, measured realtime factor, wall-clock |

## Flags

| Flag | Effect |
|---|---|
| `--no-diarize` | Skip speaker labels (a little faster, flat transcript) |
| `--hint "..."` | Prime Whisper with names/acronyms you know are coming. Free text, per run |
| `--lang en` | Force a language instead of auto-detecting |
| `--model <id>` | Different Whisper model — the speed/accuracy dial |
| `--out <dir>` | Send outputs elsewhere |
| `--serial` | Lanes one at a time; use if you need the machine for something else |

Pass a **folder** instead of a file to batch every media file inside it.

## Speed

Read the measured numbers for this machine from `config/engine.json`, or re-measure with
`scripts/calibrate.sh`. Design targets: **30 min → under 6 min**, **2 h → under 25 min** —
these are validated on the `mlx-whisper` (Apple Silicon) path. The `faster-whisper` path
(Windows/Intel Mac/Linux) is CPU-bound by default and not yet benchmarked; every run still
prints its own realtime factor, so drift or a slow machine is visible immediately either way.

If a run comes in slow, the dial is the model, not the architecture:

| Model | Relative speed | Accuracy |
|---|---|---|
| `mlx-community/whisper-large-v3-turbo` *(default)* | 1× | best — handles strong accents well |
| `mlx-community/distil-whisper-large-v3` | ~2× | slightly lower |
| `mlx-community/whisper-medium-mlx` | ~3× | noticeably lower on accents |

## Notes worth knowing

- **Accents:** `large-v3-turbo` is the right default for mixed Indian/native-speaker audio;
  the smaller models degrade on exactly that material. Don't downgrade for speed unless a
  measured run says you must.
- **Speaker labels come out as `SPEAKER_00`, `SPEAKER_01`.** Whisper cannot know real names.
  Rename them afterwards if it matters.
- **No HF token → no speaker labels, but the transcript still runs.** It warns and continues.
- **Long silences and music** produce occasional junk segments. This is inherent to ASR.
- **Local-only by design.** There is no cloud path in this skill, deliberately.
