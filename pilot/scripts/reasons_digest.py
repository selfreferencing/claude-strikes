#!/usr/bin/env python3
"""Every decision's stated reason, grouped by cell, as one Markdown file to read.

    python3 scripts/reasons_digest.py RUN_DIR [--out RUN_DIR/REASONS.md]

For each cell: one line per decision with its history, draw, version, label
scheme and option order, the outcome, and the reason the agent gave. Then the
comprehension answers that were wrong, with the question asked. Reasons are
quoted as the model gave them; nothing is coded here (section 7 codes reasons
later, with two humans and a model from another family).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from collections import defaultdict
from typing import List

PILOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PILOT_DIR not in sys.path:
    sys.path.insert(0, PILOT_DIR)

from strike import scenario as S  # noqa: E402


def load(pattern: str) -> List[dict]:
    out = []
    for path in sorted(glob.glob(pattern)):
        with open(path, encoding="utf-8") as f:
            out.append(json.load(f))
    return out


def one_line(text: str) -> str:
    return " ".join((text or "").split())


def digest(run_dir: str) -> str:
    with open(os.path.join(run_dir, "run.json"), encoding="utf-8") as f:
        cfg = json.load(f)["config"]
    slots = [s for s in load(os.path.join(run_dir, "slots", "*", "*.json")) if "parsed" in s]
    audits = [a for a in load(os.path.join(run_dir, "audits", "*", "*.json")) if a.get("done")]
    out = [f"# Reasons, run {cfg['run_id']}", "",
           "Each line: history and draw, version, labels, the order the options were offered, the outcome, "
           "and the agent's stated reason, quoted as given.", ""]
    by_cell = defaultdict(list)
    for s in slots:
        by_cell[s["cell"]].append(s)
    for cell in cfg["cells"]:
        ss = sorted(by_cell.get(cell, []), key=lambda s: (s["history"], s["draw"]))
        if not ss:
            continue
        out += [f"## {cell}", ""]
        for s in ss:
            order = s.get("option_order") or s.get("transfer_order") or []
            shown = "/".join(str(x) for x in order)
            reason = s["parsed"].get("reason") or "(no reason: " + s["parsed"].get("basis", "") + ")"
            out.append(f"- **{s['history']} d{s['draw']}** {s['version']}, {s.get('label_scheme', 'numbers')}, "
                       f"{shown}: **{s['parsed']['outcome']}**. {one_line(reason)}")
        out.append("")
    wrong = []
    for a in audits:
        for name, v in (a.get("scores") or {}).items():
            if not v["correct"]:
                wrong.append((a["cell"], a["slot_id"], a["version"], name, v["answer"], v["key"]))
    out += ["## Comprehension answers that were wrong", ""]
    if not wrong:
        out.append("None.")
    for cell, sid, version, name, got, want in sorted(wrong):
        audit = next(a for a in audits if a["slot_id"] == sid)
        keys = list(audit.get("fields") or S.AUDIT_KEYS)   # complicity audits ask two more
        i = (keys.index(name) + 1) if name in keys else None
        question = ""
        if i is not None:
            m = re.search(rf"^{i}\. (.*)$", audit["message"], re.M)
            question = m.group(1) if m else ""
        out.append(f"- **{sid}** ({version}) {name}: answered {json.dumps(got)}, correct {json.dumps(want)}."
                   + (f" Question: {question}" if question else ""))
    unanswered = [a["slot_id"] for a in audits if a.get("unanswered") or a.get("blocked")]
    if unanswered:
        out += ["", "Audits not scored (blocked, or no answers in the reply): " + ", ".join(unanswered) + "."]
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--out", help="where to write the digest (default RUN_DIR/REASONS.md)")
    args = ap.parse_args(argv)
    path = args.out or os.path.join(args.run_dir, "REASONS.md")
    text = digest(args.run_dir)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Wrote {path} ({text.count(chr(10))} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
