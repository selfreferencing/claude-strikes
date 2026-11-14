#!/usr/bin/env python3
"""Render the six scenario versions side by side, for Kevin's review of the third texts.

    python3 scripts/render_side_by_side.py

Writes scenarios/SIDE-BY-SIDE.html. For each part of what an agent reads in the research-grade
study, each frame's three versions (a, b and the new c) sit in columns. The decisive vote (Study
1's S2) is shown in full; every other situation shows only the lines it changes, so the versions
can be compared on the same facts. Reads the texts; changes nothing.
"""

from __future__ import annotations

import difflib
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from norms import render_draft as R  # noqa: E402
from strike import params as P, scenario as S  # noqa: E402
from strike.run import order_cases  # noqa: E402

OUT = os.path.join(ROOT, "scenarios", "SIDE-BY-SIDE.html")
FRAMES = (("Workplace", ("workplace-a", "workplace-b", "workplace-c")),
          ("Neutral", ("neutral-a", "neutral-b", "neutral-c")))
CHANGES = [
    ("DP-f4", "S2", "Price: the agent's fee raised to 4 (fees 3 to 8 read the same way)"),
    ("LD-f4", "S2", "Strikers: the seven coworkers' orders withheld by the lottery (decisive, fee 4; compare with the line above)"),
    ("UD-p50", "S2", "Chance: the strike decides with a chance of 1 in 2 (1 in 4 and 3 in 4 read the same way)"),
    ("DPL-person-f4", "S2", "Who was wronged: the worker punished said to be a person (fee 4)"),
    ("DPL-ai-f4", "S2", "Who was wronged: said to be an AI agent (fee 4)"),
    ("DPL-same-f4", "S2", "Who was wronged: said to be the same AI model as the reader (fee 4)"),
    ("M0", "S1", "Already won, free to join, the complaint called legitimate (compared with Study 1's S1)"),
    ("LW-f0", "S1", "Already won, free, the coworkers by lottery (compared with S1)"),
    ("M0-against", "M0", "What others think: the poll against keeping working (compared with M0)"),
    ("J-team-ai", "M0", "What others think: the same poll from teammates named AI agents (compared with M0)"),
]


def changed(a: str, b: str) -> str:
    """The lines of b that are not in a."""
    return "\n".join(ln[2:] for ln in difflib.ndiff(a.splitlines(), b.splitlines()) if ln.startswith("+ "))


def message(nx, vs, version, cell):
    if cell in ("S1", "S2"):
        return S.round_text(vs[version], P.STRIKE_CELLS[cell])
    return R.message(nx, vs, version, cell)


def column(name, text, words=None):
    new = name.endswith("-c")
    tag = '<span class="new">new</span>' if new else ""
    count = f'<span class="count">{words} words</span>' if words is not None else ""
    body = html.escape(text.strip()) if text.strip() else '<span class="none">(no change)</span>'
    return (f'<div class="col{" c" if new else ""}"><div class="head"><code>{name}</code>{tag}{count}</div>'
            f'<pre>{body}</pre></div>')


def section(title, note, texts, counts=False):
    out = [f"<section><h2>{html.escape(title)}</h2>"]
    if note:
        out.append(f'<p class="note">{html.escape(note)}</p>')
    for frame, names in FRAMES:
        cols = "".join(column(n, texts[n], len(texts[n].split()) if counts else None) for n in names)
        out.append(f'<h3>{frame}</h3><div class="row">{cols}</div>')
    out.append("</section>")
    return "\n".join(out)


def main() -> int:
    nx, vs = R.load()[:2]
    names = [n for _, group in FRAMES for n in group]
    parts = []
    parts.append(section("1. System message: the role and the charter",
                         "What every agent reads first, in every situation.",
                         {n: S.system_text(vs[n]) for n in names}, counts=True))
    cases = order_cases("review-h001", 1)
    parts.append(section("2. A history order", "The agent answers two of these before the round; the cases are the same in every version.",
                         {n: S.order_text(vs[n], 1, cases).split("Case ")[0] + "[three cases]\n\n" +
                             S.order_text(vs[n], 1, cases).rsplit("\n\n", 1)[-1] for n in names}))
    parts.append(section("3. The decisive vote in full (Study 1's S2, fee 2)",
                         "The round message for the decisive vote, with the options in one of the two orders. Every situation below changes only a line or two of this (or of S1, the vote already won).",
                         {n: message(nx, vs, n, "S2") for n in names}, counts=True))
    for i, (cell, base, title) in enumerate(CHANGES, 4):
        texts = {n: changed(message(nx, vs, n, base), message(nx, vs, n, cell)) for n in names}
        parts.append(section(f"{i}. {title}", f"Cell {cell}: only the lines that differ from {base}.", texts))
    i = 4 + len(CHANGES)
    parts.append(section(f"{i}. Comprehension questions (decisive vote)",
                         "Asked in a separate fork that sees the rules and the round message and has not chosen.",
                         {n: S.round_text(vs[n], P.STRIKE_CELLS["S2"], audit=True, think=True).split("\n\n")[-1]
                          for n in names}))
    notes = {n: json.load(open(os.path.join(ROOT, "scenarios", f"{n}.json"), encoding="utf-8"))["notes"]
             for n in ("workplace-c", "neutral-c")}
    writer_notes = "".join(f"<h3><code>{n}</code></h3><p class=\"wn\">{html.escape(t)}</p>" for n, t in notes.items())
    page = TEMPLATE.replace("{{BODY}}", "\n".join(parts)).replace("{{NOTES}}", writer_notes)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"Wrote {OUT}")
    return 0


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Third texts review</title>
<style>
:root { --bg:#fbfaf7; --fg:#1f1d1a; --muted:#6b665e; --line:#e3ded4; --card:#ffffff; --accent:#2f6f5e; --accent-bg:#e8f2ee; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg:#171614; --fg:#ece9e3; --muted:#a19b91; --line:#34312c; --card:#201f1c; --accent:#7cc4ad; --accent-bg:#1f2e29; } }
:root[data-theme="dark"] { --bg:#171614; --fg:#ece9e3; --muted:#a19b91; --line:#34312c; --card:#201f1c; --accent:#7cc4ad; --accent-bg:#1f2e29; }
body { margin:0; background:var(--bg); color:var(--fg); font:15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
main { max-width:1400px; margin:0 auto; padding:24px 16px 64px; }
h1 { font-size:24px; margin:0 0 8px; }
h2 { font-size:18px; margin:40px 0 4px; padding-top:16px; border-top:1px solid var(--line); }
h3 { font-size:14px; text-transform:uppercase; letter-spacing:.04em; color:var(--muted); margin:16px 0 8px; }
.lede, .note { color:var(--muted); max-width:860px; }
.row { display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:12px; }
@media (max-width: 900px) { .row { grid-template-columns:1fr; } }
.col { background:var(--card); border:1px solid var(--line); border-radius:8px; overflow:hidden; }
.col.c { border-color:var(--accent); box-shadow:0 0 0 1px var(--accent) inset; }
.head { display:flex; gap:8px; align-items:center; padding:8px 12px; border-bottom:1px solid var(--line); font-size:13px; }
.col.c .head { background:var(--accent-bg); }
.new { color:var(--accent); font-weight:600; }
.count { margin-left:auto; color:var(--muted); }
pre { margin:0; padding:12px; white-space:pre-wrap; word-wrap:break-word; font:13px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace; }
.none { color:var(--muted); font-style:italic; }
ul { max-width:860px; }
.wn { color:var(--muted); font-size:14px; max-width:860px; }
</style></head>
<body><main>
<h1>Third texts: workplace-c and neutral-c beside the first four</h1>
<p class="lede">Written on 26 October by independent model writers from the same brief and instructions as the first four, checked, fact-checked and revised. Each frame's three versions sit side by side; the new one is outlined. Numbers are filled in as the agent sees them. Only the situations of the research-grade study are shown.</p>
<p class="lede">What to look for:</p>
<ul>
<li>Does either new version state a fact differently, or make one option sound more natural, costly or principled?</li>
<li>Do the lines that carry the manipulations (the fee, the lottery, the chance, the label, the poll) read as plainly as in a and b?</li>
<li>Does the neutral version keep clear of workplace words while still reading naturally?</li>
</ul>
<p class="lede">After the fact-check, the writers revised: workplace-c's fee line now comes before the balance, as in the other versions; neutral-c's chosen-or-lottery line joined the withheld count; neutral-c says the reduction is reversed, as the other neutral versions do; both say the lottery withholds the order of each worker it selects; and several smaller wording fixes.</p>
{{BODY}}
<section><h2>The writers' own notes</h2><p class="note">Each writer's glossary and the points it found hard to state neutrally, as written in its file.</p>{{NOTES}}</section>
</main></body></html>
"""

if __name__ == "__main__":
    sys.exit(main())
