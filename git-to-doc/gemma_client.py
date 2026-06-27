"""
gemma_client.py  --  OWNER: Person 1 (Model engine)

The ONLY job of this file is to turn a prompt into text from Gemma.
Everyone else calls `call_gemma(...)` and never touches the backend directly.

BACKEND SUPPORT
---------------
Works with both Ollama and LM Studio (OpenAI-compatible). Auto-detected from
OLLAMA_URL — if it contains /v1/ it uses LM Studio format, otherwise Ollama.
Force with: export BACKEND=lmstudio  or  export BACKEND=ollama

    Ollama:    export OLLAMA_URL=http://localhost:11434/api/generate
    LM Studio: export OLLAMA_URL=http://localhost:1234/v1/chat/completions
    Shared:    export OLLAMA_URL=http://192.168.X.X:11434/api/generate

MODEL-AGNOSTIC
--------------
Each teammate runs whatever Gemma they have (gemma3:4b, gemma4:12b, gemma4:31b)
via a gitignored `.gemma-model` file — no code edits needed.
Resolution order: --model flag > GEMMA_MODEL env > ./.gemma-model file > default.
The file is read robustly so it works even when Windows PowerShell saves it as
UTF-16 with a BOM (the classic `echo "tag" > .gemma-model` gotcha).

STREAMING
---------
Ollama backend streams output live to stderr as it generates (so a slow model
doesn't look frozen) while still returning the complete text string.
LM Studio backend uses a single non-streaming request.

Zero third-party dependencies (Python stdlib only).
"""

import codecs
import json
import os
import sys
import time
import urllib.error
import urllib.request

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
DEFAULT_MODEL = "gemma3:4b"          # fallback only; see resolve_model()
_MODEL_FILE = ".gemma-model"          # per-machine, gitignored

# Auto-detect backend from URL: if it contains /v1/ it's LM Studio (OpenAI-compatible).
# Force with: export BACKEND=lmstudio  or  export BACKEND=ollama
_BACKEND_ENV = os.environ.get("BACKEND", "").lower()


def _detect_backend():
    if _BACKEND_ENV in ("lmstudio", "lm_studio", "lm-studio", "openai"):
        return "lmstudio"
    if _BACKEND_ENV == "ollama":
        return "ollama"
    if "/v1/" in OLLAMA_URL:
        return "lmstudio"
    return "ollama"


class GemmaError(RuntimeError):
    """Raised when we cannot get usable text out of the model."""


def _read_text_robust(path):
    """Read a small text file regardless of how it was encoded/saved.

    Handles UTF-8, UTF-8-with-BOM, and UTF-16 (with or without BOM) -- the
    last of which is what Windows PowerShell's `>` redirection produces. Strips
    BOM characters and stray null bytes, then whitespace.
    """
    with open(path, "rb") as f:
        raw = f.read()
    if not raw:
        return ""
    if raw.startswith(codecs.BOM_UTF16_LE) or raw.startswith(codecs.BOM_UTF16_BE):
        text = raw.decode("utf-16", errors="ignore")
    elif raw.startswith(codecs.BOM_UTF8):
        text = raw.decode("utf-8-sig", errors="ignore")
    else:
        text = raw.decode("utf-8", errors="ignore")
    return text.replace("\ufeff", "").replace("\x00", "").strip()


def resolve_model(cli_value=None):
    """Decide which model tag to use. Works for ANY Gemma variant.

    Order: --model flag > GEMMA_MODEL env > ./.gemma-model file > DEFAULT_MODEL.
    """
    if cli_value:
        return cli_value.strip()

    env = os.environ.get("GEMMA_MODEL")
    if env and env.strip():
        return env.strip()

    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in (_MODEL_FILE, os.path.join(here, _MODEL_FILE),
                      os.path.join(here, "..", _MODEL_FILE)):
        try:
            val = _read_text_robust(candidate)
            if val:
                return val
        except OSError:
            continue

    return DEFAULT_MODEL


def _call_ollama(prompt, system, model, temperature, timeout, show_live):
    """Ollama streaming backend (/api/generate)."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "options": {"temperature": temperature},
    }
    if system:
        payload["system"] = system
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL, data=data, headers={"Content-Type": "application/json"},
    )
    chunks = []
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for line in resp:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line.decode("utf-8"))
            piece = obj.get("response", "")
            if piece:
                chunks.append(piece)
                if show_live:
                    print(piece, end="", file=sys.stderr, flush=True)
            if obj.get("done"):
                break
    if show_live:
        print("", file=sys.stderr)
    return "".join(chunks).strip()


def _call_lmstudio(prompt, system, model, temperature, timeout, show_live):
    """LM Studio OpenAI-compatible backend (/v1/chat/completions)."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL, data=data, headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    try:
        text = body["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError):
        text = ""
    return text


def call_gemma(
    prompt,
    model=None,
    system=None,
    temperature=0.2,
    timeout=300,
    retries=2,
    show_live=True,
):
    """Send `prompt` to Ollama or LM Studio and return the full response text.

    Auto-detects backend from OLLAMA_URL (contains /v1/ → LM Studio, else Ollama).
    Force with: export BACKEND=lmstudio  or  export BACKEND=ollama
    """
    model = resolve_model(model)
    backend = _detect_backend()
    caller = _call_lmstudio if backend == "lmstudio" else _call_ollama
    last_err = None

    for attempt in range(retries + 1):
        try:
            text = caller(prompt, system, model, temperature, timeout, show_live)
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
        f"Could not get a usable response from {OLLAMA_URL} "
        f"after {retries + 1} attempts (model: {model}, backend: {backend}).\n"
        f"  Ollama:    export OLLAMA_URL=http://localhost:11434/api/generate\n"
        f"  LM Studio: export OLLAMA_URL=http://localhost:1234/v1/chat/completions\n"
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