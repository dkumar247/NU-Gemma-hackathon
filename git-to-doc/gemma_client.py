"""
gemma_client.py  --  OWNER: Person 1 (Model engine)

The ONLY job of this file is to turn a prompt into text from Gemma.
Everyone else calls `call_gemma(...)` and never touches Ollama directly.

MODEL-AGNOSTIC: each teammate runs whatever Gemma they have (gemma3:4b,
gemma4:12b, gemma4:31b) via a gitignored `.gemma-model` file -- no code edits.
Resolution order: --model flag > GEMMA_MODEL env > ./.gemma-model file > default.
The file is read robustly so it works even when Windows PowerShell saves it as
UTF-16 with a BOM (the classic `echo "tag" > .gemma-model` gotcha).

STREAMING: call_gemma streams the model's output and prints it live to the
screen as it generates (so a slow model doesn't look frozen), while still
returning the COMPLETE text string -- so main.py and parser.py are unchanged.

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


def call_gemma(
    prompt,
    model=None,
    system=None,
    temperature=0.2,
    timeout=180,
    retries=2,
    show_live=True,
):
    """Send `prompt` to Ollama and return the model's full response text.

    Streams the response: each chunk is printed live to stderr as it arrives
    (set show_live=False to silence it, e.g. in batch mode), and the full text
    is assembled and returned so callers get one complete string as before.
    """
    model = resolve_model(model)
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,                       # <-- stream chunk by chunk
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
            chunks = []
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                # Ollama sends one JSON object per line as it generates.
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
                print("", file=sys.stderr)     # newline after the live stream
            text = "".join(chunks).strip()
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
        f"  - Is the server running?  -> on Windows, check the llama tray icon\n"
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