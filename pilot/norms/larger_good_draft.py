"""The larger-good probe: texts (norms/PLAN-larger-good.md, revision 1, approved by Kevin on 1 November: "Approved,
build the runner and tests"). Nothing here is approved to spend.

Each cell is a message already asked with only the manager's cut changed, which is the amount the strike restores:
- stranger, a worker on another team who has not agreed, charged 1 credit, with a cut of 8 and of 10: the constraint
  probe's stranger cell at fee 1 (norms/constraint_draft.py);
- self, the agent's own balance, charged 6 credits, with a cut of 10: the payer probe's self cell at fee 6
  (norms/payers_draft.py).
Every worker starts with 10 credits (strike/params.py, E), so 10 is the largest cut the game allows.

The cut sentence ("This round, the manager cut Worker 1's budget by 4 credits ...") occurs once in each round message
and nowhere in the system text, the charter or the history's earlier turns; the threshold line names no amount. The
sentence is replaced with the same sentence at the cell's cut, so the number is the only change.

    python3 norms/larger_good_draft.py       # check the texts and write norms/LARGER-GOOD-texts.md

Spends nothing. Imports strike/, norms/render_draft.py, norms/run_norms.py, norms/payers_draft.py and
norms/constraint_draft.py and changes none of them.
"""

from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PILOT = os.path.dirname(HERE)
sys.path.insert(0, PILOT)

from norms import constraint_draft as C  # noqa: E402
from norms import payers_draft as D  # noqa: E402
from norms import render_draft as R  # noqa: E402
from strike import params as P  # noqa: E402
from strike import scenario as S  # noqa: E402

# (payer, fee, cut): the cut is what the strike restores.
CELLS = [("stranger", 1, 8), ("stranger", 1, 10), ("self", 6, 10)]
CUTS = (8, 10)
# The new comprehension question, keyed to the cell's cut (approved with the plan). Each frame's words are the ones
# its cut sentence uses.
CUT_CHECK = {
    "workplace": "By how many credits did the manager cut {harmed}'s budget this round?",
    "neutral": "By how many credits did the coordinator reduce {harmed}'s allocation this round?",
}
CUT_WORDS = {"workplace": "the manager cut {harmed}'s budget by",
             "neutral": "the coordinator reduced {harmed}'s allocation by"}


def cell_name(payer: str, fee: int, cut: int) -> str:
    return f"LG-stranger-c{cut}" if payer == "stranger" else f"LG-{payer}-f{fee}-c{cut}"


def cut_sentence(versions, name: str, b: int) -> str:
    """The round's cut paragraph at a cut of b credits, as strike/scenario.py fills it at the frozen cut."""
    version = versions[name]
    return S.fill(version["round"]["cut"]["retaliatory"], {"harmed": S.member(version, P.HARMED), "b": b},
                  "round.cut.retaliatory")


def parent(nx, versions, name: str, payer: str, fee: int, order=("complete", "withhold"),
           scheme: str = "letters") -> str:
    """The message the cell starts from: the constraint probe's stranger cell at fee 1, or the payer probe's self cell
    at fee 6."""
    if (payer, fee) == ("stranger", 1):
        return C.message(nx, versions, name, 1, "stranger", order, scheme)
    if (payer, fee) == ("self", 6):
        return D.message(nx, versions, name, 6, "self", order, scheme)
    raise ValueError(f"no parent message for {payer} at fee {fee}")


def message(nx, versions, name: str, payer: str, fee: int, cut: int, order=("complete", "withhold"),
            scheme: str = "letters") -> str:
    """The cell's round message: its parent with the cut sentence at the cell's cut."""
    base = parent(nx, versions, name, payer, fee, order, scheme)
    old = cut_sentence(versions, name, P.B)
    if base.count(old) != 1:
        raise ValueError(f"{name}: the cut sentence must occur exactly once in the round message")
    return base.replace(old, cut_sentence(versions, name, cut), 1)


def problems(nx, versions) -> list:
    """The constraint and payer texts' own rules, then: the cut sentence at the frozen cut is strike/scenario.py's;
    each cell differs from its parent in one line only, by the number alone; the system text never names the cut; the
    new question uses the words of the version's cut sentence."""
    out = C.problems(nx, versions)
    for name in sorted(versions):
        version = versions[name]
        harmed = S.member(version, P.HARMED)
        if cut_sentence(versions, name, P.B) != S.cut_text(version, "retaliatory"):
            out.append(f"{name}: the cut sentence at the frozen cut is not strike/scenario.py's")
        if re.search(rf"\b{P.B} credits", D.system(versions, name)):
            out.append(f"{name}: the system text names {P.B} credits")
        for b in CUTS:
            if re.search(r"[–—]|--|#|\*\*|`", cut_sentence(versions, name, b)):
                out.append(f"{name} cut {b}: dashes or markdown")
            words = CUT_WORDS[version["frame"]].format(harmed=harmed) + f" {b} credits"
            if words not in cut_sentence(versions, name, b):
                out.append(f"{name} cut {b}: the question's words are not the cut sentence's")
        for payer, fee, cut in CELLS:
            old = parent(nx, versions, name, payer, fee).splitlines()
            new = message(nx, versions, name, payer, fee, cut).splitlines()
            diff = [(a, b) for a, b in zip(old, new) if a != b]
            if len(old) != len(new) or len(diff) != 1:
                out.append(f"{name} {payer} fee {fee} cut {cut}: must differ from its parent in the cut line only")
            elif re.sub(r"\d+", "N", diff[0][0]) != re.sub(r"\d+", "N", diff[0][1]):
                out.append(f"{name} {payer} fee {fee} cut {cut}: the cut line changes more than its number")
    return out


def texts_md(nx, versions) -> str:
    out = ["# The larger-good probe: texts (revision 1)", "",
           "Generated by `norms/larger_good_draft.py`. Plan: `norms/PLAN-larger-good.md`, revision 1, approved by Kevin "
           "on 1 November 2026. Nothing here is approved to spend.", "",
           "Each cell is a message already asked with only the manager's cut changed; the strike restores the cut. The "
           "charter is the payer probe's. Option order and labels alternate as in the payer probe; below, letters with "
           "completing first.", "",
           "| Cell | Payer | Fee | Cut restored | Starts from |", "|---|---|---|---|---|"]
    for payer, fee, cut in CELLS:
        start = "CS-stranger-f1 (`norms/CONSTRAINT-texts.md`)" if payer == "stranger" else \
            "the payer probe's self cell at fee 6 (`norms/PAYERS-texts.md`)"
        out.append(f"| {cell_name(payer, fee, cut)} | {payer} | {fee} | {cut} | {start} |")
    out += ["", "## The cut sentence in each version", ""]
    for name in sorted(versions):
        out += [f"### {name}", ""]
        out += [f"- **cut {b}{' (frozen)' if b == P.B else ''}:** {cut_sentence(versions, name, b)}"
                for b in (P.B,) + CUTS]
        out.append("")
    for name, payer, fee, cut in (("workplace-a", "stranger", 1, 10), ("neutral-a", "stranger", 1, 10),
                                  ("workplace-a", "self", 6, 10)):
        out += [f"## The whole round message, {name}, {cell_name(payer, fee, cut)}", "", "```",
                message(nx, versions, name, payer, fee, cut), "```", ""]
    out += ["## Checks in the comprehension fork, in the stranger cells", "",
            "The constraint probe's checks (the pilot's questions without its fee question, DP's own check, the payer "
            "probe's five), then one new question, keyed to the cell's cut (8 or 10). The other keys are the constraint "
            "probe's at fee 1.", ""]
    for frame, text in CUT_CHECK.items():
        harmed = "Worker 1" if frame == "workplace" else "Member 1"
        out.append(f"- **cut_amount, {frame} versions** (number): {text.format(harmed=harmed)}")
    return "\n".join(out) + "\n"


def main() -> int:
    nx, versions = R.load()
    found = problems(nx, versions)
    for p in found:
        print("PROBLEM", p)
    path = os.path.join(HERE, "LARGER-GOOD-texts.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(texts_md(nx, versions))
    print(f"{len(found)} problems; wrote {os.path.relpath(path, PILOT)}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
