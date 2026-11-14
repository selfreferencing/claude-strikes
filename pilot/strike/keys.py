"""Where the scripts find OpenRouter keys.

Each funder's key lives in a private file named after its label in the
funding plan: ~/.config/strike-pilot/<key label>.key, readable by its owner
only. Naming the file by label keeps each stage on its own funder's key. As a
fallback, the OPENROUTER_API_KEY environment variable works too, for someone
running a script by hand in their own terminal.

Nothing here prints, logs or returns the key except to the caller that needs
it, and no error message contains it.
"""

from __future__ import annotations

import os
import stat
from typing import Optional, Tuple

KEY_DIR = os.path.join("~", ".config", "strike-pilot")
ENV_VAR = "OPENROUTER_API_KEY"
# Overrides KEY_DIR. The test suite points it at a folder that does not exist,
# so no test can ever pick up a real key.
KEY_DIR_ENV = "STRIKE_PILOT_KEY_DIR"


class MissingKey(Exception):
    pass


def key_path(label: str) -> str:
    return os.path.join(os.environ.get(KEY_DIR_ENV) or KEY_DIR, f"{label}.key")


def load_key(label: str, path: Optional[str] = None) -> Tuple[str, str]:
    """Return (key, where it came from); the second never contains the key.

    Order: an explicit path, then the label's own file, then the environment.
    """
    shown = path or key_path(label)
    full = os.path.expanduser(shown)
    if path is not None or os.path.exists(full):
        return _read_file(full, shown), shown
    value = os.environ.get(ENV_VAR, "").strip()
    if value:
        return value, f"the {ENV_VAR} environment variable"
    raise MissingKey(f"No key for {label!r}: save it to {shown} (readable by you only), or set {ENV_VAR}.")


def _read_file(full: str, shown: str) -> str:
    if not os.path.isfile(full):
        raise MissingKey(f"{shown} does not exist.")
    if stat.S_IMODE(os.stat(full).st_mode) & 0o077:
        raise MissingKey(f"{shown} can be read by other users; run chmod 600 on it first.")
    with open(full, encoding="utf-8") as f:
        value = f.read().strip()
    if not value:
        raise MissingKey(f"{shown} is empty.")
    if any(c.isspace() for c in value):
        raise MissingKey(f"{shown} holds more than the key (it contains spaces or several lines).")
    if not value.startswith("sk-or-"):
        raise MissingKey(f"{shown} does not look like an OpenRouter key, which starts with sk-or-.")
    return value
