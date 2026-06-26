"""
prompts.py  --  OWNER: Person 2 (Prompt engineer)

This is the highest-leverage file in the project. Your whole job is to make
gemma3:4b emit the COMMIT/CHANGELOG block below with NO conversational filler
("Sure, here is...") and a valid Conventional Commit line.

How to iterate fast (you are never blocked waiting on code):
    1. Open a terminal:  ollama run gemma3:4b
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
- Do NOT show your reasoning or thinking. Do not output <think> tags. Output only the format.
- Do NOT wrap the whole answer in a markdown code fence.
- The commit line MUST follow Conventional Commits 1.0.0.
- Allowed commit types: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert.
- Commit subject: lowercase, imperative mood ("add", not "adds"/"added"), under 72 characters, no trailing period.
- Pick the single most important change for the commit subject.
- Describe the ACTUAL diff provided. Never copy the example wording or any placeholder text.
- Never output angle brackets (< or >) around your answer.
- ALWAYS output both a COMMIT: section and a CHANGELOG: section. Never stop after the commit.
- The changelog ### heading MUST be exactly one of: Added, Fixed, Changed, Removed, Deprecated, Security. Never invent another heading (use Changed for documentation edits).
"""

USER_TEMPLATE = """Analyze the git diff at the bottom and produce documentation for IT.

Output two sections only: a COMMIT: section, then a CHANGELOG: section. Nothing before COMMIT: and nothing after the last changelog bullet.

Below is ONE complete example showing the exact format. Do NOT reuse its wording -- it is only there to show the shape. Describe the real diff instead.

--- EXAMPLE INPUT ---
diff --git a/cache.py b/cache.py
@@ -8,6 +8,8 @@ def get(self, key):
-        return self.store[key]
+        if key not in self.store:
+            return None
+        return self.store[key]
--- EXAMPLE OUTPUT ---
COMMIT:
fix(cache): return None for missing keys

CHANGELOG:
### Fixed
- Return None instead of raising when a cache key is missing
--- END EXAMPLE ---

Now document the diff below in that same format. The ### heading must be one of: Added, Fixed, Changed, Removed, Deprecated, Security.

Git diff:
---
{diff}
---
"""


def build_user_prompt(diff_text):
    """Fill the user template with the diff. Person 3 calls this."""
    return USER_TEMPLATE.format(diff=diff_text)


# ---------------------------------------------------------------------------
# SELF-HEALING REPAIR (the differentiator)
# When the parser/validator rejects the model's output, main.py calls Gemma a
# SECOND time with this prompt -- handing back the bad output + the reason so the
# model can correct itself. The format RULES come from SYSTEM_PROMPT (passed via
# call_gemma's system=...), so this prompt deliberately does NOT re-show a format
# template -- that avoids re-introducing the placeholder-copy bug.
# ---------------------------------------------------------------------------
REPAIR_TEMPLATE = """Your previous attempt was REJECTED.
Reason: {reason}

Your previous (rejected) answer was:
--- BEGIN REJECTED ANSWER ---
{bad_output}
--- END REJECTED ANSWER ---

Do it again correctly, fixing exactly that problem. Follow the instructions and
the example below precisely, including the multi-line COMMIT:/CHANGELOG: shape
with a "### Heading" and bullet points.

{original_prompt}
"""


def build_repair_prompt(diff_text, bad_output, reason):
    """Build a correction prompt after a rejected attempt. Person 3 calls this
    on retry, passing the SAME diff, the model's bad output, and the validator's
    reason. Reuses the full original prompt (worked example included) so the
    repaired answer keeps full format quality. Pair with SYSTEM_PROMPT via
    call_gemma(system=...)."""
    return REPAIR_TEMPLATE.format(
        reason=reason,
        bad_output=bad_output,
        original_prompt=build_user_prompt(diff_text),
    )


# ---------------------------------------------------------------------------
# TUNING NOTES (Person 2 -- keep your experiments here)
# - MIXED MODELS: our team runs different Gemmas (gemma3:4b, gemma4:12b,
#   gemma4:31b). Tune and test this prompt against the SMALLEST model on the
#   team (gemma3:4b). If the format is clean there, the bigger models -- which
#   follow instructions better -- will handle it too. Then spot-check on one
#   Gemma 4 model to confirm no stray reasoning tokens leak through.
# - If the model adds a preamble, make the first system rule harsher.
# - If the type is usually wrong, add 1-2 few-shot examples ABOVE "Git diff:".
# - If subjects run long, restate the 72-char limit inside USER_TEMPLATE too.
# ---------------------------------------------------------------------------
