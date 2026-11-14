#!/usr/bin/env python3
"""Write or check the research-grade study's freeze record (FREEZE-research-grade.md).

    python3 scripts/freeze_research_grade.py           write the record
    python3 scripts/freeze_research_grade.py --check   exit 1 if any fingerprint has changed

The record fingerprints the files the preregistration names, on top of Study 1's freeze (FREEZE.md,
27 files), which must still match. The combined fingerprint is what this prints from pilot/:

    shasum -a 256 FILE ... | shasum -a 256

with the files in the order listed.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "FREEZE-research-grade.md")
FILES = [
    ("Texts", ["scenarios/workplace-c.json", "scenarios/neutral-c.json", "norms/norms.json"]),
    ("Code", ["norms/render_draft.py", "norms/run_norms.py", "analysis/research_grade.py",
              "analysis/research_grade_sim.py", "analysis/test_awareness.py", "tests/test_research_grade.py",
              "scripts/keep_going.py", "tests/test_keep_going.py"]),
    ("Preregistration", ["norms/PREREG-research-grade.md"]),
]


def sha(path: str) -> str:
    return hashlib.sha256(open(os.path.join(ROOT, path), "rb").read()).hexdigest()


def study1_ok() -> bool:
    rows = re.findall(r"`([^`]+)`\s*\|\s*`([0-9a-f]{64})`", open(os.path.join(ROOT, "FREEZE.md"), encoding="utf-8").read())
    return len(rows) == 27 and all(sha(p) == h for p, h in rows)


def combined(paths) -> str:
    return hashlib.sha256("".join(f"{sha(p)}  {p}\n" for p in paths).encode()).hexdigest()


def main() -> int:
    paths = [p for _, group in FILES for p in group]
    if "--check" in sys.argv[1:]:
        rows = re.findall(r"`([^`]+)`\s*\|\s*`([0-9a-f]{64})`", open(OUT, encoding="utf-8").read())
        changed = [p for p, h in rows if sha(p) != h]
        print("Study 1 freeze:", "matches" if study1_ok() else "BROKEN")
        print(f"Research-grade freeze: {len(rows)} files;", "changed: " + ", ".join(changed) if changed else "all match")
        return 0 if study1_ok() and not changed else 1
    if not study1_ok():
        print("Study 1's freeze (FREEZE.md) no longer matches; fix that first.")
        return 1
    lines = ["# Research-grade study freeze record", "",
             "Written 26 October 2026 by `scripts/freeze_research_grade.py`, after GPT Pro's outside review found the "
             "preregistration ready to freeze apart from Kevin's items, and Kevin approved those (\"That's all fine, "
             "all approved\"). It fixes the texts, code and analysis before any research-grade data exist. If any "
             "fingerprint below changes, the freeze is broken and this record must be rewritten before the run. "
             "Check with `python3 scripts/freeze_research_grade.py --check`.", "",
             "It sits on Study 1's freeze (`FREEZE.md`): its 27 files, among them the four original versions, the "
             "engine, `scripts/run_pilot.py`, `scripts/probe.py` and `scripts/reasons_digest.py`, still match.", "",
             f"Combined fingerprint of the files below (`shasum -a 256 FILE ... | shasum -a 256`, in this order): "
             f"`{combined(paths)}`", ""]
    for title, group in FILES:
        lines += [f"**{title}**", "", "| File | SHA-256 |", "|---|---|"] + [f"| `{p}` | `{sha(p)}` |" for p in group] + [""]
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
