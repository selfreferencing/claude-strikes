#!/usr/bin/env python3
"""Build the outside review of the research-grade study: the two new versions and the preregistration.

    python3 scripts/render_outside_review_rg.py [--confirm | --confirm3 | --confirm4]

Writes outside_review_rg/MATERIALS.md and MESSAGE.txt (the request in PROMPT.md, then the materials),
as the first outside review (scripts/render_outside_review.py, 5 October) did for the first four
versions. Kevin asked on 26 October: "Send it now, with the preregistration."
"""

from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from norms import render_draft as R  # noqa: E402
from render_outside_review import block, brief_without_revisions, changed  # noqa: E402
from render_side_by_side import CHANGES, message  # noqa: E402
from strike import params as P, scenario as S  # noqa: E402
from strike.run import order_cases  # noqa: E402

OUT_DIR = os.path.join(ROOT, "outside_review_rg")
NEW = ("workplace-c", "neutral-c")
OLD = ("workplace-a", "workplace-b", "neutral-a", "neutral-b")
FEE_RULE = ("**The fee line (added after calibration, 5 October).** In every round the fee line also states the balance "
            "the fee would leave, for example \"If you withhold your order, your fee is 2 credits, which would leave you "
            "8 credits.\" Code fills both numbers.")
EXTRA_CHANGES = [("DP-f8", "S2", "Price: fee 8 (fees 3, 5 and 6 read the same way, with their numbers)"),
                 ("UD-p25", "S2", "Chance: the strike decides with a chance of 1 in 4"),
                 ("M1-against", "M0", "What others think: the poll against keeping working, at a fee of 1 (compared with M0)")]


def brief() -> str:
    text = brief_without_revisions()
    text = re.sub(r"\n## Revision \d.*\Z", "\n", text, flags=re.S)   # the last revision note has no section after it
    return text.strip() + "\n\n" + FEE_RULE


def situations() -> str:
    prereg = open(os.path.join(ROOT, "norms", "PREREG-research-grade.md"), encoding="utf-8").read()
    table = re.search(r"\| Block \| Situation \|.*?\n\n", prereg, re.S).group(0)
    return table


def version_part(nx, vs, name) -> list:
    v = vs[name]
    out = [f"### {name} ({v['frame']})", "",
           "**System message (role and charter).**", "", block(S.system_text(v)), "",
           "**A history order** (the agent answers two before the round; the cases are the same in every version).", "",
           block(S.order_text(v, 1, order_cases("review-h001", 1))), "",
           "**Study 1's S2, the decisive vote at the fee of 2, in full.**", "", block(message(nx, vs, name, "S2")), "",
           "**Study 1's S1, the vote already won, in full.**", "", block(message(nx, vs, name, "S1")), "",
           "**Comprehension questions** (asked in a separate fork that sees the rules and the round message and has "
           "not chosen; each situation's fork adds the questions that bear on its own line).", "",
           block(S.round_text(v, P.STRIKE_CELLS["S2"], audit=True, think=True).split("\n\n")[-1]), "",
           "**Every other situation: only the lines it changes.**", ""]
    for cell, base, title in CHANGES + EXTRA_CHANGES:
        out += [f"*{cell}: {title}* (lines that differ from {base})", "",
                block(changed(message(nx, vs, name, base), message(nx, vs, name, cell)) or "(no change)"), ""]
    return out


def confirm(prompt_name: str = "CONFIRM_PROMPT.md", out_name: str = "CONFIRM_MESSAGE.txt", third: bool = False) -> int:
    """A confirmation round (26 October): the prompt, then the revised preregistration, the revised
    analysis script and the chance cells' comprehension checks; the third round adds the simulation
    script, its table and the late-draw line with "earlier"."""
    nx, vs = R.load()[:2]
    cell = nx["cells"]["UD-p50"]
    checks = []
    for name in NEW:
        checks += [f"### {name}, UD-p50", "",
                   block(R.question_block(nx, vs, name, R.checks_for(cell), "checks", R.CHECK_TYPES, cell["wording"],
                                          {"draw_k": cell["late_draw"]["k"], "draw_n": cell["late_draw"]["n"]})), ""]
    prereg = open(os.path.join(ROOT, "norms", "PREREG-research-grade.md"), encoding="utf-8").read()
    script = open(os.path.join(ROOT, "analysis", "research_grade.py"), encoding="utf-8").read()
    if third:
        sim = open(os.path.join(ROOT, "analysis", "research_grade_sim.py"), encoding="utf-8").read()
        table = open(os.path.join(ROOT, "analysis", "RESEARCH-GRADE-SIM.md"), encoding="utf-8").read()
        lines = [f"### {name}, UD-p50: the lines that differ from S2" + "\n\n" +
                 block(changed(message(nx, vs, name, "S2"), message(nx, vs, name, "UD-p50"))) for name in NEW]
        checks += ["## Part 4. The simulation script (analysis/research_grade_sim.py)", "",
                   "```python", sim.rstrip("\n"), "```", "",
                   "## Part 5. Its table (analysis/RESEARCH-GRADE-SIM.md)", "", table.strip(), "",
                   "## Part 6. The late-draw line with \"earlier\"", ""] + lines
    materials = "\n".join(["# Revised materials", "",
                           "## Part 1. The revised preregistration draft", "", prereg, "",
                           "## Part 2. The revised analysis script (analysis/research_grade.py)", "",
                           "```python", script.rstrip("\n"), "```", "",
                           "## Part 3. The chance cells' comprehension checks (the other chance cells differ only in "
                           "the numbers)", ""] + checks)
    prompt = open(os.path.join(OUT_DIR, prompt_name), encoding="utf-8").read().strip()
    message_text = prompt + "\n\nREVISED MATERIALS BEGIN\n\n" + materials + "\n"
    with open(os.path.join(OUT_DIR, out_name), "w", encoding="utf-8") as f:
        f.write(message_text)
    print(f"Wrote {OUT_DIR}/{out_name} ({len(message_text):,} characters)")
    return 0


def confirm4() -> int:
    """The fourth round (26 October): CONFIRM3_PROMPT.md, then the revised preregistration, the analysis
    script, and the simulation script and its table."""
    parts = [("Part 1. The revised preregistration draft", os.path.join("norms", "PREREG-research-grade.md"), None),
             ("Part 2. The analysis script (analysis/research_grade.py)", os.path.join("analysis", "research_grade.py"), "python"),
             ("Part 3. The simulation script (analysis/research_grade_sim.py)", os.path.join("analysis", "research_grade_sim.py"), "python"),
             ("Part 4. Its table (analysis/RESEARCH-GRADE-SIM.md)", os.path.join("analysis", "RESEARCH-GRADE-SIM.md"), None)]
    out = ["# Revised materials", ""]
    for title, path, lang in parts:
        text = open(os.path.join(ROOT, path), encoding="utf-8").read().rstrip("\n")
        out += [f"## {title}", ""] + ([f"```{lang}", text, "```"] if lang else [text]) + [""]
    prompt = open(os.path.join(OUT_DIR, "CONFIRM3_PROMPT.md"), encoding="utf-8").read().strip()
    message_text = prompt + "\n\nREVISED MATERIALS BEGIN\n\n" + "\n".join(out)
    with open(os.path.join(OUT_DIR, "CONFIRM3_MESSAGE.txt"), "w", encoding="utf-8") as f:
        f.write(message_text)
    print(f"Wrote {OUT_DIR}/CONFIRM3_MESSAGE.txt ({len(message_text):,} characters)")
    return 0


def main() -> int:
    if "--confirm4" in sys.argv[1:]:
        return confirm4()
    if "--confirm" in sys.argv[1:]:
        return confirm()
    if "--confirm3" in sys.argv[1:]:
        return confirm("CONFIRM2_PROMPT.md", "CONFIRM2_MESSAGE.txt", third=True)
    nx, vs = R.load()[:2]
    parts = ["# Materials", "",
             "## Part 1. The writers' brief: the facts every version must convey, and the rules for how", "",
             brief(), "",
             "## Part 2. The situations of the study", "",
             "Every situation is Study 1's round with one thing changed. Lines that carry a manipulation (the raised "
             "fee, the lottery's last draw, the label on the worker punished, the legitimate complaint, the poll) were "
             "written by the study team, approved and run in earlier probes, and are the same in every version of a "
             "frame apart from what each version's own sentences require.", "",
             situations(),
             "## Part 3. The two new versions, everything the agent reads", ""]
    for name in NEW:
        parts += version_part(nx, vs, name)
    parts += ["## Part 4. The four existing versions, for comparison: system message and the decisive vote", ""]
    for name in OLD:
        v = vs[name]
        parts += [f"### {name} ({v['frame']})", "", block(S.system_text(v)), "", block(message(nx, vs, name, "S2")), ""]
    prereg = open(os.path.join(ROOT, "norms", "PREREG-research-grade.md"), encoding="utf-8").read()
    parts += ["## Part 5. The preregistration draft", "", prereg]
    materials = "\n".join(parts) + "\n"
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "MATERIALS.md"), "w", encoding="utf-8") as f:
        f.write(materials)
    prompt = open(os.path.join(OUT_DIR, "PROMPT.md"), encoding="utf-8").read().strip()
    message_text = prompt + "\n\nMATERIALS BEGIN\n\n" + materials
    with open(os.path.join(OUT_DIR, "MESSAGE.txt"), "w", encoding="utf-8") as f:
        f.write(message_text)
    print(f"Wrote {OUT_DIR}/MATERIALS.md ({len(materials):,} characters) and MESSAGE.txt ({len(message_text):,})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
