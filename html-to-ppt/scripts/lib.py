"""Shared helpers for the html-to-ppt pipeline. No external deps beyond the stdlib."""
import re

EMU_PER_INCH = 914400
PX_PER_INCH = 96  # CSS reference pixel

# Slide canvas, 16:9, inches (matches standards/deck.md's layout archetypes)
SLIDE_WIDTH_IN = 13.333
SLIDE_HEIGHT_IN = 7.5

# Fonts guaranteed present on both a fresh macOS and a fresh Windows install.
# Source-HTML font-family names get mapped to the closest of these; every
# substitution is logged, never applied silently.
SAFE_FONTS = {
    "sans": "Arial",
    "sans-condensed": "Arial Narrow",
    "serif": "Georgia",
    "serif-classic": "Times New Roman",
    "system": "Calibri",
    "mono": "Courier New",
}

_SANS_HINTS = ("helvetica", "arial", "roboto", "inter", "sf pro", "segoe", "system-ui",
               "-apple-system", "sans-serif", "poppins", "montserrat", "open sans", "lato")
_SERIF_HINTS = ("georgia", "times", "serif", "garamond", "playfair", "merriweather")
_MONO_HINTS = ("mono", "courier", "consolas", "menlo", "monaco")


def px_to_emu(px: float) -> int:
    return round(px / PX_PER_INCH * EMU_PER_INCH)


def px_to_in(px: float) -> float:
    return px / PX_PER_INCH


def safe_font(css_font_family: str) -> tuple[str, bool]:
    """Map a CSS font-family stack to a cross-platform-safe font.

    Returns (font_name, was_substituted).
    """
    if not css_font_family:
        return SAFE_FONTS["system"], True
    stack = css_font_family.lower()
    first = stack.split(",")[0].strip().strip("'\"")
    if first in ("arial", "helvetica", "calibri", "georgia", "times new roman", "courier new"):
        # Already a safe font by exact name.
        canonical = {"helvetica": "Arial"}.get(first, first.title() if first != "times new roman" else "Times New Roman")
        return (canonical if first != "calibri" else "Calibri"), False
    if any(h in stack for h in _MONO_HINTS):
        return SAFE_FONTS["mono"], True
    if any(h in stack for h in _SERIF_HINTS):
        return SAFE_FONTS["serif"], True
    if any(h in stack for h in _SANS_HINTS):
        return SAFE_FONTS["sans"], True
    return SAFE_FONTS["system"], True


def rgb_str_to_hex(color: str) -> str | None:
    """'rgb(102, 126, 234)' / 'rgba(102, 126, 234, 0.5)' / '#667eea' -> '667EEA' (no alpha)."""
    if not color:
        return None
    color = color.strip()
    if color.startswith("#"):
        h = color.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return h[:6].upper() if len(h) >= 6 else None
    m = re.match(r"rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)", color)
    if m:
        r, g, b = (max(0, min(255, round(float(v)))) for v in m.groups())
        return f"{r:02X}{g:02X}{b:02X}"
    return None


def is_transparent(color: str) -> bool:
    if not color:
        return True
    c = color.strip().lower()
    if c in ("transparent", "none"):
        return True
    m = re.match(r"rgba\(\s*[\d.]+[,\s]+[\d.]+[,\s]+[\d.]+[,\s]+([\d.]+)\s*\)", c)
    if m and float(m.group(1)) == 0:
        return True
    return False


_LINEAR_RE = re.compile(r"linear-gradient\(\s*(.*)\)", re.IGNORECASE | re.DOTALL)
_STOP_RE = re.compile(r"(rgba?\([^)]+\)|#[0-9a-fA-F]{3,8})\s*([\d.]+%)?")
_ANGLE_RE = re.compile(r"^\s*(-?[\d.]+)deg")
_ANGLE_KEYWORD = {
    "to top": 0, "to right": 90, "to bottom": 180, "to left": 270,
    "to top right": 45, "to bottom right": 135, "to bottom left": 225, "to top left": 315,
}


def parse_linear_gradient(css_value: str):
    """Parse a single `linear-gradient(...)` CSS function into (angle_deg, stops).

    stops: list of {"hex": "RRGGBB", "pos": 0.0-1.0}. Returns (None, []) if unparseable
    or if the value contains more than one gradient layer (multi-background — caller
    should treat that as 'complex' and rasterize instead).
    """
    if css_value.count("gradient(") != 1 or "linear-gradient" not in css_value:
        return None, []
    m = _LINEAR_RE.search(css_value)
    if not m:
        return None, []
    body = m.group(1)
    angle_deg = 135  # CSS default direction is "to bottom" but 135 is a sane visual default
    am = _ANGLE_RE.match(body)
    if am:
        angle_deg = float(am.group(1))
        body = body[am.end():].lstrip(", ")
    else:
        for kw, deg in _ANGLE_KEYWORD.items():
            if body.strip().lower().startswith(kw):
                angle_deg = deg
                body = body[len(kw):].lstrip(", ")
                break
        else:
            angle_deg = 180  # "to bottom" default when no direction is given

    stops = []
    matches = list(_STOP_RE.finditer(body))
    n = len(matches)
    for i, sm in enumerate(matches):
        hexcolor = rgb_str_to_hex(sm.group(1))
        if not hexcolor:
            continue
        pos_str = sm.group(2)
        if pos_str:
            pos = float(pos_str.strip("%")) / 100.0
        else:
            pos = i / max(1, n - 1) if n > 1 else 0.0
        stops.append({"hex": hexcolor, "pos": max(0.0, min(1.0, pos))})
    if len(stops) < 2:
        return None, []
    # PowerPoint measures gradient angle clockwise from 3 o'clock in 60000ths of a degree;
    # CSS measures clockwise from 12 o'clock (0deg = to top... no, "to top" via keyword above,
    # bare `Ndeg` in CSS is clockwise from "up"). Convert CSS-bare-deg -> PPTX convention.
    pptx_angle = (angle_deg + 270) % 360
    return pptx_angle, stops


def classify_background(background_image: str | None, background_color: str | None) -> dict:
    """Decide how a background should be rendered: solid / linear-gradient / rasterize.

    Mirrors standards/deck.md's three-tier gradient decision rule.
    """
    if background_image and background_image != "none":
        layers = background_image.count("gradient(")
        if layers == 1 and "linear-gradient" in background_image:
            angle, stops = parse_linear_gradient(background_image)
            if stops:
                return {"kind": "linear-gradient", "angle_deg": angle, "stops": stops}
        # radial/conic/multi-layer/unparseable -> rasterize
        return {"kind": "complex", "raw": background_image}
    if background_color and not is_transparent(background_color):
        hexcolor = rgb_str_to_hex(background_color)
        if hexcolor:
            return {"kind": "solid", "hex": hexcolor}
    return {"kind": "none"}
