"""Per-token prices, for projections and cross-checks only.

Checked 3 October 2026 against OpenRouter's public model list
(https://openrouter.ai/api/v1/models). The charge OpenRouter reports on each
call (usage.cost) is what we log as the cost; these figures project the full
study and flag surprises.
"""

from __future__ import annotations

PER_MILLION = {
    "anthropic/claude-sonnet-5.5": {
        "input": 2.00, "output": 10.00, "cache_read": 0.20, "cache_write": 2.50, "cache_write_1h": 4.00,
    },
    "anthropic/claude-sonnet-5.5:batch": {
        "input": 1.00, "output": 5.00, "cache_read": 0.10, "cache_write": 1.25, "cache_write_1h": 2.00,
    },
    # Released 7 October 2026; input and output checked that day against the public model list.
    # Cache prices are not used by the runner and are scaled from Sonnet's ratios.
    "anthropic/claude-haiku-5.5": {
        "input": 0.10, "output": 0.50, "cache_read": 0.01, "cache_write": 0.125, "cache_write_1h": 0.20,
    },
    "anthropic/claude-haiku-5.5:batch": {
        "input": 0.05, "output": 0.25, "cache_read": 0.005, "cache_write": 0.0625, "cache_write_1h": 0.10,
    },
}

MODEL = "anthropic/claude-sonnet-5.5"


def price_key(model: str, mode: str) -> str:
    base = model[: -len(":batch")] if model.endswith(":batch") else model
    return base + ":batch" if mode == "batch" else base


def estimate_cost(
    model: str,
    mode: str,
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    """Dollar cost of one call. prompt_tokens includes cached and cache-write tokens;
    completion_tokens includes reasoning tokens, which bill as output."""
    p = PER_MILLION[price_key(model, mode)]
    uncached = max(prompt_tokens - cached_tokens - cache_write_tokens, 0)
    return (
        uncached * p["input"]
        + cached_tokens * p["cache_read"]
        + cache_write_tokens * p["cache_write"]
        + completion_tokens * p["output"]
    ) / 1e6
