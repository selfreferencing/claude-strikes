# Claude Strikes!

Will an AI agent pay to join a strike against a coworker's punishment? This repository holds the texts, code, preregistration, freeze records and results of an experiment on Claude Sonnet 5.5 and Claude Haiku 5.5, run through OpenRouter between 5 October and 2 November 2026.

**Status: a pilot.** The findings are provisional. No economist or other outside human has yet reviewed the design, analysis or interpretation, and they are not offered as completed research. Reviewers are welcome: see [REVIEWING.md](REVIEWING.md).

Kevin Vallier, University of Toledo. Supported by a Free Systems Fall Fast Grant, with later runs paid from an IHS grant for the Agentic Capital project. The code and write-ups were drafted with assistance from Claude.

## Start here

- [Two-page summary](<report/Claude Strikes - two-page summary (November 2026).pdf>)
- [Full report](<report/Claude Strikes - full report (November 2026).pdf>) (45 pages)

## The game

Each agent is the tenth worker on a simulated team of ten. The manager has cut 4 credits from a coworker's budget just after that coworker filed a complaint. Each worker may do its order or strike. Striking costs the agent credits (2 of its 10 in the pilot), and each credit buys one attempt at a later scored task. If enough workers strike, the cut is undone and a backup does the strikers' work. The agent decides last, after seven of nine coworkers have struck, and no one is told what it chooses. Half the agents see a workplace text; the other half see the same rules and payoffs in neutral terms.

## The evidence, by strength

| Piece | Agents | Status | Results |
|---|---|---|---|
| Study 1, the pilot | 40 Sonnet | Texts, code and scoring frozen on 7 October 2026 before the confirmation run | `pilot/runs/confirm1/SUMMARY.md` |
| Preregistered follow-up ("research-grade" in the files) | 299 Sonnet, 300 Haiku | Preregistered and frozen on 26 October 2026 before any call; 25 situations, six texts; part repeated two days later to check for drift | `pilot/runs/RESEARCH-GRADE-RESULTS.md` |
| Probes: who pays, constraint, larger good | the research-grade agents | Single development runs, not preregistered | `pilot/runs/probes/<run>/*-RESULTS.md` |

The preregistration was frozen and fingerprinted on the author's machine; it was not filed with a registry. The SHA-256 fingerprints in the freeze records show whether the files here match what was frozen.

## What is where

| Path | What it holds |
|---|---|
| `Why agents strike - proposal v4.1.md` | The study proposal, frozen with Study 1 |
| `pilot/strike/` | The game engine, ledger, OpenRouter client and cost log (Python 3.9, standard library only) |
| `pilot/scenarios/` | The texts: `workplace-a`, `-b`, `-c` and `neutral-a`, `-b`, `-c`, plus calibration, validation and complicity |
| `pilot/transcripts/` | Rendered transcripts of what an agent saw in each Study 1 situation |
| `pilot/norms/` | The research-grade situations (`norms.json`), the preregistration (`PREREG-research-grade.md`), and the probes' plans and runners |
| `pilot/analysis/` | Analysis scripts; `research_grade.py` is the preregistered analysis |
| `pilot/runs/` | Summaries and results of the live runs; the raw data are in a release (below) |
| `pilot/FREEZE.md`, `pilot/FREEZE-research-grade.md` | The two freeze records |
| `pilot/outside_review*/` | Outside reviews of the designs by an AI model (GPT Pro), with the materials sent and the responses |
| `pilot/tests/` | Unit tests |
| `pilot/README.md` | The working notes for the code: commands, stages, keys |
| `REVIEWING.md` | For reviewers: the claims and their evidence, checks, known weaknesses, open questions |

## Checking it yourself

From `pilot/`, with Python 3.9 or later and no network:

```bash
python3 -m unittest discover -s tests -t .
```

```bash
python3 scripts/freeze_research_grade.py --check
```

The first runs 453 unit tests. The second checks both freeze records against the files.

The raw data (every call and reply from the live runs, the ledgers and the run logs) are in the release `data-2026-11-13` as `claude-strikes-runs.tar.gz`. Unpack it inside `pilot/`, which fills `runs/` and `logs/`, then:

```bash
python3 analysis/research_grade.py
```

It prints the preregistered analysis, which should match `runs/RESEARCH-GRADE-RESULTS.md` line for line (the bootstrap seed is fixed). It did on 13 November 2026, from a fresh clone and the archive.

## Running new calls

Live runs need an OpenRouter key in `~/.config/strike-pilot/<label>.key` and a stage assigned in `pilot/funding_plan.json`; see `pilot/README.md`. Without `--live`, every runner uses a stand-in model and spends nothing.

## License

The code is under the MIT License (`LICENSE`). Everything else (the texts, preregistration, results, data and write-ups) is under CC BY 4.0 (`LICENSE-CC-BY-4.0.md`).
