#!/usr/bin/env python3
"""Stage 1 -- HTML -> structured JSON content manifest.

Primary path: Playwright (Chromium headless) reads *computed* styles (resolved CSS --
external stylesheets, cascade, custom properties all included), which is required for
faithful gradient/color/font extraction. Falls back to BeautifulSoup4 + tinycss2
(inline/<style>-block styles only, no cascade resolution) if Chromium isn't installed,
degrading loudly rather than silently.

Usage:
    parse_html.py <input.html> [--out manifest.json] [--assets-dir assets/]
"""
import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).parent))
from lib import classify_background  # noqa: E402

# Elements needing an image asset written to disk (gradients Tier 3 -- rasterize).
RASTERIZE_KINDS = {"complex"}

JS_EXTRACT = r"""
() => {
  const BLOCK_TAGS = new Set(['H1','H2','H3','H4','H5','H6','P','LI','TD','TH','BLOCKQUOTE','FIGCAPTION','DT','DD']);
  const BLOCK_DISPLAY = new Set(['block','list-item','table-cell','flex','grid','table-row']);
  const SKIP_TAGS = new Set(['SCRIPT','STYLE','NOSCRIPT','SVG','TEMPLATE']);

  function isBlockLike(el) {
    if (BLOCK_TAGS.has(el.tagName)) return true;
    return BLOCK_DISPLAY.has(getComputedStyle(el).display);
  }
  function hasBlockDescendant(el) {
    for (const child of el.children) {
      if (SKIP_TAGS.has(child.tagName)) continue;
      if (isBlockLike(child) || hasBlockDescendant(child)) return true;
    }
    return false;
  }
  function isVisible(el) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }
  function isTransparent(c) {
    if (!c) return true;
    const m = /rgba\(\s*[\d.]+[,\s]+[\d.]+[,\s]+[\d.]+[,\s]+([\d.]+)\s*\)/.exec(c);
    return c === 'transparent' || (m && parseFloat(m[1]) === 0);
  }
  function styleOf(el) {
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return {
      color: cs.color,
      background_color: cs.backgroundColor,
      background_image: cs.backgroundImage !== 'none' ? cs.backgroundImage : null,
      font_family: cs.fontFamily,
      font_size_px: parseFloat(cs.fontSize),
      font_weight: cs.fontWeight,
      font_style: cs.fontStyle,
      text_align: cs.textAlign,
      box: { x: r.x, y: r.y, w: r.width, h: r.height }
    };
  }
  function domPath(el) {
    const parts = [];
    let node = el;
    while (node && node.tagName && node !== document.body) {
      let idx = 1, sib = node.previousElementSibling;
      while (sib) { if (sib.tagName === node.tagName) idx++; sib = sib.previousElementSibling; }
      parts.unshift(node.tagName.toLowerCase() + ':nth-of-type(' + idx + ')');
      node = node.parentElement;
    }
    return 'body > ' + parts.join(' > ');
  }

  const results = [];
  let counter = 0;
  const makeId = () => 'el-' + String(++counter).padStart(4, '0');

  // Pass 1 -- background panels: any element with an explicit background (color isn't
  // inherited in CSS unless set, so this naturally finds real background containers,
  // not every ancestor).
  document.querySelectorAll('body *').forEach(el => {
    if (SKIP_TAGS.has(el.tagName) || !isVisible(el)) return;
    const cs = getComputedStyle(el);
    const hasBgImage = cs.backgroundImage && cs.backgroundImage !== 'none';
    const hasBgColor = !isTransparent(cs.backgroundColor);
    if (hasBgImage || hasBgColor) {
      results.push({ id: makeId(), type: 'background_panel', dom_path: domPath(el), style: styleOf(el) });
    }
  });

  // Pass 2 -- images.
  document.querySelectorAll('img').forEach(img => {
    if (!isVisible(img)) return;
    results.push({
      id: makeId(), type: 'image', dom_path: domPath(img),
      src: img.currentSrc || img.getAttribute('src') || '', alt: img.alt || '',
      style: styleOf(img)
    });
  });

  // Pass 3 -- tables (structured, not flattened into loose text blocks).
  document.querySelectorAll('table').forEach(table => {
    if (!isVisible(table)) return;
    const rows = [];
    table.querySelectorAll('tr').forEach(tr => {
      const cells = [];
      tr.querySelectorAll('td,th').forEach(cell => cells.push((cell.innerText || '').trim()));
      if (cells.length) rows.push(cells);
    });
    if (rows.length) results.push({ id: makeId(), type: 'table', dom_path: domPath(table), rows, style: styleOf(table) });
  });

  // Pass 4 -- leaf text blocks, document order, skipping table/img subtrees already handled.
  function walk(el) {
    if (SKIP_TAGS.has(el.tagName) || el.tagName === 'TABLE' || el.tagName === 'IMG') return;
    if (!isVisible(el)) return;
    if (isBlockLike(el) && !hasBlockDescendant(el)) {
      const text = (el.innerText || '').trim();
      if (text) {
        results.push({
          id: makeId(),
          type: el.tagName === 'LI' ? 'list_item' : (/^H[1-6]$/.test(el.tagName) ? 'heading' : 'text'),
          tag: el.tagName.toLowerCase(),
          level: /^H[1-6]$/.test(el.tagName) ? parseInt(el.tagName[1]) : null,
          dom_path: domPath(el),
          text,
          style: styleOf(el)
        });
      }
      return;
    }
    for (const child of el.children) walk(child);
  }
  walk(document.body);

  return results;
}
"""


def parse_with_playwright(html_path: Path, assets_dir: Path):
    from playwright.sync_api import sync_playwright

    elements = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 720}, device_scale_factor=2)
        page.goto(html_path.resolve().as_uri())
        page.wait_for_load_state("networkidle")
        raw = page.evaluate(JS_EXTRACT)

        for entry in raw:
            style = entry.get("style")
            if style:
                bg = classify_background(style.get("background_image"), style.get("background_color"))
                style["background"] = bg
                if bg["kind"] in RASTERIZE_KINDS:
                    # Rasterize this element's background as a PNG via a real screenshot.
                    assets_dir.mkdir(parents=True, exist_ok=True)
                    asset_path = assets_dir / f"{entry['id']}.png"
                    try:
                        xp = _dom_path_to_xpath(entry["dom_path"])
                        handle = page.query_selector("xpath=//" + xp)
                        if handle:
                            handle.screenshot(path=str(asset_path))
                            style["background"]["asset"] = str(asset_path)
                    except Exception as err:  # noqa: BLE001 -- best-effort, report and continue
                        style["background"]["asset_error"] = str(err)
            if entry.get("type") == "image" and entry.get("src"):
                entry["src_resolved"] = urljoin(html_path.resolve().as_uri(), entry["src"])
            elements.append(entry)

        browser.close()
    return elements, "playwright"


def _dom_path_to_xpath(dom_path: str) -> str:
    # 'body > div:nth-of-type(1) > h1:nth-of-type(1)' -> 'body/div[1]/h1[1]'
    parts = dom_path.split(" > ")
    xpath_parts = []
    for part in parts:
        m = re.match(r"([a-z0-9]+):nth-of-type\((\d+)\)", part)
        if m:
            xpath_parts.append(m.group(1) + "[" + m.group(2) + "]")
        else:
            xpath_parts.append(part)
    return "/".join(xpath_parts)


def parse_with_bs4(html_path: Path):
    """Degraded fallback: inline/<style>-block styles only, no cascade resolution."""
    from bs4 import BeautifulSoup

    warned = ("degraded mode: computed styles unavailable (Playwright/Chromium not installed) -- "
              "using inline style attributes and raw <style> blocks only, no CSS cascade resolution. "
              "Gradients defined in external stylesheets will NOT be detected.")
    print("WARNING: " + warned, file=sys.stderr)

    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    elements = []
    counter = 0
    BLOCK_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td", "th", "blockquote", "figcaption"}

    def inline_style_dict(tag):
        style_attr = tag.get("style", "")
        out = {}
        for decl in style_attr.split(";"):
            if ":" in decl:
                k, v = decl.split(":", 1)
                out[k.strip().lower()] = v.strip()
        return out

    for img in soup.find_all("img"):
        counter += 1
        elements.append({
            "id": "el-%04d" % counter, "type": "image", "dom_path": "unknown (bs4 fallback)",
            "src": img.get("src", ""), "alt": img.get("alt", ""),
            "style": {"background": {"kind": "none"}},
        })

    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
            if cells:
                rows.append(cells)
        if rows:
            counter += 1
            elements.append({"id": "el-%04d" % counter, "type": "table", "dom_path": "unknown (bs4 fallback)", "rows": rows})

    for tag in soup.find_all(BLOCK_TAGS):
        if tag.find(list(BLOCK_TAGS)):
            continue  # not a leaf, its children will be captured instead
        text = tag.get_text(strip=True)
        if not text:
            continue
        counter += 1
        inline = inline_style_dict(tag)
        bg = classify_background(None, inline.get("background-color") or inline.get("background"))
        elements.append({
            "id": "el-%04d" % counter,
            "type": "list_item" if tag.name == "li" else ("heading" if tag.name.startswith("h") else "text"),
            "tag": tag.name,
            "level": int(tag.name[1]) if tag.name.startswith("h") and len(tag.name) == 2 else None,
            "dom_path": "unknown (bs4 fallback)",
            "text": text,
            "style": {
                "color": inline.get("color"),
                "font_family": inline.get("font-family"),
                "background": bg,
            },
        })
    return elements, "bs4-fallback"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--assets-dir", type=Path, default=None)
    args = ap.parse_args()

    if not args.input.exists():
        print("error: " + str(args.input) + " not found", file=sys.stderr)
        sys.exit(1)

    out_path = args.out or args.input.with_suffix(".manifest.json")
    assets_dir = args.assets_dir or out_path.parent / (args.input.stem + "_assets")

    try:
        elements, mode = parse_with_playwright(args.input, assets_dir)
    except Exception as err:  # noqa: BLE001 -- Chromium missing/broken, degrade loudly
        print("WARNING: Playwright path failed (" + str(err) + "); falling back to bs4-only parsing.", file=sys.stderr)
        elements, mode = parse_with_bs4(args.input)

    manifest = {
        "source": str(args.input.resolve()),
        "parser_mode": mode,
        "element_count": len(elements),
        "elements": elements,
    }
    out_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("manifest: " + str(out_path) + "  (" + str(len(elements)) + " elements, mode=" + mode + ")")


if __name__ == "__main__":
    main()
