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
NORTH_STAR_STATES = {"active", "achieved"}
DELIVERY_STAGE_STATES = {"planned", "active", "blocked", "complete"}
COUNTEREVIDENCE_STATES = {"unresolved", "resolved"}
SUPPORTED_SCHEMA_VERSIONS = {1, 2, 3, 4, 5}
PRESERVATION_VALUES = {"stage", "permanent"}
GATE_TIERS = {"change", "pre-release", "release"}
SYSTEM_SCOPES = {"component", "interaction", "end-to-end"}
PROOF_FIDELITIES = {"synthetic", "production-shaped", "production"}
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
PROJECT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")
PROJECT_STATE_PATTERN = re.compile(r"^State: (active|blocked|complete)$", re.MULTILINE)
PROJECT_UPDATED_PATTERN = re.compile(r"^Updated: (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)$", re.MULTILINE)
CURRENT_SLICE_PATTERN = re.compile(r"^- Acceptance ID: ([A-Z][A-Z0-9_-]{2,63}|none)$", re.MULTILINE)
CURRENT_STAGE_PATTERN = re.compile(r"^- Delivery Stage ID: ([A-Z][A-Z0-9_-]{2,63}|none)$", re.MULTILINE)
ACCEPTANCE_AUTHORITY_LINE = "- Authority: .codex/ACCEPTANCE.json"
PRODUCT_OUTCOME_PREFIX = "- Product outcome:"
ACTIVE_PROOF_SLICE_PREFIX = "- Active proof slice:"
PROOF_LIMITS_PREFIX = "- Proof limits:"
NORTH_STAR_OUTCOME_PREFIX = "- North-star outcome:"
CURRENT_DELIVERY_STAGE_PREFIX = "- Current delivery stage:"
STAGE_COMPLETION_BOUNDARY_PREFIX = "- Stage completion boundary:"
ACTIVE_ACCEPTANCE_SLICE_PREFIX = "- Active acceptance slice:"
SLICE_PROOF_LIMITS_PREFIX = "- Slice proof limits:"
EARLIEST_DIVERGENCE_PREFIX = "- Earliest divergent transition:"
STOP_CONDITIONS_PREFIX = "- Stop conditions and attempt limits:"


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
    acceptance = validate_acceptance_file(
        acceptance_path, project_path.parent.parent, errors, warnings
    )

    if project and acceptance:
        schema_version = acceptance["schema_version"]
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

        if schema_version >= 3 and acceptance["outcome_hierarchy"]:
            current_stage_id = acceptance["outcome_hierarchy"]["current_stage_id"]
            if project["current_stage_id"] != (current_stage_id or "none"):
                errors.append(
                    "current delivery stage mismatch: PROJECT_OUTCOME.md="
                    f"{project['current_stage_id']} ACCEPTANCE.json={current_stage_id or 'none'}"
                )

        if acceptance["updated"] < project["updated"]:
            message = "ACCEPTANCE.json is older than PROJECT_OUTCOME.md; reconcile acceptance state"
            if mode in {"resume", "completion"}:
                errors.append(message)
            else:
                warnings.append(message)

        if schema_version == 2:
            for field, present in (
                (PRODUCT_OUTCOME_PREFIX, project["has_product_outcome"]),
                (ACTIVE_PROOF_SLICE_PREFIX, project["has_active_proof_slice"]),
                (PROOF_LIMITS_PREFIX, project["has_proof_limits"]),
            ):
                if not present:
                    errors.append(
                        f"schema version 2 requires a non-empty PROJECT_OUTCOME.md line: {field}"
                    )

        if schema_version >= 3:
            for field, present in (
                (NORTH_STAR_OUTCOME_PREFIX, project["has_north_star_outcome"]),
                (CURRENT_DELIVERY_STAGE_PREFIX, project["has_current_delivery_stage"]),
                (STAGE_COMPLETION_BOUNDARY_PREFIX, project["has_stage_completion_boundary"]),
                (ACTIVE_ACCEPTANCE_SLICE_PREFIX, project["has_active_acceptance_slice"]),
                (SLICE_PROOF_LIMITS_PREFIX, project["has_slice_proof_limits"]),
            ):
                if not present:
                    errors.append(
                        f"schema version {schema_version} requires a non-empty PROJECT_OUTCOME.md line: {field}"
                    )

        if schema_version >= 5:
            for field, present in (
                (EARLIEST_DIVERGENCE_PREFIX, project["has_earliest_divergence"]),
                (STOP_CONDITIONS_PREFIX, project["has_stop_conditions"]),
            ):
                if not present:
                    errors.append(
                        f"schema version {schema_version} requires a non-empty PROJECT_OUTCOME.md line: {field}"
                    )

        if mode == "resume":
            if acceptance["project_state"] == "active" and current_id is None:
                errors.append("active work requires current_slice_requirement_id")
            if (
                current_id
                and current_id in acceptance["requirements_by_id"]
                and acceptance["requirements_by_id"][current_id]["status"] == "passing"
            ):
                errors.append("current slice already passes; select a remaining requirement or complete the project")
            if schema_version >= 3 and acceptance["outcome_hierarchy"] and acceptance["project_state"] == "active":
                hierarchy = acceptance["outcome_hierarchy"]
                if hierarchy["current_stage_id"] is None:
                    errors.append("active work requires outcome_hierarchy.current_stage_id")

        if mode == "completion":
            if schema_version != 5:
                errors.append(
                    "completion requires ACCEPTANCE.json schema_version 5; migrate legacy state first"
                )
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
            if schema_version >= 2:
                covered_capabilities = {
                    capability_id
                    for item in acceptance["requirements"]
                    if item["required"] and item["status"] == "passing"
                    for capability_id in item["capability_ids"]
                }
                uncovered = [
                    item["id"]
                    for item in acceptance["outcome_capabilities"]
                    if item["required"] and item["id"] not in covered_capabilities
                ]
                if uncovered:
                    errors.append(
                        "required outcome capabilities lack passing coverage: "
                        + ", ".join(uncovered)
                    )
                unresolved = sum(
                    item["unresolved_counterevidence"]
                    for item in acceptance["requirements"]
                )
                if unresolved:
                    errors.append(
                        f"completion has {unresolved} unresolved counterevidence item(s)"
                    )
            if schema_version >= 3 and acceptance["outcome_hierarchy"]:
                hierarchy = acceptance["outcome_hierarchy"]
                if hierarchy["north_star"]["status"] != "achieved":
                    errors.append("completion requires the north star status to be achieved")
                if hierarchy["current_stage_id"] is not None:
                    errors.append("completion requires outcome_hierarchy.current_stage_id to be null")
                incomplete_stages = [
                    stage["id"]
                    for stage in hierarchy["delivery_stages"]
                    if stage["required"] and stage["status"] != "complete"
                ]
                if incomplete_stages:
                    errors.append(
                        "required delivery stages are not complete: "
                        + ", ".join(incomplete_stages)
                    )

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
    current_stage_match = CURRENT_STAGE_PATTERN.search(text)
    if not state_match:
        errors.append("PROJECT_OUTCOME.md State must be active, blocked, or complete")
    if not updated_match:
        errors.append("PROJECT_OUTCOME.md Updated must use UTC format YYYY-MM-DDTHH:MM:SSZ")
    if not current_match:
        errors.append("Current Slice must contain '- Acceptance ID: REQ-ID' or '- Acceptance ID: none'")

    decisions = section_bullets(lines, "## Decisions", "## Failure Memory")
    failure_end = "## Causal Control" if "## Causal Control" in lines else "## Current Slice"
    failures = section_bullets(lines, "## Failure Memory", failure_end)
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
        "current_stage_id": current_stage_match.group(1) if current_stage_match else "none",
        "has_product_outcome": has_nonempty_prefixed_line(
            lines, PRODUCT_OUTCOME_PREFIX
        ),
        "has_active_proof_slice": has_nonempty_prefixed_line(
            lines, ACTIVE_PROOF_SLICE_PREFIX
        ),
        "has_proof_limits": has_nonempty_prefixed_line(lines, PROOF_LIMITS_PREFIX),
        "has_north_star_outcome": has_nonempty_prefixed_line(lines, NORTH_STAR_OUTCOME_PREFIX),
        "has_current_delivery_stage": has_nonempty_prefixed_line(lines, CURRENT_DELIVERY_STAGE_PREFIX),
        "has_stage_completion_boundary": has_nonempty_prefixed_line(lines, STAGE_COMPLETION_BOUNDARY_PREFIX),
        "has_active_acceptance_slice": has_nonempty_prefixed_line(lines, ACTIVE_ACCEPTANCE_SLICE_PREFIX),
        "has_slice_proof_limits": has_nonempty_prefixed_line(lines, SLICE_PROOF_LIMITS_PREFIX),
        "has_earliest_divergence": has_nonempty_prefixed_line(lines, EARLIEST_DIVERGENCE_PREFIX),
        "has_stop_conditions": has_nonempty_prefixed_line(lines, STOP_CONDITIONS_PREFIX),
    }


def validate_acceptance_file(
    path: Path, root: Path, errors: list[str], warnings: list[str]
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

    schema_version = data.get("schema_version")
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        errors.append("ACCEPTANCE.json schema_version must be 1, 2, 3, 4, or 5")
        return None
    if schema_version in {1, 2, 3, 4}:
        warnings.append(
            f"legacy ACCEPTANCE.json schema_version {schema_version} is readable for recovery but cannot prove new completion"
        )

    updated_value = data.get("updated_utc")
    updated = validate_utc(updated_value, "updated_utc", errors)
    project_state = data.get("project_state")
    if project_state not in STATE_VALUES:
        errors.append("ACCEPTANCE.json project_state must be active, blocked, or complete")

    if schema_version >= 2:
        project_identity = validate_project_identity(
            data.get("project_identity"), root, errors
        )
        outcome_hierarchy = (
            validate_outcome_hierarchy(
                data.get("outcome_hierarchy"), errors, schema_version=schema_version
            )
            if schema_version >= 3
            else None
        )
        known_stage_ids = {
            stage["id"] for stage in outcome_hierarchy["delivery_stages"]
        } if outcome_hierarchy else set()
        outcome_capabilities = validate_outcome_capabilities(
            data.get("outcome_capabilities"), errors,
            schema_version=schema_version, known_stage_ids=known_stage_ids
        )
        capability_floors = (
            validate_capability_floors(
                data.get("capability_floors"), errors,
                known_capability_ids={item["id"] for item in outcome_capabilities},
                known_fitness_dimension_ids=set(outcome_hierarchy["fitness_dimension_ids"]),
            )
            if schema_version >= 4 and outcome_hierarchy else []
        )
        identity_requirements = validate_identity_requirements(
            data.get("identity_requirements"), errors
        )
    else:
        project_identity = None
        outcome_hierarchy = None
        outcome_capabilities = []
        capability_floors = []
        identity_requirements = []

    capability_ids = {item["id"] for item in outcome_capabilities}
    identity_ids = {item["id"] for item in identity_requirements}

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
        normalized_item = validate_requirement(
            item,
            prefix,
            errors,
            schema_version=schema_version,
            known_capability_ids=capability_ids,
            known_identity_ids=identity_ids,
            known_stage_ids=known_stage_ids if schema_version >= 3 else set(),
            capability_stage_ids={item["id"]: item.get("stage_id") for item in outcome_capabilities},
        )
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

    if schema_version >= 3 and outcome_hierarchy:
        current_stage_id = outcome_hierarchy["current_stage_id"]
        if current_id in requirements_by_id and current_stage_id is not None:
            if requirements_by_id[current_id]["stage_id"] != current_stage_id:
                errors.append(
                    "current slice must belong to outcome_hierarchy.current_stage_id"
                )
        validate_hierarchy_coverage(
            outcome_hierarchy, outcome_capabilities, normalized, errors
        )
    if schema_version >= 4 and outcome_hierarchy:
        validate_capability_preservation(
            outcome_hierarchy, outcome_capabilities, capability_floors,
            normalized, errors, schema_version=schema_version
        )

    counts = {
        state: sum(item["status"] == state for item in normalized)
        for state in REQUIREMENT_STATES
    }
    counts["required"] = sum(item["required"] for item in normalized)
    if schema_version >= 2:
        counts["required_capabilities"] = sum(
            item["required"] for item in outcome_capabilities
        )
        counts["unresolved_counterevidence"] = sum(
            item["unresolved_counterevidence"] for item in normalized
        )

    if updated is None or project_state not in STATE_VALUES:
        return None
    return {
        "schema_version": schema_version,
        "updated": updated,
        "project_state": project_state,
        "project_identity": project_identity,
        "outcome_hierarchy": outcome_hierarchy,
        "outcome_capabilities": outcome_capabilities,
        "capability_floors": capability_floors,
        "identity_requirements": identity_requirements,
        "current_slice_requirement_id": current_id,
        "requirements": normalized,
        "requirements_by_id": requirements_by_id,
        "counts": counts,
    }


def validate_project_identity(
    item: object, root: Path, errors: list[str]
) -> dict[str, Any] | None:
    prefix = "project_identity"
    if not isinstance(item, dict):
        errors.append(f"{prefix} must be an object for schema version 2 or 3")
        return None
    project_id = item.get("id")
    if not isinstance(project_id, str) or not PROJECT_ID_PATTERN.fullmatch(project_id):
        errors.append(f"{prefix}.id must match {PROJECT_ID_PATTERN.pattern}")
    markers = item.get("root_markers")
    if not isinstance(markers, list) or not markers:
        errors.append(f"{prefix}.root_markers must be a non-empty array")
        return None

    normalized_markers: list[str] = []
    resolved_root = root.resolve()
    for index, marker in enumerate(markers):
        field = f"{prefix}.root_markers[{index}]"
        if not nonempty(marker):
            errors.append(f"{field} must be a non-empty relative path")
            continue
        marker_path = Path(marker)
        if marker_path.is_absolute() or marker in {".", ".."} or ".." in marker_path.parts:
            errors.append(f"{field} must stay within the project root")
            continue
        target = (resolved_root / marker_path).resolve()
        try:
            target.relative_to(resolved_root)
        except ValueError:
            errors.append(f"{field} resolves outside the project root")
            continue
        if not target.exists():
            errors.append(f"{field} does not exist under the selected project root: {marker}")
        normalized_markers.append(marker)

    return {"id": project_id, "root_markers": normalized_markers}


def validate_declared_ids(
    values: object, prefix: str, errors: list[str], *, required: bool
) -> list[str]:
    if not isinstance(values, list) or (required and not values):
        errors.append(f"{prefix} must be {'a non-empty array' if required else 'an array'}")
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(values):
        if not valid_requirement_id(value):
            errors.append(f"{prefix}[{index}] must match {REQUIREMENT_ID_PATTERN.pattern}")
            continue
        if value in seen:
            errors.append(f"{prefix} contains duplicate ID: {value}")
        seen.add(value)
        normalized.append(value)
    return normalized


def validate_outcome_hierarchy(
    item: object, errors: list[str], *, schema_version: int
) -> dict[str, Any] | None:
    prefix = "outcome_hierarchy"
    if not isinstance(item, dict):
        errors.append(f"{prefix} must be an object for schema version 3")
        return None

    north_star = item.get("north_star")
    if not isinstance(north_star, dict):
        errors.append(f"{prefix}.north_star must be an object")
        return None
    north_star_id = north_star.get("id")
    if not valid_requirement_id(north_star_id):
        errors.append(f"{prefix}.north_star.id must match {REQUIREMENT_ID_PATTERN.pattern}")
    if not nonempty(north_star.get("description")):
        errors.append(f"{prefix}.north_star.description must be non-empty")
    if north_star.get("status") not in NORTH_STAR_STATES:
        errors.append(f"{prefix}.north_star.status must be active or achieved")
    fitness_dimension_ids: list[str] = []
    if schema_version >= 4:
        dimensions = north_star.get("fitness_dimensions")
        if not isinstance(dimensions, list) or len(dimensions) < 2:
            errors.append(
                f"{prefix}.north_star.fitness_dimensions must contain at least two balanced outcome dimensions"
            )
        else:
            seen_dimensions: set[str] = set()
            for index, dimension in enumerate(dimensions):
                dimension_prefix = f"{prefix}.north_star.fitness_dimensions[{index}]"
                if not isinstance(dimension, dict):
                    errors.append(f"{dimension_prefix} must be an object")
                    continue
                dimension_id = dimension.get("id")
                if not valid_requirement_id(dimension_id):
                    errors.append(f"{dimension_prefix}.id must match {REQUIREMENT_ID_PATTERN.pattern}")
                    continue
                if dimension_id in seen_dimensions:
                    errors.append(f"duplicate fitness dimension id: {dimension_id}")
                seen_dimensions.add(dimension_id)
                if not nonempty(dimension.get("description")):
                    errors.append(f"{dimension_prefix}.description must be non-empty")
                fitness_dimension_ids.append(dimension_id)

    stages = item.get("delivery_stages")
    if not isinstance(stages, list) or not stages:
        errors.append(f"{prefix}.delivery_stages must be a non-empty array")
        return None
    normalized_stages: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, stage in enumerate(stages):
        stage_prefix = f"{prefix}.delivery_stages[{index}]"
        if not isinstance(stage, dict):
            errors.append(f"{stage_prefix} must be an object")
            continue
        stage_id = stage.get("id")
        if not valid_requirement_id(stage_id):
            errors.append(f"{stage_prefix}.id must match {REQUIREMENT_ID_PATTERN.pattern}")
            continue
        if stage_id in seen:
            errors.append(f"duplicate delivery stage id: {stage_id}")
        seen.add(stage_id)
        if stage.get("parent_outcome_id") != north_star_id:
            errors.append(f"{stage_prefix}.parent_outcome_id must equal the north star id")
        if not nonempty(stage.get("description")):
            errors.append(f"{stage_prefix}.description must be non-empty")
        if not isinstance(stage.get("required"), bool):
            errors.append(f"{stage_prefix}.required must be boolean")
            continue
        if stage.get("status") not in DELIVERY_STAGE_STATES:
            errors.append(f"{stage_prefix}.status must be planned, active, blocked, or complete")
            continue
        normalized_stages.append({
            "id": stage_id,
            "parent_outcome_id": stage.get("parent_outcome_id"),
            "description": stage.get("description"),
            "required": stage["required"],
            "status": stage.get("status"),
            "preserves_capability_ids": validate_declared_ids(
                stage.get("preserves_capability_ids"),
                f"{stage_prefix}.preserves_capability_ids", errors,
                required=schema_version >= 4,
            ) if schema_version >= 4 else [],
        })

    current_stage_id = item.get("current_stage_id")
    if current_stage_id is not None and current_stage_id not in seen:
        errors.append(f"{prefix}.current_stage_id does not identify a declared delivery stage")
    current_stage = next(
        (stage for stage in normalized_stages if stage["id"] == current_stage_id), None
    )
    if current_stage and current_stage["status"] not in {"active", "blocked"}:
        errors.append(f"{prefix}.current_stage_id must identify an active or blocked stage")
    if north_star.get("status") == "achieved":
        incomplete = [
            stage["id"] for stage in normalized_stages
            if stage["required"] and stage["status"] != "complete"
        ]
        if incomplete:
            errors.append(
                "north star cannot be achieved while required delivery stages are incomplete: "
                + ", ".join(incomplete)
            )

    return {
        "north_star": {
            "id": north_star_id,
            "description": north_star.get("description"),
            "status": north_star.get("status"),
        },
        "fitness_dimension_ids": fitness_dimension_ids,
        "delivery_stages": normalized_stages,
        "current_stage_id": current_stage_id,
    }


def validate_outcome_capabilities(
    items: object, errors: list[str], *, schema_version: int,
    known_stage_ids: set[str]
) -> list[dict[str, Any]]:
    if not isinstance(items, list) or not items:
        errors.append("outcome_capabilities must be a non-empty array for schema version 2 or 3")
        return []
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        prefix = f"outcome_capabilities[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        item_id = item.get("id")
        if not valid_requirement_id(item_id):
            errors.append(f"{prefix}.id must match {REQUIREMENT_ID_PATTERN.pattern}")
            continue
        if item_id in seen:
            errors.append(f"duplicate outcome capability id: {item_id}")
        seen.add(item_id)
        if not nonempty(item.get("description")):
            errors.append(f"{prefix}.description must be non-empty")
        if not isinstance(item.get("required"), bool):
            errors.append(f"{prefix}.required must be boolean")
            continue
        stage_id = item.get("stage_id") if schema_version == 3 else None
        if schema_version >= 3:
            stage_id = item.get("stage_id")
        if schema_version >= 3 and stage_id not in known_stage_ids:
            errors.append(f"{prefix}.stage_id must identify a declared delivery stage")
        preservation = item.get("preservation") if schema_version >= 4 else "stage"
        if schema_version >= 4 and preservation not in PRESERVATION_VALUES:
            errors.append(f"{prefix}.preservation must be stage or permanent")
        normalized.append(
            {
                "id": item_id,
                "description": item.get("description"),
                "required": item["required"],
                "stage_id": stage_id,
                "preservation": preservation,
            }
        )
    return normalized


def validate_hierarchy_coverage(
    hierarchy: dict[str, Any], capabilities: list[dict[str, Any]],
    requirements: list[dict[str, Any]], errors: list[str]
) -> None:
    for stage in hierarchy["delivery_stages"]:
        if stage["status"] != "complete":
            continue
        required_capabilities = {
            item["id"] for item in capabilities
            if item["required"] and item["stage_id"] == stage["id"]
        }
        passing_coverage = {
            capability_id
            for item in requirements
            if item["stage_id"] == stage["id"] and item["status"] == "passing"
            for capability_id in item["capability_ids"]
        }
        missing_capabilities = sorted(required_capabilities - passing_coverage)
        if missing_capabilities:
            errors.append(
                f"delivery stage {stage['id']} cannot be complete without passing capability coverage: "
                + ", ".join(missing_capabilities)
            )
        incomplete_requirements = [
            item["id"] for item in requirements
            if item["stage_id"] == stage["id"]
            and item["required"] and item["status"] != "passing"
        ]
        if incomplete_requirements:
            errors.append(
                f"delivery stage {stage['id']} cannot be complete while required slices are not passing: "
                + ", ".join(incomplete_requirements)
            )


def validate_capability_floors(
    items: object, errors: list[str], *, known_capability_ids: set[str],
    known_fitness_dimension_ids: set[str]
) -> list[dict[str, Any]]:
    if not isinstance(items, list) or not items:
        errors.append("capability_floors must be a non-empty array for schema version 4 or later")
        return []
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_capabilities: set[str] = set()
    for index, item in enumerate(items):
        prefix = f"capability_floors[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        floor_id = item.get("id")
        if not valid_requirement_id(floor_id):
            errors.append(f"{prefix}.id must match {REQUIREMENT_ID_PATTERN.pattern}")
            continue
        if floor_id in seen_ids:
            errors.append(f"duplicate capability floor id: {floor_id}")
        seen_ids.add(floor_id)
        capability_id = item.get("capability_id")
        if capability_id not in known_capability_ids:
            errors.append(f"{prefix}.capability_id references unknown ID: {capability_id}")
        if capability_id in seen_capabilities:
            errors.append(f"duplicate capability floor for: {capability_id}")
        seen_capabilities.add(capability_id)
        if not nonempty(item.get("invariant")):
            errors.append(f"{prefix}.invariant must be non-empty")
        dimension_ids = validate_declared_ids(
            item.get("fitness_dimension_ids"), f"{prefix}.fitness_dimension_ids",
            errors, required=True
        )
        for dimension_id in dimension_ids:
            if dimension_id not in known_fitness_dimension_ids:
                errors.append(f"{prefix}.fitness_dimension_ids references unknown ID: {dimension_id}")
        proof_ladder = item.get("proof_ladder")
        normalized_ladder: dict[str, list[str]] = {}
        if not isinstance(proof_ladder, dict):
            errors.append(f"{prefix}.proof_ladder must be an object")
        else:
            for tier in sorted(GATE_TIERS):
                normalized_ladder[tier] = validate_declared_ids(
                    proof_ladder.get(tier), f"{prefix}.proof_ladder.{tier}",
                    errors, required=True
                )
            ladder_ids = [
                requirement_id
                for requirement_ids in normalized_ladder.values()
                for requirement_id in requirement_ids
            ]
            if len(ladder_ids) != len(set(ladder_ids)):
                errors.append(f"{prefix}.proof_ladder tiers must use distinct requirements")
        optional_state = item.get("optional_supporting_state")
        if not isinstance(optional_state, list) or not all(nonempty(value) for value in optional_state):
            errors.append(f"{prefix}.optional_supporting_state must be an array of non-empty strings")
            optional_state = []
        independence_ids = validate_declared_ids(
            item.get("independence_requirement_ids"),
            f"{prefix}.independence_requirement_ids", errors,
            required=bool(optional_state)
        )
        normalized.append({
            "id": floor_id,
            "capability_id": capability_id,
            "fitness_dimension_ids": dimension_ids,
            "proof_ladder": normalized_ladder,
            "optional_supporting_state": optional_state,
            "independence_requirement_ids": independence_ids,
        })
    return normalized


def validate_capability_preservation(
    hierarchy: dict[str, Any], capabilities: list[dict[str, Any]],
    floors: list[dict[str, Any]], requirements: list[dict[str, Any]],
    errors: list[str], *, schema_version: int
) -> None:
    capability_by_id = {item["id"]: item for item in capabilities}
    requirement_by_id = {item["id"]: item for item in requirements}
    permanent_ids = {
        item["id"] for item in capabilities
        if item["required"] and item["preservation"] == "permanent"
    }
    floor_capability_ids = {item["capability_id"] for item in floors}
    missing_floors = sorted(permanent_ids - floor_capability_ids)
    if missing_floors:
        errors.append(
            "permanent capabilities require capability floors: " + ", ".join(missing_floors)
        )
    nonpermanent_floors = sorted(floor_capability_ids - permanent_ids)
    if nonpermanent_floors:
        errors.append(
            "capability floors may reference only required permanent capabilities: "
            + ", ".join(nonpermanent_floors)
        )

    for stage in hierarchy["delivery_stages"]:
        declared = set(stage["preserves_capability_ids"])
        unknown = sorted(declared - set(capability_by_id))
        if unknown:
            errors.append(
                f"delivery stage {stage['id']} preserves unknown capabilities: " + ", ".join(unknown)
            )
        missing = sorted(permanent_ids - declared)
        if missing:
            errors.append(
                f"delivery stage {stage['id']} does not preserve permanent capabilities: "
                + ", ".join(missing)
            )

    covered_dimensions: set[str] = set()
    for floor in floors:
        capability_id = floor["capability_id"]
        covered_dimensions.update(floor["fitness_dimension_ids"])
        for tier, requirement_ids in floor["proof_ladder"].items():
            for requirement_id in requirement_ids:
                requirement = requirement_by_id.get(requirement_id)
                if not requirement:
                    errors.append(
                        f"capability floor {floor['id']} {tier} gate references unknown requirement: {requirement_id}"
                    )
                    continue
                if capability_id not in requirement["capability_ids"]:
                    errors.append(
                        f"capability floor {floor['id']} {tier} gate requirement {requirement_id} does not cover {capability_id}"
                    )
                if not requirement["required"]:
                    errors.append(
                        f"capability floor {floor['id']} {tier} gate requirement {requirement_id} must be required"
                    )
                if tier not in requirement["gate_tiers"]:
                    errors.append(
                        f"capability floor {floor['id']} {tier} gate requirement {requirement_id} lacks that gate tier"
                    )
                minimum_rank = EVIDENCE_RANKS.get(requirement["minimum_evidence_level"], -1)
                if tier == "change" and minimum_rank > EVIDENCE_RANKS["focused-test"]:
                    errors.append(f"change gate {requirement_id} must remain focused-test strength or cheaper")
                if tier == "pre-release" and minimum_rank < EVIDENCE_RANKS["integration"]:
                    errors.append(f"pre-release gate {requirement_id} requires integration evidence or stronger")
                if tier == "release" and minimum_rank < EVIDENCE_RANKS["end-to-end"]:
                    errors.append(f"release gate {requirement_id} requires end-to-end evidence or stronger")
                if schema_version >= 5:
                    proof_path = requirement.get("proof_path") or {}
                    fidelity = proof_path.get("fidelity")
                    if tier == "change" and requirement["system_scope"] not in {"interaction", "end-to-end"}:
                        errors.append(
                            f"permanent-floor change gate {requirement_id} must cross an interaction or end-to-end boundary"
                        )
                    if tier in {"change", "pre-release"} and fidelity not in {"production-shaped", "production"}:
                        errors.append(
                            f"{tier} gate {requirement_id} must use production-shaped or production proof fidelity"
                        )
                    if tier == "release" and fidelity != "production":
                        errors.append(
                            f"release gate {requirement_id} must use production proof fidelity"
                        )
        for requirement_id in floor["independence_requirement_ids"]:
            requirement = requirement_by_id.get(requirement_id)
            if not requirement:
                errors.append(
                    f"capability floor {floor['id']} independence gate references unknown requirement: {requirement_id}"
                )
            elif capability_id not in requirement["capability_ids"]:
                errors.append(
                    f"capability floor {floor['id']} independence gate {requirement_id} does not cover {capability_id}"
                )
            else:
                if not requirement["required"]:
                    errors.append(
                        f"capability floor {floor['id']} independence gate {requirement_id} must be required"
                    )
                minimum_rank = EVIDENCE_RANKS.get(requirement["minimum_evidence_level"], -1)
                if "pre-release" not in requirement["gate_tiers"]:
                    errors.append(
                        f"capability floor {floor['id']} independence gate {requirement_id} must be pre-release"
                    )
                if minimum_rank < EVIDENCE_RANKS["integration"]:
                    errors.append(
                        f"capability floor {floor['id']} independence gate {requirement_id} requires integration evidence or stronger"
                    )
                if requirement["system_scope"] not in {"interaction", "end-to-end"}:
                    errors.append(
                        f"capability floor {floor['id']} independence gate {requirement_id} must exercise an interaction or end-to-end path"
                    )

    missing_dimensions = sorted(set(hierarchy["fitness_dimension_ids"]) - covered_dimensions)
    if missing_dimensions:
        errors.append(
            "north-star fitness dimensions lack permanent capability coverage: "
            + ", ".join(missing_dimensions)
        )

    for stage in hierarchy["delivery_stages"]:
        stage_requirements = [item for item in requirements if item["stage_id"] == stage["id"]]
        whole_system = [
            item for item in stage_requirements
            if item["required"] and item["system_scope"] == "end-to-end"
            and "release" in item["gate_tiers"]
            and permanent_ids.issubset(set(item["capability_ids"]))
            and (schema_version < 5 or (item.get("proof_path") or {}).get("fidelity") == "production")
        ]
        if not whole_system:
            errors.append(
                f"delivery stage {stage['id']} requires one end-to-end release gate covering every permanent capability"
            )


def validate_identity_requirements(
    items: object, errors: list[str]
) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        errors.append("identity_requirements must be an array for schema version 2 or 3")
        return []
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        prefix = f"identity_requirements[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        item_id = item.get("id")
        if not valid_requirement_id(item_id):
            errors.append(f"{prefix}.id must match {REQUIREMENT_ID_PATTERN.pattern}")
            continue
        if item_id in seen:
            errors.append(f"duplicate identity requirement id: {item_id}")
        seen.add(item_id)
        if not nonempty(item.get("description")):
            errors.append(f"{prefix}.description must be non-empty")
        if not isinstance(item.get("substitutable"), bool):
            errors.append(f"{prefix}.substitutable must be boolean")
            continue
        normalized.append(
            {
                "id": item_id,
                "description": item.get("description"),
                "substitutable": item["substitutable"],
            }
        )
    return normalized


def validate_requirement(
    item: object,
    prefix: str,
    errors: list[str],
    *,
    schema_version: int,
    known_capability_ids: set[str],
    known_identity_ids: set[str],
    known_stage_ids: set[str],
    capability_stage_ids: dict[str, str | None],
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

    if schema_version >= 2:
        capability_ids = validate_id_references(
            item.get("capability_ids"),
            f"{prefix}.capability_ids",
            known_capability_ids,
            errors,
            require_nonempty=True,
        )
        identity_ids = validate_id_references(
            item.get("identity_ids"),
            f"{prefix}.identity_ids",
            known_identity_ids,
            errors,
            require_nonempty=False,
        )
        if not nonempty(item.get("proof_scope")):
            errors.append(f"{prefix}.proof_scope must be non-empty")
        if not nonempty(item.get("proof_limits")):
            errors.append(f"{prefix}.proof_limits must be non-empty")
        step_ids = validate_acceptance_steps(steps, prefix, errors)
        unresolved_counterevidence = validate_counterevidence(
            item.get("counterevidence"), f"{prefix}.counterevidence", errors
        )
        stage_id = item.get("stage_id") if schema_version >= 3 else None
        if schema_version >= 3:
            if stage_id not in known_stage_ids:
                errors.append(f"{prefix}.stage_id must identify a declared delivery stage")
            cross_stage = [
                capability_id for capability_id in capability_ids
                if capability_stage_ids.get(capability_id) != stage_id
            ]
            if cross_stage:
                errors.append(
                    f"{prefix}.capability_ids must belong to its delivery stage: "
                    + ", ".join(cross_stage)
                )
        if schema_version >= 4:
            raw_gate_tiers = item.get("gate_tiers")
            if not isinstance(raw_gate_tiers, list) or not raw_gate_tiers:
                errors.append(f"{prefix}.gate_tiers must be a non-empty array")
                gate_tiers = []
            else:
                gate_tiers = []
                for tier in raw_gate_tiers:
                    if tier not in GATE_TIERS:
                        errors.append(f"{prefix}.gate_tiers contains invalid tier: {tier}")
                    elif tier not in gate_tiers:
                        gate_tiers.append(tier)
            system_scope = item.get("system_scope")
            if system_scope not in SYSTEM_SCOPES:
                errors.append(f"{prefix}.system_scope must be component, interaction, or end-to-end")
            proof_path = (
                validate_proof_path(item.get("proof_path"), f"{prefix}.proof_path", errors)
                if schema_version >= 5 else None
            )
            if schema_version >= 5 and proof_path:
                fidelity = proof_path["fidelity"]
                if "pre-release" in gate_tiers and (
                    system_scope == "component" or fidelity == "synthetic"
                ):
                    errors.append(
                        f"{prefix} pre-release proof must be production-shaped or production interaction evidence"
                    )
                if "release" in gate_tiers and (
                    system_scope != "end-to-end" or fidelity != "production"
                ):
                    errors.append(
                        f"{prefix} release proof must be production-fidelity end-to-end evidence"
                    )
        else:
            gate_tiers = []
            system_scope = None
            proof_path = None
    else:
        capability_ids = []
        identity_ids = []
        step_ids = []
        unresolved_counterevidence = 0
        stage_id = None
        gate_tiers = []
        system_scope = None
        proof_path = None
        if not isinstance(steps, list) or not steps or not all(nonempty(step) for step in steps):
            errors.append(f"{prefix}.acceptance_steps must contain non-empty strings")

    if not isinstance(evidence, list):
        errors.append(f"{prefix}.evidence must be an array")
        evidence = []

    normalized_evidence: list[dict[str, Any]] = []
    for evidence_index, entry in enumerate(evidence):
        normalized_entry = validate_evidence(
            entry,
            f"{prefix}.evidence[{evidence_index}]",
            errors,
            schema_version=schema_version,
            known_step_ids=set(step_ids),
            known_identity_ids=set(identity_ids),
        )
        if normalized_entry is not None:
            normalized_evidence.append(normalized_entry)

    if status == "passing":
        if blocker is not None:
            errors.append(f"{prefix}.blocker must be null when passing")
        minimum_rank = EVIDENCE_RANKS.get(minimum, 999)
        sufficient = [
            entry for entry in normalized_evidence if entry["rank"] >= minimum_rank
        ]
        if not sufficient:
            errors.append(
                f"{prefix} cannot pass without evidence at level {minimum} or higher"
            )
        if schema_version >= 2:
            covered_steps = {
                step_id for entry in sufficient for step_id in entry["step_ids"]
            }
            missing_steps = [step_id for step_id in step_ids if step_id not in covered_steps]
            if missing_steps:
                errors.append(
                    f"{prefix} cannot pass without sufficient evidence for steps: "
                    + ", ".join(missing_steps)
                )
            covered_identities = {
                identity_id
                for entry in sufficient
                for identity_id in entry["identity_ids"]
            }
            missing_identities = [
                identity_id
                for identity_id in identity_ids
                if identity_id not in covered_identities
            ]
            if missing_identities:
                errors.append(
                    f"{prefix} cannot pass without exact identity evidence for: "
                    + ", ".join(missing_identities)
                )
            if unresolved_counterevidence:
                errors.append(
                    f"{prefix} cannot pass with unresolved counterevidence"
                )
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
        "stage_id": stage_id,
        "gate_tiers": gate_tiers,
        "system_scope": system_scope,
        "proof_path": proof_path,
        "minimum_evidence_level": minimum,
        "capability_ids": capability_ids,
        "identity_ids": identity_ids,
        "acceptance_step_ids": step_ids,
        "unresolved_counterevidence": unresolved_counterevidence,
    }


def validate_proof_path(
    item: object, prefix: str, errors: list[str]
) -> dict[str, str] | None:
    if not isinstance(item, dict):
        errors.append(f"{prefix} must be an object for schema version 5")
        return None
    normalized: dict[str, str] = {}
    for field in ("origin", "boundary", "observation"):
        value = item.get(field)
        if not nonempty(value):
            errors.append(f"{prefix}.{field} must be non-empty")
        else:
            normalized[field] = value
    fidelity = item.get("fidelity")
    if fidelity not in PROOF_FIDELITIES:
        errors.append(
            f"{prefix}.fidelity must be synthetic, production-shaped, or production"
        )
    else:
        normalized["fidelity"] = fidelity
    return normalized if len(normalized) == 4 else None


def validate_id_references(
    values: object,
    prefix: str,
    known_ids: set[str],
    errors: list[str],
    *,
    require_nonempty: bool,
) -> list[str]:
    if not isinstance(values, list) or (require_nonempty and not values):
        qualifier = "a non-empty array" if require_nonempty else "an array"
        errors.append(f"{prefix} must be {qualifier}")
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not valid_requirement_id(value):
            errors.append(f"{prefix} contains an invalid ID")
            continue
        if value in seen:
            errors.append(f"{prefix} contains duplicate ID: {value}")
            continue
        seen.add(value)
        if value not in known_ids:
            errors.append(f"{prefix} references unknown ID: {value}")
        normalized.append(value)
    return normalized


def validate_acceptance_steps(
    steps: object, prefix: str, errors: list[str]
) -> list[str]:
    if not isinstance(steps, list) or not steps:
        errors.append(f"{prefix}.acceptance_steps must be a non-empty array")
        return []
    step_ids: list[str] = []
    seen: set[str] = set()
    for index, step in enumerate(steps):
        field = f"{prefix}.acceptance_steps[{index}]"
        if not isinstance(step, dict):
            errors.append(f"{field} must be an object for schema version 2 or 3")
            continue
        step_id = step.get("id")
        if not valid_requirement_id(step_id):
            errors.append(f"{field}.id must match {REQUIREMENT_ID_PATTERN.pattern}")
            continue
        if step_id in seen:
            errors.append(f"duplicate acceptance step id in {prefix}: {step_id}")
        seen.add(step_id)
        if not nonempty(step.get("description")):
            errors.append(f"{field}.description must be non-empty")
        step_ids.append(step_id)
    return step_ids


def validate_evidence(
    entry: object,
    prefix: str,
    errors: list[str],
    *,
    schema_version: int,
    known_step_ids: set[str],
    known_identity_ids: set[str],
) -> dict[str, Any] | None:
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

    if schema_version >= 2:
        step_ids = validate_id_references(
            entry.get("step_ids"),
            f"{prefix}.step_ids",
            known_step_ids,
            errors,
            require_nonempty=True,
        )
        identity_ids = validate_id_references(
            entry.get("identity_ids"),
            f"{prefix}.identity_ids",
            known_identity_ids,
            errors,
            require_nonempty=False,
        )
    else:
        step_ids = []
        identity_ids = []
    return {
        "rank": EVIDENCE_RANKS[level],
        "step_ids": step_ids,
        "identity_ids": identity_ids,
    }


def validate_counterevidence(
    entries: object, prefix: str, errors: list[str]
) -> int:
    if not isinstance(entries, list):
        errors.append(f"{prefix} must be an array")
        return 0
    unresolved = 0
    for index, entry in enumerate(entries):
        field = f"{prefix}[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{field} must be an object")
            continue
        if not nonempty(entry.get("ref")):
            errors.append(f"{field}.ref must be non-empty")
        if not nonempty(entry.get("summary")):
            errors.append(f"{field}.summary must be non-empty")
        validate_utc(entry.get("observed_utc"), f"{field}.observed_utc", errors)
        status = entry.get("status")
        if status not in COUNTEREVIDENCE_STATES:
            errors.append(f"{field}.status must be unresolved or resolved")
        elif status == "unresolved":
            unresolved += 1
            if entry.get("resolution") is not None:
                errors.append(f"{field}.resolution must be null while unresolved")
        elif not nonempty(entry.get("resolution")):
            errors.append(f"{field}.resolution must be non-empty when resolved")
    return unresolved

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


def has_nonempty_prefixed_line(lines: list[str], prefix: str) -> bool:
    return any(line.startswith(prefix) and bool(line[len(prefix) :].strip()) for line in lines)


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
