#!/usr/bin/env python3
"""Stage 3 -- Perceive Gate: turn a .pptx into something that can actually be looked at.

Fallback chain (best fidelity first, most portable last -- see standards/deck.md):
  1. LibreOffice headless (`soffice --headless --convert-to pdf`) -- cross-platform, the
     primary path for this skill.
  2. Windows-only: PowerPoint COM automation via pywin32, if PowerPoint is installed.
  3. Last resort: python-pptx-only geometry checks (shape bounding-box overlap/overflow
     in EMUs). No visual render -- catches binary-critical #1/#2 only, cannot check
     contrast, chart integrity, or rasterized-gradient legibility. Reported honestly.

Usage:
    render_preview.py <deck.pptx> [--out-dir render/]
"""
import argparse
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from pptx import Presentation
from pptx.util import Emu

LIBREOFFICE_CANDIDATES = [
    "soffice", "libreoffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
]


def find_libreoffice():
    for candidate in LIBREOFFICE_CANDIDATES:
        found = shutil.which(candidate)
        if found:
            return found
        if Path(candidate).exists():
            return candidate
    return None


def render_via_libreoffice(pptx_path: Path, out_dir: Path):
    soffice = find_libreoffice()
    if not soffice:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(pptx_path)],
        capture_output=True, text=True, timeout=120,
    )
    pdf_path = out_dir / (pptx_path.stem + ".pdf")
    if result.returncode == 0 and pdf_path.exists():
        return {"tier": "libreoffice", "pdf": str(pdf_path), "stdout": result.stdout[-500:]}
    return None


def render_via_com(pptx_path: Path, out_dir: Path):
    if platform.system() != "Windows":
        return None
    try:
        import win32com.client  # noqa: F401 -- optional, Windows + PowerPoint only
    except ImportError:
        return None
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = out_dir / (pptx_path.stem + ".pdf")
        powerpoint = win32com.client.Dispatch("PowerPoint.Application")
        deck = powerpoint.Presentations.Open(str(pptx_path.resolve()), WithWindow=False)
        deck.SaveAs(str(pdf_path.resolve()), 32)  # 32 = ppSaveAsPDF
        deck.Close()
        powerpoint.Quit()
        if pdf_path.exists():
            return {"tier": "powerpoint-com", "pdf": str(pdf_path)}
    except Exception as err:  # noqa: BLE001 -- COM automation is inherently fragile
        return {"tier": "powerpoint-com", "error": str(err)}
    return None


BACKGROUND_SHAPE_NAME = "html-to-ppt:background"  # must match build_pptx.py


def geometry_only_check(pptx_path: Path):
    """Last-resort tier: overlap (#1) and overflow (#2) via bounding-box maths, no render.

    A full-slide background shape is *supposed* to sit underneath every other shape --
    that's not what rubric item #1 is about, so it's excluded from pairwise checks.
    """
    prs = Presentation(str(pptx_path))
    findings = []
    for si, slide in enumerate(prs.slides):
        boxes = []
        for shape in slide.shapes:
            if shape.left is None or shape.top is None:
                continue
            if getattr(shape, "name", "") == BACKGROUND_SHAPE_NAME:
                continue
            boxes.append((shape.shape_id, shape.left, shape.top,
                          (shape.width or Emu(0)), (shape.height or Emu(0)), shape))
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                _, l1, t1, w1, h1, s1 = boxes[i]
                _, l2, t2, w2, h2, s2 = boxes[j]
                if l1 < l2 + w2 and l2 < l1 + w1 and t1 < t2 + h2 and t2 < t1 + h1:
                    findings.append({
                        "slide": si + 1, "issue": "overlap",
                        "shapes": [_shape_label(s1), _shape_label(s2)],
                    })
        slide_w, slide_h = prs.slide_width, prs.slide_height
        for shape_id, l, t, w, h, s in boxes:
            if l < 0 or t < 0 or l + w > slide_w or t + h > slide_h:
                findings.append({"slide": si + 1, "issue": "off-slide-or-overflow", "shape": _shape_label(s)})
    return findings


def _shape_label(shape):
    if shape.has_text_frame and shape.text_frame.text.strip():
        return shape.text_frame.text.strip()[:40]
    return shape.shape_type.__str__() if shape.shape_type else "shape"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pptx", type=Path)
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args()

    out_dir = args.out_dir or args.pptx.parent / (args.pptx.stem + "_render")
    report = {"pptx": str(args.pptx), "tier": None, "detail": None, "geometry_findings": None}

    lo = render_via_libreoffice(args.pptx, out_dir)
    if lo:
        report.update({"tier": "libreoffice", "detail": lo})
    else:
        com = render_via_com(args.pptx, out_dir)
        if com and com.get("pdf"):
            report.update({"tier": "powerpoint-com", "detail": com})
        else:
            findings = geometry_only_check(args.pptx)
            report.update({
                "tier": "geometry-only",
                "detail": {"note": ("No renderer available (LibreOffice not found" +
                                     (", PowerPoint COM failed" if com else "") +
                                     "). Visual checks (#3 contrast, #9 chart integrity, "
                                     "rasterized-gradient legibility) were SKIPPED -- this is "
                                     "reduced coverage, not a clean bill of health.")},
                "geometry_findings": findings,
            })

    report_path = out_dir.parent / (args.pptx.stem + ".render_report.json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("render tier used: " + str(report["tier"]))
    print("render report: " + str(report_path))
    if report["tier"] == "geometry-only":
        print("WARNING: " + report["detail"]["note"], file=sys.stderr)
        if report["geometry_findings"]:
            print(str(len(report["geometry_findings"])) + " geometry issue(s) found -- see report.", file=sys.stderr)


if __name__ == "__main__":
    main()
