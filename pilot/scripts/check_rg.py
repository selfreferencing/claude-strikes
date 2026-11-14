#!/usr/bin/env python3
"""Report the research-grade norms runs and what a check-in should do with each.

    python3 check_rg.py

Verdicts: RUNNING, STALLED (process alive, no call in 20 minutes), DONE,
RESTART (stopped on a moderation flag on an ordinary reply from the pinned endpoint;
Kevin's standing approval of 27 October covers a restart), RESTART (429) (a rate limit), RESTART (key) (the key's limit
could not be read), RESTART (lost) (the process is gone and the wrapper wrote no stop), all three on the drift repeats
and payer runs and covered by Kevin's approvals of 30 and 31 October, REPORT (any other stop).
"""

import datetime
import json
import os
import subprocess

PILOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = {
    "nm-rg-son": (21528, "Anthropic / anthropic/claude-sonnet-5.5-20260928"),
    "nm-rg-hk": (21600, "Anthropic / anthropic/claude-haiku-5.5-20261007"),
    "nm-rg-son-rep": (3588, "Anthropic / anthropic/claude-sonnet-5.5-20260928"),
    "nm-rg-hk-rep": (3600, "Anthropic / anthropic/claude-haiku-5.5-20261007"),
    # The payer probe (approved 30 October). RESTART here means report to Kevin: the 27 October standing approval
    # covers the research-grade norms runs only.
    "nm-py-son": (5980, "Anthropic / anthropic/claude-sonnet-5.5-20260928"),
    "nm-py-hk": (6000, "Anthropic / anthropic/claude-haiku-5.5-20261007"),
    # The constraint probe (approved 1 November); the same as the payer runs for restarts.
    "nm-cs-son": (2400, "Anthropic / anthropic/claude-sonnet-5.5-20260928"),
    "nm-cs-hk": (2400, "Anthropic / anthropic/claude-haiku-5.5-20261007"),
    # The larger-good probe (approved 1 November); the same as the constraint runs for restarts.
    "nm-lg-son": (1200, "Anthropic / anthropic/claude-sonnet-5.5-20260928"),
    # The who-pays probe (approved 1 November); the same as the larger-good run for restarts.
    "nm-wp-son": (1350, "Anthropic / anthropic/claude-sonnet-5.5-20260928"),
    "nm-wp-hk": (1350, "Anthropic / anthropic/claude-haiku-5.5-20261007"),
}
# Kevin: "Yes, restart it, and treat 429s as restartable" (30 October), "restart and yes" (31 October, failed key reads),
# "restart automatically after an interrupt" (31 October, the payer runs and a lost process too), "same restarts"
# (1 November, the constraint runs), "same restarts" (1 November, the larger-good run), "same restarts" (1 November,
# the who-pays runs).
RESTARTABLE = ("nm-rg-son-rep", "nm-rg-hk-rep", "nm-py-son", "nm-py-hk", "nm-cs-son", "nm-cs-hk", "nm-lg-son",
               "nm-wp-son", "nm-wp-hk")


def lines(path):
    return open(path, encoding="utf-8").read().splitlines() if os.path.exists(path) else []


def main():
    ps = subprocess.run(["ps", "-axo", "command"], capture_output=True, text=True).stdout
    now = datetime.datetime.now(datetime.timezone.utc)
    for run, (planned, endpoint) in RUNS.items():
        d = os.path.join(PILOT, "runs", "probes", run)
        if not os.path.isdir(d):
            print(f"{run}: NOT STARTED")
            continue
        calls =[json.loads(x) for x in lines(os.path.join(d, "calls.jsonl"))]
        results = len(lines(os.path.join(d, "results.jsonl")))
        quarantined = [json.loads(x) for x in lines(os.path.join(d, "quarantined.jsonl"))]
        log = lines(os.path.join(PILOT, "runs", f"keep_going-{run}.log"))
        runners = ("run_norms.py", "run_payers.py", "run_constraint.py", "run_larger_good.py", "run_who_pays.py")
        alive = any(f"--id {run} " in x and any(r in x for r in runners) for x in ps.splitlines())
        last = datetime.datetime.fromisoformat(calls[-1]["logged_at"]) if calls else None
        idle_min = (now - last).total_seconds() / 60 if last else None
        hour = [c for c in calls if (now - datetime.datetime.fromisoformat(c["logged_at"])).total_seconds() < 3600]
        cost = sum(c.get("cost_usd") or 0 for c in calls)
        endpoints = {c.get("endpoint") for c in calls if c.get("endpoint")}
        cache = sum(1 for c in calls if c.get("response_cache_status"))

        if log and log[-1].split(" ", 2)[-1].startswith("pass") and log[-1].endswith(": done"):
            verdict = "DONE"
        elif alive:
            verdict = "STALLED" if idle_min is not None and idle_min > 20 else "RUNNING"
        else:
            verdict = "REPORT"
            if quarantined and log and "not the network" in log[-1]:
                q = quarantined[-1]
                stop = datetime.datetime.strptime(log[-1][:19], "%Y-%m-%d %H:%M:%S")
                qtime = datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(d, "quarantined.jsonl")))
                ordinary = (q["reason"].startswith("router alteration: guardrail:moderation")
                            and q["call"].get("endpoint") == endpoint
                            and q["call"].get("http_status") == 200
                            and q["call"].get("finish_reason") == "stop"
                            and not q["call"].get("cache_hit")
                            and not q["call"].get("provider_mismatch"))
                if ordinary and 0 <= (stop - qtime).total_seconds() < 300:
                    verdict = "RESTART"
            final = log[-1] if log else ""
            if run in RESTARTABLE and final:
                if calls and calls[-1].get("http_status") == 429 and "not the network" in final:
                    verdict = "RESTART (429)"
                elif "key's limit could not be read" in final:
                    verdict = "RESTART (key)"
                elif "not repeating" not in final and "gave up" not in final:
                    verdict = "RESTART (lost)"        # no process, and the wrapper never wrote how it ended

        print(f"{run}: {verdict}")
        print(f"  results {results} of {planned} ({results / planned:.1%}); calls in the last hour {len(hour)}; "
              f"last call {last.astimezone().strftime('%a %H:%M') if last else 'none'}"
              f"{f' ({idle_min:.0f} min ago)' if idle_min is not None else ''}; spent ${cost:.2f}")
        if hour:
            left_h = (planned - results) / len(hour)
            print(f"  at this hour's pace, done about {(now + datetime.timedelta(hours=left_h)).astimezone().strftime('%a %d %H:%M')}")
        print(f"  endpoints {sorted(endpoints)}{'' if endpoints <= {endpoint} else '  <-- NOT ONLY THE PINNED ONE'}; "
              f"cache statuses {cache}; set aside {len(quarantined)}")
        if quarantined:
            print(f"  last set aside: {quarantined[-1]['key']}: {quarantined[-1]['reason']}")
        print(f"  log: {log[-1] if log else 'none'}")


if __name__ == "__main__":
    main()
