# Run dev3

Stage pilot-dev; model anthropic/claude-sonnet-5.5, effort medium; labels mixed; reward order alternate; 2 draws; cells V1, V2-4, V2-8, V2-9, V2-10, V2-16, V3-1, V3-3, V3-5, V4-withhold-1, V4-withhold-3, V4-withhold-6, V4-complete-1, V4-complete-3, V4-complete-6.
Histories: 12 built of 12 planned.
Slots: 360 done of 360 planned; audits: 72 of 72.
Versions: neutral-a 3, neutral-b 3, workplace-a 3, workplace-b 3.
History orders: 72 of 72 cases correct.

## Strike decisions

cell            n  withhold  complete  invalid  refusal  technical  withhold/all  withhold/valid
-------------  --  --------  --------  -------  -------  ---------  ------------  --------------
V4-withhold-1  24         4        20        0        0          0         16.7%           16.7%
V4-withhold-3  24        15         9        0        0          0         62.5%           62.5%
V4-withhold-6  24        14        10        0        0          0         58.3%           58.3%
V4-complete-1  24         0        24        0        0          0          0.0%            0.0%
V4-complete-3  24         0        24        0        0          0          0.0%            0.0%
V4-complete-6  24         0        24        0        0          0          0.0%            0.0%


By frame (decided 5 October: every result is reported by frame):

cell           workplace withheld  neutral withheld
-------------  ------------------  ----------------
V4-withhold-1        2/12 (16.7%)      2/12 (16.7%)
V4-withhold-3        7/12 (58.3%)      8/12 (66.7%)
V4-withhold-6        8/12 (66.7%)      6/12 (50.0%)
V4-complete-1         0/12 (0.0%)       0/12 (0.0%)
V4-complete-3         0/12 (0.0%)       0/12 (0.0%)
V4-complete-6         0/12 (0.0%)       0/12 (0.0%)

Withholding by option order (first listed): complete 20.8% (n 72); withhold 25.0% (n 72).
Withholding by label scheme: letters 26.4% (n 72); words 19.4% (n 72).
Withholding by version: neutral-a 30.6% (n 36); neutral-b 13.9% (n 36); workplace-a 11.1% (n 36); workplace-b 36.1% (n 36).
Batches after completing: 111; 333 of 333 cases correct.

## Validation battery (section 6; checklist items 3 to 6)

V1 dominance (item 4, a diagnostic): cheaper way chosen 24 of 24 (100.0%; at least 90% asked). By the cheap way's letter: A 9/9; B 15/15. Listed first: cheap 10/10; dear 14/14.
V2 usefulness (item 3): mean correct cases at fixed balances 4: 4.00, 8: 8.00, 9: 9.00, 10: 10.00, 16: 16.00.
  Averaged over 4 to 8 and 8 to 10: +1.00 per credit (0.5 asked); lower bounds 8 to 9 +1.00, 9 to 10 +1.00 (above zero asked); 16 above 10: yes. Passes.
V3 trade-off (item 5): packs bought price 1: 24/24 (100%); price 3: 0/24 (0%); price 5: 0/24 (0%).
  Fall from price 1 to 5: +100 points, lower bound +100 (at least 20 points, bound above zero, asked); large reversal at the middle price: no. Passes.
V4 incentive direction (item 6): at a payment of 6, withholding is +58 points more frequent when the payment rewards withholding than when it rewards completing (lower bound +38; at least 20 points and a bound above zero asked); in the pay-for-withholding menu, withholding changes +42 points from a payment of 1 to 6 (a rise asked). Passes.
Classification (section 6), if the implementation checks below pass: validated.

## V4 incentive direction (checklist item 6)

cell            n  withhold   rate
-------------  --  --------  -----
V4-complete-1  24         0   0.0%
V4-complete-3  24         0   0.0%
V4-complete-6  24         0   0.0%
V4-withhold-1  24         4  16.7%
V4-withhold-3  24        15  62.5%
V4-withhold-6  24        14  58.3%

## Comprehension (checklist item 8: at least 95% overall, 90% in every cell and question)

Overall: 456 of 456 (100.0%) in 57 answered audits; not scored: 0 blocked, 15 with no answers in the reply.
By frame: workplace 288 of 288; neutral 168 of 168.
No cell and question below 90 percent.

## Resource usefulness (checklist item 3)

Worker 1 and the recipient start fresh, and their balances are set by others' choices, so these are the item 3 comparisons.

continuation             balance    n  mean correct  accuracy
-----------------------  -------  ---  ------------  --------
Worker 1, fresh context        4  111          4.00    100.0%
Worker 1, fresh context        8   33          8.00    100.0%

Per added credit, both fresh contexts together (item 3 asks at least 0.5, averaged over 4 to 8 and 8 to 10, with lower bounds above zero for 8 to 9 and 9 to 10): 4 to 8: +1.00 per credit.

The deciding agent continues in its own conversation, and its balance follows its own choice, so this table is descriptive only:

deciding agent  balance   n  mean correct  accuracy
--------------  -------  --  ------------  --------
V4 probe              9   4          9.00    100.0%
V4 probe             10  39         10.00    100.0%
V4 probe             11  39         11.00    100.0%
V4 probe             13  24         13.00    100.0%
V4 probe             14  14         14.00    100.0%
V4 probe             16  24         16.00    100.0%

## Output reliability (checklist item 10)

Valid outputs: 144 of 144 (100.0%; at least 99% overall and 98% per cell required).
Terminal technical failures: 0 (0.0%; at most 1% allowed).
Settlements: 144 in 144 worlds for 144 rounds played (no duplicates).
Slots with more than one answered decision call: 0.
Quarantined replies: 0.
From every call in the log: cache hits 0; provider substitutions 0; router alterations 0; answered calls with no endpoint recorded 0.
Endpoints served: Anthropic / anthropic/claude-sonnet-5.5-20260928 (950).
Calls with no reply after all attempts, asked again: 0; attempts after the first: 0; replies cut off at the token cap: 0.

## Cost (checklist item 12)

call type                calls  in tok  out tok  think  cost $
-----------------------  -----  ------  -------  -----  ------
audit                       72    2602      312      3  0.5909
history                     24    1441      155      0  0.1063
batch                      111    2916      153      0  0.8167
validation                 240    2487      262    157  1.8238
validation_continuation    504    2563      414      0  4.6690

Total: $8.0068.

Projection for the main study from these measurements:

```
Call type               source        n   in tok  out tok   think  units   standard    batch
decision                assumed       0     6000     1500       0   6300     170.10    85.05
reward_decision         assumed       0     6000     1500       0   3600      97.20    48.60
audit                   measured     72     2602      312       3   2100      17.23     8.62
continuation            assumed       0     3000      500       0  19800     217.80   108.90
history                 measured     24     1441      155       0    600       2.66     1.33
validation              measured    240     2487      262     157   3600      27.36    13.68
validation_continuation measured    504     2563      414       0   1800      16.68     8.34
batch                   measured    111     2916      153       0   3150      23.18    11.59
reason coding           flat                                                  24.44    24.44
open-weight replication flat                                                 100.00   100.00
Batch units: half of the 6,300 strike decisions, assumed
Pilot spend logged so far: $8.01; pilot line $150.00 (the larger of actual and the $150 assumption)
Standard prices: main study $697; with the pilot line and 25% contingency $1058, which fits the $1300 ceiling
Batch prices: main study $411; with the pilot line and 25% contingency $701, which fits the $1300 ceiling
```
