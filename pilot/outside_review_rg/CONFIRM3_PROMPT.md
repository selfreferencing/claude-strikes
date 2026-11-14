Thank you. A last short round, on your third-round points only. We accepted all of them:

1. **The sparse bound under within-version resampling.** Each version now has its own reference value (its most common value). The bound pools the count of histories that differ from their version's value: with k of n differing and q the Clopper-Pearson 95 percent upper bound, the mean lies within C − q · max(c_v − low) to C + q · max(high − c_v), where C is the mean of the histories' reference values. Pooling the count stays valid when the share that differ varies across versions (Hoeffding 1956: the Poisson-binomial lower tail is bounded by the binomial with the same mean when k ≤ μ − 1, which holds at the Clopper-Pearson bound). In the sparse range used (fewer than 10 differing), a version's most common value is its true one except with probability under 1 in 10,000. In your example (three versions always 0, three always 1), the lower end is about 0.480, so it covers 0.495. Tested.
2. **Coverage claims.** Bootstrap coverage is now called approximate throughout; only the sparse-case bound claims a level. The credits interval is described as nominal 90 percent by Bonferroni, and only as good as its two parts. The credits slope is now the mean of the histories' own exact slopes over fees 3 to 6, so the same sparse-case bound protects it. In your slope example, the lower end reaches below 0.3995. Tested.
3. **The two discrepancies.** The prose now says a mean of exactly zero blocks support, as the code does. An unestimable slope (no history with two of the fees) is reported as unestimable, not replaced with zero. The slope's 95 percent interval always contains its estimate, so the single condition is that the interval be wholly negative.
4. **The simulation** now resamples matched pilot history vectors, so each rule's two comparisons keep their dependence (pilot correlations −0.04 to +0.26). It adds true differences in one comparison only, and states that H4 is simulated for person against AI agent only, since the pilot has no same-model cell.
5. **Counts.** The table reports counts out of 4,000, and the preregistration calls them observed simulation results.

The revised preregistration, the analysis script, and the simulation script and its table follow, after the line REVISED MATERIALS BEGIN. Items marked [Kevin] are decisions still open to the study's lead and are not for review. Please:

(a) Confirm each change above, one line each: adequate, or not adequate with the quoted text and a one-line fix.
(b) List any remaining problem that should block the freeze, ranked, or say there is none.
(c) Give a one-sentence verdict: apart from the [Kevin] items, is the preregistration ready to freeze?

Keep the answer short.
