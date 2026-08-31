#!/usr/bin/env python3
"""Initialize and validate durable project intent and acceptance state."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
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
CURRENT_SCHEMA_VERSION = 6
SUPPORTED_SCHEMA_VERSIONS = {1, 2, 3, 4, 5, 6}
PRESERVATION_VALUES = {"stage", "permanent"}
GATE_TIERS = {"change", "pre-release", "release"}
GATE_TIER_ORDER = {"change": 0, "pre-release": 1, "release": 2}
SYSTEM_SCOPES = {"component", "interaction", "end-to-end"}
PROOF_FIDELITIES = {"synthetic", "production-shaped", "production"}
CONTROL_STATES = {"ready", "running", "stopped", "closed"}
ACTION_CLASSES = {
    "local",
    "proof",
    "external-write",
    "irreversible",
    "unattended",
    "support",
}
COST_CLASSES = {"cheap", "expensive"}
SCOPE_GROWTH_VALUES = {
    "none",
    "implementation",
    "architecture",
    "operations",
    "custody",
}
TOOL_OBSERVATION_OUTCOMES = {"completed", "failed", "aborted"}
READ_ONLY_TOOL_NAMES = {
    "view_image",
    "read_mcp_resource",
    "list_mcp_resources",
    "list_mcp_resource_templates",
    "control-status",
}
SUBAGENT_TOOL_NAMES = {
    "Agent",
    "agent",
    "spawn_agent",
    "collaboration.spawn_agent",
}
APPLY_PATCH_TOOL_NAMES = {"apply_patch", "functions.apply_patch"}
SHELL_TOOL_NAMES = {"Bash", "bash", "exec_command", "functions.exec_command"}
KNOWN_MATERIAL_TOOL_NAMES = {
    "Bash",
    "Agent",
    "apply_patch",
    "functions.apply_patch",
    "exec_command",
    "functions.exec_command",
    "write_stdin",
    "spawn_agent",
    "collaboration.spawn_agent",
}
EXTERNAL_WRITE_VERBS = {
    "archive",
    "cancel",
    "close",
    "commit",
    "create",
    "delete",
    "deploy",
    "disable",
    "edit",
    "enable",
    "forward",
    "grant",
    "install",
    "invite",
    "merge",
    "move",
    "post",
    "publish",
    "push",
    "remove",
    "reply",
    "revoke",
    "send",
    "share",
    "start",
    "stop",
    "trigger",
    "unarchive",
    "update",
    "upload",
    "write",
}
IRREVERSIBLE_TOOL_VERBS = {"delete", "purge", "remove", "revoke", "terminate"}
SHELL_EXTERNAL_WRITE_PATTERNS = (
    re.compile(r"(?i)(?:^|[;&|]\s*)git\s+push\b"),
    re.compile(r"(?i)(?:^|[;&|]\s*)(?:gh|glab)\s+\S+\s+(?:create|edit|close|merge|delete|upload)\b"),
    re.compile(r"(?i)\b(?:npm|pnpm|yarn)\s+publish\b"),
    re.compile(r"(?i)\bcurl\b[^\r\n]*(?:--request|-X)\s*(?:POST|PUT|PATCH|DELETE)\b"),
    re.compile(r"(?i)\bInvoke-(?:RestMethod|WebRequest)\b[^\r\n]*-Method\s+(?:POST|PUT|PATCH|DELETE)\b"),
)
CONTROL_STATE_PATHS = {
    ".codex/ACCEPTANCE.json",
    ".codex/PROJECT_OUTCOME.md",
}
EXECUTION_LIMIT_FIELDS = (
    "total_attempts",
    "failed_attempts",
    "equivalent_failures",
    "expensive_attempts",
    "support_attempts",
    "no_progress_attempts",
    "total_tool_calls",
    "support_tool_calls",
    "support_no_progress_calls",
    "active_attempt_seconds",
    "spawned_workers",
    "scope_growth_actions",
    "direct_delivery_reserved_calls",
    "max_path_touches",
    "max_touches_per_path",
)
# A recovery may add capacity, but it cannot relax the repeated-failure or
# support-loop floors that stop unsafe method families.
NON_EXTENDABLE_LIMIT_FIELDS = {
    "equivalent_failures",
    "support_no_progress_calls",
}
LEGACY_LIMIT_EXTENSION_KIND = "outcome-integrity-limit-extension-v1"
LEGACY_LIMIT_EXTENSION_RECEIPT_KIND = "outcome-integrity-limit-extension-receipt-v1"
LIMIT_EXTENSION_KIND = "outcome-integrity-limit-extension-v2"
LIMIT_EXTENSION_RECEIPT_KIND = "outcome-integrity-limit-extension-receipt-v2"
LIMIT_EXTENSION_REQUEST_KINDS = {
    LEGACY_LIMIT_EXTENSION_KIND,
    LIMIT_EXTENSION_KIND,
}
LIMIT_EXTENSION_REQUEST_FIELDS = {
    "kind",
    "id",
    "reason",
    "authorization_ref",
    "receipt_ref",
    "expected_lineage_id",
    "expected_candidate_fingerprint",
    "expected_scope_fingerprint",
    "limits",
}
LEGACY_LIMIT_EXTENSION_RECORD_FIELDS = {
    "kind",
    "id",
    "applied_utc",
    "prior_revision",
    "result_revision",
    "reason",
    "authorization_ref",
    "authorization_fingerprint",
    "receipt_ref",
    "lineage_id",
    "candidate_fingerprint",
    "scope_fingerprint",
    "usage_fingerprint",
    "usage_snapshot",
    "prior_limits",
    "new_limits",
    "extension_fingerprint",
}
LIMIT_EXTENSION_RECORD_FIELDS = (
    LEGACY_LIMIT_EXTENSION_RECORD_FIELDS - {"usage_snapshot"}
) | {"usage_anchor"}
# A one-time, evidence-bound repair for schema-v6's original failure identity.
# It splits a legacy v1 aggregate only when a provenance bundle contains the
# complete, distinct historical attempt records. It preserves every usage
# counter, limit, candidate, scope, and stopped method family.
LEGACY_FAILURE_IDENTITY_MIGRATION_KIND = (
    "outcome-integrity-failure-fingerprint-migration-v1"
)
LEGACY_FAILURE_IDENTITY_MIGRATION_RECEIPT_KIND = (
    "outcome-integrity-failure-fingerprint-migration-receipt-v1"
)
FAILURE_IDENTITY_MIGRATION_KIND = "outcome-integrity-failure-fingerprint-migration-v2"
FAILURE_IDENTITY_MIGRATION_RECEIPT_KIND = (
    "outcome-integrity-failure-fingerprint-migration-receipt-v2"
)
FAILURE_IDENTITY_MIGRATION_REQUEST_KINDS = {
    LEGACY_FAILURE_IDENTITY_MIGRATION_KIND,
    FAILURE_IDENTITY_MIGRATION_KIND,
}
FAILURE_IDENTITY_PROVENANCE_KIND = (
    "outcome-integrity-recovered-failure-provenance-v1"
)
FAILURE_IDENTITY_MIGRATION_REQUEST_FIELDS = {
    "kind",
    "id",
    "reason",
    "authorization_ref",
    "provenance_ref",
    "receipt_ref",
    "expected_lineage_id",
    "expected_candidate_fingerprint",
    "expected_scope_fingerprint",
    "legacy_fingerprint",
}
LEGACY_FAILURE_IDENTITY_MIGRATION_RECORD_FIELDS = {
    "kind",
    "id",
    "migrated_utc",
    "prior_revision",
    "result_revision",
    "reason",
    "authorization_ref",
    "authorization_fingerprint",
    "provenance_ref",
    "provenance_fingerprint",
    "receipt_ref",
    "lineage_id",
    "candidate_fingerprint",
    "scope_fingerprint",
    "usage_fingerprint",
    "usage_snapshot",
    "source_legacy_failure_class",
    "migrated_failure_classes",
    "migration_fingerprint",
}
FAILURE_IDENTITY_MIGRATION_RECORD_FIELDS = (
    LEGACY_FAILURE_IDENTITY_MIGRATION_RECORD_FIELDS - {"usage_snapshot"}
) | {
    "usage_anchor",
    "result_usage_fingerprint",
    "result_usage_anchor",
}
LEGACY_STATE_TRANSITION_KIND = "outcome-integrity-control-state-transition-v1"
STATE_TRANSITION_KIND = "outcome-integrity-control-state-transition-v2"
STATE_TRANSITION_REQUEST_KINDS = {
    LEGACY_STATE_TRANSITION_KIND,
    STATE_TRANSITION_KIND,
}
STATE_TRANSITION_REQUEST_FIELDS = {"kind", "id", "reason", "authorization_ref", "recovery_evidence_ref", "target_project_state", "expected_lineage_id", "expected_candidate_fingerprint", "expected_scope_fingerprint"}
STRUCTURED_TARGET_KEYS = {
    "dest",
    "destination",
    "file",
    "file_path",
    "filename",
    "output",
    "output_file",
    "output_path",
    "path",
    "target",
    "target_path",
}
SHELL_CONTROL_MUTATION_PATTERN = re.compile(
    r"(?im)(?:^|[;&|]\s*)"
    r"(?:sudo\s+)?"
    r"(?:set-content|add-content|clear-content|remove-item|move-item|copy-item|"
    r"rename-item|out-file|tee|rm|mv|cp|del|erase|move|copy|truncate|touch|"
    r"sed\s+-i)\b"
    r"[^\r\n;&|]*?"
    r"\.codex[\\/](?:ACCEPTANCE\.json|PROJECT_OUTCOME\.md)"
)
SHELL_CONTROL_REDIRECT_PATTERN = re.compile(
    r"(?im)(?:>|>>)\s*[\"']?"
    r"\.codex[\\/](?:ACCEPTANCE\.json|PROJECT_OUTCOME\.md)"
)
SHELL_CONTROL_BARE_TARGET_PATTERN = re.compile(
    r"(?im)(?:(?:^|[;&|]\s*)"
    r"(?:sudo\s+)?(?:set-content|add-content|clear-content|remove-item|move-item|"
    r"copy-item|rename-item|out-file|tee|rm|mv|cp|del|erase|move|copy|truncate|"
    r"touch|sed\s+-i)\b[^\r\n;&|]*?|(?:>|>>)\s*[\"']?)"
    r"(?:ACCEPTANCE\.json|PROJECT_OUTCOME\.md)"
)
METHOD_FAMILY_FAILURE_LIMIT = 2
METHOD_FAMILY_NO_PROGRESS_LIMIT = 2
MAX_METHOD_FAMILIES_PER_PARENT = 2
USAGE_ANCHOR_SCALAR_FIELDS = (
    "total_attempts",
    "failed_attempts",
    "expensive_attempts",
    "support_attempts",
    "no_progress_attempts",
    "total_tool_calls",
    "support_tool_calls",
    "support_no_progress_calls",
    "active_attempt_seconds",
    "spawned_workers",
    "scope_growth_actions",
    "path_touches",
    "hot_path_touches",
)
EVALUATION_ROLES = {"none", "diagnostic", "prospective"}
FAILURE_CLASSES = {
    "transient",
    "reasoning-recoverable",
    "user-fixable",
    "semantic",
    "ambiguous-external-write",
}
ATTEMPT_REQUEST_STABLE_FIELDS = (
    "requirement_id",
    "tier",
    "method_family_id",
    "prior_method_family_id",
    "method_change_evidence_ref",
    "lower_complexity_comparison_ref",
    "acceptance_outcome_id",
    "boundary_id",
    "cost_class",
    "action_classes",
    "scope_growth",
    "allowed_paths",
    "tool_binding",
    "candidate_fingerprint",
    "prerequisite_ids",
    "no_prerequisites_reason",
    "authorization_id",
    "target_identity_ids",
    "action",
    "effect",
    "principal",
    "context_fingerprint",
    "evaluation_fingerprint",
    "evaluation_role",
    "causal_evidence_ref",
)
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
FINGERPRINT_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
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
EXECUTION_CONTROL_AUTHORITY_LINE = (
    "- Mutable execution-control ledger: "
    ".codex/ACCEPTANCE.json#execution_control (sole authority)"
)
LEGACY_MUTABLE_CONTROL_PREFIXES = (
    "- Execution-control revision:",
    "- Candidate fingerprint:",
    "- Stable attempt lineage:",
    "- Next material-action admission:",
    "- Evaluation exposure:",
    "- Progress metrics:",
)


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

        if schema_version >= 6 and acceptance["updated"] != project["updated"]:
            message = (
                "schema version 6 requires identical PROJECT_OUTCOME.md and "
                "ACCEPTANCE.json reconciliation timestamps"
            )
            if mode in {"resume", "completion", "admit"}:
                errors.append(message)
            else:
                warnings.append(message)
        elif acceptance["updated"] < project["updated"]:
            message = "ACCEPTANCE.json is older than PROJECT_OUTCOME.md; reconcile acceptance state"
            if mode in {"resume", "completion", "admit"}:
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

        if schema_version >= 6 and project["execution_control_authority_count"] != 1:
            errors.append(
                "schema version 6 requires exactly one PROJECT_OUTCOME.md line: "
                + EXECUTION_CONTROL_AUTHORITY_LINE
            )
        if schema_version >= 6 and project["legacy_mutable_control_line_count"]:
            errors.append(
                "schema version 6 forbids duplicated mutable execution-control lines in "
                "PROJECT_OUTCOME.md"
            )

        if mode in {"resume", "admit"}:
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
            if schema_version != CURRENT_SCHEMA_VERSION:
                errors.append(
                    f"completion requires ACCEPTANCE.json schema_version {CURRENT_SCHEMA_VERSION}; migrate legacy state first"
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
            if schema_version >= 6 and acceptance.get("execution_control"):
                if acceptance["execution_control"]["status"] != "closed":
                    errors.append("completion requires execution_control.status closed")

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
        "execution_control_authority_count": lines.count(
            EXECUTION_CONTROL_AUTHORITY_LINE
        ),
        "legacy_mutable_control_line_count": sum(
            1
            for line in lines
            if any(line.startswith(prefix) for prefix in LEGACY_MUTABLE_CONTROL_PREFIXES)
        ),
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
        errors.append("ACCEPTANCE.json schema_version must be 1, 2, 3, 4, 5, or 6")
        return None
    if schema_version < CURRENT_SCHEMA_VERSION:
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

    raw_control = data.get("execution_control") if schema_version >= 6 else None
    raw_lineage = raw_control.get("lineage") if isinstance(raw_control, dict) else None
    control_acceptance_ids = set(
        raw_lineage.get("acceptance_ids", [])
        if isinstance(raw_lineage, dict) and isinstance(raw_lineage.get("acceptance_ids"), list)
        else []
    )
    raw_candidate = raw_control.get("candidate") if isinstance(raw_control, dict) else None
    control_candidate_fingerprint = (
        raw_candidate.get("fingerprint") if isinstance(raw_candidate, dict) else None
    )
    control_lineage_id = raw_lineage.get("id") if isinstance(raw_lineage, dict) else None

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
            stage_allowed_capability_ids={
                stage["id"]: set(stage.get("preserves_capability_ids", []))
                | {
                    capability["id"]
                    for capability in outcome_capabilities
                    if capability.get("stage_id") == stage["id"]
                }
                for stage in (outcome_hierarchy["delivery_stages"] if outcome_hierarchy else [])
            },
            control_acceptance_ids=control_acceptance_ids,
            control_candidate_fingerprint=control_candidate_fingerprint,
            control_lineage_id=control_lineage_id,
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
    if schema_version >= 6:
        validate_predecessor_requirements(
            normalized,
            capability_floors,
            control_acceptance_ids,
            errors,
        )
        execution_control = validate_execution_control(
            raw_control,
            data,
            root,
            normalized,
            outcome_hierarchy,
            outcome_capabilities,
            capability_floors,
            identity_ids,
            updated,
            project_state,
            errors,
        )
    else:
        execution_control = None

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
        "execution_control": execution_control,
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
    stage_order = {
        stage["id"]: index for index, stage in enumerate(hierarchy["delivery_stages"])
    }
    capability_stage_order = {
        item["id"]: stage_order.get(item["stage_id"], len(stage_order))
        for item in capabilities
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
        applicable_permanent_ids = {
            capability_id
            for capability_id in permanent_ids
            if capability_stage_order.get(capability_id, len(stage_order))
            <= stage_order.get(stage["id"], -1)
        }
        future = sorted(
            capability_id
            for capability_id in declared
            if capability_stage_order.get(capability_id, -1)
            > stage_order.get(stage["id"], -1)
        )
        if future:
            errors.append(
                f"delivery stage {stage['id']} cannot preserve future capabilities: "
                + ", ".join(future)
            )
        missing = sorted(applicable_permanent_ids - declared)
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
        applicable_permanent_ids = {
            capability_id
            for capability_id in permanent_ids
            if capability_stage_order.get(capability_id, len(stage_order))
            <= stage_order.get(stage["id"], -1)
        }
        whole_system = [
            item for item in stage_requirements
            if item["required"] and item["system_scope"] == "end-to-end"
            and "release" in item["gate_tiers"]
            and applicable_permanent_ids.issubset(set(item["capability_ids"]))
            and (schema_version < 5 or (item.get("proof_path") or {}).get("fidelity") == "production")
        ]
        if not whole_system:
            errors.append(
                f"delivery stage {stage['id']} requires one end-to-end release gate covering every permanent capability"
            )


def validate_predecessor_requirements(
    requirements: list[dict[str, Any]],
    floors: list[dict[str, Any]],
    active_ids: set[str],
    errors: list[str],
) -> None:
    requirement_by_id = {item["id"]: item for item in requirements}
    for requirement_id in sorted(active_ids):
        requirement = requirement_by_id.get(requirement_id)
        if not requirement:
            continue
        predecessors = set(requirement.get("predecessor_requirement_ids", []))
        if requirement_id in predecessors:
            errors.append(f"requirement {requirement_id} cannot depend on itself")
        for predecessor_id in sorted(predecessors):
            predecessor = requirement_by_id.get(predecessor_id)
            if not predecessor:
                errors.append(
                    f"requirement {requirement_id} references unknown predecessor: {predecessor_id}"
                )
                continue
            if predecessor_id not in active_ids:
                errors.append(
                    f"requirement {requirement_id} predecessor {predecessor_id} must belong to the active attempt lineage"
                )
            if predecessor["stage_id"] != requirement["stage_id"]:
                errors.append(
                    f"requirement {requirement_id} predecessor {predecessor_id} must belong to the same delivery stage"
                )
            predecessor_rank = max(
                (GATE_TIER_ORDER[tier] for tier in predecessor["gate_tiers"]),
                default=-1,
            )
            requirement_rank = min(
                (GATE_TIER_ORDER[tier] for tier in requirement["gate_tiers"]),
                default=99,
            )
            if predecessor_rank >= requirement_rank:
                errors.append(
                    f"requirement {requirement_id} predecessor {predecessor_id} must be a lower proof tier"
                )

        expected: set[str] = set()
        requirement_capabilities = set(requirement["capability_ids"])
        for floor in floors:
            if floor["capability_id"] not in requirement_capabilities:
                continue
            for tier in requirement["gate_tiers"]:
                for lower_tier, rank in GATE_TIER_ORDER.items():
                    if rank < GATE_TIER_ORDER[tier]:
                        expected.update(floor["proof_ladder"].get(lower_tier, []))
        missing = sorted(expected - predecessors)
        if missing:
            errors.append(
                f"requirement {requirement_id} is missing lower-tier predecessors: "
                + ", ".join(missing)
            )


def validate_execution_control(
    item: object,
    data: dict[str, Any],
    root: Path,
    requirements: list[dict[str, Any]],
    hierarchy: dict[str, Any] | None,
    capabilities: list[dict[str, Any]],
    floors: list[dict[str, Any]],
    identity_ids: set[str],
    updated: datetime | None,
    project_state: object,
    errors: list[str],
) -> dict[str, Any] | None:
    prefix = "execution_control"
    if not isinstance(item, dict):
        errors.append(f"{prefix} must be an object for schema version 6")
        return None

    revision = item.get("revision")
    if not nonnegative_int(revision):
        errors.append(f"{prefix}.revision must be a non-negative integer")
    reconciled = validate_utc(item.get("reconciled_utc"), f"{prefix}.reconciled_utc", errors)
    if reconciled is not None and updated is not None and reconciled != updated:
        errors.append(f"{prefix}.reconciled_utc must equal updated_utc")

    requirement_by_id = {entry["id"]: entry for entry in requirements}
    known_stage_ids = {
        stage["id"] for stage in hierarchy["delivery_stages"]
    } if hierarchy else set()
    lineage = item.get("lineage")
    if not isinstance(lineage, dict):
        errors.append(f"{prefix}.lineage must be an object")
        lineage = {}
    lineage_id = lineage.get("id")
    if not valid_requirement_id(lineage_id):
        errors.append(f"{prefix}.lineage.id must be a stable ID")
    stage_id = lineage.get("stage_id")
    if stage_id not in known_stage_ids:
        errors.append(f"{prefix}.lineage.stage_id must identify a declared delivery stage")
    acceptance_ids = validate_declared_ids(
        lineage.get("acceptance_ids"),
        f"{prefix}.lineage.acceptance_ids",
        errors,
        required=True,
    )
    expected_ids = sorted(
        entry["id"]
        for entry in requirements
        if entry["required"] and entry["stage_id"] == stage_id
    )
    if sorted(acceptance_ids) != expected_ids:
        errors.append(
            f"{prefix}.lineage.acceptance_ids must equal every required slice in its delivery stage"
        )
    if hierarchy and project_state == "active" and hierarchy["current_stage_id"] != stage_id:
        errors.append(f"{prefix}.lineage.stage_id must equal the active delivery stage")
    scope_fingerprint = lineage.get("scope_fingerprint")
    if not valid_fingerprint(scope_fingerprint):
        errors.append(f"{prefix}.lineage.scope_fingerprint must be a SHA-256 fingerprint")
    else:
        calculated_scope = calculate_scope_fingerprint(data)
        if scope_fingerprint != calculated_scope:
            errors.append(
                f"{prefix}.lineage.scope_fingerprint is stale for the declared acceptance semantics"
            )

    candidate = item.get("candidate")
    candidate_fingerprint = validate_candidate_control(
        candidate, root, f"{prefix}.candidate", errors
    )

    limits = item.get("limits")
    limit_fields = EXECUTION_LIMIT_FIELDS
    normalized_limits: dict[str, int] = {}
    if not isinstance(limits, dict):
        errors.append(f"{prefix}.limits must be an object")
        limits = {}
    for field in limit_fields:
        value = limits.get(field)
        if not positive_int(value):
            errors.append(f"{prefix}.limits.{field} must be a positive integer")
        else:
            normalized_limits[field] = value

    usage = item.get("usage")
    usage_fields = (
        "total_attempts",
        "failed_attempts",
        "expensive_attempts",
        "support_attempts",
        "no_progress_attempts",
        "total_tool_calls",
        "support_tool_calls",
        "support_no_progress_calls",
        "active_attempt_seconds",
        "spawned_workers",
        "scope_growth_actions",
        "path_touches",
        "hot_path_touches",
    )
    normalized_usage: dict[str, int] = {}
    if not isinstance(usage, dict):
        errors.append(f"{prefix}.usage must be an object")
        usage = {}
    for field in usage_fields:
        value = usage.get(field)
        if not nonnegative_int(value):
            errors.append(f"{prefix}.usage.{field} must be a non-negative integer")
        else:
            normalized_usage[field] = value

    failure_classes = validate_failure_classes(
        usage.get("failure_classes"),
        f"{prefix}.usage.failure_classes",
        lineage_id,
        errors,
    )
    validate_failure_identity_migrations(
        item.get("failure_identity_migrations"),
        root,
        f"{prefix}.failure_identity_migrations",
        revision,
        usage,
        failure_classes,
        lineage_id,
        candidate_fingerprint,
        scope_fingerprint,
        errors,
    )
    if sum(entry["count"] for entry in failure_classes) != normalized_usage.get("failed_attempts", -1):
        errors.append(
            f"{prefix}.usage.failed_attempts must equal the aggregate failure-class count"
        )

    if (
        normalized_limits.get("direct_delivery_reserved_calls", 0)
        >= normalized_limits.get("total_tool_calls", 0)
    ):
        errors.append(
            f"{prefix}.limits.direct_delivery_reserved_calls must be less than total_tool_calls"
        )
    for usage_field, limit_field in (
        ("total_tool_calls", "total_tool_calls"),
        ("support_tool_calls", "support_tool_calls"),
        ("active_attempt_seconds", "active_attempt_seconds"),
        ("spawned_workers", "spawned_workers"),
        ("scope_growth_actions", "scope_growth_actions"),
        ("path_touches", "max_path_touches"),
    ):
        if normalized_usage.get(usage_field, 0) > normalized_limits.get(limit_field, 0):
            errors.append(
                f"{prefix}.usage.{usage_field} cannot exceed limits.{limit_field}"
            )

    path_counts = item.get("usage", {}).get("path_counts") if isinstance(item.get("usage"), dict) else None
    normalized_path_counts: dict[str, int] = {}
    if not isinstance(path_counts, dict):
        errors.append(f"{prefix}.usage.path_counts must be an object")
    else:
        for path, count in path_counts.items():
            normalized_path = normalize_declared_relative_path(path)
            if normalized_path is None or normalized_path != path:
                errors.append(f"{prefix}.usage.path_counts contains an invalid relative path")
            elif not positive_int(count):
                errors.append(f"{prefix}.usage.path_counts[{path!r}] must be a positive integer")
            else:
                normalized_path_counts[path] = count
    if sum(normalized_path_counts.values()) != normalized_usage.get("path_touches", -1):
        errors.append(f"{prefix}.usage.path_touches must equal the aggregate path count")
    over_touched_paths = sorted(
        path
        for path, count in normalized_path_counts.items()
        if count > normalized_limits.get("max_touches_per_path", 0)
    )
    if over_touched_paths:
        errors.append(
            f"{prefix}.usage.path_counts exceeds limits.max_touches_per_path: "
            + ", ".join(over_touched_paths)
        )

    method_families = validate_method_families(
        item.get("usage", {}).get("method_families")
        if isinstance(item.get("usage"), dict)
        else None,
        f"{prefix}.usage.method_families",
        errors,
    )

    diagnostics = item.get("diagnostic_evaluation_fingerprints")
    diagnostic_fingerprints: list[str] = []
    if not isinstance(diagnostics, list):
        errors.append(f"{prefix}.diagnostic_evaluation_fingerprints must be an array")
    else:
        for fingerprint in diagnostics:
            if not valid_fingerprint(fingerprint):
                errors.append(
                    f"{prefix}.diagnostic_evaluation_fingerprints contains an invalid fingerprint"
                )
            elif fingerprint in diagnostic_fingerprints:
                errors.append(
                    f"{prefix}.diagnostic_evaluation_fingerprints contains a duplicate"
                )
            else:
                diagnostic_fingerprints.append(fingerprint)

    receipts = validate_gate_receipts(
        item.get("gate_receipts"),
        f"{prefix}.gate_receipts",
        requirement_by_id,
        lineage_id,
        candidate_fingerprint,
        set(diagnostic_fingerprints),
        errors,
    )
    prerequisites = validate_prerequisites(
        item.get("prerequisites"),
        f"{prefix}.prerequisites",
        set(requirement_by_id),
        errors,
    )
    authorizations = validate_authorizations(
        item.get("authorizations"),
        f"{prefix}.authorizations",
        identity_ids,
        errors,
    )

    status = item.get("status")
    if status not in CONTROL_STATES:
        errors.append(f"{prefix}.status must be ready, running, stopped, or closed")
    active_attempt = item.get("active_attempt")
    if status == "running":
        validate_active_attempt(
            active_attempt,
            f"{prefix}.active_attempt",
            requirement_by_id,
            lineage_id,
            scope_fingerprint,
            candidate_fingerprint,
            item.get("reconciled_utc"),
            prerequisites,
            authorizations,
            method_families,
            identity_ids,
            set(diagnostic_fingerprints),
            errors,
        )
    elif active_attempt is not None:
        errors.append(f"{prefix}.active_attempt must be null unless status is running")

    stop_reason = item.get("stop_reason")
    if status == "stopped":
        if not nonempty(stop_reason):
            errors.append(f"{prefix}.stop_reason must be non-empty when stopped")
    elif stop_reason is not None:
        errors.append(f"{prefix}.stop_reason must be null unless stopped")
    if project_state == "complete" and status != "closed":
        errors.append(f"{prefix}.status must be closed when project_state is complete")
    if project_state == "active" and status == "closed":
        errors.append(f"{prefix}.status cannot be closed while project_state is active")

    support_stop_reason = item.get("support_stop_reason")
    support_fired = (
        normalized_usage.get("support_tool_calls", 0)
        >= normalized_limits.get("support_tool_calls", 1)
        or normalized_usage.get("support_no_progress_calls", 0)
        >= normalized_limits.get("support_no_progress_calls", 1)
    )
    if support_fired and not nonempty(support_stop_reason):
        errors.append(f"{prefix}.support_stop_reason must explain the fired support-only stop")
    if not support_fired and support_stop_reason is not None:
        errors.append(f"{prefix}.support_stop_reason must be null before a support-only limit fires")

    failed_limit = normalized_limits.get("failed_attempts")
    equivalent_limit = normalized_limits.get("equivalent_failures")
    no_progress_limit = normalized_limits.get("no_progress_attempts")
    fired = (
        (failed_limit is not None and normalized_usage.get("failed_attempts", 0) >= failed_limit)
        or (
            equivalent_limit is not None
            and any(entry["count"] >= equivalent_limit for entry in failure_classes)
        )
        or (
            no_progress_limit is not None
            and normalized_usage.get("no_progress_attempts", 0) >= no_progress_limit
        )
    )
    if fired and status not in {"stopped", "closed"}:
        errors.append(f"{prefix}.status must be stopped after a failure or no-progress limit fires")

    validate_limit_extensions(
        item.get("limit_extensions"),
        root,
        f"{prefix}.limit_extensions",
        normalized_limits,
        normalized_usage,
        revision,
        errors,
    )

    receipt_by_id = {receipt["id"]: receipt for receipt in receipts}
    for requirement_id in acceptance_ids:
        requirement = requirement_by_id.get(requirement_id)
        if not requirement or requirement["status"] != "passing":
            continue
        exact_receipts = 0
        for evidence in requirement.get("evidence", []):
            receipt = receipt_by_id.get(evidence.get("gate_receipt_id"))
            if receipt is None:
                continue
            mismatches: list[str] = []
            if receipt.get("requirement_id") != requirement_id:
                mismatches.append("requirement")
            if receipt.get("tier") not in requirement.get("gate_tiers", []):
                mismatches.append("tier")
            if receipt.get("candidate_fingerprint") != evidence.get("candidate_fingerprint"):
                mismatches.append("candidate")
            if receipt.get("lineage_id") != evidence.get("lineage_id"):
                mismatches.append("lineage")
            if receipt.get("evidence_ref") != evidence.get("ref"):
                mismatches.append("evidence_ref")
            if receipt.get("evaluation_fingerprint") != evidence.get("evaluation_fingerprint"):
                mismatches.append("evaluation_fingerprint")
            if receipt.get("evaluation_role") != evidence.get("evaluation_role"):
                mismatches.append("evaluation_role")
            if mismatches:
                errors.append(
                    f"requirement {requirement_id} evidence receipt binding mismatches: "
                    + ", ".join(mismatches)
                )
            else:
                exact_receipts += 1
        if exact_receipts == 0:
            errors.append(
                f"requirement {requirement_id} cannot pass without an exact atomic receipt binding"
            )

    return {
        "revision": revision,
        "status": status,
        "lineage_id": lineage_id,
        "stage_id": stage_id,
        "acceptance_ids": acceptance_ids,
        "candidate_fingerprint": candidate_fingerprint,
        "limits": normalized_limits,
        "usage": normalized_usage,
        "receipts": receipts,
    }


def file_sha256_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def resolve_limit_extension_evidence_path(
    root: Path,
    value: object,
    prefix: str,
    errors: list[str],
    *,
    must_exist: bool,
) -> tuple[str | None, Path | None]:
    normalized = normalize_declared_relative_path(value)
    if (
        normalized is None
        or normalized != value
        or not normalized.startswith(".codex/evidence/")
    ):
        errors.append(f"{prefix} must be a normalized .codex/evidence relative path")
        return None, None
    raw_path = root / Path(normalized)
    evidence_root = (root / ".codex" / "evidence").resolve(strict=False)
    try:
        resolved = raw_path.resolve(strict=False)
        resolved.relative_to(evidence_root)
    except (OSError, ValueError):
        errors.append(f"{prefix} must remain inside .codex/evidence")
        return None, None
    if raw_path.is_symlink():
        errors.append(f"{prefix} must not be a symlink")
        return None, None
    if must_exist:
        if not raw_path.is_file():
            errors.append(f"{prefix} must name an existing regular evidence file")
            return None, None
    elif raw_path.exists() or raw_path.is_symlink():
        errors.append(f"{prefix} must name a new evidence file")
        return None, None
    return normalized, raw_path


def validate_exact_limit_map(
    value: object, prefix: str, errors: list[str]
) -> dict[str, int]:
    if not isinstance(value, dict):
        errors.append(f"{prefix} must be an object")
        return {}
    unknown = sorted(set(value) - set(EXECUTION_LIMIT_FIELDS))
    missing = sorted(set(EXECUTION_LIMIT_FIELDS) - set(value))
    if unknown:
        errors.append(f"{prefix} contains unknown limit fields: {', '.join(unknown)}")
    if missing:
        errors.append(f"{prefix} is missing limit fields: {', '.join(missing)}")
    normalized: dict[str, int] = {}
    for field in EXECUTION_LIMIT_FIELDS:
        candidate = value.get(field)
        if not positive_int(candidate):
            errors.append(f"{prefix}.{field} must be a positive integer")
        else:
            normalized[field] = candidate
    if (
        normalized.get("direct_delivery_reserved_calls", 0)
        >= normalized.get("total_tool_calls", 0)
    ):
        errors.append(f"{prefix}.direct_delivery_reserved_calls must be less than total_tool_calls")
    if normalized.get("support_tool_calls", 0) > normalized.get("total_tool_calls", 0):
        errors.append(f"{prefix}.support_tool_calls cannot exceed total_tool_calls")
    for field in (
        "failed_attempts",
        "expensive_attempts",
        "support_attempts",
        "no_progress_attempts",
    ):
        if normalized.get(field, 0) > normalized.get("total_attempts", 0):
            errors.append(f"{prefix}.{field} cannot exceed total_attempts")
    return normalized


def validate_limit_extensions(
    items: object,
    root: Path,
    prefix: str,
    current_limits: dict[str, int],
    current_usage: dict[str, int],
    current_revision: object,
    errors: list[str],
) -> None:
    """Validate append-only audited capacity extensions without reopening work."""
    if items is None:
        return
    if not isinstance(items, list):
        errors.append(f"{prefix} must be an array when present")
        return
    seen_ids: set[str] = set()
    previous_result_revision = -1
    last_limits: dict[str, int] | None = None
    for index, item in enumerate(items):
        item_prefix = f"{prefix}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{item_prefix} must be an object")
            continue
        record_kind = item.get("kind")
        if record_kind == LEGACY_LIMIT_EXTENSION_KIND:
            record_fields = LEGACY_LIMIT_EXTENSION_RECORD_FIELDS
            receipt_kind = LEGACY_LIMIT_EXTENSION_RECEIPT_KIND
        elif record_kind == LIMIT_EXTENSION_KIND:
            record_fields = LIMIT_EXTENSION_RECORD_FIELDS
            receipt_kind = LIMIT_EXTENSION_RECEIPT_KIND
        else:
            record_fields = LIMIT_EXTENSION_RECORD_FIELDS
            receipt_kind = LIMIT_EXTENSION_RECEIPT_KIND
            errors.append(f"{item_prefix}.kind is invalid")
        unknown = sorted(set(item) - record_fields)
        missing = sorted(record_fields - set(item))
        if unknown:
            errors.append(f"{item_prefix} contains unknown fields: {', '.join(unknown)}")
        if missing:
            errors.append(f"{item_prefix} is missing fields: {', '.join(missing)}")
        item_id = item.get("id")
        if not valid_requirement_id(item_id):
            errors.append(f"{item_prefix}.id must be a stable ID")
        elif item_id in seen_ids:
            errors.append(f"duplicate limit extension id: {item_id}")
        else:
            seen_ids.add(item_id)
        validate_utc(item.get("applied_utc"), f"{item_prefix}.applied_utc", errors)
        prior_revision = item.get("prior_revision")
        result_revision = item.get("result_revision")
        if not nonnegative_int(prior_revision):
            errors.append(f"{item_prefix}.prior_revision must be a non-negative integer")
        if not nonnegative_int(result_revision):
            errors.append(f"{item_prefix}.result_revision must be a non-negative integer")
        elif nonnegative_int(prior_revision) and result_revision != prior_revision + 1:
            errors.append(f"{item_prefix}.result_revision must equal prior_revision plus one")
        if nonnegative_int(prior_revision) and prior_revision < previous_result_revision:
            errors.append(f"{item_prefix}.prior_revision must not precede earlier extension history")
        if nonnegative_int(result_revision):
            previous_result_revision = max(previous_result_revision, result_revision)
            if nonnegative_int(current_revision) and result_revision > current_revision:
                errors.append(f"{item_prefix}.result_revision cannot exceed the live control revision")
        if not nonempty(item.get("reason")):
            errors.append(f"{item_prefix}.reason must be non-empty")
        for field in ("lineage_id",):
            if not valid_requirement_id(item.get(field)):
                errors.append(f"{item_prefix}.{field} must be a stable ID")
        for field in (
            "candidate_fingerprint",
            "scope_fingerprint",
            "authorization_fingerprint",
            "usage_fingerprint",
            "extension_fingerprint",
        ):
            if not valid_fingerprint(item.get(field)):
                errors.append(f"{item_prefix}.{field} must be a SHA-256 fingerprint")
        _, authorization_path = resolve_limit_extension_evidence_path(
            root, item.get("authorization_ref"), f"{item_prefix}.authorization_ref", errors,
            must_exist=True,
        )
        if authorization_path is not None and valid_fingerprint(item.get("authorization_fingerprint")):
            if file_sha256_fingerprint(authorization_path) != item.get("authorization_fingerprint"):
                errors.append(f"{item_prefix}.authorization_fingerprint does not match the evidence file")
        _, receipt_path = resolve_limit_extension_evidence_path(
            root, item.get("receipt_ref"), f"{item_prefix}.receipt_ref", errors,
            must_exist=True,
        )
        prior_limits = validate_exact_limit_map(item.get("prior_limits"), f"{item_prefix}.prior_limits", errors)
        new_limits = validate_exact_limit_map(item.get("new_limits"), f"{item_prefix}.new_limits", errors)
        if prior_limits and new_limits:
            for field in EXECUTION_LIMIT_FIELDS:
                if new_limits[field] < prior_limits[field]:
                    errors.append(f"{item_prefix}.new_limits.{field} cannot decrease")
                if (
                    field in NON_EXTENDABLE_LIMIT_FIELDS
                    and new_limits[field] != prior_limits[field]
                ):
                    errors.append(f"{item_prefix}.new_limits.{field} is a permanent floor")
            if not any(new_limits[field] > prior_limits[field] for field in EXECUTION_LIMIT_FIELDS):
                errors.append(f"{item_prefix}.new_limits must extend at least one ceiling")
            last_limits = new_limits
        if record_kind == LEGACY_LIMIT_EXTENSION_KIND:
            if canonical_fingerprint(item.get("usage_snapshot")) != item.get(
                "usage_fingerprint"
            ):
                errors.append(
                    f"{item_prefix}.usage_snapshot does not match usage_fingerprint"
                )
        else:
            validate_usage_anchor(
                item.get("usage_anchor"), f"{item_prefix}.usage_anchor", errors
            )
        fingerprint_payload = {
            field: item.get(field)
            for field in sorted(record_fields - {"extension_fingerprint"})
        }
        if valid_fingerprint(item.get("extension_fingerprint")) and (
            canonical_fingerprint(fingerprint_payload) != item.get("extension_fingerprint")
        ):
            errors.append(f"{item_prefix}.extension_fingerprint is invalid")
        if receipt_path is not None:
            receipt, receipt_errors = load_json_object(receipt_path, f"{item_prefix}.receipt")
            if receipt_errors:
                errors.extend(receipt_errors)
            elif receipt is not None:
                if receipt.get("kind") != receipt_kind:
                    errors.append(f"{item_prefix}.receipt has the wrong kind")
                if receipt.get("extension") != item:
                    errors.append(f"{item_prefix}.receipt does not exactly mirror the extension")
    if last_limits is not None and last_limits != current_limits:
        errors.append(f"{prefix} final new_limits must equal live execution_control.limits")


def validate_candidate_control(
    item: object, root: Path, prefix: str, errors: list[str]
) -> str | None:
    if not isinstance(item, dict):
        errors.append(f"{prefix} must be an object")
        return None
    fingerprint = item.get("fingerprint")
    if not valid_fingerprint(fingerprint):
        errors.append(f"{prefix}.fingerprint must be a SHA-256 fingerprint")
    manifest_paths = item.get("manifest_paths")
    external_fingerprints = item.get("external_fingerprints")
    if not isinstance(manifest_paths, list):
        errors.append(f"{prefix}.manifest_paths must be an array")
    if not isinstance(external_fingerprints, list):
        errors.append(f"{prefix}.external_fingerprints must be an array")
    if isinstance(manifest_paths, list) and isinstance(external_fingerprints, list):
        if not manifest_paths and not external_fingerprints:
            errors.append(f"{prefix} must bind at least one manifest path or external fingerprint")
        calculated = calculate_candidate_fingerprint(root, item, errors, prefix=prefix)
        if valid_fingerprint(fingerprint) and calculated and fingerprint != calculated:
            errors.append(f"{prefix}.fingerprint does not match the current candidate manifest")
    return fingerprint if valid_fingerprint(fingerprint) else None


def calculate_candidate_fingerprint(
    root: Path, candidate: object, errors: list[str] | None = None, *, prefix: str = "candidate"
) -> str | None:
    local_errors = errors if errors is not None else []
    if not isinstance(candidate, dict):
        local_errors.append(f"{prefix} must be an object")
        return None
    manifest_paths = candidate.get("manifest_paths")
    external_fingerprints = candidate.get("external_fingerprints")
    if not isinstance(manifest_paths, list) or not isinstance(external_fingerprints, list):
        return None
    resolved_root = root.resolve()
    files: dict[str, str] = {}
    for index, value in enumerate(manifest_paths):
        field = f"{prefix}.manifest_paths[{index}]"
        if not nonempty(value):
            local_errors.append(f"{field} must be a non-empty relative path")
            continue
        relative = Path(value)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or any(part in {".git", ".codex"} for part in relative.parts)
        ):
            local_errors.append(f"{field} must stay inside the project and outside .git/.codex")
            continue
        target = (resolved_root / relative).resolve()
        try:
            target.relative_to(resolved_root)
        except ValueError:
            local_errors.append(f"{field} resolves outside the project root")
            continue
        if not target.exists():
            local_errors.append(f"{field} does not exist: {value}")
            continue
        candidates = [target] if target.is_file() else sorted(target.rglob("*"))
        for path in candidates:
            if not path.is_file():
                continue
            try:
                relative_file = path.resolve().relative_to(resolved_root)
            except ValueError:
                local_errors.append(
                    f"{field} contains a file that resolves outside the project root"
                )
                continue
            if (
                any(part in {".git", ".codex", "__pycache__"} for part in relative_file.parts)
                or path.suffix == ".pyc"
            ):
                continue
            key = relative_file.as_posix()
            files[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    normalized_external: list[str] = []
    for index, fingerprint in enumerate(external_fingerprints):
        if not valid_fingerprint(fingerprint):
            local_errors.append(
                f"{prefix}.external_fingerprints[{index}] must be a SHA-256 fingerprint"
            )
        else:
            normalized_external.append(fingerprint)
    if not files and not normalized_external:
        return None
    return canonical_fingerprint(
        {
            "files": [{"path": path, "sha256": files[path]} for path in sorted(files)],
            "external_fingerprints": sorted(set(normalized_external)),
        }
    )


def calculate_scope_fingerprint(data: dict[str, Any]) -> str:
    control = data.get("execution_control") if isinstance(data, dict) else None
    lineage = control.get("lineage") if isinstance(control, dict) else None
    stage_id = lineage.get("stage_id") if isinstance(lineage, dict) else None
    acceptance_ids = set(
        lineage.get("acceptance_ids", [])
        if isinstance(lineage, dict) and isinstance(lineage.get("acceptance_ids"), list)
        else []
    )
    hierarchy = data.get("outcome_hierarchy") if isinstance(data, dict) else None
    north_star = hierarchy.get("north_star", {}) if isinstance(hierarchy, dict) else {}
    stages = hierarchy.get("delivery_stages", []) if isinstance(hierarchy, dict) else []
    stage = next(
        (entry for entry in stages if isinstance(entry, dict) and entry.get("id") == stage_id),
        {},
    )
    capabilities = [
        entry
        for entry in data.get("outcome_capabilities", [])
        if isinstance(entry, dict)
        and (
            entry.get("stage_id") == stage_id
            or entry.get("id") in set(stage.get("preserves_capability_ids", []))
        )
    ]
    capability_ids = {entry.get("id") for entry in capabilities}
    floors = [
        entry
        for entry in data.get("capability_floors", [])
        if isinstance(entry, dict) and entry.get("capability_id") in capability_ids
    ]
    requirements = [
        entry
        for entry in data.get("requirements", [])
        if isinstance(entry, dict) and entry.get("id") in acceptance_ids
    ]
    referenced_identity_ids = {
        identity_id
        for requirement in requirements
        for identity_id in requirement.get("identity_ids", [])
    }
    identities = [
        entry
        for entry in data.get("identity_requirements", [])
        if isinstance(entry, dict) and entry.get("id") in referenced_identity_ids
    ]
    stable_requirement_fields = (
        "id",
        "description",
        "required",
        "stage_id",
        "capability_ids",
        "identity_ids",
        "gate_tiers",
        "predecessor_requirement_ids",
        "system_scope",
        "proof_path",
        "proof_scope",
        "proof_limits",
        "minimum_evidence_level",
        "acceptance_steps",
    )
    payload = {
        "project_identity": data.get("project_identity"),
        "north_star": {
            "id": north_star.get("id"),
            "description": north_star.get("description"),
            "fitness_dimensions": sorted(
                [
                    dimension
                    for dimension in north_star.get("fitness_dimensions", [])
                    if isinstance(dimension, dict)
                ],
                key=lambda dimension: str(dimension.get("id")),
            ),
        },
        "stage": {
            key: stage.get(key)
            for key in (
                "id",
                "parent_outcome_id",
                "description",
                "required",
                "preserves_capability_ids",
            )
        },
        "capabilities": sorted(capabilities, key=lambda entry: str(entry.get("id"))),
        "floors": sorted(floors, key=lambda entry: str(entry.get("id"))),
        "requirements": sorted(
            [
                {key: requirement.get(key) for key in stable_requirement_fields}
                for requirement in requirements
            ],
            key=lambda entry: str(entry.get("id")),
        ),
        "identities": sorted(identities, key=lambda entry: str(entry.get("id"))),
    }
    return canonical_fingerprint(payload)


def validate_failure_classes(
    items: object, prefix: str, lineage_id: object, errors: list[str]
) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        errors.append(f"{prefix} must be an array")
        return []
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[object, object]] = set()
    for index, item in enumerate(items):
        field = f"{prefix}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{field} must be an object")
            continue
        fingerprint = item.get("fingerprint")
        item_lineage_id = item.get("lineage_id")
        acceptance_outcome_id = item.get("acceptance_outcome_id")
        boundary_id = item.get("boundary_id")
        failure_identity_version = item.get("failure_identity_version", 1)
        if not valid_fingerprint(fingerprint):
            errors.append(f"{field}.fingerprint must be a SHA-256 fingerprint")
        if item_lineage_id != lineage_id:
            errors.append(f"{field}.lineage_id must match the active lineage")
        if not valid_requirement_id(acceptance_outcome_id):
            errors.append(f"{field}.acceptance_outcome_id must be a structured ID")
        if not valid_requirement_id(boundary_id):
            errors.append(f"{field}.boundary_id must be a structured ID")
        if failure_identity_version not in {1, 2, 3}:
            errors.append(f"{field}.failure_identity_version must be 1, 2, or 3")
        earliest_divergence = item.get("earliest_divergence")
        if not nonempty(earliest_divergence):
            errors.append(f"{field}.earliest_divergence must be non-empty")
        if (
            valid_fingerprint(fingerprint)
            and valid_requirement_id(acceptance_outcome_id)
            and valid_requirement_id(boundary_id)
        ):
            if failure_identity_version == 1:
                expected_fingerprint = canonical_failure_fingerprint_v1(
                    item_lineage_id, acceptance_outcome_id, boundary_id
                )
            elif failure_identity_version == 2:
                expected_fingerprint = canonical_failure_fingerprint_v2(
                    {
                        "lineage_id": item_lineage_id,
                        "acceptance_outcome_id": acceptance_outcome_id,
                        "boundary_id": boundary_id,
                    },
                    str(earliest_divergence),
                )
            else:
                expected_fingerprint = canonical_failure_fingerprint(
                    {
                        "lineage_id": item_lineage_id,
                        "acceptance_outcome_id": acceptance_outcome_id,
                        "boundary_id": boundary_id,
                    },
                    str(earliest_divergence),
                )
            if fingerprint != expected_fingerprint:
                errors.append(f"{field}.fingerprint does not match its structured failure identity")
        key = (item_lineage_id, fingerprint)
        if key in seen:
            errors.append(f"{prefix} contains a duplicate failure fingerprint")
        seen.add(key)
        if item.get("failure_class") not in FAILURE_CLASSES:
            errors.append(f"{field}.failure_class is invalid")
        count = item.get("count")
        if not positive_int(count):
            errors.append(f"{field}.count must be a positive integer")
            count = 0
        validate_utc(item.get("last_observed_utc"), f"{field}.last_observed_utc", errors)
        normalized.append({
            "fingerprint": fingerprint,
            "acceptance_outcome_id": acceptance_outcome_id,
            "boundary_id": boundary_id,
            "count": count,
        })
    return normalized


def recovered_failure_entries_from_provenance(
    provenance: object,
    source_failure: object,
    provenance_ref: object,
    prefix: str,
    errors: list[str],
) -> list[dict[str, Any]] | None:
    """Derive one v2 identity per recovered historic attempt, or fail closed."""
    if not isinstance(provenance, dict):
        errors.append(f"{prefix} must be an object")
        return None
    required_fields = {"kind", "source", "legacy_failure_class", "attempts"}
    allowed_fields = required_fields | {"status", "purpose", "integrity_conclusion"}
    if not required_fields.issubset(provenance) or not set(provenance).issubset(allowed_fields):
        missing = sorted(required_fields - set(provenance))
        unknown = sorted(set(provenance) - allowed_fields)
        if missing:
            errors.append(f"{prefix} is missing fields: " + ", ".join(missing))
        if unknown:
            errors.append(f"{prefix} has unknown fields: " + ", ".join(unknown))
    if provenance.get("kind") != FAILURE_IDENTITY_PROVENANCE_KIND:
        errors.append(f"{prefix}.kind is invalid")
    if provenance.get("legacy_failure_class") != source_failure:
        errors.append(f"{prefix}.legacy_failure_class must exactly match the legacy ledger record")

    source = provenance.get("source")
    required_source_fields = {
        "kind",
        "path",
        "snapshot_observed_utc",
        "snapshot_sha256",
        "custody",
    }
    allowed_source_fields = required_source_fields | {"limit"}
    if not isinstance(source, dict):
        errors.append(f"{prefix}.source must be an object")
    else:
        if not required_source_fields.issubset(source) or not set(source).issubset(allowed_source_fields):
            missing = sorted(required_source_fields - set(source))
            unknown = sorted(set(source) - allowed_source_fields)
            if missing:
                errors.append(f"{prefix}.source is missing fields: " + ", ".join(missing))
            if unknown:
                errors.append(f"{prefix}.source has unknown fields: " + ", ".join(unknown))
        if source.get("kind") != "codex-session-transcript":
            errors.append(f"{prefix}.source.kind is invalid")
        if not nonempty(source.get("path")):
            errors.append(f"{prefix}.source.path must be non-empty")
        validate_utc(source.get("snapshot_observed_utc"), f"{prefix}.source.snapshot_observed_utc", errors)
        if not valid_fingerprint(source.get("snapshot_sha256")):
            errors.append(f"{prefix}.source.snapshot_sha256 must be a SHA-256 fingerprint")
        if source.get("custody") != "recovered-mutable-transcript":
            errors.append(f"{prefix}.source.custody must state recovered-mutable-transcript")

    attempts = provenance.get("attempts")
    if not isinstance(source_failure, dict):
        errors.append(f"{prefix} cannot derive entries without a legacy failure object")
        return None
    if not isinstance(attempts, list) or not attempts:
        errors.append(f"{prefix}.attempts must be a non-empty array")
        return None
    source_count = source_failure.get("count")
    if not positive_int(source_count) or len(attempts) != source_count:
        errors.append(f"{prefix}.attempts must contain exactly one record per legacy failure count")

    required_attempt_fields = {
        "attempt_id",
        "earliest_divergence",
        "last_observed_utc",
        "transcript_line_hashes",
    }
    allowed_attempt_fields = required_attempt_fields | {
        "recovered_result_sha256",
        "current_result_ref",
        "current_result_sha256",
        "provenance_limit",
    }
    normalized_attempts: list[dict[str, Any]] = []
    seen_attempt_ids: set[str] = set()
    seen_divergences: set[str] = set()
    for index, attempt in enumerate(attempts):
        attempt_prefix = f"{prefix}.attempts[{index}]"
        if not isinstance(attempt, dict):
            errors.append(f"{attempt_prefix} must be an object")
            continue
        if not required_attempt_fields.issubset(attempt) or not set(attempt).issubset(allowed_attempt_fields):
            missing = sorted(required_attempt_fields - set(attempt))
            unknown = sorted(set(attempt) - allowed_attempt_fields)
            if missing:
                errors.append(f"{attempt_prefix} is missing fields: " + ", ".join(missing))
            if unknown:
                errors.append(f"{attempt_prefix} has unknown fields: " + ", ".join(unknown))
        attempt_id = attempt.get("attempt_id")
        if not valid_requirement_id(attempt_id):
            errors.append(f"{attempt_prefix}.attempt_id must be a stable ID")
        elif attempt_id in seen_attempt_ids:
            errors.append(f"{prefix}.attempts contains a duplicate attempt_id")
        else:
            seen_attempt_ids.add(attempt_id)
        divergence = attempt.get("earliest_divergence")
        if not nonempty(divergence):
            errors.append(f"{attempt_prefix}.earliest_divergence must be non-empty")
        else:
            normalized_divergence = normalize_earliest_divergence(divergence)
            if normalized_divergence in seen_divergences:
                errors.append(f"{prefix}.attempts must have distinct earliest divergences")
            seen_divergences.add(normalized_divergence)
        last_observed = attempt.get("last_observed_utc")
        validate_utc(last_observed, f"{attempt_prefix}.last_observed_utc", errors)
        line_hashes = attempt.get("transcript_line_hashes")
        if not isinstance(line_hashes, list) or not line_hashes:
            errors.append(f"{attempt_prefix}.transcript_line_hashes must be a non-empty array")
        elif len(set(line_hashes)) != len(line_hashes) or not all(
            valid_fingerprint(value) for value in line_hashes
        ):
            errors.append(f"{attempt_prefix}.transcript_line_hashes must contain unique SHA-256 fingerprints")
        if (
            valid_requirement_id(attempt_id)
            and nonempty(divergence)
            and isinstance(last_observed, str)
            and isinstance(line_hashes, list)
            and line_hashes
            and all(valid_fingerprint(value) for value in line_hashes)
        ):
            normalized_attempts.append(
                {
                    "attempt_id": attempt_id,
                    "earliest_divergence": divergence,
                    "last_observed_utc": last_observed,
                    "transcript_line_hashes": line_hashes,
                }
            )
    if len(normalized_attempts) != len(attempts):
        return None
    source_divergence = source_failure.get("earliest_divergence")
    if not nonempty(source_divergence) or (
        normalize_earliest_divergence(source_divergence)
        not in {normalize_earliest_divergence(item["earliest_divergence"]) for item in normalized_attempts}
    ):
        errors.append(f"{prefix}.attempts must retain the legacy ledger's earliest divergence")
    if source_failure.get("last_observed_utc") != max(
        item["last_observed_utc"] for item in normalized_attempts
    ):
        errors.append(f"{prefix}.attempts latest observation must equal the legacy ledger observation")
    if errors:
        return None

    entries: list[dict[str, Any]] = []
    for attempt in normalized_attempts:
        entries.append(
            {
                "fingerprint": canonical_failure_fingerprint_v2(
                    source_failure, attempt["earliest_divergence"]
                ),
                "failure_identity_version": 2,
                "lineage_id": source_failure.get("lineage_id"),
                "failure_class": source_failure.get("failure_class"),
                "earliest_divergence": attempt["earliest_divergence"],
                "acceptance_outcome_id": source_failure.get("acceptance_outcome_id"),
                "boundary_id": source_failure.get("boundary_id"),
                "candidate_fingerprint": source_failure.get("candidate_fingerprint"),
                "count": 1,
                "last_observed_utc": attempt["last_observed_utc"],
                "source_attempt_id": attempt["attempt_id"],
                "provenance_ref": provenance_ref,
            }
        )
    return entries


def validate_usage_monotonic_extension(
    previous_usage: object,
    current_usage: object,
    prefix: str,
    errors: list[str],
) -> None:
    """Require later ledger usage to retain every historic migration outcome.

    Failure-identity migrations are append-only historical corrections.  A later
    candidate bind or accepted attempt must therefore be able to add usage, but
    cannot erase, rewrite, or revive the usage that the sealed correction
    produced.
    """
    if not isinstance(previous_usage, dict) or not isinstance(current_usage, dict):
        errors.append(f"{prefix} must compare two usage objects")
        return

    for field in (
        "total_attempts",
        "failed_attempts",
        "expensive_attempts",
        "support_attempts",
        "no_progress_attempts",
        "total_tool_calls",
        "support_tool_calls",
        "support_no_progress_calls",
        "active_attempt_seconds",
        "spawned_workers",
        "scope_growth_actions",
        "path_touches",
        "hot_path_touches",
    ):
        prior = previous_usage.get(field)
        current = current_usage.get(field)
        if not nonnegative_int(prior) or not nonnegative_int(current):
            errors.append(f"{prefix}.{field} must remain a non-negative integer")
        elif current < prior:
            errors.append(f"{prefix}.{field} cannot decrease from historic migration usage")

    prior_paths = previous_usage.get("path_counts")
    current_paths = current_usage.get("path_counts")
    if not isinstance(prior_paths, dict) or not isinstance(current_paths, dict):
        errors.append(f"{prefix}.path_counts must remain an object")
    else:
        for path, prior_count in prior_paths.items():
            current_count = current_paths.get(path)
            if not positive_int(prior_count) or not positive_int(current_count):
                errors.append(f"{prefix}.path_counts[{path!r}] must remain a positive integer")
            elif current_count < prior_count:
                errors.append(f"{prefix}.path_counts[{path!r}] cannot decrease from historic migration usage")

    prior_families = previous_usage.get("method_families")
    current_families = current_usage.get("method_families")
    if not isinstance(prior_families, list) or not isinstance(current_families, list):
        errors.append(f"{prefix}.method_families must remain an array")
    else:
        current_by_id = {
            item.get("id"): item for item in current_families if isinstance(item, dict)
        }
        for index, prior_family in enumerate(prior_families):
            family_prefix = f"{prefix}.method_families[{index}]"
            if not isinstance(prior_family, dict):
                errors.append(f"{family_prefix} must remain an object")
                continue
            family_id = prior_family.get("id")
            current_family = current_by_id.get(family_id)
            if not isinstance(current_family, dict):
                errors.append(f"{family_prefix} must not be removed from later usage")
                continue
            for field in (
                "id",
                "requirement_id",
                "acceptance_outcome_id",
                "method_family_fingerprint",
                "prior_method_family_id",
                "method_change_evidence_ref",
                "method_change_evidence_fingerprint",
                "lower_complexity_comparison_ref",
                "lower_complexity_comparison_fingerprint",
            ):
                if current_family.get(field) != prior_family.get(field):
                    errors.append(f"{family_prefix}.{field} cannot change after historic migration")
            for field in ("failed_attempts", "no_progress_attempts"):
                prior_count = prior_family.get(field)
                current_count = current_family.get(field)
                if not nonnegative_int(prior_count) or not nonnegative_int(current_count):
                    errors.append(f"{family_prefix}.{field} must remain a non-negative integer")
                elif current_count < prior_count:
                    errors.append(f"{family_prefix}.{field} cannot decrease after historic migration")
            prior_stop_evidence = prior_family.get("stop_evidence_fingerprints")
            current_stop_evidence = current_family.get("stop_evidence_fingerprints")
            if not isinstance(prior_stop_evidence, list) or not isinstance(current_stop_evidence, list):
                errors.append(f"{family_prefix}.stop_evidence_fingerprints must remain an array")
            elif not set(prior_stop_evidence).issubset(current_stop_evidence):
                errors.append(f"{family_prefix}.stop_evidence_fingerprints cannot remove historic evidence")
            if prior_family.get("status") == "stopped":
                if current_family.get("status") != "stopped":
                    errors.append(f"{family_prefix} cannot revive a stopped method family")
                elif current_family.get("stop_reason") != prior_family.get("stop_reason"):
                    errors.append(f"{family_prefix}.stop_reason cannot change for a stopped family")
            prior_failures = prior_family.get("failures")
            current_failures = current_family.get("failures")
            if not isinstance(prior_failures, list) or not isinstance(current_failures, list):
                errors.append(f"{family_prefix}.failures must remain an array")
            else:
                current_failure_counts = {
                    (item.get("acceptance_outcome_id"), item.get("boundary_id")): item.get("count")
                    for item in current_failures if isinstance(item, dict)
                }
                for failure in prior_failures:
                    if not isinstance(failure, dict):
                        errors.append(f"{family_prefix}.failures must retain historic objects")
                        continue
                    key = (failure.get("acceptance_outcome_id"), failure.get("boundary_id"))
                    prior_count = failure.get("count")
                    current_count = current_failure_counts.get(key)
                    if not positive_int(prior_count) or not positive_int(current_count):
                        errors.append(f"{family_prefix}.failures[{key!r}] must remain a positive integer")
                    elif current_count < prior_count:
                        errors.append(f"{family_prefix}.failures[{key!r}] cannot decrease after historic migration")

    prior_failures = previous_usage.get("failure_classes")
    current_failures = current_usage.get("failure_classes")
    if not isinstance(prior_failures, list) or not isinstance(current_failures, list):
        errors.append(f"{prefix}.failure_classes must remain an array")
        return
    current_by_fingerprint = {
        item.get("fingerprint"): item for item in current_failures if isinstance(item, dict)
    }
    for index, prior_failure in enumerate(prior_failures):
        failure_prefix = f"{prefix}.failure_classes[{index}]"
        if not isinstance(prior_failure, dict):
            errors.append(f"{failure_prefix} must remain an object")
            continue
        current_failure = current_by_fingerprint.get(prior_failure.get("fingerprint"))
        if not isinstance(current_failure, dict):
            errors.append(f"{failure_prefix} must not be removed from later usage")
            continue
        for field, value in prior_failure.items():
            if field not in {"count", "last_observed_utc"} and current_failure.get(field) != value:
                errors.append(f"{failure_prefix}.{field} cannot change after historic migration")
        prior_count = prior_failure.get("count")
        current_count = current_failure.get("count")
        if not positive_int(prior_count) or not positive_int(current_count):
            errors.append(f"{failure_prefix}.count must remain a positive integer")
        elif current_count < prior_count:
            errors.append(f"{failure_prefix}.count cannot decrease after historic migration")
        prior_observed = prior_failure.get("last_observed_utc")
        current_observed = current_failure.get("last_observed_utc")
        if isinstance(prior_observed, str) and isinstance(current_observed, str) and current_observed < prior_observed:
            errors.append(f"{failure_prefix}.last_observed_utc cannot move backward after historic migration")


def validate_failure_identity_migrations(
    items: object,
    root: Path,
    prefix: str,
    current_revision: object,
    current_usage: object,
    active_failure_classes: list[dict[str, Any]],
    lineage_id: object,
    candidate_fingerprint: object,
    scope_fingerprint: object,
    errors: list[str],
) -> None:
    """Validate an append-only legacy-v1 to divergence-aware-v2 correction history."""
    if items is None:
        return
    if not isinstance(items, list):
        errors.append(f"{prefix} must be an array when present")
        return
    if not isinstance(current_usage, dict):
        errors.append(f"{prefix} cannot validate without execution-control usage")
        return
    active_fingerprints = {entry.get("fingerprint") for entry in active_failure_classes}
    seen_ids: set[str] = set()
    seen_sources: set[str] = set()
    previous_after: dict[str, Any] | None = None
    previous_result_anchor: dict[str, Any] | None = None
    previous_result_revision = -1
    for index, item in enumerate(items):
        item_prefix = f"{prefix}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{item_prefix} must be an object")
            continue
        item_kind = item.get("kind")
        record_fields = (
            LEGACY_FAILURE_IDENTITY_MIGRATION_RECORD_FIELDS
            if item_kind == LEGACY_FAILURE_IDENTITY_MIGRATION_KIND
            else FAILURE_IDENTITY_MIGRATION_RECORD_FIELDS
        )
        unknown = sorted(set(item) - record_fields)
        missing = sorted(record_fields - set(item))
        if unknown:
            errors.append(f"{item_prefix} contains unknown fields: " + ", ".join(unknown))
        if missing:
            errors.append(f"{item_prefix} is missing fields: " + ", ".join(missing))
        if item_kind not in FAILURE_IDENTITY_MIGRATION_REQUEST_KINDS:
            errors.append(f"{item_prefix}.kind is invalid")
        item_id = item.get("id")
        if not valid_requirement_id(item_id):
            errors.append(f"{item_prefix}.id must be a stable ID")
        elif item_id in seen_ids:
            errors.append(f"{prefix} contains a duplicate migration id")
        else:
            seen_ids.add(item_id)
        validate_utc(item.get("migrated_utc"), f"{item_prefix}.migrated_utc", errors)
        prior_revision = item.get("prior_revision")
        result_revision = item.get("result_revision")
        if not nonnegative_int(prior_revision) or not nonnegative_int(result_revision):
            errors.append(f"{item_prefix} revisions must be non-negative integers")
        elif result_revision != prior_revision + 1:
            errors.append(f"{item_prefix}.result_revision must equal prior_revision plus one")
        elif prior_revision < previous_result_revision:
            errors.append(f"{item_prefix}.prior_revision must not precede earlier migration history")
        elif nonnegative_int(current_revision) and result_revision > current_revision:
            errors.append(f"{item_prefix}.result_revision cannot exceed the live control revision")
        if nonnegative_int(result_revision):
            previous_result_revision = max(previous_result_revision, result_revision)
        if not nonempty(item.get("reason")):
            errors.append(f"{item_prefix}.reason must be non-empty")
        item_lineage_id = item.get("lineage_id")
        item_candidate_fingerprint = item.get("candidate_fingerprint")
        item_scope_fingerprint = item.get("scope_fingerprint")
        if not valid_requirement_id(item_lineage_id):
            errors.append(f"{item_prefix}.lineage_id must be a stable ID")
        elif item_lineage_id != lineage_id:
            errors.append(f"{item_prefix}.lineage_id must match live control")
        if not valid_fingerprint(item_candidate_fingerprint):
            errors.append(f"{item_prefix}.candidate_fingerprint must be a SHA-256 fingerprint")
        if not valid_fingerprint(item_scope_fingerprint):
            errors.append(f"{item_prefix}.scope_fingerprint must be a SHA-256 fingerprint")
        historical_binding = (
            item_candidate_fingerprint != candidate_fingerprint
            or item_scope_fingerprint != scope_fingerprint
        )
        if historical_binding and (
            not nonnegative_int(result_revision)
            or not nonnegative_int(current_revision)
            or result_revision >= current_revision
        ):
            errors.append(f"{item_prefix} historical binding must precede the live control revision")
        for field in (
            "authorization_fingerprint",
            "provenance_fingerprint",
            "usage_fingerprint",
            "migration_fingerprint",
        ):
            if not valid_fingerprint(item.get(field)):
                errors.append(f"{item_prefix}.{field} must be a SHA-256 fingerprint")
        if item_kind == FAILURE_IDENTITY_MIGRATION_KIND and not valid_fingerprint(
            item.get("result_usage_fingerprint")
        ):
            errors.append(
                f"{item_prefix}.result_usage_fingerprint must be a SHA-256 fingerprint"
            )
        _, authorization_path = resolve_limit_extension_evidence_path(
            root, item.get("authorization_ref"), f"{item_prefix}.authorization_ref", errors,
            must_exist=True,
        )
        _, provenance_path = resolve_limit_extension_evidence_path(
            root, item.get("provenance_ref"), f"{item_prefix}.provenance_ref", errors,
            must_exist=True,
        )
        _, receipt_path = resolve_limit_extension_evidence_path(
            root, item.get("receipt_ref"), f"{item_prefix}.receipt_ref", errors,
            must_exist=True,
        )
        if authorization_path is not None and valid_fingerprint(item.get("authorization_fingerprint")):
            if file_sha256_fingerprint(authorization_path) != item.get("authorization_fingerprint"):
                errors.append(f"{item_prefix}.authorization_fingerprint does not match the evidence file")
        if provenance_path is not None and valid_fingerprint(item.get("provenance_fingerprint")):
            if file_sha256_fingerprint(provenance_path) != item.get("provenance_fingerprint"):
                errors.append(f"{item_prefix}.provenance_fingerprint does not match the evidence file")
        source_failure = item.get("source_legacy_failure_class")
        source_normalized = validate_failure_classes(
            [source_failure], f"{item_prefix}.source_legacy_failure_class", item_lineage_id, errors
        )
        if not isinstance(source_failure, dict) or source_failure.get("failure_identity_version", 1) != 1:
            errors.append(f"{item_prefix}.source_legacy_failure_class must be a legacy v1 identity")
        source_fingerprint = source_failure.get("fingerprint") if isinstance(source_failure, dict) else None
        if source_fingerprint in seen_sources:
            errors.append(f"{prefix} contains a duplicate legacy source fingerprint")
        elif valid_fingerprint(source_fingerprint):
            seen_sources.add(source_fingerprint)
        if source_fingerprint in active_fingerprints:
            errors.append(f"{item_prefix}.source legacy fingerprint must not remain active")
        if isinstance(source_failure, dict) and source_failure.get("candidate_fingerprint") != item_candidate_fingerprint:
            errors.append(f"{item_prefix}.source legacy candidate must match the migration record")

        provenance = None
        if provenance_path is not None:
            provenance, provenance_errors = load_json_object(provenance_path, f"{item_prefix}.provenance")
            errors.extend(provenance_errors)
        expected_entries = recovered_failure_entries_from_provenance(
            provenance,
            source_failure,
            item.get("provenance_ref"),
            f"{item_prefix}.provenance",
            errors,
        )
        migrated = item.get("migrated_failure_classes")
        if not isinstance(migrated, list):
            errors.append(f"{item_prefix}.migrated_failure_classes must be an array")
        else:
            validate_failure_classes(
                migrated, f"{item_prefix}.migrated_failure_classes", item_lineage_id, errors
            )
            if any(
                not isinstance(entry, dict)
                or entry.get("failure_identity_version") != 2
                or entry.get("count") != 1
                or entry.get("candidate_fingerprint") != item_candidate_fingerprint
                for entry in migrated
            ):
                errors.append(f"{item_prefix}.migrated_failure_classes must be individual v2 records")
            if expected_entries is not None and migrated != expected_entries:
                errors.append(f"{item_prefix}.migrated_failure_classes do not match recovered provenance")
        if item_kind == LEGACY_FAILURE_IDENTITY_MIGRATION_KIND:
            usage_snapshot = item.get("usage_snapshot")
            if canonical_fingerprint(usage_snapshot) != item.get("usage_fingerprint"):
                errors.append(f"{item_prefix}.usage_snapshot does not match usage_fingerprint")
            if not isinstance(usage_snapshot, dict) or not isinstance(migrated, list):
                continue
            snapshot_classes = usage_snapshot.get("failure_classes")
            if not isinstance(snapshot_classes, list):
                errors.append(f"{item_prefix}.usage_snapshot.failure_classes must be an array")
                continue
            source_positions = [
                position
                for position, entry in enumerate(snapshot_classes)
                if entry == source_failure
            ]
            if len(source_positions) != 1:
                errors.append(
                    f"{item_prefix}.usage_snapshot must contain exactly one unchanged legacy source"
                )
                continue
            position = source_positions[0]
            expected_after = json.loads(json.dumps(usage_snapshot))
            expected_after["failure_classes"] = (
                snapshot_classes[:position] + migrated + snapshot_classes[position + 1 :]
            )
            if previous_after is not None:
                validate_usage_monotonic_extension(
                    previous_after,
                    usage_snapshot,
                    f"{item_prefix}.usage_snapshot",
                    errors,
                )
            previous_after = expected_after
            previous_result_anchor = compact_usage_anchor(expected_after)
        else:
            usage_anchor = item.get("usage_anchor")
            result_usage_anchor = item.get("result_usage_anchor")
            validate_usage_anchor(usage_anchor, f"{item_prefix}.usage_anchor", errors)
            validate_usage_anchor(
                result_usage_anchor, f"{item_prefix}.result_usage_anchor", errors
            )
            if isinstance(usage_anchor, dict) and isinstance(result_usage_anchor, dict):
                expected_result_anchor = dict(usage_anchor)
                if isinstance(migrated, list):
                    expected_result_anchor["failure_class_count"] = (
                        usage_anchor.get("failure_class_count", 0) - 1 + len(migrated)
                    )
                if result_usage_anchor != expected_result_anchor:
                    errors.append(
                        f"{item_prefix}.result_usage_anchor must change only the migrated failure-class count"
                    )
                if previous_result_anchor is not None:
                    for field in USAGE_ANCHOR_SCALAR_FIELDS:
                        if usage_anchor.get(field, 0) < previous_result_anchor.get(field, 0):
                            errors.append(
                                f"{item_prefix}.usage_anchor.{field} cannot decrease"
                            )
                previous_result_anchor = result_usage_anchor
            previous_after = None
        fingerprint_payload = {
            field: item.get(field)
            for field in sorted(record_fields - {"migration_fingerprint"})
        }
        if valid_fingerprint(item.get("migration_fingerprint")) and (
            canonical_fingerprint(fingerprint_payload) != item.get("migration_fingerprint")
        ):
            errors.append(f"{item_prefix}.migration_fingerprint is invalid")
        if receipt_path is not None:
            receipt, receipt_errors = load_json_object(receipt_path, f"{item_prefix}.receipt")
            errors.extend(receipt_errors)
            if receipt is not None:
                expected_receipt_kind = (
                    LEGACY_FAILURE_IDENTITY_MIGRATION_RECEIPT_KIND
                    if item_kind == LEGACY_FAILURE_IDENTITY_MIGRATION_KIND
                    else FAILURE_IDENTITY_MIGRATION_RECEIPT_KIND
                )
                if receipt.get("kind") != expected_receipt_kind:
                    errors.append(f"{item_prefix}.receipt has the wrong kind")
                if receipt.get("migration") != item:
                    errors.append(f"{item_prefix}.receipt does not exactly mirror the migration")
    if previous_after is not None:
        validate_usage_monotonic_extension(
            previous_after,
            current_usage,
            f"{prefix} final migration output",
            errors,
        )
    elif items:
        last = items[-1] if isinstance(items[-1], dict) else {}
        if (
            last.get("kind") == FAILURE_IDENTITY_MIGRATION_KIND
            and last.get("result_revision") == current_revision
            and last.get("result_usage_fingerprint")
            != canonical_fingerprint(current_usage)
        ):
            errors.append(f"{prefix} final migration output does not match current usage")


def validate_method_families(
    items: object, prefix: str, errors: list[str]
) -> dict[str, dict[str, Any]]:
    if not isinstance(items, list):
        errors.append(f"{prefix} must be an array")
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    seen_fingerprints: dict[str, str] = {}
    for index, item in enumerate(items):
        field = f"{prefix}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{field} must be an object")
            continue
        family_id = item.get("id")
        requirement_id = item.get("requirement_id")
        acceptance_outcome_id = item.get("acceptance_outcome_id")
        if not valid_requirement_id(family_id):
            errors.append(f"{field}.id must be a structured ID")
            continue
        if family_id in normalized:
            errors.append(f"duplicate method family id: {family_id}")
        if not valid_requirement_id(requirement_id):
            errors.append(f"{field}.requirement_id must be a structured ID")
        if not valid_requirement_id(acceptance_outcome_id):
            errors.append(f"{field}.acceptance_outcome_id must be a structured ID")
        family_fingerprint = item.get("method_family_fingerprint")
        if not valid_fingerprint(family_fingerprint):
            errors.append(f"{field}.method_family_fingerprint must be SHA-256")
        elif family_fingerprint in seen_fingerprints:
            errors.append(
                f"{field}.method_family_fingerprint duplicates family "
                + seen_fingerprints[family_fingerprint]
            )
        else:
            seen_fingerprints[family_fingerprint] = str(family_id)
        prior_family_id = item.get("prior_method_family_id")
        if prior_family_id is not None and not valid_requirement_id(prior_family_id):
            errors.append(f"{field}.prior_method_family_id must be null or structured ID")
        if prior_family_id == family_id:
            errors.append(f"{field}.prior_method_family_id cannot equal its own ID")
        for ref_field, fingerprint_field in (
            ("method_change_evidence_ref", "method_change_evidence_fingerprint"),
            (
                "lower_complexity_comparison_ref",
                "lower_complexity_comparison_fingerprint",
            ),
        ):
            ref = item.get(ref_field)
            fingerprint = item.get(fingerprint_field)
            if (ref is None) != (fingerprint is None):
                errors.append(
                    f"{field}.{ref_field} and {fingerprint_field} must both be null or bound"
                )
            if ref is not None and normalize_declared_relative_path(ref) != ref:
                errors.append(f"{field}.{ref_field} must be normalized")
            if fingerprint is not None and not valid_fingerprint(fingerprint):
                errors.append(f"{field}.{fingerprint_field} must be SHA-256")
        stop_evidence = item.get("stop_evidence_fingerprints")
        if not isinstance(stop_evidence, list) or any(
            not valid_fingerprint(value) for value in stop_evidence
        ) or len(set(stop_evidence)) != len(stop_evidence):
            errors.append(
                f"{field}.stop_evidence_fingerprints must contain unique SHA-256 values"
            )
        failed_attempts = item.get("failed_attempts")
        no_progress_attempts = item.get("no_progress_attempts")
        if not nonnegative_int(failed_attempts):
            errors.append(f"{field}.failed_attempts must be a non-negative integer")
            failed_attempts = 0
        if not nonnegative_int(no_progress_attempts):
            errors.append(f"{field}.no_progress_attempts must be a non-negative integer")
            no_progress_attempts = 0
        failures = item.get("failures")
        normalized_failures: list[dict[str, Any]] = []
        if not isinstance(failures, list):
            errors.append(f"{field}.failures must be an array")
        else:
            seen: set[tuple[object, object]] = set()
            for failure_index, failure in enumerate(failures):
                failure_field = f"{field}.failures[{failure_index}]"
                if not isinstance(failure, dict):
                    errors.append(f"{failure_field} must be an object")
                    continue
                outcome_id = failure.get("acceptance_outcome_id")
                boundary_id = failure.get("boundary_id")
                count = failure.get("count")
                pair = (outcome_id, boundary_id)
                if not valid_requirement_id(outcome_id):
                    errors.append(f"{failure_field}.acceptance_outcome_id must be a structured ID")
                if not valid_requirement_id(boundary_id):
                    errors.append(f"{failure_field}.boundary_id must be a structured ID")
                if pair in seen:
                    errors.append(f"{field}.failures contains a duplicate structured boundary")
                seen.add(pair)
                if not positive_int(count):
                    errors.append(f"{failure_field}.count must be a positive integer")
                    count = 0
                normalized_failures.append({
                    "acceptance_outcome_id": outcome_id,
                    "boundary_id": boundary_id,
                    "count": count,
                })
        if sum(entry["count"] for entry in normalized_failures) != failed_attempts:
            errors.append(f"{field}.failed_attempts must equal its structured failure count")
        status = item.get("status")
        if status not in {"active", "stopped"}:
            errors.append(f"{field}.status must be active or stopped")
        fired = (
            failed_attempts >= METHOD_FAMILY_FAILURE_LIMIT
            or no_progress_attempts >= METHOD_FAMILY_NO_PROGRESS_LIMIT
        )
        stop_reason = item.get("stop_reason")
        if fired and status != "stopped":
            errors.append(f"{field}.status must be stopped after its method-family breaker fires")
        if status == "stopped" and not nonempty(stop_reason):
            errors.append(f"{field}.stop_reason must be non-empty when stopped")
        if status == "active" and stop_reason is not None:
            errors.append(f"{field}.stop_reason must be null while active")
        normalized[family_id] = {
            **item,
            "failed_attempts": failed_attempts,
            "no_progress_attempts": no_progress_attempts,
            "failures": normalized_failures,
        }
    for family_id, family in normalized.items():
        prior_family_id = family.get("prior_method_family_id")
        if prior_family_id is None:
            continue
        prior = normalized.get(prior_family_id)
        if prior is None:
            errors.append(
                f"{prefix} family {family_id} references unknown prior family {prior_family_id}"
            )
        elif prior.get("status") != "stopped":
            errors.append(
                f"{prefix} family {family_id} prior family must be stopped"
            )
        elif (
            prior.get("requirement_id") != family.get("requirement_id")
            or prior.get("acceptance_outcome_id")
            != family.get("acceptance_outcome_id")
        ):
            errors.append(
                f"{prefix} family {family_id} prior family belongs to another outcome"
            )
    return normalized


def validate_gate_receipts(
    items: object,
    prefix: str,
    requirement_by_id: dict[str, dict[str, Any]],
    lineage_id: object,
    candidate_fingerprint: object,
    diagnostic_fingerprints: set[str],
    errors: list[str],
) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        errors.append(f"{prefix} must be an array")
        return []
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        field = f"{prefix}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{field} must be an object")
            continue
        receipt_id = item.get("id")
        requirement_id = item.get("requirement_id")
        tier = item.get("tier")
        if not valid_requirement_id(receipt_id):
            errors.append(f"{field}.id must be a stable receipt ID")
        elif receipt_id in seen:
            errors.append(f"duplicate gate receipt id: {receipt_id}")
        seen.add(receipt_id)
        requirement = requirement_by_id.get(requirement_id)
        if not requirement:
            errors.append(f"{field}.requirement_id is unknown")
        elif tier not in requirement["gate_tiers"]:
            errors.append(f"{field}.tier is not declared by its requirement")
        if item.get("lineage_id") != lineage_id:
            errors.append(f"{field}.lineage_id must match the active lineage")
        if item.get("candidate_fingerprint") != candidate_fingerprint:
            errors.append(f"{field}.candidate_fingerprint must match the active candidate")
        if not nonempty(item.get("evidence_ref")):
            errors.append(f"{field}.evidence_ref must be non-empty")
        validate_utc(item.get("verified_utc"), f"{field}.verified_utc", errors)
        evaluation_role = item.get("evaluation_role", "none")
        evaluation_fingerprint = item.get("evaluation_fingerprint")
        if evaluation_role not in EVALUATION_ROLES:
            errors.append(f"{field}.evaluation_role is invalid")
        if evaluation_role == "none" and evaluation_fingerprint is not None:
            errors.append(f"{field}.evaluation_fingerprint must be null for role none")
        if evaluation_role != "none" and not valid_fingerprint(evaluation_fingerprint):
            errors.append(f"{field}.evaluation_fingerprint must be a SHA-256 fingerprint")
        normalized.append(
            {
                "id": receipt_id,
                "requirement_id": requirement_id,
                "tier": tier,
                "lineage_id": item.get("lineage_id"),
                "candidate_fingerprint": item.get("candidate_fingerprint"),
                "evidence_ref": item.get("evidence_ref"),
                "evaluation_role": evaluation_role,
                "evaluation_fingerprint": evaluation_fingerprint,
            }
        )
    return normalized


def validate_prerequisites(
    items: object, prefix: str, known_requirement_ids: set[str], errors: list[str]
) -> dict[str, dict[str, Any]]:
    if not isinstance(items, list):
        errors.append(f"{prefix} must be an array")
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(items):
        field = f"{prefix}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{field} must be an object")
            continue
        item_id = item.get("id")
        if not valid_requirement_id(item_id):
            errors.append(f"{field}.id must be a stable prerequisite ID")
            continue
        if item_id in normalized:
            errors.append(f"duplicate prerequisite id: {item_id}")
        if not nonempty(item.get("description")):
            errors.append(f"{field}.description must be non-empty")
        status = item.get("status")
        if status not in {"missing", "verified"}:
            errors.append(f"{field}.status must be missing or verified")
        requirement_ids = validate_id_references(
            item.get("requirement_ids"),
            f"{field}.requirement_ids",
            known_requirement_ids,
            errors,
            require_nonempty=True,
        )
        action_classes = item.get("action_classes")
        if not isinstance(action_classes, list) or not action_classes:
            errors.append(f"{field}.action_classes must be a non-empty array")
            action_classes = []
        elif any(action not in ACTION_CLASSES for action in action_classes):
            errors.append(f"{field}.action_classes contains an invalid class")
        gate_tiers = item.get("gate_tiers")
        if not isinstance(gate_tiers, list) or any(tier not in GATE_TIERS for tier in gate_tiers):
            errors.append(f"{field}.gate_tiers must be an array of proof tiers")
            gate_tiers = []
        context_fingerprint = item.get("context_fingerprint")
        if not valid_fingerprint(context_fingerprint):
            errors.append(f"{field}.context_fingerprint must be a SHA-256 fingerprint")
        verified_utc = None
        if status == "verified":
            if not nonempty(item.get("evidence_ref")):
                errors.append(f"{field}.evidence_ref must be non-empty when verified")
            verified_utc = validate_utc(
                item.get("verified_utc"), f"{field}.verified_utc", errors
            )
            if (
                verified_utc is not None
                and verified_utc > datetime.now(timezone.utc).replace(tzinfo=None)
            ):
                errors.append(f"{field}.verified_utc cannot be in the future")
        expires_utc = item.get("expires_utc")
        if expires_utc is not None:
            expires = validate_utc(expires_utc, f"{field}.expires_utc", errors)
            if verified_utc is not None and expires is not None and expires <= verified_utc:
                errors.append(f"{field}.expires_utc must be later than verified_utc")
        normalized[item_id] = {
            **item,
            "requirement_ids": requirement_ids,
            "action_classes": action_classes,
            "gate_tiers": gate_tiers,
        }
    return normalized


def validate_authorizations(
    items: object, prefix: str, identity_ids: set[str], errors: list[str]
) -> dict[str, dict[str, Any]]:
    if not isinstance(items, list):
        errors.append(f"{prefix} must be an array")
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(items):
        field = f"{prefix}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{field} must be an object")
            continue
        item_id = item.get("id")
        if not valid_requirement_id(item_id):
            errors.append(f"{field}.id must be a stable authorization ID")
            continue
        if item_id in normalized:
            errors.append(f"duplicate authorization id: {item_id}")
        for name in ("action", "effect", "principal"):
            if not nonempty(item.get(name)):
                errors.append(f"{field}.{name} must be non-empty")
        targets = validate_id_references(
            item.get("target_identity_ids"),
            f"{field}.target_identity_ids",
            identity_ids,
            errors,
            require_nonempty=True,
        )
        if not valid_fingerprint(item.get("context_fingerprint")):
            errors.append(f"{field}.context_fingerprint must be a SHA-256 fingerprint")
        authorized_utc = validate_utc(
            item.get("authorized_utc"), f"{field}.authorized_utc", errors
        )
        expires_utc = validate_utc(
            item.get("expires_utc"), f"{field}.expires_utc", errors
        )
        if (
            authorized_utc is not None
            and authorized_utc > datetime.now(timezone.utc).replace(tzinfo=None)
        ):
            errors.append(f"{field}.authorized_utc cannot be in the future")
        if (
            authorized_utc is not None
            and expires_utc is not None
            and expires_utc <= authorized_utc
        ):
            errors.append(f"{field}.expires_utc must be later than authorized_utc")
        status = item.get("status")
        if status not in {"active", "consumed", "revoked"}:
            errors.append(f"{field}.status must be active, consumed, or revoked")
        uses_remaining = item.get("uses_remaining")
        if not nonnegative_int(uses_remaining):
            errors.append(f"{field}.uses_remaining must be a non-negative integer")
        if status == "active" and uses_remaining == 0:
            errors.append(f"{field}.status cannot be active with zero uses remaining")
        normalized[item_id] = {**item, "target_identity_ids": targets}
    return normalized


def validate_tool_binding(
    item: object, prefix: str, action_classes: set[str], errors: list[str]
) -> dict[str, Any]:
    if not isinstance(item, dict):
        errors.append(f"{prefix} must be an object")
        return {}
    tool_name = item.get("tool_name")
    if not nonempty(tool_name):
        errors.append(f"{prefix}.tool_name must be non-empty")
    cwd_relative = normalize_declared_relative_path(item.get("cwd_relative"))
    if cwd_relative is None or cwd_relative != item.get("cwd_relative"):
        errors.append(f"{prefix}.cwd_relative must be a normalized project-relative path")
    fingerprint = item.get("tool_input_fingerprint")
    if fingerprint is not None and not valid_fingerprint(fingerprint):
        errors.append(f"{prefix}.tool_input_fingerprint must be null or a SHA-256 fingerprint")
    if fingerprint is None and tool_is_effectful(str(tool_name), action_classes):
        errors.append(
            f"{prefix}.tool_input_fingerprint may be null only for a non-effectful local/support call"
        )
    if item.get("max_uses") != 1:
        errors.append(f"{prefix}.max_uses must equal 1")
    return item


def validate_tool_claim(item: object, prefix: str, errors: list[str]) -> None:
    if not isinstance(item, dict):
        errors.append(f"{prefix} must be an object")
        return
    status = item.get("status")
    if status not in {"unclaimed", "claimed", "observed"}:
        errors.append(f"{prefix}.status must be unclaimed, claimed, or observed")
        return
    if status == "unclaimed":
        for field in (
            "tool_use_id",
            "claimed_utc",
            "observed_utc",
            "outcome",
            "actual_tool_name",
            "actual_cwd_relative",
            "actual_tool_input_fingerprint",
            "progress_observed",
            "causal_evidence_fingerprint_after",
            "charged_active_attempt_seconds",
            "time_budget_overrun",
        ):
            if item.get(field) is not None:
                errors.append(f"{prefix}.{field} must be null before claim")
    else:
        if not nonempty(item.get("tool_use_id")):
            errors.append(f"{prefix}.tool_use_id must be non-empty after claim")
        validate_utc(item.get("claimed_utc"), f"{prefix}.claimed_utc", errors)
        if not nonempty(item.get("actual_tool_name")):
            errors.append(f"{prefix}.actual_tool_name must be non-empty after claim")
        if normalize_declared_relative_path(item.get("actual_cwd_relative")) != item.get(
            "actual_cwd_relative"
        ):
            errors.append(f"{prefix}.actual_cwd_relative must be normalized")
        if not valid_fingerprint(item.get("actual_tool_input_fingerprint")):
            errors.append(
                f"{prefix}.actual_tool_input_fingerprint must be a SHA-256 fingerprint after claim"
            )
    derived = item.get("derived_action_classes")
    if not isinstance(derived, list) or any(value not in ACTION_CLASSES for value in derived):
        errors.append(f"{prefix}.derived_action_classes must be an array of valid classes")
    paths = item.get("path_touches")
    if not isinstance(paths, list) or any(
        normalize_declared_relative_path(path) != path for path in paths
    ):
        errors.append(f"{prefix}.path_touches must contain normalized relative paths")
    if not nonnegative_int(item.get("hot_path_touches")):
        errors.append(f"{prefix}.hot_path_touches must be a non-negative integer")
    if status == "observed":
        validate_utc(item.get("observed_utc"), f"{prefix}.observed_utc", errors)
        if item.get("outcome") not in TOOL_OBSERVATION_OUTCOMES:
            errors.append(f"{prefix}.outcome is invalid")
        if not isinstance(item.get("progress_observed"), bool):
            errors.append(f"{prefix}.progress_observed must be boolean after observation")
        causal_after = item.get("causal_evidence_fingerprint_after")
        if causal_after is not None and not valid_fingerprint(causal_after):
            errors.append(
                f"{prefix}.causal_evidence_fingerprint_after must be null or SHA-256"
            )
        if not positive_int(item.get("charged_active_attempt_seconds")):
            errors.append(
                f"{prefix}.charged_active_attempt_seconds must be a positive integer"
            )
        if not isinstance(item.get("time_budget_overrun"), bool):
            errors.append(f"{prefix}.time_budget_overrun must be boolean")
    else:
        if item.get("observed_utc") is not None or item.get("outcome") is not None:
            errors.append(f"{prefix} observation fields must be null before PostToolUse")
        if item.get("progress_observed") is not None:
            errors.append(f"{prefix}.progress_observed must be null before PostToolUse")
        if item.get("causal_evidence_fingerprint_after") is not None:
            errors.append(
                f"{prefix}.causal_evidence_fingerprint_after must be null before PostToolUse"
            )
        if item.get("charged_active_attempt_seconds") is not None:
            errors.append(
                f"{prefix}.charged_active_attempt_seconds must be null before PostToolUse"
            )
        if item.get("time_budget_overrun") is not None:
            errors.append(f"{prefix}.time_budget_overrun must be null before PostToolUse")


def validate_active_attempt(
    item: object,
    prefix: str,
    requirement_by_id: dict[str, dict[str, Any]],
    lineage_id: object,
    scope_fingerprint: object,
    candidate_fingerprint: object,
    reconciled_utc: object,
    prerequisites: dict[str, dict[str, Any]],
    authorizations: dict[str, dict[str, Any]],
    method_families: dict[str, dict[str, Any]],
    identity_ids: set[str],
    diagnostic_fingerprints: set[str],
    errors: list[str],
) -> None:
    if not isinstance(item, dict):
        errors.append(f"{prefix} must be an object while running")
        return
    if not valid_requirement_id(item.get("id")):
        errors.append(f"{prefix}.id must be a stable attempt ID")
    requirement = requirement_by_id.get(item.get("requirement_id"))
    if not requirement:
        errors.append(f"{prefix}.requirement_id is unknown")
    elif item.get("tier") not in requirement["gate_tiers"]:
        errors.append(f"{prefix}.tier is not declared by its requirement")
    if item.get("lineage_id") != lineage_id:
        errors.append(f"{prefix}.lineage_id must match the active lineage")
    if item.get("scope_fingerprint") != scope_fingerprint:
        errors.append(f"{prefix}.scope_fingerprint must match the admitted acceptance scope")
    candidate_after = item.get("candidate_fingerprint_after")
    if candidate_after is None:
        if item.get("candidate_fingerprint") != candidate_fingerprint:
            errors.append(f"{prefix}.candidate_fingerprint must match the active candidate")
    elif candidate_after != candidate_fingerprint:
        errors.append(f"{prefix}.candidate_fingerprint_after must match the rebound candidate")
    if item.get("reconciled_utc") != reconciled_utc:
        errors.append(f"{prefix}.reconciled_utc must match the admitted reconciliation")
    if item.get("cost_class") not in COST_CLASSES:
        errors.append(f"{prefix}.cost_class must be cheap or expensive")
    action_classes = item.get("action_classes")
    if not isinstance(action_classes, list) or not action_classes or any(
        action not in ACTION_CLASSES for action in action_classes
    ):
        errors.append(f"{prefix}.action_classes must contain valid classes")
        action_classes = []
    action_class_set = set(action_classes)
    for field in ("method_family_id", "acceptance_outcome_id", "boundary_id"):
        if not valid_requirement_id(item.get(field)):
            errors.append(f"{prefix}.{field} must be a structured ID")
    family = method_families.get(item.get("method_family_id"))
    method_family_fingerprint = item.get("method_family_fingerprint")
    if method_family_fingerprint != calculate_method_family_fingerprint(item):
        errors.append(f"{prefix}.method_family_fingerprint is not canonical")
    if family is None:
        errors.append(f"{prefix}.method_family_id is not registered")
    elif family.get("requirement_id") != item.get("requirement_id"):
        errors.append(f"{prefix} method family is bound to another requirement")
    elif family.get("acceptance_outcome_id") != item.get("acceptance_outcome_id"):
        errors.append(f"{prefix} method family is bound to another acceptance outcome")
    elif family.get("method_family_fingerprint") != method_family_fingerprint:
        errors.append(f"{prefix} method family fingerprint does not match")
    elif (
        item.get("prior_method_family_id") is not None
        and family.get("prior_method_family_id") != item.get("prior_method_family_id")
    ):
        errors.append(f"{prefix} prior method-family identity does not match")
    elif family.get("status") == "stopped":
        errors.append(f"{prefix} cannot remain active in a stopped method family")
    for ref_field, fingerprint_field in (
        ("method_change_evidence_ref", "method_change_evidence_fingerprint"),
        (
            "lower_complexity_comparison_ref",
            "lower_complexity_comparison_fingerprint",
        ),
    ):
        ref = item.get(ref_field)
        fingerprint = item.get(fingerprint_field)
        if (ref is None) != (fingerprint is None):
            errors.append(
                f"{prefix}.{ref_field} and {fingerprint_field} must both be null or bound"
            )
        if ref is not None and normalize_declared_relative_path(ref) != ref:
            errors.append(f"{prefix}.{ref_field} must be normalized")
        if fingerprint is not None and not valid_fingerprint(fingerprint):
            errors.append(f"{prefix}.{fingerprint_field} must be SHA-256")
    if item.get("scope_growth") not in SCOPE_GROWTH_VALUES:
        errors.append(f"{prefix}.scope_growth is invalid")
    allowed_paths = item.get("allowed_paths")
    if not isinstance(allowed_paths, list) or any(
        normalize_declared_relative_path(path) != path for path in allowed_paths
    ):
        errors.append(f"{prefix}.allowed_paths must contain normalized project-relative paths")
    validate_tool_binding(item.get("tool_binding"), f"{prefix}.tool_binding", action_class_set, errors)
    validate_tool_claim(item.get("tool_claim"), f"{prefix}.tool_claim", errors)
    if not valid_fingerprint(item.get("progress_fingerprint_before")):
        errors.append(f"{prefix}.progress_fingerprint_before must be a SHA-256 fingerprint")
    progress_state_before = item.get("progress_state_before")
    if not isinstance(progress_state_before, dict):
        errors.append(f"{prefix}.progress_state_before must be an object")
    elif canonical_fingerprint(progress_state_before) != item.get(
        "progress_fingerprint_before"
    ):
        errors.append(
            f"{prefix}.progress_fingerprint_before must bind progress_state_before"
        )
    causal_before = item.get("causal_evidence_fingerprint_before")
    if causal_before is not None and not valid_fingerprint(causal_before):
        errors.append(
            f"{prefix}.causal_evidence_fingerprint_before must be null or SHA-256"
        )
    for name in ("action", "effect", "principal"):
        if not nonempty(item.get(name)):
            errors.append(f"{prefix}.{name} must be non-empty")
    if not valid_fingerprint(item.get("context_fingerprint")):
        errors.append(f"{prefix}.context_fingerprint must be a SHA-256 fingerprint")
    validate_utc(item.get("started_utc"), f"{prefix}.started_utc", errors)
    prerequisite_ids = item.get("prerequisite_ids")
    if not isinstance(prerequisite_ids, list):
        errors.append(f"{prefix}.prerequisite_ids must be an array")
        prerequisite_ids = []
    for prerequisite_id in prerequisite_ids:
        prerequisite = prerequisites.get(prerequisite_id)
        if prerequisite is None:
            errors.append(f"{prefix}.prerequisite_ids references unknown ID: {prerequisite_id}")
        else:
            if prerequisite.get("status") != "verified":
                errors.append(f"{prefix} uses an unverified prerequisite: {prerequisite_id}")
            if prerequisite.get("context_fingerprint") != item.get("context_fingerprint"):
                errors.append(f"{prefix} uses prerequisite {prerequisite_id} from another context")
    target_ids = item.get("target_identity_ids")
    if not isinstance(target_ids, list):
        errors.append(f"{prefix}.target_identity_ids must be an array")
        target_ids = []
    unknown_targets = sorted(set(target_ids) - identity_ids)
    if unknown_targets:
        errors.append(f"{prefix}.target_identity_ids references unknown IDs: " + ", ".join(unknown_targets))
    authorization_id = item.get("authorization_id")
    if authorization_id is not None and authorization_id not in authorizations:
        errors.append(f"{prefix}.authorization_id is unknown")
    elif authorization_id is not None:
        authorization = authorizations[authorization_id]
        if authorization.get("status") == "revoked":
            errors.append(f"{prefix}.authorization_id has been revoked")
        for field in ("action", "effect", "principal", "context_fingerprint"):
            if authorization.get(field) != item.get(field):
                errors.append(f"{prefix} no longer matches authorization {field}")
        if set(authorization.get("target_identity_ids", [])) != set(target_ids):
            errors.append(f"{prefix} no longer matches the authorized target/effect set")
    evaluation_role = item.get("evaluation_role", "none")
    evaluation_fingerprint = item.get("evaluation_fingerprint")
    if evaluation_role not in EVALUATION_ROLES:
        errors.append(f"{prefix}.evaluation_role is invalid")
    if evaluation_role == "prospective" and evaluation_fingerprint in diagnostic_fingerprints:
        errors.append(f"{prefix} cannot reuse an exposed evaluation as prospective")
    if evaluation_role == "none" and evaluation_fingerprint is not None:
        errors.append(f"{prefix}.evaluation_fingerprint must be null for role none")
    if evaluation_role != "none" and not valid_fingerprint(evaluation_fingerprint):
        errors.append(f"{prefix}.evaluation_fingerprint must be a SHA-256 fingerprint")
    stable_request = {key: item.get(key) for key in ATTEMPT_REQUEST_STABLE_FIELDS}
    if item.get("request_fingerprint") != canonical_fingerprint(stable_request):
        errors.append(f"{prefix}.request_fingerprint does not match the admitted request")


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
    stage_allowed_capability_ids: dict[str, set[str]],
    control_acceptance_ids: set[str],
    control_candidate_fingerprint: object,
    control_lineage_id: object,
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
            allowed_capability_ids = stage_allowed_capability_ids.get(stage_id, set())
            cross_stage = [
                capability_id for capability_id in capability_ids
                if capability_id not in allowed_capability_ids
            ]
            if cross_stage:
                errors.append(
                    f"{prefix}.capability_ids must belong to or be explicitly preserved by its delivery stage: "
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
            if schema_version >= 6 and requirement_id in control_acceptance_ids:
                predecessor_ids = validate_declared_ids(
                    item.get("predecessor_requirement_ids"),
                    f"{prefix}.predecessor_requirement_ids",
                    errors,
                    required=False,
                )
            else:
                predecessor_ids = []
        else:
            gate_tiers = []
            system_scope = None
            proof_path = None
            predecessor_ids = []
    else:
        capability_ids = []
        identity_ids = []
        step_ids = []
        unresolved_counterevidence = 0
        stage_id = None
        gate_tiers = []
        system_scope = None
        proof_path = None
        predecessor_ids = []
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
            require_control_binding=(
                schema_version >= 6 and requirement_id in control_acceptance_ids
            ),
            expected_candidate_fingerprint=control_candidate_fingerprint,
            expected_lineage_id=control_lineage_id,
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
        "predecessor_requirement_ids": predecessor_ids,
        "minimum_evidence_level": minimum,
        "capability_ids": capability_ids,
        "identity_ids": identity_ids,
        "acceptance_step_ids": step_ids,
        "unresolved_counterevidence": unresolved_counterevidence,
        "evidence": normalized_evidence,
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
    require_control_binding: bool,
    expected_candidate_fingerprint: object,
    expected_lineage_id: object,
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
    if require_control_binding:
        candidate_fingerprint = entry.get("candidate_fingerprint")
        lineage_id = entry.get("lineage_id")
        gate_receipt_id = entry.get("gate_receipt_id")
        if candidate_fingerprint != expected_candidate_fingerprint:
            errors.append(f"{prefix}.candidate_fingerprint must match the active candidate")
        if lineage_id != expected_lineage_id:
            errors.append(f"{prefix}.lineage_id must match the active attempt lineage")
        if not valid_requirement_id(gate_receipt_id):
            errors.append(f"{prefix}.gate_receipt_id must identify an atomic gate receipt")
        evaluation_fingerprint = entry.get("evaluation_fingerprint")
        evaluation_role = entry.get("evaluation_role", "none")
        if evaluation_role not in EVALUATION_ROLES:
            errors.append(f"{prefix}.evaluation_role must be none, diagnostic, or prospective")
        if evaluation_role == "none" and evaluation_fingerprint is not None:
            errors.append(f"{prefix}.evaluation_fingerprint must be null when evaluation_role is none")
        if evaluation_role != "none" and not valid_fingerprint(evaluation_fingerprint):
            errors.append(f"{prefix}.evaluation_fingerprint must be a SHA-256 fingerprint")
    else:
        candidate_fingerprint = None
        lineage_id = None
        gate_receipt_id = None
        evaluation_fingerprint = None
        evaluation_role = "none"
    return {
        "rank": EVIDENCE_RANKS[level],
        "ref": entry.get("ref"),
        "step_ids": step_ids,
        "identity_ids": identity_ids,
        "candidate_fingerprint": candidate_fingerprint,
        "lineage_id": lineage_id,
        "gate_receipt_id": gate_receipt_id,
        "evaluation_fingerprint": evaluation_fingerprint,
        "evaluation_role": evaluation_role,
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


def valid_fingerprint(value: object) -> bool:
    return isinstance(value, str) and bool(FINGERPRINT_PATTERN.fullmatch(value))


def positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def canonical_fingerprint(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def compact_usage_anchor(usage: object) -> dict[str, int]:
    """Keep recovery history constant-size while binding the full usage by hash."""
    item = usage if isinstance(usage, dict) else {}
    anchor = {
        field: int(item.get(field, 0))
        if nonnegative_int(item.get(field, 0))
        else 0
        for field in USAGE_ANCHOR_SCALAR_FIELDS
    }
    anchor.update(
        {
            "failure_class_count": len(item.get("failure_classes", []))
            if isinstance(item.get("failure_classes"), list)
            else 0,
            "method_family_count": len(item.get("method_families", []))
            if isinstance(item.get("method_families"), list)
            else 0,
            "path_count": len(item.get("path_counts", {}))
            if isinstance(item.get("path_counts"), dict)
            else 0,
        }
    )
    return anchor


def validate_usage_anchor(value: object, prefix: str, errors: list[str]) -> None:
    expected = set(USAGE_ANCHOR_SCALAR_FIELDS) | {
        "failure_class_count",
        "method_family_count",
        "path_count",
    }
    if not isinstance(value, dict):
        errors.append(f"{prefix} must be a compact usage object")
        return
    missing = sorted(expected - set(value))
    unknown = sorted(set(value) - expected)
    if missing:
        errors.append(f"{prefix} is missing fields: {', '.join(missing)}")
    if unknown:
        errors.append(f"{prefix} contains unknown fields: {', '.join(unknown)}")
    for field in sorted(expected):
        if not nonnegative_int(value.get(field)):
            errors.append(f"{prefix}.{field} must be a non-negative integer")


def consumed_recovery_authorization_fingerprints(
    control: object,
) -> set[str]:
    """Return every recovery authority already consumed, independent of its path."""
    if not isinstance(control, dict):
        return set()
    consumed: set[str] = set()
    for history_name in (
        "limit_extensions",
        "failure_identity_migrations",
        "state_transitions",
    ):
        history = control.get(history_name, [])
        if not isinstance(history, list):
            continue
        for record in history:
            if isinstance(record, dict) and valid_fingerprint(
                record.get("authorization_fingerprint")
            ):
                consumed.add(record["authorization_fingerprint"])
    return consumed


def canonical_tool_input_fingerprint(value: object) -> str:
    """Fingerprint the exact host-provided tool input without storing it."""
    return canonical_fingerprint(value)


def control_snapshot_root_fingerprint(root: Path) -> str:
    return canonical_fingerprint(
        {"root": os.path.normcase(str(root.expanduser().resolve()))}
    )


def control_snapshot_directory(root: Path) -> Path:
    root_hash = hashlib.sha256(
        os.path.normcase(str(root.expanduser().resolve())).encode("utf-8")
    ).hexdigest()
    # The snapshot is integrity state for this exact project, not generic host
    # scratch data.  Windows sandbox temp roots can be non-traversable across
    # the PreToolUse/PostToolUse processes, so keep it under the same
    # authoritative project state as the lock and acceptance ledger.
    return (
        root.expanduser().resolve()
        / ".codex"
        / ".outcome-integrity-control-snapshots"
        / root_hash
    )


def write_preclaim_control_snapshot(
    root: Path, acceptance_state: dict[str, Any]
) -> Path:
    """Create one exclusive pending control snapshot without raw tool input/output."""
    directory = control_snapshot_directory(root)
    if os.name == "nt":
        directory.mkdir(parents=True, exist_ok=True)
    else:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    pending = sorted(directory.glob("*.pending.json"))
    if pending:
        raise ValueError(
            "an unsettled preclaim control snapshot already exists; authoritative recovery is required"
        )
    control = acceptance_state.get("execution_control")
    if not isinstance(control, dict):
        raise ValueError("cannot snapshot state without execution_control")
    attempt = control.get("active_attempt")
    claim = attempt.get("tool_claim") if isinstance(attempt, dict) else None
    if not isinstance(attempt, dict) or not isinstance(claim, dict):
        raise ValueError("cannot snapshot control without an active claimed attempt")
    if claim.get("status") != "claimed":
        raise ValueError("cannot snapshot control before the exact claim is bound")
    state_copy = json.loads(json.dumps(acceptance_state))
    control_copy = state_copy["execution_control"]
    payload = {
        "snapshot_schema_version": 1,
        "root_fingerprint": control_snapshot_root_fingerprint(root),
        "revision": control.get("revision"),
        "attempt_id": attempt.get("id"),
        "tool_use_id": claim.get("tool_use_id"),
        "created_utc": utc_now(),
        "state_fingerprint": canonical_fingerprint(state_copy),
        "control_fingerprint": canonical_fingerprint(control_copy),
        "acceptance_state": state_copy,
        "control": control_copy,
    }
    filename = (
        f"{control.get('revision')}-{attempt.get('id')}.pending.json"
    )
    path = directory / filename
    # The root-scoped acceptance lock is already held, so atomic replacement
    # is sufficient and avoids Windows-only POSIX ACL translation on a named
    # temporary file.  A new snapshot is always private to this project root.
    atomic_write_json(path, payload)
    if os.name != "nt":
        path.chmod(0o400)
    return path


def load_preclaim_control_snapshot(
    root: Path,
) -> tuple[dict[str, Any] | None, Path | None, list[str]]:
    directory = control_snapshot_directory(root)
    pending = sorted(directory.glob("*.pending.json")) if directory.is_dir() else []
    if len(pending) != 1:
        return (
            None,
            None,
            [
                "exactly one immutable preclaim control snapshot is required before PostToolUse"
            ],
        )
    path = pending[0]
    snapshot, errors = load_json_object(path, "preclaim control snapshot")
    if errors or snapshot is None:
        return None, path, errors
    snapshot_control = snapshot.get("control")
    snapshot_state = snapshot.get("acceptance_state")
    if snapshot.get("snapshot_schema_version") != 1:
        errors.append("preclaim control snapshot schema is invalid")
    if snapshot.get("root_fingerprint") != control_snapshot_root_fingerprint(root):
        errors.append("preclaim control snapshot belongs to another project root")
    if not isinstance(snapshot_state, dict):
        errors.append("preclaim control snapshot is missing its authoritative state")
    elif snapshot.get("state_fingerprint") != canonical_fingerprint(snapshot_state):
        errors.append("preclaim authoritative state fingerprint is invalid")
    if not isinstance(snapshot_control, dict):
        errors.append("preclaim control snapshot is missing its authoritative control state")
    elif snapshot.get("control_fingerprint") != canonical_fingerprint(snapshot_control):
        errors.append("preclaim control snapshot fingerprint is invalid")
    elif isinstance(snapshot_state, dict) and snapshot_state.get(
        "execution_control"
    ) != snapshot_control:
        errors.append("preclaim control snapshot is not bound to its authoritative state")
    elif snapshot.get("revision") != snapshot_control.get("revision"):
        errors.append("preclaim control snapshot revision is inconsistent")
    else:
        attempt = snapshot_control.get("active_attempt")
        claim = attempt.get("tool_claim") if isinstance(attempt, dict) else None
        if not isinstance(attempt, dict) or not isinstance(claim, dict):
            errors.append("preclaim control snapshot has no active claimed attempt")
        else:
            if snapshot.get("attempt_id") != attempt.get("id"):
                errors.append("preclaim control snapshot attempt identity is inconsistent")
            if snapshot.get("tool_use_id") != claim.get("tool_use_id"):
                errors.append("preclaim control snapshot tool identity is inconsistent")
            if claim.get("status") != "claimed":
                errors.append("preclaim control snapshot claim is not pending observation")
    return (snapshot if not errors else None), path, errors


def clear_preclaim_control_snapshot(path: Path | None) -> None:
    if path is None or not path.exists():
        return
    if os.name != "nt":
        path.chmod(0o600)
    path.unlink()
    try:
        path.parent.rmdir()
    except OSError:
        pass


def normalize_declared_relative_path(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().replace("\\", "/")
    path = Path(normalized)
    if path.is_absolute() or ".." in path.parts:
        return None
    cleaned = path.as_posix().strip("/")
    return cleaned or "."


def cwd_relative_to_root(root: Path, value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        relative = candidate.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return None
    normalized = relative.as_posix().strip("/")
    return normalized or "."


def _tool_input_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for key in sorted(value):
            strings.extend(_tool_input_strings(value[key]))
        return strings
    if isinstance(value, list):
        strings = []
        for entry in value:
            strings.extend(_tool_input_strings(entry))
        return strings
    return []


def extract_apply_patch_paths(
    tool_name: str, tool_input: object, cwd_relative: str
) -> list[str]:
    if tool_name not in APPLY_PATCH_TOOL_NAMES:
        return []
    paths: set[str] = set()
    for source in _tool_input_strings(tool_input):
        for match in re.finditer(
            r"(?m)^\*\*\* (?:(?:Add|Update|Delete) File|Move to): (.+?)\s*$", source
        ):
            declared = normalize_declared_relative_path(match.group(1))
            if declared is None:
                continue
            combined = declared if cwd_relative == "." else f"{cwd_relative}/{declared}"
            normalized = normalize_declared_relative_path(combined)
            if normalized is not None:
                paths.add(normalized)
    return sorted(paths)


def is_control_state_path(path: str) -> bool:
    return path.casefold() in {value.casefold() for value in CONTROL_STATE_PATHS}


def _structured_target_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [
            string
            for entry in value
            for string in _structured_target_strings(entry)
        ]
    return []


def _resolved_structured_target(
    root: Path, cwd_relative: str, value: str
) -> str | None:
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        base = root if cwd_relative == "." else root / Path(cwd_relative)
        candidate = base / candidate
    try:
        relative = candidate.resolve(strict=False).relative_to(root.resolve())
    except (OSError, ValueError):
        return None
    return relative.as_posix().strip("/") or "."


def extract_control_state_targets(
    root: Path,
    tool_name: str,
    tool_input: object,
    cwd_relative: str,
    patch_paths: list[str],
) -> list[str]:
    """Find mechanically explicit control-ledger mutation targets, not mentions."""
    targets = {path for path in patch_paths if is_control_state_path(path)}

    if tool_name in SHELL_TOOL_NAMES:
        if isinstance(tool_input, dict):
            command_sources = [
                value
                for key, value in tool_input.items()
                if str(key).casefold() in {"cmd", "command", "script"}
            ]
        else:
            command_sources = [tool_input]
        for source in command_sources:
            for command in _tool_input_strings(source):
                if SHELL_CONTROL_MUTATION_PATTERN.search(
                    command
                ) or SHELL_CONTROL_REDIRECT_PATTERN.search(command):
                    for control_path in CONTROL_STATE_PATHS:
                        basename = control_path.rsplit("/", 1)[-1]
                        if re.search(
                            rf"(?i)\.codex[\\/]{re.escape(basename)}\b", command
                        ):
                            targets.add(control_path)
                if cwd_relative.casefold() == ".codex" and SHELL_CONTROL_BARE_TARGET_PATTERN.search(
                    command
                ):
                    for control_path in CONTROL_STATE_PATHS:
                        if re.search(
                            rf"(?i)(?<![A-Za-z0-9_.-]){re.escape(control_path.rsplit('/', 1)[-1])}\b",
                            command,
                        ):
                            targets.add(control_path)

    if isinstance(tool_input, dict) and tool_name not in READ_ONLY_TOOL_NAMES:
        for key, value in tool_input.items():
            if str(key).casefold() not in STRUCTURED_TARGET_KEYS:
                continue
            for declared in _structured_target_strings(value):
                resolved = _resolved_structured_target(
                    root, cwd_relative, declared
                )
                if resolved is not None and is_control_state_path(resolved):
                    targets.add(resolved)
    return sorted(targets)


def path_resolves_within_root(root: Path, relative_path: str) -> bool:
    """Reject existing symlink/junction targets or destination parents escaping root."""
    try:
        resolved_root = root.resolve()
        candidate = root / Path(relative_path)
        resolved_target = candidate.resolve() if candidate.exists() else candidate.parent.resolve()
        resolved_target.relative_to(resolved_root)
        return True
    except (OSError, ValueError):
        return False


def path_is_allowed(path: str, allowed_paths: list[str]) -> bool:
    return any(
        path == allowed or (allowed != "." and path.startswith(allowed.rstrip("/") + "/"))
        or allowed == "."
        for allowed in allowed_paths
    )


def _tool_name_tokens(tool_name: str) -> set[str]:
    return {
        token
        for token in re.split(r"[^a-z0-9]+", tool_name.casefold())
        if token
    }


def host_derived_action_classes(
    tool_name: str, tool_input: object | None = None
) -> set[str]:
    """Classify risk from host facts only; caller declarations cannot lower it."""
    if tool_name in APPLY_PATCH_TOOL_NAMES:
        return {"local"}
    if tool_name in SUBAGENT_TOOL_NAMES:
        return {"support"}
    if tool_name in SHELL_TOOL_NAMES:
        classes = {"local"}
        shell_text = "\n".join(_tool_input_strings(tool_input))
        if any(pattern.search(shell_text) for pattern in SHELL_EXTERNAL_WRITE_PATTERNS):
            classes.add("external-write")
        return classes
    if tool_name in READ_ONLY_TOOL_NAMES:
        return {"local"}

    tokens = _tool_name_tokens(tool_name)
    if tokens & EXTERNAL_WRITE_VERBS:
        classes = {"external-write"}
        if tokens & IRREVERSIBLE_TOOL_VERBS:
            classes.add("irreversible")
        return classes

    # Unknown or mixed-capability tools fail toward the bounded support lane.
    return {"support"}


def tool_is_effectful(tool_name: str, action_classes: set[str]) -> bool:
    if action_classes & {"proof", "external-write", "irreversible", "unattended"}:
        return True
    if tool_name in KNOWN_MATERIAL_TOOL_NAMES:
        return True
    return host_derived_action_classes(tool_name) != {"local"}


def derive_action_classes(
    tool_name: str, attempt: dict[str, Any], tool_input: object | None = None
) -> list[str]:
    derived = host_derived_action_classes(tool_name, tool_input)
    if attempt.get("scope_growth") in {"architecture", "operations", "custody"}:
        derived.add("support")
    return sorted(derived)


def hook_requires_claim(payload: dict[str, Any]) -> bool:
    """Return whether a host call is material enough to require atomic admission."""
    tool_name = payload.get("tool_name")
    return not (isinstance(tool_name, str) and tool_name in READ_ONLY_TOOL_NAMES)


def calculate_progress_state(
    data: dict[str, Any], requirement_id: object
) -> dict[str, Any]:
    requirement = next(
        (
            entry
            for entry in data.get("requirements", [])
            if isinstance(entry, dict) and entry.get("id") == requirement_id
        ),
        {},
    )
    control = data.get("execution_control", {})
    candidate = (
        control.get("candidate", {}).get("fingerprint")
        if isinstance(control.get("candidate"), dict)
        else None
    )
    lineage_id = (
        control.get("lineage", {}).get("id")
        if isinstance(control.get("lineage"), dict)
        else None
    )
    receipts = [
        {
            "id": entry.get("id"),
            "evidence_ref": entry.get("evidence_ref"),
            "tier": entry.get("tier"),
        }
        for entry in control.get("gate_receipts", [])
        if isinstance(entry, dict) and entry.get("requirement_id") == requirement_id
        and entry.get("candidate_fingerprint") == candidate
        and entry.get("lineage_id") == lineage_id
    ]
    evidence = [
        {
            "ref": entry.get("ref"),
            "level": entry.get("level"),
            "gate_receipt_id": entry.get("gate_receipt_id"),
        }
        for entry in requirement.get("evidence", [])
        if isinstance(entry, dict)
        and entry.get("candidate_fingerprint") == candidate
        and entry.get("lineage_id") == lineage_id
        and valid_requirement_id(entry.get("gate_receipt_id"))
    ]
    resolved_counterevidence = [
        {
            "ref": entry.get("ref"),
            "resolution": entry.get("resolution"),
        }
        for entry in requirement.get("counterevidence", [])
        if isinstance(entry, dict) and entry.get("status") == "resolved"
    ]
    blocker = requirement.get("blocker") if requirement.get("status") == "blocked" else None
    return {
        "status": requirement.get("status"),
        "blocker": blocker,
        "bound_evidence": sorted(evidence, key=lambda entry: canonical_fingerprint(entry)),
        "bound_receipts": sorted(receipts, key=lambda entry: canonical_fingerprint(entry)),
        "resolved_counterevidence": sorted(
            resolved_counterevidence, key=lambda entry: canonical_fingerprint(entry)
        ),
    }


def calculate_method_family_fingerprint(request: dict[str, Any]) -> str:
    """Derive family identity from stable method semantics, never caller labels."""
    binding = request.get("tool_binding")
    binding = binding if isinstance(binding, dict) else {}
    return canonical_fingerprint(
        {
            "requirement_id": request.get("requirement_id"),
            "acceptance_outcome_id": request.get("acceptance_outcome_id"),
            "action_classes": sorted(request.get("action_classes", [])),
            "scope_growth": request.get("scope_growth"),
            "tool_binding": {
                "tool_name": binding.get("tool_name"),
                "cwd_relative": binding.get("cwd_relative"),
            },
            "allowed_paths": sorted(request.get("allowed_paths", [])),
            "target_identity_ids": sorted(request.get("target_identity_ids", [])),
            "principal": request.get("principal"),
            "context_fingerprint": request.get("context_fingerprint"),
            "action": request.get("action"),
            "effect": request.get("effect"),
        }
    )


def calculate_progress_fingerprint(
    data: dict[str, Any], requirement_id: object
) -> str:
    """Fingerprint only acceptance/evidence state; candidate activity is excluded."""
    return canonical_fingerprint(calculate_progress_state(data, requirement_id))


def calculate_causal_evidence_fingerprint(
    root: Path, evidence_ref: object
) -> str | None:
    normalized = normalize_declared_relative_path(evidence_ref)
    if normalized is None or normalized == ".":
        return None
    path = root / Path(normalized)
    try:
        if not path.is_file():
            return None
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def progress_delta_observed(
    before: dict[str, Any],
    after: dict[str, Any],
    causal_before: object,
    causal_after: object,
) -> bool:
    """Recognize directional evidence progress, never mere candidate churn."""
    for field in ("bound_evidence", "bound_receipts", "resolved_counterevidence"):
        before_items = {
            canonical_fingerprint(entry) for entry in before.get(field, [])
        }
        after_items = {
            canonical_fingerprint(entry) for entry in after.get(field, [])
        }
        if after_items - before_items:
            return True
    status_rank = {"failing": 0, "blocked": 1, "passing": 2}
    if status_rank.get(after.get("status"), -1) > status_rank.get(
        before.get("status"), -1
    ):
        return True
    if (
        after.get("status") == "blocked"
        and after.get("blocker") is not None
        and canonical_fingerprint(after.get("blocker"))
        != canonical_fingerprint(before.get("blocker"))
    ):
        return True
    # A changed diagnostic/causal artifact may justify a replan, but is not by
    # itself acceptance progress.
    return False


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


@contextlib.contextmanager
def acceptance_lock(root: str | Path):
    resolved_root = Path(root).expanduser().resolve()
    root_identity = os.path.normcase(str(resolved_root)).encode("utf-8")
    lock_name = hashlib.sha256(root_identity).hexdigest() + ".lock"
    # Lock state remains in the authoritative project state. Windows managed
    # sandboxes can deny `msvcrt.locking` even when they allow the same process
    # to create and update the project file, so use atomic directory creation
    # as the cross-process lease primitive instead of weakening the boundary.
    lock_directory = resolved_root / ".codex" / ".outcome-integrity-locks"
    if lock_directory.is_symlink():
        raise OSError(f"lock directory is a symlink: {lock_directory}")
    if os.name == "nt":
        lock_directory.mkdir(parents=True, exist_ok=True)
    else:
        lock_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_path = lock_directory / lock_name
    if lock_path.is_symlink():
        raise OSError(f"lock file is a symlink: {lock_path}")
    lease_directory = lock_directory / f"{lock_name}.lease"
    if lease_directory.is_symlink():
        raise OSError(f"lock lease is a symlink: {lease_directory}")
    try:
        lease_directory.mkdir()
    except FileExistsError as exc:
        raise OSError(
            "an Outcome Integrity operation already holds the exact project lock; "
            "do not bypass it"
        ) from exc
    try:
        yield
    finally:
        # rmdir deliberately fails closed if a foreign child appears; deleting
        # it recursively would make a lock-ownership conflict look harmless.
        lease_directory.rmdir()


def load_json_object(path: Path, label: str) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return None, [f"cannot read {label}: {exc}"]
    except json.JSONDecodeError as exc:
        return None, [f"{label} is invalid JSON: {exc}"]
    if not isinstance(data, dict):
        return None, [f"{label} root must be an object"]
    return data, []


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def atomic_write_text(path: Path, text_value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(text_value)
            if not text_value.endswith("\n"):
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def attempt_begin(
    root: str | Path, request_path: str | Path, expected_revision: int
) -> dict[str, object]:
    project_path, acceptance_path = project_paths(root)
    resolved_root = project_path.parent.parent
    request, request_errors = load_json_object(Path(request_path).expanduser().resolve(), "attempt request")
    if request_errors:
        return {"ok": False, "command": "attempt-begin", "errors": request_errors}
    try:
        with acceptance_lock(resolved_root):
            resume = validate(resolved_root, mode="admit")
            if not resume["ok"]:
                return {
                    "ok": False,
                    "command": "attempt-begin",
                    "errors": ["resume/admission gate failed", *resume["errors"]],
                }
            data, errors = load_json_object(acceptance_path, "ACCEPTANCE.json")
            if errors or data is None:
                return {"ok": False, "command": "attempt-begin", "errors": errors}
            if data.get("schema_version") != CURRENT_SCHEMA_VERSION:
                return {
                    "ok": False,
                    "command": "attempt-begin",
                    "errors": [f"attempt admission requires schema version {CURRENT_SCHEMA_VERSION}"],
                }
            control = data["execution_control"]
            if control.get("revision") != expected_revision:
                return {
                    "ok": False,
                    "command": "attempt-begin",
                    "errors": [
                        f"stale expected revision {expected_revision}; current revision is {control.get('revision')}"
                    ],
                }
            if control.get("status") != "ready" or control.get("active_attempt") is not None:
                return {
                    "ok": False,
                    "command": "attempt-begin",
                    "errors": [f"execution control is {control.get('status')}; no new attempt is admissible"],
                }
            request_errors = validate_attempt_request(
                data, request or {}, utc_now(), resolved_root
            )
            if request_errors:
                return {"ok": False, "command": "attempt-begin", "errors": request_errors}

            usage = control["usage"]
            limits = control["limits"]
            projected = {
                "total_attempts": usage["total_attempts"] + 1,
                "expensive_attempts": usage["expensive_attempts"]
                + (1 if request["cost_class"] == "expensive" else 0),
                "support_attempts": usage["support_attempts"]
                + (1 if "support" in request["action_classes"] else 0),
            }
            exhausted = [
                field
                for field, value in projected.items()
                if value > limits[field]
            ]
            if usage["active_attempt_seconds"] >= limits["active_attempt_seconds"]:
                exhausted.append("active_attempt_seconds")
            if exhausted:
                control["status"] = "stopped"
                control["stop_reason"] = "attempt admission exhausted: " + ", ".join(exhausted)
                control["revision"] += 1
                atomic_write_json(acceptance_path, data)
                return {
                    "ok": False,
                    "command": "attempt-begin",
                    "revision": control["revision"],
                    "errors": [control["stop_reason"]],
                }

            for field, value in projected.items():
                usage[field] = value
            method_family_fingerprint = calculate_method_family_fingerprint(request)
            method_change_evidence_fingerprint = (
                calculate_causal_evidence_fingerprint(
                    resolved_root, request.get("method_change_evidence_ref")
                )
                if request.get("method_change_evidence_ref") is not None
                else None
            )
            lower_complexity_comparison_fingerprint = (
                calculate_causal_evidence_fingerprint(
                    resolved_root,
                    request.get("lower_complexity_comparison_ref"),
                )
                if request.get("lower_complexity_comparison_ref") is not None
                else None
            )
            family = next(
                (
                    entry
                    for entry in usage["method_families"]
                    if entry.get("id") == request["method_family_id"]
                ),
                None,
            )
            if family is None:
                family = {
                    "id": request["method_family_id"],
                    "requirement_id": request["requirement_id"],
                    "acceptance_outcome_id": request["acceptance_outcome_id"],
                    "method_family_fingerprint": method_family_fingerprint,
                    "prior_method_family_id": request.get(
                        "prior_method_family_id"
                    ),
                    "method_change_evidence_ref": request.get(
                        "method_change_evidence_ref"
                    ),
                    "method_change_evidence_fingerprint": (
                        method_change_evidence_fingerprint
                    ),
                    "lower_complexity_comparison_ref": request.get(
                        "lower_complexity_comparison_ref"
                    ),
                    "lower_complexity_comparison_fingerprint": (
                        lower_complexity_comparison_fingerprint
                    ),
                    "stop_evidence_fingerprints": [],
                    "failed_attempts": 0,
                    "no_progress_attempts": 0,
                    "failures": [],
                    "status": "active",
                    "stop_reason": None,
                }
                usage["method_families"].append(family)
            authorization_id = request.get("authorization_id")
            if authorization_id is not None:
                authorization = next(
                    entry
                    for entry in control["authorizations"]
                    if entry["id"] == authorization_id
                )
                authorization["uses_remaining"] -= 1
                if authorization["uses_remaining"] == 0:
                    authorization["status"] = "consumed"

            next_revision = control["revision"] + 1
            attempt_id = f"ATTEMPT-{next_revision:06d}"
            stable_request = {
                key: request.get(key) for key in ATTEMPT_REQUEST_STABLE_FIELDS
            }
            progress_state_before = calculate_progress_state(
                data, request["requirement_id"]
            )
            control["active_attempt"] = {
                "id": attempt_id,
                "lineage_id": control["lineage"]["id"],
                "scope_fingerprint": control["lineage"]["scope_fingerprint"],
                "reconciled_utc": data["updated_utc"],
                **stable_request,
                "method_family_fingerprint": method_family_fingerprint,
                "method_change_evidence_fingerprint": (
                    method_change_evidence_fingerprint
                ),
                "lower_complexity_comparison_fingerprint": (
                    lower_complexity_comparison_fingerprint
                ),
                "request_fingerprint": canonical_fingerprint(stable_request),
                "external_run_id": request.get("external_run_id"),
                "started_utc": utc_now(),
                "candidate_fingerprint_after": None,
                "progress_state_before": progress_state_before,
                "progress_fingerprint_before": canonical_fingerprint(
                    progress_state_before
                ),
                "causal_evidence_fingerprint_before": (
                    calculate_causal_evidence_fingerprint(
                        resolved_root, request.get("causal_evidence_ref")
                    )
                ),
                "tool_claim": {
                    "status": "unclaimed",
                    "tool_use_id": None,
                    "claimed_utc": None,
                    "observed_utc": None,
                    "outcome": None,
                    "actual_tool_name": None,
                    "actual_cwd_relative": None,
                    "actual_tool_input_fingerprint": None,
                    "progress_observed": None,
                    "causal_evidence_fingerprint_after": None,
                    "charged_active_attempt_seconds": None,
                    "time_budget_overrun": None,
                    "derived_action_classes": [],
                    "path_touches": [],
                    "hot_path_touches": 0,
                },
            }
            control["status"] = "running"
            control["stop_reason"] = None
            control["revision"] = next_revision
            atomic_write_json(acceptance_path, data)
            return {
                "ok": True,
                "command": "attempt-begin",
                "revision": next_revision,
                "attempt": control["active_attempt"],
            }
    except (OSError, ValueError) as exc:
        return {"ok": False, "command": "attempt-begin", "errors": [str(exc)]}


def validate_attempt_request(
    data: dict[str, Any], request: dict[str, Any], now_utc: str, root: Path
) -> list[str]:
    errors: list[str] = []
    control = data["execution_control"]
    if data.get("project_state") != "active":
        errors.append("attempt admission requires project_state active")
    requirements = {
        item["id"]: item for item in data.get("requirements", []) if isinstance(item, dict)
    }
    requirement_id = request.get("requirement_id")
    requirement = requirements.get(requirement_id)
    if not requirement:
        errors.append("attempt request requirement_id is unknown")
        return errors
    if requirement.get("status") != "failing":
        errors.append("attempt request requirement must be failing, not blocked or passing")
    if data.get("current_slice_requirement_id") != requirement_id:
        errors.append("attempt request must target current_slice_requirement_id")
    if requirement_id not in control["lineage"]["acceptance_ids"]:
        errors.append("attempt request must target the active attempt lineage")
    tier = request.get("tier")
    if tier not in requirement.get("gate_tiers", []):
        errors.append("attempt request tier is not declared by its requirement")
    if request.get("candidate_fingerprint") != control["candidate"]["fingerprint"]:
        errors.append("attempt request candidate_fingerprint is stale or mismatched")
    if request.get("cost_class") not in COST_CLASSES:
        errors.append("attempt request cost_class must be cheap or expensive")
    action_classes = request.get("action_classes")
    if not isinstance(action_classes, list) or not action_classes or any(
        action not in ACTION_CLASSES for action in action_classes
    ):
        errors.append("attempt request action_classes must be a non-empty valid array")
        action_classes = []
    for field in ("method_family_id", "acceptance_outcome_id", "boundary_id"):
        if not valid_requirement_id(request.get(field)):
            errors.append(f"attempt request {field} must be a structured ID")
    hierarchy = data.get("outcome_hierarchy")
    north_star = hierarchy.get("north_star") if isinstance(hierarchy, dict) else {}
    north_star_id = north_star.get("id") if isinstance(north_star, dict) else None
    if request.get("acceptance_outcome_id") != north_star_id:
        errors.append(
            "attempt request acceptance_outcome_id must equal the live north-star outcome"
        )
    for field in (
        "prior_method_family_id",
        "method_change_evidence_ref",
        "lower_complexity_comparison_ref",
    ):
        if field not in request:
            errors.append(f"attempt request must declare {field}, using null when initial")
    method_family_entries = [
        entry
        for entry in control.get("usage", {}).get("method_families", [])
        if isinstance(entry, dict)
    ]
    method_families = {
        entry.get("id"): entry
        for entry in method_family_entries
    }
    method_family_fingerprint = calculate_method_family_fingerprint(request)
    family = method_families.get(request.get("method_family_id"))
    relabeled_family = next(
        (
            entry
            for entry in method_families.values()
            if entry.get("method_family_fingerprint") == method_family_fingerprint
            and entry.get("id") != request.get("method_family_id")
        ),
        None,
    )
    if relabeled_family is not None:
        errors.append(
            "fresh method_family_id cannot relabel canonical family "
            + str(relabeled_family.get("id"))
        )
    if family is not None:
        if family.get("requirement_id") != requirement_id:
            errors.append("attempt method family is bound to another requirement")
        if family.get("acceptance_outcome_id") != request.get("acceptance_outcome_id"):
            errors.append("attempt method family is bound to another acceptance outcome")
        if family.get("method_family_fingerprint") != method_family_fingerprint:
            errors.append("attempt changed the semantics of an existing method family")
        if family.get("status") == "stopped":
            errors.append("attempt method family is stopped")
        if any(
            request.get(field) is not None
            for field in (
                "prior_method_family_id",
                "method_change_evidence_ref",
                "lower_complexity_comparison_ref",
            )
        ):
            errors.append(
                "continuing an existing method family cannot declare recovery-change evidence"
            )
    else:
        sibling_families = [
            entry
            for entry in method_family_entries
            if entry.get("requirement_id") == requirement_id
        ]
        active_siblings = [
            entry for entry in sibling_families if entry.get("status") == "active"
        ]
        if active_siblings:
            errors.append(
                "a new method family cannot abandon an active method family before its breaker fires"
            )
        if len(sibling_families) >= MAX_METHOD_FAMILIES_PER_PARENT:
            errors.append(
                "the permanent replacement-family limit is reached for this acceptance requirement"
            )
        stopped_families = [
            entry
            for entry in sibling_families
            if entry.get("status") == "stopped"
        ]
        recovery_fields = (
            request.get("prior_method_family_id"),
            request.get("method_change_evidence_ref"),
            request.get("lower_complexity_comparison_ref"),
        )
        if not stopped_families:
            if any(value is not None for value in recovery_fields):
                errors.append(
                    "an initial method family requires null recovery-change fields"
                )
        else:
            prior_family_id = request.get("prior_method_family_id")
            latest_stopped_family = stopped_families[-1]
            prior_family = (
                latest_stopped_family
                if latest_stopped_family.get("id") == prior_family_id
                else None
            )
            if prior_family is None:
                errors.append(
                    "a new method after a breaker must name the most recent stopped prior_method_family_id"
                )
            change_ref = request.get("method_change_evidence_ref")
            comparison_ref = request.get("lower_complexity_comparison_ref")
            normalized_change = normalize_declared_relative_path(change_ref)
            normalized_comparison = normalize_declared_relative_path(comparison_ref)
            if normalized_change != change_ref or normalized_comparison != comparison_ref:
                errors.append(
                    "method-change and lower-complexity evidence refs must be normalized project-relative files"
                )
            if change_ref == comparison_ref:
                errors.append(
                    "method-change evidence and lower-complexity comparison must be distinct files"
                )
            change_fingerprint = calculate_causal_evidence_fingerprint(root, change_ref)
            comparison_fingerprint = calculate_causal_evidence_fingerprint(
                root, comparison_ref
            )
            if not valid_fingerprint(change_fingerprint) or not valid_fingerprint(
                comparison_fingerprint
            ):
                errors.append(
                    "method-change and lower-complexity evidence files must both exist and hash"
                )
            elif change_fingerprint == comparison_fingerprint:
                errors.append(
                    "method-change evidence and lower-complexity comparison must have distinct content"
                )
            if prior_family is not None:
                prior_stop_evidence = set(
                    prior_family.get("stop_evidence_fingerprints", [])
                )
                stale = sorted(
                    fingerprint
                    for fingerprint in (
                        change_fingerprint,
                        comparison_fingerprint,
                    )
                    if valid_fingerprint(fingerprint)
                    and fingerprint in prior_stop_evidence
                )
                if stale:
                    errors.append(
                        "method recovery evidence is not fresh from the prior stop"
                    )
    scope_growth = request.get("scope_growth")
    if scope_growth not in SCOPE_GROWTH_VALUES:
        errors.append("attempt request scope_growth is invalid")
    allowed_paths = request.get("allowed_paths")
    if not isinstance(allowed_paths, list):
        errors.append("attempt request allowed_paths must be an array")
        allowed_paths = []
    else:
        normalized_allowed = [normalize_declared_relative_path(path) for path in allowed_paths]
        if any(value is None for value in normalized_allowed) or normalized_allowed != allowed_paths:
            errors.append("attempt request allowed_paths must contain normalized project-relative paths")
        if len(set(allowed_paths)) != len(allowed_paths):
            errors.append("attempt request allowed_paths must not contain duplicates")
    tool_binding = validate_tool_binding(
        request.get("tool_binding"),
        "attempt request tool_binding",
        set(action_classes),
        errors,
    )
    required_action_classes = set(
        derive_action_classes(str(tool_binding.get("tool_name", "")), request)
    )
    undeclared_action_classes = sorted(required_action_classes - set(action_classes))
    if undeclared_action_classes:
        errors.append(
            "attempt request cannot lower host-derived action classes: "
            + ", ".join(undeclared_action_classes)
        )
    if tool_binding.get("tool_name") in APPLY_PATCH_TOOL_NAMES and not allowed_paths:
        errors.append("apply_patch admission requires at least one allowed path")
    for field in ("action", "effect", "principal"):
        if not nonempty(request.get(field)):
            errors.append(f"attempt request {field} must be non-empty")
    context_fingerprint = request.get("context_fingerprint")
    if not valid_fingerprint(context_fingerprint):
        errors.append("attempt request context_fingerprint must be a SHA-256 fingerprint")
    causal_evidence_ref = request.get("causal_evidence_ref")
    if causal_evidence_ref is not None and normalize_declared_relative_path(
        causal_evidence_ref
    ) != causal_evidence_ref:
        errors.append(
            "attempt request causal_evidence_ref must be null or a normalized project-relative file"
        )
    if "proof" in set(action_classes) and not nonempty(causal_evidence_ref):
        errors.append(
            "proof attempt requires a declared project-relative causal_evidence_ref"
        )
    target_ids = request.get("target_identity_ids")
    if not isinstance(target_ids, list):
        errors.append("attempt request target_identity_ids must be an array")
        target_ids = []
    known_identity_ids = {
        item.get("id") for item in data.get("identity_requirements", []) if isinstance(item, dict)
    }
    unknown_targets = sorted(set(target_ids) - known_identity_ids)
    if unknown_targets:
        errors.append("attempt request targets unknown identities: " + ", ".join(unknown_targets))

    evaluation_role = request.get("evaluation_role", "none")
    evaluation_fingerprint = request.get("evaluation_fingerprint")
    if evaluation_role not in EVALUATION_ROLES:
        errors.append("attempt request evaluation_role is invalid")
    if evaluation_role == "none" and evaluation_fingerprint is not None:
        errors.append("evaluation_fingerprint must be null when evaluation_role is none")
    if evaluation_role != "none" and not valid_fingerprint(evaluation_fingerprint):
        errors.append("attempt request evaluation_fingerprint must be a SHA-256 fingerprint")
    if (
        evaluation_role == "prospective"
        and evaluation_fingerprint in control["diagnostic_evaluation_fingerprints"]
    ):
        errors.append("an exposed evaluation cannot be reused as prospective evidence")

    receipts = control["gate_receipts"]
    receipt_pairs = {
        (receipt.get("requirement_id"), receipt.get("candidate_fingerprint"))
        for receipt in receipts
    }
    missing_predecessors = [
        predecessor_id
        for predecessor_id in requirement.get("predecessor_requirement_ids", [])
        if (predecessor_id, control["candidate"]["fingerprint"]) not in receipt_pairs
    ]
    if missing_predecessors:
        errors.append(
            "same-candidate predecessor receipts are missing: "
            + ", ".join(missing_predecessors)
        )

    prerequisite_ids = request.get("prerequisite_ids")
    no_prerequisites_reason = request.get("no_prerequisites_reason")
    if not isinstance(prerequisite_ids, list):
        errors.append("attempt request prerequisite_ids must be an array")
        prerequisite_ids = []
    if bool(prerequisite_ids) == bool(nonempty(no_prerequisites_reason)):
        errors.append(
            "attempt request must provide prerequisite_ids or a specific no_prerequisites_reason, not both"
        )
    prerequisites = {
        item["id"]: item for item in control["prerequisites"] if isinstance(item, dict)
    }
    applicable = {
        item_id
        for item_id, item in prerequisites.items()
        if requirement_id in item.get("requirement_ids", [])
        and bool(set(action_classes) & set(item.get("action_classes", [])))
        and (not item.get("gate_tiers") or tier in item.get("gate_tiers", []))
    }
    missing_declared = sorted(applicable - set(prerequisite_ids))
    if missing_declared:
        errors.append("required downstream prerequisites are omitted: " + ", ".join(missing_declared))
    for prerequisite_id in prerequisite_ids:
        prerequisite = prerequisites.get(prerequisite_id)
        if not prerequisite:
            errors.append(f"attempt request references unknown prerequisite: {prerequisite_id}")
            continue
        if prerequisite.get("status") != "verified":
            errors.append(f"prerequisite {prerequisite_id} is not verified")
        if prerequisite.get("context_fingerprint") != context_fingerprint:
            errors.append(f"prerequisite {prerequisite_id} was verified in a different context")
        expires = prerequisite.get("expires_utc")
        if expires is not None and parse_utc(expires) <= parse_utc(now_utc):
            errors.append(f"prerequisite {prerequisite_id} has expired")

    requires_authorization = bool(
        set(action_classes) & {"external-write", "irreversible", "unattended"}
        or scope_growth in {"operations", "custody"}
    )
    authorization_id = request.get("authorization_id")
    if requires_authorization and authorization_id is None:
        errors.append(
            "external, irreversible, unattended, operations, or custody effects require exact authorization"
        )
    if authorization_id is not None:
        authorizations = {
            item["id"]: item for item in control["authorizations"] if isinstance(item, dict)
        }
        authorization = authorizations.get(authorization_id)
        if not authorization:
            errors.append("attempt request authorization_id is unknown")
        else:
            if authorization.get("status") != "active" or authorization.get("uses_remaining", 0) < 1:
                errors.append("attempt authorization is not active")
            if parse_utc(authorization["expires_utc"]) <= parse_utc(now_utc):
                errors.append("attempt authorization has expired")
            for field in ("action", "effect", "principal", "context_fingerprint"):
                if authorization.get(field) != request.get(field):
                    errors.append(f"attempt authorization {field} does not match exactly")
            if set(authorization.get("target_identity_ids", [])) != set(target_ids):
                errors.append("attempt authorization target/effect set does not match exactly")
    elif target_ids and requires_authorization:
        errors.append("target identities cannot be acted on without exact authorization")
    return errors


def hook_pre_claim(root: str | Path, payload: dict[str, Any]) -> dict[str, object]:
    """Atomically bind one real host tool call to the active attempt."""
    if not hook_requires_claim(payload):
        return {
            "ok": True,
            "command": "hook-pre-claim",
            "decision": "bypass",
            "requires_claim": False,
        }
    project_path, acceptance_path = project_paths(root)
    resolved_root = project_path.parent.parent
    try:
        with acceptance_lock(resolved_root):
            current = validate(resolved_root, mode="admit")
            if not current["ok"]:
                return {
                    "ok": False,
                    "command": "hook-pre-claim",
                    "decision": "deny",
                    "errors": ["current control state is invalid", *current["errors"]],
                }
            data, errors = load_json_object(acceptance_path, "ACCEPTANCE.json")
            if errors or data is None:
                return {
                    "ok": False,
                    "command": "hook-pre-claim",
                    "decision": "deny",
                    "errors": errors,
                }
            control = data.get("execution_control", {})
            attempt = control.get("active_attempt")
            if control.get("status") != "running" or not isinstance(attempt, dict):
                return {
                    "ok": False,
                    "command": "hook-pre-claim",
                    "decision": "deny",
                    "errors": ["material tool call has no active atomic attempt"],
                }
            tool_use_id = payload.get("tool_use_id")
            tool_name = payload.get("tool_name")
            if not nonempty(tool_use_id) or not nonempty(tool_name) or "tool_input" not in payload:
                return {
                    "ok": False,
                    "command": "hook-pre-claim",
                    "decision": "deny",
                    "errors": ["hook payload requires tool_use_id, tool_name, cwd, and tool_input"],
                }
            actual_cwd = cwd_relative_to_root(resolved_root, payload.get("cwd"))
            if actual_cwd is None:
                return {
                    "ok": False,
                    "command": "hook-pre-claim",
                    "decision": "deny",
                    "errors": ["tool cwd is outside the exact project root"],
                }
            now = utc_now()
            elapsed = (parse_utc(now) - parse_utc(attempt["started_utc"])).total_seconds()
            remaining_active_seconds = (
                control["limits"]["active_attempt_seconds"]
                - control["usage"]["active_attempt_seconds"]
            )
            if remaining_active_seconds <= 0 or elapsed >= remaining_active_seconds:
                return {
                    "ok": False,
                    "command": "hook-pre-claim",
                    "decision": "deny",
                    "errors": [
                        "project-cumulative active-attempt time budget expired before the tool call"
                    ],
                }
            claim = attempt.get("tool_claim")
            if not isinstance(claim, dict) or claim.get("status") != "unclaimed":
                return {
                    "ok": False,
                    "command": "hook-pre-claim",
                    "decision": "deny",
                    "errors": ["the single-use tool binding has already been claimed"],
                }
            binding = attempt.get("tool_binding", {})
            actual_input_fingerprint = canonical_tool_input_fingerprint(payload["tool_input"])
            mismatches: list[str] = []
            if binding.get("tool_name") != tool_name:
                mismatches.append("tool_name")
            if binding.get("cwd_relative") != actual_cwd:
                mismatches.append("cwd")
            bound_input = binding.get("tool_input_fingerprint")
            if bound_input is not None and bound_input != actual_input_fingerprint:
                mismatches.append("tool_input")
            if mismatches:
                return {
                    "ok": False,
                    "command": "hook-pre-claim",
                    "decision": "deny",
                    "errors": ["actual tool call differs from its admission: " + ", ".join(mismatches)],
                }

            derived = derive_action_classes(str(tool_name), attempt, payload["tool_input"])
            undeclared = sorted(set(derived) - set(attempt.get("action_classes", [])))
            if undeclared:
                return {
                    "ok": False,
                    "command": "hook-pre-claim",
                    "decision": "deny",
                    "errors": [
                        "actual tool risk exceeds its admission: " + ", ".join(undeclared)
                    ],
                }

            requires_authorization = bool(
                (set(derived) | set(attempt.get("action_classes", [])))
                & {"external-write", "irreversible", "unattended"}
                or attempt.get("scope_growth") in {"operations", "custody"}
            )
            if requires_authorization:
                authorization = next(
                    (
                        entry
                        for entry in control.get("authorizations", [])
                        if isinstance(entry, dict)
                        and entry.get("id") == attempt.get("authorization_id")
                    ),
                    None,
                )
                authorization_errors: list[str] = []
                if authorization is None:
                    authorization_errors.append("exact authorization is missing at tool claim")
                else:
                    if authorization.get("status") == "revoked":
                        authorization_errors.append("authorization was revoked before tool claim")
                    if parse_utc(authorization["expires_utc"]) <= parse_utc(now):
                        authorization_errors.append("authorization expired before tool claim")
                    for field in ("action", "effect", "principal", "context_fingerprint"):
                        if authorization.get(field) != attempt.get(field):
                            authorization_errors.append(
                                f"authorization {field} no longer matches the exact admission"
                            )
                    if set(authorization.get("target_identity_ids", [])) != set(
                        attempt.get("target_identity_ids", [])
                    ):
                        authorization_errors.append(
                            "authorization target/effect set no longer matches the exact admission"
                        )
                if authorization_errors:
                    return {
                        "ok": False,
                        "command": "hook-pre-claim",
                        "decision": "deny",
                        "errors": authorization_errors,
                    }
            is_support = "support" in derived
            usage = control["usage"]
            limits = control["limits"]
            if is_support and control.get("support_stop_reason") is not None:
                return {
                    "ok": False,
                    "command": "hook-pre-claim",
                    "decision": "deny",
                    "errors": [control["support_stop_reason"]],
                }
            projected_total = usage["total_tool_calls"] + 1
            if projected_total > limits["total_tool_calls"]:
                return {
                    "ok": False,
                    "command": "hook-pre-claim",
                    "decision": "deny",
                    "errors": ["project-cumulative tool-call limit exhausted"],
                }
            if is_support and projected_total > (
                limits["total_tool_calls"] - limits["direct_delivery_reserved_calls"]
            ):
                return {
                    "ok": False,
                    "command": "hook-pre-claim",
                    "decision": "deny",
                    "errors": ["support cannot consume the direct-delivery reserve"],
                }
            projected_support = usage["support_tool_calls"] + (1 if is_support else 0)
            if projected_support > limits["support_tool_calls"]:
                return {
                    "ok": False,
                    "command": "hook-pre-claim",
                    "decision": "deny",
                    "errors": ["project-cumulative support tool-call limit exhausted"],
                }
            is_subagent = str(tool_name) in SUBAGENT_TOOL_NAMES
            projected_workers = usage["spawned_workers"] + (1 if is_subagent else 0)
            if projected_workers > limits["spawned_workers"]:
                return {
                    "ok": False,
                    "command": "hook-pre-claim",
                    "decision": "deny",
                    "errors": ["project-cumulative spawned-worker limit exhausted"],
                }
            grows_scope = attempt.get("scope_growth") != "none"
            projected_scope = usage["scope_growth_actions"] + (1 if grows_scope else 0)
            if projected_scope > limits["scope_growth_actions"]:
                return {
                    "ok": False,
                    "command": "hook-pre-claim",
                    "decision": "deny",
                    "errors": ["project-cumulative scope-growth limit exhausted"],
                }

            touched_paths = extract_apply_patch_paths(
                str(tool_name), payload["tool_input"], actual_cwd
            )
            control_state_targets = extract_control_state_targets(
                resolved_root,
                str(tool_name),
                payload["tool_input"],
                actual_cwd,
                touched_paths,
            )
            if control_state_targets:
                return {
                    "ok": False,
                    "command": "hook-pre-claim",
                    "decision": "deny",
                    "errors": [
                        "direct control-state mutation is forbidden; use state-reconcile: "
                        + ", ".join(control_state_targets)
                    ],
                }
            if str(tool_name) in APPLY_PATCH_TOOL_NAMES:
                if not touched_paths:
                    return {
                        "ok": False,
                        "command": "hook-pre-claim",
                        "decision": "deny",
                        "errors": ["apply_patch call has no mechanically detectable target path"],
                    }
                disallowed = [
                    path
                    for path in touched_paths
                    if not path_is_allowed(path, attempt.get("allowed_paths", []))
                ]
                if disallowed:
                    return {
                        "ok": False,
                        "command": "hook-pre-claim",
                        "decision": "deny",
                        "errors": ["apply_patch targets paths outside admission: " + ", ".join(disallowed)],
                    }
                escaped = [
                    path
                    for path in touched_paths
                    if not path_resolves_within_root(resolved_root, path)
                ]
                if escaped:
                    return {
                        "ok": False,
                        "command": "hook-pre-claim",
                        "decision": "deny",
                        "errors": [
                            "apply_patch target resolves outside the project root: "
                            + ", ".join(escaped)
                        ],
                    }

            path_counts = usage["path_counts"]
            projected_path_touches = usage["path_touches"] + len(touched_paths)
            if projected_path_touches > limits["max_path_touches"]:
                return {
                    "ok": False,
                    "command": "hook-pre-claim",
                    "decision": "deny",
                    "errors": ["project-cumulative path-touch limit exhausted"],
                }
            over_hot_paths = sorted(
                path
                for path in touched_paths
                if path_counts.get(path, 0) + 1 > limits["max_touches_per_path"]
            )
            if over_hot_paths:
                return {
                    "ok": False,
                    "command": "hook-pre-claim",
                    "decision": "deny",
                    "errors": [
                        "project-cumulative per-path touch limit exhausted: "
                        + ", ".join(over_hot_paths)
                    ],
                }
            hot_touches = sum(1 for path in touched_paths if path_counts.get(path, 0) > 0)
            for path in touched_paths:
                path_counts[path] = path_counts.get(path, 0) + 1
            usage["total_tool_calls"] = projected_total
            usage["support_tool_calls"] = projected_support
            usage["spawned_workers"] = projected_workers
            usage["scope_growth_actions"] = projected_scope
            usage["path_touches"] += len(touched_paths)
            usage["hot_path_touches"] += hot_touches
            if is_support and projected_support >= limits["support_tool_calls"]:
                control["support_stop_reason"] = "support tool-call limit reached; direct delivery reserve remains"
            claim.update(
                {
                    "status": "claimed",
                    "tool_use_id": tool_use_id,
                    "claimed_utc": now,
                    "actual_tool_name": tool_name,
                    "actual_cwd_relative": actual_cwd,
                    "actual_tool_input_fingerprint": actual_input_fingerprint,
                    "derived_action_classes": derived,
                    "path_touches": touched_paths,
                    "hot_path_touches": hot_touches,
                }
            )
            control["revision"] += 1
            snapshot_path: Path | None = None
            try:
                snapshot_path = write_preclaim_control_snapshot(
                    resolved_root, data
                )
                atomic_write_json(acceptance_path, data)
            except (OSError, ValueError):
                clear_preclaim_control_snapshot(snapshot_path)
                raise
            return {
                "ok": True,
                "command": "hook-pre-claim",
                "decision": "allow",
                "revision": control["revision"],
                "attempt_id": attempt["id"],
                "tool_use_id": tool_use_id,
                "derived_action_classes": derived,
                "counters": {
                    field: usage[field]
                    for field in (
                        "total_tool_calls",
                        "support_tool_calls",
                        "spawned_workers",
                        "scope_growth_actions",
                        "path_touches",
                        "hot_path_touches",
                    )
                },
            }
    except (OSError, ValueError) as exc:
        return {
            "ok": False,
            "command": "hook-pre-claim",
            "decision": "deny",
            "errors": [str(exc)],
        }


def hook_post_observe(root: str | Path, payload: dict[str, Any]) -> dict[str, object]:
    """Settle the exact claimed call without persisting its response body."""
    if not hook_requires_claim(payload):
        return {
            "ok": True,
            "command": "hook-post-observe",
            "decision": "bypass",
            "requires_claim": False,
        }
    project_path, acceptance_path = project_paths(root)
    resolved_root = project_path.parent.parent
    try:
        with acceptance_lock(resolved_root):
            snapshot, snapshot_path, snapshot_errors = load_preclaim_control_snapshot(
                resolved_root
            )
            if snapshot_errors or snapshot is None:
                return {
                    "ok": False,
                    "command": "hook-post-observe",
                    "decision": "deny",
                    "errors": snapshot_errors,
                }
            data, state_read_errors = load_json_object(
                acceptance_path, "ACCEPTANCE.json"
            )
            snapshot_control = snapshot["control"]
            state_drift = bool(
                state_read_errors
                or data is None
                or canonical_fingerprint(data) != snapshot.get("state_fingerprint")
            )
            if state_drift:
                data = json.loads(json.dumps(snapshot["acceptance_state"]))
                restored_control = json.loads(json.dumps(snapshot_control))
                restored_attempt = restored_control.get("active_attempt")
                restored_claim = (
                    restored_attempt.get("tool_claim")
                    if isinstance(restored_attempt, dict)
                    else {}
                )
                restored_control["last_integrity_incident"] = {
                    "attempt_id": (
                        restored_attempt.get("id")
                        if isinstance(restored_attempt, dict)
                        else snapshot.get("attempt_id")
                    ),
                    "tool_use_id": restored_claim.get(
                        "tool_use_id", snapshot.get("tool_use_id")
                    ),
                    "detected_utc": utc_now(),
                    "reason": "authoritative state drift between PreToolUse and PostToolUse",
                }
                restored_control["active_attempt"] = None
                restored_control["status"] = "stopped"
                restored_control["stop_reason"] = (
                    "authoritative state drift detected after the claimed tool call; "
                    "state-reconcile recovery is required"
                )
                restored_control["revision"] = int(snapshot["revision"]) + 1
                data["execution_control"] = restored_control
                atomic_write_json(acceptance_path, data)
                try:
                    clear_preclaim_control_snapshot(snapshot_path)
                except OSError:
                    pass
                return {
                    "ok": False,
                    "command": "hook-post-observe",
                    "decision": "deny",
                    "revision": restored_control["revision"],
                    "status": "stopped",
                    "errors": [restored_control["stop_reason"]],
                }
            control = data.get("execution_control", {})
            attempt = control.get("active_attempt")
            if control.get("status") != "running" or not isinstance(attempt, dict):
                return {
                    "ok": False,
                    "command": "hook-post-observe",
                    "decision": "deny",
                    "errors": ["there is no active claimed attempt to observe"],
                }
            claim = attempt.get("tool_claim")
            if not isinstance(claim, dict) or claim.get("status") != "claimed":
                return {
                    "ok": False,
                    "command": "hook-post-observe",
                    "decision": "deny",
                    "errors": ["the exact tool call is not awaiting PostToolUse"],
                }
            required = ("tool_use_id", "tool_name", "cwd", "tool_input", "outcome")
            if any(field not in payload for field in required):
                return {
                    "ok": False,
                    "command": "hook-post-observe",
                    "decision": "deny",
                    "errors": ["PostToolUse payload is incomplete"],
                }
            actual_cwd = cwd_relative_to_root(resolved_root, payload.get("cwd"))
            actual_input_fingerprint = canonical_tool_input_fingerprint(payload.get("tool_input"))
            mismatches: list[str] = []
            if payload.get("tool_use_id") != claim.get("tool_use_id"):
                mismatches.append("tool_use_id")
            if payload.get("tool_name") != claim.get("actual_tool_name"):
                mismatches.append("tool_name")
            if actual_cwd != claim.get("actual_cwd_relative"):
                mismatches.append("cwd")
            if actual_input_fingerprint != claim.get("actual_tool_input_fingerprint"):
                mismatches.append("tool_input")
            if payload.get("outcome") not in TOOL_OBSERVATION_OUTCOMES:
                mismatches.append("outcome")
            duration = payload.get("duration_seconds", 0)
            if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration < 0:
                mismatches.append("duration_seconds")
            if mismatches:
                return {
                    "ok": False,
                    "command": "hook-post-observe",
                    "decision": "deny",
                    "errors": ["PostToolUse does not match the claimed call: " + ", ".join(mismatches)],
                }

            observed_now = utc_now()
            wall_elapsed = (
                parse_utc(observed_now) - parse_utc(attempt["started_utc"])
            ).total_seconds()
            requested_charge = max(
                1, int(max(float(duration), wall_elapsed) + 0.999999)
            )
            remaining_seconds = max(
                0,
                control["limits"]["active_attempt_seconds"]
                - control["usage"]["active_attempt_seconds"],
            )
            charged_seconds = min(requested_charge, remaining_seconds)
            time_budget_overrun = requested_charge > remaining_seconds

            fingerprint_errors: list[str] = []
            calculated = calculate_candidate_fingerprint(
                resolved_root,
                control["candidate"],
                fingerprint_errors,
                prefix="execution_control.candidate",
            )
            if fingerprint_errors or calculated is None:
                return {
                    "ok": False,
                    "command": "hook-post-observe",
                    "decision": "deny",
                    "errors": fingerprint_errors or ["candidate manifest is empty"],
                }
            changed = calculated != control["candidate"].get("fingerprint")
            if changed:
                derived = set(claim.get("derived_action_classes", []))
                if not derived.issubset({"local", "support"}) or not claim.get("path_touches"):
                    return {
                        "ok": False,
                        "command": "hook-post-observe",
                        "decision": "deny",
                        "errors": [
                            "candidate changed outside a path-bound local/support admission; authoritative recovery required"
                        ],
                    }
                receipt_evaluations = [
                    receipt.get("evaluation_fingerprint")
                    for receipt in control["gate_receipts"]
                    if valid_fingerprint(receipt.get("evaluation_fingerprint"))
                ]
                for fingerprint in receipt_evaluations:
                    if fingerprint not in control["diagnostic_evaluation_fingerprints"]:
                        control["diagnostic_evaluation_fingerprints"].append(fingerprint)
                control["candidate"]["fingerprint"] = calculated
                control["gate_receipts"] = []
                attempt["candidate_fingerprint_after"] = calculated
                active_ids = set(control["lineage"]["acceptance_ids"])
                for requirement in data.get("requirements", []):
                    if requirement.get("id") in active_ids:
                        requirement["status"] = "failing"
                        requirement["evidence"] = []
                        requirement["blocker"] = None

            progress_state_after = calculate_progress_state(
                data, attempt["requirement_id"]
            )
            causal_after = calculate_causal_evidence_fingerprint(
                resolved_root, attempt.get("causal_evidence_ref")
            )
            progressed = progress_delta_observed(
                attempt.get("progress_state_before", {}),
                progress_state_after,
                attempt.get("causal_evidence_fingerprint_before"),
                causal_after,
            )
            claim.update(
                {
                    "status": "observed",
                    "observed_utc": observed_now,
                    "outcome": payload["outcome"],
                    "duration_seconds": duration,
                    "progress_observed": progressed,
                    "causal_evidence_fingerprint_after": causal_after,
                    "charged_active_attempt_seconds": charged_seconds,
                    "time_budget_overrun": time_budget_overrun,
                }
            )
            control["usage"]["active_attempt_seconds"] += charged_seconds
            control["revision"] += 1
            atomic_write_json(acceptance_path, data)
            snapshot_cleanup_warning = None
            try:
                clear_preclaim_control_snapshot(snapshot_path)
            except OSError as exc:
                snapshot_cleanup_warning = (
                    "observed safely but could not remove settled preclaim snapshot: "
                    + str(exc)
                )
            return {
                "ok": True,
                "command": "hook-post-observe",
                "decision": "observed",
                "revision": control["revision"],
                "attempt_id": attempt["id"],
                "tool_use_id": claim["tool_use_id"],
                "outcome": claim["outcome"],
                "candidate_changed": changed,
                "progress_observed": progressed,
                "charged_active_attempt_seconds": charged_seconds,
                "warnings": (
                    [snapshot_cleanup_warning]
                    if snapshot_cleanup_warning is not None
                    else []
                ),
            }
    except (OSError, ValueError) as exc:
        return {
            "ok": False,
            "command": "hook-post-observe",
            "decision": "deny",
            "errors": [str(exc)],
        }


def validate_reconciliation_pair(
    project_path: Path, acceptance_path: Path, root: Path
) -> list[str]:
    errors: list[str] = []
    warnings: list[str] = []
    project = validate_project_file(project_path, errors, warnings)
    acceptance = validate_acceptance_file(acceptance_path, root, errors, warnings)
    if not project or not acceptance:
        return errors
    if project["state"] != acceptance["project_state"]:
        errors.append("reconciled project states do not match")
    current_id = acceptance["current_slice_requirement_id"]
    if project["current_slice_id"] != (current_id or "none"):
        errors.append("reconciled current slices do not match")
    hierarchy = acceptance.get("outcome_hierarchy")
    current_stage_id = hierarchy.get("current_stage_id") if hierarchy else None
    if project["current_stage_id"] != (current_stage_id or "none"):
        errors.append("reconciled delivery stages do not match")
    if project["updated"] != acceptance["updated"]:
        errors.append("reconciled timestamps do not match")
    if project["execution_control_authority_count"] != 1:
        errors.append(
            "reconciled PROJECT_OUTCOME.md must name exactly one execution-control authority"
        )
    if project["legacy_mutable_control_line_count"]:
        errors.append("reconciled PROJECT_OUTCOME.md duplicates mutable control state")
    if acceptance["project_state"] == "active":
        if current_id is None:
            errors.append("active reconciliation requires a current slice")
        elif acceptance["requirements_by_id"].get(current_id, {}).get("status") == "passing":
            errors.append("active reconciliation must select a non-passing current slice")
        if current_stage_id is None:
            errors.append("active reconciliation requires a current delivery stage")
    return errors


def state_reconcile(
    root: str | Path, request_path: str | Path, expected_revision: int
) -> dict[str, object]:
    """Atomically reconcile intent while preserving the monotonic control ledger."""
    project_path, acceptance_path = project_paths(root)
    resolved_root = project_path.parent.parent
    request, request_errors = load_json_object(
        Path(request_path).expanduser().resolve(), "state reconcile request"
    )
    if request_errors or request is None:
        return {"ok": False, "command": "state-reconcile", "errors": request_errors}
    proposed_text = request.get("project_outcome_md")
    proposed = request.get("acceptance")
    if not isinstance(proposed_text, str) or not isinstance(proposed, dict):
        return {
            "ok": False,
            "command": "state-reconcile",
            "errors": [
                "state reconcile request requires project_outcome_md text and acceptance object"
            ],
        }
    try:
        with acceptance_lock(resolved_root):
            current, errors = load_json_object(acceptance_path, "ACCEPTANCE.json")
            if errors or current is None:
                return {"ok": False, "command": "state-reconcile", "errors": errors}
            current_control = current.get("execution_control")
            if not isinstance(current_control, dict):
                return {
                    "ok": False,
                    "command": "state-reconcile",
                    "errors": ["current execution_control is missing"],
                }
            if current_control.get("revision") != expected_revision:
                return {
                    "ok": False,
                    "command": "state-reconcile",
                    "errors": [
                        f"stale expected revision {expected_revision}; current revision is {current_control.get('revision')}"
                    ],
                }
            if current_control.get("active_attempt") is not None:
                return {
                    "ok": False,
                    "command": "state-reconcile",
                    "errors": ["finish or abort the active attempt before state reconciliation"],
                }
            current_slice_id = current.get("current_slice_requirement_id")
            proposed_slice_id = proposed.get("current_slice_requirement_id")
            slice_switch_has_method_history = False
            if current_slice_id != proposed_slice_id:
                proposed_requirements = {
                    item.get("id"): item
                    for item in proposed.get("requirements", [])
                    if isinstance(item, dict)
                }
                current_slice_is_proven = (
                    proposed_requirements.get(current_slice_id, {}).get("status")
                    == "passing"
                )
                current_slice_families = [
                    family
                    for family in current_control.get("usage", {}).get(
                        "method_families", []
                    )
                    if isinstance(family, dict)
                    and family.get("requirement_id") == current_slice_id
                    and family.get("status") in {"active", "stopped"}
                ]
                slice_switch_has_method_history = bool(current_slice_families)
                if current_slice_families and not current_slice_is_proven:
                    return {
                        "ok": False,
                        "command": "state-reconcile",
                        "errors": [
                            "state reconciliation cannot replace a current slice with active or stopped method-family history before that slice passes"
                        ],
                    }
            if proposed.get("schema_version") != CURRENT_SCHEMA_VERSION:
                return {
                    "ok": False,
                    "command": "state-reconcile",
                    "errors": ["state reconciliation requires schema version 6"],
                }

            proposed = json.loads(json.dumps(proposed))
            control = json.loads(json.dumps(current_control))
            now = utc_now()
            if len(PROJECT_UPDATED_PATTERN.findall(proposed_text)) != 1:
                return {
                    "ok": False,
                    "command": "state-reconcile",
                    "errors": ["project_outcome_md must contain exactly one Updated line"],
                }
            proposed_text = PROJECT_UPDATED_PATTERN.sub(f"Updated: {now}", proposed_text)
            proposed["updated_utc"] = now
            hierarchy = proposed.get("outcome_hierarchy")
            stages = hierarchy.get("delivery_stages", []) if isinstance(hierarchy, dict) else []
            declared_stage_ids = {
                stage.get("id") for stage in stages if isinstance(stage, dict)
            }
            stage_id = hierarchy.get("current_stage_id") if isinstance(hierarchy, dict) else None
            if stage_id is None:
                prior_stage = control.get("lineage", {}).get("stage_id")
                stage_id = prior_stage if prior_stage in declared_stage_ids else None
            if stage_id is None:
                return {
                    "ok": False,
                    "command": "state-reconcile",
                    "errors": ["state reconciliation cannot derive a stable delivery-stage lineage"],
                }
            acceptance_ids = sorted(
                entry.get("id")
                for entry in proposed.get("requirements", [])
                if isinstance(entry, dict)
                and entry.get("required") is True
                and entry.get("stage_id") == stage_id
            )
            control["lineage"]["stage_id"] = stage_id
            control["lineage"]["acceptance_ids"] = acceptance_ids
            control["reconciled_utc"] = now
            proposed["execution_control"] = control

            candidate_errors: list[str] = []
            candidate_fingerprint = calculate_candidate_fingerprint(
                resolved_root,
                control["candidate"],
                candidate_errors,
                prefix="execution_control.candidate",
            )
            if candidate_errors or candidate_fingerprint is None:
                return {
                    "ok": False,
                    "command": "state-reconcile",
                    "errors": candidate_errors or ["candidate manifest is empty"],
                }
            scope_fingerprint = calculate_scope_fingerprint(proposed)
            invalidates_receipts = (
                candidate_fingerprint != control["candidate"].get("fingerprint")
                or scope_fingerprint != control["lineage"].get("scope_fingerprint")
            )
            if slice_switch_has_method_history and invalidates_receipts:
                return {
                    "ok": False,
                    "command": "state-reconcile",
                    "errors": [
                        "state reconciliation cannot replace a method-bound current slice while candidate or scope changes invalidate its proof"
                    ],
                }
            control["candidate"]["fingerprint"] = candidate_fingerprint
            control["lineage"]["scope_fingerprint"] = scope_fingerprint
            if invalidates_receipts:
                invalid_receipt_ids = {
                    receipt.get("id")
                    for receipt in control.get("gate_receipts", [])
                    if isinstance(receipt, dict)
                }
                for receipt in control.get("gate_receipts", []):
                    fingerprint = receipt.get("evaluation_fingerprint")
                    if valid_fingerprint(fingerprint) and fingerprint not in control[
                        "diagnostic_evaluation_fingerprints"
                    ]:
                        control["diagnostic_evaluation_fingerprints"].append(fingerprint)
                control["gate_receipts"] = []
                for requirement in proposed.get("requirements", []):
                    if not isinstance(requirement, dict):
                        continue
                    requirement["evidence"] = [
                        evidence
                        for evidence in requirement.get("evidence", [])
                        if not isinstance(evidence, dict)
                        or evidence.get("gate_receipt_id") not in invalid_receipt_ids
                    ]
                    if requirement.get("id") in acceptance_ids:
                        requirement["status"] = "failing"
                        requirement["blocker"] = None

            prior_status = current_control.get("status")
            recovery_ref = request.get("recovery_evidence_ref")
            if prior_status == "stopped" and proposed.get("project_state") == "active":
                return {
                    "ok": False,
                    "command": "state-reconcile",
                    "errors": [
                        "state reconciliation cannot clear stopped control; use an authorized state-transition after recovery"
                    ],
                }
            if proposed.get("project_state") == "complete":
                control["status"] = "closed"
                control["stop_reason"] = None
            elif proposed.get("project_state") == "blocked":
                control["status"] = "stopped"
                control["stop_reason"] = "project state reconciled as blocked"
            else:
                control["status"] = "ready"
                control["stop_reason"] = None
            if nonempty(recovery_ref):
                control["last_recovery_evidence_ref"] = recovery_ref
            control["revision"] = expected_revision + 1
            proposed["execution_control"] = control

            project_path.parent.mkdir(parents=True, exist_ok=True)
            staged_project: Path | None = None
            staged_acceptance: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=project_path.parent,
                    prefix=".PROJECT_OUTCOME.reconcile.", suffix=".md", delete=False,
                ) as handle:
                    handle.write(proposed_text)
                    staged_project = Path(handle.name)
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=acceptance_path.parent,
                    prefix=".ACCEPTANCE.reconcile.", suffix=".json", delete=False,
                ) as handle:
                    json.dump(proposed, handle, indent=2, ensure_ascii=False)
                    handle.write("\n")
                    staged_acceptance = Path(handle.name)
                validation_errors = validate_reconciliation_pair(
                    staged_project, staged_acceptance, resolved_root
                )
            finally:
                if staged_project is not None and staged_project.exists():
                    staged_project.unlink()
                if staged_acceptance is not None and staged_acceptance.exists():
                    staged_acceptance.unlink()
            if validation_errors:
                return {
                    "ok": False,
                    "command": "state-reconcile",
                    "errors": validation_errors,
                }
            atomic_write_json(acceptance_path, proposed)
            atomic_write_text(project_path, proposed_text)
            return {
                "ok": True,
                "command": "state-reconcile",
                "revision": control["revision"],
                "candidate_changed": candidate_fingerprint
                != current_control.get("candidate", {}).get("fingerprint"),
                "scope_changed": scope_fingerprint
                != current_control.get("lineage", {}).get("scope_fingerprint"),
                "status": control["status"],
            }
    except (OSError, ValueError) as exc:
        return {"ok": False, "command": "state-reconcile", "errors": [str(exc)]}


def stopped_limit_has_fired(control: dict[str, Any]) -> bool:
    limits = control.get("limits") if isinstance(control.get("limits"), dict) else {}
    usage = control.get("usage") if isinstance(control.get("usage"), dict) else {}
    if usage.get("failed_attempts", 0) >= limits.get("failed_attempts", 1):
        return True
    if usage.get("no_progress_attempts", 0) >= limits.get("no_progress_attempts", 1):
        return True
    return any(
        isinstance(entry, dict)
        and entry.get("count", 0) >= limits.get("equivalent_failures", 1)
        for entry in usage.get("failure_classes", [])
    )


def validate_limit_extension_request(
    data: dict[str, Any], request: dict[str, Any], root: Path
) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    if set(request) != LIMIT_EXTENSION_REQUEST_FIELDS:
        missing = sorted(LIMIT_EXTENSION_REQUEST_FIELDS - set(request))
        unknown = sorted(set(request) - LIMIT_EXTENSION_REQUEST_FIELDS)
        if missing:
            errors.append("limit extension request is missing fields: " + ", ".join(missing))
        if unknown:
            errors.append("limit extension request has unknown fields: " + ", ".join(unknown))
    if request.get("kind") not in LIMIT_EXTENSION_REQUEST_KINDS:
        errors.append("limit extension request kind is invalid")
    extension_id = request.get("id")
    if not valid_requirement_id(extension_id):
        errors.append("limit extension request id must be a stable ID")
    if not nonempty(request.get("reason")):
        errors.append("limit extension request reason must be non-empty")
    control = data.get("execution_control")
    if not isinstance(control, dict):
        return None, [*errors, "execution_control is missing"]
    lineage = control.get("lineage") if isinstance(control.get("lineage"), dict) else {}
    candidate = control.get("candidate") if isinstance(control.get("candidate"), dict) else {}
    expected_pairs = (
        ("expected_lineage_id", lineage.get("id")),
        ("expected_candidate_fingerprint", candidate.get("fingerprint")),
        ("expected_scope_fingerprint", lineage.get("scope_fingerprint")),
    )
    for field, actual in expected_pairs:
        if request.get(field) != actual:
            errors.append(f"limit extension request {field} does not match live control")
    current_limits = validate_exact_limit_map(
        control.get("limits"), "execution_control.limits", errors
    )
    proposed_limits = validate_exact_limit_map(request.get("limits"), "limit extension request limits", errors)
    if current_limits and proposed_limits:
        for field in EXECUTION_LIMIT_FIELDS:
            if proposed_limits[field] < current_limits[field]:
                errors.append(f"limit extension request limits.{field} cannot decrease")
            if (
                field in NON_EXTENDABLE_LIMIT_FIELDS
                and proposed_limits[field] != current_limits[field]
            ):
                errors.append(f"limit extension request limits.{field} is a permanent floor")
        if not any(
            proposed_limits[field] > current_limits[field]
            for field in EXECUTION_LIMIT_FIELDS
        ):
            errors.append("limit extension request must increase at least one ceiling")
    usage = control.get("usage") if isinstance(control.get("usage"), dict) else {}
    for usage_field, limit_field in (
        ("total_attempts", "total_attempts"),
        ("failed_attempts", "failed_attempts"),
        ("expensive_attempts", "expensive_attempts"),
        ("support_attempts", "support_attempts"),
        ("no_progress_attempts", "no_progress_attempts"),
        ("total_tool_calls", "total_tool_calls"),
        ("support_tool_calls", "support_tool_calls"),
        ("support_no_progress_calls", "support_no_progress_calls"),
        ("active_attempt_seconds", "active_attempt_seconds"),
        ("spawned_workers", "spawned_workers"),
        ("scope_growth_actions", "scope_growth_actions"),
        ("path_touches", "max_path_touches"),
    ):
        if proposed_limits and usage.get(usage_field, 0) > proposed_limits[limit_field]:
            errors.append(
                f"limit extension request limits.{limit_field} is below live usage.{usage_field}"
            )
    _, authorization_path = resolve_limit_extension_evidence_path(
        root,
        request.get("authorization_ref"),
        "limit extension request authorization_ref",
        errors,
        must_exist=True,
    )
    authorization_fingerprint = (
        file_sha256_fingerprint(authorization_path)
        if authorization_path is not None
        else None
    )
    if (
        valid_fingerprint(authorization_fingerprint)
        and authorization_fingerprint
        in consumed_recovery_authorization_fingerprints(control)
    ):
        errors.append(
            "limit extension authorization has already been consumed by a recovery action"
        )
    receipt_ref, receipt_path = resolve_limit_extension_evidence_path(
        root,
        request.get("receipt_ref"),
        "limit extension request receipt_ref",
        errors,
        must_exist=False,
    )
    history = control.get("limit_extensions", [])
    if isinstance(history, list) and extension_id in {
        entry.get("id") for entry in history if isinstance(entry, dict)
    }:
        errors.append("limit extension request id already exists")
    if errors:
        return None, errors
    return {
        "id": extension_id,
        "reason": request["reason"].strip(),
        "authorization_ref": request["authorization_ref"],
        "authorization_path": authorization_path,
        "authorization_fingerprint": authorization_fingerprint,
        "receipt_ref": receipt_ref,
        "receipt_path": receipt_path,
        "limits": proposed_limits,
    }, []


def validate_failure_identity_migration_request(
    data: dict[str, Any], request: dict[str, Any], root: Path
) -> tuple[dict[str, Any] | None, list[str]]:
    """Admit only a complete, provenance-backed legacy-v1 identity correction."""
    errors: list[str] = []
    if set(request) != FAILURE_IDENTITY_MIGRATION_REQUEST_FIELDS:
        missing = sorted(FAILURE_IDENTITY_MIGRATION_REQUEST_FIELDS - set(request))
        unknown = sorted(set(request) - FAILURE_IDENTITY_MIGRATION_REQUEST_FIELDS)
        if missing:
            errors.append("failure fingerprint migration request is missing fields: " + ", ".join(missing))
        if unknown:
            errors.append("failure fingerprint migration request has unknown fields: " + ", ".join(unknown))
    if request.get("kind") not in FAILURE_IDENTITY_MIGRATION_REQUEST_KINDS:
        errors.append("failure fingerprint migration request kind is invalid")
    migration_id = request.get("id")
    if not valid_requirement_id(migration_id):
        errors.append("failure fingerprint migration request id must be a stable ID")
    if not nonempty(request.get("reason")):
        errors.append("failure fingerprint migration request reason must be non-empty")
    control = data.get("execution_control")
    if not isinstance(control, dict):
        return None, [*errors, "execution_control is missing"]
    lineage = control.get("lineage") if isinstance(control.get("lineage"), dict) else {}
    candidate = control.get("candidate") if isinstance(control.get("candidate"), dict) else {}
    for field, actual in (
        ("expected_lineage_id", lineage.get("id")),
        ("expected_candidate_fingerprint", candidate.get("fingerprint")),
        ("expected_scope_fingerprint", lineage.get("scope_fingerprint")),
    ):
        if request.get(field) != actual:
            errors.append(f"failure fingerprint migration request {field} does not match live control")
    legacy_fingerprint = request.get("legacy_fingerprint")
    if not valid_fingerprint(legacy_fingerprint):
        errors.append("failure fingerprint migration request legacy_fingerprint must be SHA-256")
    usage = control.get("usage") if isinstance(control.get("usage"), dict) else {}
    live_classes = usage.get("failure_classes") if isinstance(usage.get("failure_classes"), list) else []
    matches = [
        item for item in live_classes
        if isinstance(item, dict) and item.get("fingerprint") == legacy_fingerprint
    ]
    if len(matches) != 1:
        errors.append("failure fingerprint migration requires exactly one live legacy source record")
        source_failure: dict[str, Any] | None = None
    else:
        source_failure = matches[0]
        source_errors: list[str] = []
        validate_failure_classes([source_failure], "migration source", lineage.get("id"), source_errors)
        errors.extend(source_errors)
        if source_failure.get("failure_identity_version", 1) != 1:
            errors.append("failure fingerprint migration can repair legacy v1 records only")
        if not positive_int(source_failure.get("count")) or source_failure.get("count") < 2:
            errors.append("failure fingerprint migration requires a legacy aggregate count of at least two")
        if source_failure.get("candidate_fingerprint") != candidate.get("fingerprint"):
            errors.append("failure fingerprint migration source candidate does not match live control")
    history = control.get("failure_identity_migrations", [])
    if isinstance(history, list):
        if migration_id in {entry.get("id") for entry in history if isinstance(entry, dict)}:
            errors.append("failure fingerprint migration id already exists")
        if legacy_fingerprint in {
            entry.get("source_legacy_failure_class", {}).get("fingerprint")
            for entry in history
            if isinstance(entry, dict) and isinstance(entry.get("source_legacy_failure_class"), dict)
        }:
            errors.append("failure fingerprint migration source was already migrated")
    _, authorization_path = resolve_limit_extension_evidence_path(
        root,
        request.get("authorization_ref"),
        "failure fingerprint migration request authorization_ref",
        errors,
        must_exist=True,
    )
    authorization_fingerprint = (
        file_sha256_fingerprint(authorization_path)
        if authorization_path is not None
        else None
    )
    if (
        valid_fingerprint(authorization_fingerprint)
        and authorization_fingerprint
        in consumed_recovery_authorization_fingerprints(control)
    ):
        errors.append(
            "failure fingerprint migration authorization has already been consumed by a recovery action"
        )
    provenance_ref, provenance_path = resolve_limit_extension_evidence_path(
        root,
        request.get("provenance_ref"),
        "failure fingerprint migration request provenance_ref",
        errors,
        must_exist=True,
    )
    receipt_ref, receipt_path = resolve_limit_extension_evidence_path(
        root,
        request.get("receipt_ref"),
        "failure fingerprint migration request receipt_ref",
        errors,
        must_exist=False,
    )
    provenance = None
    if provenance_path is not None:
        provenance, provenance_errors = load_json_object(
            provenance_path, "failure fingerprint migration provenance"
        )
        errors.extend(provenance_errors)
    entries = recovered_failure_entries_from_provenance(
        provenance,
        source_failure,
        provenance_ref,
        "failure fingerprint migration provenance",
        errors,
    )
    if entries is not None:
        active_fingerprints = {
            item.get("fingerprint") for item in live_classes if isinstance(item, dict)
        }
        if any(entry["fingerprint"] in active_fingerprints for entry in entries):
            errors.append("failure fingerprint migration would collide with a live failure identity")
    if errors or source_failure is None or entries is None:
        return None, errors
    return {
        "id": migration_id,
        "reason": request["reason"].strip(),
        "authorization_ref": request["authorization_ref"],
        "authorization_path": authorization_path,
        "authorization_fingerprint": authorization_fingerprint,
        "provenance_ref": provenance_ref,
        "provenance_path": provenance_path,
        "receipt_ref": receipt_ref,
        "receipt_path": receipt_path,
        "source_failure": json.loads(json.dumps(source_failure)),
        "migrated_entries": entries,
    }, []


def failure_fingerprint_migrate(
    root: str | Path, request_path: str | Path, expected_revision: int
) -> dict[str, object]:
    """Atomically split a proven legacy v1 aggregate into divergence-aware v2 entries."""
    project_path, acceptance_path = project_paths(root)
    resolved_root = project_path.parent.parent
    request, request_errors = load_json_object(
        Path(request_path).expanduser().resolve(), "failure fingerprint migration request"
    )
    if request_errors or request is None:
        return {
            "ok": False,
            "command": "failure-fingerprint-migrate",
            "errors": request_errors,
        }
    receipt_created = False
    state_write_started = False
    receipt_path: Path | None = None
    try:
        with acceptance_lock(resolved_root):
            data, errors = load_json_object(acceptance_path, "ACCEPTANCE.json")
            if errors or data is None:
                return {"ok": False, "command": "failure-fingerprint-migrate", "errors": errors}
            if data.get("schema_version") != CURRENT_SCHEMA_VERSION:
                return {
                    "ok": False,
                    "command": "failure-fingerprint-migrate",
                    "errors": [
                        f"failure fingerprint migration requires schema version {CURRENT_SCHEMA_VERSION}"
                    ],
                }
            control = data.get("execution_control")
            if not isinstance(control, dict):
                return {
                    "ok": False,
                    "command": "failure-fingerprint-migrate",
                    "errors": ["execution_control is missing"],
                }
            if control.get("revision") != expected_revision:
                return {
                    "ok": False,
                    "command": "failure-fingerprint-migrate",
                    "errors": [
                        f"stale expected revision {expected_revision}; current revision is {control.get('revision')}"
                    ],
                }
            if data.get("project_state") not in {"active", "blocked"}:
                return {
                    "ok": False,
                    "command": "failure-fingerprint-migrate",
                    "errors": [
                        "failure fingerprint migration requires an active or blocked project state"
                    ],
                }
            if control.get("status") != "stopped" or control.get("active_attempt") is not None:
                return {
                    "ok": False,
                    "command": "failure-fingerprint-migrate",
                    "errors": ["failure fingerprint migration requires a stopped control with no active attempt"],
                }
            if not stopped_limit_has_fired(control):
                return {
                    "ok": False,
                    "command": "failure-fingerprint-migrate",
                    "errors": ["failure fingerprint migration requires a fired limit"],
                }
            normalized_request, request_errors = validate_failure_identity_migration_request(
                data, request, resolved_root
            )
            if request_errors or normalized_request is None:
                return {
                    "ok": False,
                    "command": "failure-fingerprint-migrate",
                    "errors": request_errors,
                }
            current_project_text = project_path.read_text(encoding="utf-8")
            if len(PROJECT_UPDATED_PATTERN.findall(current_project_text)) != 1:
                return {
                    "ok": False,
                    "command": "failure-fingerprint-migrate",
                    "errors": ["PROJECT_OUTCOME.md must contain exactly one Updated line"],
                }
            proposed = json.loads(json.dumps(data))
            proposed_control = proposed["execution_control"]
            proposed_usage = proposed_control["usage"]
            source_failure = normalized_request["source_failure"]
            source_positions = [
                index
                for index, entry in enumerate(proposed_usage["failure_classes"])
                if entry == source_failure
            ]
            if len(source_positions) != 1:
                return {
                    "ok": False,
                    "command": "failure-fingerprint-migrate",
                    "errors": ["live legacy source changed during migration admission"],
                }
            position = source_positions[0]
            proposed_usage["failure_classes"] = (
                proposed_usage["failure_classes"][:position]
                + normalized_request["migrated_entries"]
                + proposed_usage["failure_classes"][position + 1 :]
            )
            now = utc_now()
            migration = {
                "kind": FAILURE_IDENTITY_MIGRATION_KIND,
                "id": normalized_request["id"],
                "migrated_utc": now,
                "prior_revision": expected_revision,
                "result_revision": expected_revision + 1,
                "reason": normalized_request["reason"],
                "authorization_ref": normalized_request["authorization_ref"],
                "authorization_fingerprint": normalized_request[
                    "authorization_fingerprint"
                ],
                "provenance_ref": normalized_request["provenance_ref"],
                "provenance_fingerprint": file_sha256_fingerprint(
                    normalized_request["provenance_path"]
                ),
                "receipt_ref": normalized_request["receipt_ref"],
                "lineage_id": proposed_control["lineage"]["id"],
                "candidate_fingerprint": proposed_control["candidate"]["fingerprint"],
                "scope_fingerprint": proposed_control["lineage"]["scope_fingerprint"],
                "usage_fingerprint": canonical_fingerprint(control["usage"]),
                "usage_anchor": compact_usage_anchor(control["usage"]),
                "result_usage_fingerprint": canonical_fingerprint(proposed_usage),
                "result_usage_anchor": compact_usage_anchor(proposed_usage),
                "source_legacy_failure_class": source_failure,
                "migrated_failure_classes": normalized_request["migrated_entries"],
            }
            migration["migration_fingerprint"] = canonical_fingerprint(
                {
                    field: migration.get(field)
                    for field in sorted(
                        FAILURE_IDENTITY_MIGRATION_RECORD_FIELDS - {"migration_fingerprint"}
                    )
                }
            )
            history = proposed_control.setdefault("failure_identity_migrations", [])
            history.append(migration)
            proposed_control["status"] = "stopped"
            proposed_control["stop_reason"] = (
                "aggregate failed-attempt limit reached; no-progress limit reached; "
                "legacy failure identity repaired from recovered transcript provenance"
            )
            proposed_control["reconciled_utc"] = now
            proposed_control["revision"] = expected_revision + 1
            proposed["updated_utc"] = now
            proposed_project_text = PROJECT_UPDATED_PATTERN.sub(f"Updated: {now}", current_project_text)
            receipt_path = normalized_request["receipt_path"]
            atomic_write_json(
                receipt_path,
                {"kind": FAILURE_IDENTITY_MIGRATION_RECEIPT_KIND, "migration": migration},
            )
            receipt_created = True
            staged_project: Path | None = None
            staged_acceptance: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=project_path.parent,
                    prefix=".PROJECT_OUTCOME.failure-fingerprint-migrate.", suffix=".md", delete=False,
                ) as handle:
                    handle.write(proposed_project_text)
                    staged_project = Path(handle.name)
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=acceptance_path.parent,
                    prefix=".ACCEPTANCE.failure-fingerprint-migrate.", suffix=".json", delete=False,
                ) as handle:
                    json.dump(proposed, handle, indent=2, ensure_ascii=False)
                    handle.write("\n")
                    staged_acceptance = Path(handle.name)
                validation_errors = validate_reconciliation_pair(
                    staged_project, staged_acceptance, resolved_root
                )
            finally:
                if staged_project is not None and staged_project.exists():
                    staged_project.unlink()
                if staged_acceptance is not None and staged_acceptance.exists():
                    staged_acceptance.unlink()
            if validation_errors:
                return {
                    "ok": False,
                    "command": "failure-fingerprint-migrate",
                    "errors": validation_errors,
                }
            counters_preserved = all(
                proposed_usage.get(field) == control["usage"].get(field)
                for field in set(proposed_usage) | set(control["usage"])
                if field not in {"failure_classes", "method_families"}
            )
            state_write_started = True
            atomic_write_json(acceptance_path, proposed)
            atomic_write_text(project_path, proposed_project_text)
            return {
                "ok": True,
                "command": "failure-fingerprint-migrate",
                "revision": proposed_control["revision"],
                "status": proposed_control["status"],
                "receipt_ref": normalized_request["receipt_ref"],
                "counters_preserved": counters_preserved,
                "old_method_families_preserved": (
                    proposed_control["usage"].get("method_families")
                    == control["usage"].get("method_families")
                ),
            }
    except (OSError, ValueError) as exc:
        return {"ok": False, "command": "failure-fingerprint-migrate", "errors": [str(exc)]}
    finally:
        if receipt_created and not state_write_started and receipt_path is not None:
            try:
                receipt_path.unlink()
            except OSError:
                pass


def state_transition(root: str | Path, request_path: str | Path, expected_revision: int) -> dict[str, object]:
    """Atomically move only the mirrored active/blocked execution state."""
    project_path, acceptance_path = project_paths(root)
    resolved_root = project_path.parent.parent
    request, errors = load_json_object(Path(request_path).expanduser().resolve(), "state transition request")
    if errors or request is None:
        return {"ok": False, "command": "state-transition", "errors": errors}
    if (
        set(request) != STATE_TRANSITION_REQUEST_FIELDS
        or request.get("kind") not in STATE_TRANSITION_REQUEST_KINDS
    ):
        return {"ok": False, "command": "state-transition", "errors": ["state transition request shape is invalid"]}
    try:
        with acceptance_lock(resolved_root):
            data, errors = load_json_object(acceptance_path, "ACCEPTANCE.json")
            if errors or data is None:
                return {"ok": False, "command": "state-transition", "errors": errors}
            control = data.get("execution_control")
            if not isinstance(control, dict) or control.get("revision") != expected_revision:
                return {"ok": False, "command": "state-transition", "errors": ["stale expected control revision"]}
            target = request.get("target_project_state")
            if target not in {"active", "blocked"} or target == data.get("project_state"):
                return {"ok": False, "command": "state-transition", "errors": ["target project state is invalid or unchanged"]}
            if control.get("status") != "stopped" or control.get("active_attempt") is not None:
                return {"ok": False, "command": "state-transition", "errors": ["state transition requires stopped control and no active attempt"]}
            lineage = control.get("lineage", {}); candidate = control.get("candidate", {})
            if any((request.get("expected_lineage_id") != lineage.get("id"), request.get("expected_candidate_fingerprint") != candidate.get("fingerprint"), request.get("expected_scope_fingerprint") != lineage.get("scope_fingerprint"))):
                return {"ok": False, "command": "state-transition", "errors": ["state transition identity does not match live control"]}
            auth_ref, auth_path = resolve_limit_extension_evidence_path(resolved_root, request.get("authorization_ref"), "state transition authorization_ref", [], must_exist=True)
            if auth_path is None or not valid_requirement_id(request.get("id")) or not nonempty(request.get("reason")):
                return {"ok": False, "command": "state-transition", "errors": ["state transition authorization, id, or reason is invalid"]}
            authorization_fingerprint = file_sha256_fingerprint(auth_path)
            if authorization_fingerprint in consumed_recovery_authorization_fingerprints(control):
                return {
                    "ok": False,
                    "command": "state-transition",
                    "errors": [
                        "state transition authorization has already been consumed by a recovery action"
                    ],
                }
            recovery_ref = request.get("recovery_evidence_ref")
            if target == "active":
                _, recovery_path = resolve_limit_extension_evidence_path(resolved_root, recovery_ref, "state transition recovery_evidence_ref", [], must_exist=True)
                if recovery_path is None or stopped_limit_has_fired(control):
                    return {"ok": False, "command": "state-transition", "errors": ["active transition requires recovery evidence and cleared limits"]}
            elif recovery_ref is not None:
                return {"ok": False, "command": "state-transition", "errors": ["blocked transition cannot include recovery evidence"]}
            text = project_path.read_text(encoding="utf-8")
            if len(PROJECT_UPDATED_PATTERN.findall(text)) != 1 or len(PROJECT_STATE_PATTERN.findall(text)) != 1:
                return {"ok": False, "command": "state-transition", "errors": ["PROJECT_OUTCOME state markers are invalid"]}
            proposed = json.loads(json.dumps(data)); proposed_control = proposed["execution_control"]; now = utc_now()
            record = {"kind": STATE_TRANSITION_KIND, "id": request["id"], "transitioned_utc": now, "prior_revision": expected_revision, "result_revision": expected_revision + 1, "reason": request["reason"].strip(), "authorization_ref": auth_ref, "authorization_fingerprint": authorization_fingerprint, "recovery_evidence_ref": recovery_ref, "target_project_state": target, "lineage_id": lineage.get("id"), "candidate_fingerprint": candidate.get("fingerprint"), "scope_fingerprint": lineage.get("scope_fingerprint"), "usage_fingerprint": canonical_fingerprint(control["usage"]), "usage_anchor": compact_usage_anchor(control["usage"])}
            record["transition_fingerprint"] = canonical_fingerprint(record)
            proposed_control.setdefault("state_transitions", []).append(record)
            proposed["project_state"] = target; proposed["updated_utc"] = now; proposed_control["reconciled_utc"] = now; proposed_control["revision"] = expected_revision + 1
            if target == "blocked": proposed_control["status"] = "stopped"; proposed_control["stop_reason"] = "project state transitioned to blocked: " + record["reason"]
            else: proposed_control["status"] = "ready"; proposed_control["stop_reason"] = None; proposed_control["last_recovery_evidence_ref"] = recovery_ref
            proposed_text = PROJECT_UPDATED_PATTERN.sub(f"Updated: {now}", PROJECT_STATE_PATTERN.sub("State: " + target, text))
            staged_project = staged_acceptance = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=project_path.parent, delete=False) as handle: handle.write(proposed_text); staged_project = Path(handle.name)
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=acceptance_path.parent, delete=False) as handle: json.dump(proposed, handle, indent=2); handle.write("\n"); staged_acceptance = Path(handle.name)
                validation_errors = validate_reconciliation_pair(staged_project, staged_acceptance, resolved_root)
            finally:
                if staged_project is not None and staged_project.exists(): staged_project.unlink()
                if staged_acceptance is not None and staged_acceptance.exists(): staged_acceptance.unlink()
            if validation_errors: return {"ok": False, "command": "state-transition", "errors": validation_errors}
            atomic_write_json(acceptance_path, proposed); atomic_write_text(project_path, proposed_text)
            return {"ok": True, "command": "state-transition", "revision": proposed_control["revision"], "project_state": target, "status": proposed_control["status"], "counters_preserved": proposed_control["usage"] == control["usage"]}
    except (OSError, ValueError) as exc:
        return {"ok": False, "command": "state-transition", "errors": [str(exc)]}


def limit_extend(
    root: str | Path, request_path: str | Path, expected_revision: int
) -> dict[str, object]:
    """Append a bounded audit record and raise ceilings without reopening work."""
    project_path, acceptance_path = project_paths(root)
    resolved_root = project_path.parent.parent
    request, request_errors = load_json_object(
        Path(request_path).expanduser().resolve(), "limit extension request"
    )
    if request_errors or request is None:
        return {"ok": False, "command": "limit-extend", "errors": request_errors}
    receipt_created = False
    state_write_started = False
    receipt_path: Path | None = None
    try:
        with acceptance_lock(resolved_root):
            resume = validate(resolved_root, mode="resume")
            if not resume["ok"]:
                return {
                    "ok": False,
                    "command": "limit-extend",
                    "errors": ["resume gate failed", *resume["errors"]],
                }
            data, errors = load_json_object(acceptance_path, "ACCEPTANCE.json")
            if errors or data is None:
                return {"ok": False, "command": "limit-extend", "errors": errors}
            if data.get("schema_version") != CURRENT_SCHEMA_VERSION:
                return {
                    "ok": False,
                    "command": "limit-extend",
                    "errors": [f"limit extension requires schema version {CURRENT_SCHEMA_VERSION}"],
                }
            control = data.get("execution_control")
            if not isinstance(control, dict):
                return {"ok": False, "command": "limit-extend", "errors": ["execution_control is missing"]}
            if control.get("revision") != expected_revision:
                return {
                    "ok": False,
                    "command": "limit-extend",
                    "errors": [
                        f"stale expected revision {expected_revision}; current revision is {control.get('revision')}"
                    ],
                }
            if data.get("project_state") != "blocked":
                return {
                    "ok": False,
                    "command": "limit-extend",
                    "errors": ["limit extension requires project_state blocked"],
                }
            if control.get("status") != "stopped" or control.get("active_attempt") is not None:
                return {
                    "ok": False,
                    "command": "limit-extend",
                    "errors": ["limit extension requires a stopped control with no active attempt"],
                }
            total_attempts_exhausted = (
                control.get("usage", {}).get("total_attempts", 0)
                >= control.get("limits", {}).get("total_attempts", 1)
            )
            direct_total_attempt_admission_stop = (
                control.get("stop_reason") == "attempt admission exhausted: total_attempts"
            )
            transitions = control.get("state_transitions")
            last_transition = transitions[-1] if isinstance(transitions, list) and transitions else {}
            blocked_total_attempt_admission_stop = (
                isinstance(last_transition, dict)
                and last_transition.get("target_project_state") == "blocked"
                and last_transition.get("result_revision") == control.get("revision")
                and last_transition.get("usage_fingerprint") == canonical_fingerprint(control.get("usage"))
                and (
                    (
                        last_transition.get("kind") == LEGACY_STATE_TRANSITION_KIND
                        and last_transition.get("usage_snapshot") == control.get("usage")
                    )
                    or (
                        last_transition.get("kind") == STATE_TRANSITION_KIND
                        and last_transition.get("usage_anchor")
                        == compact_usage_anchor(control.get("usage"))
                    )
                )
                and control.get("stop_reason") == "project state transitioned to blocked: " + str(last_transition.get("reason", ""))
            )
            total_attempt_admission_exhausted = total_attempts_exhausted and (
                direct_total_attempt_admission_stop or blocked_total_attempt_admission_stop
            )
            if not stopped_limit_has_fired(control) and not total_attempt_admission_exhausted:
                return {
                    "ok": False,
                    "command": "limit-extend",
                    "errors": ["limit extension requires a fired failure/no-progress limit or exact total-attempt admission exhaustion"],
                }
            normalized_request, request_errors = validate_limit_extension_request(
                data, request, resolved_root
            )
            if request_errors or normalized_request is None:
                return {
                    "ok": False,
                    "command": "limit-extend",
                    "errors": request_errors,
                }
            try:
                current_project_text = project_path.read_text(encoding="utf-8")
            except OSError as exc:
                return {"ok": False, "command": "limit-extend", "errors": [str(exc)]}
            if len(PROJECT_UPDATED_PATTERN.findall(current_project_text)) != 1:
                return {
                    "ok": False,
                    "command": "limit-extend",
                    "errors": ["PROJECT_OUTCOME.md must contain exactly one Updated line"],
                }
            proposed = json.loads(json.dumps(data))
            proposed_control = proposed["execution_control"]
            now = utc_now()
            extension = {
                "kind": LIMIT_EXTENSION_KIND,
                "id": normalized_request["id"],
                "applied_utc": now,
                "prior_revision": expected_revision,
                "result_revision": expected_revision + 1,
                "reason": normalized_request["reason"],
                "authorization_ref": normalized_request["authorization_ref"],
                "authorization_fingerprint": normalized_request[
                    "authorization_fingerprint"
                ],
                "receipt_ref": normalized_request["receipt_ref"],
                "lineage_id": proposed_control["lineage"]["id"],
                "candidate_fingerprint": proposed_control["candidate"]["fingerprint"],
                "scope_fingerprint": proposed_control["lineage"]["scope_fingerprint"],
                "usage_fingerprint": canonical_fingerprint(proposed_control["usage"]),
                "usage_anchor": compact_usage_anchor(proposed_control["usage"]),
                "prior_limits": json.loads(json.dumps(proposed_control["limits"])),
                "new_limits": json.loads(json.dumps(normalized_request["limits"])),
            }
            extension["extension_fingerprint"] = canonical_fingerprint(
                {
                    field: extension.get(field)
                    for field in sorted(LIMIT_EXTENSION_RECORD_FIELDS - {"extension_fingerprint"})
                }
            )
            proposed_control["limits"] = json.loads(json.dumps(normalized_request["limits"]))
            history = proposed_control.setdefault("limit_extensions", [])
            history.append(extension)
            proposed_control["reconciled_utc"] = now
            proposed_control["revision"] = expected_revision + 1
            proposed["updated_utc"] = now
            proposed_project_text = PROJECT_UPDATED_PATTERN.sub(
                f"Updated: {now}", current_project_text
            )
            receipt_path = normalized_request["receipt_path"]
            atomic_write_json(
                receipt_path,
                {"kind": LIMIT_EXTENSION_RECEIPT_KIND, "extension": extension},
            )
            receipt_created = True
            staged_project: Path | None = None
            staged_acceptance: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=project_path.parent,
                    prefix=".PROJECT_OUTCOME.limit-extend.", suffix=".md", delete=False,
                ) as handle:
                    handle.write(proposed_project_text)
                    staged_project = Path(handle.name)
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=acceptance_path.parent,
                    prefix=".ACCEPTANCE.limit-extend.", suffix=".json", delete=False,
                ) as handle:
                    json.dump(proposed, handle, indent=2, ensure_ascii=False)
                    handle.write("\n")
                    staged_acceptance = Path(handle.name)
                validation_errors = validate_reconciliation_pair(
                    staged_project, staged_acceptance, resolved_root
                )
            finally:
                if staged_project is not None and staged_project.exists():
                    staged_project.unlink()
                if staged_acceptance is not None and staged_acceptance.exists():
                    staged_acceptance.unlink()
            if validation_errors:
                return {
                    "ok": False,
                    "command": "limit-extend",
                    "errors": validation_errors,
                }
            state_write_started = True
            atomic_write_json(acceptance_path, proposed)
            atomic_write_text(project_path, proposed_project_text)
            return {
                "ok": True,
                "command": "limit-extend",
                "revision": proposed_control["revision"],
                "status": proposed_control["status"],
                "receipt_ref": normalized_request["receipt_ref"],
                "counters_preserved": proposed_control["usage"] == control["usage"],
                "limits": proposed_control["limits"],
            }
    except (OSError, ValueError) as exc:
        return {"ok": False, "command": "limit-extend", "errors": [str(exc)]}
    finally:
        if receipt_created and not state_write_started and receipt_path is not None:
            try:
                receipt_path.unlink()
            except OSError:
                pass


def control_status(root: str | Path) -> dict[str, object]:
    _, acceptance_path = project_paths(root)
    data, errors = load_json_object(acceptance_path, "ACCEPTANCE.json")
    if errors or data is None:
        return {"ok": False, "command": "control-status", "errors": errors}
    control = data.get("execution_control")
    if not isinstance(control, dict):
        return {
            "ok": False,
            "command": "control-status",
            "errors": ["execution_control is missing"],
        }
    attempt = control.get("active_attempt")
    return {
        "ok": True,
        "command": "control-status",
        "revision": control.get("revision"),
        "status": control.get("status"),
        "support_stop_reason": control.get("support_stop_reason"),
        "usage": control.get("usage"),
        "active_attempt": (
            {
                "id": attempt.get("id"),
                "method_family_id": attempt.get("method_family_id"),
                "tool_binding": attempt.get("tool_binding"),
                "tool_claim": attempt.get("tool_claim"),
            }
            if isinstance(attempt, dict)
            else None
        ),
    }


def attempt_finish(
    root: str | Path, result_path: str | Path, expected_revision: int
) -> dict[str, object]:
    project_path, acceptance_path = project_paths(root)
    resolved_root = project_path.parent.parent
    result, result_errors = load_json_object(Path(result_path).expanduser().resolve(), "attempt result")
    if result_errors:
        return {"ok": False, "command": "attempt-finish", "errors": result_errors}
    try:
        with acceptance_lock(resolved_root):
            current = validate(resolved_root, mode="admit")
            if not current["ok"]:
                return {
                    "ok": False,
                    "command": "attempt-finish",
                    "errors": ["current control state is invalid", *current["errors"]],
                }
            data, errors = load_json_object(acceptance_path, "ACCEPTANCE.json")
            if errors or data is None:
                return {"ok": False, "command": "attempt-finish", "errors": errors}
            control = data.get("execution_control", {})
            if control.get("revision") != expected_revision:
                return {
                    "ok": False,
                    "command": "attempt-finish",
                    "errors": [
                        f"stale expected revision {expected_revision}; current revision is {control.get('revision')}"
                    ],
                }
            attempt = control.get("active_attempt")
            if control.get("status") != "running" or not isinstance(attempt, dict):
                return {
                    "ok": False,
                    "command": "attempt-finish",
                    "errors": ["there is no atomically reserved active attempt"],
                }
            errors = validate_attempt_result(result or {}, attempt)
            if errors:
                return {"ok": False, "command": "attempt-finish", "errors": errors}

            outcome = result["outcome"]
            claim = attempt.get("tool_claim", {})
            if outcome == "passed" and claim.get("status") != "observed":
                return {
                    "ok": False,
                    "command": "attempt-finish",
                    "errors": ["a passing finish requires the exact PostToolUse observation"],
                }
            if outcome == "passed" and claim.get("outcome") != "completed":
                return {
                    "ok": False,
                    "command": "attempt-finish",
                    "errors": ["a passing finish requires a completed tool observation"],
                }
            if outcome == "passed" and claim.get("time_budget_overrun") is True:
                return {
                    "ok": False,
                    "command": "attempt-finish",
                    "errors": [
                        "a passing finish cannot cross the remaining project-cumulative time budget"
                    ],
                }
            if outcome == "failed":
                result["failure_fingerprint"] = canonical_failure_fingerprint(
                    attempt, result["earliest_divergence"]
                )
            now = utc_now()
            next_revision = control["revision"] + 1
            receipt = None
            proof_attempt = "proof" in set(attempt.get("action_classes", []))
            derived_progress = bool(claim.get("progress_observed"))
            usage = control["usage"]
            fresh_proof_evidence = bool(
                proof_attempt
                and result.get("evidence_ref") == attempt.get("causal_evidence_ref")
                and valid_fingerprint(claim.get("causal_evidence_fingerprint_after"))
                and claim.get("causal_evidence_fingerprint_after")
                != attempt.get("causal_evidence_fingerprint_before")
            )
            if outcome == "passed" and proof_attempt and fresh_proof_evidence:
                receipt = {
                    "id": f"RECEIPT-{next_revision:06d}",
                    "requirement_id": attempt["requirement_id"],
                    "tier": attempt["tier"],
                    "lineage_id": attempt["lineage_id"],
                    "candidate_fingerprint": control["candidate"]["fingerprint"],
                    "evidence_ref": result["evidence_ref"],
                    "summary": result["summary"],
                    "verified_utc": now,
                    "evaluation_fingerprint": attempt.get("evaluation_fingerprint"),
                    "evaluation_role": attempt.get("evaluation_role", "none"),
                    "evidence_fingerprint": claim.get(
                        "causal_evidence_fingerprint_after"
                    ),
                }
                control["gate_receipts"] = [
                    existing
                    for existing in control["gate_receipts"]
                    if not (
                        existing.get("requirement_id") == attempt["requirement_id"]
                        and existing.get("tier") == attempt["tier"]
                    )
                ]
                control["gate_receipts"].append(receipt)
                derived_progress = True
            elif outcome == "failed":
                usage["failed_attempts"] += 1
                failure = next(
                    (
                        entry
                        for entry in usage["failure_classes"]
                        if entry.get("fingerprint") == result["failure_fingerprint"]
                        and entry.get("lineage_id") == attempt["lineage_id"]
                    ),
                    None,
                )
                if failure is None:
                    failure = {
                        "fingerprint": result["failure_fingerprint"],
                        "failure_identity_version": 3,
                        "lineage_id": attempt["lineage_id"],
                        "failure_class": result["failure_class"],
                        "earliest_divergence": result["earliest_divergence"],
                        "acceptance_outcome_id": attempt["acceptance_outcome_id"],
                        "boundary_id": attempt["boundary_id"],
                        "candidate_fingerprint": control["candidate"]["fingerprint"],
                        "count": 0,
                        "last_observed_utc": now,
                    }
                    usage["failure_classes"].append(failure)
                failure["count"] += 1
                failure["last_observed_utc"] = now

            family = next(
                entry
                for entry in control["usage"]["method_families"]
                if entry.get("id") == attempt["method_family_id"]
            )
            if outcome == "failed":
                family["failed_attempts"] += 1
                structured = next(
                    (
                        entry
                        for entry in family["failures"]
                        if entry.get("acceptance_outcome_id")
                        == attempt["acceptance_outcome_id"]
                        and entry.get("boundary_id") == attempt["boundary_id"]
                    ),
                    None,
                )
                if structured is None:
                    structured = {
                        "acceptance_outcome_id": attempt["acceptance_outcome_id"],
                        "boundary_id": attempt["boundary_id"],
                        "count": 0,
                    }
                    family["failures"].append(structured)
                structured["count"] += 1

            evaluation_fingerprint = attempt.get("evaluation_fingerprint")
            if (
                valid_fingerprint(evaluation_fingerprint)
                and evaluation_fingerprint
                not in control["diagnostic_evaluation_fingerprints"]
            ):
                control["diagnostic_evaluation_fingerprints"].append(
                    evaluation_fingerprint
                )
            if not derived_progress:
                usage["no_progress_attempts"] += 1
                family["no_progress_attempts"] += 1
                if "support" in claim.get("derived_action_classes", []):
                    usage["support_no_progress_calls"] += 1
                    if (
                        usage["support_no_progress_calls"]
                        >= control["limits"]["support_no_progress_calls"]
                    ):
                        control["support_stop_reason"] = (
                            "support no-progress tool-call limit reached; "
                            "direct delivery reserve remains"
                        )
            family_reasons: list[str] = []
            if family["failed_attempts"] >= METHOD_FAMILY_FAILURE_LIMIT:
                family_reasons.append("method-family failure limit reached")
            if family["no_progress_attempts"] >= METHOD_FAMILY_NO_PROGRESS_LIMIT:
                family_reasons.append("method-family no-progress limit reached")
            if family_reasons:
                family["status"] = "stopped"
                family["stop_reason"] = "; ".join(family_reasons)
                stop_evidence = list(family.get("stop_evidence_fingerprints", []))
                for fingerprint in (
                    family.get("method_change_evidence_fingerprint"),
                    family.get("lower_complexity_comparison_fingerprint"),
                    claim.get("causal_evidence_fingerprint_after"),
                ):
                    if valid_fingerprint(fingerprint) and fingerprint not in stop_evidence:
                        stop_evidence.append(fingerprint)
                family["stop_evidence_fingerprints"] = stop_evidence
            control["active_attempt"] = None
            control["status"] = "ready"
            control["stop_reason"] = None
            stop_reasons: list[str] = []
            if control["usage"]["failed_attempts"] >= control["limits"]["failed_attempts"]:
                stop_reasons.append("aggregate failed-attempt limit reached")
            if any(
                entry["count"] >= control["limits"]["equivalent_failures"]
                for entry in control["usage"]["failure_classes"]
            ):
                stop_reasons.append("equivalent-failure limit reached")
            if control["usage"]["no_progress_attempts"] >= control["limits"]["no_progress_attempts"]:
                stop_reasons.append("no-progress limit reached")
            if usage["active_attempt_seconds"] >= control["limits"]["active_attempt_seconds"]:
                stop_reasons.append("project-cumulative active-attempt time limit reached")
            if outcome == "failed" and result["failure_class"] in {
                "user-fixable",
                "ambiguous-external-write",
            }:
                stop_reasons.append(f"{result['failure_class']} requires authoritative recovery")
            if outcome == "aborted" and set(attempt.get("action_classes", [])) & {
                "external-write",
                "irreversible",
                "unattended",
            }:
                stop_reasons.append(
                    "aborted effectful attempt requires authoritative state or idempotency recovery"
                )
            if stop_reasons:
                control["status"] = "stopped"
                control["stop_reason"] = "; ".join(stop_reasons)
            control["revision"] = next_revision
            atomic_write_json(acceptance_path, data)
            return {
                "ok": True,
                "command": "attempt-finish",
                "revision": next_revision,
                "outcome": outcome,
                "receipt": receipt,
                "derived_acceptance_progress": derived_progress,
                "caller_acceptance_progress": result.get("acceptance_progress"),
                "method_family_status": family["status"],
                "method_family_stop_reason": family["stop_reason"],
                "status": control["status"],
                "stop_reason": control["stop_reason"],
            }
    except (OSError, ValueError) as exc:
        return {"ok": False, "command": "attempt-finish", "errors": [str(exc)]}


def normalize_earliest_divergence(value: str) -> str:
    return " ".join(value.split()).casefold()


def canonical_failure_fingerprint(
    attempt: dict[str, Any], earliest_divergence: str
) -> str:
    """Bind equivalent failures to structured state, never diagnostic wording."""
    return canonical_fingerprint(
        {
            "failure_identity_version": 3,
            "lineage_id": attempt.get("lineage_id"),
            "acceptance_outcome_id": attempt.get("acceptance_outcome_id"),
            "boundary_id": attempt.get("boundary_id"),
        }
    )


def canonical_failure_fingerprint_v2(
    attempt: dict[str, Any], earliest_divergence: str
) -> str:
    """Validate historic divergence-text-bound v2 identities."""
    return canonical_fingerprint(
        {
            "failure_identity_version": 2,
            "lineage_id": attempt.get("lineage_id"),
            "acceptance_outcome_id": attempt.get("acceptance_outcome_id"),
            "boundary_id": attempt.get("boundary_id"),
            "earliest_divergence": normalize_earliest_divergence(
                earliest_divergence
            ),
        }
    )


def canonical_failure_fingerprint_v1(
    lineage_id: object, acceptance_outcome_id: object, boundary_id: object
) -> str:
    """Validate historic v1 records without claiming their old grouping was sound."""
    return canonical_fingerprint(
        {
            "lineage_id": lineage_id,
            "acceptance_outcome_id": acceptance_outcome_id,
            "boundary_id": boundary_id,
        }
    )


def validate_attempt_result(
    result: dict[str, Any], attempt: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    if result.get("attempt_id") != attempt.get("id"):
        errors.append("attempt result attempt_id does not match the active reservation")
    outcome = result.get("outcome")
    if outcome not in {"passed", "failed", "aborted"}:
        errors.append("attempt result outcome must be passed, failed, or aborted")
    if not isinstance(result.get("acceptance_progress"), bool):
        errors.append("attempt result acceptance_progress must be boolean")
    if not nonempty(result.get("summary")):
        errors.append("attempt result summary must be non-empty")
    if outcome in {"passed", "failed"} and not nonempty(result.get("evidence_ref")):
        errors.append("attempt result evidence_ref must be non-empty")
    if outcome == "failed":
        if result.get("failure_class") not in FAILURE_CLASSES:
            errors.append("attempt result failure_class is invalid")
        if result.get("failure_class") == "reasoning-recoverable":
            boundary_id = str(attempt.get("boundary_id", ""))
            if "UNKNOWN" in boundary_id.upper():
                errors.append(
                    "reasoning-recoverable failure requires a known structured boundary"
                )
            if not nonempty(attempt.get("causal_evidence_ref")):
                errors.append(
                    "reasoning-recoverable failure requires causal evidence"
                )
        earliest_divergence = result.get("earliest_divergence")
        if not nonempty(earliest_divergence):
            errors.append("attempt result earliest_divergence must be non-empty")
        else:
            expected_fingerprint = canonical_failure_fingerprint(
                attempt, earliest_divergence
            )
            supplied_fingerprint = result.get("failure_fingerprint")
            if supplied_fingerprint is not None and not valid_fingerprint(
                supplied_fingerprint
            ):
                errors.append(
                    "attempt result failure_fingerprint must be a SHA-256 fingerprint when supplied"
                )
            elif (
                supplied_fingerprint is not None
                and supplied_fingerprint != expected_fingerprint
            ):
                errors.append(
                    "attempt result failure_fingerprint does not match the canonical failure identity"
                )
    return errors


def candidate_bind(
    root: str | Path,
    expected_revision: int,
    observed_evaluation_fingerprints: list[str],
) -> dict[str, object]:
    project_path, acceptance_path = project_paths(root)
    resolved_root = project_path.parent.parent
    try:
        with acceptance_lock(resolved_root):
            data, errors = load_json_object(acceptance_path, "ACCEPTANCE.json")
            if errors or data is None:
                return {"ok": False, "command": "candidate-bind", "errors": errors}
            if data.get("schema_version") != CURRENT_SCHEMA_VERSION:
                return {
                    "ok": False,
                    "command": "candidate-bind",
                    "errors": [f"candidate binding requires schema version {CURRENT_SCHEMA_VERSION}"],
                }
            if data.get("project_state") != "active":
                return {
                    "ok": False,
                    "command": "candidate-bind",
                    "errors": ["reopen the appropriate delivery stage before binding a new candidate"],
                }
            control = data["execution_control"]
            if control.get("revision") != expected_revision:
                return {
                    "ok": False,
                    "command": "candidate-bind",
                    "errors": [
                        f"stale expected revision {expected_revision}; current revision is {control.get('revision')}"
                    ],
                }
            if control.get("active_attempt") is not None:
                return {
                    "ok": False,
                    "command": "candidate-bind",
                    "errors": ["finish or abort the active attempt before rebinding the candidate"],
                }
            invalid_evaluations = [
                value for value in observed_evaluation_fingerprints if not valid_fingerprint(value)
            ]
            if invalid_evaluations:
                return {
                    "ok": False,
                    "command": "candidate-bind",
                    "errors": ["observed evaluation fingerprints must use SHA-256"],
                }
            fingerprint_errors: list[str] = []
            calculated = calculate_candidate_fingerprint(
                resolved_root,
                control["candidate"],
                fingerprint_errors,
                prefix="execution_control.candidate",
            )
            if fingerprint_errors or calculated is None:
                return {
                    "ok": False,
                    "command": "candidate-bind",
                    "errors": fingerprint_errors or ["candidate manifest is empty"],
                }
            changed = calculated != control["candidate"].get("fingerprint")
            receipt_evaluations = [
                receipt.get("evaluation_fingerprint")
                for receipt in control["gate_receipts"]
                if valid_fingerprint(receipt.get("evaluation_fingerprint"))
            ] if changed else []
            if changed:
                control["candidate"]["fingerprint"] = calculated
                control["gate_receipts"] = []
                active_ids = set(control["lineage"]["acceptance_ids"])
                for requirement in data.get("requirements", []):
                    if requirement.get("id") in active_ids:
                        requirement["status"] = "failing"
                        requirement["evidence"] = []
                        requirement["blocker"] = None
            diagnostics = control["diagnostic_evaluation_fingerprints"]
            for fingerprint in [*receipt_evaluations, *observed_evaluation_fingerprints]:
                if fingerprint not in diagnostics:
                    diagnostics.append(fingerprint)
            if changed or observed_evaluation_fingerprints:
                control["revision"] += 1
                atomic_write_json(acceptance_path, data)
            return {
                "ok": True,
                "command": "candidate-bind",
                "revision": control["revision"],
                "candidate_fingerprint": control["candidate"]["fingerprint"],
                "changed": changed,
                "receipts_invalidated": changed,
                "counters_preserved": True,
            }
    except (OSError, ValueError) as exc:
        return {"ok": False, "command": "candidate-bind", "errors": [str(exc)]}


def emit(result: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    print(json.dumps(result, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "init",
            "validate",
            "resume",
            "completion",
            "path",
            "scope-fingerprint",
            "candidate-bind",
            "attempt-begin",
            "attempt-finish",
            "hook-pre-claim",
            "hook-post-observe",
            "control-status",
            "state-reconcile",
            "state-transition",
            "failure-fingerprint-migrate",
            "limit-extend",
        ),
    )
    parser.add_argument("--root", default=".", help="Project root; defaults to the current directory")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--request", help="JSON attempt-request file for attempt-begin")
    parser.add_argument("--result", help="JSON attempt-result file for attempt-finish")
    parser.add_argument("--payload", help="JSON host-hook payload file")
    parser.add_argument("--expected-revision", type=int, help="Required optimistic control revision")
    parser.add_argument(
        "--observed-evaluation-fingerprint",
        action="append",
        default=[],
        help="Evaluation observed before a candidate change; repeat as needed",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "init":
        result = initialize(args.root)
    elif args.command == "path":
        project_path, acceptance_path = project_paths(args.root)
        result = {"ok": True, "paths": paths_payload(project_path, acceptance_path)}
    elif args.command == "scope-fingerprint":
        _, acceptance_path = project_paths(args.root)
        data, errors = load_json_object(acceptance_path, "ACCEPTANCE.json")
        result = (
            {"ok": False, "command": args.command, "errors": errors}
            if errors or data is None
            else {
                "ok": True,
                "command": args.command,
                "scope_fingerprint": calculate_scope_fingerprint(data),
            }
        )
    elif args.command == "candidate-bind":
        if args.expected_revision is None:
            result = {
                "ok": False,
                "command": args.command,
                "errors": ["--expected-revision is required"],
            }
        else:
            result = candidate_bind(
                args.root,
                args.expected_revision,
                args.observed_evaluation_fingerprint,
            )
    elif args.command == "attempt-begin":
        if args.expected_revision is None or not args.request:
            result = {
                "ok": False,
                "command": args.command,
                "errors": ["--request and --expected-revision are required"],
            }
        else:
            result = attempt_begin(args.root, args.request, args.expected_revision)
    elif args.command == "state-reconcile":
        if args.expected_revision is None or not args.request:
            result = {
                "ok": False,
                "command": args.command,
                "errors": ["--request and --expected-revision are required"],
            }
        else:
            result = state_reconcile(args.root, args.request, args.expected_revision)
    elif args.command == "state-transition":
        if args.expected_revision is None or not args.request:
            result = {"ok": False, "command": args.command, "errors": ["--request and --expected-revision are required"]}
        else:
            result = state_transition(args.root, args.request, args.expected_revision)
    elif args.command == "failure-fingerprint-migrate":
        if args.expected_revision is None or not args.request:
            result = {
                "ok": False,
                "command": args.command,
                "errors": ["--request and --expected-revision are required"],
            }
        else:
            result = failure_fingerprint_migrate(
                args.root, args.request, args.expected_revision
            )
    elif args.command == "limit-extend":
        if args.expected_revision is None or not args.request:
            result = {
                "ok": False,
                "command": args.command,
                "errors": ["--request and --expected-revision are required"],
            }
        else:
            result = limit_extend(args.root, args.request, args.expected_revision)
    elif args.command == "attempt-finish":
        if args.expected_revision is None or not args.result:
            result = {
                "ok": False,
                "command": args.command,
                "errors": ["--result and --expected-revision are required"],
            }
        else:
            result = attempt_finish(args.root, args.result, args.expected_revision)
    elif args.command in {"hook-pre-claim", "hook-post-observe"}:
        if not args.payload:
            result = {
                "ok": False,
                "command": args.command,
                "errors": ["--payload is required"],
            }
        else:
            payload, errors = load_json_object(
                Path(args.payload).expanduser().resolve(), "hook payload"
            )
            if errors or payload is None:
                result = {"ok": False, "command": args.command, "errors": errors}
            elif args.command == "hook-pre-claim":
                result = hook_pre_claim(args.root, payload)
            else:
                result = hook_post_observe(args.root, payload)
    elif args.command == "control-status":
        result = control_status(args.root)
    else:
        result = validate(args.root, mode=args.command)

    emit(result, args.json)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
