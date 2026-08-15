"""The agent-reach lane. Nothing else in this skill touches the network.

Two backends, both from agent-reach's own reference docs:
  * web    -> Jina Reader  (curl https://r.jina.ai/<url>)
  * search -> Exa          (mcporter call 'exa.web_search_exa(...)')

THE CRITICAL DETAIL
-------------------
The default Jina call returns the page *shell* for every one of these tracker
sites — the price figures are injected after hydration, so a plain read comes
back with the FAQ text and zero numbers. Sending `x-timeout` makes the reader
wait for the browser to settle, and the figures appear.

Measured 2026-08-15 on producthistory.in:
    no header  -> 2,256 bytes, 0 price fields
    x-timeout  -> 4,135 bytes, Lowest/Average/Highest all present

If this skill ever starts returning empty bands across every source at once,
check this header first.
"""
from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from .util import load_config, now_iso


class FetchResult:
    __slots__ = ("url", "text", "ok", "error", "fetched_at")

    def __init__(self, url, text="", ok=False, error=None):
        self.url = url
        self.text = text
        self.ok = ok
        self.error = error
        self.fetched_at = now_iso()

    def __repr__(self):
        state = "ok" if self.ok else f"FAIL({self.error})"
        return f"<FetchResult {self.url} {state} {len(self.text)}b>"


def read_url(url: str, cfg: dict | None = None) -> FetchResult:
    """Read one page through the agent-reach web channel (Jina Reader)."""
    cfg = cfg or load_config()
    fc = cfg["fetch"]
    target = fc["reader"] + url

    last = None
    for attempt in range(fc["retries"] + 1):
        req = urllib.request.Request(target, method="GET")
        for k, v in fc["headers"].items():
            req.add_header(k, str(v))
        req.add_header("Accept", "text/plain")
        try:
            with urllib.request.urlopen(req, timeout=fc["timeout_seconds"]) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            if len(body) < 200:
                last = f"thin response ({len(body)}b)"
            else:
                return FetchResult(url, body, ok=True)
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            # 4xx other than 429 will not fix themselves on retry.
            if e.code != 429 and 400 <= e.code < 500:
                break
        except Exception as e:  # noqa: BLE001 - network layer, report don't crash
            last = type(e).__name__
        if attempt < fc["retries"]:
            import time

            time.sleep(fc["backoff_seconds"] * (attempt + 1))

    return FetchResult(url, ok=False, error=last or "unknown")


def read_many(urls: list[str], cfg: dict | None = None) -> list[FetchResult]:
    """Read pages in parallel. A dead source yields a failed result, never an exception."""
    cfg = cfg or load_config()
    if not urls:
        return []
    workers = min(cfg["fetch"]["parallel_workers"], len(urls))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda u: read_url(u, cfg), urls))


def exa_search(query: str, num_results: int = 8) -> list[str]:
    """Resolve a product name to candidate tracker URLs via agent-reach's Exa channel.

    Shells out to mcporter exactly as agent-reach/references/search.md prescribes.
    Returns [] if Exa is unavailable — the caller degrades to ASIN-keyed lookup.
    """
    call = f'exa.web_search_exa(query: "{query}", numResults: {num_results})'
    try:
        proc = subprocess.run(
            ["mcporter", "call", call],
            capture_output=True, text=True, timeout=90,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []

    import re

    urls = re.findall(r"https?://[^\s\"',)\]]+", proc.stdout)
    seen, out = set(), []
    for u in urls:
        u = u.rstrip(".,)")
        if u.startswith("http") and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def preflight() -> dict:
    """Is the agent-reach lane actually up? Reported before any run."""
    status = {"reader": False, "exa": False, "detail": {}}

    probe = read_url("https://example.com")
    status["reader"] = probe.ok
    status["detail"]["reader"] = "ok" if probe.ok else str(probe.error)

    try:
        proc = subprocess.run(
            ["agent-reach", "doctor", "--json"],
            capture_output=True, text=True, timeout=60,
        )
        doc = json.loads(proc.stdout)
        status["exa"] = doc.get("exa_search", {}).get("status") == "ok"
        status["detail"]["exa"] = doc.get("exa_search", {}).get("status", "unknown")
        status["detail"]["web"] = doc.get("web", {}).get("status", "unknown")
    except Exception as e:  # noqa: BLE001
        status["detail"]["exa"] = f"agent-reach doctor unavailable ({type(e).__name__})"

    return status
