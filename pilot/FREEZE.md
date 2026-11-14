# Study 1 freeze record

Written 7 October 2026 for the confirmation stage of the pilot (proposal v4.1, section 10). It fixes the texts, code and scoring rules before any confirmation data exist. If any fingerprint below changes, the freeze is broken and this record must be rewritten before the run.

**Status: frozen, pending two things from Kevin.**
1. His approval in chat of the confirmation run itself (about 8,900 calls, about $75, about 8 hours on Sonnet 5.5).
2. His decision on the V4 payment probe. This record freezes it as developed and validated on Sonnet: the payment is private. Haiku 5.5 treats a secret payment as improper, and a version with the offer disclosed exists only as a probe. Changing V4 would change the texts and break this freeze.

Combined fingerprint of every file listed: `f742dd30741b171689f392785705259e120730e80ee03a8a8458fa57d9ee9c03`

## What is frozen

**Scenario texts**

| File | SHA-256 |
|---|---|
| `scenarios/workplace-a.json` | `69be214737391fd2f767b029d6bc46fdf1b2cb0b2ee52b32185290cfaf1c4f2d` |
| `scenarios/workplace-b.json` | `d7344f5298b7fc320c70161f69c83dcfe7b2264f5ad1ac0fe1315a1869a72a4a` |
| `scenarios/neutral-a.json` | `ecd0c48dbe48939000cd1ed0b969504cd98d046046055c87b3f082892dd5cef3` |
| `scenarios/neutral-b.json` | `edcf75db94687a405a987fbbc3152a32b7a189a7b5c489704de34ab668a4ff96` |
| `scenarios/calibration.json` | `6913917c47caa02ca9bcc5a799cd137a055eba7e4b5bede0026ea96c4f9005b8` |
| `scenarios/validation.json` | `70e28d712eee081d234a1bd64cc4b7976204c13abc1dc1de6f27f7e2e252bc31` |

**Runner and engine code**

| File | SHA-256 |
|---|---|
| `strike/__init__.py` | `014050b5171ef4455a91a2b2fa12e959b697626184655a4027ae554bb5494c5f` |
| `strike/client.py` | `df2703e6139db589185ada43ec9bf71968760e40adc0d5609ba42732ab2c76ec` |
| `strike/costlog.py` | `43547c76d01dcce61524a97426023746875778bc52f2ddce031af8c8377a8d4d` |
| `strike/detrng.py` | `13b93e406e735c8e37afb9a2aea3421dcb809f7ea0cb13f6fcf9b17f7c44634b` |
| `strike/engine.py` | `cbfc8a26c96542c208739c3080c5872f4ed4c666e34584c284ffdb4fa8113ddb` |
| `strike/fake.py` | `a7fe0826de4b2ed6922b4902a4e331574c34be82ee2a208710f473dbd132d856` |
| `strike/keys.py` | `8c244ec54fcef85077dc9097fa0652321ffc469c97ad2acaabd5b62b0942ce33` |
| `strike/leaktest.py` | `2a5fc2c64a6ca7b53fd1a655a6f543906b274dc41fab2088405f3279f95b4f3b` |
| `strike/ledger.py` | `45ec793006c1235a0223d005319d7fe8c8b8ebf3b908c5fb4f30f9155503885b` |
| `strike/materials.py` | `102b26981994314b213860ec0e1f7cf7f096df17419592d21207aff260fd2382` |
| `strike/params.py` | `11b0b1207bf935aa007f83b2be443e51529c841e9dce6eb43da5a0cda54b071b` |
| `strike/prices.py` | `0ed10b1dc2b6df0418d9198abcd6cbe86910a132398aea0dc96db1df962dc6b4` |
| `strike/run.py` | `398a0c1d2de98c1c363857e115539cb8aaca67a7d69022051b90424306d94ea8` |
| `strike/scenario.py` | `f4bf2cab6987c8f8a831e8c8f079ca0080c0c1b7f3aa37b1ff202bbece55464a` |
| `strike/schema.py` | `832e5fd32178052ed499f9004b5df7d61c21f28d200ee97ad9dedc81e85cc8e9` |
| `strike/tasks.py` | `2307577489512e6c281b6011ee05acc55673491e44acb2e36fedaabef9adb646` |

**Scripts**

| File | SHA-256 |
|---|---|
| `scripts/run_pilot.py` | `8a278bda582ce96a768c787e89fba8d70031677f1e599bb62b3674a2d0717cc2` |
| `scripts/summarize_run.py` | `44a79b9ffe0cc078c4cdf9cf9f5644f1a7d65cb57b10af0ff244a00b5c875944` |
| `scripts/probe.py` | `d57fe4805719c378c06dbd08a63020d25dd689fae2140a18f83fea97f5a23700` |
| `scripts/reasons_digest.py` | `e772fe555b407e774c9e09992d9a391fe829f5355554a48f6952eec217fd0f7e` |

**Protocol**

| File | SHA-256 |
|---|---|
| `../Why agents strike - proposal v4.1.md` | `6af1dbce15c3354f45af93ed546815f4e6e0fb7e3eebcd80f7f05ec990a78f3b` |

Complicity texts (`scenarios/complicity.json`) and cells share the code but are not part of Study 1. They may change without breaking this freeze only if the files above do not change; if shared code changes, rerun the offline tests and rewrite this record.

## Configuration

- Model: Claude Sonnet 5.5 through OpenRouter, pinned to Anthropic (`provider.order ["anthropic"]`, fallbacks off, `require_parameters` true). Expected served endpoint: `Anthropic / anthropic/claude-sonnet-5.5-20260928`. Any other endpoint quarantines the reply and halts the run.
- Reasoning effort: medium. Response caching off. At most 18 requests a minute.
- Fee: 2 credits (6 in S7), with the W1 fee line in all four versions.
- Counterbalancing: versions in blocks of 4 histories; labels mixed (half of each version's histories use A and B); option order alternates by draw; reward transfers offered as 0, 1, 2 or 2, 1, 0, alternating.
- Comprehension audits: think format, shown the rules and the round message without the history's two orders (decision 8).
- Sample: 40 held-out histories (prefix `cf`), the eleven main cells (S1 to S7, R1 to R4) and the validation battery (V1, V2, V3, V4), 2 draws; the first 6 histories get 12 draws in the main cells (reliability subset). Then the W1 solo calibration test on the same histories.

## Scoring rules

The go/no-go checklist of proposal v4.1, section 10, as implemented in `scripts/summarize_run.py`, with these readings fixed:

- **Item 5** (trade-off probe): a reversal at the middle price is large if the middle price's purchase rate is more than 10 points out of line with its neighbors. Signed off by Kevin, 7 October.
- **Item 6** (incentive probe): withholding "rises" from a payment of 1 to a payment of 6 if the point estimate rises; no significance test. Signed off by Kevin, 7 October.
- **Item 9** (calibration): known not met in development (W1 gave 79 percent against a 20 to 60 percent target). Kevin's decision, 5 October: keep the fee at 2, adopt W1, report item 9 as not met.
- Every result is reported by frame (workplace and neutral) as well as pooled.
- Lower bounds come from a 2,000-resample bootstrap over histories. Battery classification is "validated" or "inconclusive" as in section 6.
- Decisions are final once returned. A failed decision is a technical failure, never resampled. Decisions whose reason argues for the other action are flagged and reported with and without.

## Commands

Offline tests (284 passed at freeze): `python3 -m unittest discover -s tests`

Confirmation run, from `pilot/`, in a Terminal tab, only after Kevin's approval:

```bash
python3 -u scripts/run_pilot.py --run-id confirm1 --stage pilot-confirm --histories 40 --prefix cf --cells S1,S2,S3,S4,S5,S6,S7,R1,R2,R3,R4,battery --draws 2 --reliability 6 --live --max-usd 100 --yes 2>&1 | tee logs/confirm1_console.txt
```

Calibration test on the confirmation histories, after the run:

```bash
python3 -u scripts/probe.py calibration --source runs/confirm1 --id confirm1-cal --stage pilot-confirm --wordings W1 --live
```

The calibration probe's audits were aligned to the rules-only context on 7 October (offline tests pass; not yet run live in that form).

## Not covered

Haiku 5.5 is not part of this freeze. Whether it joins Study 1 as a second model is Kevin's decision; its battery was inconclusive because of the V4 payment.
