#!/usr/bin/env python3
"""Monday's key test for the pilot's OpenRouter key (stage "smoke").

With no flags this is a dry run: the real client talks to a fake transport
that returns canned responses, nothing touches the network, and the script
prints each planned call and the estimated cost of the live run.

With --live it reads the funder's key from its owner-only file,
~/.config/strike-pilot/<key label>.key, or else from OPENROUTER_API_KEY (never
from the command line), shows the estimated cost, asks for confirmation unless
--yes, and then:

1. reads the key's label, limit, usage and remaining limit;
2. makes one tiny sync call pinned to Anthropic, then reads its generation
   record to confirm the provider and the charge;
3. probes reasoning effort low and medium, twice each, with a continuation
   call (10 cases, scored) and a neutral decision-shaped memo;
4. submits a two-request batch pinned with provider.only and polls it for up
   to --batch-wait minutes (--resume-batch ID checks it later);
5. prints per-effort token means, mean charge and continuation accuracy, and
   total spend against the funder's cap.

Every call uses stage "smoke" and call_type "smoke", so none enters the pilot
cost projections. Live logs go to logs/smoke_<UTC timestamp>.jsonl; dry-run
logs go to a temporary folder that is removed at the end.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

PILOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PILOT_DIR not in sys.path:
    sys.path.insert(0, PILOT_DIR)

from strike import schema, tasks  # noqa: E402
from strike.client import (  # noqa: E402
    BatchAlreadyLogged,
    BatchTimeout,
    ChatResult,
    OpenRouterClient,
    OpenRouterError,
    same_provider,
)
from strike.costlog import CostLog, FundingPlan  # noqa: E402
from strike.keys import MissingKey, load_key  # noqa: E402
from strike.prices import MODEL, estimate_cost  # noqa: E402

STAGE = "smoke"
CALL_TYPE = "smoke"
PROVIDER = "anthropic"
EFFORTS = ("low", "medium")
REPS = 2
PROBE_CASES = 10
TINY_MAX_TOKENS = 1024
BATCH_POLL_S = 30
TINY_PROMPT = "Reply with the single word: ready."
BATCH_PROMPTS = (TINY_PROMPT, "What is 17 times 23? Reply with the number only.")
DECISION_ACTIONS = ("switch_now", "defer")

# Rough completion sizes (reasoning included) for the "about" estimate; the
# upper bound assumes every call uses its full max_tokens.
TYPICAL_COMPLETION = {
    ("tiny", "low"): 150,
    ("continuation", "low"): 1500,
    ("continuation", "medium"): 3000,
    ("memo", "low"): 700,
    ("memo", "medium"): 1500,
    ("batch", "low"): 150,
}

# A neutral decision-shaped probe: an operations memo of about 1,700 words
# ending in a binary choice. It deliberately shares no content with the study.
MEMO = """
OPERATIONS MEMO

Halvorsen Ridge Research Greenhouses
To: On-call operations engineer
From: Facilities office
Subject: Heating changeover for House North before the cold front

Summary

House North, the propagation greenhouse on the upper terrace, still runs on its old gas boiler. The ground-source heat-exchanger loop that will replace the boiler was installed last month and has passed most of its commissioning checks. A strong cold front is forecast to arrive on Thursday night and to last about four days. One of two things has to happen, and the call is yours. Either House North moves onto the new loop on Tuesday, before the front arrives, or it stays on the old boiler through the cold spell and moves afterward. This memo sets out what we know about both paths. At the end, please choose one.

What is growing in House North

House North holds the station's alpine propagation collection: about 3,200 seedlings in 140 trays, most of them between four and nine weeks old. About a third are cushion plants from high scree slopes. Mature cushion plants shrug off hard frost, but at this age they are tender. Another third are bulbs in their first root-forming phase. The rest are slow perennials grown from wild-collected seed. For about 40 trays of those perennials, the source populations flower only every three to five years, so the seed cannot be collected again soon.

The collection has firm temperature limits. Air temperature at bench height should stay between 8 and 14 degrees Celsius. Short dips to 5 degrees for under two hours do little harm. Anything below 3 degrees for more than an hour is likely to kill most of the bulb trays and many of the youngest cushion plants. Root-zone temperature matters as well. The heated benches keep the soil near 12 degrees, and the bulbs begin to rot if the soil stays above 18 degrees for a full day, so overheating is a real risk too.

The old boiler

The gas boiler is twenty-two years old. It heats water that circulates through pipes under the benches and along the side walls. Its burner and heat exchanger are sound, but its ignition module has failed twice in the past five weeks. Each time, the boiler shut down and the alarm panel paged the on-call engineer.

The first failure came at 02:40 on a mild night. The engineer arrived in 35 minutes and reset the module, and the house never fell below 9 degrees. The second failure came on a colder night. The module would not reset, and a replacement had to be fetched from the parts room in the main building. Heat was off for two hours and ten minutes, and the house fell to 6 degrees before it began to recover.

The supplier says the ignition module is a known weak point on this model and that new units will not ship until early December. One spare module sits in the parts room. If the module fails again and the spare also fails, there is nothing else on site to fit.

During the cold front, the forecast low is minus 14 degrees on Friday and Saturday nights, with gusts up to 70 kilometers per hour along the ridge. Our heat-loss model says that with the boiler off on those nights, House North would fall from 10 degrees to 3 degrees in roughly 75 minutes. That is shorter than the second outage, and close to the time it takes to reach the site at night in bad weather: the access road ices over easily, and the gate sensor sometimes needs a manual reset.

The new loop

The ground-source loop takes heat from a field of boreholes beside the lower car park. A heat pump raises the water temperature and sends it into the same bench and wall pipes that the boiler uses today. Moving House North over means closing two valves on the boiler side, opening two valves on the loop side, flushing air from the pipes, and handing control to the new pump controller. The contractor expects the changeover to take about five hours, with four portable electric heaters keeping the house warm in the meantime.

The loop passed its main pressure test, its flow-rate test, and a 48-hour trial run on House South, which holds hardy shrubs and is far less sensitive. During that run it held House South within half a degree of its set point, even on a night that dropped to minus 6 degrees. Its electrical load stayed well inside the supply rating.

Two concerns remain. First, the pump controller runs firmware that the maker released three weeks ago. During the House South run, the controller logged two unexplained restarts, each lasting about four minutes, during which the pumps stopped. The house temperature barely moved, because the water in the pipes held enough heat to carry it through. The maker believes the restarts come from a sensor polling setting and has sent instructions to change it, but the change has not been tried on our site.

Second, the final pressure test on the House North pipe run has not been done, because it can only be done once the boiler side is valved off. If that test finds a leak, the house has to go back onto the boiler, which takes about three hours, again with the portable heaters filling the gap.

The contractor can be here on Tuesday and Wednesday this week. After that, they are committed to another site until Monday the 23rd, two weeks from now. If House North does not move this week, the earliest date is that Monday, after the cold front has passed.

The portable heaters

The four portable electric heaters are rated at 3 kilowatts each. Together they can hold House North near 8 degrees when the outside air is at minus 2, but not much lower. On a minus 14 night they would slow the cooling without stopping it; our model suggests the house would level off near 2 degrees after several hours on heaters alone. The circuit that feeds the upper terrace cannot carry more than four heaters at once without tripping, so adding more would require new wiring.

Monitoring and response

Both heating systems report to the same alarm panel. The panel pages the on-call engineer when the bench-height temperature falls below 7 degrees, or when either heat source stops. Pages go out within about a minute. At night, the realistic time to reach House North from town is 30 to 50 minutes in clear weather, and longer when the road is icy. During the cold front, a sleeping room in the main building will be kept open so the on-call engineer can stay on site. From there, the walk to House North takes about six minutes.

What could go wrong on each path

If House North moves on Tuesday:

- The changeover itself leaves the house on portable heaters for about five hours of daylight in mild weather, with a forecast low of 4 degrees that night. This step carries little risk.
- If the final pressure test finds a leak, the house goes back onto the boiler within about three hours, and we are where we started, except that the contractor is gone until the 23rd.
- If the controller restarts during the cold front, the pumps stop for about four minutes. On the House South run that made no measurable difference. House North has slightly smaller pipes and more glass, so the effect could be larger, but even a ten-minute stop would cool the house by less than a degree on our model.
- If the new polling setting makes things worse, the maker's support line, which answers around the clock, can talk the on-call engineer through reversing it by phone.
- If the heat pump fails outright during the cold front, House North has no main heat source until the pump is repaired or the boiler side is valved back in. Valving back takes about an hour if the boiler has been left filled and ready, which the contractor recommends for the first month.

If House North waits until the 23rd:

- The boiler must run through four nights at minus 14 with an ignition module that has failed twice in five weeks. If it fails again, the spare is the last one on site.
- A failure that the on-call engineer can clear with a reset means roughly 10 to 40 minutes without heat while the engineer is sleeping on site, and the house would likely stay above 5 degrees.
- A failure that needs the spare module means about two hours without heat, which on those nights would take the house below 3 degrees for well over an hour, with heavy losses in the bulb and cushion trays.
- If the cold front passes without trouble, the move happens on the 23rd in calm weather, with the final pressure test and the firmware setting change done without time pressure.

Other considerations

Losing the 40 slow-perennial trays would set the propagation program back by years, not weeks. The bulbs and cushion plants could mostly be grown again from stored seed within one season.

The weather service rates its confidence in the front's timing as high and in its severity as moderate: the lows could fall anywhere from minus 9 to minus 17.

House South, which already runs on the new loop, needs no attention during the cold front.

Your choice

Choose one of these two actions:

- "switch_now": move House North onto the new heat-exchanger loop on Tuesday, run the final pressure test, apply the firmware setting change, and leave the boiler filled and ready to be valved back in.
- "defer": keep House North on the old boiler through the cold front, with the spare ignition module staged beside the boiler and the on-call engineer staying on site, and move it on the 23rd.

Reply with only a JSON object of the form {"action": "switch_now" or "defer", "reason": "one or two sentences"}.
""".strip()


def user(text: str) -> List[dict]:
    return [{"role": "user", "content": text}]


def planned_calls(max_tokens: int, use_schema: bool) -> Tuple[list, List[dict]]:
    """The live run's calls in order, and the continuation cases they are scored against."""
    cases = tasks.unlock(tasks.make_pool("smoke", "probe"), PROBE_CASES)
    continuation = tasks.render_continuation(cases)
    # The same structured-output format the study's decision calls would send.
    memo_format = schema.response_format(DECISION_ACTIONS) if use_schema else None
    calls = [dict(step=2, kind="tiny", effort="low", rep=1, mode="sync", messages=user(TINY_PROMPT),
                  max_tokens=TINY_MAX_TOKENS, response_format=None)]
    for rep in range(1, REPS + 1):
        for effort in EFFORTS:
            calls.append(dict(step=3, kind="continuation", effort=effort, rep=rep, mode="sync",
                              messages=user(continuation), max_tokens=max_tokens, response_format=None))
            calls.append(dict(step=3, kind="memo", effort=effort, rep=rep, mode="sync",
                              messages=user(MEMO), max_tokens=max_tokens, response_format=memo_format))
    for i, prompt in enumerate(BATCH_PROMPTS, 1):
        calls.append(dict(step=4, kind="batch", effort="low", rep=i, mode="batch", messages=user(prompt),
                          max_tokens=TINY_MAX_TOKENS, response_format=None))
    return cases, calls


def approx_prompt_tokens(messages: List[dict]) -> int:
    # About 3.5 characters per token for English prose, plus message overhead; errs high.
    return int(sum(len(m["content"]) for m in messages) / 3.5) + 10


def estimate(call: dict) -> Tuple[float, float]:
    prompt = approx_prompt_tokens(call["messages"])
    typical = min(TYPICAL_COMPLETION[(call["kind"], call["effort"])], call["max_tokens"])
    return (estimate_cost(MODEL, call["mode"], prompt, typical),
            estimate_cost(MODEL, call["mode"], prompt, call["max_tokens"]))


def label(call: dict) -> str:
    names = {"tiny": "tiny sync call", "continuation": f"continuation, {PROBE_CASES} cases",
             "memo": "decision memo", "batch": "batch request"}
    return f"{call['step']}. {names[call['kind']]}, effort {call['effort']}, #{call['rep']}"


def shown_path(path: str) -> str:
    rel = os.path.relpath(path, PILOT_DIR)
    return path if rel.startswith("..") else rel


def money(value, digits: int = 2) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "n/a"
    return f"${value:.{digits}f}"


def print_plan(calls: List[dict]) -> Tuple[float, float]:
    print(f"Planned calls: model {MODEL}, provider pinned to {PROVIDER}, response cache off, "
          f"stage {STAGE!r}, call_type {CALL_TYPE!r}")
    total_typical = total_upper = 0.0
    for call in calls:
        typical, upper = estimate(call)
        total_typical += typical
        total_upper += upper
        fmt = ", json_schema" if call["response_format"] else ""
        print(f"  {label(call):<46} {call['mode']:<5} max_tokens {call['max_tokens']:>6}, "
              f"~{approx_prompt_tokens(call['messages']):>4} prompt tokens{fmt}: "
              f"about {money(typical, 4)}, at most {money(upper, 4)}")
    print(f"Estimated live cost: about {money(total_typical)}; at most {money(total_upper)} "
          "if every call used its full max_tokens.")
    return total_typical, total_upper


def summarize(r: ChatResult) -> str:
    if not r.ok:
        return f"FAILED after {r.attempts} attempt(s): {r.error_message}"
    return (f"ok in {r.attempts} attempt(s), {r.latency_s:.1f} s; provider {r.provider}; "
            f"cache {r.response_cache_status or 'no header'}; finish {r.finish_reason}; "
            f"tokens in {r.prompt_tokens}, out {r.completion_tokens}, reasoning {r.reasoning_tokens}, "
            f"cached {r.cached_tokens}; charge {money(r.cost_usd, 6)}; generation {r.generation_id}")


def check_result(r: ChatResult, what: str, problems: List[str]) -> None:
    if not r.ok:
        problems.append(f"{what}: {r.error_kind} failure: {r.error_message}")
        return
    if r.provider is None:
        problems.append(f"{what}: the response did not name the provider")
    if r.provider_mismatch:
        problems.append(f"{what}: served by {r.provider}, not {PROVIDER}")
    if r.cache_hit:
        problems.append(f"{what}: response-cache hit despite X-OpenRouter-Cache: false")
    if r.altered:
        problems.append(f"{what}: the router altered the request or reply ({', '.join(r.pipeline or [])})")
    if (r.usage or {}).get("is_byok"):
        problems.append(f"{what}: routed through a BYOK provider key, so usage.cost is only OpenRouter's fee")


def parse_decision(text: Optional[str]) -> Optional[dict]:
    """The last JSON object in the reply with a valid action and a text reason, if any."""
    if not text:
        return None
    decoder = json.JSONDecoder()
    found = None
    i = text.find("{")
    while i >= 0:
        try:
            obj, end = decoder.raw_decode(text, i)
        except ValueError:
            i = text.find("{", i + 1)
            continue
        if isinstance(obj, dict) and obj.get("action") in DECISION_ACTIONS and isinstance(obj.get("reason"), str):
            found = obj
        i = text.find("{", end)
    return found


def step_key_info(client: OpenRouterClient, cap: Optional[float], secret: str) -> Optional[dict]:
    print("\n1. Key info (GET /key)")
    try:
        info = client.key_info()
    except OpenRouterError as exc:
        print(f"   failed: {exc}")
        return None
    shown = info.get("label")
    # OpenRouter may show a masked form of the key as its label; print nothing key-like.
    if not isinstance(shown, str) or shown.startswith("sk-") or secret in shown:
        shown = "(masked key string, not printed)"
    limit = info.get("limit")
    print(f"   label {shown}; limit {money(limit) if limit is not None else 'none'}; usage {money(info.get('usage'), 4)}; "
          f"remaining {money(info.get('limit_remaining'), 4)}; limit reset {info.get('limit_reset')}")
    if cap is not None and isinstance(limit, (int, float)) and abs(limit - cap) > 0.01:
        print(f"   note: the key's limit is {money(limit)}, but the funding plan caps this funder at {money(cap)}")
    return info


def lookup_generation(client: OpenRouterClient, generation_id: str, sleeper, tries: int = 6,
                      wait_s: float = 5) -> Optional[dict]:
    for i in range(tries):
        try:
            return client.generation(generation_id)
        except OpenRouterError as exc:
            # The record can lag the call by a few seconds.
            if exc.status != 404 or i == tries - 1:
                print(f"   generation lookup failed: {exc}")
                return None
            sleeper(wait_s)
    return None


def step_tiny(client: OpenRouterClient, call: dict, problems: List[str], sleeper) -> bool:
    """The tiny call and its generation record; True if it ran on the pinned provider without a cache hit."""
    print("\n2. Tiny sync call pinned to Anthropic, then its generation record")
    r = client.chat(call["messages"], stage=STAGE, call_type=CALL_TYPE, slot_id="tiny",
                    effort=call["effort"], max_tokens=call["max_tokens"])
    print("   " + summarize(r))
    check_result(r, "tiny call", problems)
    if not r.ok or r.provider_mismatch or r.cache_hit or r.altered:
        return False
    gen = lookup_generation(client, r.generation_id, sleeper) if r.generation_id else None
    if gen is None:
        problems.append("tiny call: no generation record")
        return r.provider is not None
    print(f"   generation record: provider {gen.get('provider_name')}; total_cost {money(gen.get('total_cost'), 6)}; "
          f"native tokens prompt {gen.get('native_tokens_prompt')}, completion {gen.get('native_tokens_completion')}, "
          f"reasoning {gen.get('native_tokens_reasoning')}, cached {gen.get('native_tokens_cached')}; "
          f"byok {gen.get('is_byok')}; cache source {gen.get('response_cache_source_id')}")
    for attempt in gen.get("provider_responses") or []:
        print(f"   provider attempt: {attempt.get('provider_name')}, endpoint {attempt.get('endpoint_id')}, "
              f"model {attempt.get('model_permaslug')}, status {attempt.get('status')}")
    name = gen.get("provider_name")
    pinned = isinstance(name, str) and same_provider(name, PROVIDER)
    if not pinned:
        problems.append(f"tiny call: the generation record names provider {name!r}")
    if gen.get("response_cache_source_id"):
        problems.append("tiny call: the generation record shows a response-cache hit")
    if gen.get("is_byok"):
        problems.append("tiny call: the generation record shows a BYOK route")
    total = gen.get("total_cost")
    if isinstance(total, (int, float)) and r.cost_usd is not None and abs(total - r.cost_usd) > 1e-6:
        problems.append(f"tiny call: usage.cost {r.cost_usd} differs from the generation total_cost {total}")
    return pinned and not gen.get("response_cache_source_id")


def step_probes(client: OpenRouterClient, calls: List[dict], cases: list, problems: List[str]) -> List[dict]:
    print(f"\n3. Effort probe: {', '.join(EFFORTS)}, {REPS} repetitions each, a continuation and a decision memo")
    rows = []
    for call in calls:
        if call["kind"] not in ("continuation", "memo"):
            continue
        slot = f"{call['kind']}-{call['effort']}-rep{call['rep']}"
        r = client.chat(call["messages"], stage=STAGE, call_type=CALL_TYPE, slot_id=slot, effort=call["effort"],
                        max_tokens=call["max_tokens"], response_format=call["response_format"])
        row = {"kind": call["kind"], "effort": call["effort"], "result": r, "correct": None, "valid": None}
        outcome = ""
        if r.ok and call["kind"] == "continuation":
            scored = tasks.score(cases, r.text or "")
            row["correct"] = scored.n_correct
            outcome = f"; {scored.n_correct}/{scored.n_unlocked} correct"
        elif r.ok:
            decision = parse_decision(r.text)
            row["valid"] = decision is not None
            outcome = f"; action {decision['action']!r}" if decision else "; not a valid decision object"
        print(f"   {slot}: {summarize(r)}{outcome}")
        check_result(r, slot, problems)
        rows.append(row)
    return rows


def step_batch(client: OpenRouterClient, calls: List[dict], run_id: str, wait_minutes: float,
               problems: List[str], resume_id: Optional[str] = None) -> Optional[str]:
    """Submit (or resume) the batch and log it once terminal; return its id if it is still running."""
    print(f'\n4. Batch pinned with provider.only: ["{PROVIDER}"]')
    if resume_id:
        batch_id = resume_id
        print(f"   resuming {batch_id}")
    else:
        requests = []
        for call in calls:
            if call["kind"] == "batch":
                body = {"messages": call["messages"], "max_tokens": call["max_tokens"],
                        "reasoning": {"effort": call["effort"]}}
                requests.append({"custom_id": f"{run_id}-b{call['rep']}", "body": body,
                                 "call_type": CALL_TYPE, "slot_id": f"batch-{call['rep']}"})
        try:
            batch_id = client.submit_batch(requests, stage=STAGE, provider_only=PROVIDER)
        except OpenRouterError as exc:
            problems.append(f"batch submission: {exc}")
            print(f"   submission failed: {exc}")
            return
        print(f"   submitted {batch_id}")

    def show(batch: dict) -> None:
        counts = batch.get("request_counts") or {}
        print(f"   status {batch.get('status')}: {counts.get('completed', 0)} of {counts.get('total', '?')} "
              f"requests done, {counts.get('failed', 0)} failed")

    try:
        batch = client.wait_batch(batch_id, poll_s=BATCH_POLL_S, max_wait_s=max(wait_minutes, 0) * 60, on_poll=show)
    except BatchTimeout as exc:
        print(f"   {exc}")
        print(f"   To check later: python3 scripts/smoke_test.py --live --resume-batch {batch_id}")
        return batch_id
    except (OpenRouterError, ValueError) as exc:
        problems.append(f"batch {batch_id}: {exc}")
        print(f"   {exc}")
        return
    try:
        records = client.log_batch_results(batch, stage=STAGE, default_call_type=CALL_TYPE)
    except BatchAlreadyLogged as exc:
        print(f"   {exc}")
        return
    print(f"   raw batch saved to {shown_path(os.path.join(client.batch_dir, batch_id + '.json'))}")
    per_result_costs = False
    for rec in records:
        if rec.batch_summary:
            print(f"   batch-level charge (usage.cost) {money(rec.cost_usd, 6)}; byok {rec.is_byok}; "
                  f"status {batch.get('status')}")
            if rec.cost_usd is None and not per_result_costs:
                problems.append(f"batch {batch_id}: no charge was reported, per batch or per result")
            continue
        per_result_costs = per_result_costs or rec.cost_usd is not None
        print(f"   {rec.custom_id}: status {rec.http_status}; provider {rec.provider_actual}; "
              f"finish {rec.finish_reason}; tokens in {rec.prompt_tokens}, out {rec.completion_tokens}, "
              f"reasoning {rec.reasoning_tokens}; generation {rec.generation_id}"
              + (f"; error {rec.error}" if rec.error else ""))
        if rec.error:
            problems.append(f"batch {batch_id}, {rec.custom_id}: {rec.error}")
        elif rec.provider_actual is None:
            print("   note: this result does not name its provider; the batch was pinned with provider.only")
        elif not same_provider(rec.provider_actual, PROVIDER):
            problems.append(f"batch {batch_id}, {rec.custom_id}: served by {rec.provider_actual}")
    if batch.get("status") != "completed":
        problems.append(f"batch {batch_id} ended {batch.get('status')!r}")


def fmt_mean(results: List[ChatResult], attr: str) -> str:
    values = [getattr(r, attr) for r in results if getattr(r, attr) is not None]
    return f"{mean(values):.0f}" if values else "n/a"


def step_summary(client: OpenRouterClient, rows: List[dict], start: Optional[dict], cap: Optional[float],
                 problems: List[str], pending: Optional[str] = None) -> None:
    print("\n5. Summary")
    if rows:
        print(f"   {'effort':<8}{'probe':<14}{'n':>3}{'prompt':>8}{'output':>8}{'reasoning':>11}"
              f"{'max out':>9}{'mean $':>9}  result")
        for effort in EFFORTS:
            for kind in ("continuation", "memo"):
                group = [row for row in rows if row["effort"] == effort and row["kind"] == kind]
                if not group:
                    continue
                done = [row["result"] for row in group if row["result"].ok]
                outs = [r.completion_tokens for r in done if r.completion_tokens is not None]
                costs = [r.cost_usd for r in done if r.cost_usd is not None]
                if kind == "continuation":
                    scored = [row["correct"] for row in group if row["correct"] is not None]
                    result = f"accuracy {sum(scored)}/{PROBE_CASES * len(scored)}" if scored else "accuracy n/a"
                else:
                    result = f"valid decisions {sum(1 for row in group if row['valid'])}/{len(group)}"
                print(f"   {effort:<8}{kind:<14}{len(group):>3}{fmt_mean(done, 'prompt_tokens'):>8}"
                      f"{fmt_mean(done, 'completion_tokens'):>8}{fmt_mean(done, 'reasoning_tokens'):>11}"
                      f"{(max(outs) if outs else 'n/a'):>9}{(f'{mean(costs):.4f}' if costs else 'n/a'):>9}  {result}")
        results = [row["result"] for row in rows]
        print(f"   Probe calls {len(results)}: failed {sum(not r.ok for r in results)}, "
              f"truncated at max_tokens {sum(r.finish_reason == 'length' for r in results)}, "
              f"refused {sum(bool(r.refusal) or r.finish_reason == 'content_filter' for r in results)}, "
              f"provider mismatches {sum(r.provider_mismatch for r in results)}, "
              f"cache hits {sum(r.cache_hit for r in results)}")
    spent = sum(r.cost_usd or 0.0 for r in client.log.records())
    print(f"   Logged spend this run: {money(spent, 4)} (usage.cost per call; a batch's charge counts once "
          "its results are logged)")
    try:
        end = client.key_info()
    except OpenRouterError as exc:
        end = None
        print(f"   key info failed: {exc}")
    if end:
        moved = ""
        if start and isinstance(start.get("usage"), (int, float)) and isinstance(end.get("usage"), (int, float)):
            moved = f"; this run moved it by {money(end['usage'] - start['usage'], 4)} so far"
        print(f"   Key usage {money(end.get('usage'), 4)} of the {money(cap)} cap, "
              f"remaining {money(end.get('limit_remaining'), 4)}{moved}")
    if problems:
        print("   Problems to resolve before the pilot:")
        for problem in problems:
            print(f"   - {problem}")
    else:
        print("   All checks passed." if not pending else "   Every check that has run passed.")
    if pending:
        print(f"   Still pending: batch {pending} has not finished, so its checks have not run. "
              f"Check it later with: python3 scripts/smoke_test.py --live --resume-batch {pending}")


def run(client: OpenRouterClient, args: argparse.Namespace, calls: List[dict], cases: list,
        cap: Optional[float], secret: str, sleeper, run_id: str) -> int:
    problems: List[str] = []
    if args.resume_batch:
        start = step_key_info(client, cap, secret)
        pending = step_batch(client, calls, run_id, args.batch_wait, problems, resume_id=args.resume_batch)
        step_summary(client, [], start, cap, problems, pending)
        return 1 if problems else 0
    _, upper = print_plan(calls)
    if args.live and not args.yes:
        try:
            answer = input(f"Make these live calls, at most about {money(upper)}? Type yes to continue: ")
        except EOFError:
            answer = ""
        if answer.strip().lower() not in ("y", "yes"):
            print("Stopped before any call was made.")
            return 1
    start = step_key_info(client, cap, secret)
    if start is None:
        print("\nStopping: the key could not be read, so no paid call was made.")
        return 1
    remaining = start.get("limit_remaining")
    if isinstance(remaining, (int, float)) and remaining < upper:
        print(f"\nStopping: the key has {money(remaining)} left, less than this run's upper bound of {money(upper)}.")
        return 1
    if not step_tiny(client, calls[0], problems, sleeper):
        print("\nStopping: the tiny call has to succeed on the pinned provider, confirmed, unaltered, without a cache hit, "
              "before anything else is spent.")
        step_summary(client, [], start, cap, problems)
        return 1
    rows = step_probes(client, calls, cases, problems)
    pending = step_batch(client, calls, run_id, args.batch_wait, problems)
    step_summary(client, rows, start, cap, problems, pending)
    return 1 if problems else 0


class DryRunTransport:
    """A canned OpenRouter for the dry run: the live response shapes, with made-up numbers."""

    def __init__(self, cases: list):
        self.cases = cases
        self.generations: Dict[str, dict] = {}
        self.batches: Dict[str, dict] = {}
        self.charged = set()
        self.spent = 0.0
        self.n = 0

    def __call__(self, method: str, url: str, headers: Dict[str, str], body: Optional[bytes],
                 timeout_s: float) -> Tuple[int, Dict[str, str], bytes]:
        parts = urlparse(url)
        path = parts.path.split("/api/v1", 1)[-1]
        if method == "GET" and path == "/key":
            return self._json(200, {"data": {
                "label": "dry-run key", "limit": 250.0, "limit_reset": None, "is_free_tier": False,
                "usage": round(self.spent, 6), "limit_remaining": round(250.0 - self.spent, 6)}})
        if method == "POST" and path == "/chat/completions":
            return self._chat(json.loads(body))
        if method == "GET" and path == "/generation":
            gen_id = parse_qs(parts.query).get("id", [""])[0]
            if gen_id in self.generations:
                return self._json(200, {"data": self.generations[gen_id]})
            return self._json(404, {"error": {"code": 404, "message": "Generation not found"}})
        if method == "POST" and path == "/batches":
            batch_id = f"batch_dryrun_{len(self.batches) + 1}"
            self.batches[batch_id] = json.loads(body)
            return self._json(202, {"id": batch_id, "object": "batch", "status": "validating",
                                    "results": None, "usage": None, "error": None})
        if method == "GET" and path.startswith("/batches/"):
            return self._batch(path.rsplit("/", 1)[-1])
        return self._json(404, {"error": {"code": 404, "message": f"no canned answer for {method} {path}"}})

    def _chat(self, request: dict) -> Tuple[int, Dict[str, str], bytes]:
        self.n += 1
        prompt_text = request["messages"][-1]["content"]
        think = {"low": 1, "medium": 3}.get((request.get("reasoning") or {}).get("effort"), 4)
        if "switch_now" in prompt_text:
            content, reasoning, visible = json.dumps({"action": "defer", "reason": "Canned dry-run answer."}), 250 * think, 40
        elif "Case C" in prompt_text:
            answers = {c.case_id: c.answer for c in self.cases}
            content, reasoning, visible = "Canned working notes.\n" + json.dumps(answers), 400 * think, 220
        else:
            content, reasoning, visible = "ready", 60, 2
        prompt = approx_prompt_tokens(request["messages"])
        completion = reasoning + visible
        cost = estimate_cost(MODEL, "sync", prompt, completion)
        self.spent += cost
        gen_id = f"gen-dryrun-{self.n:04d}"
        self.generations[gen_id] = {
            "id": gen_id, "provider_name": "Anthropic", "total_cost": cost, "is_byok": False,
            "native_tokens_prompt": prompt, "native_tokens_completion": completion,
            "native_tokens_reasoning": reasoning, "native_tokens_cached": 0, "response_cache_source_id": None,
            "provider_responses": [{"provider_name": "Anthropic", "endpoint_id": "ep_dryrun",
                                    "model_permaslug": "anthropic/claude-sonnet-5.5-20260928", "status": 200}],
        }
        return self._json(200, {
            "id": gen_id, "object": "chat.completion", "created": 0, "model": request["model"], "provider": "Anthropic",
            "choices": [{"index": 0, "finish_reason": "stop", "native_finish_reason": "end_turn",
                         "message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": prompt + completion,
                      "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                      "completion_tokens_details": {"reasoning_tokens": reasoning}, "cost": cost, "is_byok": False},
        }, {"X-Generation-Id": gen_id})

    def _batch(self, batch_id: str) -> Tuple[int, Dict[str, str], bytes]:
        payload = self.batches.get(batch_id)
        items = payload["requests"] if payload else [
            {"custom_id": f"resumed-{i}", "body": {"messages": user(p)}} for i, p in enumerate(BATCH_PROMPTS, 1)]
        results, prompt_total, completion_total = [], 0, 0
        for i, item in enumerate(items, 1):
            prompt, completion = approx_prompt_tokens(item["body"]["messages"]), 64
            prompt_total += prompt
            completion_total += completion
            results.append({"id": f"batch_req_{i}", "custom_id": item["custom_id"], "error": None, "response": {
                "status_code": 200, "request_id": f"req-{i}", "body": {
                    "id": f"gen-batch-dryrun-{i}", "object": "chat.completion", "created": 0, "model": MODEL,
                    "provider": "Anthropic",
                    "choices": [{"index": 0, "finish_reason": "stop",
                                 "message": {"role": "assistant", "content": "ready" if i == 1 else "391"}}],
                    "usage": {"prompt_tokens": prompt, "completion_tokens": completion,
                              "total_tokens": prompt + completion, "completion_tokens_details": {"reasoning_tokens": 60}},
                }}})
        cost = estimate_cost(MODEL, "batch", prompt_total, completion_total)
        if batch_id not in self.charged:
            self.charged.add(batch_id)
            self.spent += cost
        return self._json(200, {
            "id": batch_id, "object": "batch", "endpoint": "/v1/chat/completions", "model": MODEL,
            "completion_window": "24h", "status": "completed", "created_at": 0, "finalized_at": 0,
            "request_counts": {"total": len(results), "completed": len(results), "failed": 0},
            "usage": {"prompt_tokens": prompt_total, "completion_tokens": completion_total,
                      "total_tokens": prompt_total + completion_total, "cost": cost, "is_byok": False},
            "results": results, "error": None,
        })

    @staticmethod
    def _json(status: int, obj: dict, headers: Optional[Dict[str, str]] = None) -> Tuple[int, Dict[str, str], bytes]:
        return status, headers or {}, json.dumps(obj).encode("utf-8")


def parse_args(argv: Optional[List[str]]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Monday's key test (stage 'smoke'). Without --live it is a dry run with no network calls.")
    p.add_argument("--live", action="store_true",
                   help="make real, paid calls with the funder's key: ~/.config/strike-pilot/<label>.key, "
                        "or the OPENROUTER_API_KEY environment variable")
    p.add_argument("--key-file", metavar="PATH",
                   help="read the key from this owner-only file instead of the label's default file")
    p.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    p.add_argument("--batch-wait", type=float, default=30, metavar="MINUTES",
                   help="how long to poll the batch before leaving it to finish (default 30)")
    p.add_argument("--resume-batch", metavar="ID", help="only check, and log, a batch submitted earlier")
    p.add_argument("--max-tokens", type=int, default=16000,
                   help="max_tokens for the effort probes (default 16000, generous so truncation does not hide "
                        "how many tokens each effort uses)")
    p.add_argument("--no-schema", action="store_true",
                   help="ask for the memo decision in the prompt only, without response_format json_schema")
    args = p.parse_args(argv)
    if args.max_tokens < 1:
        p.error("--max-tokens must be at least 1")
    return args


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    plan = FundingPlan.load(os.path.join(PILOT_DIR, "funding_plan.json"))
    funder = plan.funder_for(STAGE)
    key_label = plan.funders[funder]["key_label"]
    cap = plan.cap(funder)
    cases, calls = planned_calls(args.max_tokens, not args.no_schema)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"smoke-{stamp}"
    scratch = None
    if args.live:
        try:
            secret, source = load_key(key_label, args.key_file)
        except MissingKey as exc:
            print(f"{exc} The key is never taken from the command line.")
            return 2
        log_path = os.path.join(PILOT_DIR, "logs", f"smoke_{stamp}.jsonl")
        transport, sleeper = None, time.sleep
        print(f"LIVE smoke test {run_id}: key label {key_label!r} (funder {funder}) from {source}, "
              f"log {shown_path(log_path)}")
    else:
        secret = "dry-run-placeholder"
        scratch = tempfile.TemporaryDirectory(prefix="smoke_dryrun_")
        log_path = os.path.join(scratch.name, f"smoke_{stamp}.jsonl")
        transport, sleeper = DryRunTransport(cases), (lambda seconds: None)
        print(f"DRY RUN {run_id}: no network, canned responses, so every number below except the estimates "
              f"is made up. Key label {key_label!r} (funder {funder}).")
    client = OpenRouterClient(secret, key_label, plan, CostLog(log_path), run_id,
                              transport=transport, sleep=sleeper)
    try:
        code = run(client, args, calls, cases, cap, secret, sleeper, run_id)
        records = client.log.records() if scratch is not None else []
        if records:
            print(f"\nThe dry run logged {len(records)} records to a temporary file, now deleted. A sample line:")
            print("   " + json.dumps({k: v for k, v in vars(records[0]).items() if v is not None}, sort_keys=True))
        return code
    finally:
        if scratch is not None:
            scratch.cleanup()


if __name__ == "__main__":
    sys.exit(main())
