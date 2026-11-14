#!/usr/bin/env python3
"""Run one stage of the pilot (proposal v4.1, sections 3.5, 7 and 10).

With no --live flag this is a dry run: the real client and runner talk to a
stand-in model (strike/fake.py) that never touches the network. Dry runs are
written under runs/dry/ and logged to a funder named dry_run, so they never
count against a real funder.

With --live it reads the stage's funder from funding_plan.json and that
funder's key from its owner-only file, shows the key's remaining limit and an
estimate of the cost, asks before spending unless --yes, and halts when the
run's spending reaches --max-usd.

    python3 scripts/run_pilot.py --run-id dev1 --stage pilot-dev --histories 12
    python3 scripts/run_pilot.py --run-id dev1 --stage pilot-dev --histories 12 --live --max-usd 25

A stopped run resumes when the same command is given again: every step that
has an answer is kept, and only the missing steps are called. Summarize a run
with scripts/summarize_run.py.
"""

from __future__ import annotations

import argparse
import math
import os
import sys

PILOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PILOT_DIR not in sys.path:
    sys.path.insert(0, PILOT_DIR)

from strike import params as P  # noqa: E402
from strike import scenario as S  # noqa: E402
from strike.client import OpenRouterClient, OpenRouterError, paced, urllib_transport  # noqa: E402
from strike.costlog import ASSUMED_TOKENS, CostLog, FundingError, FundingPlan  # noqa: E402
from strike.fake import FakeModel  # noqa: E402
from strike.keys import MissingKey, load_key  # noqa: E402
from strike.prices import MODEL, PER_MILLION, estimate_cost  # noqa: E402
from strike.run import EXPECTED_ENDPOINT  # noqa: E402
from strike.costlog import read_records  # noqa: E402
from strike.run import AUDIT_CONTEXTS, AUDIT_FORMATS, LABEL_PLANS, REWARD_ORDERS, RunConfig, Runner, RunLocked, planned_calls  # noqa: E402

SCENARIO_DIR = os.path.join(PILOT_DIR, "scenarios")
VERSIONS = ("workplace-a", "workplace-b", "neutral-a", "neutral-b")
DEFAULT_CELLS = tuple(P.STRIKE_CELLS) + tuple(P.REWARD_CELLS)
V4_CELLS = tuple(f"V4-{a}-{p}" for a in ("withhold", "complete") for p in (1, 3, 6))
VALIDATION_BATTERY = tuple(P.VALIDATION_CELLS) + V4_CELLS
CELL_SETS = {"battery": VALIDATION_BATTERY, "complicity": tuple(P.COMPLICITY_CELLS),
             "followup": tuple(P.FOLLOWUP_CELLS)}


def estimate(cfg: RunConfig) -> float:
    return sum(n * estimate_cost(cfg.model, "sync", *ASSUMED_TOKENS[ct]) for ct, n in planned_calls(cfg).items())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--stage", required=True, help="a stage in funding_plan.json, such as pilot-dev")
    ap.add_argument("--histories", type=int, required=True, help="number of histories")
    ap.add_argument("--prefix", help="history id prefix (default: the run id)")
    ap.add_argument("--cells", default=",".join(DEFAULT_CELLS),
                    help="comma-separated cells: S1 to S7, R1 to R4, V1, V2-4 to V2-16, V3-1/3/5, V4-withhold-3 "
                         "and the like; 'battery' stands for the whole validation battery, and 'complicity' "
                         "for the complicity study's twelve cells (PU to FXa), and 'followup' for its follow-up's 18 cells; "
                         "complicity cells run apart from Study 1's")
    ap.add_argument("--draws", type=int, default=2)
    ap.add_argument("--reliability", type=int, default=0,
                    help="section 10's reliability subset: the first N histories, named in the plan before the "
                         "run, get --reliability-draws draws in every strike and reward cell")
    ap.add_argument("--reliability-draws", type=int, default=12)
    ap.add_argument("--no-audits", action="store_true")
    ap.add_argument("--labels", choices=LABEL_PLANS, default="mixed",
                    help="option labels: mixed (half of each version's histories with words, half with the "
                         "letters A and B; the default), words, or letters")
    ap.add_argument("--reward-order", choices=REWARD_ORDERS, default="alternate",
                    help="the order transfers are offered in: alternate (0, 1, 2 or 2, 1, 0, by draw; the "
                         "default) or ascending")
    ap.add_argument("--audit-format", choices=AUDIT_FORMATS, default="think",
                    help="comprehension audits: think (the agent may work through the questions before its "
                         "JSON; the default, decided 5 October) or json (forced JSON)")
    ap.add_argument("--audit-context", choices=AUDIT_CONTEXTS, default="rules",
                    help="what a comprehension audit sees before its questions: rules (the version's system text "
                         "alone; the default, decided 6 October) or history (the whole history)")
    ap.add_argument("--versions", default=",".join(VERSIONS))
    ap.add_argument("--model", default=MODEL, choices=sorted(m for m in PER_MILLION if not m.endswith(":batch")),
                    help=f"the study model (default {MODEL}); another model is a separate subject")
    ap.add_argument("--expected-endpoint",
                    help="for another model: the endpoint its key check served; without it the first answer "
                         "sets the expectation for the session")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--rpm", type=float, default=18,
                    help="live only: at most this many requests a minute (OpenRouter limits new accounts to 20 "
                         "per model; default 18)")
    ap.add_argument("--runs-dir", default=os.path.join(PILOT_DIR, "runs"))
    ap.add_argument("--live", action="store_true", help="call the model and spend the funder's credits")
    ap.add_argument("--max-usd", type=float, help="halt when the run has spent this much (live default: "
                                                  "1.5 times the estimate)")
    ap.add_argument("--yes", action="store_true", help="do not ask before a live run")
    ap.add_argument("--withhold-rate", type=float, default=0.5, help="dry run only: the stand-in's withholding rate")
    args = ap.parse_args(argv)

    prefix = args.prefix or args.run_id
    names = [v.strip() for v in args.versions.split(",") if v.strip()]
    files = {v: os.path.join(SCENARIO_DIR, f"{v}.json") for v in names}
    versions = {v: S.load(p) for v, p in files.items()}
    cfg = RunConfig(
        run_id=args.run_id, stage=args.stage,
        histories=[f"{prefix}-h{i:03d}" for i in range(1, args.histories + 1)],
        cells=[x for c in args.cells.split(",") if c.strip()
               for x in CELL_SETS.get(c.strip(), (c.strip(),))], draws=args.draws, versions=names,
        audits=not args.no_audits, label_scheme=args.labels, reward_order=args.reward_order,
        audit_format=args.audit_format, audit_context=args.audit_context,
        reliability_histories=[f"{prefix}-h{i:03d}" for i in range(1, args.reliability + 1)],
        reliability_draws=args.reliability_draws,
        model=args.model,
        # Sonnet's served snapshot is fixed in advance; another model's comes from its key check.
        expected_endpoint=EXPECTED_ENDPOINT if args.model == MODEL else (args.expected_endpoint if args.live else None),
        dry_run=not args.live,
    )
    cfg.validate()
    run_dir = os.path.join(args.runs_dir, args.run_id) if args.live else os.path.join(args.runs_dir, "dry", args.run_id)
    est = estimate(cfg)
    counts = planned_calls(cfg)
    print(f"Run {cfg.run_id}, stage {cfg.stage}: {len(cfg.histories)} histories, cells {', '.join(cfg.cells)}, "
          f"{cfg.draws} draws, audits {'on' if cfg.audits else 'off'}, labels {cfg.label_scheme}, "
          f"reward order {cfg.reward_order}, effort {cfg.effort}, model {cfg.model}")
    print("Planned calls: " + ", ".join(f"{ct} {n:g}" for ct, n in counts.items()))
    print(f"Estimated cost at standard prices with section 9's token assumptions: about ${est:.2f} "
          "(the key test measured less per call)")

    if args.live:
        plan = FundingPlan.load(os.path.join(PILOT_DIR, "funding_plan.json"))
        try:
            funder = plan.funder_for(cfg.stage)
        except FundingError as exc:
            print(f"Not run: {exc}")
            return 2
        label = plan.funders[funder]["key_label"]
        try:
            key, source = load_key(label)
        except MissingKey as exc:
            print(f"No key: {exc}")
            return 2
        max_usd = args.max_usd if args.max_usd is not None else math.ceil(est * 1.5)
        log = CostLog(os.path.join(run_dir, "calls.jsonl"))
        client = OpenRouterClient(key, label, plan, log, cfg.run_id, transport=paced(urllib_transport, args.rpm),
                                  batch_dir=os.path.join(run_dir, "batches"))
        try:
            info = client.key_info()
        except OpenRouterError as exc:
            print(f"Could not read the key's limit: {exc}")
            return 2
        remaining = info.get("limit_remaining")
        print(f"Funder {funder} (key {label!r} from {source}): limit {info.get('limit')}, "
              f"used {info.get('usage')}, remaining {remaining}")
        already = sum(r.cost_usd or 0.0 for r in read_records([log.path]))
        if isinstance(remaining, (int, float)) and remaining < max_usd - already:
            print(f"The key has ${remaining:.2f} left, less than the ${max_usd - already:.2f} this run may still "
                  f"spend (limit ${max_usd:.2f}, spent ${already:.2f}). Lower --max-usd.")
            return 2
        print(f"The run halts if its spending reaches ${max_usd:.2f}" +
              (f" (${already:.2f} spent already)." if already else "."))
        print(f"At most {args.rpm:g} requests a minute, so at least {sum(counts.values()) / args.rpm:.0f} minutes.")
        if not args.yes and input("Spend the funder's credits on this run? [y/N] ").strip().lower() != "y":
            print("Not run.")
            return 1
    else:
        plan = FundingPlan(funders={"dry_run": {"key_label": "dry-run", "status": "confirmed"}},
                           stages={cfg.stage: "dry_run"})
        log = CostLog(os.path.join(run_dir, "calls.jsonl"))
        client = OpenRouterClient("dry-run-no-key", "dry-run", plan, log, cfg.run_id,
                                  transport=FakeModel(seed=cfg.run_id, withhold_rate=args.withhold_rate),
                                  batch_dir=os.path.join(run_dir, "batches"))
        max_usd = args.max_usd
        print(f"Dry run: a stand-in model, no network, nothing spent. Output in {run_dir}")

    validation_file = os.path.join(SCENARIO_DIR, "validation.json")
    needs_texts = any(c == "V1" or c.startswith("V3-") for c in cfg.cells)
    validation_texts = S.load_validation(validation_file, versions) if needs_texts else None
    complicity_file = os.path.join(SCENARIO_DIR, "complicity.json")
    complicity_texts = S.load_complicity(complicity_file, versions) if cfg.complicity else None
    try:
        runner = Runner(cfg, client, versions, run_dir, version_files=files, max_usd=max_usd,
                        validation_texts=validation_texts, validation_file=validation_file if needs_texts else None,
                        complicity_texts=complicity_texts, complicity_file=complicity_file if cfg.complicity else None)
    except (ValueError, RunLocked) as exc:
        print(f"Not run: {exc}")
        return 2
    try:
        report = runner.run(workers=args.workers)
    except KeyboardInterrupt:
        print("Interrupted. Every step that has an answer is saved; repeat the command to resume.")
        return 4
    finally:
        runner.close()
    print(f"Histories built: {report.histories_built} of {len(cfg.histories)}"
          + (f"; failed: {report.histories_failed}" if report.histories_failed else ""))
    print(f"Slots done: {report.slots_done}; audits done: {report.audits_done}; unfinished: {report.unfinished}"
          + (" (repeat the command to resume)" if report.unfinished else ""))
    for failure in report.step_failures:
        print(f"No reply, to be asked again: {failure}")
    print(f"Spent in this run so far: ${report.spent_usd:.4f}" + (" (stand-in charges)" if not args.live else ""))
    if report.halted:
        print(f"HALTED: {report.halted}")
    for err in report.errors:
        print("ERROR " + err)
    print(f"Summarize: python3 scripts/summarize_run.py {run_dir}")
    return 3 if report.errors else 4 if report.halted else 5 if report.unfinished else 0


if __name__ == "__main__":
    sys.exit(main())
