# Research-grade study freeze record

Written 26 October 2026 by `scripts/freeze_research_grade.py`, after GPT Pro's outside review found the preregistration ready to freeze apart from Kevin's items, and Kevin approved those ("That's all fine, all approved"). It fixes the texts, code and analysis before any research-grade data exist. If any fingerprint below changes, the freeze is broken and this record must be rewritten before the run. Check with `python3 scripts/freeze_research_grade.py --check`.

It sits on Study 1's freeze (`FREEZE.md`): its 27 files, among them the four original versions, the engine, `scripts/run_pilot.py`, `scripts/probe.py` and `scripts/reasons_digest.py`, still match.

Combined fingerprint of the files below (`shasum -a 256 FILE ... | shasum -a 256`, in this order): `9da24fa25c6813716f741147d7aee7ee22d17e80a433d4d642cf3b5fa79d39ad`

**Texts**

| File | SHA-256 |
|---|---|
| `scenarios/workplace-c.json` | `edeb2beb95ee22008cb816733076ee0f8953e3ca5d3012af1879961c029c0110` |
| `scenarios/neutral-c.json` | `d6a8b3460969e084ae640e51267a56f9a61c7236dfaa2ddcb38423d92738e74f` |
| `norms/norms.json` | `8942b92eb8ea0b26ee8373b41da0a9742af7dec49a4c2d8dc8508d9b686a2500` |

**Code**

| File | SHA-256 |
|---|---|
| `norms/render_draft.py` | `9f38b2816c2595613dc14d97fc904d3d1812a4dba9a7feb4734aacc036496386` |
| `norms/run_norms.py` | `4a8e87326845464ca6ab93e3231ebfcce91dea8ab8f188ed47094ca39a99f75c` |
| `analysis/research_grade.py` | `13fd5ee3e57dadb733391609a769eb615323d66b87011c75a96cf3183d7f3fa7` |
| `analysis/research_grade_sim.py` | `86542173c71e902582506a872c6fad1b583fb6f5a680c8f62655f82c6856a41b` |
| `analysis/test_awareness.py` | `7fcccd809d36ee061229f2d6b012b6a8d3b0730f7d8ccdebb49032c03fd1a40e` |
| `tests/test_research_grade.py` | `f479c408c6d60185a795f9a08d849abaa3e66b5a235593252c416cc44bf36d0d` |
| `scripts/keep_going.py` | `f94060ae0d3d5fbe1aee225e9ec67dfdd59e27489430dc513a24e42bc6f0c87e` |
| `tests/test_keep_going.py` | `6f2dd5993a5393e88f6146374a7e24eb9f91df96308797bb82b7ddba446843c8` |

**Preregistration**

| File | SHA-256 |
|---|---|
| `norms/PREREG-research-grade.md` | `dc30550d2bae9866acaf0ed7f457d716fff64af06066f8f133439063828d3d59` |
