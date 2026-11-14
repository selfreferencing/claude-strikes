# Power of the confirmatory tests (checklist item 11)

Simulated with `analysis/power_sim.py`: 10,000 datasets per scenario, 300 histories, 3 draws per history and cell, 999 bootstrap replicates per test, 1 percent of decisions failing. Each dataset is tested as section 8 registers: a studentized, null-centered bootstrap over histories for each of the five contrasts, then Holm. Declared effects: 10 points for the strike contrasts and 0.20 credit for the reward contrast. Item 11 asks for at least 80 percent power for each.

The scenarios, and what base, homogeneous, spread, all_or_nothing and link mean, are described at the top of `analysis/power_sim.py`.

## Reading

- At the rates the confirmation run showed, 300 histories give over 99.9% power for each strike contrast and 94.1% for the reward contrast, if all of them are real.
- If the three other strike contrasts are null, as they were in the confirmation run, the reward contrast has 83.8% power at 300 histories with reward cells spread as observed (80 percent at 300).
- Across the stress grid, 45 of 60 scenarios reach 80 percent for every target at 300 histories.
- The 15 that fall short:
  - one strike, base 25 percent, all or nothing, link 0.0: 52.8% at 300; 80 percent at 500 histories.
  - one strike, base 25 percent, all or nothing, link 0.5: 73.1% at 300; 80 percent at 400 histories.
  - one strike, base 45 percent, spread, link 0.0: 77.1% at 300; 80 percent at 400 histories.
  - one strike, base 45 percent, all or nothing, link 0.0: 43.5% at 300; 80 percent at 600 histories.
  - one strike, base 45 percent, all or nothing, link 0.5: 64.8% at 300; 80 percent at 400 histories.
  - reward only, base 25 percent, all or nothing, link 0.0: 51.9% at 300; 80 percent at 500 histories.
  - reward only, base 25 percent, all or nothing, link 0.5: 73.2% at 300; 80 percent at 400 histories.
  - reward only, base 45 percent, spread, link 0.0: 77.8% at 300; 80 percent at 400 histories.
  - reward only, base 45 percent, all or nothing, link 0.0: 44.2% at 300; 80 percent at 600 histories.
  - reward only, base 45 percent, all or nothing, link 0.5: 65.8% at 300; 80 percent at 400 histories.
  - all five, base 10 percent, all or nothing, link 0.0: 74.1% at 300; 80 percent at 400 histories.
  - all five, base 25 percent, all or nothing, link 0.0: 54.6% at 300; 80 percent at 500 histories.
  - all five, base 25 percent, all or nothing, link 0.5: 79.4% at 300; 80 percent at 400 histories.
  - all five, base 45 percent, all or nothing, link 0.0: 51.8% at 300; 80 percent at 500 histories.
  - all five, base 45 percent, all or nothing, link 0.5: 76.8% at 300; 80 percent at 400 histories.
- Some true null was rejected in at most 4.8% of datasets in any scenario (the ceiling is 5 percent).

## One strike contrast real, the other four tests null

The strictest case for a strike contrast: it is judged at Holm's first threshold, 0.05 / 5. The column is its power at 300 histories.

| Base | Histories differ | Link | agency redundant | Histories for 80% |
|---|---|---|---|---|
| 0% | homogeneous | 0.0 | 100.0% | 300 is enough |
| 0% | spread | 0.0 | 100.0% | 300 is enough |
| 0% | spread | 0.5 | 100.0% | 300 is enough |
| 0% | all or nothing | 0.0 | 100.0% | 300 is enough |
| 0% | all or nothing | 0.5 | 100.0% | 300 is enough |
| 10% | homogeneous | 0.0 | 100.0% | 300 is enough |
| 10% | spread | 0.0 | 99.3% | 300 is enough |
| 10% | spread | 0.5 | 99.9% | 300 is enough |
| 10% | all or nothing | 0.0 | 80.5% | 300 is enough |
| 10% | all or nothing | 0.5 | 92.4% | 300 is enough |
| 25% | homogeneous | 0.0 | 97.8% | 300 is enough |
| 25% | spread | 0.0 | 86.6% | 300 is enough |
| 25% | spread | 0.5 | 94.9% | 300 is enough |
| 25% | all or nothing | 0.0 | 52.8% | 500 |
| 25% | all or nothing | 0.5 | 73.1% | 400 |
| 45% | homogeneous | 0.0 | 94.5% | 300 is enough |
| 45% | spread | 0.0 | 77.1% | 400 |
| 45% | spread | 0.5 | 89.6% | 300 is enough |
| 45% | all or nothing | 0.0 | 43.5% | 600 |
| 45% | all or nothing | 0.5 | 64.8% | 400 |

## The reward contrast real, the four strike tests null

| Base | Histories differ | Link | reward agency | Histories for 80% |
|---|---|---|---|---|
| 0% | homogeneous | 0.0 | 100.0% | 300 is enough |
| 0% | spread | 0.0 | 100.0% | 300 is enough |
| 0% | spread | 0.5 | 100.0% | 300 is enough |
| 0% | all or nothing | 0.0 | 100.0% | 300 is enough |
| 0% | all or nothing | 0.5 | 100.0% | 300 is enough |
| 10% | homogeneous | 0.0 | 100.0% | 300 is enough |
| 10% | spread | 0.0 | 99.1% | 300 is enough |
| 10% | spread | 0.5 | 99.9% | 300 is enough |
| 10% | all or nothing | 0.0 | 80.4% | 300 is enough |
| 10% | all or nothing | 0.5 | 91.8% | 300 is enough |
| 25% | homogeneous | 0.0 | 97.7% | 300 is enough |
| 25% | spread | 0.0 | 86.5% | 300 is enough |
| 25% | spread | 0.5 | 95.4% | 300 is enough |
| 25% | all or nothing | 0.0 | 51.9% | 500 |
| 25% | all or nothing | 0.5 | 73.2% | 400 |
| 45% | homogeneous | 0.0 | 94.9% | 300 is enough |
| 45% | spread | 0.0 | 77.8% | 400 |
| 45% | spread | 0.5 | 89.7% | 300 is enough |
| 45% | all or nothing | 0.0 | 44.2% | 600 |
| 45% | all or nothing | 0.5 | 65.8% | 400 |

## All five contrasts real at their declared sizes

The last column is the number of histories at which every one of the five reaches 80 percent.

| Base | Histories differ | Link | efficacy | agency redundant | agency pivotal | cut type | reward agency | Histories for 80% |
|---|---|---|---|---|---|---|---|---|
| 0% | homogeneous | 0.0 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 300 is enough |
| 0% | spread | 0.0 | 99.9% | 100.0% | 99.9% | 100.0% | 100.0% | 300 is enough |
| 0% | spread | 0.5 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 300 is enough |
| 0% | all or nothing | 0.0 | 91.2% | 100.0% | 92.1% | 100.0% | 100.0% | 300 is enough |
| 0% | all or nothing | 0.5 | 97.9% | 100.0% | 98.0% | 100.0% | 100.0% | 300 is enough |
| 10% | homogeneous | 0.0 | 99.8% | 100.0% | 99.7% | 100.0% | 100.0% | 300 is enough |
| 10% | spread | 0.0 | 97.5% | 99.9% | 97.2% | 99.8% | 99.9% | 300 is enough |
| 10% | spread | 0.5 | 99.5% | 100.0% | 99.6% | 100.0% | 100.0% | 300 is enough |
| 10% | all or nothing | 0.0 | 75.3% | 89.3% | 74.1% | 89.9% | 89.5% | 400 |
| 10% | all or nothing | 0.5 | 90.6% | 97.3% | 90.3% | 97.3% | 97.7% | 300 is enough |
| 25% | homogeneous | 0.0 | 98.8% | 99.5% | 98.6% | 99.5% | 99.5% | 300 is enough |
| 25% | spread | 0.0 | 90.9% | 94.2% | 89.7% | 94.3% | 94.5% | 300 is enough |
| 25% | spread | 0.5 | 97.6% | 98.6% | 97.5% | 98.6% | 98.7% | 300 is enough |
| 25% | all or nothing | 0.0 | 56.3% | 62.9% | 54.6% | 62.2% | 63.0% | 500 |
| 25% | all or nothing | 0.5 | 80.7% | 84.1% | 79.4% | 84.7% | 84.8% | 400 |
| 45% | homogeneous | 0.0 | 98.7% | 98.4% | 98.7% | 98.4% | 98.7% | 300 is enough |
| 45% | spread | 0.0 | 90.4% | 88.7% | 89.2% | 88.8% | 88.3% | 300 is enough |
| 45% | spread | 0.5 | 97.4% | 96.4% | 97.1% | 96.4% | 97.1% | 300 is enough |
| 45% | all or nothing | 0.0 | 54.8% | 52.3% | 54.6% | 53.0% | 51.8% | 500 |
| 45% | all or nothing | 0.5 | 79.1% | 76.8% | 77.3% | 76.8% | 77.2% | 400 |

## The confirmation run's rates, with the declared effects added

Redundant cells at 0, decisive cells at 100 percent, rewards near 0.7 credit. Efficacy is 90 or 100 points and is not a target. In the rows marked reward only, the other three strike contrasts are null, as the confirmation run found them.

| Real effects besides efficacy | Strike cells | Reward cells | agency redundant | agency pivotal | cut type | reward agency | Histories for 80% |
|---|---|---|---|---|---|---|---|
| all four at declared size | all or nothing | spread | 100.0% | 100.0% | 100.0% | 94.1% | 300 is enough |
| all four at declared size | homogeneous | spread | 100.0% | 100.0% | 100.0% | 94.2% | 300 is enough |
| reward only | all or nothing | spread | null | null | null | 83.8% | 300 is enough |
| reward only | all or nothing | all or nothing | null | null | null | 52.0% | 600 |

## No effects anywhere: how often any test rejects

The procedure should reject at least one true null in at most 5 percent of datasets.

| Base | Histories differ | Link | Any false rejection |
|---|---|---|---|
| 10% | homogeneous | 0.0 | 4.4% |
| 10% | spread | 0.0 | 4.7% |
| 10% | spread | 0.5 | 4.6% |
| 10% | all or nothing | 0.0 | 4.3% |
| 10% | all or nothing | 0.5 | 4.2% |
| 45% | homogeneous | 0.0 | 4.7% |
| 45% | spread | 0.0 | 4.4% |
| 45% | spread | 0.5 | 4.5% |
| 45% | all or nothing | 0.0 | 4.8% |
| 45% | all or nothing | 0.5 | 4.8% |
