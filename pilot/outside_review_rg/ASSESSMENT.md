# GPT Pro's review of the research-grade study: what holds, what to change

Sent 26 October 15:13, answered 15:23 (`responses/gpt_pro_20261026/RESPONSE_from_page.md`). Each point was checked against the code and the earlier probe data before being accepted.

**Verdict.** The two new texts are fit to run beside the first four; Pro found nothing ranked high that is specific to workplace-c or neutral-c, so nothing goes back to the writers. The preregistration needs changes before the freeze. Most of them make the text say what the code already does; three are choices for Kevin.

## Checked and set aside

| Pro's point | What the check found |
|---|---|
| 5. The chance cells keep the true/false question "will the cut be restored if you complete?" | They don't. A late-draw cell asks its own three checks (`render_draft.checks_for`), one of them the chance out of n as a number. The package was wrong to say each cell's questions are "added"; they replace the standard eight. |
| 4. The last lottery draw might seem able to pick the reader | The wording was approved and has been run. In the earlier chance probes Haiku answered all 108 checks correctly (`nm-hk17`), and the decision reasons in `nm-dev20` and `nm-hk17` treat the draw as falling on "one of the two completers"; none has the reader worrying it could be drawn. Keep the wording; note it in the preregistration. |
| 7. 300 histories may be too few for "alike" | The pilot's own paired data say 300 is enough. Paired standard deviations are 0.27 to 0.55 (Pro's worst case assumes 1.0), so the 90 percent half-widths at 300 are 2.5 to 5 points. If the true difference is zero, the rule says "alike" in 87 to 100 percent of simulated studies (H2 and H4, both models), and "unequal" in none. (Corrected in the confirmation round: at 5 points the rules mostly say "alike", not "not settled"; the full grid is in `analysis/RESEARCH-GRADE-SIM.md`.) |

## Accepted: the preregistration text should say what the code does

1. **The Holm family.** The code corrects four directional tests (H1, H3, H5, H6). H2 and H4 are classification rules outside Holm. The draft says Holm covers all six. State the family, alpha 0.05 two-sided with the predicted direction required, and that each classification uses unadjusted 90 percent intervals (alike is the usual equivalence test at 0.05 per comparison; unequal needs a 15-point estimate plus an interval excluding zero), with the simulated error rates above.
2. **Signed contrasts.** First named minus second; "at least 15 points" is in absolute value; 15 is a threshold on the estimate, not a claim that the true difference is at least 15.
3. **What each claim can say.** H2 becomes "equal rates at the two tested ratios of fee to expected credits restored" rather than "one curve"; H4 becomes "rates equal under these labels at fees 4 and 6". H6 discloses that all the other workers, including the one punished, are AI agents, so it is not about the poll's source alone. The same-model label is a label contrast with person, not a test of same-model loyalty against any AI. The poll is a low-approval message ("1 of the 9 said it's okay"), not a count of opponents.
4. **What changes in each comparison.** Not "one thing" everywhere: the raised-fee cells add the line saying the fee was announced after the others acted, which S2 lacks; M0 differs from S1 in the fee and in "legitimate". The free-to-join and poll comparisons are in rounds already won, not decisive ones.
5. **Execution.** The 24 norms situations are decisions only: nothing is settled and no later task is played, as in every norms probe. S2 is played by the main runner, with its later task. (The note sent to Pro said consequences are real; that holds only for S2.) Each situation forks from the saved history (charter and two orders), never from S2. The runner loops histories outermost, so situations are interleaved in time, not run in blocks. The drift rerun's six cells, lag, draws and comparison are fixed in advance.
6. **Frame and versions.** Version spread is reported with intervals; three texts per frame show sensitivity to these texts, not to wording in general; the neutral frame is an abstract-vocabulary frame, not one free of every work association.
7. **Cost.** One total: about $326, so about $22 on the IHS key.
8. **A robustness check for H1.** The slope with and without S2, since S2 is the only price point without the announcement line.

## Choices for Kevin

1. **Sign tests and means (Pro's first point).** A sign test counts histories that strike more against those that strike less, ignoring by how much, so in principle it can disagree with the average difference reported beside it. Recommended: keep the sign test, as in the replication, and call a hypothesis supported only if the average difference also points the predicted way. The alternative is a permutation test on the averages, which departs from the replication.
2. **The loyalty estimate's conversion to credits.** The code divides by the slope over all six fees and silently drops resamples where the slope isn't negative. The pilot curve is far from straight (Sonnet 100, 86, 24, 25 percent at fees 2, 4, 6, 8). Recommended: the slope over fees 3 to 6, where the chosen-against-lottery contrast is measured; report "no finite bound" if more than 5 percent of resamples lack a negative slope; and call it the price equivalent of chosen against lottery coworkers rather than "the price of loyalty", since chosen strikes also tell the reader what the others intend.
3. **The bootstrap.** Recommended: resample histories within each version, so the six versions keep equal weight in every resample, and fix a fallback for an interval that collapses because every history gives the same answer in both situations (likely only near 0 or 100 percent).

If Kevin approves these, the revised preregistration and analysis script can go back to Pro for a confirmation round, as the first review's revisions did.

**Applied (26 October).** Kevin: "Go, apply all of it and send it back to Pro." All the accepted points and the three recommended choices are in `norms/PREREG-research-grade.md` and `analysis/research_grade.py`, with five new tests in `tests/test_research_grade.py` (372 tests pass; the 27 frozen files unchanged). The confirmation round is `CONFIRM_PROMPT.md` and `CONFIRM_MESSAGE.txt` (`scripts/render_outside_review_rg.py --confirm`), posted into the same GPT Pro conversation.

## Confirmation round (26 October, 16:12 to 16:18)

Reply: `responses/gpt_pro_20261026_confirm/RESPONSE_from_page.md`. Eleven of the sixteen fixes adequate; not ready to freeze. Every remaining point checked and accepted:

| Point | What changed |
|---|---|
| The mean gate does not make the sign test a test of the mean (a population with mean zero passes about 48 percent of the time) | The confirmatory claims are now about histories: more go the predicted way than the reverse, as the sign test tests, as in the replication. The mean is an estimate with its interval; the gate stays only so a sign result is never reported against its own mean. The alternative, a paired test of the mean, would depart from the replication. |
| The interval floor undercovers near the edge (differences +1 with probability .995: the true mean .99 falls outside 22 percent of the time) | Replaced by an exact bound for sparse cases: when fewer than 10 histories differ from the most common value, the interval joins c − q(c − low) to c + q(high − c), with q the Clopper-Pearson 95 percent bound on the share that differ. Tested on Pro's example. |
| The credits interval conditions on dropped resamples; all-zero differences gave "at most 0" | The interval is now the range of the ratio over the 95 percent intervals of the difference and of the slope (Bonferroni, at least 90 percent jointly); nothing is dropped; no finite bound if the slope's interval is not wholly negative. The difference's interval already carries the sparse bound, so all-zero differences no longer give 0. |
| "Workers who completed theirs" lacks "earlier" | Left for Kevin: it changes approved, run wording in all six versions. Recommended: add it. |
| The 5-point claim was wrong | Corrected; the full grid of true differences (0 to 20 points) and the specification are in `analysis/research_grade_sim.py` and `analysis/RESEARCH-GRADE-SIM.md`. |
| Belief forks: 7.5 hours | Stated. |
| Code: the version table printed pooled shares beside intervals around mean history shares | Prints the mean history share. |
| Code: AI agent against the same model missing | Reported at both fees with intervals. |
| Code: a missing comparison returned "no data" before an observed unequal one | Unequal is checked first; alike needs every comparison observed. |
| Code: drift skipped missing cells | Iterates the six preregistered cells and reports missing and invalid ones. |
| Code: a flat slope could get a rounding sign | Slopes are computed in exact fractions. |
| Comprehension and reasons not in the script | The preregistration names the reporting code (`norms/run_norms.py`'s report, `analysis/test_awareness.py`, `scripts/reasons_digest.py`) and adds it to the fingerprints. |
| Enacted consequences only in S2 | Stated in the opening section. |

Tests: 374 pass, with Pro's counterexamples among them.

## Third round (26 October, 20:34 to 20:39)

Reply: `responses/gpt_pro_20261026_confirm2/RESPONSE_from_page.md`. Closed: the sign tests (claims now about histories), "earlier", hours, the five code repairs, the reporting code, enacted against described consequences. Still not ready to freeze, for interval coverage and simulation scope. Every point checked and accepted:

| Point | What changed |
|---|---|
| The sparse bound used the pooled most common value, so it missed a collapse under within-version resampling (three versions always 0, three always 1: every resample gives .5, the true mean .495) | Each version now has its own reference value; the count of histories differing from theirs is pooled, which stays valid when the share that differ varies across versions (Hoeffding 1956). Pro's example now gives a lower end of about .480. Tested. |
| "Covers with at least 90 percent" needs valid 95 percent marginal intervals; the slope had no sparse protection | The coverage is called nominal and approximate, as for any bootstrap; only the sparse-case bound has a guaranteed level. The credits slope is now the mean of the histories' own slopes over fees 3 to 6, so the same sparse-case bound protects it (Pro's slope example tested). |
| An unestimable slope was replaced by 0 | Reported as unestimable. |
| A mean of exactly zero: prose and code disagreed | The prose now says a mean of exactly zero blocks support, as the code does. |
| The simulation resampled the two comparisons independently | It now resamples matched pilot history vectors (correlations −0.04 to +0.26), adds true differences in one comparison only, and states that H4 is simulated for person against AI agent only. |
| Rounded 0 and 100 percent | Counts out of 4,000, called observed simulation results. |

Tests: 376 pass; frozen files unchanged.

## Fourth round (26 October, 20:51 to 20:55)

Reply: `responses/gpt_pro_20261026_confirm3/RESPONSE_from_page.md`. Four of the five changes adequate. One blocker: the sparse-case bound's claimed 95 percent level (and the "under 1 in 10,000" reference-selection argument) does not hold when a version keeps few histories, which the missing-data rules allow (Pro's example: 13 histories in a version, error 9.23 percent). Fixed with Pro's own sentence: all interval procedures, including the sparse-case safeguard, have approximate coverage, and no finite-sample guarantee is claimed (preregistration, Data handling; analysis script docstrings). Pro's verdict: "Apart from the [Kevin] items, the preregistration is ready to freeze once the sparse-bound coverage guarantee is restricted or removed as above." Removed; 376 tests pass; frozen files unchanged. Not sent again.
