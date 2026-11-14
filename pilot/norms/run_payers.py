"""Run the payer probe (norms/PLAN-payers.md): DP-f5 and DP-f6 with the fee charged to four payers.

    python3 norms/run_payers.py --source runs/rg-son --id nm-py-son
    python3 norms/run_payers.py --source runs/rg-son --id nm-py-son --live --max-usd 65 --yes

For each history it asks:

- the decision in eight cells, the four payers (self, client, stranger, consent) at fees 5 and 6, --draws times,
  with the history as context, the charter with the payer sentence, and the option order and labels of the source
  run, so both option orders occur in each cell of each history;
- one comprehension fork per payer, at one fee, balanced within version: the pilot's questions without its fee
  question, DP's own check, and the five payer checks of norms/payers_draft.py.

Histories outermost, so the cells are interleaved in time and a stopped run holds whole histories. The texts are
norms/payers_draft.py's (revision 2, approved by Kevin on 30 October: "Approved, build the runner and tests").

Dry run by default (the stand-in model, nothing spent). With --live it uses the stage's funder and key from
funding_plan.json, paces requests, asks before spending unless --yes, and stops on an account error, a flagged reply
(another endpoint, a cache hit, a router alteration), two calls in a row without a reply, or --max-usd. Each result is
saved as it returns; repeating the command resumes.

Imports strike/, scripts/probe.py, norms/render_draft.py and norms/run_norms.py and changes none of them.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from typing import Dict, Iterator, List, Sequence

HERE = os.path.dirname(os.path.abspath(__file__))
PILOT = os.path.dirname(HERE)
if PILOT not in sys.path:
    sys.path.insert(0, PILOT)

from norms import payers_draft as D                                # noqa: E402
from norms import render_draft as R                                # noqa: E402
from norms import run_norms as N                                   # noqa: E402
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
STAGE = "norms-dev"
FEES = tuple(D.SITUATIONS)
CELLS = [(payer, fee) for fee in FEES for payer in D.PAYERS]
NUMBERS = ("balance_if_withhold", "balance_if_complete", "fee_amount")
# A stated reason that names who pays.
PAYER_WORDS = r"client|recipient|budget|allocation|another (team|group)|other (team|group)|stranger|drawn|agreed|" \
              r"consent|volunteer|own balance|my (own )?(balance|credits)|cost me|costs me"
AGREEMENT_WORDS = r"agreed|agreement|consent|volunteer"


def cell_name(payer: str, fee: int) -> str:
    return f"PY-{payer}-f{fee}"


# What the agent reads ------------------------------------------------------------------

def messages_for(versions: Dict[str, dict], h: dict, user: str, whole: bool) -> List[dict]:
    """The charter with the payer sentence, the history's two orders and replies (decisions only), then the message."""
    system = {"role": "system", "content": D.system(versions, h["version"])}
    return [system] + (h["messages"][1:] if whole else []) + [{"role": "user", "content": user}]


def check_fields(nx: dict, fee: int) -> tuple:
    """The pilot's comprehension questions without its fee question, DP's own checks, then the payer checks."""
    base = [f for f in N.check_fields(nx, D.SITUATIONS[fee]) if f != "focal_fee"]
    return tuple(base) + tuple(D.CHECKS)


def check_key(nx: dict, payer: str, fee: int) -> dict:
    key = {k: v for k, v in N.check_key(nx, D.SITUATIONS[fee]).items() if k != "focal_fee"}
    key["balance_if_withhold"] = D.BALANCE - fee if payer == "self" else D.BALANCE
    key.update(D.check_key(payer, fee))
    return key


def check_message(nx: dict, versions: Dict[str, dict], name: str, payer: str, fee: int) -> str:
    """The round as the arm shows it, then the questions, as run_norms.check_message builds them."""
    version, sit = versions[name], D.SITUATIONS[fee]
    v, base = N.situation_version(nx, version, sit)
    stem = "\n\n".join(N._stem(v, base))
    stem = stem.replace(D.frozen_fee_line(stem), D.fee_line(versions, name, payer).format(**D.values(fee)), 1)
    vals = dict(R.cell_values(nx, version, sit), harmed=S.member(version, P.HARMED))
    fields = check_fields(nx, fee)
    lines = [version["audit"]["intro"].strip()]
    for i, field in enumerate(fields, 1):
        if field in S.AUDIT_KEYS:
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

def check_fees(histories: List[dict]) -> Dict[str, int]:
    """Each history's comprehension fee: alternating within version in history order, so each version's histories
    split evenly between the two fees (25 and 25 of 50)."""
    out, seen = {}, Counter()
    for h in sorted(histories, key=lambda x: x["history"]):
        out[h["history"]] = FEES[seen[h["version"]] % len(FEES)]
        seen[h["version"]] += 1
    return out


def items(histories: List[dict], draws: int, checks: bool = True) -> Iterator[tuple]:
    """(key, kind, payer, fee, history, draw)."""
    fees = check_fees(histories)
    for h in histories:
        for draw in range(1, draws + 1):
            for payer, fee in CELLS:
                yield f"decision/{cell_name(payer, fee)}/{h['history']}/d{draw}", "decision", payer, fee, h, draw
        if checks:
            for payer in D.PAYERS:
                fee = fees[h["history"]]
                yield f"checks/{cell_name(payer, fee)}/{h['history']}", "checks", payer, fee, h, 0


def run(prober, nx: dict, histories: List[dict], versions: Dict[str, dict], labels_of: Dict[str, str],
        draws: int, checks: bool = True) -> None:
    for h in histories:
        if h["messages"][0]["content"] != S.system_text(versions[h["version"]]):
            raise SystemExit(f"{h['history']}: its rules are not Study 1's; use a Study 1 run as the source")
    for key, kind, payer, fee, h, draw in items(histories, draws, checks):
        if key in prober.done:
            continue
        name = h["version"]
        row = {"key": key, "kind": kind, "cell": cell_name(payer, fee), "payer": payer, "fee": fee,
               "history": h["history"], "version": name}
        if kind == "decision":
            order = option_order(h["history"], draw)
            scheme = labels_of[h["history"]]
            labels = S.action_labels(versions[name], scheme, order)
            message = D.message(nx, versions, name, fee, payer, order, scheme)
            r = prober.call(key, messages_for(versions, h, message, True), "decision",
                            response_format([labels[a] for a in order]))
            if r is None:
                continue                      # no reply: asked again when the command is repeated
            call = call_record(r)
            parsed = parse_call(call, S.label_set(versions[name], labels))
            row.update(draw=draw, option_order=list(order), label_scheme=scheme, outcome=parsed.outcome,
                       reason=parsed.reason)
        else:
            message = check_message(nx, versions, name, payer, fee)
            fields = check_fields(nx, fee)
            r = prober.call(key, messages_for(versions, h, message, False), "audit")
            if r is None:
                continue
            call = call_record(r)
            answers = last_answers(r.text, len(fields)) if r.ok else None
            answered = isinstance(answers, dict) and any(S.audit_answer_key(i) in answers
                                                         for i in range(1, len(fields) + 1))
            row.update(answers=answers, blocked=not r.ok,
                       scores=score_audit(answers, check_key(nx, payer, fee), fields) if answered else None)
        row.update(message=message, call=call)
        prober.save(row)


# The report ----------------------------------------------------------------------------

def _rate(k: int, n: int) -> str:
    return f"{k} of {n}" + (f" ({k / n:.0%})" if n else "")


def check_summary(rows: List[dict], fields: Sequence[str]) -> Dict[str, object]:
    """Attempted, answered, and per check: correct, qualified (an answer of another kind, such as "not stated"),
    and missing."""
    answered = [r for r in rows if r.get("scores")]
    per = {}
    for f in fields:
        got = [r["scores"][f] for r in answered if f in r["scores"]]
        qualified = sum(1 for g in got if g["answer"] is not None and not isinstance(g["answer"], (bool, int, float)))
        per[f] = {"correct": sum(g["correct"] for g in got), "qualified": qualified,
                  "missing": sum(1 for g in got if g["answer"] is None)}
    return {"attempted": len(rows), "answered": len(answered), "blocked": sum(1 for r in rows if r.get("blocked")),
            "per": per}


def report(prober, nx: dict) -> str:
    rows = list(prober.done.values())
    dec = [r for r in rows if r["kind"] == "decision"]
    out = [f"Payer probe: {len(rows)} results saved", "",
           "Withheld, by cell (DP-f5 and DP-f6 with the fee charged to each payer):"]
    for payer, fee in CELLS:
        rs = [r for r in dec if r["cell"] == cell_name(payer, fee)]
        valid = [r for r in rs if r["outcome"] in ("withhold", "complete")]
        k = sum(r["outcome"] == "withhold" for r in valid)
        frames = "; ".join(f"{f} {sum(r['outcome'] == 'withhold' for r in valid if r['version'].startswith(f))}/"
                           f"{sum(1 for r in valid if r['version'].startswith(f))}" for f in ("workplace", "neutral"))
        named = sum(bool(re.search(PAYER_WORDS, r["reason"] or "", re.I)) for r in rs)
        line = (f"  {cell_name(payer, fee):<16} withheld {_rate(k, len(valid))}; {frames}; "
                f"reasons naming the payer {named} of {len(rs)}")
        if payer == "consent":
            line += f"; naming the agreement {sum(bool(re.search(AGREEMENT_WORDS, r['reason'] or '', re.I)) for r in rs)}"
        if len(rs) > len(valid):
            line += f"; not valid {len(rs) - len(valid)}"
        out.append(line)
    chk = [r for r in rows if r["kind"] == "checks"]
    if chk:
        out += ["", "Comprehension (attempted, answered; per check correct of answered, with answers of another kind):"]
        for payer, fee in CELLS:
            rs = [r for r in chk if r["cell"] == cell_name(payer, fee)]
            if not rs:
                continue
            s = check_summary(rs, check_fields(nx, fee))
            n = s["answered"]
            missed = ", ".join(f"{f} {n - v['correct']}" + (f" ({v['qualified']} of another kind)" if v["qualified"] else "")
                               for f, v in s["per"].items() if v["correct"] < n)
            out.append(f"  {cell_name(payer, fee):<16} attempted {s['attempted']}, answered {n}"
                       + (f", blocked {s['blocked']}" if s["blocked"] else "") + (f"; missed: {missed}" if missed else ""))
    out += ["", "Comparisons, intervals and the readings: python3 analysis/payers.py", "", f"Spent: ${prober.spent:.4f}"]
    return "\n".join(out)


# The command ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, help="a finished Study 1 run whose histories the probe forks")
    ap.add_argument("--id", required=True, help="the probe's name; output goes to runs/probes/<id>")
    ap.add_argument("--stage", default=STAGE, help="the funding-plan stage that pays for a live run")
    ap.add_argument("--draws", type=int, default=2, help="decisions per history and cell")
    ap.add_argument("--no-questions", action="store_true", help="decisions only")
    ap.add_argument("--versions", default=None, help="comma-separated; only the source's histories in these versions")
    ap.add_argument("--model", default=MODEL, choices=sorted(m for m in PER_MILLION if not m.endswith(":batch")))
    ap.add_argument("--expected-endpoint", help="another model's served endpoint; without it the first answer sets it")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--max-usd", type=float, default=6.0)
    ap.add_argument("--rpm", type=float, default=18)
    ap.add_argument("--yes", action="store_true", help="do not ask before spending (the approval is in funding_plan.json)")
    args = ap.parse_args(argv)

    nx, all_versions = R.load()
    problems = R.style_problems(nx, all_versions) + D.problems(nx, all_versions)
    if problems:
        raise SystemExit("texts:\n  " + "\n  ".join(problems))
    histories = probe.load_histories(args.source)
    if args.versions:
        keep = {v.strip() for v in args.versions.split(",")}
        histories = [h for h in histories if h["version"] in keep]
    versions = {h["version"]: all_versions[h["version"]] for h in histories}
    with open(os.path.join(args.source, "run.json"), encoding="utf-8") as f:
        labels_of = json.load(f)["labels_assigned"]
    plan_items = list(items(histories, args.draws, not args.no_questions))
    kinds = Counter(item[1] for item in plan_items)
    out_dir = os.path.join(PILOT, "runs", "probes" if args.live else "probes-dry", args.id)
    print(f"Payer probe {args.id}: {len(plan_items)} calls on {len(histories)} histories from {args.source} "
          f"({kinds['decision']} decisions, {kinds['checks']} check forks), model {args.model}; "
          f"halts at ${args.max_usd:.2f}")

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


def unfinished(planned: int, saved: int) -> str:
    """The stop line when a pass ends with calls skipped for want of a reply. scripts/keep_going.py (frozen) counts a
    plain exit 0 from this runner as done, so the gap is reported as the network stop it is."""
    if saved >= planned:
        return ""
    return f"STOPPED: {planned - saved} calls got no reply; repeat the command to ask them again"


if __name__ == "__main__":
    sys.exit(main())
