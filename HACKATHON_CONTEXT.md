# Hackathon Context

## Theme: AI-First Developer Efficiencies

**Duration:** 5 Hours Strict | **Execution:** Pure Code, No Frontend UIs Allowed

---

## The Mission

Build highly focused micro-utilities that eliminate developer friction. Write clean software "plumbing" that takes a specific raw technical text input, routes it through a Google Gemma model, and returns a structured, functional text output.

---

## Tracks

### Track 1: The Automagic Documenter (Git-to-Doc)

**The Friction:** Developers write terrible commit messages and skip code documentation updates.

**The Challenge:** Write a local Python script or terminal command that:
1. Accepts a raw git diff output file
2. Parses the diff and sends it to a local Gemma instance
3. Outputs:
   - A perfectly structured Conventional Commit message (e.g., `fix(parser): resolve null pointer exception in json parsing`)
   - An updated markdown README changelog snippet

**Target Output:** A single execution script that takes a `.diff` or `.txt` file and prints out the markdown documentation.

**Sample Data:** 5–10 raw pull request diffs from open GitHub repositories (Flask, Express, Transformers) provided as raw text diff files.

---

### Track 2: The Raw Log Triage Pipeline (Log-to-JSON)

**The Friction:** Production systems emit gigabytes of asynchronous logs; finding what actually failed requires manual regex parsing.

**The Challenge:** Write a pipeline utility that:
1. Consumes a raw text dump of system or server logs
2. Uses Gemma to strip benign noise and locate the precise failing line
3. Converts the anomaly/crash event into a strictly formatted, validated JSON object:

```json
{
  "service_name": "...",
  "timestamp": "...",
  "error_severity": "...",
  "suggested_remediation": "..."
}
```

**Target Output:** A local script that reads a log text stream and returns a cleanly parsed, syntactically perfect JSON string ready for webhook/database injection.

**Sample Data:** 500KB snippet of raw text logs from the [Loghub Repository](https://github.com/logpai/loghub) (HDFS or Linux folder), saved as `sample_production_logs.txt`.

---

## Timeline

| Phase | Time | Goal |
|---|---|---|
| Model Validation | 0:00 – 0:30 | Verify local Gemma instance (`ollama run gemma`), download sample datasets |
| Prompt Tuning | 0:30 – 2:00 | Tune system prompts for structured output (no conversational filler) |
| Script Construction | 2:00 – 4:00 | Build core script logic: file I/O → model call → structured output |
| Edge Case Hardening | 4:00 – 5:00 | Test on unseen samples, handle invalid JSON / truncated lines, prep repo |

---

## Model Setup

```bash
# Verify local Gemma instance
ollama run gemma
```

Confirm you receive text back before starting. Cloud endpoints also accepted if pre-allocated.
