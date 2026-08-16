#!/usr/bin/env python3
"""
transcript — local video/audio -> transcript. Domain-agnostic. Nothing leaves the machine.

Pipeline:
    media --ffmpeg--> 16kHz mono wav
                 |
        +--------+--------+
    [ASR lane]        [CPU lane]
  mlx-whisper OR      pyannote diarize   (subprocess, runs concurrently)
 faster-whisper
  (backend picked
   by what's
   importable)
        +--------+--------+
             merge on timestamp overlap
                 |
      .txt .srt .vtt .json .md .manifest.json
"""

import argparse
import json
import os
import subprocess
import sys
import time
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
CONFIG = SKILL / "config" / "engine.json"

DEFAULT_MODEL = {
    "mlx": "mlx-community/whisper-large-v3-turbo",
    "faster": "large-v3-turbo",
}
FASTER_MODEL_FALLBACK = "large-v3"  # official Systran repo, used if the turbo community repo fails to load
MEDIA_EXT = {
    ".mp4", ".mov", ".mkv", ".avi", ".webm", ".flv", ".m4v", ".mpg", ".mpeg", ".wmv",
    ".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg", ".opus", ".wma", ".aiff",
}


class MediaError(Exception):
    """A failure affecting ONE file — a corrupt container, a video with no audio
    stream, an ffmpeg decode error.

    Deliberately an Exception, not SystemExit: the batch loop catches Exception so
    that one unreadable file is reported and skipped instead of killing a folder
    run half-way through. Reserve SystemExit for conditions that make the WHOLE
    run impossible (no ffmpeg, no ASR backend, bad arguments).
    """


# ---------------------------------------------------------------- utilities

def log(msg):
    print(f"  {msg}", flush=True)


def hhmmss(sec):
    sec = max(0.0, float(sec))
    h, rem = divmod(int(sec), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def ts_srt(sec):
    sec = max(0.0, float(sec))
    ms = int(round((sec - int(sec)) * 1000))
    if ms == 1000:  # rounding carry
        sec, ms = int(sec) + 1, 0
    h, rem = divmod(int(sec), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def ts_vtt(sec):
    return ts_srt(sec).replace(",", ".")


def find_ffmpeg():
    """
    Resolve an ffmpeg binary AND guarantee it's reachable on PATH as plain `ffmpeg`
    (`ffmpeg.exe` on Windows).

    imageio-ffmpeg ships it under a versioned name (e.g. `ffmpeg-macos-aarch64-v7.1`,
    `ffmpeg-win-x86_64-v7.1.exe`), but mlx-whisper (and yt-dlp) shell out to the bare
    name. So when the resolved binary isn't called that, drop a correctly-named shim
    next to the venv python and prepend it to PATH — a symlink where possible, falling
    back to a copy where it isn't (e.g. non-admin/non-Developer-Mode Windows, where
    symlink creation raises a permission error).
    """
    from shutil import which, copy2

    exe = which("ffmpeg") or which("ffmpeg.exe")
    if not exe:
        try:
            import imageio_ffmpeg

            exe = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            exe = None
    if not exe:
        raise SystemExit(
            "ffmpeg not found.\nFix: run scripts/setup.sh (Mac) or scripts/setup.ps1 (Windows)"
        )

    shim_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    if Path(exe).name != shim_name:
        shim = Path(sys.executable).parent
        link = shim / shim_name
        if not link.exists():
            try:
                link.symlink_to(exe)
            except OSError:
                try:
                    copy2(exe, link)
                    if os.name != "nt":
                        os.chmod(link, 0o755)
                except OSError:
                    pass
        if link.exists():
            exe = str(link)
        os.environ["PATH"] = f"{shim}{os.pathsep}{os.environ.get('PATH', '')}"

    return exe


def wav_duration(path):
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def load_wav(path):
    """
    16-bit PCM wav -> float32 numpy in [-1, 1], which is what whisper wants.
    We already decoded the media ourselves, so handing whisper the array directly
    saves it re-decoding the whole file a second time.
    """
    import numpy as np

    with wave.open(str(path), "rb") as w:
        frames = w.readframes(w.getnframes())
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0


# ---------------------------------------------------------------- stages

def extract_audio(src, dst, ffmpeg):
    """Decode to 16 kHz mono 16-bit PCM — what both whisper and pyannote want."""
    cmd = [
        ffmpeg, "-nostdin", "-loglevel", "error", "-y",
        "-i", str(src),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
        str(dst),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not dst.exists():
        # MediaError, not SystemExit: this is a per-FILE failure. SystemExit derives
        # from BaseException, so the batch loop's `except Exception` could not catch
        # it and a single corrupt file (or a video with no audio stream) aborted the
        # entire folder run part-way through.
        raise MediaError(f"ffmpeg failed on {src.name}:\n{r.stderr.strip()[:2000]}")
    return dst


def start_diarization(wav, out_json, serial=False):
    """Launch the CPU lane. Returns a Popen, or None if unavailable."""
    if not os.environ.get("HF_TOKEN") and not os.environ.get("HUGGINGFACE_TOKEN"):
        log("! HF_TOKEN not set -> speaker labels OFF (transcript still produced).")
        log("  See SETUP.md step 3-4 to enable diarization.")
        return None
    proc = subprocess.Popen(
        [sys.executable, str(HERE / "diarize.py"), str(wav), str(out_json)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    log(f"[cpu lane] diarization started (pid {proc.pid})")
    if serial:
        # communicate(), never wait(): nothing drains the pipe while the child runs,
        # and pyannote's first-run weight-download progress easily exceeds the ~64KB
        # OS pipe buffer — at which point the child blocks writing and the parent
        # blocks in wait() forever. communicate() reads and waits together.
        out, _ = proc.communicate()
        proc._captured_output = out  # consumed by the failure path in transcribe_one
    return proc


def detect_backend():
    """
    Capability probe, not an OS check: whichever ASR package is actually importable
    wins. mlx-whisper only has wheels for Apple Silicon, so it's tried first (it's the
    faster, measured path) and simply isn't importable anywhere else.
    """
    try:
        import mlx_whisper  # noqa: F401

        return "mlx"
    except ImportError:
        pass
    try:
        import faster_whisper  # noqa: F401

        return "faster"
    except ImportError:
        pass
    raise SystemExit(
        "No ASR backend installed.\nFix: run scripts/setup.sh (Mac) or scripts/setup.ps1 (Windows)"
    )


def run_asr_mlx(wav, model, language, hint):
    import mlx_whisper

    kwargs = {
        "path_or_hf_repo": model,
        "word_timestamps": False,
        "condition_on_previous_text": False,  # prevents runaway repetition loops
        "verbose": None,
    }
    if language:
        kwargs["language"] = language
    if hint:
        kwargs["initial_prompt"] = hint

    return mlx_whisper.transcribe(load_wav(wav), **kwargs)


def run_asr_faster(wav, model, language, hint):
    """
    Non-Apple-Silicon path (Windows, Intel Mac, Linux) via faster-whisper/CTranslate2.
    vad_filter=False matches mlx-whisper's plain sequential decode — the batched
    pipeline's default vad_filter=True would shift segment boundaries and break the
    diarization speaker-attach merge downstream.
    """
    from faster_whisper import WhisperModel

    def load(model_id):
        try:
            return WhisperModel(model_id, device="auto", compute_type="auto")
        except Exception:
            return WhisperModel(model_id, device="auto", compute_type="int8")

    try:
        m = load(model)
    except Exception:
        if model == DEFAULT_MODEL["faster"]:
            # community turbo conversion unavailable -> fall back to the official repo
            m = load(FASTER_MODEL_FALLBACK)
        else:
            raise

    kwargs = {"condition_on_previous_text": False, "vad_filter": False}
    if language:
        kwargs["language"] = language
    if hint:
        kwargs["initial_prompt"] = hint

    segments, info = m.transcribe(load_wav(wav), **kwargs)
    segs = [{"start": s.start, "end": s.end, "text": s.text} for s in segments]
    return {"language": info.language, "segments": segs}


# ---------------------------------------------------------------- merge

def attach_speakers(segments, turns):
    """
    Assign each ASR segment the speaker whose diarization turns overlap it most.
    turns: [{start, end, speaker}]. Pure interval arithmetic - no model involved.
    """
    if not turns:
        return segments

    turns = sorted(turns, key=lambda t: t["start"])
    starts = [t["start"] for t in turns]
    import bisect

    for seg in segments:
        s, e = seg["start"], seg["end"]
        # first turn that could overlap
        i = max(0, bisect.bisect_left(starts, s) - 1)
        best, best_ov = None, 0.0
        while i < len(turns) and turns[i]["start"] < e:
            ov = min(e, turns[i]["end"]) - max(s, turns[i]["start"])
            if ov > best_ov:
                best, best_ov = turns[i]["speaker"], ov
            i += 1
        seg["speaker"] = best
    return segments


# ---------------------------------------------------------------- writers

def write_txt(segs, path):
    """[HH:MM:SS] text -- byte-format-identical to the prior LSSBB output."""
    with open(path, "w", encoding="utf-8") as f:
        for s in segs:
            f.write(f"[{hhmmss(s['start'])}] {s['text'].strip()}\n")


def write_srt(segs, path):
    with open(path, "w", encoding="utf-8") as f:
        for i, s in enumerate(segs, 1):
            spk = f"[{s['speaker']}] " if s.get("speaker") else ""
            f.write(f"{i}\n{ts_srt(s['start'])} --> {ts_srt(s['end'])}\n{spk}{s['text'].strip()}\n\n")


def write_vtt(segs, path):
    with open(path, "w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")
        for s in segs:
            spk = f"[{s['speaker']}] " if s.get("speaker") else ""
            f.write(f"{ts_vtt(s['start'])} --> {ts_vtt(s['end'])}\n{spk}{s['text'].strip()}\n\n")


def write_json(segs, path, name, duration, language):
    payload = {
        "file": name,
        "duration_sec": duration,
        "language": language,
        "segments": [
            {k: v for k, v in (
                ("start", s["start"]), ("end", s["end"]),
                ("text", s["text"].strip()), ("speaker", s.get("speaker")),
            ) if not (k == "speaker" and v is None)}
            for s in segs
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, ensure_ascii=False)


MD_MAX_PARA_SEC = 75.0   # cap a paragraph's span
MD_GAP_SEC = 2.5         # a pause this long is a natural paragraph break


def write_md(segs, path, name, duration, language):
    """
    Readable doc. Deterministic string joining only - no model rewrites the words.

    A paragraph breaks on any of: speaker change, a pause longer than MD_GAP_SEC, or
    MD_MAX_PARA_SEC of accumulated speech. The last two matter most when there are no
    speaker labels, which would otherwise yield one unreadable wall of text.
    """
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# {name}\n\n")
        f.write(f"*{hhmmss(duration)} · language: {language or 'auto'}*\n\n---\n\n")

        block, cur = [], None

        def flush():
            if not block:
                return
            head = f"**{cur}** " if cur else ""
            f.write(f"{head}`[{hhmmss(block[0]['start'])}]`\n\n")
            f.write(" ".join(s["text"].strip() for s in block) + "\n\n")

        for s in segs:
            spk = s.get("speaker")
            if block:
                too_long = s["end"] - block[0]["start"] > MD_MAX_PARA_SEC
                gap = s["start"] - block[-1]["end"] > MD_GAP_SEC
                if spk != cur or too_long or gap:
                    flush()
                    block = []
            cur = spk
            block.append(s)
        flush()


# ---------------------------------------------------------------- driver

def transcribe_one(src, outdir, args, ffmpeg, backend):
    import tempfile

    name = src.stem
    outdir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    print(f"\n=== {src.name}")

    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "audio.wav"
        dia_json = Path(tmp) / "diar.json"

        t = time.time()
        extract_audio(src, wav, ffmpeg)
        duration = wav_duration(wav)
        log(f"decoded {hhmmss(duration)} of audio in {time.time()-t:.1f}s")

        dia = None
        if not args.no_diarize:
            dia = start_diarization(wav, dia_json, serial=args.serial)

        log(f"[gpu lane] ASR ({backend}): {args.model}")
        t_asr = time.time()
        run_fn = run_asr_mlx if backend == "mlx" else run_asr_faster
        result = run_fn(wav, args.model, args.lang, args.hint)
        asr_sec = time.time() - t_asr
        language = result.get("language")
        segs = [
            {"start": float(s["start"]), "end": float(s["end"]), "text": s["text"]}
            for s in result.get("segments", [])
            if s.get("text", "").strip()
        ]
        log(f"[gpu lane] done in {asr_sec/60:.1f} min  ({duration/asr_sec:.1f}x realtime, "
            f"{len(segs)} segments, lang={language})")

        turns = []
        if dia is not None:
            # In --serial mode start_diarization already drained the pipe; calling
            # communicate() a second time on a finished process would raise.
            out = getattr(dia, "_captured_output", None)
            if out is None:
                out, _ = dia.communicate()
            if dia.returncode == 0 and dia_json.exists():
                turns = json.loads(dia_json.read_text())
                spk = sorted({t_["speaker"] for t_ in turns})
                log(f"[cpu lane] {len(turns)} turns, {len(spk)} speakers: {', '.join(spk)}")
            else:
                log("! diarization failed -> flat transcript. Detail:")
                for line in (out or "").strip().splitlines()[-6:]:
                    log(f"    {line}")

        if turns:
            segs = attach_speakers(segs, turns)

    write_txt(segs, outdir / f"{name}.txt")
    write_srt(segs, outdir / f"{name}.srt")
    write_vtt(segs, outdir / f"{name}.vtt")
    write_json(segs, outdir / f"{name}.json", name, duration, language)
    write_md(segs, outdir / f"{name}.md", name, duration, language)

    wall = time.time() - t0
    manifest = {
        "file": name,
        "source": str(src),
        "duration_sec": round(duration, 2),
        "language": language,
        "model": args.model,
        "diarized": bool(turns),
        "speakers": len(sorted({s.get("speaker") for s in segs if s.get("speaker")})),
        "segments": len(segs),
        "asr_sec": round(asr_sec, 1),
        "wall_sec": round(wall, 1),
        "asr_realtime_factor": round(duration / asr_sec, 2) if asr_sec else None,
        "wall_realtime_factor": round(duration / wall, 2) if wall else None,
        "flags": {"hint": args.hint, "lang": args.lang, "serial": args.serial,
                  "no_diarize": args.no_diarize},
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "tool": f"transcript skill (local, {backend}-whisper)",
    }
    (outdir / f"{name}.manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    log(f"TOTAL {wall/60:.1f} min for {hhmmss(duration)} "
        f"({duration/wall:.1f}x realtime) -> {outdir}")
    return manifest


def main():
    p = argparse.ArgumentParser(
        prog="transcript",
        description="Local video/audio -> transcript. Nothing leaves this machine.",
    )
    p.add_argument("input", help="media file, or a directory to batch")
    p.add_argument("--out", help="output dir (default: alongside the source)")
    p.add_argument("--model", help="ASR model id (default depends on the detected backend)")
    p.add_argument("--lang", help="force language code, e.g. en (default: auto-detect)")
    p.add_argument("--hint", help="free-text primer for names/acronyms in this recording")
    p.add_argument("--no-diarize", action="store_true", help="skip speaker labels")
    p.add_argument("--serial", action="store_true", help="run lanes one at a time (lower load)")
    args = p.parse_args()

    src = Path(args.input).expanduser().resolve()
    if not src.exists():
        raise SystemExit(f"not found: {src}")

    if src.is_dir():
        files = sorted(f for f in src.iterdir() if f.suffix.lower() in MEDIA_EXT)
        if not files:
            raise SystemExit(f"no media files in {src}")
    else:
        files = [src]

    backend = detect_backend()
    args.model = args.model or DEFAULT_MODEL[backend]

    ffmpeg = find_ffmpeg()
    print(f"transcript · {len(files)} file(s) · backend={backend} · model={args.model} · local-only")

    run0 = time.time()
    done = []
    for f in files:
        outdir = Path(args.out).expanduser().resolve() if args.out else f.parent
        try:
            done.append(transcribe_one(f, outdir, args, ffmpeg, backend))
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"!! FAILED {f.name}: {e}", file=sys.stderr)

    if len(files) > 1:
        total = time.time() - run0
        audio = sum(m["duration_sec"] for m in done)
        print(f"\n{len(done)}/{len(files)} ok · {hhmmss(audio)} audio in "
              f"{total/60:.1f} min ({audio/total:.1f}x realtime)")
    if not done:
        sys.exit(1)


if __name__ == "__main__":
    main()
