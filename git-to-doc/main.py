#!/usr/bin/env python3
"""
main.py  --  OWNER: Person 3 (CLI & orchestration)

The glue. Reads a .diff/.txt file, asks Gemma for documentation, parses it,
validates it, and prints clean markdown (optionally writing it to a file).

Usage:
    python main.py path/to/change.diff
    python main.py change.diff --out docs.md
    python main.py change.diff --mock           # no Ollama needed
    python main.py change.diff --model gemma2:2b --temperature 0.1
    python main.py change.diff --append CHANGELOG.md
    git diff | python main.py -                 # stdin support

This file owns argument parsing, file I/O, diff truncation, and the final
markdown rendering. It calls into the other three modules and does not contain
any Ollama or regex logic itself.
"""

import argparse
import os
import re
import sys

import gemma_client
import parser as out_parser  # avoid shadowing the stdlib name `parser`
import prompts

DEFAULT_MAX_DIFF_CHARS = 50000

# Auto-generated files that add noise without useful signal for commit messages.
_SKIP_FILES = re.compile(
    r"^diff --git a/("
    r".*\.lock"           # uv.lock, poetry.lock, package-lock.json, yarn.lock, etc.
    r"|.*lock\.json"      # package-lock.json variants
    r"|uv\.lock"
    r"|Pipfile\.lock"
    r")",
    re.MULTILINE,
)


def filter_diff(text):
    """Remove auto-generated lockfile hunks from a diff before sending to Gemma."""
    chunks = re.split(r'(?=^diff --git )', text, flags=re.MULTILINE)
    kept, skipped = [], []
    for chunk in chunks:
        if chunk.strip() and _SKIP_FILES.match(chunk):
            fname = chunk.splitlines()[0].replace("diff --git a/", "").split(" ")[0]
            skipped.append(fname)
        else:
            kept.append(chunk)
    if skipped:
        print(f"[skipped generated files: {', '.join(skipped)}]", file=sys.stderr)
    return "".join(kept)


def parse_args(argv):
    p = argparse.ArgumentParser(
        prog="git-to-doc",
        description="Turn a git diff into a Conventional Commit + changelog snippet using Gemma.",
    )
    p.add_argument("input", help="Path to a .diff or .txt file containing a git diff.")
    p.add_argument("--out", help="Also write the markdown output to this file.")
    p.add_argument("--model", default=None,
                   help="Ollama model tag. If omitted, resolves from GEMMA_MODEL "
                        "env, then a .gemma-model file, then a built-in default.")
    p.add_argument("--temperature", type=float, default=0.2,
                   help="Sampling temperature (default: 0.2; lower = more deterministic).")
    p.add_argument("--max-diff-chars", type=int, default=DEFAULT_MAX_DIFF_CHARS,
                   help=f"Truncate diffs longer than this (default: {DEFAULT_MAX_DIFF_CHARS}).")
    p.add_argument("--mock", action="store_true",
                   help="Use a fake model response instead of calling Ollama.")
    p.add_argument("--append", metavar="FILE",
                   help="Prepend the changelog snippet to this file.")
    return p.parse_args(argv)


def read_input(path, max_chars):
    """Read the diff file or stdin, filter generated files, truncate if still too big."""
    if path == "-":
        text = sys.stdin.read()
    else:
        if not os.path.isfile(path):
            raise SystemExit(f"Error: file not found: {path}")
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    text = filter_diff(text)
    if max_chars and len(text) > max_chars:
        original_size = len(text)
        text = text[:max_chars] + "\n\n[... diff truncated for model context ...]"
        print(f"[diff truncated: {original_size} → {max_chars} chars]", file=sys.stderr)
    return text


def render_markdown(commit, changelog, note=None):
    """Assemble the final markdown document that gets printed/written."""
    parts = [
        "## Suggested Commit Message",
        "",
        "```",
        commit,
        "```",
    ]
    if note:
        parts += ["", f"> :warning: {note}. Review before committing."]
    parts += [
        "",
        "## Changelog Snippet",
        "",
        changelog if changelog.strip() else "_(model produced no changelog -- see TODO in prompts.py)_",
        "",
    ]
    return "\n".join(parts)


def main(argv=None):
    args = parse_args(argv)

    diff_text = read_input(args.input, args.max_diff_chars)
    if not diff_text.strip():
        print("Error: input file is empty.", file=sys.stderr)
        return 2

    user_prompt = prompts.build_user_prompt(diff_text)

    if args.mock:
        caller = gemma_client.mock_call_gemma
        model = "(mock)"
    else:
        caller = gemma_client.call_gemma
        model = gemma_client.resolve_model(args.model)
        print(f"[using model: {model}]", file=sys.stderr)

    try:
        raw = caller(
            user_prompt,
            model=None if args.mock else model,
            system=prompts.SYSTEM_PROMPT,
            temperature=args.temperature,
        )
    except gemma_client.GemmaError as e:
        print(f"Model error:\n{e}", file=sys.stderr)
        return 1

    result = out_parser.parse_model_output(raw)
    valid, reason = out_parser.validate_commit(result["commit"])
    if valid:
        commit, note = result["commit"], None
    else:
        commit = out_parser.salvage_commit(result["commit"])
        note = f"model output failed validation ({reason}); auto-corrected to a generic commit"

    markdown = render_markdown(commit, result["changelog"], note)
    print(markdown)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(markdown)
        print(f"\n[written to {args.out}]", file=sys.stderr)

    if args.append:
        changelog = result["changelog"].strip()
        if os.path.isfile(args.append):
            with open(args.append, "r", encoding="utf-8") as f:
                existing = f.read()
            lines = existing.splitlines(keepends=True)
            if lines and lines[0].startswith("# "):
                content = lines[0] + "\n" + changelog + "\n\n" + "".join(lines[1:])
            else:
                content = changelog + "\n\n" + existing
        else:
            content = changelog + "\n"
        with open(args.append, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[changelog prepended to {args.append}]", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())