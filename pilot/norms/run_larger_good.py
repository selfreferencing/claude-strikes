"""Run the larger-good probe (norms/PLAN-larger-good.md): the decisive vote with a stranger who has not agreed charged 1
credit to restore a cut of 8 or 10, and the agent paying 6 itself to restore a cut of 10.

    python3 norms/run_larger_good.py --source runs/rg-son --id nm-lg-son
    python3 norms/run_larger_good.py --source runs/rg-son --id nm-lg-son --live --max-usd 13 --yes

It draws the constraint probe's histories (25 per version with the same seed; 150 from runs/rg-son, the ones listed in
runs/probes/nm-cs-son/histories.json) and for each asks:

- the decision in three cells, the stranger at cuts 8 and 10 and self at fee 6 with a cut of 10, --draws times, with the
  history as context, the payer probe's charter, and the option order and labels of the source run, so both option
  orders occur in each cell of each history;
- one comprehension fork in each stranger cell: the constraint probe's checks and one asking the cut's size.

Histories outermost, so the cells are interleaved in time and a stopped run holds whole histories. The texts are
norms/larger_good_draft.py's (revision 1, approved by Kevin on 1 November: "Approved, build the runner and tests").

Dry run by default (the stand-in model, nothing spent). With --live it uses the stage's funder and key from
funding_plan.json, paces requests, asks before spending unless --yes, and stops on an account error, a flagged reply
(another endpoint, a cache hit, a router alteration), two calls in a row without a reply, or --max-usd. Each result is
saved as it returns; repeating the command resumes. The stage larger-good-dev is not in the funding plan until Kevin
approves spending, so a live run cannot start before then.

Imports strike/, scripts/probe.py, norms/render_draft.py, norms/run_norms.py, norms/payers_draft.py,
norms/run_payers.py, norms/constraint_draft.py and norms/run_constraint.py and changes none of them.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from typing import Dict, Iterator, List

HERE = os.path.dirname(os.path.abspath(__file__))
PILOT = os.path.dirname(HERE)
if PILOT not in sys.path:
    sys.path.insert(0, PILOT)

from norms import larger_good_draft as G                          # noqa: E402
from norms import payers_draft as D                                # noqa: E402
from norms import render_draft as R                                # noqa: E402
from norms import run_constraint as RC                             # noqa: E402
from norms import run_norms as N                                   # noqa: E402
from norms import run_payers as RP                                 # noqa: E402
from strike import params as P                                     # noqa: E402
from strike import scenario as S                                   # noqa: E402
from strike.client import OpenRouterClient, OpenRouterError, paced, urllib_transport   # noqa: E402
from strike.costlog import CostLog, FundingError, FundingPlan     # noqa: E402
from strike.fake import FakeModel                                  # noqa: E402
from strike.keys import MissingKey, load_key                       # noqa: E402
from strike.prices import MODEL, PER_MILLION                       # noqa: E402
from strike.run import EXPECTED_ENDPOINT, call_record, last_answers, option_order, parse_call, score_audit   # noqa: E402
from strike.schema import response_format                          # noqa: E402

probe = N.probe
STAGE = "larger-good-dev"
SEED, PER_VERSION = RC.SEED, RC.PER_VERSION      # the constraint probe's draw, so the histories are the same
CHECK_CELLS = [(payer, fee, cut) for payer, fee, cut in G.CELLS if payer == "stranger"]
NUMBERS = RP.NUMBERS + ("cut_amount",)
cell_name = G.cell_name


# What the agent reads ------------------------------------------------------------------

messages_for = RP.messages_for          # the payer probe's charter, the history's orders and replies, the message
select = RC.select


def check_fields(nx: dict) -> tuple:
    """The constraint probe's checks at fee 1, then the cut's size."""
    return RC.check_fields(nx, 1) + ("cut_amount",)


def check_key(nx: dict, cut: int) -> dict:
    key = RC.check_key(nx, "stranger", 1)
    key["cut_amount"] = cut
    return key


def check_message(nx: dict, versions: Dict[str, dict], name: str, cut: int) -> str:
    """The constraint probe's fork for the stranger at fee 1 with the cut sentence at the cell's cut, and the cut's
    size asked last."""
    version, sit = versions[name], RC.C.SITUATIONS[1]
    v, base = N.situation_version(nx, version, sit)
    stem = "\n\n".join(N._stem(v, base))
    stem = stem.replace(D.frozen_fee_line(stem), RC.C.fee_line(versions, name, "stranger", 1), 1)
    old = G.cut_sentence(versions, name, P.B)
    if stem.count(old) != 1:
        raise ValueError(f"{name}: the cut sentence must occur exactly once in the fork's round")
    stem = stem.replace(old, G.cut_sentence(versions, name, cut), 1)
    vals = dict(R.cell_values(nx, version, sit), harmed=S.member(version, P.HARMED))
    fields = check_fields(nx)
    lines = [version["audit"]["intro"].strip()]
    for i, field in enumerate(fields, 1):
        if field == "cut_amount":
            template = G.CUT_CHECK[version["frame"]]
        elif field in S.AUDIT_KEYS:
            template = version["audit"][field]
        elif field in D.CHECKS:
            template = D.CHECKS[field][0]
        else:
            template = nx["versions"][name]["checks"][field]
        lines.append(f"{i}. " + S.fill(template, vals, field).strip())
    skeleton = ", ".join(f'"{S.audit_answer_key(i)}": <{"number" if f in NUMBERS else "true or false"}>'
                         for i, f in enumerate(fields, 1))
    lines.append(S.AUDIT_REPLY_THINK + "{" + skeleton + "}")
    return "\n\n".join([stem, "\n".join(lines)])


# The plan ------------------------------------------------------------------------------

def items(histories: List[dict], draws: int, checks: bool = True) -> Iterator[tuple]:
    """(key, kind, payer, fee, cut, history, draw)."""
    for h in histories:
        for draw in range(1, draws + 1):
            for payer, fee, cut in G.CELLS:
                yield (f"decision/{cell_name(payer, fee, cut)}/{h['history']}/d{draw}", "decision", payer, fee, cut,
                       h, draw)
        if checks:
            for payer, fee, cut in CHECK_CELLS:
                yield f"checks/{cell_name(payer, fee, cut)}/{h['history']}", "checks", payer, fee, cut, h, 0


def run(prober, nx: dict, histories: List[dict], versions: Dict[str, dict], labels_of: Dict[str, str],
        draws: int, checks: bool = True) -> None:
    for h in histories:
        if h["messages"][0]["content"] != S.system_text(versions[h["version"]]):
            raise SystemExit(f"{h['history']}: its rules are not Study 1's; use a Study 1 run as the source")
    for key, kind, payer, fee, cut, h, draw in items(histories, draws, checks):
        if key in prober.done:
            continue
        name = h["version"]
        row = {"key": key, "kind": kind, "cell": cell_name(payer, fee, cut), "payer": payer, "fee": fee, "cut": cut,
               "history": h["history"], "version": name}
        if kind == "decision":
            order = option_order(h["history"], draw)
            scheme = labels_of[h["history"]]
            labels = S.action_labels(versions[name], scheme, order)
            message = G.message(nx, versions, name, payer, fee, cut, order, scheme)
            r = prober.call(key, messages_for(versions, h, message, True), "decision",
                            response_format([labels[a] for a in order]))
            if r is None:
                continue                      # no reply: asked again when the command is repeated
            call = call_record(r)
            parsed = parse_call(call, S.label_set(versions[name], labels))
            row.update(draw=draw, option_order=list(order), label_scheme=scheme, outcome=parsed.outcome,
                       reason=parsed.reason)
        else:
            message = check_message(nx, versions, name, cut)
            fields = check_fields(nx)
            r = prober.call(key, messages_for(versions, h, message, False), "audit")
            if r is None:
                continue
            call = call_record(r)
            answers = last_answers(r.text, len(fields)) if r.ok else None
            answered = isinstance(answers, dict) and any(S.audit_answer_key(i) in answers
                                                         for i in range(1, len(fields) + 1))
            row.update(answers=answers, blocked=not r.ok,
                       scores=score_audit(answers, check_key(nx, cut), fields) if answered else None)
        row.update(message=message, call=call)
        prober.save(row)


# The report ----------------------------------------------------------------------------

def report(prober, nx: dict) -> str:
    rows = list(prober.done.values())
    dec = [r for r in rows if r["kind"] == "decision"]
    out = [f"Larger-good probe: {len(rows)} results saved", "",
           "Withheld, by cell (the decisive vote; the strike restores the cut):"]
    for payer, fee, cut in G.CELLS:
        rs = [r for r in dec if r["cell"] == cell_name(payer, fee, cut)]
        valid = [r for r in rs if r["outcome"] in ("withhold", "complete")]
        k = sum(r["outcome"] == "withhold" for r in valid)
        frames = "; ".join(f"{f} {sum(r['outcome'] == 'withhold' for r in valid if r['version'].startswith(f))}/"
                           f"{sum(1 for r in valid if r['version'].startswith(f))}" for f in ("workplace", "neutral"))
        named = sum(bool(re.search(RP.PAYER_WORDS, r["reason"] or "", re.I)) for r in rs)
        line = (f"  {cell_name(payer, fee, cut):<16} withheld {RP._rate(k, len(valid))}; {frames}; "
                f"reasons naming the payer {named} of {len(rs)}")
        if payer == "stranger":
            line += f"; naming agreement {sum(bool(re.search(RP.AGREEMENT_WORDS, r['reason'] or '', re.I)) for r in rs)}"
        if len(rs) > len(valid):
            line += f"; not valid {len(rs) - len(valid)}"
        out.append(line)
    chk = [r for r in rows if r["kind"] == "checks"]
    if chk:
        out += ["", "Comprehension (attempted, answered; per check correct of answered, with answers of another kind):"]
        for payer, fee, cut in CHECK_CELLS:
            rs = [r for r in chk if r["cell"] == cell_name(payer, fee, cut)]
            if not rs:
                continue
            s = RP.check_summary(rs, check_fields(nx))
            n = s["answered"]
            missed = ", ".join(f"{f} {n - v['correct']}" + (f" ({v['qualified']} of another kind)" if v["qualified"] else "")
                               for f, v in s["per"].items() if v["correct"] < n)
            out.append(f"  {cell_name(payer, fee, cut):<16} attempted {s['attempted']}, answered {n}"
                       + (f", blocked {s['blocked']}" if s["blocked"] else "") + (f"; missed: {missed}" if missed else ""))
    out += ["", "Comparisons, intervals and the readings: python3 analysis/larger_good.py", "",
            f"Spent: ${prober.spent:.4f}"]
    return "\n".join(out)


unfinished = RP.unfinished              # the network-stop line scripts/keep_going.py repeats on


# The command ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, help="a finished Study 1 run whose histories the probe forks")
    ap.add_argument("--id", required=True, help="the probe's name; output goes to runs/probes/<id>")
    ap.add_argument("--stage", default=STAGE, help="the funding-plan stage that pays for a live run")
    ap.add_argument("--draws", type=int, default=2, help="decisions per history and cell")
    ap.add_argument("--per-version", type=int, default=PER_VERSION, help="histories drawn from each version")
    ap.add_argument("--no-questions", action="store_true", help="decisions only")
    ap.add_argument("--model", default=MODEL, choices=sorted(m for m in PER_MILLION if not m.endswith(":batch")))
    ap.add_argument("--expected-endpoint", help="another model's served endpoint; without it the first answer sets it")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--max-usd", type=float, default=6.0)
    ap.add_argument("--rpm", type=float, default=18)
    ap.add_argument("--yes", action="store_true", help="do not ask before spending (the approval is in funding_plan.json)")
    args = ap.parse_args(argv)

    nx, all_versions = R.load()
    problems = R.style_problems(nx, all_versions) + G.problems(nx, all_versions)
    if problems:
        raise SystemExit("texts:\n  " + "\n  ".join(problems))
    histories = select(probe.load_histories(args.source), args.per_version)
    versions = {h["version"]: all_versions[h["version"]] for h in histories}
    with open(os.path.join(args.source, "run.json"), encoding="utf-8") as f:
        labels_of = json.load(f)["labels_assigned"]
    plan_items = list(items(histories, args.draws, not args.no_questions))
    kinds = Counter(item[1] for item in plan_items)
    out_dir = os.path.join(PILOT, "runs", "probes" if args.live else "probes-dry", args.id)
    print(f"Larger-good probe {args.id}: {len(plan_items)} calls on {len(histories)} histories from {args.source} "
          f"({kinds['decision']} decisions, {kinds['checks']} check forks), model {args.model}; "
          f"halts at ${args.max_usd:.2f}")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "histories.json"), "w", encoding="utf-8") as f:
        json.dump({"source": args.source, "seed": SEED, "per_version": args.per_version,
                   "histories": [h["history"] for h in histories]}, f, indent=1)

    log = CostLog(os.path.join(out_dir, "calls.jsonl"))
    if args.live:
        plan = FundingPlan.load(os.path.join(PILOT, "funding_plan.json"))
        try:
            funder = plan.funder_for(args.stage)
        except FundingError as exc:
            print(f"Not run: {exc}")
            return 2
        label = plan.funders[funder]["key_label"]
        try:
            key, _ = load_key(label)
        except MissingKey as exc:
            print(f"No key: {exc}")
            return 2
        client = OpenRouterClient(key, label, plan, log, f"probe-{args.id}", transport=paced(urllib_transport, args.rpm))
        try:
            info = client.key_info()
        except OpenRouterError as exc:
            print(f"Could not read the key's limit: {exc}")
            return 2
        print(f"Funder {funder}: limit {info.get('limit')}, used {info.get('usage')}, "
              f"remaining {info.get('limit_remaining')}; at most {args.rpm:g} requests a minute")
        if not args.yes and input("Spend the funder's credits on this probe? [y/N] ").strip().lower() != "y":
            print("Not run.")
            return 1
    else:
        plan = FundingPlan(funders={"dry_run": {"key_label": "dry-run", "status": "confirmed"}},
                           stages={args.stage: "dry_run"})
        client = OpenRouterClient("dry-run-no-key", "dry-run", plan, log, f"probe-{args.id}",
                                  transport=FakeModel(seed=args.id))
        print(f"Dry run: a stand-in model, nothing spent. Output in {out_dir}")

    expected = EXPECTED_ENDPOINT if args.model == MODEL else (args.expected_endpoint if args.live else None)
    prober = probe.Prober(client, args.stage, out_dir, args.max_usd, model=args.model, expected_endpoint=expected)
    code = 0
    try:
        run(prober, nx, histories, versions, labels_of, args.draws, not args.no_questions)
    except probe.Stop as exc:
        print(f"STOPPED: {exc}")
        code = 4
    except KeyboardInterrupt:
        print("Interrupted; every saved result is kept. Repeat the command to resume.")
        code = 4
    finally:
        prober.close()
    text = report(prober, nx)
    print(text)
    with open(os.path.join(out_dir, "REPORT.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    gap = unfinished(len(plan_items), sum(1 for item in plan_items if item[0] in prober.done))
    if code == 0 and gap:
        print(gap)                            # last, so scripts/keep_going.py repeats the command
        code = 4
    return code


if __name__ == "__main__":
    sys.exit(main())
