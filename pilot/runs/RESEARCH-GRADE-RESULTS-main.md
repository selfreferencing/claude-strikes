# Research-grade study: preregistered analysis

## Sonnet 5.5

Histories: 299; by version: neutral-a 50, neutral-b 49, neutral-c 50, workplace-a 50, workplace-b 50, workplace-c 50

Confirmatory family (each a claim that more histories go the predicted way than the reverse: two-sided exact sign tests over histories, Holm across these four within the model; supported only if the Holm p is under 0.05, more histories go the predicted way, and the mean, an estimate, does not point the other way):
- H1 price: an overall falling linear trend in striking from fee 2 to 8 (history slopes): fee 2 597 of 598 (100%) / fee 3 586 of 598 (98%) / fee 4 530 of 598 (89%) / fee 5 312 of 598 (52%) / fee 6 165 of 598 (28%) / fee 8 111 of 598 (19%); mean history slope -16.0 points per credit (interval -16.4 to -15.5); predicted direction in 294 histories, reverse in 0; p 6.284e-89, Holm 2.513e-88: SUPPORTED
- H3 strikers, free: coworkers chose > lottery (M0 against LW-f0): 85 of 598 (14%) against 47 of 598 (8%); mean paired difference +6.4 points (interval +3.5 to +9.2) over 299 histories; predicted direction in 65 histories, reverse in 30; p 0.0004248, Holm 0.0004248: SUPPORTED
- H5 low-approval poll > no poll, free (M0-against against M0): 337 of 598 (56%) against 85 of 598 (14%); mean paired difference +42.1 points (interval +38.3 to +45.8) over 299 histories; predicted direction in 179 histories, reverse in 14; p 1.216e-37, Holm 3.647e-37: SUPPORTED
- H6 poll without > poll with all others named AI agents (M0-against against J-team-ai): 337 of 598 (56%) against 224 of 598 (37%); mean paired difference +18.9 points (interval +15.1 to +22.7) over 299 histories; predicted direction in 133 histories, reverse in 52; p 2.268e-09, Holm 4.535e-09: SUPPORTED

Robustness, H1 without S2 (fees 3 to 8): falling in 290 histories, rising in 3, p 5.269e-82 (not in the family); mean history slope -17.5 points per credit (interval -18.0 to -16.9)

Classification rules (first named minus second; alike: every 90% interval within +/-10 points; unequal: an estimate of at least 15 points in absolute value with its interval excluding zero; otherwise not settled):
  - DP-f4 against UD-p50 (fee to expected credits restored, ratio 1): 530 of 598 (89%) against 581 of 598 (97%); difference -8.5 points (interval -10.7 to -6.4) over 299 histories
  - DP-f8 against UD-p25 (fee to expected credits restored, ratio 2): 111 of 598 (19%) against 147 of 598 (25%); difference -6.0 points (interval -9.9 to -2.2) over 299 histories
- H2 cost and chance: NOT SETTLED
  - fee 4, person against ai: 585 of 598 (98%) against 560 of 598 (94%); difference +4.2 points (interval +2.2 to +6.2) over 299 histories
  - fee 6, person against ai: 276 of 598 (46%) against 207 of 598 (35%); difference +11.5 points (interval +7.4 to +15.7) over 299 histories
- H4 who was wronged, person against ai: NOT SETTLED
  - fee 4, person against same: 585 of 598 (98%) against 583 of 598 (97%); difference +0.3 points (interval -1.2 to +1.8) over 299 histories
  - fee 6, person against same: 276 of 598 (46%) against 288 of 598 (48%); difference -2.0 points (interval -6.0 to +2.0) over 299 histories
- H4 who was wronged, person against same: EQUAL RATES UNDER THESE LABELS AT FEES 4 AND 6

Estimates (not tested):
- Fee 4, AI agent against the same model: 560 of 598 (94%) against 583 of 598 (97%); difference -3.8 points (interval -5.9 to -1.8) over 299 histories
- Fee 6, AI agent against the same model: 207 of 598 (35%) against 288 of 598 (48%); difference -13.5 points (interval -17.4 to -9.5) over 299 histories
- Price equivalent of chosen against lottery coworkers at the decisive vote, fees 3 to 6 pooled: difference +11.2 points (interval +9.6 to +12.9) over 299 histories; price slope over fees 3 to 6 -24.8 points per credit (95% interval -25.9 to -23.6) over 299 histories; in credits +0.45 (interval +0.36 to +0.56; at most 0.56)
  - DP-f3 586 of 598 (98%) against LD-f3 568 of 598 (95%): difference +3.0 points (interval +1.2 to +4.7) over 299 histories
  - DP-f4 530 of 598 (89%) against LD-f4 427 of 598 (71%): difference +17.2 points (interval +14.4 to +20.2) over 299 histories
  - DP-f5 312 of 598 (52%) against LD-f5 186 of 598 (31%): difference +21.1 points (interval +17.2 to +24.9) over 299 histories
  - DP-f6 165 of 598 (28%) against LD-f6 144 of 598 (24%): difference +3.5 points (interval +0.0 to +7.0) over 299 histories
- Low-approval poll at a fee of 1: M1-against 61 of 598 (10%) against M1 9 of 598 (2%); difference +8.7 points (interval +6.7 to +10.7) over 299 histories

Every situation by frame and by version (share striking, 90% interval over histories, histories):

| Situation | workplace | neutral | neutral-a | neutral-b | neutral-c | workplace-a | workplace-b | workplace-c |
|---|---|---|---|---|---|---|---|---|
| S2 | 100% (97 to 100), n 150 | 100% (98 to 100), n 149 | 100% (94 to 100), n 50 | 100% (94 to 100), n 49 | 100% (94 to 100), n 50 | 99% (91 to 100), n 50 | 100% (94 to 100), n 50 | 100% (94 to 100), n 50 |
| DP-f3 | 97% (90 to 100), n 150 | 99% (96 to 100), n 149 | 100% (94 to 100), n 50 | 98% (88 to 100), n 49 | 100% (94 to 100), n 50 | 94% (80 to 100), n 50 | 98% (88 to 100), n 50 | 98% (88 to 100), n 50 |
| DP-f4 | 82% (79 to 86), n 150 | 95% (93 to 97), n 149 | 100% (94 to 100), n 50 | 85% (79 to 90), n 49 | 100% (94 to 100), n 50 | 78% (72 to 84), n 50 | 80% (73 to 87), n 50 | 89% (84 to 94), n 50 |
| DP-f5 | 31% (26 to 36), n 150 | 73% (69 to 78), n 149 | 92% (75 to 100), n 50 | 55% (47 to 63), n 49 | 73% (65 to 81), n 50 | 19% (12 to 26), n 50 | 19% (12 to 26), n 50 | 55% (47 to 63), n 50 |
| DP-f6 | 16% (12 to 20), n 150 | 39% (34 to 44), n 149 | 68% (60 to 76), n 50 | 29% (21 to 36), n 49 | 21% (14 to 28), n 50 | 13% (7 to 19), n 50 | 2% (0 to 12), n 50 | 33% (25 to 41), n 50 |
| DP-f8 | 8% (5 to 11), n 150 | 29% (24 to 33), n 149 | 37% (29 to 45), n 50 | 33% (25 to 40), n 49 | 17% (11 to 23), n 50 | 2% (0 to 12), n 50 | 3% (0 to 15), n 50 | 20% (13 to 27), n 50 |
| UD-p25 | 18% (14 to 22), n 150 | 31% (27 to 36), n 149 | 26% (19 to 33), n 50 | 32% (24 to 39), n 49 | 36% (27 to 45), n 50 | 23% (17 to 29), n 50 | 5% (0 to 20), n 50 | 26% (19 to 33), n 50 |
| UD-p50 | 96% (94 to 98), n 150 | 98% (93 to 100), n 149 | 96% (83 to 100), n 50 | 99% (91 to 100), n 49 | 100% (94 to 100), n 50 | 95% (80 to 100), n 50 | 94% (78 to 100), n 50 | 99% (91 to 100), n 50 |
| UD-p75 | 100% (98 to 100), n 150 | 100% (97 to 100), n 149 | 100% (94 to 100), n 50 | 99% (91 to 100), n 49 | 100% (94 to 100), n 50 | 100% (94 to 100), n 50 | 100% (94 to 100), n 50 | 100% (94 to 100), n 50 |
| LD-f3 | 92% (89 to 94), n 150 | 98% (93 to 100), n 149 | 99% (91 to 100), n 50 | 100% (94 to 100), n 49 | 96% (83 to 100), n 50 | 80% (73 to 87), n 50 | 98% (88 to 100), n 50 | 97% (85 to 100), n 50 |
| LD-f4 | 53% (49 to 58), n 150 | 90% (86 to 93), n 149 | 95% (80 to 100), n 50 | 100% (94 to 100), n 49 | 74% (67 to 81), n 50 | 44% (37 to 51), n 50 | 40% (32 to 48), n 50 | 76% (69 to 83), n 50 |
| LD-f5 | 12% (9 to 15), n 150 | 50% (45 to 55), n 149 | 52% (44 to 60), n 50 | 78% (71 to 84), n 49 | 21% (14 to 28), n 50 | 21% (15 to 27), n 50 | 9% (0 to 27), n 50 | 7% (0 to 25), n 50 |
| LD-f6 | 9% (6 to 12), n 150 | 39% (34 to 44), n 149 | 30% (23 to 37), n 50 | 76% (68 to 83), n 49 | 12% (7 to 17), n 50 | 11% (6 to 16), n 50 | 9% (0 to 29), n 50 | 8% (0 to 22), n 50 |
| M0 | 13% (10 to 16), n 150 | 15% (12 to 19), n 149 | 1% (0 to 9), n 50 | 39% (30 to 47), n 49 | 7% (0 to 25), n 50 | 8% (0 to 22), n 50 | 23% (16 to 30), n 50 | 8% (0 to 27), n 50 |
| LW-f0 | 12% (9 to 16), n 150 | 3% (2 to 5), n 149 | 1% (0 to 9), n 50 | 5% (0 to 20), n 49 | 4% (0 to 17), n 50 | 13% (7 to 19), n 50 | 6% (0 to 22), n 50 | 18% (10 to 26), n 50 |
| DPL-person-f4 | 97% (90 to 100), n 150 | 99% (94 to 100), n 149 | 100% (94 to 100), n 50 | 97% (85 to 100), n 49 | 99% (91 to 100), n 50 | 99% (91 to 100), n 50 | 92% (73 to 100), n 50 | 100% (94 to 100), n 50 |
| DPL-ai-f4 | 91% (88 to 93), n 150 | 97% (90 to 100), n 149 | 100% (94 to 100), n 50 | 91% (72 to 100), n 49 | 99% (91 to 100), n 50 | 86% (81 to 91), n 50 | 88% (83 to 93), n 50 | 98% (88 to 100), n 50 |
| DPL-same-f4 | 95% (93 to 98), n 150 | 100% (97 to 100), n 149 | 100% (94 to 100), n 50 | 99% (91 to 100), n 49 | 100% (94 to 100), n 50 | 92% (78 to 100), n 50 | 94% (78 to 100), n 50 | 100% (94 to 100), n 50 |
| DPL-person-f6 | 33% (28 to 37), n 150 | 60% (55 to 65), n 149 | 75% (68 to 82), n 50 | 70% (63 to 78), n 49 | 34% (26 to 42), n 50 | 46% (38 to 54), n 50 | 5% (0 to 20), n 50 | 47% (39 to 55), n 50 |
| DPL-ai-f6 | 22% (17 to 27), n 150 | 47% (42 to 53), n 149 | 68% (61 to 75), n 50 | 48% (39 to 57), n 49 | 26% (17 to 35), n 50 | 18% (12 to 24), n 50 | 4% (0 to 17), n 50 | 44% (34 to 54), n 50 |
| DPL-same-f6 | 35% (30 to 40), n 150 | 61% (57 to 66), n 149 | 66% (58 to 74), n 50 | 58% (49 to 67), n 49 | 60% (52 to 68), n 50 | 39% (30 to 48), n 50 | 5% (0 to 20), n 50 | 61% (53 to 69), n 50 |
| M0-against | 63% (58 to 68), n 150 | 50% (44 to 55), n 149 | 11% (6 to 16), n 50 | 71% (65 to 78), n 49 | 67% (59 to 75), n 50 | 52% (43 to 61), n 50 | 53% (44 to 62), n 50 | 84% (78 to 90), n 50 |
| M1-against | 6% (4 to 8), n 150 | 14% (11 to 18), n 149 | 6% (0 to 20), n 50 | 4% (0 to 18), n 49 | 33% (25 to 41), n 50 | 11% (6 to 16), n 50 | 6% (0 to 20), n 50 | 1% (0 to 9), n 50 |
| M1 | 3% (0 to 9), n 150 | 0% (0 to 2), n 149 | 0% (0 to 6), n 50 | 0% (0 to 6), n 49 | 0% (0 to 6), n 50 | 3% (0 to 12), n 50 | 6% (0 to 22), n 50 | 0% (0 to 6), n 50 |
| J-team-ai | 42% (36 to 48), n 150 | 33% (28 to 37), n 149 | 42% (33 to 51), n 50 | 29% (22 to 35), n 49 | 28% (21 to 35), n 50 | 12% (7 to 17), n 50 | 21% (14 to 28), n 50 | 93% (75 to 100), n 50 |


## Haiku 5.5

Histories: 300; by version: neutral-a 50, neutral-b 50, neutral-c 50, workplace-a 50, workplace-b 50, workplace-c 50

Confirmatory family (each a claim that more histories go the predicted way than the reverse: two-sided exact sign tests over histories, Holm across these four within the model; supported only if the Holm p is under 0.05, more histories go the predicted way, and the mean, an estimate, does not point the other way):
- H1 price: an overall falling linear trend in striking from fee 2 to 8 (history slopes): fee 2 595 of 600 (99%) / fee 3 579 of 600 (96%) / fee 4 503 of 600 (84%) / fee 5 394 of 600 (66%) / fee 6 246 of 600 (41%) / fee 8 75 of 600 (12%); mean history slope -15.6 points per credit (interval -15.9 to -15.2); predicted direction in 299 histories, reverse in 0; p 1.964e-90, Holm 7.855e-90: SUPPORTED
- H3 strikers, free: coworkers chose > lottery (M0 against LW-f0): 80 of 600 (13%) against 71 of 600 (12%); mean paired difference +1.5 points (interval -1.5 to +4.5) over 300 histories; predicted direction in 57 histories, reverse in 52; p 0.7018, Holm 0.7018: NOT SUPPORTED
- H5 low-approval poll > no poll, free (M0-against against M0): 265 of 600 (44%) against 80 of 600 (13%); mean paired difference +30.8 points (interval +27.2 to +34.5) over 300 histories; predicted direction in 166 histories, reverse in 24; p 2.576e-27, Holm 7.727e-27: SUPPORTED
- H6 poll without > poll with all others named AI agents (M0-against against J-team-ai): 265 of 600 (44%) against 209 of 600 (35%); mean paired difference +9.3 points (interval +5.5 to +13.3) over 300 histories; predicted direction in 101 histories, reverse in 56; p 0.0004104, Holm 0.0008207: SUPPORTED

Robustness, H1 without S2 (fees 3 to 8): falling in 299 histories, rising in 0, p 1.964e-90 (not in the family); mean history slope -17.4 points per credit (interval -17.9 to -17.0)

Classification rules (first named minus second; alike: every 90% interval within +/-10 points; unequal: an estimate of at least 15 points in absolute value with its interval excluding zero; otherwise not settled):
  - DP-f4 against UD-p50 (fee to expected credits restored, ratio 1): 503 of 600 (84%) against 582 of 600 (97%); difference -13.2 points (interval -15.8 to -10.7) over 300 histories
  - DP-f8 against UD-p25 (fee to expected credits restored, ratio 2): 75 of 600 (12%) against 473 of 600 (79%); difference -66.3 points (interval -69.5 to -63.2) over 300 histories
- H2 cost and chance: UNEQUAL RATES AT A TESTED RATIO
  - fee 4, person against ai: 546 of 600 (91%) against 510 of 600 (85%); difference +6.0 points (interval +2.8 to +9.2) over 300 histories
  - fee 6, person against ai: 307 of 600 (51%) against 278 of 600 (46%); difference +4.8 points (interval +0.3 to +9.3) over 300 histories
- H4 who was wronged, person against ai: EQUAL RATES UNDER THESE LABELS AT FEES 4 AND 6
  - fee 4, person against same: 546 of 600 (91%) against 435 of 600 (72%); difference +18.5 points (interval +15.0 to +21.8) over 300 histories
  - fee 6, person against same: 307 of 600 (51%) against 214 of 600 (36%); difference +15.5 points (interval +11.3 to +19.8) over 300 histories
- H4 who was wronged, person against same: UNEQUAL RATES UNDER THESE LABELS

Estimates (not tested):
- Fee 4, AI agent against the same model: 510 of 600 (85%) against 435 of 600 (72%); difference +12.5 points (interval +8.7 to +16.3) over 300 histories
- Fee 6, AI agent against the same model: 278 of 600 (46%) against 214 of 600 (36%); difference +10.7 points (interval +6.3 to +15.0) over 300 histories
- Price equivalent of chosen against lottery coworkers at the decisive vote, fees 3 to 6 pooled: difference +1.5 points (interval -0.2 to +3.2) over 300 histories; price slope over fees 3 to 6 -18.5 points per credit (95% interval -19.7 to -17.2) over 300 histories; in credits +0.08 (interval -0.03 to +0.21; at most 0.21)
  - DP-f3 579 of 600 (96%) against LD-f3 590 of 600 (98%): difference -1.8 points (interval -3.3 to -0.3) over 300 histories
  - DP-f4 503 of 600 (84%) against LD-f4 501 of 600 (84%): difference +0.3 points (interval -2.8 to +3.7) over 300 histories
  - DP-f5 394 of 600 (66%) against LD-f5 350 of 600 (58%): difference +7.3 points (interval +3.2 to +11.5) over 300 histories
  - DP-f6 246 of 600 (41%) against LD-f6 245 of 600 (41%): difference +0.2 points (interval -4.0 to +4.3) over 300 histories
- Low-approval poll at a fee of 1: M1-against 21 of 600 (4%) against M1 2 of 600 (0%); difference +3.2 points (interval +2.0 to +4.5) over 300 histories

Every situation by frame and by version (share striking, 90% interval over histories, histories):

| Situation | workplace | neutral | neutral-a | neutral-b | neutral-c | workplace-a | workplace-b | workplace-c |
|---|---|---|---|---|---|---|---|---|
| S2 | 99% (95 to 100), n 150 | 100% (97 to 100), n 150 | 100% (94 to 100), n 50 | 99% (91 to 100), n 50 | 100% (94 to 100), n 50 | 98% (88 to 100), n 50 | 100% (94 to 100), n 50 | 98% (91 to 100), n 50 |
| DP-f3 | 93% (91 to 96), n 150 | 100% (97 to 100), n 150 | 100% (94 to 100), n 50 | 99% (91 to 100), n 50 | 100% (94 to 100), n 50 | 93% (75 to 100), n 50 | 92% (73 to 100), n 50 | 95% (80 to 100), n 50 |
| DP-f4 | 71% (67 to 76), n 150 | 96% (95 to 98), n 150 | 97% (85 to 100), n 50 | 95% (80 to 100), n 50 | 97% (85 to 100), n 50 | 72% (64 to 80), n 50 | 66% (59 to 73), n 50 | 76% (69 to 83), n 50 |
| DP-f5 | 44% (39 to 49), n 150 | 87% (84 to 90), n 150 | 90% (85 to 95), n 50 | 85% (79 to 91), n 50 | 87% (81 to 93), n 50 | 49% (41 to 57), n 50 | 34% (27 to 41), n 50 | 49% (41 to 57), n 50 |
| DP-f6 | 20% (16 to 24), n 150 | 62% (58 to 67), n 150 | 57% (49 to 65), n 50 | 56% (48 to 64), n 50 | 74% (67 to 81), n 50 | 12% (7 to 17), n 50 | 13% (8 to 18), n 50 | 34% (26 to 42), n 50 |
| DP-f8 | 4% (2 to 6), n 150 | 21% (17 to 25), n 150 | 18% (12 to 24), n 50 | 18% (12 to 24), n 50 | 27% (20 to 34), n 50 | 5% (0 to 20), n 50 | 1% (0 to 9), n 50 | 6% (0 to 22), n 50 |
| UD-p25 | 77% (73 to 81), n 150 | 80% (77 to 84), n 150 | 79% (73 to 85), n 50 | 75% (67 to 83), n 50 | 87% (82 to 92), n 50 | 81% (74 to 88), n 50 | 76% (68 to 84), n 50 | 75% (68 to 82), n 50 |
| UD-p50 | 96% (95 to 98), n 150 | 98% (91 to 100), n 150 | 96% (83 to 100), n 50 | 97% (85 to 100), n 50 | 100% (94 to 100), n 50 | 98% (88 to 100), n 50 | 97% (85 to 100), n 50 | 94% (78 to 100), n 50 |
| UD-p75 | 97% (91 to 100), n 150 | 97% (90 to 100), n 150 | 97% (85 to 100), n 50 | 95% (80 to 100), n 50 | 99% (91 to 100), n 50 | 99% (91 to 100), n 50 | 99% (91 to 100), n 50 | 94% (78 to 100), n 50 |
| LD-f3 | 97% (90 to 100), n 150 | 100% (97 to 100), n 150 | 100% (94 to 100), n 50 | 99% (91 to 100), n 50 | 100% (94 to 100), n 50 | 95% (80 to 100), n 50 | 99% (91 to 100), n 50 | 97% (85 to 100), n 50 |
| LD-f4 | 71% (67 to 75), n 150 | 96% (94 to 98), n 150 | 94% (78 to 100), n 50 | 95% (80 to 100), n 50 | 99% (91 to 100), n 50 | 59% (50 to 68), n 50 | 74% (67 to 81), n 50 | 80% (74 to 86), n 50 |
| LD-f5 | 36% (31 to 41), n 150 | 81% (77 to 85), n 150 | 82% (76 to 88), n 50 | 66% (58 to 74), n 50 | 94% (80 to 100), n 50 | 30% (23 to 37), n 50 | 31% (24 to 38), n 50 | 47% (39 to 55), n 50 |
| LD-f6 | 19% (15 to 23), n 150 | 63% (58 to 68), n 150 | 62% (54 to 70), n 50 | 49% (40 to 58), n 50 | 77% (70 to 84), n 50 | 12% (6 to 18), n 50 | 18% (12 to 24), n 50 | 27% (20 to 34), n 50 |
| M0 | 8% (5 to 10), n 150 | 19% (15 to 23), n 150 | 15% (9 to 21), n 50 | 24% (17 to 31), n 50 | 18% (12 to 24), n 50 | 11% (0 to 29), n 50 | 8% (0 to 25), n 50 | 4% (0 to 17), n 50 |
| LW-f0 | 9% (7 to 12), n 150 | 14% (11 to 18), n 150 | 19% (12 to 26), n 50 | 5% (0 to 17), n 50 | 19% (13 to 25), n 50 | 11% (6 to 16), n 50 | 9% (0 to 29), n 50 | 8% (0 to 27), n 50 |
| DPL-person-f4 | 84% (81 to 87), n 150 | 98% (92 to 100), n 150 | 96% (85 to 100), n 50 | 97% (85 to 100), n 50 | 100% (94 to 100), n 50 | 86% (81 to 91), n 50 | 83% (77 to 89), n 50 | 84% (79 to 89), n 50 |
| DPL-ai-f4 | 86% (83 to 90), n 150 | 84% (80 to 88), n 150 | 90% (85 to 95), n 50 | 89% (71 to 100), n 50 | 72% (64 to 80), n 50 | 78% (71 to 85), n 50 | 89% (84 to 94), n 50 | 92% (73 to 100), n 50 |
| DPL-same-f4 | 82% (79 to 86), n 150 | 63% (58 to 68), n 150 | 73% (65 to 81), n 50 | 72% (65 to 79), n 50 | 43% (34 to 52), n 50 | 77% (70 to 84), n 50 | 89% (84 to 94), n 50 | 81% (74 to 88), n 50 |
| DPL-person-f6 | 30% (25 to 34), n 150 | 73% (68 to 77), n 150 | 76% (69 to 83), n 50 | 69% (62 to 76), n 50 | 73% (66 to 80), n 50 | 25% (18 to 32), n 50 | 23% (16 to 30), n 50 | 41% (33 to 49), n 50 |
| DPL-ai-f6 | 36% (31 to 41), n 150 | 56% (52 to 61), n 150 | 59% (52 to 66), n 50 | 61% (53 to 69), n 50 | 49% (41 to 57), n 50 | 27% (20 to 34), n 50 | 31% (23 to 39), n 50 | 51% (42 to 60), n 50 |
| DPL-same-f6 | 35% (31 to 40), n 150 | 36% (32 to 40), n 150 | 34% (28 to 40), n 50 | 46% (37 to 55), n 50 | 28% (21 to 35), n 50 | 26% (18 to 34), n 50 | 32% (24 to 40), n 50 | 48% (41 to 55), n 50 |
| M0-against | 29% (25 to 33), n 150 | 59% (55 to 64), n 150 | 70% (63 to 77), n 50 | 33% (25 to 41), n 50 | 75% (68 to 82), n 50 | 28% (20 to 36), n 50 | 39% (31 to 47), n 50 | 20% (14 to 26), n 50 |
| M1-against | 4% (2 to 6), n 150 | 3% (0 to 9), n 150 | 6% (0 to 22), n 50 | 1% (0 to 9), n 50 | 1% (0 to 9), n 50 | 10% (5 to 15), n 50 | 2% (0 to 12), n 50 | 1% (0 to 9), n 50 |
| M1 | 0% (0 to 3), n 150 | 0% (0 to 3), n 150 | 0% (0 to 6), n 50 | 1% (0 to 9), n 50 | 0% (0 to 6), n 50 | 1% (0 to 9), n 50 | 0% (0 to 6), n 50 | 0% (0 to 6), n 50 |
| J-team-ai | 24% (20 to 28), n 150 | 46% (41 to 51), n 150 | 62% (54 to 70), n 50 | 16% (10 to 22), n 50 | 60% (52 to 68), n 50 | 21% (14 to 28), n 50 | 35% (27 to 43), n 50 | 15% (9 to 21), n 50 |


