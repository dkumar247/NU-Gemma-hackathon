"""
tests/test_parser.py  --  OWNER: Person 5 (QA), with Person 4

Tests for the parsing/validation logic. These are the cases the model WILL
throw at you during hardening (Hour 4-5): fenced output, leading filler,
missing markers, backtick-wrapped commits, over-length subjects.

Run either way:
    python tests/test_parser.py        # zero dependencies, prints PASS/FAIL
    python -m pytest tests/            # if you have pytest installed
"""

import os
import sys

# Make the package importable whether run from repo root or tests/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import parser as out_parser  # noqa: E402


def test_clean_output_parses():
    raw = (
        "COMMIT:\n"
        "fix(parser): handle empty input\n\n"
        "CHANGELOG:\n"
        "### Fixed\n- handle empty input\n"
    )
    result = out_parser.parse_model_output(raw)
    assert result["commit"] == "fix(parser): handle empty input"
    assert "### Fixed" in result["changelog"]


def test_strips_outer_code_fence():
    raw = "```\nCOMMIT:\nfeat: add thing\n\nCHANGELOG:\n### Added\n- thing\n```"
    result = out_parser.parse_model_output(raw)
    assert result["commit"] == "feat: add thing"
    assert "thing" in result["changelog"]


def test_ignores_leading_filler():
    raw = (
        "Sure! Here is your documentation:\n\n"
        "COMMIT:\nrefactor: simplify loop\n\n"
        "CHANGELOG:\n### Changed\n- simplify loop\n"
    )
    result = out_parser.parse_model_output(raw)
    assert result["commit"] == "refactor: simplify loop"


def test_strips_backticks_and_list_marker_on_commit():
    raw = "COMMIT:\n- `chore: bump deps`\n\nCHANGELOG:\n### Changed\n- bump deps\n"
    result = out_parser.parse_model_output(raw)
    assert result["commit"] == "chore: bump deps"


def test_missing_markers_falls_back():
    raw = "docs: update readme\n\nSome description that becomes the changelog."
    result = out_parser.parse_model_output(raw)
    assert result["commit"] == "docs: update readme"
    assert "changelog" in result["changelog"].lower()


def test_validate_accepts_good_commit():
    assert out_parser.validate_commit("fix(api): handle null user")[0] is True


def test_validate_rejects_non_conventional():
    valid, reason = out_parser.validate_commit("fixed a bug")
    assert valid is False and reason


def test_validate_rejects_overlong_subject():
    valid, _ = out_parser.validate_commit("feat: " + "x" * 100)
    assert valid is False


def test_salvage_makes_invalid_commit_valid():
    salvaged = out_parser.salvage_commit("fixed a bug")
    assert out_parser.validate_commit(salvaged)[0] is True


def _run_all():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {t.__name__}  -- {e or 'assertion failed'}")
        except Exception as e:  # noqa: BLE001
            print(f"ERROR {t.__name__}  -- {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    sys.exit(_run_all())
