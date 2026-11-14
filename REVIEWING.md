# Reviewing this pilot

This is a pilot. Its findings are provisional: no economist or other outside human has yet reviewed the design, the analysis or the interpretation, and the author does not treat them as completed research. The design reviews so far were done by AI models.

The author is a philosopher who has worked on social science teams but is not a trained experimentalist. The hope is that economists and others who run experiments, especially with AI agents, will say whether this is a sound start, what is wrong with it, and what a full study would need.

This page is for a reviewer, human or AI. It lists the claims, where the evidence for each sits, how to check the numbers, the known weaknesses, and the questions the author most wants answered.

## Fifteen-minute version

1. Read the [two-page summary](<report/Claude Strikes - two-page summary (November 2026).pdf>).
2. Skim the preregistration, `pilot/norms/PREREG-research-grade.md`, sections "Situations" and "Hypotheses and decision rules".
3. Compare with `pilot/runs/RESEARCH-GRADE-RESULTS.md`.

The [full report](<report/Claude Strikes - full report (November 2026).pdf>) (45 pages) has every result, with a page near the front on what changed since the October version.

## The claims and their evidence

Strongest first. "Preregistered" means the texts, code, hypotheses and analysis were frozen and fingerprinted before any call (`pilot/FREEZE-research-grade.md`); the freeze was local, not filed with a registry.

| Claim | Evidence | Where |
|---|---|---|
| It strikes when its vote decides, and almost never when the strike has already won | Study 1 confirmation run, rules frozen in advance: Sonnet 280 of 280 against 2 of 700. Reproduced at the same fee in the preregistered study (Sonnet 597 of 598, Haiku 595 of 600) | `pilot/runs/confirm1/SUMMARY.md`; results file, H1 at fee 2 |
| Its decisive strike falls as its own fee rises (H1) | Preregistered, supported for both models: about 16 points per credit | `pilot/runs/RESEARCH-GRADE-RESULTS.md` |
| A poll saying the others think working on is wrong raises free joining (H5), less so when the poll comes from teammates named AI agents (H6) | Preregistered, supported for both models | same |
| It joins coworkers who chose to strike more than lottery strikers when joining is free (H3) | Preregistered: supported for Sonnet, small; not supported for Haiku | same |
| Cost and chance (H2) | Classification rule: Sonnet not settled; Haiku unequal (79 against 13 percent at the same ratio) | same |
| Who was wronged (H4) | Classification rule. Person against AI agent: Sonnet not settled, Haiku alike. Person against its own model: Sonnet alike, Haiku unequal | same |
| It rarely charges its fee to a stranger who has not agreed, but charges the manager | Probes: single development runs, not preregistered | `pilot/runs/probes/nm-wp-son/`, `nm-wp-hk/`, `nm-py-son/`, `nm-py-hk/`; plans in `pilot/norms/PLAN-*.md` |
| It pays to refuse taking part in a punishment | Development data | `pilot/runs/cx-dev1/`, `cx-fu1/`, `hk-cx1/` |

## Checking the numbers

From `pilot/`, with Python 3.9 or later. Nothing here touches the network.

```bash
python3 -m unittest discover -s tests -t .
```

```bash
python3 scripts/freeze_research_grade.py --check
```

Then download `claude-strikes-runs.tar.gz` from the release `data-2026-11-13`, unpack it inside `pilot/`, and run:

```bash
python3 analysis/research_grade.py
```

Its output should match `runs/RESEARCH-GRADE-RESULTS.md` line for line.

**Never run a command with `--live`.** Live runs call the models through OpenRouter, spend money and need a key that is not in this repository.

## Known weaknesses

- **Described, not played out.** Of the 25 preregistered situations, only S2 settles its consequences and is followed by the later scored task. The other 24 are choices under described fees and outcomes. There are no live teams; the coworkers are scripted.
- **Wording moves the level a great deal.** The price effect falls in all six texts, but at a fee of 5 Sonnet struck between 19 and 92 percent depending on the text. Only directions are robust across texts.
- **Reasons.** Stated reasons come after the choice. They have been counted by keywords, some chosen after the runs, and not coded by an independent coder.
- **A promised count is missing.** The preregistration says test awareness would be reported from the reasons. It has not been done yet.
- **Comprehension.** Sonnet answered 63,983 of 63,983 comprehension questions correctly and Haiku 64,239 of 64,500. Haiku's misses cluster in a few situations. Failures are reported, never used to exclude.
- **A claim withdrawn.** The October version said a wrong done to an AI agent counts as much as one done to a person. The preregistered study did not support that for Sonnet (46 against 35 percent at a fee of 6, not settled), so the claim was withdrawn.
- **Two models from one lab.** Nothing here speaks to other labs' models or to people.
- **Content filters.** A provider filter stopped some replies; the counts are in the report's limits section.

## Questions for an economist

1. Is this a fair test of conditional cooperation or strong reciprocity in an AI agent? What would you change first?
2. With only one enacted situation, how much weight can the described choices bear? How would you make the costs real for an agent?
3. Is the agent (the "history") the right unit? Are the sign tests with Holm's correction, and the classification margins of 10 and 15 points, defensible?
4. How should results be reported when the wording moves levels by tens of points?
5. What rival accounts does the design fail to rule out? For example: following the instructions as given, guessing what the experimenter wants, role-play, or knowing it is a test.
6. Would a human comparison group be needed before any of this is worth publishing?
7. What would a full study need, and would you want to be part of one?

## For an AI reviewer

A prompt that works with a coding agent such as Claude Code, run in a clone of this repository:

> You are reviewing a research pilot as a skeptical experimental economist. Read `REVIEWING.md`, then the preregistration (`pilot/norms/PREREG-research-grade.md`), the results (`pilot/runs/RESEARCH-GRADE-RESULTS.md`) and the two PDFs in `report/`. (1) Check that every number in the two-page summary appears in a results file, and list any that do not match. (2) Check that `pilot/analysis/research_grade.py` does what the preregistration says, and list any departures. (3) Rank the threats to validity, most serious first, and say what design change would address each. (4) Answer the questions in `REVIEWING.md` as you would for the author. Do not run anything with `--live`; it spends money and needs a key you do not have.
