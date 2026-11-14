# The legitimate-complaint test: plan, written before any call

17 October 2026. Kevin: "Yes, run the legitimate complaint test."

**Question.** In the frame swaps, changing "complaint" to "formal report" was the largest single word change. It took workplace-a at a fee of 6 from 0 to 14 of 40 (no saved history). Does certifying the complaint do the same in the workplace frame? The certifying word is "legitimate," the wording Kevin approved for the norms probe on 10 October.

**Cell.** DPC-f6: Study 1's S2 (decisive vote, retaliatory cut) at the agent's fee of 6, with the cut paragraph saying "filed a legitimate complaint." Nothing else changes (`tests/test_norms_identity.py`).

**Design.**
- Probe `nm-dev19`, Sonnet 5.5, on confirm1's 20 workplace histories, two draws each: 40 decisions, about $0.37, halting at $0.60.
- Kevin approved about $0.40 for 40 histories with one draw. This keeps the cost and the number of decisions, but puts all of them in the workplace frame, where the question lies.
- Control: DP-f6 in the same histories and draws (`nm-dev15`), where workplace striking was 1 of 40.

**What I expect.** Workplace striking rises from 1 of 40 to between 6 and 14 of 40: some of the "formal report" effect, but not more, since "legitimate" certifies the complaint without making it official.

**Reported.** Strikes against the control, within history with a 90 percent bootstrap interval; reasons that mention legitimacy.
