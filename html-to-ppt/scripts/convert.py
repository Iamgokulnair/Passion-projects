#!/usr/bin/env python3
"""Thin CLI orchestrator: HTML -> manifest -> .pptx -> render -> fidelity check.

This is the scripted, deterministic backbone of the pipeline. SKILL.md wraps this with
the parts that need judgment -- Step 0 intake, Step 1 content-mapping (which can override
the default heuristic plan this script falls back to), and Step 6's independent QA pass.
Running this file directly (as `setup.sh --check` does against examples/sample.html) is a
full smoke test of everything BUT that judgment layer.

Usage:
    convert.py <input.html> [--out deck.pptx] [--plan slide_plan.json]
"""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent


def run(*args, tolerate=(0, 1)):
    """Run a stage. Exit codes in `tolerate` are reported but do not abort the run.

    1  = "checked, found problems, reported them" (verify_fidelity FAIL, degraded render)
    2  = geometry findings from the Perceive Gate — real, located defects
    """
    print("$ " + " ".join(str(a) for a in args))
    result = subprocess.run([sys.executable, *args], cwd=str(HERE))
    if result.returncode not in tolerate:
        sys.exit(result.returncode)
    return result.returncode


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--plan", type=Path, default=None)
    args = ap.parse_args()

    input_path = args.input.resolve()
    out_path = (args.out or input_path.with_suffix(".pptx")).resolve()
    manifest_path = input_path.with_suffix(".manifest.json")
    assets_dir = input_path.parent / (input_path.stem + "_assets")

    print("== Stage 1: parse ==")
    run(str(HERE / "parse_html.py"), str(input_path), "--out", str(manifest_path), "--assets-dir", str(assets_dir))

    print("\n== Stage 2: build ==")
    build_args = [str(HERE / "build_pptx.py"), str(manifest_path), "--out", str(out_path)]
    if args.plan:
        build_args += ["--plan", str(args.plan)]
    run(*build_args)

    print("\n== Stage 3: render (Perceive Gate) ==")
    render_exit = run(str(HERE / "render_preview.py"), str(out_path), tolerate=(0, 1, 2))

    print("\n== Stage 4: fidelity check ==")
    build_report = out_path.with_suffix(".build_report.json")
    fidelity_exit = run(str(HERE / "verify_fidelity.py"), str(out_path), str(build_report))

    print("\n== Done ==")
    print("deck: " + str(out_path))

    problems = []
    if fidelity_exit == 1:
        problems.append("content-fidelity check FAILED -- see "
                        + str(out_path.with_suffix(".fidelity_report.json")))
    if render_exit == 2:
        problems.append("Perceive Gate found geometry defects (overlap / off-slide) -- see "
                        + str(out_path.with_suffix(".render_report.json")))
    elif render_exit == 1:
        problems.append("no visual render was produced -- visual checks were SKIPPED, "
                        "which is reduced coverage, not a pass")
    if problems:
        for p in problems:
            print("FAIL: " + p, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
