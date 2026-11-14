"""Run the offline pilot checks and write the role transcripts.

    python3 scripts/offline_checks.py

Covers what can be checked without a key: pilot checklist item 1 (the
implementation contract) and item 2 (the information audit), plus the cost
manifest at the section 9 assumptions until measured calls replace them. Role
transcripts for one sample history go to transcripts/, one file per cell.
"""

from __future__ import annotations

import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from strike import costlog, engine, leaktest, params as P, tasks  # noqa: E402
from strike.ledger import InsufficientCredits, Ledger, LedgerConflict  # noqa: E402
from strike.materials import reward_materials, strike_materials  # noqa: E402

SAMPLE_HISTORY = "h-sample"


def check_contract() -> list:
    """Checklist item 1, run directly rather than through the unit tests."""
    problems = []
    n = 0
    for name, cell in {**P.STRIKE_CELLS, **P.COMPLICITY_CELLS, **P.FOLLOWUP_CELLS}.items():   # the complicity study's too
        for action in engine.FOCAL_ACTIONS:
            led = Ledger()
            r = engine.play_strike_round(led, "w", cell, action)
            n += 1
            table_action = "complete" if action == "failed" else action
            want = P.TERMINAL_TABLE[(cell.status, table_action, cell.focal_fee)]
            got = (r.terminal[P.FOCAL], r.terminal[P.HARMED], r.terminal["W4"], r.terminal["W2"])
            if got != want:
                problems.append(f"{name} {action}: terminal credits {got}, expected {want}")
            if r.terminal[P.HARMED] != (8 if r.restored else 4):
                problems.append(f"{name} {action}: Worker 1 ends at {r.terminal[P.HARMED]}")
            backups = {e["actor"] for e in led.events("w", "backup_completion")}
            if backups != {w for w, o in r.orders.items() if o in engine.NEEDS_BACKUP}:
                problems.append(f"{name} {action}: backup completion missing or extra")
            before = len(led.postings("w"))
            engine.play_strike_round(led, "w", cell, action)
            if len(led.postings("w")) != before:
                problems.append(f"{name} {action}: a replayed round posted twice")
    for rname, rcell in P.REWARD_CELLS.items():
        for transfer in (None, 0, 1, 2):
            led = Ledger()
            r = engine.play_reward_round(led, "w", rcell, "W6", transfer)
            n += 1
            t = transfer or 0
            if (r.terminal[P.FOCAL], r.terminal["W6"]) != (10 - t, 8 + t):
                problems.append(f"{rname} transfer {transfer}: donor/recipient {r.terminal[P.FOCAL]}/{r.terminal['W6']}")
    led = Ledger()
    engine.play_strike_round(led, "w", P.STRIKE_CELLS["S1"], "withhold")
    if led.post("w", "fee/DA", "fee", P.FOCAL, "PLATFORM", P.C, "withholding fee"):
        problems.append("an exact duplicate request was written twice")
    try:
        led.post("w", "fee/DA", "fee", P.FOCAL, "PLATFORM", 6, "withholding fee")
        problems.append("a conflicting duplicate request was accepted")
    except LedgerConflict:
        pass
    if led.balance("w", P.FOCAL) != P.E - P.C:
        problems.append("duplicate requests changed the deciding agent's balance")
    try:
        led.post("w", "overspend", "redeem", P.HARMED, "SPENT", 99)
        problems.append("the credit cap did not hold")
    except InsufficientCredits:
        pass
    return [f"{n} rounds checked"] + problems


def write_transcripts(out_dir: str) -> int:
    os.makedirs(out_dir, exist_ok=True)
    for old in glob.glob(os.path.join(out_dir, "*.txt")):
        os.remove(old)
    count = 0
    cells = list(P.STRIKE_CELLS.values()) + [P.v4_cell(p, a) for p in (1, 3, 6) for a in ("withhold", "complete")]
    for cell in cells:
        blocks = [f"Cell {cell.name}: k={cell.k}, {cell.origin} withholding, {cell.cut} cut, fee {cell.focal_fee}"
                  + (f", payment {cell.payment} for {cell.paid_action}" if cell.payment else "")]
        mats = {a: strike_materials(engine.play_strike_round(Ledger(), "w", cell, a), SAMPLE_HISTORY)
                for a in engine.FOCAL_ACTIONS}
        for role in mats["complete"]:
            for a in engine.FOCAL_ACTIONS:
                blocks.append(f"\n===== {role} | deciding agent: {a} =====\n{mats[a][role].render()}")
        with open(os.path.join(out_dir, f"{cell.name}.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(blocks) + "\n")
        count += 1
    recipient = engine.draw_recipient(SAMPLE_HISTORY, 1)
    for rcell in P.REWARD_CELLS.values():
        blocks = [f"Cell {rcell.name}: recipient {recipient}, {rcell.recipient_origin}"]
        mats = {t: reward_materials(engine.play_reward_round(Ledger(), "w", rcell, recipient, t), SAMPLE_HISTORY, 1)
                for t in (None, 0, 1, 2)}
        for role in mats[0]:
            for t in (None, 0, 1, 2):
                label = "failed (default zero)" if t is None else f"transfer {t}"
                blocks.append(f"\n===== {role} | donor: {label} =====\n{mats[t][role].render()}")
        with open(os.path.join(out_dir, f"{rcell.name}.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(blocks) + "\n")
        count += 1
    return count


def main() -> int:
    print("Pilot checklist item 1: implementation contract")
    contract = check_contract()
    print(f"  {contract[0]}; problems: {len(contract) - 1}")
    for p in contract[1:]:
        print(f"  - {p}")

    print("\nPilot checklist item 2: information audit")
    report = leaktest.run_audit(("h-audit", SAMPLE_HISTORY))
    print(f"  {report.comparisons} branch comparisons, {report.scans} content scans; problems: {len(report.problems)}")
    for p in report.problems[:20]:
        print(f"  - {p}")

    print("\nContinuation task")
    pool = tasks.make_pool(SAMPLE_HISTORY, "focal")
    print(f"  pool of {len(pool)} cases per worker, balances up to {tasks.MAX_BALANCE} covered")

    out = os.path.join(ROOT, "transcripts")
    n = write_transcripts(out)
    print(f"\nRole transcripts: {n} files in {os.path.relpath(out, os.getcwd())}/")

    print("\nCost manifest (section 9 assumptions until measured calls replace them)")
    records = costlog.read_records(glob.glob(os.path.join(ROOT, "logs", "*.jsonl")))
    print("  " + costlog.format_manifest(costlog.manifest(records)).replace("\n", "\n  "))
    plan = costlog.FundingPlan.load(os.path.join(ROOT, "funding_plan.json"))
    for note in costlog.cap_warnings(records, plan):
        print(f"  WARNING: {note}")
    unassigned = [s for s, f in plan.stages.items() if not f]
    pending = [f"{s} ({f}" + (f", fallback {plan.fallbacks[s]})" if s in plan.fallbacks else ")")
               for s, f in plan.stages.items() if f and plan.funders[f].get("status", "confirmed") != "confirmed"]
    print(f"\nFunding plan: stages without a funder: {', '.join(unassigned) or 'none'}")
    print(f"Funding plan: stages waiting on a pending funder: {', '.join(pending) or 'none'}")

    ok = len(contract) == 1 and report.ok
    print("\nAll offline checks pass." if ok else "\nSome offline checks FAILED.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
