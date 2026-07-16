#!/usr/bin/env python3
"""Initialize and validate the bounded project outcome ledger."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path


STATE_RELATIVE_PATH = Path(".codex") / "PROJECT_OUTCOME.md"
MAX_LINES = 160
MAX_WORDS = 1800
REQUIRED_HEADINGS = (
    "# Project Outcome",
    "## North Star",
    "## Done Means",
    "## User Intent",
    "## Work Map",
    "### Critical Path",
    "### Add-ons",
    "### Non-goals",
    "## Verified State",
    "## Assumptions To Test",
    "## Decisions",
    "## Failure Memory",
    "## Current Slice",
    "## Next",
)
UPDATED_PATTERN = re.compile(r"^Updated: \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", re.MULTILINE)
STATE_PATTERN = re.compile(r"^State: (active|blocked|complete)$", re.MULTILINE)


def state_path(root: str) -> Path:
    return Path(root).expanduser().resolve() / STATE_RELATIVE_PATH


def initialize(root: str) -> dict[str, object]:
    target = state_path(root)
    if target.exists():
        return {"ok": True, "created": False, "path": str(target)}

    template = Path(__file__).resolve().parent.parent / "assets" / "PROJECT_OUTCOME.template.md"
    if not template.is_file():
        return {"ok": False, "created": False, "path": str(target), "errors": ["template missing"]}

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(template, target)
    return {"ok": True, "created": True, "path": str(target)}


def validate(root: str) -> dict[str, object]:
    target = state_path(root)
    errors: list[str] = []
    warnings: list[str] = []

    if not target.is_file():
        return {"ok": False, "path": str(target), "errors": ["ledger missing"], "warnings": []}

    text = target.read_text(encoding="utf-8")
    lines = text.splitlines()
    words = re.findall(r"\b\w+\b", text)

    for heading in REQUIRED_HEADINGS:
        count = lines.count(heading)
        if count != 1:
            errors.append(f"expected exactly one heading: {heading!r}; found {count}")

    if "REPLACE_ME" in text:
        errors.append("ledger still contains REPLACE_ME placeholders")
    if len(lines) > MAX_LINES:
        errors.append(f"ledger has {len(lines)} lines; maximum is {MAX_LINES}")
    if len(words) > MAX_WORDS:
        errors.append(f"ledger has {len(words)} words; maximum is {MAX_WORDS}")
    if not UPDATED_PATTERN.search(text):
        errors.append("Updated must use UTC format YYYY-MM-DDTHH:MM:SSZ")
    if not STATE_PATTERN.search(text):
        errors.append("State must be active, blocked, or complete")

    decision_lines = section_bullets(lines, "## Decisions", "## Failure Memory")
    failure_lines = section_bullets(lines, "## Failure Memory", "## Current Slice")
    if len(decision_lines) > 5:
        warnings.append("more than five current decisions; replace stale entries")
    if len(failure_lines) > 5:
        warnings.append("more than five failure invariants; consolidate duplicates")

    return {
        "ok": not errors,
        "path": str(target),
        "lines": len(lines),
        "words": len(words),
        "errors": errors,
        "warnings": warnings,
    }


def section_bullets(lines: list[str], start: str, end: str) -> list[str]:
    try:
        start_index = lines.index(start) + 1
        end_index = lines.index(end, start_index)
    except ValueError:
        return []
    return [line for line in lines[start_index:end_index] if line.startswith("- ")]


def emit(result: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return

    print(f"Path: {result.get('path')}")
    if "created" in result:
        print("Created" if result["created"] else "Already exists")
    for warning in result.get("warnings", []):
        print(f"Warning: {warning}")
    for error in result.get("errors", []):
        print(f"Error: {error}")
    print("Valid" if result.get("ok") else "Invalid")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init", "validate", "path"))
    parser.add_argument("--root", default=".", help="Project root; defaults to the current directory")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "init":
        result = initialize(args.root)
    elif args.command == "validate":
        result = validate(args.root)
    else:
        result = {"ok": True, "path": str(state_path(args.root))}

    emit(result, args.json)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
