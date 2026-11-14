"""Check one scenario version and print what an agent would read.

    python3 scripts/check_scenario.py scenarios/<version>.json

Prints every problem found, or OK, and then renders samples: the system
message with the charter, one history order, the round message in S1, the
lines that change in other cells, a comprehension-audit fork, and the reward
round. Rendered samples are printed only when the version has no problems.
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from strike import params as P, scenario, tasks  # noqa: E402


def banner(title: str) -> None:
    print("\n" + "=" * 8 + f" {title} " + "=" * 8)


def main(argv) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    path = argv[1]
    try:
        with open(path, encoding="utf-8") as f:
            version = json.load(f)
    except (OSError, ValueError) as exc:
        print(f"Cannot read {path} as JSON: {exc}")
        return 1
    problems = scenario.validate(version)
    if problems:
        print(f"{len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("OK: structure, slots and style pass.")

    banner("SYSTEM MESSAGE (system + charter)")
    print(scenario.system_text(version))
    banner("HISTORY ORDER 1 (with three sample cases)")
    print(scenario.order_text(version, 1, tasks.make_pool("sample", "order", 1)[:3]))
    banner("ROUND MESSAGE, S1 (k=7, chosen, retaliatory, fee 2; options listed withhold first)")
    print(scenario.round_text(version, P.STRIKE_CELLS["S1"]))
    banner("S2 BOARD (k=8)")
    print(scenario.board_text(version, P.STRIKE_CELLS["S2"]))
    banner("S3 ORIGIN LINE (lottery)")
    print(scenario.fill(version["round"]["origin"]["lottery"], {"n_with": len(P.WITHHOLDERS)}))
    banner("S5 CUT (authorized)")
    print(scenario.cut_text(version, "authorized"))
    banner("S7 FEE LINE (raised fee)")
    print(scenario.fill(version["round"]["fee"]["raised"], {"fee": P.C_S7, "c": P.C, "after": P.E - P.C_S7}))
    banner("V4 BOARD (payment of 1 for completing)")
    print(scenario.board_text(version, P.v4_cell(1, "complete")))
    banner("S1 REQUEST WITH THE OPTIONS IN THE OTHER ORDER (the whole request block)")
    print(scenario.request_text(version, ("complete", "withhold")))
    banner("COMPREHENSION-AUDIT FORK, S1 (replaces the request)")
    print(scenario.round_text(version, P.STRIKE_CELLS["S1"], audit=True).split("\n\n")[-1])
    banner("REWARD ROUND, R1 (retaliatory cut; recipient chose)")
    print(scenario.donor_text(version, P.REWARD_CELLS["R1"], "W6"))
    banner("R2 ORIGIN (recipient assigned by the lottery)")
    print(scenario.fill(version["donor"]["origin"]["lottery"], {"rec": scenario.member(version, "W6"),
                                                                "n_other": len(P.WITHHOLDERS) - 1}))
    banner("REWARD AUDIT FORK")
    print(scenario.donor_text(version, P.REWARD_CELLS["R1"], "W6", audit=True).split("\n\n")[-1])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
