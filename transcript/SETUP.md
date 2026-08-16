# Setup — one time

## Prerequisite: `uv`

This skill's **one** external prerequisite is [`uv`](https://astral.sh/uv):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh     # macOS / Linux
```
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"   # Windows
```

If `uv` is missing, `setup.sh` offers to install it for you, and falls back to
`python3 -m venv` + `pip` if you decline (that path needs Python 3.10+ already installed).
With `uv`, you don't need Python at all — it fetches its own.

You do **not** need Homebrew, and you do **not** need ffmpeg: `imageio-ffmpeg` ships the
binary and the skill resolves it automatically.

## Run it

**macOS / Linux** — from the skill's own directory:

```bash
cd /path/to/transcript
./scripts/setup.sh
```

**Windows (PowerShell):**

```powershell
cd transcript
.\scripts\setup.ps1
```

Creates a self-contained `.venv` inside the skill folder. On Apple Silicon this installs
`mlx-whisper` (the fast, measured path); on Intel Mac, Windows, or Linux it installs
`faster-whisper` instead — same output, same downstream pipeline, unmeasured/CPU-bound speed
until benchmarked on real hardware. Either way: `imageio-ffmpeg` and `pyannote.audio` too.
Idempotent — safe to re-run.

**Disk footprint, honestly:** the `.venv` is ~1.3 GB, the Whisper model ~1.5 GB on first run
(the non-Apple-Silicon fallback model is ~3 GB), and diarization pulls further weights the
first time it runs. Budget **~3 GB**, more on Windows/Intel.

If Windows blocks `setup.ps1` from running ("this file came from another computer"), the repo
was downloaded as a ZIP rather than `git clone`d — run `Unblock-File .\scripts\setup.ps1` first.

Check state at any time without changing anything:

```bash
./scripts/setup.sh --check      # macOS
.\scripts\setup.ps1 -Check      # Windows
```

---

## Speaker labels — two steps only you can do

Diarization uses a **gated** model. It's free, but HuggingFace requires a human to accept the
licence, and I can't create accounts or handle your tokens.

1. Account → https://huggingface.co/join
2. Accept the licence. Installed here is **pyannote.audio 4.x**, so accept this one:
   - https://huggingface.co/pyannote/speaker-diarization-community-1

   *(The skill also falls back to the older `pyannote/speaker-diarization-3.1` +
   `pyannote/segmentation-3.0` pair if you've already accepted those instead — either
   path works.)*
3. Create a **read** token → https://huggingface.co/settings/tokens
4. Add it to your shell:

```bash
# macOS
echo 'export HF_TOKEN="hf_your_token_here"' >> ~/.zshrc && source ~/.zshrc
```

```powershell
# Windows — both lines needed: setx alone won't show up in the current window
$env:HF_TOKEN = "hf_your_token_here"
setx HF_TOKEN "hf_your_token_here"
```

**This is optional.** Without a token the skill still transcribes normally — it prints a
warning and emits a transcript with no speaker labels.

---

## Calibrate

```bash
./scripts/calibrate.sh                 # public sample clip
./scripts/calibrate.sh /path/to/video  # better — your own typical recording
```

Measures this Mac's real throughput, writes `config/engine.json`, and prints projected
wall-clock for 30 min / 1 h / 90 min / 2 h inputs against the design targets. Re-run after
changing models. `calibrate.sh` is macOS-only for now — on Windows, every `transcribe.py` run
still prints its own realtime factor at the end, just not aggregated into `config/engine.json`.

---

## Verify end to end

```bash
# macOS
./scripts/setup.sh --check
"$PWD/.venv/bin/python" scripts/transcribe.py /path/to/a/short/video
```

```powershell
# Windows
.\scripts\setup.ps1 -Check
.\.venv\Scripts\python.exe scripts\transcribe.py C:\path\to\a\short\video
```

Expect six files next to the source and a printed realtime factor.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `ffmpeg not found` | `uv tool install imageio-ffmpeg`, or re-run `setup.sh`/`setup.ps1` |
| `Could not load pyannote/...` | Licence not accepted on **both** pages above, or token isn't a read token |
| Diarization fails, transcript still appears | Working as designed — it degrades rather than blocking |
| First run stalls at 0% | Downloading the 1.5 GB model. Once only; it's cached afterwards |
| Repeated/looping text | Bad audio in that stretch. Try `--hint` with context, or `--model` |
| Wrong language detected | `--lang en` |
| Machine unusable during a run | `--serial` |
| Much slower than `engine.json` (Mac) | Something else is using the GPU; check Activity Monitor |
| Slow on Windows | Expected — the default `faster-whisper` path is CPU-only. GPU needs a manual CUDA/cuDNN install (see README), not automated by `setup.ps1` |
| `setup.ps1` won't run: "from another computer" | ZIP download, not `git clone` — run `Unblock-File .\scripts\setup.ps1` |
| `Activate.ps1 cannot be loaded` | Don't activate the venv — invoke `.venv\Scripts\python.exe` directly, as shown above |
