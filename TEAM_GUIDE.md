# TEAM GUIDE — NU-Gemma Hackathon (Track 1: git-to-doc)

> **Read this first. It's the single source of truth for how we work together.**
> If everyone follows this, we will not have a painful merge at the end.

**Tip:** at the start of your session, paste this whole file into the **Continue
chat panel** in VS Code. That gives your AI assistant the same context about our
architecture and rules, so its suggestions match what the team agreed on.

---

## 1. The 60-second mental model

There are **two different AIs** in this project. Don't confuse them:

| | What it is | Who/what uses it | How it's reached |
|---|---|---|---|
| **Continue** | Your coding assistant (autocomplete + chat) | *You*, while writing code in VS Code | VS Code extension → Ollama |
| **Our tool's model** | The Gemma call inside `git-to-doc` | `gemma_client.py` at runtime | HTTP to `localhost:11434` |

Both talk to the **same local Ollama**. So you install Ollama once and pull the
model once, and it powers both. The tool does **not** go through Continue.

---

## 2. One-time setup (~15 min — do this in the first 30 minutes)

```bash
# 1. Install Ollama (if you don't have it)
#    macOS:   brew install ollama
#    Linux:   curl -fsSL https://ollama.ai/install.sh | sh
#    Windows: download from https://ollama.com

# 2. Start the server (leave this running in its own terminal)
ollama serve

# 3. Pull whichever Gemma your machine can handle (any tag works — see §4):
#      ollama pull gemma3:4b      # lighter laptops
#      ollama pull gemma4:12b     # mid / good GPU
#      ollama pull gemma4:31b     # strong GPU only

# 4. Tell the tool which model YOU run, without editing any code:
#    create a file named `.gemma-model` at the repo root containing just your tag
echo "gemma4:12b" > .gemma-model       # <-- your tag here (this file is gitignored)

# 5. (Optional but nice) a tiny fast model for Continue autocomplete
ollama pull qwen2.5-coder:1.5b

# 6. Verify the API is up
curl http://localhost:11434        # should say "Ollama is running"

# 7. Sanity-check your model returns text (use your own tag)
ollama run gemma4:12b "say hello in 3 words"
```

### Wire up Continue (your coding assistant)

In VS Code: install the **Continue** extension, then open the Command Palette
(`Ctrl/Cmd+Shift+P`) → **"Continue: Open Config"**. This opens
`~/.continue/config.yaml` (a per-user file — **not** part of our repo). Paste:

```yaml
name: NU-Gemma Hackathon
version: 0.0.1
schema: v1
models:
  - name: Gemma Chat
    provider: ollama
    model: gemma3:4b      # <- set to whatever YOU pulled (gemma4:12b, gemma4:31b, ...)
    roles:
      - chat
      - edit
  - name: Fast Autocomplete
    provider: ollama
    model: qwen2.5-coder:1.5b
    roles:
      - autocomplete
```

(A copy of this lives at `docs/continue.config.example.yaml` for convenience.)

---

## 3. Get the code and run it

```bash
git clone https://github.com/dkumar247/NU-Gemma-hackathon.git
cd NU-Gemma-hackathon

# It runs immediately with NO model needed (fake response) — proves your setup:
python git-to-doc/main.py git-to-doc/tests/fixtures/sample.diff --mock

# Real run against your local Gemma:
python git-to-doc/main.py git-to-doc/tests/fixtures/sample.diff
```

---

## 4. Models: the tool is model-agnostic (run whatever you've got)

We deliberately do **not** force one model. The code is identical for everyone;
each person picks their model with a gitignored `.gemma-model` file (or
`GEMMA_MODEL` env var, or `--model` flag). So `gemma3:4b`, `gemma4:12b`, and
`gemma4:31b` all work side by side with zero code edits and zero merge conflicts.

Two rules make a mixed-model team safe:

1. **Person 2 tunes the prompt against the SMALLEST model on the team
   (`gemma3:4b`).** Bigger models follow instructions better, so if the output
   is clean on 4B it'll be clean on 12B/31B too. Tuning to the weakest link is
   what guarantees everyone gets usable output. (Then spot-check once on a
   Gemma 4 model to confirm no reasoning/`<think>` tokens leak — the parser
   strips them, but verify.)
2. **Pin ONE model for the final demo / judging run** so the output you *show*
   is consistent. Day-to-day everyone uses their own; for the recorded demo,
   agree on a tag (e.g. whoever has the 31B runs it) and note it in the README.

### These ARE locked (don't change without a team-wide ping)

1. **The model output format** (the `COMMIT:` / `CHANGELOG:` markers — see §7).
2. **The function signatures** in §7.

A silent change to either is the #1 cause of "it worked on my machine." Post in
the team chat **before** you push such a change so everyone updates together.

---

## 5. Who owns what (one file each = almost no conflicts)

You each own one file. **Do not edit someone else's file** without telling them.
If you need a change in their file, ask them in chat or open a PR they review.

| Person | Owns | Don't touch |
|--------|------|-------------|
| 1 | `gemma_client.py` | everyone else's modules |
| 2 | `prompts.py` | parser/orchestration |
| 3 | `main.py` (CLI + glue + rendering) | client/parser internals |
| 4 | `parser.py` | prompts/client |
| 5 | `tests/`, `README.md`, this guide, repo hygiene, demo | source modules (suggest via PR) |

The interface contract in §7 is what lets all five of you work at the same time
without waiting on each other.

---

## 6. Git workflow that prevents the end-of-hackathon merge nightmare

**The golden rule: each person works on their own branch, and pulls `main` often.**
Because you each own a separate file, your branches will rarely touch the same
lines — so merges stay tiny.

### Start of your session (and a few times during)

```bash
git checkout main
git pull                       # get everyone's latest
git checkout -b yourname/module   # e.g. priya/parser   (first time only)
# returning later? just: git checkout yourname/module && git merge main
```

### When your piece works, ship it

```bash
python git-to-doc/tests/test_parser.py   # make sure nothing is broken
git add .
git commit -m "feat(parser): add fence stripping"   # use Conventional Commits!
git push -u origin yourname/module
```

Then on GitHub, open a **Pull Request** into `main`. Keep PRs small and frequent
(every working feature), not one giant PR at hour 5.

### Stay current (do this OFTEN — it's how you avoid a big-bang merge)

```bash
git checkout main && git pull
git checkout yourname/module
git merge main                 # pulls everyone else's merged work into your branch
```

### One integrator

**Person 5 (or the repo owner) is the only one who merges PRs into `main` and
resolves any conflicts on `main`.** This keeps `main` always-working and avoids
two people fighting over the same merge.

### Git cheat sheet

```bash
git status                 # what's changed / staged
git pull                   # download teammates' changes
git add .                  # stage your changes
git commit -m "type: msg"  # save a snapshot (Conventional Commits format)
git push                   # upload to your branch
git checkout main          # switch to the main branch
git merge main             # bring main's changes into your current branch
git merge --abort          # PANIC BUTTON: undo a merge in progress
```

> **Push asks for a password?** GitHub no longer accepts your account password.
> Run `gh auth login` (GitHub CLI, browser login) once, or use a Personal Access
> Token with the `repo` scope as the "password." GitHub Desktop also handles this
> with a click.

---

## 7. The interface contract (the no-conflict backbone)

Everyone codes **to these signatures**. As long as your function takes and
returns exactly this, your module drops in without breaking anyone.

### Model output format (shared by `prompts.py` ↔ `parser.py`)

The model is instructed to output **exactly** this, nothing before or after:

```
COMMIT:
fix(parser): guard against empty input before json decode

CHANGELOG:
### Fixed
- Return None for empty parser input instead of raising
```

### Function signatures

```python
# gemma_client.py  (Person 1)
resolve_model(cli_value=None) -> str   # --model > GEMMA_MODEL > .gemma-model > default
call_gemma(prompt: str, *, model=None, system=None, temperature=0.2) -> str  # None -> resolve
mock_call_gemma(prompt: str, **kwargs) -> str     # offline fake, same format
class GemmaError(RuntimeError): ...

# prompts.py  (Person 2)
SYSTEM_PROMPT: str
build_user_prompt(diff_text: str) -> str

# parser.py  (Person 4)
parse_model_output(raw: str) -> dict   # {"commit": str, "changelog": str}
validate_commit(commit: str) -> tuple  # (is_valid: bool, reason: str)
salvage_commit(commit: str) -> str     # coerces an invalid commit to a valid one

# main.py  (Person 3) — the CLI
# python git-to-doc/main.py <file> [--out PATH] [--model NAME] [--temperature F] [--mock]
```

If you want to change any signature here, that's a §4 "locked decision" — ping
the team first.

---

## 8. Timeline checkpoints (from the hackathon brief)

| Phase | Time | What "done" looks like for the team |
|-------|------|-------------------------------------|
| Setup | 0:00–0:30 | Everyone: Ollama runs, a Gemma pulled, `.gemma-model` set, repo cloned, `--mock` works. **We agree on §4 (format + signatures) out loud.** |
| Prompt tuning | 0:30–2:00 | P2 iterating prompts in `ollama run`; P1 ships `call_gemma`; P3 builds skeleton on `--mock`; P4 writes parsers against fake strings; P5 gathers real diffs. |
| Construction | 2:00–4:00 | P3 wires the real pieces together; P2 now tunes end-to-end on real diffs; first PRs merged to `main`. |
| Hardening | 4:00–5:00 | Run on all of P5's diffs; handle bad/empty/oversized inputs; `main` is green; demo rehearsed. |

**Integration checkpoint at ~2:30:** stop and run the full pipeline once,
end-to-end, on `main`. If it works once, every later change is a small delta.

---

## 9. When things go wrong

- **Merge conflict** (`CONFLICT` in terminal): open the file, find the
  `<<<<<<<`, `=======`, `>>>>>>>` markers, keep the correct code, delete the
  markers, then `git add <file>` and `git commit`. Unsure? `git merge --abort`
  and ask the integrator.
- **Someone changed a signature and now imports break:** check §7, re-sync
  (`git merge main`), and flag it in chat — a locked decision changed.
- **`Could not reach Ollama`:** run `ollama serve`, and `ollama pull <your tag>`
  (the error message prints which model it tried).
- **Model output is messy / invalid commit:** that's expected sometimes — the
  parser auto-salvages and flags it. P2 tightens `SYSTEM_PROMPT` to reduce it.
- **Push rejected (403 / permission denied):** you're not a collaborator yet —
  the repo owner adds your GitHub username under Settings → Collaborators.
