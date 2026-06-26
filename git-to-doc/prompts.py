"""
prompts.py  --  OWNER: Person 2 (Prompt engineer)

This is the highest-leverage file in the project. Your whole job is to make
gemma2:2b emit the COMMIT/CHANGELOG block below with NO conversational filler
("Sure, here is...") and a valid Conventional Commit line.

How to iterate fast (you are never blocked waiting on code):
    1. Open a terminal:  ollama run gemma2:2b
    2. Paste SYSTEM_PROMPT, then a USER_TEMPLATE filled with a real diff.
    3. Tweak wording here until the output is clean and parseable.
    4. The parser (parser.py) keys off the literal markers `COMMIT:` and
       `CHANGELOG:` -- if you rename them, tell Person 4.

The output format is a CONTRACT shared with parser.py. Keep these two in sync.
"""

# Small models follow short, blunt, rule-style instructions better than prose.
SYSTEM_PROMPT = """You are a release-documentation generator. You read a git diff and output documentation.

Rules:
- Output ONLY the format the user asks for. No greetings, no explanation, no notes.
- Do NOT wrap the whole answer in a markdown code fence.
- The commit line MUST follow Conventional Commits 1.0.0.
- Allowed commit types: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert.
- Commit subject: lowercase, imperative mood ("add", not "adds"/"added"), under 72 characters, no trailing period.
- Pick the single most important change for the commit subject.
"""

USER_TEMPLATE = """Analyze this git diff and produce documentation.

Output EXACTLY this structure and nothing before or after it:

COMMIT:
<one Conventional Commit line, e.g. fix(parser): handle empty input>

CHANGELOG:
### <one of: Added, Fixed, Changed, Removed, Deprecated, Security>
- <short bullet describing the change>
- <another bullet if needed>

Git diff:
---
{diff}
---
"""


def build_user_prompt(diff_text):
    """Fill the user template with the diff. Person 3 calls this."""
    return USER_TEMPLATE.format(diff=diff_text)


# ---------------------------------------------------------------------------
# TUNING NOTES (Person 2 -- keep your experiments here)
# - If the model adds a preamble, make the first system rule harsher.
# - If the type is usually wrong, add 1-2 few-shot examples ABOVE "Git diff:".
# - If subjects run long, restate the 72-char limit inside USER_TEMPLATE too.
# ---------------------------------------------------------------------------
