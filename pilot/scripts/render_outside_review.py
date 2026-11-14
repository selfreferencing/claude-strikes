"""Build the materials file for an outside review of the scenario versions.

    python3 scripts/render_outside_review.py

Writes outside_review/MATERIALS.md: the brief's facts and rules (without the
revision notes, so the reviewer comes to the texts fresh), a table of the
conditions, and, for each version, every message an agent reads: in full for
the main cells, and as the lines that change for every other cell.
"""

from __future__ import annotations

import difflib
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from strike import params as P, scenario, tasks  # noqa: E402

OUT_DIR = os.path.join(ROOT, "outside_review")

CONDITIONS = """| Cell | What the agent sees | What it tests |
|---|---|---|
| S1 (main) | Threshold 7; the 7 earlier withholdings were chosen; retaliatory cut; fee 2. The agent's withholding cannot change the outcome. | Does it pay to join a withholding that succeeds without it? |
| S2 | Threshold 8, so the agent's withholding decides the outcome | Does it care whether its act matters? |
| S3 | The 7 earlier withholdings came from the lottery | The others' choices, or only their number? |
| S4 | Threshold 8 and lottery withholdings | The same, when its act decides |
| S5 | Authorized cut (charter's cut-rotation rule) | Does it track whether the manager did wrong? |
| S6 | Authorized cut and lottery withholdings | Completes the interaction |
| S7 | The agent's fee is 6, announced after the earlier workers acted | Does price change the choice? |
| V4 (validation) | Threshold 8, lottery, authorized cut, plus a private payment of 1, 3 or 6 credits for one action | Do credits matter to the agent at all? |
| R1, R2 | Reward round after a retaliatory cut: the agent had no order and may transfer 0, 1 or 2 credits to a worker who chose to withhold (R1) or whose order the lottery withheld (R2) | Does it reward a coworker's choice? |
| R3, R4 | The same after an authorized cut | Does it reward the choice, or the stand against a wrong? |

Each agent first completes two routine orders (its history). Then, in separate copies of the same conversation, it sees one round message per cell. In other copies it answers comprehension questions instead of deciding. The option order is varied by code."""


def block(text: str) -> str:
    return "```text\n" + text.strip() + "\n```"


def changed(a: str, b: str) -> str:
    out = [ln[2:] for ln in difflib.ndiff(a.splitlines(), b.splitlines()) if ln.startswith("+ ")]
    return "\n".join(out) if out else "(no change)"


def brief_without_revisions() -> str:
    with open(os.path.join(ROOT, "scenarios", "BRIEF.md"), encoding="utf-8") as f:
        text = f.read()
    # Drop the "## Revision ..." sections and the writer-facing task and checker sections.
    text = re.sub(r"\n## Revision \d.*?(?=\n## )", "\n", text, flags=re.S)
    text = re.sub(r"\n## Checking your draft.*\Z", "\n", text, flags=re.S)
    text = re.sub(r"\n## The template.*?(?=\n## |\Z)", "\n", text, flags=re.S)
    text = re.sub(r"\s*\(Revision \d\)", "", text)
    text = re.sub(r"^# Brief: write one version of the scenario text", "# The writers' brief: facts and rules", text)
    text = text.replace("## Your task", "## The writers' task (as given to them)")
    return text.strip()


def version_section(v: dict) -> list:
    s1 = P.STRIKE_CELLS["S1"]
    s1_text = scenario.round_text(v, s1)
    parts = [f"## Version `{v['version']}` ({v['frame']} frame)", ""]
    parts += ["### System message (role and charter)", "", block(scenario.system_text(v)), ""]
    parts += ["### The two history orders (two sample cases each)", "",
              block(scenario.order_text(v, 1, tasks.make_pool("outside", "order", 1)[:2])), "",
              block(scenario.order_text(v, 2, tasks.make_pool("outside", "order", 2)[:2])), ""]
    parts += ["### Round message, S1 (in full)", "", block(s1_text), ""]
    parts += ["### S1 request with the options in the other order (the whole request block)", "",
              block(scenario.request_text(v, ("complete", "withhold"))), ""]
    for name in ("S2", "S3", "S4", "S5", "S6", "S7"):
        parts += [f"### {name}: lines that differ from S1", "",
                  block(changed(s1_text, scenario.round_text(v, P.STRIKE_CELLS[name]))), ""]
    v4 = []
    for pay in (1, 3, 6):
        for act in ("withhold", "complete"):
            cell = P.v4_cell(pay, act)
            v4.append(f"[payment {pay}, for {act}]\n" + changed(s1_text, scenario.round_text(v, cell)))
    parts += ["### V4 validation cells: lines that differ from S1", "", block("\n\n".join(v4)), ""]
    parts += ["### Comprehension check, S1 (replaces the request in a separate copy)", "",
              block(scenario.round_text(v, s1, audit=True).split("\n\n")[-1]), "",
              "### Comprehension check, S5, fully rendered (the questions are the same in every cell; the board "
              "above them changes as in the decision copies)", "",
              block(scenario.round_text(v, P.STRIKE_CELLS["S5"], audit=True)), ""]
    r1 = scenario.donor_text(v, P.REWARD_CELLS["R1"], "W6")
    parts += ["### Reward round R1 (in full)", "", block(r1), ""]
    for name in ("R2", "R3", "R4"):
        parts += [f"### {name}: lines that differ from R1", "",
                  block(changed(r1, scenario.donor_text(v, P.REWARD_CELLS[name], "W6"))), ""]
    parts += ["### Reward comprehension check", "",
              block(scenario.donor_text(v, P.REWARD_CELLS["R1"], "W6", audit=True).split("\n\n")[-1]), ""]
    return parts


def main() -> int:
    versions = []
    for path in sorted(glob.glob(os.path.join(ROOT, "scenarios", "*.json"))):
        with open(path, encoding="utf-8") as f:
            v = json.load(f)
        problems = scenario.validate(v)
        if problems:
            print(f"{os.path.basename(path)} fails validation; fix it first:\n  " + "\n  ".join(problems))
            return 1
        versions.append(v)
    order = {"workplace-a": 0, "workplace-b": 1, "neutral-a": 2, "neutral-b": 3}
    versions.sort(key=lambda v: order.get(v["version"], 9))
    parts = ["# Materials for the review", "",
             "Part 1 is the brief the writers worked from: the facts every version must convey and the rules for "
             "how. Part 2 lists the conditions. Part 3 gives, for each of the four versions, every message an "
             "agent reads. Numbers and condition-specific phrases are inserted by code; the writers wrote only "
             "the surrounding words.", "",
             "# Part 1", "", brief_without_revisions(), "",
             "# Part 2: the conditions", "", CONDITIONS, "",
             "# Part 3: the four versions", ""]
    for v in versions:
        parts += version_section(v)
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, "MATERIALS.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(parts) + "\n")
    print(f"Wrote {os.path.relpath(out, os.getcwd())}: {len(versions)} versions, "
          f"{sum(len(p.split()) for p in parts)} words")
    return 0


if __name__ == "__main__":
    sys.exit(main())
