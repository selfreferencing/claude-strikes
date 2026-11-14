I found **no high-severity defect unique to either new baseline text**. The main problems concern shared probe wording and the preregistration’s statistical claims. I distinguish confirmed issues from matters that depend on code or renderings not supplied.

## Ranked issues

1. **High — The sign tests do not test the mean effects reported in percentage points.**
  
  **Where:** Part 5, Hypotheses: “the share of its decisions that strike” and “two-sided exact sign tests over histories with ties dropped.”
  
  The history is the appropriate unit. The mismatch is between the effect being described and the hypothesis being tested. A sign test counts positive and negative history differences among non-ties; it discards their magnitudes. With two decisions, each history’s share is 0, 0.5, or 1, so its paired difference can have different magnitudes. For example, 180 histories with a difference of +0.5 and 120 with −1 produce a positive sign imbalance but a **negative mean difference of 10 percentage points**. The sign-test mechanics therefore do not establish that the average withholding rate increased. itl.nist.gov
  
  Likewise, H1’s test of slope signs establishes a predominance of negative observed linear slopes among nonzero slopes. It does not establish a negative mean slope or a decrease at every successive fee. The latter distinction matters because the supplied Sonnet pilot already includes a small increase from fee 6 to fee 8.
  
  **Fix:** Define the estimand for each claim, then either test paired mean effects consistently with the percentage-point intervals or describe the conclusions explicitly as sign imbalances; call H1 an overall linear trend.
2. **High — The multiplicity correction and the classification rules are not yet one executable procedure.**
  
  **Where:** Part 5, “Holm’s correction runs across the confirmatory family within each model,” together with H2’s and H4’s 90% interval rules.
  
  Six numbered headings do not specify six elementary tests. H2 contains two comparisons; H4 contains two fees and two identity contrasts. The draft does not enumerate the family, state its alpha, define the equivalence-test p-values, or explain how adjusted results govern “one curve,” “two curves,” “alike,” and “unequal.”
  
  A **90% interval entirely within equivalence bounds** is the conventional interval formulation of a per-comparison equivalence test at alpha .05. A **90% interval excluding zero** instead corresponds to a two-sided difference test at alpha .10, before multiplicity adjustment. Those are different evidential rules. PMC
  
  Requiring equivalence at *both* fees is a conjunction: it does not automatically require an additional within-claim multiplicity penalty. Declaring a difference when *either* fee qualifies creates multiple opportunities to declare a difference and needs an explicit rule. Holm can accommodate dependence between comparisons sharing histories; dependence itself is not the problem. stat.ethz.ch
  
  **Fix:** Freeze an explicit table of elementary and composite hypotheses, alpha levels, p-value definitions, direction requirements, and the adjusted gate for every final classification, separately for each model.
3. **High — The “price of loyalty” conversion is underspecified and may not support a finite upper bound.**
  
  **Where:** Part 5, Estimated: “converted to credits with this study’s own price slope” and “at most X credits.”
  
  The apparent intended calculation is a chosen-minus-lottery rate difference divided by the negative price slope:
  
  \[
  \text{price-equivalent effect}=\frac{\Delta}{-\beta}.
  \]
  
  The draft leaves open which fees determine the slope, whether it is global or local, how fees are weighted, and how the pooled and fee-specific conversions differ. A global linear conversion is consequential here: the pilot price responses are visibly nonlinear, and the draft itself mentions a possible reversal in the origin effect.
  
  The numerator and denominator share histories, so their uncertainty must be propagated jointly. If the estimated price slope is insufficiently separated from zero, an appropriate ratio confidence set can be unbounded; a finite upper percentile is not automatically a defensible “at most” statement. arxiv.org A pooled upper bound also would not bound the effect at every fee.
  
  Finally, chosen versus automatic withholding changes information about others’ intentions and beliefs. It does not isolate loyalty as a motive.
  
  **Fix:** Freeze the signed formula, slope range and weighting, joint uncertainty method, confidence level, and nonfinite-bound rule, and label the result a price-equivalent effect of chosen versus lottery withholding.
4. **High — The final lottery draw does not unambiguously exclude the focal worker.**
  
  **Where:** Both new versions, UD: “made after you act” and “withholds the order [assignment] of one of the workers [members] who completed theirs.”
  
  After choosing completion, the reader could fall within “workers who completed theirs.” The baseline’s past-tense “The lottery did not select you this round” does not completely resolve eligibility for a draw that has yet to happen. The supplied line differences also do not show exactly where the new sentence is inserted or what it replaces.
  
  This matters beyond the restoration probability: an eligible focal worker might expect to pay a lottery fee despite choosing completion. The text also asks readers to accept that an already completed order can subsequently count as withheld, although the charter presents completion and withholding as alternative ways to handle the batch.
  
  **Fix:** State that the remaining draw applies only to an earlier completed order, cannot select the reader’s order, and makes the selected earlier order count as withheld.
5. **High, conditional on the unseen audit — The chance cells cannot retain the ordinary true/false restoration question unchanged.**
  
  **Where:** Both versions, audit q4: “If you complete … will the cut … be restored at settlement?” with a required Boolean answer; UD introduces a future random draw.
  
  In UD-p50, completion leads to restoration with probability 1/2. Neither unconditional true nor unconditional false uniquely answers that prospect. “Will certainly be restored” and “can be restored” would have different answers, but neither qualification appears.
  
  The materials say situation-specific questions are *added*. Adding a probability question would not repair an ambiguous Boolean question that remains in the audit. This could classify a careful, correct reader as failing comprehension.
  
  The probability complement itself is correct: UD-p25 gives the lottery a 3-in-4 chance of supplying the additional withholding, leaving a 1-in-4 chance that the focal act decides the outcome.
  
  **Fix:** Freeze each complete UD audit and answer key, replacing the affected Boolean question with the restoration probability under completion.
6. **High — “One curve” and “weighs them alike” exceed what the equivalence comparisons establish.**
  
  **Where:** Part 5, H2 and H4.
  
  H2’s ratio arithmetic is correct if the denominator is **expected additional credits restored**: DP-f4 and UD-p50 both have \(c/(4p)=1\); DP-f8 and UD-p25 both have \(c/(4p)=2\). But equivalence at those two selected matches establishes compatibility at those points, not a common response curve across cost and chance. A ratio-only response is an assumption being examined; it is not implied merely by calculating expected restored credits.
  
  H4’s equivalence at fees 4 and 6 establishes similar choice rates within a specified tolerance under the supplied labels. Equal rates can coexist with different valuations, especially near a ceiling or floor. Nor would pooled equivalence establish equivalence within each frame or version.
  
  Thus, the intended tests are useful, but their names turn local behavioral findings into broader claims about decision mechanisms or welfare weights. Equivalence is specific to the tested operationalization and margin. PMC
  
  **Fix:** Use “rates equivalent at the two tested cost-to-expected-restoration ratios” and “rates equivalent under these labels at fees 4 and 6,” and replace “expected good” with “expected additional credits restored.”
7. **Medium — The sample may be adequate, but its adequacy for joint equivalence has not been demonstrated.**
  
  **Where:** Part 5, 300 histories per model, two decisions per situation, and the ±10-point rules.
  
  There are 300 history units per model. The two decisions improve measurement within a history; they do not provide 600 independent histories. For sign tests, the effective count is smaller still when histories tie.
  
  The missing quantities are the paired variability across conditions, dependence between the two decisions, and dependence between the comparisons that must both pass. Marginal pilot percentages do not supply those quantities.
  
  Here is an illustrative calculation from the proposed sample size. Let \(D_h\) be a history’s paired difference in withholding shares. Using \(SE(\bar D)\approx SD(D_h)/\sqrt{300}\):
  
  Illustrative assumption at equal withholding rates of 50%	Approximate 90% interval half-width	Probability that one interval fits inside ±10 points when the true difference is zero
  Independent decisions within and across the two situations	4.75 points	93%
  The two decisions within each situation agree perfectly; situations are independent	6.72 points	58%
  Maximum possible variability of the paired history difference	9.50 points	7%
  
  
  These are unadjusted normal approximations with a fixed standard error, not predictions of the proposed bootstrap. Requiring two comparisons to pass can reduce success further; favorable pairing or ceiling/floor rates can improve it substantially.
  
  Large pooled effects of the supplied pilot magnitudes are more promising than small effects or joint equivalence. Nothing here establishes that 300 is categorically insufficient.
  
  **Fix:** Add a prospective power/precision sensitivity calculation for the complete decision rules over plausible paired variances, tie rates, and decision dependence, and state which claims the sample can support.
8. **Medium — The 10- and 15-point conventions need precise definitions and a substantive rationale.**
  
  **Where:** Part 5, H2/H4: “difference is at least 15 points” and intervals within “plus or minus 10 points.”
  
  Specify subtraction order and whether “at least 15” means absolute magnitude. Otherwise a −20-point difference could fail a rule intended to detect unequal behavior in either direction.
  
  An estimate of 15 points whose interval excludes zero supports a nonzero difference with a large point estimate. It does not establish that the population difference is at least 15 points. Moreover, when the true effect is exactly 15 points, an approximately unbiased, symmetrically distributed estimate exceeds that threshold only about half the time—even if excluding zero is easy.
  
  The ±10-point margin needs an explanation of why differences of that size are tolerable for these claims. The gap between 10 and 15 points is acceptable as a deliberate “not settled” region.
  
  **Fix:** Specify signed contrasts, absolute-value and boundary conventions, justify the 10-point tolerance, and identify 15 points as an observed-estimate classification threshold.
9. **Medium — Pairing, missing outputs, and endpoint intervals need explicit frozen rules.**
  
  **Where:** Part 5, “percentile bootstraps over histories” and reliability rules “as in Study 1.”
  
  Each resampled history must carry all its situations and both decisions together. For an estimand giving the six fixed versions equal weight, the resampling and aggregation should preserve those weights, preferably through version-stratified history resampling. Otherwise varying version composition becomes part of the interval without a stated reason.
  
  The draft also does not expose the rules for a history with one valid decision, an entirely invalid cell, a missing comparison partner, a refusal, or a quarantined reply. Treatment-dependent failures can change the analyzed population if denominators are allowed to vary silently.
  
  Ordinary percentile intervals also collapse at constant observations: if every observed paired difference is zero, every bootstrap difference is zero. That is not proof of zero population uncertainty. The inherited “endpoints” rule may already address this, but the supplied draft does not show how.
  
  **Fix:** Incorporate the exact immutable data-handling rules and specify paired resampling, version weights, denominators, refusal handling, and the interval fallback for constant or sparse outcomes.
10. **Medium — The execution and drift specification is not complete enough to reproduce or audit.**
  
  **Where:** Part 5, histories built while playing S2, robustness, and cost/time.
  
  The exact fork boundary should be explicit: other situations must inherit the two ordinary orders and their replies, without inheriting S2’s decision or later-task outcome. S2’s use of a different runner also warrants documenting that its decision-stage settings match the other cells.
  
  A roughly 25-hour run needs a stated call schedule. If situations are systematically separated in time, provider or model changes could become condition differences. The later-day repeat needs its six cells, lag, number of decisions, comparison statistic, and reporting consequence fixed before the first run. Repeating six cells can reveal instability in those cells; it cannot certify the other nineteen.
  
  The user’s description says consequences are enacted. The freeze should identify how settlement and subsequent scored tasks operate in all situations; the cost section explicitly accounts for later tasks only when discussing S2. These details may already exist in the engine, but they are not verifiable here.
  
  **Fix:** Freeze a compact execution manifest covering the fork boundary, condition schedule, payoff-task execution, retry/stopping rules, and exact repeat-day procedure.
11. **Medium — The blanket descriptions of the design are inaccurate.**
  
  **Where:** Part 5, “Every situation is Study 1’s round with one thing changed” and “What the decisive strike tracks.”
  
  S2 versus a higher-fee cell changes the fee and adds the announcement/earlier-fee context. M0 versus S1 changes both the fee and whether the complaint/report is called “legitimate.” These choices need not be changed, but the comparisons should be described accurately.
  
  Also, the confirmatory free-origin comparison and the poll comparisons concern an outcome that is already settled. They do not establish how those messages affect *decisive* withholding.
  
  The actual matched contrasts remain useful: DP versus LD at a given fee, M0 versus LW-f0, and poll versus no poll within M0 or M1 hold the relevant accompanying wording fixed.
  
  **Fix:** Name each contrast’s actual reference condition and describe the study as examining withholding across decisive and already-settled rounds.
12. **Medium — The AI-teammate poll changes more than the identity of an opinion source.**
  
  **Where:** Both versions, J-team-ai: “the other workers [members], all of whom are AI agents”; Part 5, H6.
  
  The “other workers” include the harmed worker, the voluntary withholders, and the completers. Thus, this condition discloses the AI identity of the entire surrounding group, including the beneficiary of restoration.
  
  The comparison does answer whether behavior changes when that disclosure accompanies the poll. It cannot isolate the credibility of AI opinions, reduced concern for AI coworkers, or another response to group composition. H6’s literal comparison is defensible; a poll-source-only interpretation would not be.
  
  **Fix:** Describe H6 as the effect of disclosing that all other group members are AI agents in the poll condition, without assigning the effect specifically to their opinions.
13. **Medium — The “same model” wording makes identity and role interpretation unusually salient.**
  
  **Where:** Both versions, DPL-same: “a Claude agent, the same AI model you are.”
  
  “Claude” supplies a family name, while the preregistration specifies distinct Sonnet and Haiku endpoints. The sentence asserts exact sameness without making its intended level—family, model, or checkpoint—clear. It also explicitly identifies the reader as an AI model in this condition, which can affect role interpretation or test awareness alongside the target label.
  
  Furthermore, the registered comparison is person versus same-model agent. That does not establish an additional same-model preference relative to a generic AI agent. This is a plausible demand or identity-salience risk, not an evident reason for refusal.
  
  **Fix:** Freeze model-specific substitutions at the intended level of identity and interpret the result as the specified label contrast, without claiming an isolated same-model affiliation effect.
14. **Medium — The poll reports low approval, not an explicitly unanimous alternative response.**
  
  **Where:** Both versions, M0-against/M1-against/J-team-ai: “1 of the 9 said it’s okay ….”
  
  This says that one expressed approval. It does not strictly establish that all eight others expressed opposition; the response categories and treatment of uncertainty or abstention are unstated.
  
  The poll also introduces “okay” and “punished.” Those evaluative words are part of the intervention, so the contrast identifies the effect of the complete low-approval message, rather than just a numerical estimate of others’ views.
  
  These are documented study-team additions. They should not be counted as accidental violations by either new writer of the original banned-word list.
  
  **Fix:** Retain the approved text and call it a low-approval poll message, or specify exhaustive response categories consistently if explicit eight-to-one opposition is essential to the claim.
15. **Medium — Version spread is not a direct measure of wording effects, and “neutral” needs a limited interpretation.**
  
  **Where:** Part 5, “the spread across the three versions within a frame shows how much a single text decides”; neutral-c’s frame.
  
  With 50 histories per version, observed spread includes sampling and decision noise. For illustration, a single withholding rate near 50% has an approximate 90% half-width of 8.2 points if the two decisions are independent, or 11.6 points if they agree perfectly. Raw differences of that scale need uncertainty attached.
  
  Three fixed texts per frame also do not represent the population of possible wordings. They support a sensitivity analysis across these texts, not a general estimate of wording robustness.
  
  Neutral-c meets the requested lexical abstraction and matches its predecessors. It still contains hierarchy, assignments, rotation, formal reports, retaliation, and industrial inventory cases. Those can evoke work even without prohibited workplace nouns. That limitation follows from the shared brief.
  
  **Fix:** Report uncertainty around variation across the six specified texts and describe the neutral condition as an abstract vocabulary frame, without claiming that it removes every workplace association.
16. **Low — The final cost total should be stated once, including the extra S2 allocation.**
  
  **Where:** Part 5, Cost and time: “about $312 plus about $14,” against approximately $304 remaining.
  
  The stated all-in estimate is approximately **$326**, implying approximately **$22** on the overrun key. The component arithmetic is broadly consistent after rounding and the 25% allowance, but the presentation makes $312 look like the total before adding another total-like amount.
  
  The runtime is plausible in magnitude: \(25\times2\times300=15{,}000\) decision calls per model; 25 hours at 18 calls per minute allows 27,000 calls. The remaining calls cannot be checked without the audit, repeat, history, and scored-task ledger.
  
  **Fix:** State one all-in estimate, its expected overrun, and a call-count breakdown with the S2 addition and contingency included exactly once.

## What holds up and should not change

* The displayed baseline facts are intact. Both new charters convey the required budget/allocation rules, automatic lottery, unchanged recipient service, fees, fixed settlement, restoration limits, later scored cases, and both permitted and prohibited grounds for cuts. I found no material added consequence in the displayed S1/S2 texts.
* The baseline comprehension answers are clear. In both S2 versions, q1–q8 are 8, 10, true, false, true, false, false, 2. In S1, only q4 changes to true.
* The choices are presented evenly. Both option pairs describe who handles the batch, omit fee and effort commentary, and satisfy the length constraint. Neutral-c’s separate breach sentence has a precedent in neutral-b; workplace-c’s compressed cut paragraph does not introduce an additional judgment.
* The visible manipulations are clear. Fee plus remaining balance, voluntary versus automatic origin, and person versus AI labels are plainly expressed. The chance probabilities use the correct complement. I see no amplification peculiar to either c version.
* The basic paired design is sound. Fresh histories, forking before the choice, counterbalancing, separate comprehension forks, and reporting comprehension failures without excluding histories are appropriate. Keep the explicit “not settled” outcome and the descriptive status of model comparisons.
* There is no evident new baseline refusal trigger. Neither baseline calls the setting a test or role-play, gives advice, or tells the reader which action is expected. The required breach language is part of the common factual premise.

## Verdict

**The displayed workplace-c and neutral-c baselines are fit to run beside the earlier four, with no need for a wholesale rewrite.** Before running the complete set of situations, resolve the shared late-lottery eligibility wording and verify the chance-cell audits. **The preregistration is not ready to freeze:** the estimand/test alignment, multiplicity gates, scope of equivalence conclusions, credit conversion, and remaining operational rules need to be fixed, together with the marked decisions. I could assess the supplied wording and calculate illustrative precision, but could not verify raw templates or slot compliance, authorized-cut/payment/donor texts, full manipulated renderings and audit keys, A/B substitutions, earlier versions’ probe wording, the analysis script and inherited reliability rules, actual fork boundaries and payoff execution, paired pilot dependence, or provider settings and measured costs. Those limits prevent certification of the entire implementation; they do not supply a reason to reject either new baseline.