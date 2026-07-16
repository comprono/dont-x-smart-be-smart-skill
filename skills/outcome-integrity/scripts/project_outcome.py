#!/usr/bin/env python3
"""Initialize and validate durable project intent and acceptance state."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_RELATIVE_PATH = Path(".codex") / "PROJECT_OUTCOME.md"
ACCEPTANCE_RELATIVE_PATH = Path(".codex") / "ACCEPTANCE.json"
MAX_PROJECT_LINES = 160
MAX_PROJECT_WORDS = 1800
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
    "## Context Pointers",
    "## Assumptions To Test",
    "## Decisions",
    "## Failure Memory",
    "## Current Slice",
    "## Next",
)
STATE_VALUES = {"active", "blocked", "complete"}
REQUIREMENT_STATES = {"failing", "blocked", "passing"}
EVIDENCE_RANKS = {
    "activity": 0,
    "process-health": 1,
    "focused-test": 2,
    "integration": 3,
    "end-to-end": 4,
    "user-visible": 5,
}
UTC_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
REQUIREMENT_ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9_-]{2,63}$")
PROJECT_STATE_PATTERN = re.compile(r"^State: (active|blocked|complete)$", re.MULTILINE)
PROJECT_UPDATED_PATTERN = re.compile(r"^Updated: (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)$", re.MULTILINE)
CURRENT_SLICE_PATTERN = re.compile(r"^- Acceptance ID: ([A-Z][A-Z0-9_-]{2,63}|none)$", re.MULTILINE)
ACCEPTANCE_AUTHORITY_LINE = "- Authority: .codex/ACCEPTANCE.json"


def project_paths(root: str | Path) -> tuple[Path, Path]:
    resolved = Path(root).expanduser().resolve()
    return resolved / PROJECT_RELATIVE_PATH, resolved / ACCEPTANCE_RELATIVE_PATH


def initialize(root: str | Path) -> dict[str, object]:
    project_path, acceptance_path = project_paths(root)
    asset_root = Path(__file__).resolve().parent.parent / "assets"
    templates = {
        project_path: asset_root / "PROJECT_OUTCOME.template.md",
        acceptance_path: asset_root / "ACCEPTANCE.template.json",
    }
    created: list[str] = []

    for target, template in templates.items():
        if target.exists():
            continue
        if not template.is_file():
            return {
                "ok": False,
                "paths": paths_payload(project_path, acceptance_path),
                "created": created,
                "errors": [f"template missing: {template}"],
            }
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(template, target)
        created.append(str(target))

    return {
        "ok": True,
        "paths": paths_payload(project_path, acceptance_path),
        "created": created,
    }


def validate(root: str | Path, mode: str = "validate") -> dict[str, object]:
    project_path, acceptance_path = project_paths(root)
    errors: list[str] = []
    warnings: list[str] = []
    project = validate_project_file(project_path, errors, warnings)
    acceptance = validate_acceptance_file(acceptance_path, errors, warnings)

    if project and acceptance:
        if project["state"] != acceptance["project_state"]:
            errors.append(
                "project state mismatch: PROJECT_OUTCOME.md="
                f"{project['state']} ACCEPTANCE.json={acceptance['project_state']}"
            )

        current_id = acceptance["current_slice_requirement_id"]
        if project["current_slice_id"] != (current_id or "none"):
            errors.append(
                "current slice mismatch: PROJECT_OUTCOME.md="
                f"{project['current_slice_id']} ACCEPTANCE.json={current_id or 'none'}"
            )

        if acceptance["updated"] < project["updated"]:
            message = "ACCEPTANCE.json is older than PROJECT_OUTCOME.md; reconcile acceptance state"
            if mode in {"resume", "completion"}:
                errors.append(message)
            else:
                warnings.append(message)

        if mode == "resume":
            if acceptance["project_state"] == "active" and current_id is None:
                errors.append("active work requires current_slice_requirement_id")
            if (
                current_id
                and current_id in acceptance["requirements_by_id"]
                and acceptance["requirements_by_id"][current_id]["status"] == "passing"
            ):
                errors.append("current slice already passes; select a remaining requirement or complete the project")

        if mode == "completion":
            if project["state"] != "complete" or acceptance["project_state"] != "complete":
                errors.append("completion requires both project states to be complete")
            if current_id is not None:
                errors.append("completion requires current_slice_requirement_id to be null")
            incomplete = [
                item["id"]
                for item in acceptance["requirements"]
                if item["required"] and item["status"] != "passing"
            ]
            if incomplete:
                errors.append("required acceptance items are not passing: " + ", ".join(incomplete))

    counts = acceptance["counts"] if acceptance else {}
    return {
        "ok": not errors,
        "mode": mode,
        "paths": paths_payload(project_path, acceptance_path),
        "counts": counts,
        "current_slice_requirement_id": (
            acceptance["current_slice_requirement_id"] if acceptance else None
        ),
        "errors": errors,
        "warnings": warnings,
    }


def validate_project_file(
    path: Path, errors: list[str], warnings: list[str]
) -> dict[str, Any] | None:
    if not path.is_file():
        errors.append(f"project outcome missing: {path}")
        return None

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    words = re.findall(r"\b\w+\b", text)

    for heading in REQUIRED_HEADINGS:
        count = lines.count(heading)
        if count != 1:
            errors.append(f"expected exactly one heading: {heading!r}; found {count}")
    if "REPLACE_ME" in text:
        errors.append("PROJECT_OUTCOME.md still contains REPLACE_ME placeholders")
    if len(lines) > MAX_PROJECT_LINES:
        errors.append(f"PROJECT_OUTCOME.md has {len(lines)} lines; maximum is {MAX_PROJECT_LINES}")
    if len(words) > MAX_PROJECT_WORDS:
        errors.append(f"PROJECT_OUTCOME.md has {len(words)} words; maximum is {MAX_PROJECT_WORDS}")
    if ACCEPTANCE_AUTHORITY_LINE not in lines:
        errors.append(f"Done Means must contain exactly: {ACCEPTANCE_AUTHORITY_LINE}")

    state_match = PROJECT_STATE_PATTERN.search(text)
    updated_match = PROJECT_UPDATED_PATTERN.search(text)
    current_match = CURRENT_SLICE_PATTERN.search(text)
    if not state_match:
        errors.append("PROJECT_OUTCOME.md State must be active, blocked, or complete")
    if not updated_match:
        errors.append("PROJECT_OUTCOME.md Updated must use UTC format YYYY-MM-DDTHH:MM:SSZ")
    if not current_match:
        errors.append("Current Slice must contain '- Acceptance ID: REQ-ID' or '- Acceptance ID: none'")

    decisions = section_bullets(lines, "## Decisions", "## Failure Memory")
    failures = section_bullets(lines, "## Failure Memory", "## Current Slice")
    if len(decisions) > 5:
        warnings.append("more than five current decisions; replace stale entries")
    if len(failures) > 5:
        warnings.append("more than five failure invariants; consolidate duplicates")

    if not state_match or not updated_match or not current_match:
        return None
    return {
        "state": state_match.group(1),
        "updated": parse_utc(updated_match.group(1)),
        "current_slice_id": current_match.group(1),
    }


def validate_acceptance_file(
    path: Path, errors: list[str], warnings: list[str]
) -> dict[str, Any] | None:
    if not path.is_file():
        errors.append(f"acceptance registry missing: {path}")
        return None

    raw = path.read_text(encoding="utf-8")
    if "REPLACE_ME" in raw:
        errors.append("ACCEPTANCE.json still contains REPLACE_ME placeholders")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        errors.append(f"ACCEPTANCE.json is invalid JSON: {exc}")
        return None
    if not isinstance(data, dict):
        errors.append("ACCEPTANCE.json root must be an object")
        return None

    if data.get("schema_version") != 1:
        errors.append("ACCEPTANCE.json schema_version must be 1")
    updated_value = data.get("updated_utc")
    updated = validate_utc(updated_value, "updated_utc", errors)
    project_state = data.get("project_state")
    if project_state not in STATE_VALUES:
        errors.append("ACCEPTANCE.json project_state must be active, blocked, or complete")

    current_id = data.get("current_slice_requirement_id")
    if current_id is not None and not valid_requirement_id(current_id):
        errors.append("current_slice_requirement_id must be a valid requirement ID or null")

    requirements = data.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        errors.append("ACCEPTANCE.json requirements must be a non-empty array")
        return None

    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(requirements):
        prefix = f"requirements[{index}]"
        normalized_item = validate_requirement(item, prefix, errors)
        if not normalized_item:
            continue
        requirement_id = normalized_item["id"]
        if requirement_id in seen:
            errors.append(f"duplicate requirement id: {requirement_id}")
        seen.add(requirement_id)
        normalized.append(normalized_item)

    requirements_by_id = {item["id"]: item for item in normalized}
    if current_id is not None and current_id not in requirements_by_id:
        errors.append(f"current_slice_requirement_id does not exist: {current_id}")

    counts = {state: sum(item["status"] == state for item in normalized) for state in REQUIREMENT_STATES}
    counts["required"] = sum(item["required"] for item in normalized)

    if updated is None or project_state not in STATE_VALUES:
        return None
    return {
        "updated": updated,
        "project_state": project_state,
        "current_slice_requirement_id": current_id,
        "requirements": normalized,
        "requirements_by_id": requirements_by_id,
        "counts": counts,
    }


def validate_requirement(
    item: object, prefix: str, errors: list[str]
) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        errors.append(f"{prefix} must be an object")
        return None

    requirement_id = item.get("id")
    description = item.get("description")
    required = item.get("required")
    status = item.get("status")
    minimum = item.get("minimum_evidence_level")
    steps = item.get("acceptance_steps")
    evidence = item.get("evidence")
    blocker = item.get("blocker")

    if not valid_requirement_id(requirement_id):
        errors.append(f"{prefix}.id must match {REQUIREMENT_ID_PATTERN.pattern}")
        return None
    if not nonempty(description):
        errors.append(f"{prefix}.description must be non-empty")
    if not isinstance(required, bool):
        errors.append(f"{prefix}.required must be boolean")
    if status not in REQUIREMENT_STATES:
        errors.append(f"{prefix}.status must be failing, blocked, or passing")
    if minimum not in EVIDENCE_RANKS:
        errors.append(f"{prefix}.minimum_evidence_level is invalid")
    if not isinstance(steps, list) or not steps or not all(nonempty(step) for step in steps):
        errors.append(f"{prefix}.acceptance_steps must contain non-empty strings")
    if not isinstance(evidence, list):
        errors.append(f"{prefix}.evidence must be an array")
        evidence = []

    evidence_levels: list[int] = []
    for evidence_index, entry in enumerate(evidence):
        rank = validate_evidence(entry, f"{prefix}.evidence[{evidence_index}]", errors)
        if rank is not None:
            evidence_levels.append(rank)

    if status == "passing":
        if blocker is not None:
            errors.append(f"{prefix}.blocker must be null when passing")
        minimum_rank = EVIDENCE_RANKS.get(minimum, 999)
        if not evidence_levels or max(evidence_levels) < minimum_rank:
            errors.append(f"{prefix} cannot pass without evidence at level {minimum} or higher")
    elif status == "blocked":
        validate_blocker(blocker, f"{prefix}.blocker", errors)
    elif status == "failing" and blocker is not None:
        errors.append(f"{prefix}.blocker must be null when failing")

    if not isinstance(required, bool) or status not in REQUIREMENT_STATES:
        return None
    return {
        "id": requirement_id,
        "description": description,
        "required": required,
        "status": status,
    }


def validate_evidence(entry: object, prefix: str, errors: list[str]) -> int | None:
    if not isinstance(entry, dict):
        errors.append(f"{prefix} must be an object")
        return None
    level = entry.get("level")
    if level not in EVIDENCE_RANKS:
        errors.append(f"{prefix}.level is invalid")
        return None
    if not nonempty(entry.get("ref")):
        errors.append(f"{prefix}.ref must be non-empty")
    if not nonempty(entry.get("summary")):
        errors.append(f"{prefix}.summary must be non-empty")
    validate_utc(entry.get("verified_utc"), f"{prefix}.verified_utc", errors)
    return EVIDENCE_RANKS[level]


def validate_blocker(blocker: object, prefix: str, errors: list[str]) -> None:
    if not isinstance(blocker, dict):
        errors.append(f"{prefix} must be an object when status is blocked")
        return
    for field in ("owner", "reason", "recovery_trigger", "recovery_action"):
        if not nonempty(blocker.get(field)):
            errors.append(f"{prefix}.{field} must be non-empty")


def validate_utc(value: object, field: str, errors: list[str]) -> datetime | None:
    if not isinstance(value, str) or not UTC_PATTERN.fullmatch(value):
        errors.append(f"{field} must use UTC format YYYY-MM-DDTHH:MM:SSZ")
        return None
    return parse_utc(value)


def parse_utc(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")


def valid_requirement_id(value: object) -> bool:
    return isinstance(value, str) and bool(REQUIREMENT_ID_PATTERN.fullmatch(value))


def nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and "REPLACE_ME" not in value


def section_bullets(lines: list[str], start: str, end: str) -> list[str]:
    try:
        start_index = lines.index(start) + 1
        end_index = lines.index(end, start_index)
    except ValueError:
        return []
    return [line for line in lines[start_index:end_index] if line.startswith("- ")]


def paths_payload(project_path: Path, acceptance_path: Path) -> dict[str, str]:
    return {"project_outcome": str(project_path), "acceptance": str(acceptance_path)}


def emit(result: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    print(json.dumps(result, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init", "validate", "resume", "completion", "path"))
    parser.add_argument("--root", default=".", help="Project root; defaults to the current directory")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "init":
        result = initialize(args.root)
    elif args.command == "path":
        project_path, acceptance_path = project_paths(args.root)
        result = {"ok": True, "paths": paths_payload(project_path, acceptance_path)}
    else:
        result = validate(args.root, mode=args.command)

    emit(result, args.json)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
