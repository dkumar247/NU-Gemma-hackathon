"""
parser.py  --  OWNER: Person 4 (Parser & validation)

Turns the model's raw text into two clean pieces:
    {"commit": "<one line>", "changelog": "<markdown>"}

and tells main.py whether the commit line is valid.

You can build and test ALL of this offline against hardcoded strings or via
`python main.py tests/fixtures/sample.diff --mock`. You do not need Ollama.

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

# type, optional (scope), optional !, then ": subject"
CONVENTIONAL_RE = re.compile(
    r"^(?:" + "|".join(CONVENTIONAL_TYPES) + r")(?:\([\w\-./ ]+\))?(?:!)?: .+"
)

_COMMIT_MARKER = "COMMIT:"
_CHANGELOG_MARKER = "CHANGELOG:"


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
    """From a block of text, pull the first real commit line.

    Strips backticks, surrounding quotes, and leading list markers that small
    models like to add.
    """
    for line in block.splitlines():
        line = line.strip()
        line = re.sub(r"^[-*]\s+", "", line)       # "- fix: x" -> "fix: x" (do this first)
        line = line.strip("`").strip()             # then strip wrapping backticks
        line = line.strip('"').strip("'").strip()  # then wrapping quotes
        if line:
            return line
    return ""


def parse_model_output(raw):
    """Split raw model text into {"commit", "changelog"}.

    Robust to: missing markers, fenced answers, leading filler, list markers.
    Never raises -- worst case it returns best-effort guesses for main.py to flag.
    """
    text = strip_fences(raw)
    upper = text.upper()

    ci = upper.find(_COMMIT_MARKER)
    cl = upper.find(_CHANGELOG_MARKER)

    if ci != -1 and cl != -1 and cl > ci:
        commit_block = text[ci + len(_COMMIT_MARKER):cl].strip()
        changelog = text[cl + len(_CHANGELOG_MARKER):].strip()
    elif ci != -1:
        commit_block = text[ci + len(_COMMIT_MARKER):].strip()
        changelog = ""
    else:
        # No markers at all: first non-empty line = commit, the rest = changelog.
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


def salvage_commit(commit):
    """Best-effort coercion to a valid commit, used as a fallback in hardening.

    Never invents detail -- it just makes the line syntactically valid so the
    pipeline always emits *something* usable, clearly flagged by main.py.
    """
    if not commit:
        return "chore: update code"
    subject = commit.splitlines()[0].strip()
    if CONVENTIONAL_RE.match(subject):
        return subject
    return "chore: " + subject[:64]
