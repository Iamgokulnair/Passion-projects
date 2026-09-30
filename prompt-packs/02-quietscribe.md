# 02 - QuietScribe (transcript + transcript-to-summary)

A local AI transcription pipeline. Recording in, speaker-labelled transcript out, then
structured meeting notes. Audio never leaves the machine. Six prompts.

---

### Prompt 1 - The brief and the boundary

```
Build two Claude Code skills that work as a pipeline.

/transcript: any local audio or video file in, a faithful transcript out. Fully offline.
Verbatim only - no model may rewrite the words. It must not summarise.

/transcript-to-summary: a transcript in, structured Markdown out - key points, decisions,
action items with owners and dates, notable quotes, chapter outline. It must never invent
a quote, owner or date that isn't in the source.

Keep that boundary strict: transcription and summarising never mix. Give me the stage
table for /transcript before any code.
```

**Check:** Decode -> Transcribe -> Diarize -> Merge -> Write, with the verbatim rule stated.

---

### Prompt 2 - Pick the engine per platform

```
Write scripts/transcribe.py. Decode any container with ffmpeg to 16 kHz mono WAV. For
transcription use mlx-whisper on Apple Silicon and faster-whisper everywhere else, both on
the turbo model, with language auto-detected. Detect the platform at runtime; don't make
the user choose.
```

**Check:** a 1-minute clip transcribes with timestamps on your machine.

---

### Prompt 3 - Speaker labels without extra time

```
Write scripts/diarize.py using pyannote.audio on the CPU. Run it in parallel with
transcription so speaker labels cost almost no extra time. Merge by pure interval maths:
each transcript segment gets the speaker whose turns overlap it most. If there's no
Hugging Face token, degrade to a flat transcript and say so - never crash.
```

**Check:** a two-person recording comes back with SPEAKER_00 / SPEAKER_01 turns.

---

### Prompt 4 - Six outputs

```
Write all outputs next to the source file: .txt (timestamped lines), .md (readable doc,
consecutive same-speaker segments grouped into paragraphs by deterministic code, not a
model), .srt and .vtt subtitles, .json segments, and .manifest.json with the model,
language and measured realtime factor.
```

**Check:** six files, and the `.md` text matches the `.json` word for word.

---

### Prompt 5 - Measure the speed, don't claim it

```
Write scripts/calibrate.sh. Run the ASR lane on a long sample and store the realtime
factor (seconds of audio per second of wall clock) in config/engine.json, with the machine
and the date. The README must quote only this measured number, name the machine, and state
what it excludes. For any platform not measured, say "no number yet".
```

**Check:** `engine.json` holds a real measured figure (mine: 13.36x on an Apple M4).

---

### Prompt 6 - The summary skill

```
Write transcript-to-summary/SKILL.md as a prompt-only skill with no code. It accepts
.txt/.md/.srt/.vtt/.json or pasted text. First check whether speaker labels actually
exist and branch on that - don't assume them. Output: key points, decisions, action items
(owner and date only if stated), quotes (verbatim only), chapter outline. If handed audio
or video, point to /transcript instead of trying.
```

**Check:** run it on a transcript with no names in it and confirm no owners get invented.
