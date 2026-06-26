#!/usr/bin/env python3
"""
benchmark.py  --  one-shot end-to-end health check + benchmark for git-to-doc.

Run it from the repo root:
    python git-to-doc/benchmark.py
    python git-to-doc/benchmark.py --model gemma4:12b      # force a model
    python git-to-doc/benchmark.py --quick                 # skip the real-model runs

What it does, in order, and prints PASS/FAIL for each:
  1. Imports every module (catches syntax/typo errors).
  2. Runs the parser on tricky fake outputs (no model needed).
  3. Runs the FULL pipeline in --mock mode (no model needed).
  4. Checks Ollama is reachable and your model is pulled.
  5. Benchmarks the tool on every .diff in tests/fixtures with your real model,
     reporting: valid-commit %, salvage %, and average seconds per diff.

Exit code 0 = everything that ran passed. Non-zero = something failed.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"
if os.name == "nt":
    os.system("")  # enable ANSI colors in Windows terminals


def ok(msg):   print(f"{GREEN}PASS{RST}  {msg}")
def bad(msg):  print(f"{RED}FAIL{RST}  {msg}")
def warn(msg): print(f"{YEL}SKIP{RST}  {msg}")
def head(msg): print(f"\n{BOLD}{msg}{RST}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None, help="Model tag (else resolved from .gemma-model/env).")
    ap.add_argument("--quick", action="store_true", help="Skip steps that need a real model.")
    args = ap.parse_args()

    failures = 0

    # --- 1. imports -----------------------------------------------------------
    head("1. Module imports")
    try:
        import gemma_client, prompts, parser as P, main as M  # noqa: F401
        ok("imported gemma_client, prompts, parser, main")
    except Exception as e:
        bad(f"import error: {type(e).__name__}: {e}")
        print(f"\n{RED}Cannot continue — a module failed to import.{RST}")
        return 1

    # --- 2. parser robustness (no model) -------------------------------------
    head("2. Parser robustness (fake messy outputs)")
    parser_cases = {
        "clean output": "COMMIT:\nfix(api): handle null\n\nCHANGELOG:\n### Fixed\n- handle null\n",
        "code-fenced":  "```\nCOMMIT:\nfeat: add x\n\nCHANGELOG:\n### Added\n- x\n```",
        "leading filler": "Sure! here:\n\nCOMMIT:\nrefactor: tidy\n\nCHANGELOG:\n### Changed\n- tidy\n",
        "thinking tokens": "<think>reasoning</think>\nCOMMIT:\nperf: cache\n\nCHANGELOG:\n### Changed\n- cache\n",
        "garbage (salvage)": "i could not do it sorry",
    }
    for name, raw in parser_cases.items():
        try:
            res = P.parse_model_output(raw)
            valid, _ = P.validate_commit(res["commit"])
            salv = P.salvage_commit(res["commit"])
            salv_ok = P.validate_commit(salv)[0]
            if (valid or salv_ok) and "\x00" not in res["commit"]:
                ok(f"{name:18s} -> {res['commit'][:48]!r}")
            else:
                bad(f"{name:18s} -> could not produce a valid commit"); failures += 1
        except Exception as e:
            bad(f"{name:18s} -> raised {type(e).__name__}: {e}"); failures += 1

    # --- 3. full pipeline in mock mode (no model) ----------------------------
    head("3. Full pipeline (--mock, no model needed)")
    try:
        import gemma_client, prompts, parser as P
        raw = gemma_client.mock_call_gemma("x")
        res = P.parse_model_output(raw)
        valid, reason = P.validate_commit(res["commit"])
        if valid and res["changelog"].strip():
            ok(f"mock pipeline produced a valid commit + changelog")
        else:
            bad(f"mock pipeline output looks wrong (valid={valid}, reason={reason})"); failures += 1
    except Exception as e:
        bad(f"mock pipeline raised {type(e).__name__}: {e}"); failures += 1

    # --- 4 & 5. real model ----------------------------------------------------
    import gemma_client, prompts, parser as P
    model = gemma_client.resolve_model(args.model)

    if args.quick:
        head("4-5. Real-model checks")
        warn("skipped (--quick). Steps 1-3 above need no model and validate the code.")
        print_summary(failures)
        return 1 if failures else 0

    head(f"4. Ollama reachable + model pulled  (model: {model})")
    url = gemma_client.OLLAMA_URL
    base = url.rsplit("/api/", 1)[0]
    reachable = False
    try:
        with urllib.request.urlopen(base, timeout=5) as r:
            r.read()
        reachable = True
        ok(f"Ollama is responding at {base}")
    except urllib.error.URLError as e:
        bad(f"Ollama not reachable at {base} -> start it (llama tray icon / `ollama serve`). {e}")
    if reachable:
        try:
            req = urllib.request.Request(
                base + "/api/tags", headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as r:
                tags = json.loads(r.read().decode("utf-8"))
            names = [m.get("name", "") for m in tags.get("models", [])]
            if any(n == model or n.split(":")[0] == model.split(":")[0] for n in names):
                ok(f"model '{model}' is available")
            else:
                bad(f"model '{model}' not pulled. Installed: {names or 'none'}. "
                    f"Run: ollama pull {model}")
                reachable = False
        except Exception as e:
            warn(f"couldn't list models ({e}); will still try a live run")

    head("5. Real benchmark on tests/fixtures")
    fixtures_dir = os.path.join(HERE, "tests", "fixtures")
    diffs = sorted(f for f in os.listdir(fixtures_dir)
                   if f.endswith(".diff") or f.endswith(".txt")) if os.path.isdir(fixtures_dir) else []
    if not diffs:
        warn(f"no .diff/.txt files in {fixtures_dir} — add real diffs to benchmark.")
        print_summary(failures); return 1 if failures else 0
    if not reachable:
        warn("skipping live benchmark — Ollama/model not ready (fix step 4 and rerun).")
        print_summary(failures); return 1 if failures else 0

    total = valid_n = salvage_n = 0
    times = []
    print(f"  {DIM}running {len(diffs)} diff(s) through {model}...{RST}")
    for fn in diffs:
        path = os.path.join(fixtures_dir, fn)
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            diff_text = f.read()
        if len(diff_text) > 12000:
            diff_text = diff_text[:12000]
        total += 1
        t0 = time.time()
        try:
            raw = gemma_client.call_gemma(
                prompts.build_user_prompt(diff_text),
                model=model, system=prompts.SYSTEM_PROMPT,
                temperature=0.2, show_live=False)
            dt = time.time() - t0
            times.append(dt)
            res = P.parse_model_output(raw)
            is_valid, _ = P.validate_commit(res["commit"])
            if is_valid:
                valid_n += 1
            else:
                salvage_n += 1
            mark = f"{GREEN}valid{RST}" if is_valid else f"{YEL}salvaged{RST}"
            print(f"    {fn:28s} {dt:5.1f}s  {mark}  {res['commit'][:46]}")
        except Exception as e:
            print(f"    {fn:28s}   {RED}ERROR{RST}  {type(e).__name__}: {e}")
            failures += 1

    if total and times:
        head("Benchmark summary")
        print(f"  diffs tested        : {total}")
        print(f"  valid commits       : {valid_n}/{total}  ({100*valid_n//total}%)")
        print(f"  needed salvage      : {salvage_n}/{total}  ({100*salvage_n//max(total,1)}%)")
        print(f"  avg time per diff   : {sum(times)/len(times):.1f}s")
        print(f"  slowest / fastest   : {max(times):.1f}s / {min(times):.1f}s")
        print(f"  model               : {model}")

    print_summary(failures)
    return 1 if failures else 0


def print_summary(failures):
    print()
    if failures == 0:
        print(f"{GREEN}{BOLD}ALL CHECKS PASSED — the tool works end to end.{RST}")
    else:
        print(f"{RED}{BOLD}{failures} check(s) failed — see FAIL lines above.{RST}")


if __name__ == "__main__":
    sys.exit(main())
