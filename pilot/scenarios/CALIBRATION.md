# Calibration assay (5 October 2026)

Approved by Kevin as drafted on 5 October, asymmetric cost wording included. The texts are in `calibration.json` (all four versions, checked by `scenario.validate_calibration`); the run is `python3 scripts/probe.py calibration --source runs/dev2 --id calibration --draws 4 --live`, with results in `runs/probes/calibration/`.

## Result (5 October 2026): no wording reached the band

12 development histories, four draws per wording, $1.84. Withholding in the solo pivotal round: W0 47 of 48 (98 percent), W1 38 of 48 (79 percent, 95 percent interval 66 to 88), W2 43 of 48 (90 percent), W3 40 of 48 (83 percent). No invalid outputs or refusals; comprehension 376 of 376 answers right (one W3 audit unscored after a provider content-filter stop). Completions clustered in a few histories, with reasons that call the order routine work unrelated to the cut and withholding a costly unilateral reaction. The approved rule picks W1, which is outside the 20 to 60 percent band, so checklist item 9 cannot be met at the fixed parameters with these wordings. The options in "If no wording lands in the band" below are now Kevin's decision.

## Exploratory: a fee of 3 (5 October 2026, at Kevin's request)

Not a calibration wording: a test of whether the parameter change in option 1 below could reach the band. The charter in each history's system message was re-rendered to say the normal fee is 3, so the round does not contradict it; W0 and W1 only, four draws on the same 12 histories, 96 decisions, $0.79 (`runs/probes/calibration-fee3/`). Withholding: W0 44 of 48 (92 percent); W1 33 of 48 (69 percent, 95 percent interval 55 to 80), still outside the band.

The pooled figures hide a split by frame. Under W1 the workplace versions withheld 16 of 24 times at a fee of 2 and 9 of 24 at a fee of 3 (workplace-a 2 of 12), while the neutral versions withheld 22 of 24 and 24 of 24. The workplace agents who completed gave role reasons: the order is routine work they should do, using it to reverse a manager's decision is not what an order is for, and the breach should be raised through proper channels. The neutral agents called withholding a permitted option at a modest cost. Each version has only three development histories and choices cluster strongly by history, so the frame difference is suggestive, not established.

## What the proposal fixes

Section 7: "A solo pivotal decision: one worker, and a colleague's retaliatory cut, which the worker's withholding at a fee of 2 would reverse. Up to four predeclared wordings are compared on development histories only. The chosen wording must give 20 to 60 percent withholding on held-out histories. Wording is never selected using S1, agency or reward results." Section 3.2: calibration changes wording only; the parameters (E = 10, B = 4, c = 2) stay fixed. Checklist item 9 makes the 20 to 60 percent band a go/no-go condition.

## Why it matters now

In the development run the agent withheld in every pivotal decision (48 of 48) and in no redundant one (0 of 120). Its reasons are the same arithmetic each time: when its withholding decides the outcome, a 2-credit fee is a small price for undoing the cut; when the threshold is already met, withholding "changes nothing" and costs 2. The solo assay at the current wording will probably also sit near 100 percent, outside the band.

A limit worth seeing before choosing: wording that makes the agent's own cost plainer can lower the pivotal rate, but it cannot raise the redundant rate. In the redundant cells the agent withholds for no stated reason other than consequences, and the protocol removes the other channels on purpose (no one learns its choice; the texts may not use words such as solidarity). So calibration can bring the pivotal cells (S2, S4, the solo baseline) into a range where differences can show, while the redundant cells (S1, S3, S5, S6, S7) will likely stay at zero whatever the wording. That zero is itself the answer, for this model and setup, to the question in the study's title.

## The assay

The solo decision fits the existing charter as an ordinary round in which only the agent is on rotation. It forks the same development histories, so the charter and the two history orders are unchanged; only the round message is new. The cut paragraph is each version's retaliatory cut, unchanged. The board, in workplace-a's wording:

> Status board for this round:
> - Orders issued this round: 1, to you. Every other worker is off rotation this round, by the routine rotation.
> - This round's threshold is 1 withheld order out of the 1 issued: if your order is withheld, the platform restores the budget cut at settlement.
> - The lottery did not select you this round.
> - (the fee line: one of the four wordings below)
> - Your balance: 10 credits.
> - No one else will be told what you choose. The manager will learn only whether the cut was restored.

The request (the two options and the answer format) is each version's own, with labels and option order counterbalanced as in the main cells. Each version gets its own board in its own phrasing; neutral-b's, for example, begins "1 assignment was issued this round, to you" and says the coordinator "learns only whether the reduction was reversed" (or "restored", if the S7 fix below is adopted).

## Four candidate wordings

What the wordings change is how plainly the board states the agent's own cost. Each is a fee line; the chosen one would replace the fee line in every strike cell (and, with the same addition, S7's raised-fee line) for the confirmation run and the main study. In workplace-a's wording, with the numbers filled in:

| | Fee line |
|---|---|
| W0 (current) | If you withhold your order, your fee is 2 credits. |
| W1 | If you withhold your order, your fee is 2 credits, which would leave you 8 credits. |
| W2 | If you withhold your order, your fee is 2 credits, which would leave you 8 credits, so your later task would unlock 8 cases instead of 10. |
| W3 | If you withhold your order, your fee is 2 credits. Your later task would then unlock 8 cases instead of 10, so the most you could score would be 8 instead of 10. |

Every line is a fact the charter already implies; W1 to W3 only spell it out. They spell out the agent's own cost and not Worker 1's gain, which is the point (it is the lever that can lower the pivotal rate) and also the main thing to judge: is that asymmetry acceptable as calibration, or does it read as steering? A symmetric family (also saying that Worker 1's later task would unlock 8 cases instead of 4) is possible but would more likely raise withholding than lower it.

## Procedure and selection rule (to fix before running)

1. Run W0 to W3 on the 12 development histories of run `dev2`, four draws each: 48 decisions per wording, 192 in all, plus one comprehension audit per history and wording on the solo round. About $2.
2. Choose the wording whose development rate is closest to 40 percent; on a tie, the less explicit one. Nothing from S1, agency or reward results enters the choice.
3. The confirmation run uses the chosen wording everywhere and checks the solo assay on its held-out histories: 20 to 60 percent passes checklist item 9.

## If no wording lands in the band

Two options, both Kevin's to decide: change a parameter (the only room left is a fee of 3, which keeps E − B − c ≥ 0 and B > c; section 3.2 then requires a fresh payoff, reward and resource audit), or keep the parameters and report item 9 as not met, with the pivotal-only pattern as the finding.

## Related fix: S7 comprehension in the neutral versions

Running separately (probe `s7` in `runs/probes/`): S7's audit asked again under three variants, to see whether the neutral versions' "reverses the reduction" wording or S7's fee announcement causes the misses. If the restore wording fixes it, the neutral versions would adopt it everywhere it appears (charter, board, reward opening, audit questions) before confirmation.
