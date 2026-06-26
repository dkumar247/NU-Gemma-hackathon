"""
parser.py  --  OWNER: Person 4 (Parser & validation)

Turns the model's raw text into two clean pieces:
    {"commit": "<one line>", "changelog": "<markdown>"}
and tells main.py whether the commit line is valid.

MODEL-AGNOSTIC BY DESIGN
------------------------
Different Gemma sizes/generations format things differently, and the Gemma 4
"thinking" models can emit reasoning (e.g. <think>...</think>) before the
answer. This parser is built to survive all of that:
  - it strips thinking/reasoning blocks,
  - it strips a wrapping ``` code fence,
  - it finds the COMMIT:/CHANGELOG: markers anchored to the START of a line
    (so the word "COMMIT" buried in reasoning prose doesn't fool it),
  - and it falls back gracefully if the markers are missing.

You can build and test ALL of this offline:
    python git-to-doc/main.py git-to-doc/tests/fixtures/sample.diff --mock

Format contract (shared with prompts.py):
    COMMIT:
    <conventional commit line>

    CHANGELOG:
    <markdown>
"""

import re

CONVENTIONAL_TYPES = [
    "feat", "fix", "docs", "style", "refactor",
    "perf", "test", "build", "ci", "chore", "revert",
]

CONVENTIONAL_RE = re.compile(
    r"^(?:" + "|".join(CONVENTIONAL_TYPES) + r")(?:\([\w\-./ ]+\))?(?:!)?: .+"
)

# Markers anchored to the start of a line, tolerating leading spaces / markdown
# bullet or quote chars (so "- COMMIT:" or "> COMMIT:" still match).
_COMMIT_RE = re.compile(r"(?im)^[ \t>*\-]*COMMIT:[ \t]*")
_CHANGELOG_RE = re.compile(r"(?im)^[ \t>*\-]*CHANGELOG:[ \t]*")

# Reasoning/thinking blocks emitted by "thinking" models (Gemma 4, etc.).
_THINK_RE = re.compile(r"<\|?\s*think\s*\|?>.*?<\|?\s*/\s*think\s*\|?>",
                       re.IGNORECASE | re.DOTALL)


def strip_thinking(text):
    """Remove <think>...</think> / <|think|>...<|/think|> reasoning blocks."""
    return _THINK_RE.sub("", text)


def strip_fences(text):
    """Drop a single ``` fence wrapping the whole answer (a common model habit)."""
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def _clean_commit_line(block):
    """Pull the first real commit line from a block of text."""
    for line in block.splitlines():
        line = line.strip()
        line = re.sub(r"^[-*]\s+", "", line)       # "- fix: x" -> "fix: x" (first)
        line = line.strip("`").strip()             # then wrapping backticks
        line = line.strip('"').strip("'").strip()  # then wrapping quotes
        if line:
            return line
    return ""


def _marker(text, regex, fallback):
    """Find a marker via line-anchored regex, falling back to a plain search.

    Returns (start, end) of the marker, or (-1, -1) if absent.
    """
    m = regex.search(text)
    if m:
        return m.start(), m.end()
    idx = text.upper().find(fallback)
    if idx != -1:
        return idx, idx + len(fallback)
    return -1, -1


def parse_model_output(raw):
    """Split raw model text into {"commit", "changelog"}.

    Robust to thinking blocks, fenced answers, leading filler, missing markers,
    and list/quote decoration. Never raises -- worst case it returns best-effort
    guesses for main.py to flag.
    """
    text = strip_fences(strip_thinking(raw))

    c_start, c_end = _marker(text, _COMMIT_RE, "COMMIT:")
    l_start, l_end = _marker(text, _CHANGELOG_RE, "CHANGELOG:")

    if c_start != -1 and l_start != -1 and l_start > c_end:
        commit_block = text[c_end:l_start].strip()
        changelog = text[l_end:].strip()
    elif c_start != -1:
        commit_block = text[c_end:].strip()
        changelog = ""
    else:
        # No COMMIT marker: first non-empty line = commit, the rest = changelog.
        lines = text.splitlines()
        commit_block, rest_start = "", 0
        for idx, line in enumerate(lines):
            if line.strip():
                commit_block, rest_start = line.strip(), idx + 1
                break
        changelog = "\n".join(lines[rest_start:]).strip()

    return {
        "commit": _clean_commit_line(commit_block),
        "changelog": strip_fences(changelog),
    }


def validate_commit(commit):
    """Return (is_valid, reason). Reason is human-readable for warnings."""
    if not commit:
        return False, "empty commit message"
    subject = commit.splitlines()[0]
    if len(subject) > 72:
        return False, f"subject is {len(subject)} chars (limit 72)"
    if not CONVENTIONAL_RE.match(subject):
        return False, "does not match Conventional Commits format"
    return True, "ok"


_KEYWORD_TYPE_MAP = [
    (re.compile(r"\b(fix|bug|patch|error|crash)\b", re.I), "fix"),
    (re.compile(r"\b(feat|add|new|implement)\b", re.I),    "feat"),
    (re.compile(r"\b(refactor|restructur|clean)", re.I),    "refactor"),
    (re.compile(r"\b(test|spec|coverage)\b", re.I),        "test"),
    (re.compile(r"\b(doc|readme|comment)\b", re.I),        "docs"),
    (re.compile(r"\b(perf|speed|optim)", re.I),            "perf"),
]


def salvage_commit(commit):
    """Best-effort coercion to a valid commit, used as a fallback in hardening."""
    if not commit:
        return "chore: update code"
    subject = commit.splitlines()[0].strip()
    if CONVENTIONAL_RE.match(subject):
        return subject
    for pattern, ctype in _KEYWORD_TYPE_MAP:
        if pattern.search(subject):
            return f"{ctype}: {subject[:64]}"
    return "chore: " + subject[:64]
