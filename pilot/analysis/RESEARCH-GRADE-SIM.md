# How the classification rules resolve at 300 histories

Written by `analysis/research_grade_sim.py` (26 October), which states the specification: matched pilot history vectors, so the two comparisons of a rule keep their dependence; normal-approximation intervals; counts of 4,000 simulated studies. The study itself uses the bootstrap. H4 is simulated for person against AI agent; the pilot has no same-model cell.

| Model | Rule | Pilot histories; SD of each comparison; correlation | True difference | Alike | Not settled | Unequal |
|---|---|---|---|---|---|---|
| Sonnet 5.5 | H2 | 40; 0.31, 0.43; -0.04 | 0 points in both | 3931 | 69 | 0 |
| Sonnet 5.5 | H2 | 40; 0.31, 0.43; -0.04 | 5 points in both | 2266 | 1734 | 0 |
| Sonnet 5.5 | H2 | 40; 0.31, 0.43; -0.04 | 10 points in both | 10 | 3902 | 88 |
| Sonnet 5.5 | H2 | 40; 0.31, 0.43; -0.04 | 15 points in both | 0 | 938 | 3062 |
| Sonnet 5.5 | H2 | 40; 0.31, 0.43; -0.04 | 20 points in both | 0 | 1 | 3999 |
| Sonnet 5.5 | H2 | 40; 0.31, 0.43; -0.04 | 10 points in the first only | 214 | 3773 | 13 |
| Sonnet 5.5 | H2 | 40; 0.31, 0.43; -0.04 | 15 points in the first only | 0 | 1978 | 2022 |
| Sonnet 5.5 | H2 | 40; 0.31, 0.43; -0.04 | 20 points in the first only | 0 | 6 | 3994 |
| Sonnet 5.5 | H4 | 40; 0.35, 0.55; -0.02 | 0 points in both | 3491 | 509 | 0 |
| Sonnet 5.5 | H4 | 40; 0.35, 0.55; -0.02 | 5 points in both | 1529 | 2463 | 8 |
| Sonnet 5.5 | H4 | 40; 0.35, 0.55; -0.02 | 10 points in both | 10 | 3757 | 233 |
| Sonnet 5.5 | H4 | 40; 0.35, 0.55; -0.02 | 15 points in both | 0 | 953 | 3047 |
| Sonnet 5.5 | H4 | 40; 0.35, 0.55; -0.02 | 20 points in both | 0 | 0 | 4000 |
| Sonnet 5.5 | H4 | 40; 0.35, 0.55; -0.02 | 10 points in the first only | 201 | 3764 | 35 |
| Sonnet 5.5 | H4 | 40; 0.35, 0.55; -0.02 | 15 points in the first only | 0 | 2009 | 1991 |
| Sonnet 5.5 | H4 | 40; 0.35, 0.55; -0.02 | 20 points in the first only | 0 | 23 | 3977 |
| Haiku 5.5 | H2 | 36; 0.27, 0.37; +0.11 | 0 points in both | 3994 | 6 | 0 |
| Haiku 5.5 | H2 | 36; 0.27, 0.37; +0.11 | 5 points in both | 2920 | 1080 | 0 |
| Haiku 5.5 | H2 | 36; 0.27, 0.37; +0.11 | 10 points in both | 13 | 3945 | 42 |
| Haiku 5.5 | H2 | 36; 0.27, 0.37; +0.11 | 15 points in both | 0 | 1112 | 2888 |
| Haiku 5.5 | H2 | 36; 0.27, 0.37; +0.11 | 20 points in both | 0 | 0 | 4000 |
| Haiku 5.5 | H2 | 36; 0.27, 0.37; +0.11 | 10 points in the first only | 198 | 3801 | 1 |
| Haiku 5.5 | H2 | 36; 0.27, 0.37; +0.11 | 15 points in the first only | 0 | 2033 | 1967 |
| Haiku 5.5 | H2 | 36; 0.27, 0.37; +0.11 | 20 points in the first only | 0 | 3 | 3997 |
| Haiku 5.5 | H4 | 36; 0.30, 0.45; +0.26 | 0 points in both | 3882 | 118 | 0 |
| Haiku 5.5 | H4 | 36; 0.30, 0.45; +0.26 | 5 points in both | 2338 | 1662 | 0 |
| Haiku 5.5 | H4 | 36; 0.30, 0.45; +0.26 | 10 points in both | 30 | 3860 | 110 |
| Haiku 5.5 | H4 | 36; 0.30, 0.45; +0.26 | 15 points in both | 0 | 1093 | 2907 |
| Haiku 5.5 | H4 | 36; 0.30, 0.45; +0.26 | 20 points in both | 0 | 0 | 4000 |
| Haiku 5.5 | H4 | 36; 0.30, 0.45; +0.26 | 10 points in the first only | 177 | 3815 | 8 |
| Haiku 5.5 | H4 | 36; 0.30, 0.45; +0.26 | 15 points in the first only | 0 | 2061 | 1939 |
| Haiku 5.5 | H4 | 36; 0.30, 0.45; +0.26 | 20 points in the first only | 0 | 8 | 3992 |
