# git-to-doc

Turn a raw `git diff` into a clean **Conventional Commit message** + a **markdown
changelog snippet**, using a local Gemma model (`gemma2:2b` via Ollama).

Pure CLI, no UI. Zero third-party dependencies (Python 3.8+ stdlib only).

## Quickstart

```bash
# 0. One-time: make sure Ollama is running and the model is pulled
ollama serve            # in one terminal (if not already running)
ollama pull gemma2:2b

# 1. Run it on the sample diff
python main.py tests/fixtures/sample.diff

# 2. Or run with no model at all (uses a fake response) to test the pipeline
python main.py tests/fixtures/sample.diff --mock

# 3. Write the output to a file as well as printing it
python main.py tests/fixtures/sample.diff --out docs.md
```

If you see a Conventional Commit line and a changelog block printed, you're done.

## How it works

```
.diff file ─▶ main.py ─▶ prompts.py ─▶ gemma_client.py ─▶ (Ollama / gemma2:2b)
                 ▲                                                  │
                 └──────────── parser.py ◀───── raw model text ◀────┘
```

`main.py` reads the file, `prompts.py` builds the instruction, `gemma_client.py`
calls the model, `parser.py` extracts + validates the result, and `main.py`
renders the markdown.

## Who owns what (5-person split)

Each person owns one file with a fixed interface, so you can all work in parallel
without merge conflicts. **Agree on the interface contract below in the first 30
minutes and then don't change it without telling the team.**

| Person | File | Owns | Can start immediately because... |
|--------|------|------|----------------------------------|
| 1 | `gemma_client.py` | Ollama call, retries, timeouts, errors | it's the critical path; ship `call_gemma` first |
| 2 | `prompts.py` | system prompt + template; killing filler | iterate in `ollama run` with no code needed |
| 3 | `main.py` | argparse, file I/O, diff truncation, rendering | builds the skeleton against `--mock` |
| 4 | `parser.py` | split output, strip fences, validate commit | works against hardcoded strings + `--mock` |
| 5 | `tests/`, this README, repo hygiene, demo | curates real diffs, runs everything, logs failures | `--mock` makes the pipeline runnable on minute 1 |

## The format contract (shared by `prompts.py` and `parser.py`)

The model is asked to output exactly this, and the parser keys off the literal
`COMMIT:` and `CHANGELOG:` markers:

```
COMMIT:
fix(parser): guard against empty input before json decode

CHANGELOG:
### Fixed
- Return None for empty parser input instead of raising
```

If Person 2 renames a marker, Person 4 must update `parser.py` to match.

## Testing

```bash
python tests/test_parser.py        # zero deps, prints PASS/FAIL
python -m pytest tests/            # if pytest is installed
```

Person 5: drop the 5–10 organizer-provided diffs into `tests/fixtures/` and run
`python main.py tests/fixtures/<name>.diff` against each during hardening.

## Configuration

Point at a remote Ollama or a pre-allocated cloud endpoint **without editing
code** via environment variables:

```bash
export OLLAMA_URL="http://my-host:11434/api/generate"
export GEMMA_MODEL="gemma2:2b"
```

CLI flags: `--model`, `--temperature`, `--max-diff-chars`, `--out`, `--mock`.

## Troubleshooting

- **`Could not get a usable response from Ollama`** — run `ollama serve` and
  `ollama pull gemma2:2b`, then retry.
- **Commit shows a `:warning:` "auto-corrected" note** — the model produced an
  invalid commit line; tighten `SYSTEM_PROMPT` in `prompts.py`.
- **Big diff seems ignored** — it was truncated to fit the context window; raise
  `--max-diff-chars` or trim the diff to the relevant hunk.

## Stretch goals (if you finish early)

- `--append CHANGELOG.md` to prepend the snippet into a real changelog file.
- Batch mode: accept a directory of diffs and write one doc per file.
- A second validation pass that re-prompts the model when the commit is invalid,
  instead of falling back to `salvage_commit`.
