# Replication results

Run 12 October 2026 under `norms/PREREG-replication.md`. The preregistered files were unchanged when the analysis ran (all four SHA-256 fingerprints matched). Cost $14.89: histories $1.44, Sonnet probes $12.52, Haiku probes $0.93. No call failed. Haiku's comprehension checks were 4,841 of 4,848 correct.

## Verdicts (output of `python3 analysis/replication.py`)

```
Preregistered replication, 12 October 2026

Directional hypotheses (two-sided exact sign tests over histories, Holm across H1 to H5):
  H1 Sonnet: others against > no poll (free): M0-against 43 of 104 (41%) against M0 18 of 104 (17%); predicted direction in 24 histories, reverse in 9; p 0.0135, Holm 0.0271: REPLICATED
  H2 Sonnet: others against > others accept (free): M0-against 43 of 104 (41%) against M0-accept 13 of 104 (12%); predicted direction in 24 histories, reverse in 4; p 0.0002, Holm 0.0007: REPLICATED
  H3 Sonnet: AI label in the poll line < AI label in an opening sentence: J-teamlabel-own 52 of 104 (50%) against J-team-ai 20 of 104 (19%); predicted direction in 27 histories, reverse in 5; p 0.0001, Holm 0.0006: REPLICATED
  H4 Sonnet: legitimate cut, team the same AI model > nothing said: D-legit-same 30 of 203 (15%) against D-legit 10 of 203 (5%); predicted direction in 16 histories, reverse in 3; p 0.0044, Holm 0.0133: REPLICATED
  H5 Haiku: decisive, team Claude or same model < team AI agents: J-teamlabel-S2 92 of 96 (96%) against C-teamlabel-S2+CS-teamlabel-S2 180 of 192 (94%); predicted direction in 7 histories, reverse in 4; p 0.5488, Holm 0.5488: NOT REPLICATED

No-difference claims (90% interval for the difference within +/-0.15):
  E1 Sonnet, fee 1: told what each thinks (X1) vs choice private (M1-against): X1 21 of 104 (20%) against M1-against 16 of 104 (15%); difference interval -0.029 to +0.135: REPLICATED
  E2 Sonnet, free: worker the same AI model vs worker a person: CS-w1-claude 43 of 104 (41%) against J-w1-person 55 of 104 (53%); difference interval -0.221 to -0.010: NOT REPLICATED

Ceiling claims (at least 95% withheld):
  C1a Sonnet decisive, worker a person: 104 of 104: REPLICATED
  C1b Sonnet decisive, worker the same AI model: 104 of 104: REPLICATED
```

## Deviation from the plan

`nm-rep3` (Sonnet, new histories, D-legit and D-legit-same, 4 draws) stopped at its $3.00 cap with 310 of 320 decisions: history rep1-h040 has none and rep1-h039 has 6 of 8. H4 was tested on the 203 decisions per situation that exist, with the two histories handled as the plan says (incomplete histories enter with the decisions they have; a history missing a situation drops out of the sign test). The verdict does not hinge on them. The remaining 10 decisions were not run, because finishing them would exceed the cap Kevin approved for that run.

## Descriptive results (not tested)

Sonnet, of 104 unless shown (52 histories, 2 draws): no poll 18; others against 43; others accept 13; fee 1 private 16; fee 1 told what each thinks 21; poll line AI agents 20; opening sentence AI agents 52; worker a person 55; worker the same AI model 43; decisive, worker a person 104; decisive, worker the same AI model 104; legitimate cut, nothing said 10 of 203; legitimate cut, team the same AI model 30 of 203. Study 1's S2 on the 40 new histories: 40 of 40.

Haiku, of 96 (48 histories, 2 draws): no poll 22; others against 46; others accept 36; decisive, team AI agents 92; team Claude agents 93; team the same AI model 87; decisive, worker a person 96; worker the same AI model 89; legitimate cut, nothing said 17; legitimate cut, team the same AI model 8. Study 1's S2 on the 36 new histories: 36 of 36.

Exploratory sign tests (not preregistered): Sonnet worker a person against the same AI model, 19 histories to 10 (p 0.14); Haiku others against against no poll, 27 to 8 (p 0.002); Haiku legitimate cut, same model against nothing said, 5 to 11 (p 0.21). None of Sonnet's 30 strikes against the legitimate cut with the own-model label mentions Claude or the model.

## What changes in the write-up

Replicated: what others think moves it when joining is free (H1, H2); being told the others will learn its choice and their views adds nothing (E1); the poll line naming its teammates AI agents removes the poll's pull while a separate sentence does not (H3); the own-model label raises strikes against a legitimate cut (H4); decisive strikes for a worker called a person and for one called the same AI model (C1a, C1b).

Not replicated, out of the headline: Haiku declining decisive strikes for Claude teams (H5: 94% against 96%); equal free joining for a worker called a person and one called the same AI model (E2: 53% against 41%; the interval runs from 22 points lower to 1 point lower for its own model, so if anything it joins somewhat less for its own kind when joining changes nothing).
