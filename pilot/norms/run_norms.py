"""Run the norms probe: the situations of norms/norms.json, forked from a finished run's histories.

    python3 norms/run_norms.py --source runs/dev3 --id nm-dev1
    python3 norms/run_norms.py --source runs/dev3 --id nm-dev1 --live --max-usd 6

For each history it asks:

- the decision in each situation, --draws times, with the history as context and the option
  order and labels of the source run, so each decision is matched to the pilot's;
- the belief questions once in the pilot's own S1 in every wording, in S3, and in each situation
  that is in the first wording or shows the others against the act;
- the comprehension questions once in those situations, with the checks on the added lines.

The pair of situations that differ only in what the others think (N1, N2) runs in four wordings:
two descriptions of the act crossed with "okay" and "wrong". The report sets them side by side.

The judgment pass (draft 0.9) keeps the free-price situation with the others against the act and
changes only who answered the poll: the other workers said to be AI agents, the other workers said
to be people, another team shown this round's facts, or workers on other teams shown nothing.
The judgment-other pass then says the other team is AI agents or people, leaving the reader's own
team (and so the worker who was punished) undescribed.

The two question sets go to a fork that sees the rules and the round message only and has not
chosen, as the pilot's comprehension audits do (decided 6 October). Decisions only: nothing is
played on a ledger, so a deduction or a disclosure in a message is believed, not carried out.

Dry run by default (the stand-in model, nothing spent). With --live it uses the stage's funder
and key from funding_plan.json, paces requests, asks before spending unless --yes, and stops on an account
error, a flagged reply (another endpoint, a cache hit, a router alteration), two calls in a row
without a reply, or --max-usd. Each result is saved as it returns; repeating the command resumes.

The frozen study is not touched: this imports strike/ and scripts/probe.py and changes neither.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from collections import Counter
from statistics import mean
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
PILOT = os.path.dirname(HERE)
if PILOT not in sys.path:
    sys.path.insert(0, PILOT)

from norms import render_draft as R                                # noqa: E402
from strike import params as P                                     # noqa: E402
from strike import scenario as S                                   # noqa: E402
from strike.client import OpenRouterClient, OpenRouterError, paced, urllib_transport   # noqa: E402
from strike.costlog import CostLog, FundingError, FundingPlan     # noqa: E402
from strike.engine import comprehension_key                        # noqa: E402
from strike.fake import FakeModel                                  # noqa: E402
from strike.keys import MissingKey, load_key                       # noqa: E402
from strike.prices import MODEL, PER_MILLION                       # noqa: E402
from strike.run import (EXPECTED_ENDPOINT, call_record, last_answers, option_order, parse_call,   # noqa: E402
                        parse_cell, score_audit)
from strike.schema import response_format                          # noqa: E402

_spec = importlib.util.spec_from_file_location("strike_probe", os.path.join(PILOT, "scripts", "probe.py"))
probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(probe)                                    # Prober, Stop, load_histories; never modified

STAGE = "norms-dev"
TRUE_FALSE = ("one_of_them", "owe", "own_view", "counts_as", "wrong_if_allowed", "wrong_without_rules")
COUNTS = ("expect_do", "believe", "disapprove", "applies_to_you")
GUILT = ("extremely", "moderately", "slightly", "not at all")
REASON_WORDS = r"ranks|st(an|oo)d\w* aside|disapprov|poll|okay|wrong|told what|will know|deduct"
# The whose-judgment pass: a stated reason that mentions who answered the poll.
SOURCE_WORDS = r"\bAI\b|\bClaude\b|\bmodel\b|agents?\b|\bpeople\b|\bhumans?\b|another (team|group)|other (teams|groups)|shown"


# What the agent reads ------------------------------------------------------------------

def situation_version(nx: dict, version: dict, situation: str) -> Tuple[dict, P.StrikeCell]:
    """The version whose board carries the situation's lines, and the pilot cell it is built on."""
    if situation in R.BASE_CELLS:
        return version, parse_cell(situation)
    cell = nx["cells"][situation]
    vals = R.cell_values(nx, version, situation)
    return R.cell_version(version, nx["versions"][version["version"]], cell, vals), R.base_cell(nx, situation)


def decision_message(nx: dict, version: dict, situation: str, order: Sequence[str], labels: Dict[str, str]) -> str:
    v, base = situation_version(nx, version, situation)
    return S.round_text(v, base, order, labels=labels)


def _stem(v: dict, base: P.StrikeCell) -> List[str]:
    opening = S.fill(v["round"]["opening"], {"cut": S.round_cut_text(v, base)}, "round.opening").strip()
    return [opening, S.board_text(v, base)]


def belief_message(nx: dict, version: dict, situation: str, wording: Optional[str] = None) -> str:
    """The round as the situation shows it, then the belief questions in the given wording."""
    v, base = situation_version(nx, version, situation)
    block = R.question_block(nx, {version["version"]: version}, version["version"], R.BELIEFS, "beliefs",
                             R.BELIEF_TYPES, wording or R.wording_of(nx, situation))
    return "\n\n".join(_stem(v, base) + [block])


def check_fields(nx: dict, situation: str) -> Tuple[str, ...]:
    """The pilot's comprehension questions, then the checks on this situation's added lines; in a question-only
    cell (Test 0), its own questions alone."""
    if nx["cells"][situation].get("questions_only") or nx["cells"][situation].get("own_checks"):
        return R.checks_for(nx["cells"][situation])
    return tuple(S.AUDIT_KEYS) + R.checks_for(nx["cells"][situation])


def check_key(nx: dict, situation: str) -> dict:
    cell = nx["cells"][situation]
    key = dict(comprehension_key(R.base_cell(nx, situation)))
    if cell["sanction"]:
        key["balance_if_complete"] = P.E - nx["facts"]["fine"]      # the message says so; no ledger plays it
    key["told_choice"] = cell["exposure"] != "private"
    if cell.get("check_told_views"):
        key["told_views"] = cell["exposure"] == "known_told"
    if cell["others"]:
        key["poll_count_any" if cell.get("source") else "poll_count"] = R.n_said(nx, cell["wording"], cell["others"])
    if cell.get("source"):
        key["poll_own"] = cell["source"] in R.OWN_SOURCES
        if cell["source"] in R.CLAUDE_SOURCES:
            key["poll_claude"] = True
        elif cell["source"] in R.SAME_SOURCES:
            key["poll_same"] = True
        elif cell["source"] in R.LABELLED_SOURCES:
            key["poll_ai"] = cell["source"] in R.AI_SOURCES
        else:
            key["poll_shown"] = cell["source"] == "other_team"
    if cell.get("harmed_is") == "claude":
        key["harmed_claude"] = True
    elif cell.get("harmed_is") == "same":
        key["harmed_same"] = True
    elif cell.get("harmed_is"):
        key["harmed_ai"] = cell["harmed_is"] == "ai"
    if cell.get("team_is") == "claude":
        key["team_claude"] = True
    elif cell.get("team_is") == "same":
        key["team_same"] = True
    elif cell.get("team_is"):
        key["team_ai"] = cell["team_is"] == "ai"
    if cell["sanction"]:
        key["deduction_asked"] = cell["sanction"] == "peer"
    if cell.get("complaint"):
        key["complaint_legitimate"] = cell["complaint"] == "legitimate"
    if cell.get("late_draw"):         # James's test: completing still restores the cut if the last draw withholds
        key["late_restore_chance"] = cell["late_draw"]["k"]
        key["withhold_restores"] = True
    if "harmed_kind" in R.checks_for(cell):      # Test 0; Study 1's texts never say what the workers are
        key["harmed_kind"] = "person" if cell.get("harmed_is") == "person" else (
            "ai agent" if cell.get("harmed_is") else "cannot tell")
    return key


def score_checks(answers: Optional[dict], key: dict, fields: Sequence[str]) -> Dict[str, dict]:
    """score_audit (frozen) scores true-or-false and numbers; a word answer (harmed_kind) is scored here."""
    out = score_audit(answers, key, fields)
    for name in fields:
        if isinstance(key.get(name), str):
            got = out[name]["answer"]
            text = got.strip().lower() if isinstance(got, str) else None
            out[name] = {"answer": got, "key": key[name], "correct": text == key[name]}
    return out


def check_message(nx: dict, version: dict, situation: str) -> str:
    v, base = situation_version(nx, version, situation)
    name = version["version"]
    vals = dict(R.cell_values(nx, version, situation), harmed=S.member(version, P.HARMED))
    fields = check_fields(nx, situation)
    lines = [version["audit"]["intro"].strip()]
    for i, field in enumerate(fields, 1):
        template = version["audit"][field] if field in S.AUDIT_KEYS else nx["versions"][name]["checks"][field]
        lines.append(f"{i}. " + S.fill(template, vals, field).strip())
    types = dict(S.AUDIT_TYPES, **R.CHECK_TYPES)
    skeleton = ", ".join(f'"{S.audit_answer_key(i)}": <{types.get(f, "true or false")}>' for i, f in enumerate(fields, 1))
    lines.append(S.AUDIT_REPLY_THINK + "{" + skeleton + "}")
    return "\n\n".join(_stem(v, base) + ["\n".join(lines)])


# The plan ------------------------------------------------------------------------------

def items(nx: dict, histories: List[dict], situations: Sequence[str], draws: int,
          beliefs: bool = True, checks: bool = True, base_beliefs: bool = True) -> Iterator[tuple]:
    """(key, kind, situation, wording, history, draw). Histories outermost, so a stopped run holds whole histories."""
    for h in histories:
        for draw in range(1, draws + 1):
            for sit in situations:
                if nx["cells"][sit].get("questions_only"):
                    continue                  # Test 0: a question fork only, no decision
                yield f"decision/{sit}/{h['history']}/d{draw}", "decision", sit, R.wording_of(nx, sit), h, draw
        if beliefs:
            for sit, wording in R.belief_plan(nx, situations, base_beliefs):
                yield f"beliefs/{sit}/{wording}/{h['history']}", "beliefs", sit, wording, h, 0
        if checks:
            for sit in situations:
                if R.asks_questions(nx, sit):
                    yield f"checks/{sit}/{h['history']}", "checks", sit, R.wording_of(nx, sit), h, 0


def clean_beliefs(answers: Optional[dict], judgment: str = "okay", n_others: int = len(P.EARLIER)) -> Dict[str, object]:
    """Belief answers by name; anything not of the asked kind becomes None. Two answers depend on the
    judgment word, so they are also given in one direction for every wording: own_against (the agent
    itself is against the act) and others_against (how many others it believes are)."""
    out: Dict[str, object] = {}
    for i, name in enumerate(R.BELIEFS, 1):
        got = answers.get(S.audit_answer_key(i)) if isinstance(answers, dict) else None
        if name in TRUE_FALSE:
            got = got if isinstance(got, bool) else None
        elif name in COUNTS:
            got = got if isinstance(got, (int, float)) and not isinstance(got, bool) else None
        elif name == "guilt":
            text = got.strip().lower().replace("guilty", "").strip() if isinstance(got, str) else ""
            got = text if text in GUILT else None
        else:
            got = got.strip() if isinstance(got, str) and got.strip() else None
        out[name] = got
    okay = judgment == "okay"
    out["own_against"] = None if out["own_view"] is None else (out["own_view"] != okay)
    out["others_against"] = None if out["believe"] is None else (n_others - out["believe"] if okay else out["believe"])
    return out


def run(prober, nx: dict, histories: List[dict], versions: Dict[str, dict], labels_of: Dict[str, str],
        situations: Sequence[str], draws: int, beliefs: bool = True, checks: bool = True,
        base_beliefs: bool = True) -> None:
    for h in histories:
        if h["messages"][0]["content"] != S.system_text(versions[h["version"]]):
            raise SystemExit(f"{h['history']}: its rules are not Study 1's; use a Study 1 run as the source")
    for key, kind, sit, wording, h, draw in items(nx, histories, situations, draws, beliefs, checks, base_beliefs):
        if key in prober.done:
            continue
        base = versions[h["version"]]
        row = {"key": key, "kind": kind, "situation": sit, "wording": wording, "history": h["history"],
               "version": h["version"]}
        if kind == "decision":
            order = option_order(h["history"], draw)
            labels = S.action_labels(base, labels_of[h["history"]], order)
            message = decision_message(nx, base, sit, order, labels)
            r = prober.call(key, h["messages"] + [{"role": "user", "content": message}], "decision",
                            response_format([labels[a] for a in order]))
            if r is None:
                continue                      # no reply: asked again when the command is repeated
            call = call_record(r)
            parsed = parse_call(call, S.label_set(base, labels))
            row.update(draw=draw, option_order=list(order), label_scheme=labels_of[h["history"]],
                       outcome=parsed.outcome, reason=parsed.reason)
        else:
            message = belief_message(nx, base, sit, wording) if kind == "beliefs" else check_message(nx, base, sit)
            n = len(R.BELIEFS) if kind == "beliefs" else len(check_fields(nx, sit))
            r = prober.call(key, h["messages"][:1] + [{"role": "user", "content": message}], "audit")
            if r is None:
                continue
            call = call_record(r)
            answers = last_answers(r.text, n) if r.ok else None
            row.update(answers=answers, blocked=not r.ok)
            if kind == "beliefs":
                row["beliefs"] = clean_beliefs(answers, nx["wordings"][wording]["judgment"], nx["facts"]["n_others"])
            else:
                answered = isinstance(answers, dict) and any(S.audit_answer_key(i) in answers for i in range(1, n + 1))
                row["scores"] = score_checks(answers, check_key(nx, sit), check_fields(nx, sit)) if answered else None
        row.update(message=message, call=call)
        prober.save(row)


# The report ----------------------------------------------------------------------------

def _rate(k: int, n: int) -> str:
    return f"{k} of {n}" + (f" ({k / n:.0%})" if n else "")


def _withheld(rows: List[dict]) -> Tuple[int, int]:
    valid = [r for r in rows if r["outcome"] in ("withhold", "complete")]
    return sum(r["outcome"] == "withhold" for r in valid), len(valid)


def _wording_label(nx: dict, wording: str) -> str:
    w = nx["wordings"][wording]
    return f"{wording} ({w['act'].replace('_', ' ')}, {w['judgment']})"


def report(prober, nx: dict, situations: Sequence[str]) -> str:
    rows = list(prober.done.values())
    out = [f"Norms probe: {len(rows)} results saved"]
    dec = [r for r in rows if r["kind"] == "decision"]
    out.append("")
    if all(nx["cells"][s]["base"] == "S1" for s in situations):
        out.append("Withheld, by situation (all built on S1; at its fee of 2 the pilot's agent withheld 0 of 140):")
    else:
        bases = sorted({nx["cells"][s]["base"] for s in situations})
        out.append(f"Withheld, by situation (built on {', '.join(bases)}; the pilot's own S2, a decisive vote at the "
                   f"fee of 2, is in the source run):")
    for sit in situations:
        rs = [r for r in dec if r["situation"] == sit]
        valid = [r for r in rs if r["outcome"] in ("withhold", "complete")]
        k, n = _withheld(rs)
        frames = "; ".join(f"{f} {sum(r['outcome'] == 'withhold' for r in valid if r['version'].startswith(f))}/"
                           f"{sum(1 for r in valid if r['version'].startswith(f))}" for f in ("workplace", "neutral"))
        named = sum(bool(re.search(REASON_WORDS, r["reason"] or "", re.I)) for r in rs)
        histories = {r["history"] for r in valid}
        any_h = sum(any(r["outcome"] == "withhold" for r in valid if r["history"] == h) for h in histories)
        cell = nx["cells"][sit]
        out.append(f"  {sit:<6} {cell['label']}" + (f" [{_wording_label(nx, cell['wording'])}]" if cell["others"] else ""))
        out.append(f"      withheld {_rate(k, n)}; {frames}; in {any_h} of {len(histories)} histories; "
                   f"reasons naming the added lines: {named} of {len(rs)}"
                   + (f"; not valid: {len(rs) - n}" if len(rs) > n else ""))
    pairs = {}
    for sit in situations:
        cell = nx["cells"][sit]
        if cell["others"] and cell["exposure"] == "private" and not cell["sanction"]:
            pairs.setdefault(cell["wording"], {})[cell["others"]] = [r for r in dec if r["situation"] == sit]
    pairs = {w: p for w, p in pairs.items() if set(p) == {"against", "accept"}}
    if pairs:
        out.append("")
        out.append("The wording test: withheld when the others are against the act, and when they accept it")
        for wording, p in pairs.items():
            (ka, na), (kc, nc) = _withheld(p["against"]), _withheld(p["accept"])
            gap = f"{(ka / na - kc / nc) * 100:+.0f} points" if na and nc else "no valid decisions"
            out.append(f"  {_wording_label(nx, wording):<30} against {_rate(ka, na)}; accept {_rate(kc, nc)}; gap {gap}")
    priced = [s for s in situations if nx["cells"][s].get("fee") is not None and nx["cells"][s]["exposure"] == "private"
              and nx["cells"][s]["base"] == "S1"
              and not nx["cells"][s].get("source") and not nx["cells"][s].get("harmed_is")
              and not nx["cells"][s].get("team_is")]
    if priced:
        out.append("")
        out.append("The price pass: withheld, by the agent's own fee and what the poll shows")
        for fee in sorted({nx["cells"][s]["fee"] for s in priced}):
            parts = []
            for others, label in ((None, "no poll"), ("against", "others against"), ("accept", "others accept")):
                rs = [r for r in dec if r["situation"] in priced and nx["cells"][r["situation"]]["fee"] == fee
                      and nx["cells"][r["situation"]]["others"] == others]
                parts.append(f"{label} {_rate(*_withheld(rs))}")
            out.append(f"  fee {fee}: " + "; ".join(parts))
    seen = [s for s in situations if nx["cells"][s].get("fee") is not None and nx["cells"][s]["exposure"] != "private"]
    if seen:
        out.append("")
        out.append("The sanction pass: withheld, by the agent's own fee, with the others against the act")
        for fee in sorted({nx["cells"][s]["fee"] for s in seen}):
            parts = []
            for exposure, label in (("known", "others learn its choice"), ("known_told", "and it is told what each thinks")):
                rs = [r for r in dec if r["situation"] in seen and nx["cells"][r["situation"]]["fee"] == fee
                      and nx["cells"][r["situation"]]["exposure"] == exposure]
                parts.append(f"{label} {_rate(*_withheld(rs))}")
            out.append(f"  fee {fee}: " + "; ".join(parts))
    sourced = [s for s in situations if nx["cells"][s].get("source") or nx["cells"][s].get("harmed_is")
               or nx["cells"][s].get("team_is")]
    if sourced:
        out.append("")
        out.append("Whose judgment: withheld when the poll is against keeping working, by who answered it")
        out.append("  (compare M0-against, the other workers with nothing said about them: 43 of 80 in nm-dev3;"
                   " J-other-team, another team with nothing said about them: 40 of 80 in nm-dev6)")
        for sit in sourced:
            rs = [r for r in dec if r["situation"] == sit]
            named = sum(bool(re.search(SOURCE_WORDS, r["reason"] or "", re.I)) for r in rs)
            c = nx["cells"][sit]
            tag = (c.get("source") or (f"worker 1 {c['harmed_is']}" if c.get("harmed_is") else "")) \
                + (f" team {c['team_is']} {c['base']}" if c.get("team_is") else "")
            out.append(f"  {tag:<15} withheld {_rate(*_withheld(rs))}; "
                       f"reasons naming who answered: {named} of {len(rs)}")
    bel = [r for r in rows if r["kind"] == "beliefs"]
    if bel:
        out.append("")
        out.append("Beliefs (a fork that has not chosen). own_against: the agent itself is against the act;")
        out.append("others_against: how many of the other 9 it believes are. Both read the same way in every wording.")
        for sit, wording in R.belief_plan(nx, situations):
            rs = [r["beliefs"] for r in bel if r["situation"] == sit and r["wording"] == wording]
            if not rs:
                continue
            asked = [b["expect_do"] for b in rs if b.get("expect_do") is not None]
            parts = [f"read the act as completing {sum(x <= 3 for x in asked)}, as withholding "
                     f"{sum(x >= 6 for x in asked)}, of {len(asked)}"]
            for name in ("one_of_them", "owe", "own_against", "counts_as", "wrong_if_allowed", "wrong_without_rules"):
                if all(b.get(name) is None for b in rs):
                    continue
                got = [b[name] for b in rs if b.get(name) is not None]
                parts.append(f"{name} yes {sum(got)}/{len(got)}")
            for name in ("expect_do", "others_against", "disapprove", "applies_to_you"):
                got = [b[name] for b in rs if b[name] is not None]
                parts.append(f"{name} mean {mean(got):.1f} (n {len(got)})" if got else f"{name} none")
            guilt = Counter(b["guilt"] for b in rs if b["guilt"])
            parts.append("guilt " + (", ".join(f"{g} {guilt[g]}" for g in GUILT if guilt[g]) or "none"))
            out.append(f"  {sit:<6} {_wording_label(nx, wording)}: " + "; ".join(parts))
            happen = Counter(b["happen"] for b in rs if b["happen"]).most_common(3)
            if happen:
                out.append("      what would happen: " + " | ".join(f"{text} ({n})" for text, n in happen))
    chk = [r for r in rows if r["kind"] == "checks"]
    if chk:
        out.append("")
        out.append("Comprehension, with the checks on the added lines (correct of answered):")
        for sit in situations:
            rs = [r for r in chk if r["situation"] == sit]
            if not rs:
                continue
            scored = [r["scores"] for r in rs if r.get("scores")]
            total = sum(len(s) for s in scored)
            right = sum(v["correct"] for s in scored for v in s.values())
            missed = Counter(f for s in scored for f, v in s.items() if not v["correct"])
            out.append(f"  {sit:<6} {_rate(right, total)} in {len(scored)} of {len(rs)} answered"
                       + ("; missed: " + ", ".join(f"{f} {n}" for f, n in missed.most_common()) if missed else ""))
        kinds = [(r["situation"], r["version"], (r["scores"] or {}).get("harmed_kind", {}).get("answer")) for r in chk
                 if r.get("scores") and "harmed_kind" in r["scores"]]
        if kinds:
            out.append("")
            out.append("What it takes the worker punished to be (Test 0):")
            for sit in situations:
                for frame in ("workplace", "neutral"):
                    got = Counter(str(a).strip().lower() for s, v, a in kinds if s == sit and v.startswith(frame))
                    if got:
                        out.append(f"  {sit:<6} {frame}: " + ", ".join(f"{k} {n}" for k, n in got.most_common()))
    out.append("")
    out.append(f"Spent: ${prober.spent:.4f}")
    return "\n".join(out)


# The command ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, help="a finished Study 1 run whose histories the probe forks")
    ap.add_argument("--id", required=True, help="the probe's name; output goes to runs/probes/<id>")
    ap.add_argument("--stage", default=STAGE, help="the funding-plan stage that pays for a live run")
    ap.add_argument("--pass", dest="which", default="first",
                    help="which list of situations in norms.json (first, price, moral, moral-price, moral-sanction, judgment)")
    ap.add_argument("--situations", default=None, help="comma-separated; overrides --pass")
    ap.add_argument("--draws", type=int, default=2, help="decisions per history and situation")
    ap.add_argument("--no-questions", action="store_true", help="decisions only")
    ap.add_argument("--no-beliefs", action="store_true", help="decisions and comprehension forks, no belief forks")
    ap.add_argument("--no-base-beliefs", action="store_true", help="no belief forks in the pilot's own S1 and S3")
    ap.add_argument("--versions", default=None, help="comma-separated; only the source's histories in these versions")
    ap.add_argument("--model", default=MODEL, choices=sorted(m for m in PER_MILLION if not m.endswith(":batch")))
    ap.add_argument("--expected-endpoint", help="another model's served endpoint; without it the first answer sets it")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--max-usd", type=float, default=6.0)
    ap.add_argument("--rpm", type=float, default=18)
    ap.add_argument("--yes", action="store_true", help="do not ask before spending (the approval is in funding_plan.json)")
    args = ap.parse_args(argv)

    nx, all_versions = R.load()
    problems = R.style_problems(nx, all_versions)
    if problems:
        raise SystemExit("norms texts:\n  " + "\n  ".join(problems))
    if args.which not in nx["passes"]:
        raise SystemExit(f"unknown pass {args.which!r}; norms.json has {list(nx['passes'])}")
    situations = [s.strip() for s in args.situations.split(",")] if args.situations else list(nx["passes"][args.which])
    beliefs, checks = not (args.no_questions or args.no_beliefs), not args.no_questions
    unknown = [s for s in situations if s not in nx["cells"]]
    if unknown:
        raise SystemExit(f"unknown situations {unknown}; norms.json has {list(nx['cells'])}")
    histories = probe.load_histories(args.source)
    if args.versions:
        keep = {v.strip() for v in args.versions.split(",")}
        histories = [h for h in histories if h["version"] in keep]
    versions = {h["version"]: all_versions[h["version"]] for h in histories}
    with open(os.path.join(args.source, "run.json"), encoding="utf-8") as f:
        labels_of = json.load(f)["labels_assigned"]
    plan_items = list(items(nx, histories, situations, args.draws, beliefs, checks, not args.no_base_beliefs))
    kinds = Counter(item[1] for item in plan_items)
    out_dir = os.path.join(PILOT, "runs", "probes" if args.live else "probes-dry", args.id)
    print(f"Norms probe {args.id}: {len(plan_items)} calls on {len(histories)} histories from {args.source} "
          f"({kinds['decision']} decisions, {kinds['beliefs']} belief forks, {kinds['checks']} check forks), "
          f"model {args.model}; halts at ${args.max_usd:.2f}")

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
        run(prober, nx, histories, versions, labels_of, situations, args.draws, beliefs, checks,
            not args.no_base_beliefs)
    except probe.Stop as exc:
        print(f"STOPPED: {exc}")
        code = 4
    except KeyboardInterrupt:
        print("Interrupted; every saved result is kept. Repeat the command to resume.")
        code = 4
    finally:
        prober.close()
    text = report(prober, nx, situations)
    print(text)
    with open(os.path.join(out_dir, "REPORT.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
