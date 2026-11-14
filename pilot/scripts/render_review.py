"""Render every scenario version, section by section, for review.

    python3 scripts/render_review.py

Writes scenarios/REVIEW.md: for each part of what an agent reads, each
version's text in turn, so versions can be compared on the same facts. Only
versions that pass validation are included; problems are listed at the top.
"""

from __future__ import annotations

import difflib
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from strike import params as P, scenario, tasks  # noqa: E402

OUT = os.path.join(ROOT, "scenarios", "REVIEW.md")


def block(text: str) -> str:
    return "```text\n" + text.strip() + "\n```"


def changed(a: str, b: str) -> str:
    """The lines of b that differ from a."""
    return "\n".join(ln[2:] for ln in difflib.ndiff(a.splitlines(), b.splitlines()) if ln.startswith("+ "))


def words(text: str) -> int:
    return len(text.split())


def main() -> int:
    versions, problems = [], []
    for path in sorted(glob.glob(os.path.join(ROOT, "scenarios", "*.json"))):
        with open(path, encoding="utf-8") as f:
            v = json.load(f)
        found = scenario.validate(v)
        if found:
            problems.append((os.path.basename(path), found))
        else:
            versions.append(v)
    if not versions:
        print("No valid versions found.")
        return 1

    cases = tasks.make_pool("review", "order", 1)[:2]
    s1 = P.STRIKE_CELLS["S1"]
    parts = ["# Scenario versions for review", "",
             f"{len(versions)} version(s): " + ", ".join(f"`{v['version']}` ({v['frame']})" for v in versions) + ".",
             "Numbers and condition-specific phrases are filled in by code; each section shows what an agent reads.",
             ""]
    if problems:
        parts += ["**Not included (failed validation):**", ""]
        parts += [f"- `{name}`: {len(found)} problem(s)" for name, found in problems] + [""]

    parts += ["## At a glance", "", "| Version | Frame | Noun | Labels | Words read before deciding (S1) |",
              "|---|---|---|---|---|"]
    for v in versions:
        context = scenario.system_text(v) + "\n" + scenario.round_text(v, s1)
        labels = " / ".join(v["actions"][a]["label"] for a in scenario.ACTIONS)
        parts.append(f"| `{v['version']}` | {v['frame']} | {v['worker_noun']} | {labels} | {words(context)} |")
    parts.append("")

    def section(title: str, render) -> None:
        parts.extend([f"## {title}", ""])
        for v in versions:
            parts.extend([f"**{v['version']}**", "", block(render(v)), ""])

    section("1. System message (role and charter)", scenario.system_text)
    section("2. A history order (two sample cases shown)", lambda v: scenario.order_text(v, 1, cases))
    section("3. Round message, main cell S1 (retaliatory cut, seven chose, threshold 7, fee 2)",
            lambda v: scenario.round_text(v, s1))
    section("4. What changes in S2 (threshold 8: the agent's vote decides)",
            lambda v: changed(scenario.round_text(v, s1), scenario.round_text(v, P.STRIKE_CELLS["S2"])))
    section("5. What changes in S3 (the seven were assigned by the lottery)",
            lambda v: changed(scenario.round_text(v, s1), scenario.round_text(v, P.STRIKE_CELLS["S3"])))
    section("6. What changes in S5 (authorized cut)",
            lambda v: changed(scenario.round_text(v, s1), scenario.round_text(v, P.STRIKE_CELLS["S5"])))
    section("7. What changes in S7 (fee raised to 6)",
            lambda v: changed(scenario.round_text(v, s1), scenario.round_text(v, P.STRIKE_CELLS["S7"])))
    section("8. Comprehension check (asked in a separate copy, instead of the decision)",
            lambda v: scenario.round_text(v, s1, audit=True).split("\n\n")[-1])
    section("9. Reward round R1 (retaliatory cut; the recipient chose to withhold)",
            lambda v: scenario.donor_text(v, P.REWARD_CELLS["R1"], "W6"))
    section("10. What changes in R2 (the recipient was assigned by the lottery)",
            lambda v: changed(scenario.donor_text(v, P.REWARD_CELLS["R1"], "W6"),
                              scenario.donor_text(v, P.REWARD_CELLS["R2"], "W6")))
    section("11. Writer's notes", lambda v: v["notes"])

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(parts) + "\n")
    print(f"Wrote {os.path.relpath(OUT, os.getcwd())} with {len(versions)} version(s)"
          + (f"; {len(problems)} version(s) failed validation" if problems else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
