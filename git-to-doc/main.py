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

This file owns argument parsing, file I/O, diff truncation, and the final
markdown rendering. It calls into the other three modules and does not contain
any Ollama or regex logic itself.
"""

import argparse
import os
import sys

import gemma_client
import parser as out_parser  # avoid shadowing the stdlib name `parser`
import prompts

# gemma2:2b has a small context window. Trim very large diffs so we don't blow
# it (and so the model stays focused on the meaningful hunk).
DEFAULT_MAX_DIFF_CHARS = 12000


def parse_args(argv):
    p = argparse.ArgumentParser(
        prog="git-to-doc",
        description="Turn a git diff into a Conventional Commit + changelog snippet using Gemma.",
    )
    p.add_argument("input", help="Path to a .diff or .txt file containing a git diff.")
    p.add_argument("--out", help="Also write the markdown output to this file.")
    p.add_argument("--model", default=gemma_client.DEFAULT_MODEL,
                   help=f"Ollama model name (default: {gemma_client.DEFAULT_MODEL}).")
    p.add_argument("--temperature", type=float, default=0.2,
                   help="Sampling temperature (default: 0.2; lower = more deterministic).")
    p.add_argument("--max-diff-chars", type=int, default=DEFAULT_MAX_DIFF_CHARS,
                   help=f"Truncate diffs longer than this (default: {DEFAULT_MAX_DIFF_CHARS}).")
    p.add_argument("--mock", action="store_true",
                   help="Use a fake model response instead of calling Ollama.")
    return p.parse_args(argv)


def read_input(path, max_chars):
    """Read the diff file, truncating if it's too big for the context window."""
    if not os.path.isfile(path):
        raise SystemExit(f"Error: file not found: {path}")
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    if max_chars and len(text) > max_chars:
        text = text[:max_chars] + "\n\n[... diff truncated for model context ...]"
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
    caller = gemma_client.mock_call_gemma if args.mock else gemma_client.call_gemma

    try:
        raw = caller(
            user_prompt,
            model=args.model,
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

    return 0


if __name__ == "__main__":
    sys.exit(main())
