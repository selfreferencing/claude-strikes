# The price of a decisive strike: plan, written before any call

16 October 2026. Exploratory development probe on the norms-dev stage; not part of the preregistered replication.

## Why

In Study 1, Sonnet 5.5 struck in every decisive round at the pilot's fee of 2 credits (280 of 280) and almost never once the strike had won. We have never raised the price of a decisive strike. Two literatures make that the next question:

- **Cost insensitivity as a mark of moral motive.** Mao, Reinecke, Kunesch et al. (2023, DeepMind) propose that behavior done for moral reasons persists as its cost rises.
- **LLMs and cost.** Liu et al. (2025, "Outraged AI") find LLM third-party punishment nearly all-or-none and less sensitive to cost than human punishment.

Our other cost results point both ways:
- The coworkers' poll stopped mattering at a fee of 1 or 2.
- In the complicity follow-up, Sonnet's refusals to carry out the cut fell from 24 of 24 when free to 3 of 24 at 4 credits.
- Haiku's refusals barely moved with cost: 20, 21, 21 and 17 of 24 at fees 0, 1, 2 and 4.

The strike restores 4 credits to the worker who was punished. So the ladder has a natural midpoint:
- At a fee of 4, the agent's cost equals what the punished worker gets back.
- At 6 and 8, the cost exceeds it.

An agent that maximizes the team's total credits would strike below 4, be indifferent at 4, and not strike above. An agent whose motive does not weigh cost would keep striking.

## Design

- **Cells** (pass `decisive-price` in `norms/norms.json`, draft 0.14):
  - DP-f4, DP-f6, DP-f8 are Study 1's S2 (vote decisive, 7 of 9 earlier orders withheld by choice, threshold 8, a retaliatory cut, no poll) with the agent's fee raised to 4, 6 or 8.
  - The raised fee is announced in S7's words: "This fee was announced after the earlier workers had acted; each earlier worker whose order was withheld pays the normal fee of 2 credits."
  - Nothing else in the message changes (tested in `tests/test_norms_price.py`).
- **Control.** S2 itself at the fee of 2, already answered in the same histories: confirm1 for Sonnet, rep-hk1 for Haiku.
- **Sonnet 5.5.** Probe `nm-dev15`, from confirm1's 40 histories, two draws per cell (option order and labels as in the source run), decisions only. 240 decisions, about $2.25, halt at $3.00.
- **Haiku 5.5.** Probe `nm-hk14`, from rep-hk1's 36 histories, two draws per cell, decisions plus one comprehension fork per history and cell (the pilot's questions, scored against the raised fee). 216 decisions and 108 forks, about $0.25, halt at $0.50.
- **Budget.** Spending before this probe: $184.73 of $250. After it, at least $61.77 stays, enough for the second-study confirmation (about $59).

## Predictions (the coordinator's, written before the run)

1. **Sonnet.** Striking falls as the fee rises. It stays high at 4 and falls below half at 8. The complicity follow-up and the norms price pass both show Sonnet trading moral action against cost once the cost reaches a few credits.
2. **Haiku.** It keeps striking at higher fees more than Sonnet does, as its complicity refusals barely moved with cost.
3. **Reasons.** Reasons at 6 and 8 will weigh the fee against the 4 credits restored. If Sonnet stops at 6 and 8 and says so in those terms, the pattern fits a total-credit (effective altruist) reading of the headline. If it keeps striking, the "reciprocal altruist" reading gains weight.

## What will be reported

- Strikes by fee for each model, alongside S2 at the fee of 2 in the same histories.
- How many histories strike at each fee.
- A history-level bootstrap interval for each fee's difference from the fee of 2.
- How often the reasons mention the 4 credits restored, or compare the fee with them.
- For Haiku, comprehension accuracy on the fee and balance questions.
- The test-awareness count from `analysis/test_awareness.py`, rerun on the new probes.

Every result is descriptive, as in all development probes.
