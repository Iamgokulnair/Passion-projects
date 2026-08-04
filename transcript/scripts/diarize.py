#!/usr/bin/env python3
"""
Speaker diarization worker — the CPU lane.

Runs as a separate process so it executes concurrently with the GPU-bound ASR lane.
Reads a 16 kHz mono wav, writes [{start, end, speaker}] JSON.

Exits non-zero on any failure; the caller falls back to a flat transcript.
"""

import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

# Tried in order. community-1 is the pyannote 4.x pipeline; 3.1 is the 3.x one.
# Whichever the user has accepted the licence for will load.
PIPELINES = (
    "pyannote/speaker-diarization-community-1",
    "pyannote/speaker-diarization-3.1",
)


def load_pipeline(token):
    """Load the first available pipeline, tolerating the 3.x/4.x auth-kwarg rename."""
    import inspect

    from pyannote.audio import Pipeline

    # pyannote 4.x: token=...   pyannote 3.x: use_auth_token=...
    kwarg = "token" if "token" in inspect.signature(Pipeline.from_pretrained).parameters \
        else "use_auth_token"

    errors = []
    for name in PIPELINES:
        try:
            pipe = Pipeline.from_pretrained(name, **{kwarg: token})
            if pipe is not None:
                print(f"using {name}", file=sys.stderr)
                return pipe
            errors.append(f"{name}: returned None (licence not accepted?)")
        except Exception as e:
            errors.append(f"{name}: {type(e).__name__}: {e}")
    raise RuntimeError(
        "No diarization pipeline could be loaded. Accept the licence for one of these "
        "on huggingface.co and use a READ token — see SETUP.md.\n  " + "\n  ".join(errors)
    )


def main():
    if len(sys.argv) != 3:
        print("usage: diarize.py <wav> <out.json>", file=sys.stderr)
        return 2

    wav, out = sys.argv[1], sys.argv[2]
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
    if not token:
        print("HF_TOKEN not set", file=sys.stderr)
        return 3

    import torch

    pipe = load_pipeline(token)

    # Deliberately CPU: the GPU is saturated by the ASR lane running alongside, and
    # pyannote's MPS support is partial. Keeping it on CPU is what makes the two
    # lanes genuinely parallel instead of contending for the same device.
    pipe.to(torch.device("cpu"))

    ann = pipe(wav)

    turns = [
        {"start": round(seg.start, 3), "end": round(seg.end, 3), "speaker": speaker}
        for seg, _, speaker in ann.itertracks(yield_label=True)
    ]

    with open(out, "w") as f:
        json.dump(turns, f)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"diarization error: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
