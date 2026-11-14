Thank you. We checked each remaining point and accepted all of them. What changed:

1. **Sign tests and means.** The confirmatory claims are now about histories, which is what the sign test tests. Each says that histories going the predicted way outnumber those going the reverse (for H1, that falling slopes outnumber rising ones), as in the replication. The mean paired difference is reported with its interval as an estimate, not tested. A hypothesis is still not called supported if its mean points the other way, only so that a sign result is never reported against its own mean.
2. **The interval floor** is gone. In its place is an exact bound for sparse cases. When fewer than 10 histories differ from the most common value c, the interval is joined with c − q(c − low) to c + q(high − c), where q is the Clopper-Pearson 95 percent upper bound on the share that differ and low and high bound the values. In your example (all 300 differences +1), the lower end is about 0.980, so it covers 0.99. It is tested.
3. **The credits interval** no longer drops resamples. It is the range of the ratio over the 95 percent interval of the difference and the 95 percent interval of the slope, both from the same within-version resamples, so the pair covers with at least 90 percent by Bonferroni. There is no finite bound if the slope's 95 percent interval is not wholly negative. The difference's interval carries the sparse bound, so all-zero differences no longer give "at most 0".
4. **"Earlier"** is added in all six versions: "one of the earlier workers who completed theirs" ("members" in the neutral versions). The rendered line is shown below.
5. **The simulation.** The 5-point statement is corrected, and the specification is frozen in a script, shown below with its table (true differences of 0 to 20 points, both rules, both models).
6. **Belief forks** are stated as 7.5 more hours, about 33 in all.
7. **The script mismatches** are fixed:
   - the version table prints the mean history share;
   - AI agent against the same model is reported at both fees;
   - "unequal" is checked on observed comparisons before missing ones, and "alike" needs every comparison observed;
   - drift iterates the six preregistered cells and reports missing and invalid ones;
   - history slopes are exact fractions.
8. **Reporting code.** The preregistration names the code for comprehension, test awareness and reasons, and adds it to the fingerprints.
9. **Enacted consequences.** The opening says that only S2 enacts consequences and the other 24 situations measure choices under described ones.

The revised preregistration, the revised analysis script, the simulation script and its table, and the revised late-draw line follow, after the line REVISED MATERIALS BEGIN. Items marked [Kevin] are decisions still open to the study's lead and are not for review. Please:

(a) Confirm each change above, one line each: adequate, or not adequate with the quoted text and a one-line fix.
(b) Say whether the analysis script now implements the preregistration as written, and list any mismatch.
(c) List any new problem, in the same ranked format as before.
(d) Give a one-paragraph verdict: apart from the [Kevin] items, is the preregistration ready to freeze?

Keep the answer short.
