# git-to-doc

Turn a raw `git diff` into a clean **Conventional Commit message** + a **markdown
changelog snippet**, using a local Gemma model (Ollama or LM Studio).

Pure CLI, no UI. Zero third-party dependencies (Python 3.8+ stdlib only).

## Quickstart

```bash
# 0. One-time: make sure your model server is running and the model is loaded
ollama serve                          # Ollama
ollama pull gemma3:4b                 # or gemma4:12b, gemma4:31b

# Tell the tool which model you're running (gitignored, no code edits needed)
echo "gemma3:4b" > .gemma-model

# 1. Run it on the sample diff
python3 main.py tests/fixtures/sample.diff

# 2. Run with no model at all (uses a fake response) to test the pipeline
python3 main.py tests/fixtures/sample.diff --mock

# 3. Write the output to a file as well as printing it
python3 main.py tests/fixtures/sample.diff --out docs.md

# 4. Pipe a real diff directly from git (the strongest demo)
git diff | python3 main.py -

# 5. Prepend the changelog snippet to a real changelog file
python3 main.py tests/fixtures/sample.diff --append CHANGELOG.md
```

If you see a Conventional Commit line and a changelog block printed, you're done.

## How it works

```
.diff file ─▶ main.py ─▶ prompts.py ─▶ gemma_client.py ─▶ (Ollama / LM Studio)
                 ▲                                                  │
                 └──────────── parser.py ◀───── raw model text ◀────┘
```

`main.py` reads the file, filters lockfiles, `prompts.py` builds the instruction,
`gemma_client.py` calls the model, `parser.py` extracts + validates the result,
and `main.py` renders the markdown.

### Auto-filtering of lockfiles

Lockfiles (`*.lock`, `uv.lock`, `Pipfile.lock`, `package-lock.json`, etc.) are
automatically removed from the diff before processing. They add size without
useful signal. Skipped files are reported to stderr.

## Who owns what (5-person split)

Each person owns one file with a fixed interface, so you can all work in parallel
without merge conflicts. **Agree on the interface contract below in the first 30
minutes and then don't change it without telling the team.**

| Person | File | Owns | Can start immediately because... |
|--------|------|------|----------------------------------|
| 1 | `gemma_client.py` | Ollama/LM Studio call, retries, timeouts, errors | it's the critical path; ship `call_gemma` first |
| 2 | `prompts.py` | system prompt + template; killing filler | iterate in `ollama run` with no code needed |
| 3 | `main.py` | argparse, file I/O, filtering, truncation, rendering | builds the skeleton against `--mock` |
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
python3 tests/test_parser.py        # zero deps, prints PASS/FAIL
python3 -m pytest tests/            # if pytest is installed
```

Person 5: drop the 5–10 organizer-provided diffs into `tests/fixtures/` and run
`python3 main.py tests/fixtures/<name>.diff` against each during hardening.

## Configuration

Point at a remote Ollama, LM Studio, or shared endpoint **without editing
code** via environment variables:

```bash
# Ollama (default)
export OLLAMA_URL="http://localhost:11434/api/generate"

# LM Studio
export OLLAMA_URL="http://localhost:1234/v1/chat/completions"

# Shared Ollama server (one machine hosts, everyone else connects)
export OLLAMA_URL="http://192.168.X.X:11434/api/generate"

# Force backend explicitly
export BACKEND="lmstudio"   # or "ollama"

# Override model
export GEMMA_MODEL="gemma4:12b"
```

Backend is auto-detected from `OLLAMA_URL` — if it contains `/v1/` it uses
LM Studio (OpenAI-compatible) format, otherwise Ollama format.

CLI flags: `--model`, `--temperature`, `--max-diff-chars`, `--out`, `--append`, `--mock`.

## Troubleshooting

- **`Could not get a usable response`** — confirm your model server is running
  and `OLLAMA_URL` points to the correct endpoint.
- **Commit shows a `:warning:` "auto-corrected" note** — the model produced an
  invalid commit line; tighten `SYSTEM_PROMPT` in `prompts.py`.
- **`[diff truncated]` warning** — diff exceeded `--max-diff-chars`; raise the
  limit or trim the diff to the relevant hunk.
- **`[skipped generated files]`** — lockfiles were filtered automatically; this
  is expected and keeps Gemma focused on real code changes.

## Stretch goals (if you finish early)

- Batch mode: accept a directory of diffs and write one doc per file.
- A second validation pass that re-prompts the model when the commit is invalid,
  instead of falling back to `salvage_commit`.
