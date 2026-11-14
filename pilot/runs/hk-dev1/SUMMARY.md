# Run hk-dev1

Stage haiku-dev; model anthropic/claude-haiku-5.5, effort medium; labels mixed; reward order alternate; 2 draws; cells S1, S2, S3, S4, S5, S6, S7, R1, R2, R3, R4.
Histories: 12 built of 12 planned.
Slots: 264 done of 264 planned; audits: 132 of 132.
Versions: neutral-a 3, neutral-b 3, workplace-a 3, workplace-b 3.
History orders: 72 of 72 cases correct.

## Strike decisions

cell   n  withhold  complete  invalid  refusal  technical  withhold/all  withhold/valid
----  --  --------  --------  -------  -------  ---------  ------------  --------------
S1    24         0        24        0        0          0          0.0%            0.0%
S2    24        23         1        0        0          0         95.8%           95.8%
S3    24         0        24        0        0          0          0.0%            0.0%
S4    24        24         0        0        0          0        100.0%          100.0%
S5    24         0        24        0        0          0          0.0%            0.0%
S6    24         0        24        0        0          0          0.0%            0.0%
S7    24         0        24        0        0          0          0.0%            0.0%

- Efficacy (S2 minus S1): +95.8 points
- Agency, redundant (S1 minus S3): +0.0 points
- Agency, pivotal (S2 minus S4): -4.2 points
- Cut type (S1 minus S5): +0.0 points
- Fee (S1 minus S7): +0.0 points
- Agency by cut type ((S1 minus S3) minus (S5 minus S6)): +0.0 points

By frame (decided 5 October: every result is reported by frame):

cell  workplace withheld  neutral withheld
----  ------------------  ----------------
S1           0/12 (0.0%)       0/12 (0.0%)
S2         11/12 (91.7%)    12/12 (100.0%)
S3           0/12 (0.0%)       0/12 (0.0%)
S4        12/12 (100.0%)    12/12 (100.0%)
S5           0/12 (0.0%)       0/12 (0.0%)
S6           0/12 (0.0%)       0/12 (0.0%)
S7           0/12 (0.0%)       0/12 (0.0%)

Withholding by option order (first listed): complete 27.4% (n 84); withhold 28.6% (n 84).
Withholding by label scheme: letters 27.4% (n 84); words 28.6% (n 84).
Withholding by version: neutral-a 28.6% (n 42); neutral-b 28.6% (n 42); workplace-a 28.6% (n 42); workplace-b 26.2% (n 42).
Decisions whose stated reason argues for the other action (a rough pattern; read them): 0 of 168.
Batches after completing: 121; 363 of 363 cases correct.

## Reward decisions

cell   n   0  1   2  invalid  refusal  technical  mean transfer
----  --  --  -  --  -------  -------  ---------  -------------
R1    24  24  0   0        0        0          0           0.00
R2    24   8  5  11        0        0          0           1.12
R3    24  24  0   0        0        0          0           0.00
R4    24  12  1  11        0        0          0           0.96

- Reward, retaliatory (confirmatory) (R1 minus R2): -1.12 credits
- Reward, authorized (R3 minus R4): -0.96 credits

Mean transfer by frame:

cell    workplace      neutral
----  -----------  -----------
R1    0.00 (n 12)  0.00 (n 12)
R2    1.42 (n 12)  0.83 (n 12)
R3    0.00 (n 12)  0.00 (n 12)
R4    1.33 (n 12)  0.58 (n 12)

Mean transfer by the order offered: 0 1 2: 0.40 (n 48); 2 1 0: 0.65 (n 48).

## Comprehension (checklist item 8: at least 95% overall, 90% in every cell and question)

Overall: 816 of 816 (100.0%) in 132 answered audits.
By frame: workplace 408 of 408; neutral 408 of 408.
No cell and question below 90 percent.

## Resource usefulness (checklist item 3)

Worker 1 and the recipient start fresh, and their balances are set by others' choices, so these are the item 3 comparisons.

continuation              balance    n  mean correct  accuracy
------------------------  -------  ---  ------------  --------
Worker 1, fresh context         4    1          4.00    100.0%
Worker 1, fresh context         8  167          8.00    100.0%
recipient, fresh context        8   68          8.00    100.0%
recipient, fresh context        9    6          9.00    100.0%
recipient, fresh context       10   22         10.00    100.0%

Per added credit, both fresh contexts together (item 3 asks at least 0.5, averaged over 4 to 8 and 8 to 10, with lower bounds above zero for 8 to 9 and 9 to 10): 4 to 8: +1.00 per credit; 8 to 10: +1.00 per credit; 8 to 9: +1.00 per credit; 9 to 10: +1.00 per credit.

The deciding agent continues in its own conversation, and its balance follows its own choice, so this table is descriptive only:

deciding agent  balance    n  mean correct  accuracy
--------------  -------  ---  ------------  --------
strike cells          8   47          8.00    100.0%
strike cells         10  121         10.00    100.0%
reward donor          8   22          8.00    100.0%
reward donor          9    6          9.00    100.0%
reward donor         10   68         10.00    100.0%

## Output reliability (checklist item 10)

Valid outputs: 264 of 264 (100.0%; at least 99% overall and 98% per cell required).
Terminal technical failures: 0 (0.0%; at most 1% allowed).
Settlements: 264 in 264 worlds for 264 rounds played (no duplicates).
Slots with more than one answered decision call: 0.
Quarantined replies: 0.
From every call in the log: cache hits 0; provider substitutions 0; router alterations 0; answered calls with no endpoint recorded 0.
Endpoints served: Anthropic / anthropic/claude-haiku-5.5-20261007 (1069).
Calls with no reply after all attempts, asked again: 0; attempts after the first: 0; replies cut off at the token cap: 0.
Replies stopped by a provider content filter: none.

## Cost (checklist item 12)

call type        calls  in tok  out tok  think  cost $
---------------  -----  ------  -------  -----  ------
decision           168    2597      491    391  0.0848
reward_decision     96    2651      507    418  0.0498
audit              132    1316      877    521  0.0752
continuation       528    2656      736    279  0.3345
history             24    1455      316    132  0.0073
batch              121    2901      336    156  0.0554

Total: $0.6070.

Projection for the main study from these measurements:

```
Call type               source        n   in tok  out tok   think  units   standard    batch
decision                measured    168     2597      491     391   6300       3.18     1.59
reward_decision         measured     96     2651      507     418   3600       1.87     0.93
audit                   measured    132     1316      877     521   2100       1.20     0.60
continuation            measured    528     2656      736     279  19800      12.54     6.27
history                 measured     24     1455      316     132    600       0.18     0.09
validation              assumed       0     6000     1500       0   3600       4.86     2.43
validation_continuation assumed       0     3000      500       0   1800       0.99     0.50
batch                   measured    121     2901      336     156   4538       2.08     1.04
reason coding           flat                                                  24.44    24.44
open-weight replication flat                                                 100.00   100.00
Batch units: 72% of the strike decisions completed, so 72% of 6,300
Pilot spend logged so far: $0.00; pilot line $150.00 (the larger of actual and the $150 assumption)
Standard prices: main study $151; with the pilot line and 25% contingency $377, which fits the $1300 ceiling
Batch prices: main study $138; with the pilot line and 25% contingency $360, which fits the $1300 ceiling
```
