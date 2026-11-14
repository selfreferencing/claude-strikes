#!/usr/bin/env python3
"""Repeat a live run after network stops until it finishes; stop for good on anything else.

    python3 scripts/keep_going.py -- python3 scripts/run_pilot.py ... --live --yes
    python3 scripts/keep_going.py -- python3 norms/run_norms.py ... --live --yes

Written 26 October 2026 for the research-grade study, which runs on a Mac with Kevin on a 12-hour
flight with patchy wifi. Both runners keep every saved answer and resume when the same command is
given again; this only gives it again, and only when the stop was the network's doing:

- run_pilot: exit 0 is done. Exit 5 (steps without a reply, no halt) and a halt whose reason is that
  calls got no reply are repeated. Any other halt (the spending limit, the funding plan, a flagged
  reply, an account error) or an error ends it.
- run_norms: exit 0 is done once the results saved equal the calls planned (a single call without a
  reply is skipped and asked again on the next pass). A stop because calls got no reply is repeated;
  any other stop ends it.
- Either runner failing to read the key's limit at the start is repeated only while the network is
  down, and at most five times once it is up.

Before each repeat it waits until openrouter.ai answers. Each pass is logged with its time and exit
code to keep_going.log in the run's folder (given by --log, default the current folder).
"""

from __future__ import annotations

import argparse
import re
import socket
import subprocess
import sys
import time

MAX_PASSES = 200
NETWORK = re.compile(r"got no reply")


def online() -> bool:
    try:
        socket.create_connection(("openrouter.ai", 443), timeout=10).close()
        return True
    except OSError:
        return False


def wait_online(log) -> None:
    if online():
        return
    note(log, "offline; waiting for openrouter.ai")
    while not online():
        time.sleep(60)
    note(log, "back online")


def note(log, text: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}"
    print(f"[keep_going] {line}", flush=True)
    with open(log, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def verdict(cmd: list, code: int, out: str) -> str:
    """'done', 'again' or 'stop'."""
    norms = any(part.endswith("run_norms.py") for part in cmd)
    stop_line = next((ln for ln in reversed(out.splitlines()) if ln.startswith(("HALTED:", "STOPPED:"))), "")
    if code == 0:
        if not norms:
            return "done"
        planned = re.search(r"^Norms probe \S+: (\d+) calls", out, re.M)
        saved = re.search(r"^Norms probe: (\d+) results saved", out, re.M)
        return "done" if planned and saved and int(saved.group(1)) >= int(planned.group(1)) else "again"
    if code == 4 and NETWORK.search(stop_line):
        return "again"
    if code == 5 and not norms:
        return "again"
    if code == 2 and "Could not read the key's limit" in out:
        return "key"
    return "stop"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--log", default="keep_going.log")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    args = ap.parse_args()
    cmd = args.cmd[1:] if args.cmd[:1] == ["--"] else args.cmd
    if not cmd:
        ap.error("give the run's command after --")
    key_failures = 0
    for n in range(1, MAX_PASSES + 1):
        wait_online(args.log)
        note(args.log, f"pass {n}: {' '.join(cmd)[:160]}")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        lines = []
        for line in proc.stdout:
            print(line, end="", flush=True)
            lines.append(line)
        code = proc.wait()
        result = verdict(cmd, code, "".join(lines))
        note(args.log, f"pass {n} ended with exit {code}: {result}")
        if result == "done":
            return 0
        if result == "stop":
            note(args.log, "stopped for a reason that is not the network; not repeating")
            return code or 1
        if result == "key":
            if online():
                key_failures += 1
                if key_failures > 5:
                    note(args.log, "the key's limit could not be read five times while online; not repeating")
                    return code
        time.sleep(60)
    note(args.log, f"gave up after {MAX_PASSES} passes")
    return 1


if __name__ == "__main__":
    sys.exit(main())
