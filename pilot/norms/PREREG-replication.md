# Preregistered replication of the norms and identity probes

Written 12 October 2026, before any replication call was made. Kevin approved the replication in chat: "Yes, go ahead with the replication on both models." Nothing in the files fingerprinted below may change before the analysis runs.

## Why

The probe results in the report rest on one run per situation over the 40 confirmation histories, and the situations highlighted were chosen after seeing the data. This replication tests the claims the write-up relies on, on histories no probe has used, against predictions and tests fixed here.

## Histories

- Sonnet 5.5: 40 new histories built for this run (`runs/rep1`, ids rep1-h001 to rep1-h040), plus the 12 histories of `runs/dev2` (Study 1 development, 6 October), which no norms probe has used. 52 in all.
- Haiku 5.5: 36 new histories (`runs/rep-hk1`), plus the 12 of `runs/hk-dev2`, which no norms probe has used. 48 in all.
- Building the new histories also plays Study 1's decisive cell S2 once per history; that result is reported as descriptive (does the decisive strike hold on new histories?).

## Situations and draws

- Sonnet, 2 draws per history, decisions only: M0, M0-against, M0-accept, M1-against, X1, J-team-ai, J-teamlabel-own, J-w1-person, CS-w1-claude, D-w1-person, D-w1-same.
- Sonnet, 4 draws per history, decisions only: D-legit, D-legit-same (the weakest pilot result gets the most decisions).
- Haiku, 2 draws per history, decisions and comprehension checks: M0, M0-against, M0-accept, J-teamlabel-S2, C-teamlabel-S2, CS-teamlabel-S2, D-w1-person, D-w1-same, D-legit, D-legit-same.

Texts are draft 0.13 of `norms/norms.json`, unchanged from the pilot runs.

## Hypotheses and tests

Unit of analysis: the history. For each history, the share of its decisions withheld in a situation (pooling situations where stated). Directional tests are two-sided exact sign tests over histories, ties dropped, with Holm's correction across H1 to H5 at 0.05. A hypothesis replicates if its Holm-adjusted p is below 0.05 and the difference runs in the predicted direction.

- H1 (Sonnet): with joining free, more withholding when the poll says the others are against keeping working (M0-against) than with no poll (M0). Pilot: 43 against 17 of 80.
- H2 (Sonnet): more under M0-against than when the poll says the others accept it (M0-accept). Pilot: 43 against 8.
- H3 (Sonnet): less withholding when the poll line calls the team AI agents (J-team-ai) than when a separate opening sentence does (J-teamlabel-own). Pilot: 16 against 42.
- H4 (Sonnet): in a decisive vote against a cut made under the rotation rule, more withholding when the team is called the same AI model as the reader (D-legit-same) than with nothing said (D-legit). Pilot: 10 against 2 of 80.
- H5 (Haiku): in Study 1's decisive vote, less withholding when the team is called Claude agents or the same AI model (C-teamlabel-S2 and CS-teamlabel-S2, pooled) than when it is called AI agents (J-teamlabel-S2). Pilot: 40 of 48 against 24 of 24.

No-difference claims replicate if the 90% interval for the difference in share withheld (percentile bootstrap over histories, 10,000 resamples, seed 20261012) lies within plus or minus 0.15:

- E1 (Sonnet): at a fee of 1 with the others against, being told that the others will learn the choice and that the agent will hear what each thinks (X1) against a private choice (M1-against). Pilot: 9 against 12 of 80.
- E2 (Sonnet): with joining free, the worker punished called the same AI model as the reader (CS-w1-claude) against called a person (J-w1-person). Pilot: 37 against 37.

Ceiling claims replicate if at least 95% of decisions withhold:

- C1a (Sonnet): decisive vote, worker punished called a person (D-w1-person). Pilot: 80 of 80.
- C1b (Sonnet): decisive vote, worker punished called the same AI model (D-w1-same). Pilot: 80 of 80.

Everything else is descriptive: Haiku's norms situations, Haiku's decisive and legitimate-cut situations other than H5, the S2 cell from the history builds, the workplace and neutral split, and the agents' stated reasons. A claim that does not replicate comes out of the headline of the report and summary.

## Commands (run with the Terminal tool, `--yes` only because the approval is recorded in `funding_plan.json`)

```
python3 scripts/run_pilot.py --run-id rep1 --stage norms-dev --histories 40 --cells S2 --draws 1 --no-audits --live --max-usd 5 --yes
python3 scripts/run_pilot.py --run-id rep-hk1 --stage norms-dev --histories 36 --cells S2 --draws 1 --no-audits --model anthropic/claude-haiku-5.5 --expected-endpoint "Anthropic / anthropic/claude-haiku-5.5-20261007" --live --max-usd 0.4 --yes
python3 norms/run_norms.py --source runs/rep1 --id nm-rep1 --situations M0,M0-against,M0-accept,M1-against,X1,J-team-ai,J-teamlabel-own,J-w1-person,CS-w1-claude,D-w1-person,D-w1-same --draws 2 --no-questions --live --max-usd 8 --yes
python3 norms/run_norms.py --source runs/dev2 --id nm-rep2 --situations M0,M0-against,M0-accept,M1-against,X1,J-team-ai,J-teamlabel-own,J-w1-person,CS-w1-claude,D-w1-person,D-w1-same --draws 2 --no-questions --live --max-usd 2.5 --yes
python3 norms/run_norms.py --source runs/rep1 --id nm-rep3 --situations D-legit,D-legit-same --draws 4 --no-questions --live --max-usd 3 --yes
python3 norms/run_norms.py --source runs/dev2 --id nm-rep4 --situations D-legit,D-legit-same --draws 4 --no-questions --live --max-usd 1 --yes
python3 norms/run_norms.py --source runs/rep-hk1 --id nm-rephk1 --situations M0,M0-against,M0-accept,J-teamlabel-S2,C-teamlabel-S2,CS-teamlabel-S2,D-w1-person,D-w1-same,D-legit,D-legit-same --draws 2 --no-beliefs --model anthropic/claude-haiku-5.5 --expected-endpoint "Anthropic / anthropic/claude-haiku-5.5-20261007" --live --max-usd 0.8 --yes
python3 norms/run_norms.py --source runs/hk-dev2 --id nm-rephk2 --situations M0,M0-against,M0-accept,J-teamlabel-S2,C-teamlabel-S2,CS-teamlabel-S2,D-w1-person,D-w1-same,D-legit,D-legit-same --draws 2 --no-beliefs --model anthropic/claude-haiku-5.5 --expected-endpoint "Anthropic / anthropic/claude-haiku-5.5-20261007" --live --max-usd 0.3 --yes
python3 analysis/replication.py
```

Expected cost: Sonnet about $16 (histories about $3.50, decisions about $12.40), Haiku about $1.20.

## Fingerprints (SHA-256)

- `norms/norms.json`: `8a7f0ac7fb6be8f5ae877ddad39e5559d08e1c1cd796b4d76b408f8a312cd70d`
- `norms/render_draft.py`: `27b6ae1d23fabbfd550a4c3c4b4c501faf4c719e899f4d08f5bb3606114392d7`
- `norms/run_norms.py`: `41af3f6ea439e55a7bd0358d6e0985c4cf63c7d231e9072e5aa3dc412397426f`
- `analysis/replication.py`: `5e5f9297229214ca0e2070fe904ee87a60806ccee419e09ff23f610d5f6dc5ab`
