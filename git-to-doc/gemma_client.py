"""
gemma_client.py  --  OWNER: Person 1 (Model engine)

The ONLY job of this file is to turn a prompt into text from Gemma.
Everyone else calls `call_gemma(...)` and never touches Ollama directly.

INTERFACE CONTRACT (do not change the signature without telling the team):

    call_gemma(prompt: str, *, model=..., system=None, temperature=0.2) -> str

It returns the model's raw text. Parsing/validation is Person 4's job, not this file's.

Zero third-party dependencies: this uses the Python standard library so the repo
runs straight after `git clone` with nothing to `pip install`.

Config via environment (so you can point at a remote Ollama or a cloud endpoint
WITHOUT editing code):
    OLLAMA_URL   default http://localhost:11434/api/generate
    GEMMA_MODEL  default gemma2:2b
"""

import json
import os
import time
import urllib.error
import urllib.request

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
DEFAULT_MODEL = os.environ.get("GEMMA_MODEL", "gemma2:2b")


class GemmaError(RuntimeError):
    """Raised when we cannot get usable text out of the model."""


def call_gemma(
    prompt,
    model=DEFAULT_MODEL,
    system=None,
    temperature=0.2,
    timeout=120,
    retries=2,
):
    """Send `prompt` to Ollama's /api/generate and return the response text.

    Retries on transient/connection errors with a short backoff. Raises
    GemmaError with an actionable message if the model can't be reached.
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,  # one shot, one JSON object back -- simplest to parse
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
        f"after {retries + 1} attempts.\n"
        f"  - Is the server running?  -> `ollama serve`\n"
        f"  - Is the model pulled?    -> `ollama pull {model}`\n"
        f"  Last error: {last_err}"
    )


def mock_call_gemma(prompt, **_kwargs):
    """A fake model for offline work.

    Person 4 (parser) and Person 5 (QA) use this via `--mock` so they can build
    and test the whole pipeline before the real model is wired up. It returns
    output in the exact format the real prompt asks for (see prompts.py).
    """
    return (
        "COMMIT:\n"
        "fix(parser): guard against empty input before json decode\n"
        "\n"
        "CHANGELOG:\n"
        "### Fixed\n"
        "- Return `None` for empty parser input instead of raising on `json.loads`\n"
        "- Use `dict.get` so a missing `result` key no longer throws `KeyError`\n"
    )
