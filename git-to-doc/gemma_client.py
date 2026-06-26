"""
gemma_client.py  --  OWNER: Person 1 (Model engine)

The ONLY job of this file is to turn a prompt into text from Gemma.
Everyone else calls `call_gemma(...)` and never touches Ollama directly.

MODEL-AGNOSTIC BY DESIGN
------------------------
This code does NOT hardcode a model. Each teammate runs whatever Gemma they
have (gemma3:4b, gemma4:12b, gemma4:31b, ...) WITHOUT editing this file, so the
code stays identical for everyone and never causes merge conflicts.

The model is resolved in this priority order (first one wins):
    1. the --model CLI flag            (explicit, one-off override)
    2. the GEMMA_MODEL env variable    (per-shell)
    3. a local `.gemma-model` file     (per-machine; gitignored)  <-- easiest
    4. DEFAULT_MODEL below             (safe fallback)

So the 31B person just puts `gemma4:31b` in a `.gemma-model` file at the repo
root, the 4B person puts `gemma3:4b`, and nobody changes a line of code.

Zero third-party dependencies (Python stdlib only).

Config via environment:
    OLLAMA_URL   default http://localhost:11434/api/generate
    GEMMA_MODEL  overrides the resolved model (see above)
"""

import json
import os
import time
import urllib.error
import urllib.request

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
DEFAULT_MODEL = "gemma3:4b"          # fallback only; see resolve_model()
_MODEL_FILE = ".gemma-model"          # per-machine, gitignored


class GemmaError(RuntimeError):
    """Raised when we cannot get usable text out of the model."""


def resolve_model(cli_value=None):
    """Decide which model tag to use. Works for ANY Gemma variant.

    Order: --model flag > GEMMA_MODEL env > ./.gemma-model file > DEFAULT_MODEL.
    """
    if cli_value:
        return cli_value.strip()

    env = os.environ.get("GEMMA_MODEL")
    if env and env.strip():
        return env.strip()

    # Look for a local model file in the current dir and the repo root.
    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in (_MODEL_FILE, os.path.join(here, _MODEL_FILE),
                      os.path.join(here, "..", _MODEL_FILE)):
        try:
            with open(candidate, "r", encoding="utf-8") as f:
                val = f.read().strip()
                if val:
                    return val
        except OSError:
            continue

    return DEFAULT_MODEL


def call_gemma(
    prompt,
    model=None,
    system=None,
    temperature=0.2,
    timeout=180,
    retries=2,
):
    """Send `prompt` to Ollama's /api/generate and return the response text.

    `model=None` means "resolve it" (see resolve_model). Passing an explicit
    model overrides resolution. Uses /api/generate with a `system` field, which
    Ollama maps correctly for every Gemma generation (it owns the chat template),
    so this works unchanged across gemma2 / gemma3 / gemma4.

    A low default temperature keeps structured output stable regardless of the
    model's own "recommended" sampling settings.
    """
    model = resolve_model(model)
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if system:
        payload["system"] = system

    data = json.dumps(payload).encode("utf-8")
    last_err = None

    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                OLLAMA_URL,
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            text = (body.get("response") or "").strip()
            if not text:
                raise GemmaError("Model returned an empty response.")
            return text
        except urllib.error.URLError as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
        except (GemmaError, json.JSONDecodeError) as e:
            last_err = e
            time.sleep(1.0 * (attempt + 1))

    raise GemmaError(
        f"Could not get a usable response from Ollama at {OLLAMA_URL} "
        f"after {retries + 1} attempts (model: {model}).\n"
        f"  - Is the server running?  -> `ollama serve`\n"
        f"  - Is the model pulled?    -> `ollama pull {model}`\n"
        f"  Last error: {last_err}"
    )


def mock_call_gemma(prompt, **_kwargs):
    """A fake model for offline work (used via --mock). Format matches prompts.py."""
    return (
        "COMMIT:\n"
        "fix(parser): guard against empty input before json decode\n"
        "\n"
        "CHANGELOG:\n"
        "### Fixed\n"
        "- Return `None` for empty parser input instead of raising on `json.loads`\n"
        "- Use `dict.get` so a missing `result` key no longer throws `KeyError`\n"
    )
