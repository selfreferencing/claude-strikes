"""Test suite. No test may find a real key: keys are looked up in a folder that
does not exist, and the environment fallback is cleared."""

import os
import tempfile

os.environ["STRIKE_PILOT_KEY_DIR"] = os.path.join(tempfile.gettempdir(), "strike-pilot-tests-have-no-keys")
os.environ.pop("OPENROUTER_API_KEY", None)
