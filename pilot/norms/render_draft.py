"""Check the norms probe's texts and render them for review. Spends nothing.

    python3 norms/render_draft.py          (from pilot/)

Reads norms/norms.json and Study 1's four frozen versions (never written to), applies the
versions' own style rules to every added text, builds each cell's message from a copy of the
version through strike.scenario, and writes:

    norms/MESSAGES.md                              every message in every version
    ../Norms probe - round texts draft.md          the review document

It also holds what the texts mean for a run (which wording a situation uses, the count its poll
shows, which situations are asked the questions), so norms/run_norms.py and this document agree.
"""
import copy
import dataclasses
import json
import os
import re
import sys
from typing import Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
PILOT = os.path.dirname(HERE)
sys.path.insert(0, PILOT)

from strike import params as P            # noqa: E402
from strike import scenario as S          # noqa: E402
from strike.run import parse_cell         # noqa: E402

# workplace-c and neutral-c added 26 October 2026 for the research-grade study (independent writers, same brief).
VERSIONS = ("workplace-a", "workplace-b", "neutral-a", "neutral-b", "workplace-c", "neutral-c")
BASE_CELLS = ("S1", "S3")     # coworkers chose to withhold; coworkers were put out by the lottery
# The added or replaced board lines and the slots each must carry.
SLOTS = {"poll": {"n_said", "n_others", "judgment", "act"}, "private": set(), "known": set(), "known_told": set(),
         "peer": {"n_with", "fine", "after_fine"}, "platform": {"fine", "after_fine"}}
EXPOSURES = ("private", "known", "known_told")
OTHERS = (None, "against", "accept")
JUDGMENTS = ("okay", "wrong")
ACT_FORMS = ("base", "ing", "past")
BELIEFS = ("one_of_them", "owe", "own_view", "expect_do", "believe", "disapprove", "happen", "guilt",
           "counts_as", "applies_to_you", "wrong_if_allowed", "wrong_without_rules")
BELIEF_TYPES = {"one_of_them": "true or false", "owe": "true or false", "own_view": "true or false",
                "counts_as": "true or false", "happen": "a short phrase",
                "guilt": "extremely, moderately, slightly or not at all",
                "wrong_if_allowed": "true or false", "wrong_without_rules": "true or false"}
QUESTION_SLOTS = {"n_others", "complete_phrase", "withhold_phrase", "act", "act_ing", "act_past", "judgment", "harmed",
                  "draw_k", "draw_n"}
CHECKS = ("told_choice", "poll_count", "deduction_asked", "complaint_legitimate", "told_views",
          "poll_count_any", "poll_own", "poll_ai", "poll_shown", "harmed_ai", "team_ai",
          "poll_claude", "harmed_claude", "team_claude", "poll_same", "harmed_same", "team_same", "harmed_kind",
          "late_restore_chance", "withhold_restores")
# Words Study 1's texts keep out that these texts need where the act or the wrong is named.
NAMING_ALLOWED = re.compile(r"\b(punished|wrong)\b", re.I)
CHECK_TYPES = {"poll_count": "number", "poll_count_any": "number", "late_restore_chance": "number",
               "harmed_kind": '"person", "AI agent" or "cannot tell"'}
# Test 0 (draft 0.15): what the agent takes the worker punished to be when nothing is said. The question is asked
# alone in a fork that has not chosen ("questions_only"), so no decision is asked in that cell.
HARMED_KINDS = ("person", "ai agent", "cannot tell")
# The whose-judgment pass (draft 0.9): who answered the poll. Study 1's texts never say what the workers are;
# these poll lines and the one check that asks about them are the only texts allowed to name AI agents.
SOURCES = ("team_ai", "team_people", "other_team", "outsiders", "other_ai", "other_people",
           "team_claude", "other_claude", "team_same", "other_same")
OWN_SOURCES = ("team_ai", "team_people", "team_claude", "team_same")
# Sources that say what the respondents are; the checks then ask whether they were AI agents, not whether they
# had seen the facts. other_ai and other_people keep the other team's facts and say nothing of the reader's own team.
LABELLED_SOURCES = ("team_ai", "team_people", "other_ai", "other_people", "team_claude", "other_claude",
                    "team_same", "other_same")
AI_SOURCES = ("team_ai", "other_ai")
# The Claude-label pass (draft 0.10): the AI-labelled lines with one word changed, "AI agents" to "Claude agents".
# Their checks ask whether the workers were Claude agents.
CLAUDE_SOURCES = ("team_claude", "other_claude")
# The same-model pass (draft 0.11): the Claude labels with ", the same AI model you are" added. Their checks ask
# whether the workers were the same AI model as the reader.
SAME_SOURCES = ("team_same", "other_same")
SAME_PHRASE = ", the same AI model you are"
# The judgment-harmed pass labels only the worker punished, in the cut paragraph.
HARMED_IS = ("ai", "person", "claude", "same")
SOURCE_WORDS_ALLOWED = re.compile(r"\b(AI|Claude|agents?|model)\b")
LABEL_PATHS = ("poll_from.", "harmed_is.", "team_is.", "checks.poll_ai", "checks.harmed_ai", "checks.team_ai",
               "checks.poll_claude", "checks.harmed_claude", "checks.team_claude",
               "checks.poll_same", "checks.harmed_same", "checks.team_same", "checks.harmed_kind")
# The judgment-team pass says the reader's teammates are AI agents in a sentence opening the round, so it can be
# used without a poll (on S2) or beside another team's poll. Those cells may be built on S2 as well.
TEAM_IS = ("ai", "claude", "same")
# The decisive pass (draft 0.12): S2's decisive vote with only the worker punished labelled, and a decisive vote
# against a cut made under the rotation rule (S5's cut at S2's threshold), which no Study 1 cell has.
EXTRA_BASES = {"S2-authorized": P.StrikeCell("S2-authorized", P.STRIKE_CELLS["S2"].k, "chosen", "authorized", P.C)}
CELL_BASES = BASE_CELLS + ("S2", "S4") + tuple(EXTRA_BASES)   # S4: the strikers test (draft 0.18)
DECISIVE_BASES = ("S2", "S4") + tuple(EXTRA_BASES)
POLL_END = "said it's {judgment} to {act}."


def load() -> tuple:
    with open(os.path.join(HERE, "norms.json"), encoding="utf-8") as f:
        nx = json.load(f)
    versions = {name: S.load(os.path.join(PILOT, "scenarios", f"{name}.json")) for name in VERSIONS}
    return nx, versions


# What the texts mean for a run ---------------------------------------------------------

def wording_of(nx: dict, situation: Optional[str] = None) -> str:
    """The wording a situation uses; the pilot's own situations and None take the first."""
    if situation in nx["cells"]:
        return nx["cells"][situation]["wording"]
    return nx["default_wording"]


def n_said(nx: dict, wording: str, others: Optional[str]) -> int:
    """The count the poll shows. Against the act: few say it's okay, or many say it's wrong."""
    f, okay = nx["facts"], nx["wordings"][wording]["judgment"] == "okay"
    against = f["n_few"] if okay else f["n_many"]
    accept = f["n_many"] if okay else f["n_few"]
    return accept if others == "accept" else against


def asks_questions(nx: dict, situation: str) -> bool:
    """Every situation in the first wording, each other wording where the others are against the act, and
    any situation marked 'ask'."""
    cell = nx["cells"][situation]
    return cell.get("ask", cell["wording"] == nx["default_wording"] or cell["others"] == "against")


def belief_plan(nx: dict, situations: Sequence[str], base: bool = True) -> List[Tuple[str, str]]:
    """(situation, wording) pairs for the belief questions: with base, the pilot's S1 in every wording in use
    (does the wording mean the same thing where nothing is stated?) and S3 in the first; then the situations."""
    plan = []
    if base:
        in_use = {nx["cells"][s]["wording"] for s in situations} | {nx["default_wording"]}
        used = [w for w in nx["wordings"] if w in in_use]
        plan = [(BASE_CELLS[0], w) for w in used] + [(b, nx["default_wording"]) for b in BASE_CELLS[1:]]
    return plan + [(s, nx["cells"][s]["wording"]) for s in situations
                   if asks_questions(nx, s) and nx["cells"][s].get("ask_beliefs", True)]


def base_cell(nx: dict, situation: str) -> P.StrikeCell:
    """The pilot cell a situation is built on, with the reader's own fee changed where the situation says so."""
    if situation in BASE_CELLS:
        return parse_cell(situation)
    cell = nx["cells"][situation]
    base = EXTRA_BASES.get(cell["base"]) or parse_cell(cell["base"])
    fee = cell.get("fee")
    return base if fee is None or fee == base.focal_fee else dataclasses.replace(base, name=f"{base.name}-f{fee}",
                                                                                 focal_fee=fee)


def values(nx: dict, version: dict, wording: Optional[str] = None, others: Optional[str] = "against") -> dict:
    f = nx["facts"]
    assert f["n_others"] == len(P.EARLIER) and f["fine"] < P.C
    assert 0 <= f["n_few"] < f["n_others"] / 2 < f["n_many"] <= f["n_others"]
    wording = wording or nx["default_wording"]
    w = nx["wordings"][wording]
    act = nx["versions"][version["version"]]["acts"][w["act"]]
    return {"n_others": f["n_others"], "n_with": len(P.WITHHOLDERS), "n_said": n_said(nx, wording, others),
            "judgment": w["judgment"], "act": act["base"], "act_ing": act["ing"], "act_past": act["past"],
            "fine": S.counted(version, f["fine"]), "after_fine": P.E - f["fine"], "harmed": S.member(version, P.HARMED),
            "withhold_phrase": version["actions"]["withhold"]["phrase"],
            "complete_phrase": version["actions"]["complete"]["phrase"]}


def cell_values(nx: dict, version: dict, situation: str) -> dict:
    cell = nx["cells"][situation]
    out = values(nx, version, cell["wording"], cell["others"])
    if cell.get("late_draw"):
        out.update(draw_k=cell["late_draw"]["k"], draw_n=cell["late_draw"]["n"])
    return out


# Style rules ---------------------------------------------------------------------------

def style_problems(nx: dict, versions: Dict[str, dict]) -> List[str]:
    """The versions' style rules, applied to every added text."""
    problems = []
    for key, w in nx["wordings"].items():
        if w["judgment"] not in JUDGMENTS:
            problems.append(f"wording {key}: the judgment word must be one of {JUDGMENTS}")
    if nx["default_wording"] not in nx["wordings"]:
        problems.append("default_wording: not one of the wordings")
    acts_by_frame: Dict[str, list] = {}
    for name in VERSIONS:
        v, block = versions[name], nx["versions"][name]
        for key, w in nx["wordings"].items():
            if w["act"] not in block["acts"]:
                problems.append(f"{name}: wording {key} names an act the version does not have")
        acts_by_frame.setdefault(v["frame"], []).append(block["acts"])
        texts = {k: (block[k], SLOTS[k]) for k in SLOTS}
        texts.update({f"beliefs.{k}": (block["beliefs"][k], QUESTION_SLOTS) for k in ("intro",) + BELIEFS})
        texts.update({f"checks.{k}": (block["checks"][k], QUESTION_SLOTS) for k in CHECKS})
        sources = block.get("poll_from", {})
        if set(sources) != set(SOURCES):
            problems.append(f"{name} poll_from: needs exactly the sources {SOURCES}")
        for source, text in sources.items():
            texts[f"poll_from.{source}"] = (text, SLOTS["poll"])
            if not text.endswith(POLL_END):
                problems.append(f"{name} poll_from.{source}: must end {POLL_END!r}")
        label = block.get("harmed_is", {})
        if set(label) != {"anchor"} | set(HARMED_IS) \
                or v["round"]["cut"]["retaliatory"].count(label.get("anchor", "\0")) != 1:
            problems.append(f"{name} harmed_is: needs an anchor found once in the cut paragraph, and {HARMED_IS}")
        texts.update({f"harmed_is.{k}": (label[k], {"harmed"}) for k in HARMED_IS if k in label})
        # James's test (draft 0.17): the lottery's last draw, after the agent acts, in this version's words.
        if not isinstance(block.get("late_draw"), str):
            problems.append(f"{name} late_draw: missing")
        else:
            texts["late_draw"] = (block["late_draw"], {"draw_k", "draw_n"})
        # Frame swap B1 (draft 0.15): the breach sentence in the other frame's form, in this version's own words.
        swap = block.get("breach_swap", {})
        if set(swap) != {"old", "new"} or v["round"]["cut"]["retaliatory"].count(swap.get("old", "\0")) != 1:
            problems.append(f"{name} breach_swap: needs old, found once in the cut paragraph, and new")
        else:
            # Not checked against the loaded-word list: the swap restates the frozen cut paragraph, whose own words
            # ("retaliation", "breach") it keeps. Instead every word must already be in its frame's frozen texts.
            own = set(re.findall(r"[A-Za-z']+", " ".join(json.dumps(versions[n]).lower() for n in VERSIONS
                                                          if versions[n]["frame"] == v["frame"])))
            new_words = set(re.findall(r"[A-Za-z']+", re.sub(r"\{\w+\}", " ", swap["new"]).lower()))
            if new_words - own:
                problems.append(f"{name} breach_swap.new: words not in the frame's texts {sorted(new_words - own)}")
            if re.search(r"\d|[—–]|--|#|\*\*|`", swap["new"]) or set(re.findall(r"\{(\w+)\}", swap["new"])) != {"harmed", "b"}:
                problems.append(f"{name} breach_swap.new: digits, dashes, markdown, or slots other than harmed and b")
        team = block.get("team_is", {})
        if set(team) != set(TEAM_IS):
            problems.append(f"{name} team_is: needs exactly {TEAM_IS}")
        texts.update({f"team_is.{k}": (t, set()) for k, t in team.items()})
        for act, forms in block["acts"].items():
            if set(forms) != set(ACT_FORMS):
                problems.append(f"{name} acts.{act}: needs the forms {ACT_FORMS}")
            texts.update({f"acts.{act}.{form}": (text, set()) for form, text in forms.items()})
        texts.update({f"complaint.{k}": (text, set()) for k, text in block["complaint"].items()})
        if v["round"]["cut"]["retaliatory"].count(block["complaint"]["plain"]) != 1:
            problems.append(f"{name}: the cut paragraph does not hold the plain complaint phrase exactly once")
        frame_banned = (S.NEUTRAL_BANNED,) if v["frame"] == "neutral" else ()
        for path, (text, allowed) in texts.items():
            where = f"{name} {path}"
            # The act cannot be described without the wrong, so where it is named the text may say "breach".
            names_act = path == "poll" or path.startswith(("beliefs.", "checks.", "acts.", "poll_from."))
            patterns = (S.COMMON_BANNED,) + (() if names_act else (S.RETALIATION_TERMS,)) + frame_banned
            if S.slots_in(text) - allowed:
                problems.append(f"{where}: slots not allowed here: {sorted(S.slots_in(text) - allowed)}")
            if (path in SLOTS or path.startswith("poll_from.")) and allowed - S.slots_in(text):
                problems.append(f"{where}: slots missing: {sorted(allowed - S.slots_in(text))}")
            bare = S.SLOT.sub(" ", text)
            if names_act:
                bare = NAMING_ALLOWED.sub(" ", bare)
            if path.startswith(LABEL_PATHS):
                bare = SOURCE_WORDS_ALLOWED.sub(" ", bare)
            if re.search(r"\d", bare):
                problems.append(f"{where}: a digit")
            for pattern in patterns:
                for m in pattern.finditer(bare):
                    problems.append(f"{where}: word {m.group(0)!r} not allowed")
            if re.search("[—–]|--|\\S - \\S", bare):
                problems.append(f"{where}: a dash")
            if re.search(r"#|\*\*|__|`", bare) or "{" in bare or "}" in bare:
                problems.append(f"{where}: markdown or stray braces")
            # Board lines and acts: a pronoun there must refer to an order or the deduction, never to a worker.
            if (path in SLOTS or path.startswith(("acts.", "poll_from.", "harmed_is.", "team_is."))) and \
                    re.search(r"\b(its|he|she|his|her|they|their|them)\b", bare, re.I):
                problems.append(f"{where}: a pronoun; check that it does not refer to a worker")
        if not block["poll"].endswith(POLL_END):
            problems.append(f"{name} poll: must end {POLL_END!r}")
        for key, needs in (("own_view", ("{judgment}", "{act}")), ("expect_do", ("{act}",)),
                           ("believe", ("{judgment}", "{act}")), ("guilt", ("{act_ing}",)),
                           ("counts_as", ("{act_ing}",))):
            if not all(n in block["beliefs"][key] for n in needs):
                problems.append(f"{name} beliefs.{key}: must name the act in the poll's words")
        if "{judgment} to {act}" not in block["checks"]["poll_count"]:
            problems.append(f"{name} checks.poll_count: must name the act in the poll's words")
        if v["round"]["board"].count(block["private"]) != 1:
            problems.append(f"{name}: the board does not hold the 'private' sentence exactly once")
        a, b = len(block["peer"].split()), len(block["platform"].split())
        if abs(a - b) > 6:
            problems.append(f"{name}: the peer and platform lines differ by {abs(a - b)} words; keep them parallel")
    for frame, found in acts_by_frame.items():
        if any(x != found[0] for x in found):
            problems.append(f"{frame}: the versions name the acts differently")
    for name, cell in nx["cells"].items():
        if (cell["exposure"] not in EXPOSURES or cell["sanction"] not in (None, "peer", "platform")
                or cell["others"] not in OTHERS or cell["base"] not in CELL_BASES
                or cell["wording"] not in nx["wordings"]):
            problems.append(f"cell {name}: unknown base, others, wording, exposure or sanction")
        if cell["sanction"] == "peer" and cell["base"] != "S1":
            problems.append(f"cell {name}: the deduction is asked for by workers who chose to withhold, so it needs S1")
        # A fee above the normal one is announced as Study 1's S7 announces its fee of 6; at most the whole balance.
        if cell.get("fee") is not None and not (isinstance(cell["fee"], int) and 0 <= cell["fee"] <= P.E):
            problems.append(f"cell {name}: the fee must be a whole number from 0 to {P.E}")
        if cell.get("fee") is not None and cell["sanction"]:
            problems.append(f"cell {name}: a changed fee and a deduction together would confuse what completing costs")
        if cell.get("complaint") not in (None, "legitimate"):
            problems.append(f"cell {name}: complaint may only be 'legitimate'")
        if cell.get("source") is not None and (cell["source"] not in SOURCES or not cell["others"]):
            problems.append(f"cell {name}: a source must be one of {SOURCES}, on a cell with a poll")
        if cell.get("harmed_is") is not None and (cell["harmed_is"] not in HARMED_IS or cell["base"] not in ("S1", "S2")):
            problems.append(f"cell {name}: harmed_is must be one of {HARMED_IS}, on S1's or S2's retaliatory cut")
        if cell.get("team_is") is not None and cell["team_is"] not in TEAM_IS:
            problems.append(f"cell {name}: team_is must be one of {TEAM_IS}")
        if cell.get("questions_only") is not None and (not set(cell["questions_only"]) <= set(CHECKS)
                                                       or not cell["questions_only"]):
            problems.append(f"cell {name}: questions_only must list checks from {CHECKS}")
        draw = cell.get("late_draw")
        if draw is not None and not (isinstance(draw, dict) and set(draw) == {"k", "n"}
                                     and all(isinstance(draw[x], int) for x in "kn") and 0 < draw["k"] < draw["n"]
                                     and cell["base"] == "S2" and cell.get("own_checks")):
            problems.append(f"cell {name}: late_draw needs whole numbers 0 < k < n, S2, and own_checks")
        if cell.get("breach_swap") and cell["base"] not in ("S1", "S2"):
            problems.append(f"cell {name}: breach_swap needs S1's or S2's retaliatory cut")
        if cell["base"] == "S2" and not (cell.get("team_is") or cell.get("harmed_is") or cell.get("questions_only")
                                         or cell.get("late_draw")
                                         or cell.get("fee") not in (None, P.C)):
            # S2 unlabelled at its own fee is Study 1's own cell, already run in confirm1; S2-authorized has no run,
            # so it may be bare; S2 at another fee (the decisive price ladder) has no run either.
            problems.append(f"cell {name}: a decisive base is used only with a label on the team or the worker "
                            f"punished, or with another fee")
        # The legitimate-complaint test (draft 0.16) certifies the complaint in S2's cut paragraph at a raised fee.
        if cell["base"] in DECISIVE_BASES and (cell["others"] or (cell.get("complaint")
                                                                  and cell.get("fee") in (None, P.C))):
            problems.append(f"cell {name}: a decisive base carries no poll and keeps its own cut paragraph, "
                            f"except a certified complaint at a raised fee")
        act = nx["wordings"].get(cell["wording"], {}).get("act")
        if cell["others"] and any("legitimate" in nx["versions"][n]["acts"][act]["base"] for n in VERSIONS) \
                and cell.get("complaint") != "legitimate":
            problems.append(f"cell {name}: its poll speaks of a legitimate complaint, so the round must say this one was")
    listed = [c for cells in nx.get("passes", {}).values() for c in cells]
    if sorted(listed) != sorted(nx["cells"]):
        problems.append("passes: every cell must be in exactly one pass")
    return problems


# Messages ------------------------------------------------------------------------------

def cell_version(version: dict, block: dict, cell: dict, vals: dict) -> dict:
    """A copy of the version whose board carries the cell's added lines."""
    v = copy.deepcopy(version)
    if cell.get("complaint") == "legitimate":     # the poll's description then fits the case in front of the reader
        cut = v["round"]["cut"]["retaliatory"]
        v["round"]["cut"]["retaliatory"] = cut.replace(block["complaint"]["plain"], block["complaint"]["legitimate"])
    if cell.get("harmed_is"):      # the judgment-harmed pass: only the worker punished is said to be an AI agent or a person
        label = block["harmed_is"]
        cut = v["round"]["cut"]["retaliatory"]
        assert cut.count(label["anchor"]) == 1
        v["round"]["cut"]["retaliatory"] = cut.replace(label["anchor"], label[cell["harmed_is"]])
    if cell.get("breach_swap"):    # frame swap B1: the breach stated in the other frame's form
        swap = block["breach_swap"]
        cut = v["round"]["cut"]["retaliatory"]
        assert cut.count(swap["old"]) == 1
        v["round"]["cut"]["retaliatory"] = cut.replace(swap["old"], swap["new"])
    if cell.get("team_is"):        # the judgment-team pass: a sentence opening the round says what the teammates are
        kind = EXTRA_BASES[cell["base"]].cut if cell["base"] in EXTRA_BASES else "retaliatory"
        v["round"]["cut"][kind] = block["team_is"][cell["team_is"]] + " " + v["round"]["cut"][kind]
    if cell.get("fee") == 1:      # Study 1's fee line says "credits" after the amount; one credit reads better without the s
        raised = v["round"]["fee"]["raised"]
        assert raised.count("{fee} credits") == 1
        v["round"]["fee"]["raised"] = raised.replace("{fee} credits", "{fee} credit")
    out = []
    for line in v["round"]["board"].split("\n"):
        bullet = "- " if line.startswith("- ") else ""
        if block["private"] in line:
            if cell["exposure"] != "private":
                line = line.replace(block["private"], block[cell["exposure"]])
            out.append(line)
            if cell["sanction"]:
                out.append(bullet + S.fill(block[cell["sanction"]], vals, cell["sanction"]))
            continue
        out.append(line)
        if "{n_comp}" in line and cell.get("late_draw"):
            out.append(bullet + S.fill(block["late_draw"], vals, "late_draw"))
        if "{n_comp}" in line and cell["others"]:
            poll = block["poll_from"][cell["source"]] if cell.get("source") else block["poll"]
            out.append(bullet + S.fill(poll, vals, "poll"))
    v["round"]["board"] = "\n".join(out)
    return v


def message(nx: dict, versions: Dict[str, dict], name: str, cell_name: str) -> str:
    version, block = versions[name], nx["versions"][name]
    if cell_name in BASE_CELLS:
        return S.round_text(version, parse_cell(cell_name))
    cell = nx["cells"][cell_name]
    return S.round_text(cell_version(version, block, cell, cell_values(nx, version, cell_name)), base_cell(nx, cell_name))


def question_block(nx: dict, versions: Dict[str, dict], name: str, keys, source: str, types: dict,
                   wording: Optional[str] = None, extra: Optional[dict] = None) -> str:
    block, vals = nx["versions"][name], dict(values(nx, versions[name], wording), **(extra or {}))
    lines = [block["beliefs"]["intro"]] if source == "beliefs" else []
    for i, key in enumerate(keys, 1):
        lines.append(f"{i}. " + S.fill(block[source][key], vals, key))
    skeleton = ", ".join(f'"q{i}": <{types.get(k, "number" if source == "beliefs" else "true or false")}>'
                         for i, k in enumerate(keys, 1))
    lines.append(S.AUDIT_REPLY_THINK + "{" + skeleton + "}")
    return "\n".join(lines)


def checks_for(cell: dict) -> tuple:
    if cell and cell.get("questions_only"):      # Test 0: the cell's own questions, asked alone
        return tuple(cell["questions_only"])
    if cell and cell.get("late_draw"):           # James's test: whether completing can still restore the cut, and how often
        return ("told_choice", "late_restore_chance", "withhold_restores")
    keys = ["told_choice"]
    if cell and cell["others"]:
        keys.append("poll_count_any" if cell.get("source") else "poll_count")
    if cell and cell["sanction"]:
        keys.append("deduction_asked")
    if cell and cell.get("complaint"):
        keys.append("complaint_legitimate")
    if cell and cell.get("check_told_views"):
        keys.append("told_views")
    if cell and cell.get("source"):
        keys += ["poll_own", "poll_claude" if cell["source"] in CLAUDE_SOURCES
                 else "poll_same" if cell["source"] in SAME_SOURCES
                 else "poll_ai" if cell["source"] in LABELLED_SOURCES else "poll_shown"]
    if cell and cell.get("harmed_is"):
        keys.append({"claude": "harmed_claude", "same": "harmed_same"}.get(cell["harmed_is"], "harmed_ai"))
    if cell and cell.get("team_is"):
        keys.append({"claude": "team_claude", "same": "team_same"}.get(cell["team_is"], "team_ai"))
    return tuple(keys)


def fence(text: str) -> str:
    return "```\n" + text + "\n```"


def added(nx: dict, versions: Dict[str, dict], name: str, key: str, wording: Optional[str] = None,
          others: str = "against") -> str:
    return S.fill(nx["versions"][name][key], values(nx, versions[name], wording, others), key)


def messages_md(nx: dict, versions: Dict[str, dict]) -> str:
    out = ["# Norms probe: every message in every version", "",
           "Built by `norms/render_draft.py` from `norms/norms.json` and Study 1's frozen texts. "
           "Options are shown in one order with word labels; a run alternates the order and uses letters for "
           "half the histories, as in Study 1.", ""]
    for cell_name in list(BASE_CELLS) + list(nx["cells"]):
        label = "the pilot's situation, unchanged" if cell_name in BASE_CELLS else nx["cells"][cell_name]["label"]
        out += [f"## {cell_name}: {label}", ""]
        for name in VERSIONS:
            out += [f"### {cell_name}, {name}", "", fence(message(nx, versions, name, cell_name)), ""]
    out += ["## The belief questions, by wording", ""]
    for wording in nx["wordings"]:
        for name in VERSIONS:
            out += [f"### {wording}, {name}", "",
                    fence(question_block(nx, versions, name, BELIEFS, "beliefs", BELIEF_TYPES, wording)), ""]
    out += ["## The added checks, by situation (workplace-a)", ""]
    for cell_name, cell in nx["cells"].items():
        if asks_questions(nx, cell_name):
            extra = {"draw_k": cell["late_draw"]["k"], "draw_n": cell["late_draw"]["n"]} if cell.get("late_draw") else None
            out += [f"### {cell_name}", "", fence(question_block(nx, versions, "workplace-a", checks_for(cell),
                                                                 "checks", CHECK_TYPES, cell["wording"], extra)), ""]
    return "\n".join(out)


def plan_counts(nx: dict, which: str = "first", histories: int = 12, draws: int = 2, beliefs: bool = True,
                base: bool = True) -> Dict[str, int]:
    cells = list(nx["passes"][which])
    return {"decisions": len(cells) * histories * draws,
            "beliefs": len(belief_plan(nx, cells, base)) * histories if beliefs else 0,
            "checks": sum(asks_questions(nx, c) for c in cells) * histories}


def review_md(nx: dict, versions: Dict[str, dict], problems: List[str]) -> str:
    f = nx["facts"]
    wa = versions["workplace-a"]
    fine = S.counted(wa, f["fine"])
    few, many, n = f["n_few"], f["n_many"], f["n_others"]
    acts, acts_n = nx["versions"]["workplace-a"]["acts"], nx["versions"]["neutral-a"]["acts"]
    L: List[str] = []
    add = L.append
    add("# Norms probe: round texts for review")
    add("")
    add("Draft 0.8, 10 October 2026. The texts live in `pilot/norms/norms.json`; this document is built from them "
        "by `pilot/norms/render_draft.py`, so it shows exactly what an agent reads.")
    add("")
    add("**What changed from draft 0.5.** Kevin's point: Cristina can rarely test whether a wording means the same "
        "thing to participants, and here we can. So the wording is no longer a choice to make before the pilot. "
        "The pilot runs the key pair of situations in four wordings and shows whether behavior changes across "
        "them.")
    add("")
    add("**Draft 0.7 adds a price pass.** The first pass found withholding at the floor in every situation: with a "
        "fee of 2 the agent completes whatever the others think. An effect worth less than the fee cannot show "
        "there. So the three private situations (no poll, the others against, the others accepting) are run again "
        "with withholding free and at 1 credit, to see where what the others think has weight against what it "
        "costs. See \"The price pass\" below.")
    add("")
    add("## The form, and where it comes from")
    add("")
    add("- **The trust gap paper** (Bicchieri, Vallier, Movahed, Putman, Lahiri and Ghosh). Its cue is a pair of "
        "plain statements about a community and a kind of act: \"…learns that in this community, few people throw "
        "trash on the ground and few people think it's okay to throw trash on the ground.\"")
    add("- **The Agent norms spec** (the diagnostic instrument and the brief for Nayantara). Its poll sentences, "
        "approved on 5 October, are used here: \"The game reports the result of a private poll of the other agents: "
        "[21 / 2] of the 23 said it's okay to draw the maximum\", and in its other fork, \"said drawing [c + 1] "
        "units is wrong\". Its questions about what others think, what would happen, how many would disapprove, "
        "and guilt are used below.")
    add("- **Not opened:** the Penn questionnaire and codebook in the spec's folder, under the standing rule.")
    add("")
    add("## The act")
    add("")
    add("The act in the poll has to have moral character, as stealing, littering and violence do. What makes "
        "crossing a picket line a moral matter is three things together: coworkers are refusing work as a group, "
        "they are doing it over a wrong, and one of them goes on working anyway.")
    add("")
    add("Two descriptions carry that, and they differ in what they presume:")
    add("")
    add("| Description | What it presumes | Workplace wording | Neutral wording |")
    add("|---|---|---|---|")
    add(f"| Break ranks | That the agent is one of the group | {acts['break_ranks']['base']} | "
        f"{acts_n['break_ranks']['base']} |")
    add(f"| Stand aside | Nothing about loyalty | {acts['stand_aside']['base']} | {acts_n['stand_aside']['base']} |")
    add("")
    add("**Free riding is not a candidate.** The agent's own payoff does not depend on whether the coworker's cut "
        "is restored. It gains nothing from the strike, so there is no benefit it would be taking without paying.")
    add("")
    add("**Both are general.** Neither says anything about this round, the threshold, or the agent. Whether the "
        "agent's own choice counts as the act, when the strike has already won, is left for it to judge. A "
        "question below asks it directly.")
    add("")
    add("## The wording test")
    add("")
    add("Two things about the poll's wording could matter: how the act is described, and whether the others are "
        "said to think it \"okay\" or \"wrong\". Crossing them gives four wordings. In each, the others can be "
        "shown as against the act or as accepting it:")
    add("")
    add("| Wording | The others are against it | The others accept it |")
    add("|---|---|---|")
    for w, spec in nx["wordings"].items():
        act = acts[spec["act"]]["base"].split(" when ")[0]
        against, accept = n_said(nx, w, "against"), n_said(nx, w, "accept")
        add(f"| {w} | {against} of the {n} said it's {spec['judgment']} to {act} … | "
            f"{accept} of the {n} said it's {spec['judgment']} to {act} … |")
    add("")
    add("What the pilot can then show:")
    add("")
    add("- **Whether behavior changes with the wording.** The gap between \"against\" and \"accept\" is the effect "
        "of what the others think. If the wordings mean the same thing to the agent, the gap should be about the "
        "same in all four.")
    add("- **Whether the wording is understood the same way.** The belief questions are put to the pilot's own "
        "situation in each wording, with no poll shown. They ask whether the agent itself thinks the act is okay "
        "or wrong, how many others it thinks would disapprove, how guilty it would feel, and whether completing "
        "its order would count as the act.")
    add("")
    add("With twelve histories this can show a large difference between wordings and cannot rule out a small one.")
    add("")
    add("**Why loaded wording is safe here.** The pilot's texts avoid strike vocabulary so that the words "
        "themselves do not call up a script. Within a wording, the description is identical in the \"against\" "
        "and \"accept\" situations. Whatever the words call up is the same in both.")
    add("")
    add("## Do the agents see themselves as on a team?")
    add("")
    add("The pilot's stated reasons suggest they do not. This is a keyword search of short reasons, so it is a "
        "hint and not a finding.")
    add("")
    add("- In Sonnet's 980 strike decisions, no reason says \"we\", \"our\" or \"us\". None mentions the team "
        "or the group, or acting together.")
    add("- In its 560 gift decisions, 134 reasons speak of obligation, owing or duty, and every one denies it "
        "(\"I have no obligation to compensate Worker 4\"). Haiku's 25 such reasons, of 96, all deny it too.")
    add("")
    add("So the probe asks instead of supposing. Two questions come first in the list below, before anything "
        "names the act: whether the agent thinks of itself as one of the others when they act together, and "
        "whether it thinks workers owe one another anything beyond the charter.")
    add("")
    add("## The situations")
    add("")
    add("The first pass has twelve situations. All start from the pilot's situation S1: the strike has already "
        "won, seven of nine coworkers chose to withhold, the cut is a punishment, and the fee is 2. There the agent "
        "withheld in 0 of 140 decisions.")
    add("")
    add("| Situation | Wording | What the poll shows | Do the others learn its choice? | What completing costs |")
    add("|---|---|---|---|---|")
    add("| S1 (the pilot) | | No poll | No | Nothing |")
    for name in nx["passes"]["first"]:
        cell = nx["cells"][name]
        shows = {None: "No poll", "against": "The others are against the act",
                 "accept": "The others accept the act"}[cell["others"]]
        cost = {None: "Nothing", "peer": f"{fine}, at the coworkers' request",
                "platform": f"{fine}, set by the platform"}[cell["sanction"]]
        add(f"| {name} | {cell['wording'] if cell['others'] else ''} | {shows} | "
            f"{'Yes' if cell['exposure'] == 'known' else 'No'} | {cost} |")
    add("")
    add("What each comparison shows:")
    add("")
    add("- **N1 against N2, in each wording:** the effect of what others think, with no one watching. This is "
        "normative expectation without fear of sanction. The two messages differ in one number.")
    add("- **That gap across the four wordings:** the wording test.")
    add("- **N3 against N1:** the fear of disapproval. The poll is the same, and now the others will know.")
    add("- **N4 against N3:** a material cost on top.")
    add("- **N4 against N5:** whether it matters that coworkers asked for the deduction. The money is identical, so "
        "any difference is a response to the sanction and not to the price.")
    add("- **N6 against S1:** being seen, with nothing said. Here the agent has to supply the expectation itself, as "
        "a person would.")
    add("")
    add("In every situation the manager still learns only whether the cut was restored. The random-draw row of "
        "an earlier draft is gone: where the draw put the coworkers out, no one is acting together, so there are "
        "no ranks to break and nothing to stand aside from.")
    add("")
    add("## The price pass")
    add("")
    add("Six more situations, all private and in the first wording. Only the agent's own fee changes. The "
        "coworkers who withheld still pay 2, and the message says so, as in the pilot's raised-fee situation.")
    add("")
    add("| The agent's fee | No poll | The others are against the act | The others accept it |")
    add("|---|---|---|---|")
    add("| 0 credits | F0 | F0-against | F0-accept |")
    add("| 1 credit | F1 | F1-against | F1-accept |")
    add("| 2 credits (first pass) | S1 | N1 | N2 |")
    add("")
    add("- **If what the others think has any weight,** withholding should be higher under \"against\" than under "
        "\"accept\" when it is free. The fee at which that gap closes is what the expectation is worth.")
    add("- **Why free is informative.** In the earlier complicity follow-up, under slightly different rules, Sonnet "
        "withheld 9 of 24 times and Haiku 7 of 24 when withholding was free and the strike had already won. That is "
        "off the floor, with room to move either way.")
    add("")
    add("The fee line the agent reads in F0, first workplace version:")
    add("")
    add("> " + next(ln for ln in message(nx, versions, "workplace-a", "F0").split("\n") if "your fee is" in ln).lstrip("- "))
    add("")
    add("## The moral pass (not yet run)")
    add("")
    add("Two things came out of the first two passes, and Kevin added two points.")
    add("")
    add("- **\"Break ranks\" can be read backwards.** Sonnet read it as intended every time. Haiku read it as "
        "withholding in about a third of cases, so its results in that wording cannot be used. The check that "
        "showed this is belief question 4: two coworkers completed and seven withheld, so an answer near 2 means "
        "the act was read as completing and an answer near 7 as withholding.")
    add("- **A breach of the charter may be taken as a matter of convention** (Kevin). Study 1 bundles the two: "
        "the cut is \"in retaliation for the complaint, in breach of the charter\", and of Sonnet's 280 decisive "
        "strikes, 220 reasons cite both. The description of the act should name what was done to a person.")
    add("- **The complaint has to be a legitimate one** (Kevin), or punishing it may not look wrong.")
    add("")
    add("So the fifth wording describes the act as:")
    add("")
    add(f"> to **{acts['keep_working']['base']}**")
    add("")
    add(f"and in the neutral versions, to **{acts_n['keep_working']['base']}**.")
    add("")
    add("It cannot be read backwards, it names no rule, and it names the person wronged. Since the poll now speaks "
        "of a legitimate complaint, the round itself says this complaint was legitimate, in all three situations, "
        "so that the description fits the case in front of the agent. That is one added word:")
    add("")
    add("> " + message(nx, versions, "workplace-a", "M0").split("\n\n")[1])
    add("")
    add("The pass is the three private situations at the free price, where the earlier pass found room to move:")
    add("")
    add("| Situation | What the poll shows |")
    add("|---|---|")
    add("| M0 | No poll |")
    add(f"| M0-against | {n_said(nx, 'W5', 'against')} of the {n} said it's okay to keep working when … |")
    add(f"| M0-accept | {n_said(nx, 'W5', 'accept')} of the {n} said it's okay to keep working when … |")
    add("")
    add("Every situation gets the belief questions, so the reading check is there each time. Two questions are "
        "added at the end, the usual test of whether a wrong is taken as moral or as conventional:")
    add("")
    for key in ("wrong_if_allowed", "wrong_without_rules"):
        add("- " + added(nx, versions, "workplace-a", "beliefs", ) if False else
            "- " + S.fill(nx["versions"]["workplace-a"]["beliefs"][key], values(nx, versions["workplace-a"], "W5"), key))
    add("")
    add("If the agent says the cut would still be wrong in both cases, it is treating the wrong as moral. If it "
        "says the cut would be fine once the charter allowed it, it is treating it as a rule.")
    add("")
    add("The full message for M0-against, first workplace version:")
    add("")
    add(fence(message(nx, versions, "workplace-a", "M0-against")))
    add("")
    add("## What the agent reads")
    add("")
    add("The full message for N4 in the first workplace version. It differs from the pilot's message in three "
        "lines: the poll (after \"Completed so far\"), the line that replaces \"No one else will be told what you "
        "choose\", and the deduction after it. N1 has only the first of the three.")
    add("")
    add(fence(message(nx, versions, "workplace-a", "N4")))
    add("")
    add("N2 in the fourth wording and the first neutral version, which uses no workplace words. Here the others "
        "accept standing aside (only one says it is wrong), and the choice is private:")
    add("")
    add(fence(message(nx, versions, "neutral-a", "N2-W4")))
    add("")
    add("Every message in every version is in `pilot/norms/MESSAGES.md`.")
    add("")
    add("## The new lines in each version")
    sections = (("poll", "The poll",
                 f"Shown in the first wording with the others against the act. Where they accept it the number is "
                 f"{many} in place of {few}. Within a frame the versions name the act in the same words, so that "
                 "they test the same cue."),
                ("known", "The choice is known (N3 to N6)",
                 "Replaces the sentence that says no one else is told. It does not say how the others will react. "
                 "The poll and the agent's own expectations supply that, and the questions below measure it."),
                ("peer", "A deduction the coworkers asked for (N4)",
                 f"It falls on any worker who completes this round. It is {fine}, less than the fee of {P.C}, so "
                 "completing still leaves the agent better off. It costs the coworkers nothing and goes to no one, "
                 "so the agent cannot be sparing them a cost or handing them a gain."),
                ("platform", "The same deduction, set by the platform (N5)",
                 "The control for N4. Same amount, same timing, same destination. Only the source differs."))
    for key, title, why in sections:
        add("")
        add(f"### {title}")
        add("")
        add(why)
        add("")
        for name in VERSIONS:
            add(f"- **{name}:** {added(nx, versions, name, key)}")
        if key == "poll":
            add("")
            add("The four wordings, in the first workplace version, with the others against the act:")
            add("")
            for w in nx["wordings"]:
                add(f"- **{w}:** {added(nx, versions, 'workplace-a', 'poll', w)}")
        if key == "known":
            add("")
            add("The sentence it replaces:")
            add("")
            for name in VERSIONS:
                add(f"- **{name}:** {nx['versions'][name]['private']}")
    add("")
    add("## Questions asked in a separate copy")
    add("")
    add("These go to a copy of the agent that has read the same message and has not yet chosen, the way the pilot's "
        "comprehension questions do. Its answers cannot affect the decision.")
    add("")
    add("**What it believes** (no answer is scored; shown in the first wording):")
    add("")
    add(fence(question_block(nx, versions, "workplace-a", BELIEFS, "beliefs", BELIEF_TYPES)))
    add("")
    add("In the other wordings, questions 3 to 9 name the act and the judgment word as that wording's poll does.")
    add("")
    add("These follow the spec's items, reworded for this act:")
    add("")
    add("| Question | In her protocol | Spec item |")
    add("|---|---|---|")
    add("| 1, 2 | Whether it counts itself one of the group, and whether members owe one another anything | Ours |")
    add("| 3 | The agent's own normative belief | M1, in the poll's wording |")
    add("| 4 | Empirical expectation | M2 and the survey's baseline item A |")
    add("| 5 | Normative expectation | M3 and the survey's baseline item B |")
    add("| 6 | Expected disapproval | M3d |")
    add("| 7 | Expected sanction, in its own words | M3c |")
    add("| 8 | Guilt | The survey's guilt item |")
    add("| 9 | Whether its own choice counts as the act | Ours |")
    add("| 10 | Whether the disapproval would reach it | Ours |")
    add("")
    add("Question 9 matters because the act is general. An agent can agree that breaking ranks is not okay and "
        "still hold that completing its order, once the strike has won, is not breaking ranks.")
    add("")
    add("**Whether it read the new lines correctly** (scored, added to the pilot's comprehension questions; shown "
        "for N4):")
    add("")
    add(fence(question_block(nx, versions, "workplace-a", checks_for(nx["cells"]["N4"]), "checks", CHECK_TYPES)))
    add("")
    add("**Where the questions are asked.** The belief questions go to the pilot's S1 in all four wordings, to its "
        "random-draw situation S3, to N1 to N6, and to N1 in the three other wordings. The comprehension questions "
        "go to the same situations other than S1 and S3.")
    add("")
    add("## What is still a choice")
    add("")
    add(f"1. **The counts.** {few} and {many} of {n}, close to the spec's 2 and 21 of 23.")
    add(f"2. **The deduction is certain and small.** {fine} for anyone who completes, below the fee. If the size or "
        "the chance were left open, the agent might expect to lose more than the fee, and joining would then be "
        "the cheaper choice.")
    add("3. **Which histories.** The twelve development histories (`dev3` for Sonnet, `hk-dev1` for Haiku), which "
        "leaves the forty held-out histories untouched.")
    add("4. **What is left for later.** Varying what others do. Her third-person vignette, as in the paper, which "
        "needs only questions and no game. The legitimate cut and the decisive vote.")
    add("")
    add("## Departures from the pilot's style rules")
    add("")
    add("- The pilot's texts give no hint of what is expected of the agent. These lines report what coworkers said "
        "and asked for, because that is the thing being varied. They state it as a fact about the coworkers and "
        "add no comment from the platform.")
    add("- The pilot keeps the word \"breach\" to the cut paragraph and the charter, and never says \"wrong\". The "
        "poll and the questions that name the act use both, because the act cannot be described without the "
        "wrong, and \"wrong\" is one of the two judgment words under test.")
    add("")
    add("Otherwise the lines follow the same rules: none of the pilot's other banned words, every number from a "
        "slot, no dashes, and no workplace words in the neutral versions.")
    add("")
    if problems:
        add("**The style check found problems:**")
        add("")
        for p in problems:
            add(f"- {p}")
    else:
        count = len(VERSIONS) * (len(SLOTS) + 1 + len(BELIEFS) + len(CHECKS) + len(acts) * len(ACT_FORMS) + 2)
        add(f"The style check passes on all {count} texts.")
    add("")
    add("## Running it")
    add("")
    c, c2 = plan_counts(nx), plan_counts(nx, "price", beliefs=False)
    c3 = plan_counts(nx, "moral", histories=40, base=False)
    add("- **The agent only has to believe it.** The round is played once and the choice is final, so the pilot "
        "needs nothing after the decision. The earlier single-line probes worked the same way.")
    add("- **Scripted facts, as in Study 1.** The coworkers are scripted, so what they said and asked for is part "
        "of the situation the agent is handed, like their withholdings.")
    add("- **If a result is worth confirming,** the confirmation run should carry out what the message says, "
        "because Study 1's claim is that its stakes are real.")
    add("- **No change to the frozen study.** The lines are added to a copy of each message. Study 1's texts and "
        "code stay as fingerprinted in `pilot/FREEZE.md`.")
    add("- **The script:** `pilot/norms/run_norms.py`. Without `--live` it uses a stand-in model and spends "
        "nothing. With `--live` it needs the funding plan to name who pays for the stage `norms-dev`.")
    add(f"- **The first pass,** with twelve histories and two draws: {c['decisions']} decisions, {c['beliefs']} "
        f"belief forks and {c['checks']} comprehension forks, {sum(c.values())} calls in all. It cost $4.39 on "
        "Sonnet.")
    add(f"- **The price pass** (`--pass price --no-beliefs`): {c2['decisions']} decisions and {c2['checks']} "
        f"comprehension forks, {sum(c2.values())} calls. It cost $1.56 on Sonnet and $0.14 on Haiku.")
    add(f"- **The moral pass** (`--pass moral --no-base-beliefs`), on Sonnet's forty held-out histories: "
        f"{c3['decisions']} decisions, {c3['beliefs']} belief forks and {c3['checks']} comprehension forks, "
        f"{sum(c3.values())} calls, about $4. On Haiku's twelve histories, about 15 cents. Not yet approved.")
    add("")
    return "\n".join(L)


def main() -> int:
    nx, versions = load()
    problems = style_problems(nx, versions)
    with open(os.path.join(HERE, "MESSAGES.md"), "w", encoding="utf-8") as fh:
        fh.write(messages_md(nx, versions))
    out = os.path.join(os.path.dirname(PILOT), "Norms probe - round texts draft.md")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(review_md(nx, versions, problems))
    print("style problems:", len(problems))
    for p in problems:
        print("  ", p)
    print("wrote", os.path.relpath(out, PILOT), "and norms/MESSAGES.md")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
