# transcript

Point it at a recording with no captions — a meeting, a lecture, an interview, a call — and get
back a full, timestamped, speaker-labelled transcript. Entirely local: the audio never leaves
your machine. Pair it with the sibling [`transcript-to-summary`](../transcript-to-summary/)
skill and the same pipeline goes all the way to structured meeting notes.

## Platform support

| Platform | ASR backend | Status |
|---|---|---|
| **Apple Silicon Mac** (M1–M4) | `mlx-whisper` | Fast path — measured, see below |
| **Windows** | `faster-whisper` | Works, CPU by default — not yet benchmarked on real hardware, see [Known limitations](#known-limitations) |
| **Intel Mac / Linux** | `faster-whisper` | Same as Windows |

**Speaker diarization** (who-said-what) uses plain `torch` + `pyannote.audio` on the CPU and is
identical on every platform above — it's not tied to either ASR backend.

## What it does

| Stage | Detail |
|---|---|
| Decode | ffmpeg → 16 kHz mono WAV. Any container ffmpeg reads |
| Transcribe | `mlx-whisper` (Apple Silicon) or `faster-whisper` (everywhere else), turbo model, language auto-detected |
| Diarize | `pyannote` on the CPU, launched in parallel with transcription. **Optional and currently unverified** — see Known limitations |
| Merge | Each segment gets the speaker whose turns overlap it most. Pure interval maths |
| Write | Six files, all verbatim ASR — no model ever rewrites the words |

Outputs, written alongside the source: `.txt` (timestamped lines), `.md` (readable doc, speaker
turns as paragraphs), `.srt`/`.vtt` (subtitles), `.json` (structured segments), `.manifest.json`
(model, language, measured realtime factor).

## Time benefit

Measured on this tool's own reference machine (Apple M4, 16GB — see `config/engine.json`,
reproducible via `scripts/calibrate.sh`): **13.36x realtime** on the `mlx-whisper` path,
**with speaker diarization switched off** (`--no-diarize`, as the benchmark runs it).

That caveat matters: diarization runs concurrently but the pipeline blocks until it finishes,
so with speaker labels enabled your real wall-clock is `max(ASR, diarization)` — and the
diarization side of that has never been measured. The figures below are the ASR-only path.

**Worked example** — a 30-minute meeting recording with no captions:

| | Watching it yourself | `/transcript` (Apple Silicon) |
|---|---|---|
| Time spent | 30 minutes | **≈2 minutes 15 seconds** (1800s ÷ 13.36, no diarization) |
| Time saved | — | **≈28 minutes, ~92% of the time back** |

Add `/transcript-to-summary` (a near-instant Claude pass over the transcript) and the same
30-minute recording becomes a structured Markdown doc — key points, decisions, action items,
quotes, chapter outline — still inside roughly 2–3 minutes total, instead of 30 minutes of
watching *and* manual note-taking afterward.

**Caveats, stated plainly:**
- The 13.36x figure is specific to an Apple M4; other Apple Silicon chips will differ (repeated
  runs on this machine ranged 13–17x with thermal variance).
- It excludes one-time model download and disk I/O.
- The benchmark runs with `--no-diarize`. With speaker labels on, expect wall-clock to be
  `max(ASR, diarization)` — an unmeasured number, not "~free".
- The `faster-whisper` (Windows/Intel Mac/Linux) path has **no equivalent number yet** — it will
  be slower than the Apple-Silicon path and varies by CPU. Don't extrapolate the 13.36x figure
  to it.
- `/transcript` itself stays deliberately verbatim-only — the "high-impact points" extraction is
  `/transcript-to-summary`'s job, not this skill's.

## Install

1. **Install Claude Code**, if you don't already have it: https://claude.com/claude-code
2. **Clone this repo** (not a ZIP download — see the Windows note below):
   ```
   git clone https://github.com/Iamgokulnair/Passion-projects.git
   cd Passion-projects
   ```
3. **Run setup** for your platform:
   ```bash
   # macOS (Apple Silicon or Intel)
   cd transcript && ./scripts/setup.sh
   ```
   ```powershell
   # Windows
   cd transcript; .\scripts\setup.ps1
   ```
   Creates a self-contained `.venv` inside the folder — nothing installed system-wide.
4. **Symlink both skills into Claude Code** so `/transcript` and `/transcript-to-summary`
   become available:
   ```bash
   # macOS / Linux — run from the repo root; mkdir first, the dir may not exist yet
   mkdir -p ~/.claude/skills
   ln -s "$PWD/transcript" ~/.claude/skills/transcript
   ln -s "$PWD/transcript-to-summary" ~/.claude/skills/transcript-to-summary
   ```
   ```powershell
   # Windows — needs admin or Developer Mode enabled; if that's not available,
   # just copy the two folders into %USERPROFILE%\.claude\skills\ instead
   New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.claude\skills" | Out-Null
   New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\skills\transcript" -Target "$PWD\transcript"
   New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\skills\transcript-to-summary" -Target "$PWD\transcript-to-summary"
   ```
5. **Optional — speaker labels**: create a free Hugging Face account, accept the gated
   diarization model's license, and set an `HF_TOKEN`. Full steps in [`SETUP.md`](SETUP.md).
   Without it, transcripts still work, just without speaker names.
6. **Use it** — inside a Claude Code session:
   ```
   /transcript path/to/recording.mp4
   /transcript-to-summary path/to/recording.txt
   ```
   Video in, structured summary out.

If Windows blocks `setup.ps1` ("this file came from another computer"), that means the repo was
downloaded as a ZIP rather than `git clone`d — run `Unblock-File .\scripts\setup.ps1` first.

## Security notes

- **Fully local for transcription itself.** No cloud API calls, no telemetry. Good for
  confidential recordings.
- **One exception:** the *one-time* diarization setup step downloads a gated model from Hugging
  Face, which needs internet access. After that first download it's cached and offline again.
  Don't assume zero network egress at every step — just at every step except that one.
- **Review `setup.sh`/`setup.ps1` before running them** — standard hygiene for any script from a
  public repo. Both are plain `pip`/`uv` installs into a local virtual environment; no
  `curl | bash`, no `sudo`, no admin rights required (except the optional Windows symlink step
  above, which has a copy-folder fallback).
- **Never commit `.venv` or your `HF_TOKEN`.** The repo's `.gitignore` covers this; keep the
  token as a personal environment variable, never hardcoded.
- The benchmark number above is this one machine's measurement, not a guarantee — regenerate it
  for your own hardware with `scripts/calibrate.sh` (macOS).

## Known limitations

- **The Windows/Intel-Mac/Linux path (`faster-whisper`) is new and has not been run end-to-end
  on real Windows hardware by the author.** The Apple-Silicon path is the proven one — this repo
  ships the other path as a genuine v1, not a fully field-tested equivalent. If something's off,
  that's expected for a first release; the code path is real, just unverified outside macOS.
- GPU acceleration on Windows (CUDA/cuDNN) is not automated by `setup.ps1` — it runs CPU-only by
  default, which works but is slower. See `SETUP.md`'s troubleshooting table if you want to set
  up GPU acceleration manually.
- **Speaker diarization is implemented but unverified.** It has never been run end to end —
  not benchmarked, and not confirmed working. The code path is complete and the setup steps
  are documented, but no transcript produced by this tool has yet carried real speaker labels.
  Treat it as untested until this line says otherwise. ASR (the transcript itself) is the
  measured, proven path.

Full setup detail and a troubleshooting table: [`SETUP.md`](SETUP.md).
