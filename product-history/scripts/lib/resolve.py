"""Turn whatever the user pasted into a canonical identity + one URL per source.

Accepted input:
  * an amazon.in product URL   -> ASIN extracted from the URL itself
  * a bare ASIN                -> used directly
  * a flipkart.com URL         -> product name recovered from the slug
  * a free-text product name   -> searched as-is

No retailer page is ever fetched. Amazon and Flipkart URLs carry the product
name in the slug, so identity comes from the string the user already has —
one less network call, and one less site that can block us.
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote, urlparse

from .fetch import exa_search
from .parse import source_for_url

ASIN_RE = re.compile(r"\b(B0[A-Z0-9]{8})\b", re.I)

KNOWN_DOMAINS = ("pricehistory.app", "pricediff.in",
                 "pricehistoryapp.com", "producthistory.in")

_STOP = {"dp", "gp", "product", "ref", "www", "amazon", "in", "com",
         "flipkart", "p", "itm", "pid", "sspa"}


class Target:
    def __init__(self, raw, asin=None, name=None, marketplace=None):
        self.raw = raw
        self.asin = asin
        self.name = name
        self.marketplace = marketplace
        self.urls: dict[str, str] = {}

    @property
    def key(self) -> str:
        """Stable ledger key. ASIN when we have one, else a normalised name."""
        if self.asin:
            return f"asin:{self.asin.upper()}"
        slug = re.sub(r"[^a-z0-9]+", "-", (self.name or self.raw).lower()).strip("-")
        return f"name:{slug[:80]}"

    def __repr__(self):
        return f"<Target {self.key} name={self.name!r} sources={len(self.urls)}>"


def _name_from_slug(url: str):
    """Recover a product name from an Amazon/Flipkart URL slug."""
    path = unquote(urlparse(url).path)
    words = []
    for chunk in re.split(r"[/\-_]", path):
        c = chunk.strip().lower()
        if not c or c in _STOP or ASIN_RE.fullmatch(c or "") or c.isdigit():
            continue
        if len(c) > 30:
            continue
        words.append(chunk.strip())
    return " ".join(words[:12]) or None


def identify(raw: str) -> Target:
    raw = raw.strip()

    if ASIN_RE.fullmatch(raw):
        return Target(raw, asin=raw.upper(), marketplace="amazon.in")

    if raw.startswith("http"):
        host = (urlparse(raw).hostname or "").lower()
        asin_m = ASIN_RE.search(raw)
        marketplace = None
        if "amazon." in host:
            marketplace = "amazon.in" if host.endswith(".in") else host
        elif "flipkart." in host:
            marketplace = "flipkart.com"
        return Target(
            raw,
            asin=asin_m.group(1).upper() if asin_m else None,
            name=_name_from_slug(raw),
            marketplace=marketplace,
        )

    return Target(raw, name=raw)


def _queries(t: Target) -> list[str]:
    qs = []
    if t.asin:
        qs.append(f"{t.asin} price history India")
    if t.name:
        qs.append(f"{t.name} price history lowest price India")
    if not qs:
        qs.append(f"{t.raw} price history India")
    return qs


# Alphabetic variant markers. Two listings that disagree on these are two
# different products, however similar the rest of the name looks. This is the
# gate that stops "Airdopes 141 ANC" and "Airdopes 141 Gen 2" being averaged
# into one meaningless band.
VARIANT_MARKERS = {
    "anc", "pro", "plus", "max", "mini", "lite", "gen", "ultra", "se",
    "neo", "prime", "air", "active", "nc", "xl", "hd", "fe",
}

_NOISE = {"the", "with", "for", "and", "in", "of", "a", "an", "by",
          "wireless", "bluetooth", "earbuds", "earphones", "buds", "tws",
          "price", "history", "india", "online", "buy", "best"}


def _tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9.]+", (text or "").lower())
            if t and t not in _NOISE and len(t) > 1}


def identity_score(target_name: str | None, title: str | None) -> tuple[float, bool]:
    """(coverage, markers_agree) for a candidate page title vs the target.

    coverage      — share of the target's significant tokens present in the title
    markers_agree — the two names do not disagree on a variant marker
    """
    if not target_name or not title:
        return (0.0, True)  # nothing to contradict; caller decides

    tgt, cand = _tokens(target_name), _tokens(title)
    if not tgt:
        return (0.0, True)

    coverage = len(tgt & cand) / len(tgt)

    tgt_marks = tgt & VARIANT_MARKERS
    cand_marks = cand & VARIANT_MARKERS
    markers_agree = True
    if tgt_marks and not (tgt_marks & cand_marks):
        markers_agree = False          # target says ANC, candidate never does
    elif cand_marks - tgt_marks and not tgt_marks:
        markers_agree = False          # candidate is a variant we did not ask for

    return (round(coverage, 2), markers_agree)


def same_product(target_name: str | None, title: str | None,
                 min_coverage: float = 0.5) -> tuple[bool, str]:
    # No reference name (e.g. a bare /dp/ASIN URL carries no slug) means there
    # is nothing to contradict. Do not drop a source we cannot judge.
    if not target_name or not title:
        return True, ""
    cov, marks = identity_score(target_name, title)
    if not marks:
        return False, f"different variant (marker mismatch, coverage {cov})"
    if cov < min_coverage:
        return False, f"identity mismatch (coverage {cov} < {min_coverage})"
    return True, ""


def _harvest(urls: list[str], found: dict[str, str]) -> None:
    for url in urls:
        sid = source_for_url(url)
        if not sid or sid in found:
            continue
        # Skip category/listing pages — we want a product page.
        if not re.search(r"/(p|product)/", url):
            continue
        found[sid] = url.split("#")[0]


def resolve(raw: str, max_per_source: int = 1) -> Target:
    """Identify the product and find one URL per known tracker via Exa.

    Two passes. A broad query usually returns only the one or two sites Exa
    ranks highest for the product, which is not enough for a confidence grade —
    so any source still missing gets its own domain-scoped query, run in
    parallel. Coverage is what buys confidence here, and confidence is the
    whole product.
    """
    t = identify(raw)
    found: dict[str, str] = {}

    for q in _queries(t):
        _harvest(exa_search(q, num_results=12), found)
        if len(found) >= len(KNOWN_DOMAINS):
            break

    missing = [d for d in KNOWN_DOMAINS
               if not any(d in u for u in found.values())]
    if missing:
        label = t.name or t.asin or t.raw
        with ThreadPoolExecutor(max_workers=len(missing)) as pool:
            batches = pool.map(
                lambda d: exa_search(f"{d} {label} price history", num_results=8),
                missing,
            )
            for batch in batches:
                _harvest(batch, found)

    # ASIN cross-check: a pricediff URL embeds the ASIN, so a mismatch means
    # Exa returned the wrong product. Better no source than the wrong one.
    if t.asin and "pricediff_in" in found:
        if t.asin.lower() not in found["pricediff_in"].lower():
            found.pop("pricediff_in")

    t.urls = found
    return t
