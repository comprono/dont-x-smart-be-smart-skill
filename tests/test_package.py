from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
INSTALLER = REPOSITORY_ROOT / "scripts" / "install.py"
STATE_SCRIPT = REPOSITORY_ROOT / "skills" / "outcome-integrity" / "scripts" / "project_outcome.py"
SKILL = REPOSITORY_ROOT / "skills" / "outcome-integrity" / "SKILL.md"
GLOBAL_RULES = REPOSITORY_ROOT / "global" / "AGENTS.snippet.md"
PROJECT_TEMPLATE = (
    REPOSITORY_ROOT
    / "skills"
    / "outcome-integrity"
    / "assets"
    / "PROJECT_OUTCOME.template.md"
)
ACCEPTANCE_TEMPLATE = (
    REPOSITORY_ROOT
    / "skills"
    / "outcome-integrity"
    / "assets"
    / "ACCEPTANCE.template.json"
)
ATTEMPT_REQUEST_TEMPLATE = (
    REPOSITORY_ROOT
    / "skills"
    / "outcome-integrity"
    / "assets"
    / "ATTEMPT_REQUEST.template.json"
)
ATTEMPT_RESULT_TEMPLATE = (
    REPOSITORY_ROOT
    / "skills"
    / "outcome-integrity"
    / "assets"
    / "ATTEMPT_RESULT.template.json"
)
OPENAI_YAML = (
    REPOSITORY_ROOT / "skills" / "outcome-integrity" / "agents" / "openai.yaml"
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def project_text(
    *,
    updated: str = "2026-07-16T10:00:00Z",
    state: str = "active",
    current_id: str = "REQ-001",
) -> str:
    return f"""<!-- Managed with the outcome-integrity skill. Keep this current, not chronological. -->
# Project Outcome

Updated: {updated}
State: {state}

## North Star
- North-star outcome: Produce the complete requested verified result.
- Current delivery stage: Deliver the first coherent useful release.
- Stage completion boundary: All declared stage capabilities pass; later stages remain outside it.
- User-visible proof: The real user path passes.
- Active acceptance slice: Exercise one bounded real path.
- Slice proof limits: This path does not prove unrelated capabilities.
- Methods, not outcomes: Testing and inspection.
- Why it matters: The user needs the real outcome, not proxy activity.

## Done Means
- Authority: .codex/ACCEPTANCE.json
- Summary: The real user path passes with sufficient evidence.

## User Intent
- Priorities: Outcome first.
- Working preferences: Concise reporting.
- Explicit corrections: None.
- Non-negotiables: Preserve verified behavior.

## Work Map
### Critical Path
- Repair the failed real path.
### Add-ons
- None.
### Non-goals
- Unrelated refactors.

## Verified State
- Real path fails | Evidence: reproduction | Verified: 2026-07-16T10:00:00Z

## Context Pointers
- Architecture or project map: README.md
- Active specification: .codex/ACCEPTANCE.json
- Verification commands: python -m unittest
- Evidence roots: tests

## Assumptions To Test
- State transition is invalid | Falsifier: valid trace | Next check: trace it

## Decisions
- Trace before editing | Why: repeated failure | Revisit when: reproduced

## Failure Memory
- Symptom patch | Class: semantic | Evidence: reproduction | Invariant: trace state | Do not repeat: blind retry

## Causal Control
- Known-good reference: Last accepted real path.
- Failing reference: Current reproduction.
- Earliest divergent transition: Real producer crosses the declared decision boundary incorrectly.
- Production-path proof: Real producer to decision boundary to acceptance observation.
- Stop conditions and attempt limits: Stop after two equivalent acceptance failures.
- Forbidden bypasses: Do not inject already-correct post-boundary state.
- Mutable execution-control ledger: .codex/ACCEPTANCE.json#execution_control (sole authority)

## Current Slice
- Delivery Stage ID: {'none' if state == 'complete' else 'STAGE-001'}
- Acceptance ID: {current_id}
- Objective: Reproduce the invalid transition.
- Acceptance evidence: Deterministic failure at one boundary.
- Protect: Existing passing behavior.
- Status: {state}

## Next
- Action: Trace the transition.
- Why now: It tests the root cause.
- Blocker and recovery: None.
"""


def acceptance_data(
    *,
    updated: str = "2026-07-16T10:00:00Z",
    project_state: str = "active",
    current_id: str | None = "REQ-001",
    status: str = "failing",
    minimum_level: str = "end-to-end",
    evidence_level: str | None = None,
    blocker: dict[str, str] | None = None,
    schema_version: int = 6,
) -> dict[str, object]:
    evidence = []
    if evidence_level:
        evidence_entry: dict[str, object] = {
            "level": evidence_level,
            "ref": "tests/evidence/result.json",
            "summary": "The reproducible path produced the expected result.",
            "verified_utc": updated,
        }
        if schema_version >= 2:
            evidence_entry["step_ids"] = ["STEP-001"]
            evidence_entry["identity_ids"] = ["ENTITY-001"]
        evidence.append(evidence_entry)

    requirement: dict[str, object] = {
        "id": "REQ-001",
        "description": "The real user path passes.",
        "required": True,
        "status": status,
        "minimum_evidence_level": minimum_level,
        "acceptance_steps": ["Exercise the real path and inspect the result."],
        "evidence": evidence,
        "blocker": blocker,
    }
    data: dict[str, object] = {
        "schema_version": schema_version,
        "updated_utc": updated,
        "project_state": project_state,
        "current_slice_requirement_id": current_id,
        "requirements": [requirement],
    }
    if schema_version >= 2:
        data["project_identity"] = {
            "id": "test-project",
            "root_markers": ["project.marker"],
        }
        data["outcome_capabilities"] = [
            {
                "id": "CAP-001",
                "description": "The complete real path works.",
                "required": True,
            }
        ]
        data["identity_requirements"] = [
            {
                "id": "ENTITY-001",
                "description": "The explicitly requested target.",
                "substitutable": False,
            }
        ]
        requirement["capability_ids"] = ["CAP-001"]
        requirement["identity_ids"] = ["ENTITY-001"]
        requirement["proof_scope"] = "The bounded real path for the declared target."
        requirement["proof_limits"] = "It does not establish any undeclared capability."
        requirement["acceptance_steps"] = [
            {
                "id": "STEP-001",
                "description": "Exercise the real path and inspect the result.",
            }
        ]
        requirement["counterevidence"] = []
    if schema_version >= 3:
        data["outcome_hierarchy"] = {
            "north_star": {
                "id": "OUTCOME-001",
                "description": "Produce the complete requested verified result.",
                "status": "active" if project_state != "complete" else "achieved",
            },
            "delivery_stages": [
                {
                    "id": "STAGE-001",
                    "parent_outcome_id": "OUTCOME-001",
                    "description": "Deliver the first coherent useful release.",
                    "required": True,
                    "status": "complete" if project_state == "complete" else "active",
                }
            ],
            "current_stage_id": None if project_state == "complete" else "STAGE-001",
        }
        data["outcome_capabilities"][0]["stage_id"] = "STAGE-001"
        requirement["stage_id"] = "STAGE-001"
    if schema_version >= 4:
        data["outcome_hierarchy"]["north_star"]["fitness_dimensions"] = [
            {"id": "FIT-UTILITY", "description": "Useful verified output advances."},
            {"id": "FIT-EFFICIENCY", "description": "Resources and time remain proportionate."},
        ]
        data["outcome_hierarchy"]["delivery_stages"][0]["preserves_capability_ids"] = ["CAP-001"]
        data["outcome_capabilities"][0]["preservation"] = "permanent"
        requirement["gate_tiers"] = ["change"]
        requirement["system_scope"] = "interaction" if schema_version >= 5 else "component"
        requirement["minimum_evidence_level"] = "focused-test"
        if schema_version >= 5:
            requirement["proof_path"] = {
                "origin": "The real upstream producer.",
                "boundary": "The production decision under test.",
                "observation": "The downstream acceptance effect.",
                "fidelity": "production-shaped",
            }
        pre_release = json.loads(json.dumps(requirement))
        pre_release["id"] = "REQ-PRE-RELEASE"
        pre_release["description"] = "The representative interaction path passes."
        pre_release["gate_tiers"] = ["pre-release"]
        pre_release["system_scope"] = "interaction"
        pre_release["minimum_evidence_level"] = "integration"
        if schema_version >= 5:
            pre_release["proof_path"] = {
                "origin": "A representative real input.",
                "boundary": "The production integration boundary.",
                "observation": "The canary acceptance effect.",
                "fidelity": "production-shaped",
            }
        pre_release["acceptance_steps"] = [{"id": "STEP-PRE-RELEASE", "description": "Exercise the interaction path."}]
        release = json.loads(json.dumps(requirement))
        release["id"] = "REQ-RELEASE"
        release["description"] = "The complete user flow passes."
        release["gate_tiers"] = ["release"]
        release["system_scope"] = "end-to-end"
        release["minimum_evidence_level"] = "end-to-end"
        if schema_version >= 5:
            release["proof_path"] = {
                "origin": "The real user entrypoint.",
                "boundary": "The complete production flow.",
                "observation": "The user-visible outcome.",
                "fidelity": "production",
            }
        release["acceptance_steps"] = [{"id": "STEP-RELEASE", "description": "Exercise the complete user flow."}]
        if evidence_level:
            pre_release["evidence"][0]["step_ids"] = ["STEP-PRE-RELEASE"]
            release["evidence"][0]["step_ids"] = ["STEP-RELEASE"]
        data["requirements"].extend([pre_release, release])
        data["capability_floors"] = [
            {
                "id": "FLOOR-001",
                "capability_id": "CAP-001",
                "invariant": "The complete real path keeps working.",
                "fitness_dimension_ids": ["FIT-UTILITY", "FIT-EFFICIENCY"],
                "proof_ladder": {
                    "change": ["REQ-001"],
                    "pre-release": ["REQ-PRE-RELEASE"],
                    "release": ["REQ-RELEASE"],
                },
                "optional_supporting_state": [],
                "independence_requirement_ids": [],
            }
        ]
    if schema_version >= 6:
        requirement["predecessor_requirement_ids"] = []
        pre_release["predecessor_requirement_ids"] = ["REQ-001"]
        release["predecessor_requirement_ids"] = ["REQ-001", "REQ-PRE-RELEASE"]
        placeholder = "sha256:" + "0" * 64
        receipts = []
        if evidence_level:
            receipt_specs = (
                (requirement, "RECEIPT-CHANGE", "change"),
                (pre_release, "RECEIPT-PRE-RELEASE", "pre-release"),
                (release, "RECEIPT-RELEASE", "release"),
            )
            for gate, receipt_id, tier in receipt_specs:
                gate["evidence"][0].update({
                    "candidate_fingerprint": placeholder,
                    "lineage_id": "LINEAGE-001",
                    "gate_receipt_id": receipt_id,
                    "evaluation_fingerprint": None,
                    "evaluation_role": "none",
                })
                receipts.append({
                    "id": receipt_id,
                    "requirement_id": gate["id"],
                    "tier": tier,
                    "lineage_id": "LINEAGE-001",
                    "candidate_fingerprint": placeholder,
                    "evidence_ref": "tests/evidence/result.json",
                    "summary": "The declared gate passed on the bound candidate.",
                    "verified_utc": updated,
                    "evaluation_fingerprint": None,
                    "evaluation_role": "none",
                })
        data["execution_control"] = {
            "revision": 0,
            "reconciled_utc": updated,
            "lineage": {
                "id": "LINEAGE-001",
                "stage_id": "STAGE-001",
                "acceptance_ids": ["REQ-001", "REQ-PRE-RELEASE", "REQ-RELEASE"],
                "scope_fingerprint": placeholder,
            },
            "candidate": {
                "fingerprint": placeholder,
                "manifest_paths": ["project.marker"],
                "external_fingerprints": [],
            },
            "status": "closed" if project_state == "complete" else "ready",
            "limits": {
                "total_attempts": 6,
                "failed_attempts": 4,
                "equivalent_failures": 2,
                "expensive_attempts": 2,
                "support_attempts": 2,
                "no_progress_attempts": 2,
                "total_tool_calls": 24,
                "support_tool_calls": 8,
                "support_no_progress_calls": 4,
                "active_attempt_seconds": 3600,
                "spawned_workers": 2,
                "scope_growth_actions": 1,
                "direct_delivery_reserved_calls": 6,
                "max_path_touches": 12,
                "max_touches_per_path": 3,
            },
            "usage": {
                "total_attempts": 0,
                "failed_attempts": 0,
                "expensive_attempts": 0,
                "support_attempts": 0,
                "no_progress_attempts": 0,
                "total_tool_calls": 0,
                "support_tool_calls": 0,
                "support_no_progress_calls": 0,
                "active_attempt_seconds": 0,
                "spawned_workers": 0,
                "scope_growth_actions": 0,
                "path_touches": 0,
                "hot_path_touches": 0,
                "path_counts": {},
                "method_families": [],
                "failure_classes": [],
            },
            "gate_receipts": receipts,
            "diagnostic_evaluation_fingerprints": [],
            "prerequisites": [],
            "authorizations": [],
            "active_attempt": None,
            "stop_reason": None,
            "support_stop_reason": None,
        }
    return data

def write_state(
    root: Path,
    project: str,
    acceptance: dict[str, object],
    *,
    refresh_control: bool = True,
) -> None:
    state_dir = root / ".codex"
    state_dir.mkdir(parents=True, exist_ok=True)
    (root / "project.marker").write_text("test project\n", encoding="utf-8")
    if acceptance.get("schema_version") == 6 and refresh_control:
        state_module = load_module(STATE_SCRIPT, "project_outcome_fixture")
        control = acceptance["execution_control"]
        candidate_fingerprint = state_module.calculate_candidate_fingerprint(
            root, control["candidate"]
        )
        control["candidate"]["fingerprint"] = candidate_fingerprint
        control["lineage"]["scope_fingerprint"] = state_module.calculate_scope_fingerprint(
            acceptance
        )
        for receipt in control["gate_receipts"]:
            receipt["candidate_fingerprint"] = candidate_fingerprint
        for requirement in acceptance["requirements"]:
            for evidence in requirement.get("evidence", []):
                if "candidate_fingerprint" in evidence:
                    evidence["candidate_fingerprint"] = candidate_fingerprint
    (state_dir / "PROJECT_OUTCOME.md").write_text(project, encoding="utf-8")
    (state_dir / "ACCEPTANCE.json").write_text(
        json.dumps(acceptance, indent=2) + "\n", encoding="utf-8"
    )


def attempt_request(
    state: dict[str, object],
    *,
    principal: str = "Codex",
    requirement_id: str = "REQ-001",
    tier: str = "change",
    method_family_id: str = "METHOD-001",
    prior_method_family_id: str | None = None,
    method_change_evidence_ref: str | None = None,
    lower_complexity_comparison_ref: str | None = None,
    acceptance_outcome_id: str = "OUTCOME-001",
    boundary_id: str = "BOUNDARY-001",
    cost_class: str = "cheap",
    action_classes: list[str] | None = None,
    scope_growth: str = "none",
    allowed_paths: list[str] | None = None,
    tool_name: str = "exec_command",
    cwd_relative: str = ".",
    tool_input: object = None,
    tool_input_fingerprint: str | None = None,
    external_run_id: str | None = "run-a",
    evaluation_fingerprint: str | None = None,
    evaluation_role: str = "none",
    prerequisite_ids: list[str] | None = None,
    no_prerequisites_reason: str | None = "No hard downstream dependency applies to this local gate.",
    authorization_id: str | None = None,
    target_identity_ids: list[str] | None = None,
    action: str = "Run the declared generic gate.",
    effect: str = "Read-only local proof.",
    context_fingerprint: str = "sha256:" + "1" * 64,
    causal_evidence_ref: str | None = "tests/evidence/attempt.json",
) -> dict[str, object]:
    if tool_input is None:
        tool_input = {"cmd": "run-generic-gate"}
    if tool_input_fingerprint is None:
        encoded = json.dumps(
            tool_input, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        tool_input_fingerprint = "sha256:" + hashlib.sha256(encoded).hexdigest()
    return {
        "principal": principal,
        "requirement_id": requirement_id,
        "tier": tier,
        "method_family_id": method_family_id,
        "prior_method_family_id": prior_method_family_id,
        "method_change_evidence_ref": method_change_evidence_ref,
        "lower_complexity_comparison_ref": lower_complexity_comparison_ref,
        "acceptance_outcome_id": acceptance_outcome_id,
        "boundary_id": boundary_id,
        "cost_class": cost_class,
        "action_classes": action_classes or ["local", "proof"],
        "scope_growth": scope_growth,
        "allowed_paths": allowed_paths or [],
        "tool_binding": {
            "tool_name": tool_name,
            "cwd_relative": cwd_relative,
            "tool_input_fingerprint": tool_input_fingerprint,
            "max_uses": 1,
        },
        "candidate_fingerprint": state["execution_control"]["candidate"]["fingerprint"],
        "prerequisite_ids": prerequisite_ids or [],
        "no_prerequisites_reason": no_prerequisites_reason,
        "authorization_id": authorization_id,
        "target_identity_ids": target_identity_ids or [],
        "action": action,
        "effect": effect,
        "context_fingerprint": context_fingerprint,
        "evaluation_fingerprint": evaluation_fingerprint,
        "evaluation_role": evaluation_role,
        "external_run_id": external_run_id,
        "causal_evidence_ref": causal_evidence_ref,
    }


def attempt_result(
    *,
    attempt_id: str,
    outcome: str,
    progress: bool,
    failure_class: str | None = None,
    earliest_divergence: str = "The declared transition produced the wrong acceptance effect.",
) -> dict[str, object]:
    result: dict[str, object] = {
        "attempt_id": attempt_id,
        "outcome": outcome,
        "acceptance_progress": progress,
        "summary": f"Generic attempt {outcome}.",
        "evidence_ref": "tests/evidence/attempt.json" if outcome != "aborted" else None,
    }
    if outcome == "failed":
        result.update({
            "failure_class": failure_class or "semantic",
            "earliest_divergence": earliest_divergence,
        })
    return result


def write_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.state = load_module(STATE_SCRIPT, "project_outcome")
        cls.installer = load_module(INSTALLER, "outcome_integrity_installer")

    def test_skill_metadata_and_required_policies_are_present(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nname: outcome-integrity\n"))
        self.assertNotIn("REPLACE_ME", text)
        for phrase in (
            ".codex/ACCEPTANCE.json",
            "Classify Failure Before Retrying",
            "Admit Delegation Only When It Helps",
            "completion --root",
        ):
            self.assertIn(phrase, text)

    def test_outcome_framing_precedes_methods_and_stale_contracts(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        global_rules = GLOBAL_RULES.read_text(encoding="utf-8")
        template = PROJECT_TEMPLATE.read_text(encoding="utf-8")
        openai_yaml = OPENAI_YAML.read_text(encoding="utf-8")

        for phrase in (
            "Build A Parented Outcome Stack",
            "If every method succeeded",
            "Never rewrite a parent to match a convenient child",
            "parent corrections flow down immediately",
            "replan from the outcome",
        ):
            self.assertIn(phrase, skill)

        for phrase in (
            "parented stack",
            "A passing slice does not complete its stage",
            "propagate them through dependent descendants",
        ):
            self.assertIn(phrase, global_rules)

        self.assertIn("- North-star outcome:", template)
        self.assertIn("- Current delivery stage:", template)
        self.assertIn("- Stage completion boundary:", template)
        self.assertIn("- User-visible proof:", template)
        self.assertIn("- Active acceptance slice:", template)
        self.assertIn("- Slice proof limits:", template)
        self.assertIn("- Methods, not outcomes:", template)
        self.assertIn("## Causal Control", template)
        self.assertIn("- Earliest divergent transition:", template)
        self.assertIn("- Stop conditions and attempt limits:", template)
        self.assertIn("Use $outcome-integrity", openai_yaml)

    def test_simple_questions_receive_a_direct_plain_language_answer_first(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        global_rules = GLOBAL_RULES.read_text(encoding="utf-8")
        readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
        openai_yaml = OPENAI_YAML.read_text(encoding="utf-8")

        for phrase in (
            "Communicate For Productive Understanding",
            "plain-language conclusion in the first sentence",
            "truthfully, usefully, proportionately, and without unnecessary agitation",
            "Never answer \"yes, exactly\"",
        ):
            self.assertIn(phrase, skill)

        self.assertIn("plain conclusion first", global_rules)
        self.assertIn("direct plain-language conclusion first", readme)
        self.assertIn("Use $outcome-integrity", openai_yaml)

    def test_active_projects_keep_ownership_across_questions_and_corrections(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        global_rules = GLOBAL_RULES.read_text(encoding="utf-8")
        readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
        openai_yaml = OPENAI_YAML.read_text(encoding="utf-8")

        for phrase in (
            "Maintain Continuous Project Ownership",
            "Corrections update the contract; questions do not cancel authorized work",
            "Interpret noisy wording from context",
            "continue the next safe authorized project action in the same turn",
            'Do not make the user repeatedly say "do it", "continue", or "what next"',
            "am I leaving the user to manage the next obvious action Codex owns",
        ):
            self.assertIn(phrase, skill)

        for phrase in (
            "Treat each message as an update to the active objective",
            "Maintain one compact parented stack",
            "After answering an interruption, apply that discernment gate",
            "do not make the user repeatedly say",
        ):
            self.assertIn(phrase, global_rules)

        self.assertIn("Questions and corrections update that project", readme)
        self.assertIn('instead of waiting for another "do it" instruction', readme)
        self.assertIn("advance the next efficient authorized slice", openai_yaml)

    def test_confusing_reply_loops_are_stopped_and_status_layers_are_separated(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        global_rules = GLOBAL_RULES.read_text(encoding="utf-8")
        readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
        openai_yaml = OPENAI_YAML.read_text(encoding="utf-8")

        for phrase in (
            "Communicate For Productive Understanding",
            "Material transition:",
            "Typed status:",
            "Next owned action:",
            "Never let `Done`, `working`, `complete`, `blocked`, `restart`, `plugin`, `local`, or `installed` refer to multiple layers in one sentence",
            "If the user says the answer is confusing",
            "`Next` means an agent-owned action",
        ):
            self.assertIn(phrase, skill)

        self.assertIn("Separate product, tooling, model/restart", global_rules)
        self.assertIn("conclusion, material distinction, and next owned action", global_rules)
        self.assertIn("Continuing an explanation loop", readme)
        self.assertIn("short conclusion, distinction, and next-action frame", readme)
        self.assertIn("preserve the parented outcome stack", openai_yaml)

    def test_recurring_work_has_a_bounded_operational_envelope(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        global_rules = GLOBAL_RULES.read_text(encoding="utf-8")
        template = PROJECT_TEMPLATE.read_text(encoding="utf-8")
        readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
        openai_yaml = OPENAI_YAML.read_text(encoding="utf-8")

        for phrase in (
            "Bound Autonomous And Recurring Work",
            "Continuation never authorizes unbounded resources",
            "Observe often; mutate only on state change",
            "resources grow without acceptance progress",
        ):
            self.assertIn(phrase, skill)

        for phrase in (
            "Before recurring, unattended, retrying, or automatic work",
            "idempotency",
            "exact-once",
        ):
            self.assertIn(phrase, global_rules)

        for phrase in (
            "## Operational Envelope",
            "- Progress signal and side-effect key:",
            "- Resource budget, reserve, and retention:",
            "- No-progress stop, restart, cancellation, and recovery:",
        ):
            self.assertIn(phrase, template)

        self.assertIn("unattended loops consume storage", readme)
        self.assertIn("earliest divergent transition", openai_yaml)

    def test_causal_boundary_prompt_ownership_and_failure_equivalence_are_explicit(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        global_rules = GLOBAL_RULES.read_text(encoding="utf-8")
        for phrase in (
            "Treat pasted instructions by conversational function",
            "Match the explanation requested",
            "Lock the earliest transition where known-good and failing paths diverge",
            "fixture that injects already-correct post-boundary state",
            "Equivalence is determined by the acceptance outcome and earliest divergent transition",
            "A triggered stop ends that authorization",
        ):
            self.assertIn(phrase, skill)
        for phrase in (
            "chronology, rationale, responsibility",
            "cross the production boundary",
            "earliest divergence match",
            "Record explicit `do not`",
        ):
            self.assertIn(phrase, global_rules)

    def test_product_proof_identity_and_conflict_rules_are_generic(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        global_rules = GLOBAL_RULES.read_text(encoding="utf-8")

        for phrase in (
            "Preserve Exact Identity And Contradictory Evidence",
            "A matching display name, interface, capability, output, or family is not proof of equivalence",
            "preserve both observations as counterevidence",
            "A fallback advances only requirements it independently satisfies",
        ):
            self.assertIn(phrase, skill)

        for phrase in (
            "parented stack",
            "A passing slice does not complete its stage",
            "Treat named people, accounts, tools, providers",
            "preserve unresolved counterevidence",
            "Verify root markers",
        ):
            self.assertIn(phrase, global_rules)

    def test_steady_action_contract_is_generic_and_token_bounded(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        global_rules = GLOBAL_RULES.read_text(encoding="utf-8")

        for phrase in (
            "Discern Before Persisting",
            "Do not confuse momentum with focus",
            "This never reduces responsibility, acceptance, or evidence quality",
            "return to the current acceptance gap",
            "Analytical fixation",
            "Restless activity",
            "Avoidant inaction",
            "environment, acting agent, tools and access, distinct efforts, and external conditions",
            "remaining uncertainty is tolerable and visible",
        ):
            self.assertIn(phrase, skill)

        for phrase in (
            "Discern before persisting",
            "Non-attachment to a preferred result or method never weakens outcome accountability",
            "Return wandering attention",
            "truthfully, usefully, proportionately, and without unnecessary agitation",
            "do not assign total credit or blame to one agent without evidence",
        ):
            self.assertIn(phrase, global_rules)

        self.assertLessEqual(len(skill.split()), 3800)
        self.assertLessEqual(len(global_rules.split()), 760)
        for project_specific in ("Bhagavad", "Krishna", "Arjuna", "Claude", "Antigravity"):
            self.assertNotIn(project_specific.casefold(), skill.casefold())
            self.assertNotIn(project_specific.casefold(), global_rules.casefold())


    def test_schema_v6_template_declares_proof_and_execution_control_fields(self) -> None:
        acceptance_template = ACCEPTANCE_TEMPLATE.read_text(encoding="utf-8")
        for phrase in (
            '"schema_version": 6',
            '"project_identity"',
            '"outcome_hierarchy"',
            '"delivery_stages"',
            '"parent_outcome_id"',
            '"current_stage_id"',
            '"stage_id"',
            '"fitness_dimensions"',
            '"preserves_capability_ids"',
            '"preservation": "permanent"',
            '"capability_floors"',
            '"proof_ladder"',
            '"gate_tiers"',
            '"system_scope"',
            '"proof_path"',
            '"origin"',
            '"boundary"',
            '"observation"',
            '"fidelity": "production-shaped"',
            '"outcome_capabilities"',
            '"identity_requirements"',
            '"capability_ids"',
            '"identity_ids"',
            '"proof_scope"',
            '"proof_limits"',
            '"counterevidence"',
            '"execution_control"',
            '"scope_fingerprint"',
            '"candidate"',
            '"predecessor_requirement_ids"',
            '"gate_receipts"',
            '"diagnostic_evaluation_fingerprints"',
            '"prerequisites"',
            '"authorizations"',
            '"active_attempt"',
        ):
            self.assertIn(phrase, acceptance_template)

    def test_attempt_templates_expose_the_complete_atomic_contract(self) -> None:
        request = json.loads(ATTEMPT_REQUEST_TEMPLATE.read_text(encoding="utf-8"))
        result = json.loads(ATTEMPT_RESULT_TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual(
            set(request),
            {
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
                "external_run_id",
                "causal_evidence_ref",
            },
        )
        self.assertEqual(
            set(result),
            {
                "attempt_id",
                "outcome",
                "acceptance_progress",
                "summary",
                "evidence_ref",
                "failure_class",
                "failure_fingerprint",
                "earliest_divergence",
            },
        )
        skill = SKILL.read_text(encoding="utf-8")
        readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
        for name in (ATTEMPT_REQUEST_TEMPLATE.name, ATTEMPT_RESULT_TEMPLATE.name):
            self.assertIn(name, skill)
            self.assertIn(name, readme)

    def test_project_and_acceptance_templates_share_the_initial_slice(self) -> None:
        acceptance = json.loads(ACCEPTANCE_TEMPLATE.read_text(encoding="utf-8"))
        project = PROJECT_TEMPLATE.read_text(encoding="utf-8")
        expected = acceptance["current_slice_requirement_id"]
        self.assertIn(f"- Acceptance ID: {expected}", project)
        ledger_pointer = (
            "- Mutable execution-control ledger: "
            ".codex/ACCEPTANCE.json#execution_control (sole authority)"
        )
        self.assertIn(ledger_pointer, project)
        self.assertIn(ledger_pointer, SKILL.read_text(encoding="utf-8"))
        self.assertIn(
            ledger_pointer, (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
        )

    def assert_no_installer_artifacts(self, codex_home: Path) -> None:
        skills = codex_home / "skills"
        skill_artifacts = list(skills.glob(".outcome-integrity.*")) if skills.exists() else []
        global_artifacts = list(codex_home.glob(".AGENTS.md.*"))
        lock_artifacts = list(codex_home.glob(".outcome-integrity-install.lock*"))
        self.assertEqual(skill_artifacts + global_artifacts + lock_artifacts, [])

    def test_installer_is_idempotent_prunes_stale_entries_and_has_exact_parity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary) / ".codex"
            codex_home.mkdir()
            agents = codex_home / "AGENTS.md"
            agents.write_bytes(b"# Existing rule\r\n\r\nKeep this line.\r\n")

            command = [sys.executable, str(INSTALLER), "--codex-home", str(codex_home)]
            subprocess.run(command, check=True, capture_output=True, text=True)
            installed = codex_home / "skills" / "outcome-integrity"
            (installed / "stale-managed-file.txt").write_text("obsolete\n", encoding="utf-8")
            (installed / "stale-empty-directory").mkdir()
            subprocess.run(command, check=True, capture_output=True, text=True)

            merged = agents.read_bytes().decode("utf-8")
            self.assertTrue((installed / "SKILL.md").is_file())
            self.assertTrue((installed / "assets" / "ACCEPTANCE.template.json").is_file())
            self.assertTrue((installed / "assets" / "ATTEMPT_REQUEST.template.json").is_file())
            self.assertTrue((installed / "assets" / "ATTEMPT_RESULT.template.json").is_file())
            self.assertFalse((installed / "stale-managed-file.txt").exists())
            self.assertFalse((installed / "stale-empty-directory").exists())
            source = REPOSITORY_ROOT / "skills" / "outcome-integrity"
            self.assertEqual(
                self.installer.canonical_tree_manifest(installed),
                self.installer.canonical_tree_manifest(source),
            )
            self.assertIn("Keep this line.", merged)
            self.assertEqual(merged.count("<!-- outcome-integrity:start -->"), 1)
            self.assertEqual(merged.count("<!-- outcome-integrity:end -->"), 1)
            start = merged.index("<!-- outcome-integrity:start -->")
            end = merged.index("<!-- outcome-integrity:end -->", start) + len("<!-- outcome-integrity:end -->")
            self.assertEqual(
                merged[start:end].replace("\r\n", "\n"),
                GLOBAL_RULES.read_text(encoding="utf-8").strip().replace("\r\n", "\n"),
            )
            self.assert_no_installer_artifacts(codex_home)

    def test_managed_block_update_preserves_unrelated_crlf_bytes_and_collapses_duplicates(self) -> None:
        snippet = GLOBAL_RULES.read_text(encoding="utf-8")
        old_block = (
            "<!-- outcome-integrity:start -->\r\n"
            "old managed rule\r\n"
            "<!-- outcome-integrity:end -->"
        )
        prefix = "# Before  \r\n\r\n"
        middle = "\r\n  \t\r\n# Between  \r\n\r\n"
        suffix = "\r\n \t\r\n# After  \r\n"
        merged = self.installer.merge_managed_block(
            prefix + old_block + middle + old_block + suffix,
            snippet,
        )
        start = merged.index("<!-- outcome-integrity:start -->")
        end = merged.index("<!-- outcome-integrity:end -->", start) + len(
            "<!-- outcome-integrity:end -->"
        )
        self.assertEqual(merged[:start], prefix)
        self.assertEqual(merged[end:], middle + suffix)
        self.assertEqual(merged.count("<!-- outcome-integrity:start -->"), 1)
        self.assertNotIn("\n", merged[start:end].replace("\r\n", ""))

    def test_installer_rejects_source_target_overlap_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package_root = Path(temporary) / "package"
            source = package_root / "skills" / "outcome-integrity"
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text("generic skill\n", encoding="utf-8")
            before = self.installer.canonical_tree_manifest(source)
            with mock.patch.object(self.installer, "_repository_root", return_value=package_root):
                with self.assertRaisesRegex(ValueError, "overlap"):
                    self.installer.install(package_root, skip_global_rules=True)
            self.assertEqual(self.installer.canonical_tree_manifest(source), before)
            self.assertFalse((package_root / "AGENTS.md").exists())

    def test_installer_refuses_linked_skill_file_without_touching_external_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            codex_home = root / ".codex"
            self.installer.install(codex_home)
            installed = codex_home / "skills" / "outcome-integrity"
            external = root / "external-sentinel.txt"
            external.write_bytes(b"must stay unchanged\n")
            linked_file = installed / "SKILL.md"
            linked_file.unlink()
            try:
                os.symlink(external, linked_file)
            except OSError as exc:
                self.skipTest(f"File symlinks are unavailable in this environment: {exc}")
            agents_before = (codex_home / "AGENTS.md").read_bytes()
            with self.assertRaisesRegex(ValueError, "symlink|junction|reparse"):
                self.installer.install(codex_home)
            self.assertEqual(external.read_bytes(), b"must stay unchanged\n")
            self.assertEqual((codex_home / "AGENTS.md").read_bytes(), agents_before)

    def test_installer_refuses_nested_directory_junction_without_touching_external_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            codex_home = root / ".codex"
            self.installer.install(codex_home)
            installed = codex_home / "skills" / "outcome-integrity"
            external = root / "external-directory"
            external.mkdir()
            sentinel = external / "sentinel.txt"
            sentinel.write_bytes(b"must stay unchanged\n")
            linked_directory = installed / "assets"
            shutil.rmtree(linked_directory)
            try:
                if os.name == "nt":
                    result = subprocess.run(
                        ["cmd", "/c", "mklink", "/J", str(linked_directory), str(external)],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode != 0:
                        self.skipTest(f"Directory junctions are unavailable: {result.stderr or result.stdout}")
                else:
                    os.symlink(external, linked_directory, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"Directory links are unavailable in this environment: {exc}")
            with self.assertRaisesRegex(ValueError, "symlink|junction|reparse"):
                self.installer.install(codex_home)
            self.assertEqual(sentinel.read_bytes(), b"must stay unchanged\n")
            self.assertFalse((external / "ACCEPTANCE.template.json").exists())

    def test_installer_refuses_linked_agents_file_without_touching_external_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            codex_home = root / ".codex"
            self.installer.install(codex_home)
            installed = codex_home / "skills" / "outcome-integrity"
            installed_before = self.installer.canonical_tree_manifest(installed)
            agents = codex_home / "AGENTS.md"
            agents.unlink()
            external = root / "external-agents.md"
            external.write_bytes(b"external rules\n")
            try:
                os.symlink(external, agents)
            except OSError as exc:
                self.skipTest(f"File symlinks are unavailable in this environment: {exc}")
            with self.assertRaisesRegex(ValueError, "symlink|junction|reparse"):
                self.installer.install(codex_home)
            self.assertEqual(external.read_bytes(), b"external rules\n")
            self.assertEqual(self.installer.canonical_tree_manifest(installed), installed_before)

    def test_staging_failure_preserves_previous_installation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary) / ".codex"
            self.installer.install(codex_home)
            installed = codex_home / "skills" / "outcome-integrity"
            (installed / "previous-only.txt").write_bytes(b"previous installation\n")
            before = self.installer.canonical_tree_manifest(installed)
            agents_before = (codex_home / "AGENTS.md").read_bytes()
            with mock.patch.object(
                self.installer.shutil, "copytree", side_effect=OSError("injected staging failure")
            ):
                with self.assertRaisesRegex(OSError, "injected staging failure"):
                    self.installer.install(codex_home)
            self.assertEqual(self.installer.canonical_tree_manifest(installed), before)
            self.assertEqual((codex_home / "AGENTS.md").read_bytes(), agents_before)
            self.assert_no_installer_artifacts(codex_home)

    def test_skill_activation_failure_rolls_back_previous_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary) / ".codex"
            self.installer.install(codex_home)
            installed = codex_home / "skills" / "outcome-integrity"
            (installed / "previous-only.txt").write_bytes(b"previous installation\n")
            before = self.installer.canonical_tree_manifest(installed)
            agents_before = (codex_home / "AGENTS.md").read_bytes()
            real_replace = self.installer._replace_path

            def fail_skill_stage(source: Path, target: Path) -> None:
                if target == installed and ".stage." in source.name:
                    raise OSError("injected skill activation failure")
                real_replace(source, target)

            with mock.patch.object(self.installer, "_replace_path", side_effect=fail_skill_stage):
                with self.assertRaisesRegex(OSError, "injected skill activation failure"):
                    self.installer.install(codex_home)
            self.assertEqual(self.installer.canonical_tree_manifest(installed), before)
            self.assertEqual((codex_home / "AGENTS.md").read_bytes(), agents_before)
            self.assert_no_installer_artifacts(codex_home)

    def test_global_activation_failure_rolls_back_skill_and_global_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary) / ".codex"
            self.installer.install(codex_home)
            installed = codex_home / "skills" / "outcome-integrity"
            (installed / "previous-only.txt").write_bytes(b"previous installation\n")
            agents = codex_home / "AGENTS.md"
            agents.write_bytes(
                b"# Existing\r\n\r\n<!-- outcome-integrity:start -->\r\nold\r\n"
                b"<!-- outcome-integrity:end -->\r\n"
            )
            before = self.installer.canonical_tree_manifest(installed)
            agents_before = agents.read_bytes()
            real_replace = self.installer._replace_path

            def fail_global_stage(source: Path, target: Path) -> None:
                if target == agents and ".stage." in source.name:
                    raise OSError("injected global activation failure")
                real_replace(source, target)

            with mock.patch.object(self.installer, "_replace_path", side_effect=fail_global_stage):
                with self.assertRaisesRegex(OSError, "injected global activation failure"):
                    self.installer.install(codex_home)
            self.assertEqual(self.installer.canonical_tree_manifest(installed), before)
            self.assertEqual(agents.read_bytes(), agents_before)
            self.assert_no_installer_artifacts(codex_home)

            self.installer.install(codex_home)
            self.assertFalse((installed / "previous-only.txt").exists())
            self.assertNotEqual(agents.read_bytes(), agents_before)
            self.assert_no_installer_artifacts(codex_home)

    def test_active_install_lock_fails_closed_before_installation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary) / ".codex"
            codex_home.mkdir()
            lock = codex_home / self.installer.LOCK_NAME
            lock.mkdir()
            owner = {
                "pid": os.getpid(),
                "hostname": socket.gethostname(),
                "token": "active-owner",
                "created_unix": 0,
            }
            (lock / self.installer.LOCK_OWNER_NAME).write_text(
                json.dumps(owner), encoding="utf-8"
            )
            with self.assertRaisesRegex(OSError, "holds the lock"):
                self.installer.install(codex_home)
            self.assertFalse((codex_home / "skills").exists())
            self.assertFalse((codex_home / "AGENTS.md").exists())

    def test_stale_dead_install_lock_is_recovered_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary) / ".codex"
            codex_home.mkdir()
            lock = codex_home / self.installer.LOCK_NAME
            lock.mkdir()
            owner = {
                "pid": 2_147_483_647,
                "hostname": socket.gethostname(),
                "token": "dead-owner",
                "created_unix": 0,
            }
            (lock / self.installer.LOCK_OWNER_NAME).write_text(
                json.dumps(owner), encoding="utf-8"
            )
            os.utime(lock, (0, 0))
            self.installer.install(codex_home)
            self.assertTrue((codex_home / "skills" / "outcome-integrity" / "SKILL.md").is_file())
            self.assert_no_installer_artifacts(codex_home)

    def test_initialize_creates_both_files_without_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.state.initialize(root)
            second = self.state.initialize(root)
            self.assertEqual(len(first["created"]), 2)
            self.assertEqual(second["created"], [])
            self.assertFalse(self.state.validate(root)["ok"])

    def test_valid_active_state_passes_validate_and_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_state(root, project_text(), acceptance_data())
            self.assertTrue(self.state.validate(root)["ok"])
            self.assertTrue(self.state.validate(root, mode="resume")["ok"])

    def test_passing_requires_sufficient_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            weak = acceptance_data(status="passing", evidence_level="focused-test")
            write_state(root, project_text(), weak)
            result = self.state.validate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("cannot pass" in error for error in result["errors"]))

    def test_blocked_state_requires_complete_recovery_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            incomplete_blocker = {"owner": "user", "reason": "credential missing"}
            blocked = acceptance_data(
                project_state="blocked", status="blocked", blocker=incomplete_blocker
            )
            write_state(root, project_text(state="blocked"), blocked)
            result = self.state.validate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("recovery_trigger" in error for error in result["errors"]))

    def test_resume_rejects_stale_acceptance_and_slice_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stale = acceptance_data(updated="2026-07-16T09:59:00Z", current_id=None)
            write_state(root, project_text(updated="2026-07-16T10:00:00Z"), stale)
            result = self.state.validate(root, mode="resume")
            self.assertFalse(result["ok"])
            self.assertTrue(any("reconciliation timestamps" in error for error in result["errors"]))
            self.assertTrue(any("current slice mismatch" in error for error in result["errors"]))

    def test_resume_reports_unknown_current_id_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            unknown = acceptance_data(current_id="REQ-UNKNOWN")
            write_state(root, project_text(current_id="REQ-UNKNOWN"), unknown)
            result = self.state.validate(root, mode="resume")
            self.assertFalse(result["ok"])
            self.assertTrue(any("does not exist" in error for error in result["errors"]))

    def test_legacy_state_resumes_but_cannot_prove_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            legacy = acceptance_data(schema_version=1)
            write_state(root, project_text(), legacy)
            resumed = self.state.validate(root, mode="resume")
            self.assertTrue(resumed["ok"], resumed)
            self.assertTrue(any("legacy" in warning for warning in resumed["warnings"]))

            completed = acceptance_data(
                schema_version=1,
                project_state="complete",
                current_id=None,
                status="passing",
                evidence_level="end-to-end",
            )
            write_state(root, project_text(state="complete", current_id="none"), completed)
            result = self.state.validate(root, mode="completion")
            self.assertFalse(result["ok"])
            self.assertTrue(any("schema_version 6" in error for error in result["errors"]))

    def test_completion_requires_every_product_capability(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            completed = acceptance_data(
                project_state="complete",
                current_id=None,
                status="passing",
                evidence_level="end-to-end",
            )
            completed["outcome_capabilities"].append(
                {
                    "id": "CAP-UNMAPPED",
                    "description": "A second required product capability.",
                    "required": True,
                }
            )
            write_state(root, project_text(state="complete", current_id="none"), completed)
            result = self.state.validate(root, mode="completion")
            self.assertFalse(result["ok"])
            self.assertTrue(any("CAP-UNMAPPED" in error for error in result["errors"]))

    def test_passing_requires_step_and_exact_identity_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            completed = acceptance_data(
                project_state="complete",
                current_id=None,
                status="passing",
                evidence_level="end-to-end",
            )
            evidence = completed["requirements"][0]["evidence"][0]
            evidence["step_ids"] = []
            evidence["identity_ids"] = []
            write_state(root, project_text(state="complete", current_id="none"), completed)
            result = self.state.validate(root, mode="completion")
            self.assertFalse(result["ok"])
            self.assertTrue(any("sufficient evidence for steps" in error for error in result["errors"]))
            self.assertTrue(any("exact identity evidence" in error for error in result["errors"]))

    def test_alternate_identity_cannot_satisfy_a_named_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            completed = acceptance_data(
                project_state="complete",
                current_id=None,
                status="passing",
                evidence_level="end-to-end",
            )
            completed["requirements"][0]["evidence"][0]["identity_ids"] = [
                "ENTITY-ALTERNATE"
            ]
            write_state(root, project_text(state="complete", current_id="none"), completed)
            result = self.state.validate(root, mode="completion")
            self.assertFalse(result["ok"])
            self.assertTrue(any("unknown ID: ENTITY-ALTERNATE" in error for error in result["errors"]))
            self.assertTrue(any("exact identity evidence" in error for error in result["errors"]))
    def test_unresolved_counterevidence_blocks_passing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            completed = acceptance_data(
                project_state="complete",
                current_id=None,
                status="passing",
                evidence_level="end-to-end",
            )
            completed["requirements"][0]["counterevidence"] = [
                {
                    "ref": "conflicting observation",
                    "summary": "The same declared target failed on another authoritative surface.",
                    "observed_utc": "2026-07-16T10:00:00Z",
                    "status": "unresolved",
                    "resolution": None,
                }
            ]
            write_state(root, project_text(state="complete", current_id="none"), completed)
            result = self.state.validate(root, mode="completion")
            self.assertFalse(result["ok"])
            self.assertTrue(any("unresolved counterevidence" in error for error in result["errors"]))

    def test_project_identity_markers_bind_state_to_the_selected_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data()
            state["project_identity"]["root_markers"] = ["missing-project.marker"]
            write_state(root, project_text(), state)
            result = self.state.validate(root, mode="resume")
            self.assertFalse(result["ok"])
            self.assertTrue(any("does not exist" in error for error in result["errors"]))

    def test_schema_v3_requires_outcome_stack_and_proof_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            incomplete_project = project_text().replace(
                "- Slice proof limits: This path does not prove unrelated capabilities.\n", ""
            )
            write_state(root, incomplete_project, acceptance_data())
            result = self.state.validate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("Slice proof limits" in error for error in result["errors"]))

    def test_schema_v2_resumes_but_cannot_prove_new_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            legacy = acceptance_data(schema_version=2)
            legacy_project = project_text().replace(
                "- North-star outcome:", "- Product outcome:"
            ).replace(
                "- Active acceptance slice:", "- Active proof slice:"
            ).replace(
                "- Slice proof limits:", "- Proof limits:"
            )
            write_state(root, legacy_project, legacy)
            self.assertTrue(self.state.validate(root, mode="resume")["ok"])

            completed = acceptance_data(
                schema_version=2, project_state="complete", current_id=None,
                status="passing", evidence_level="end-to-end"
            )
            write_state(
                root,
                legacy_project.replace("State: active", "State: complete")
                .replace("- Acceptance ID: REQ-001", "- Acceptance ID: none")
                .replace("- Delivery Stage ID: STAGE-001", "- Delivery Stage ID: none"),
                completed,
            )
            result = self.state.validate(root, mode="completion")
            self.assertFalse(result["ok"])
            self.assertTrue(any("schema_version 6" in error for error in result["errors"]))

    def test_cross_stage_capability_substitution_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data()
            state["outcome_hierarchy"]["delivery_stages"].append({
                "id": "STAGE-002",
                "parent_outcome_id": "OUTCOME-001",
                "description": "A later coherent delivery state.",
                "required": True,
                "status": "planned",
            })
            state["outcome_capabilities"].append({
                "id": "CAP-002", "description": "A later-stage capability.",
                "required": True, "stage_id": "STAGE-002"
            })
            state["requirements"][0]["capability_ids"] = ["CAP-002"]
            write_state(root, project_text(), state)
            result = self.state.validate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("belong to or be explicitly preserved" in error for error in result["errors"]))

    def test_stage_completion_does_not_leak_from_one_passing_slice(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data(status="passing", evidence_level="end-to-end")
            state["outcome_capabilities"].append({
                "id": "CAP-002", "description": "Another required stage capability.",
                "required": True, "stage_id": "STAGE-001"
            })
            state["outcome_hierarchy"]["delivery_stages"][0]["status"] = "complete"
            state["outcome_hierarchy"]["current_stage_id"] = None
            write_state(root, project_text().replace(
                "- Delivery Stage ID: STAGE-001", "- Delivery Stage ID: none"
            ), state)
            result = self.state.validate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("CAP-002" in error for error in result["errors"]))

    def test_north_star_cannot_be_achieved_through_incomplete_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data()
            state["outcome_hierarchy"]["north_star"]["status"] = "achieved"
            write_state(root, project_text(), state)
            result = self.state.validate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("north star cannot be achieved" in error for error in result["errors"]))

    def test_current_slice_must_belong_to_current_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data()
            state["outcome_hierarchy"]["delivery_stages"].append({
                "id": "STAGE-002", "parent_outcome_id": "OUTCOME-001",
                "description": "Another stage.", "required": True, "status": "planned"
            })
            state["requirements"][0]["stage_id"] = "STAGE-002"
            state["outcome_capabilities"][0]["stage_id"] = "STAGE-002"
            write_state(root, project_text(), state)
            result = self.state.validate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("current slice must belong" in error for error in result["errors"]))

    def test_later_stage_must_preserve_every_permanent_capability(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data()
            state["outcome_hierarchy"]["delivery_stages"][0]["preserves_capability_ids"] = []
            write_state(root, project_text(), state)
            result = self.state.validate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("does not preserve permanent capabilities" in error for error in result["errors"]))

    def test_permanent_capability_requires_all_three_distinct_proof_tiers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data()
            state["capability_floors"][0]["proof_ladder"]["pre-release"] = ["REQ-001"]
            write_state(root, project_text(), state)
            result = self.state.validate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("tiers must use distinct requirements" in error for error in result["errors"]))

    def test_proof_ladder_keeps_change_cheap_and_release_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data()
            state["requirements"][0]["minimum_evidence_level"] = "end-to-end"
            state["requirements"][2]["minimum_evidence_level"] = "focused-test"
            write_state(root, project_text(), state)
            result = self.state.validate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("must remain focused-test strength or cheaper" in error for error in result["errors"]))
            self.assertTrue(any("requires end-to-end evidence or stronger" in error for error in result["errors"]))

    def test_schema_v5_requires_a_complete_proof_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data()
            del state["requirements"][0]["proof_path"]
            write_state(root, project_text(), state)
            result = self.state.validate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("proof_path must be an object" in error for error in result["errors"]))

    def test_permanent_floor_change_gate_cannot_inject_post_boundary_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data()
            state["requirements"][0]["proof_path"]["fidelity"] = "synthetic"
            write_state(root, project_text(), state)
            result = self.state.validate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any(
                "change gate REQ-001 must use production-shaped or production proof fidelity" in error
                for error in result["errors"]
            ))

    def test_permanent_floor_change_gate_must_cross_the_real_interaction_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data()
            state["requirements"][0]["system_scope"] = "component"
            write_state(root, project_text(), state)
            result = self.state.validate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("must cross an interaction" in error for error in result["errors"]))

    def test_release_gate_requires_production_fidelity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data()
            state["requirements"][2]["proof_path"]["fidelity"] = "production-shaped"
            write_state(root, project_text(), state)
            result = self.state.validate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("release proof must be production-fidelity" in error for error in result["errors"]))

    def test_schema_v5_requires_causal_control_lines(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            incomplete = project_text().replace(
                "- Earliest divergent transition: Real producer crosses the declared decision boundary incorrectly.\n",
                "",
            )
            write_state(root, incomplete, acceptance_data())
            result = self.state.validate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("Earliest divergent transition" in error for error in result["errors"]))

    def test_schema_v4_resumes_but_cannot_prove_new_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            legacy = acceptance_data(schema_version=4)
            write_state(root, project_text(), legacy)
            resumed = self.state.validate(root, mode="resume")
            self.assertTrue(resumed["ok"], resumed)
            self.assertTrue(any("legacy" in warning for warning in resumed["warnings"]))

            completed = acceptance_data(
                schema_version=4,
                project_state="complete",
                current_id=None,
                status="passing",
                evidence_level="end-to-end",
            )
            write_state(root, project_text(state="complete", current_id="none"), completed)
            result = self.state.validate(root, mode="completion")
            self.assertFalse(result["ok"])
            self.assertTrue(any("schema_version 6" in error for error in result["errors"]))

    def test_optional_supporting_state_requires_no_state_integration_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data()
            floor = state["capability_floors"][0]
            floor["optional_supporting_state"] = ["learned routing history"]
            floor["independence_requirement_ids"] = []
            write_state(root, project_text(), state)
            result = self.state.validate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("independence_requirement_ids must be a non-empty array" in error for error in result["errors"]))

    def test_balanced_fitness_dimensions_require_permanent_floor_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data()
            state["outcome_hierarchy"]["north_star"]["fitness_dimensions"].append({
                "id": "FIT-SAFETY", "description": "Authority and safety remain bounded."
            })
            write_state(root, project_text(), state)
            result = self.state.validate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("FIT-SAFETY" in error for error in result["errors"]))

    def test_each_stage_requires_whole_system_release_gate_for_all_floors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data()
            state["requirements"][2]["system_scope"] = "interaction"
            write_state(root, project_text(), state)
            result = self.state.validate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("requires one end-to-end release gate" in error for error in result["errors"]))

    def test_permanent_floor_gates_cannot_be_optional(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data()
            state["requirements"][0]["required"] = False
            write_state(root, project_text(), state)
            result = self.state.validate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("gate requirement REQ-001 must be required" in error for error in result["errors"]))

    def test_atomic_reservation_charges_one_lineage_across_external_run_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data()
            write_state(root, project_text(), state)
            request_path = root / "request.json"
            write_json(request_path, attempt_request(state, external_run_id="run-alpha"))
            first = self.state.attempt_begin(root, request_path, 0)
            self.assertTrue(first["ok"], first)
            result_path = root / "result.json"
            write_json(
                result_path,
                attempt_result(
                    attempt_id=first["attempt"]["id"], outcome="aborted", progress=False
                ),
            )
            finished = self.state.attempt_finish(root, result_path, 1)
            self.assertTrue(finished["ok"], finished)

            current = json.loads((root / ".codex" / "ACCEPTANCE.json").read_text(encoding="utf-8"))
            write_json(request_path, attempt_request(current, external_run_id="run-beta"))
            second = self.state.attempt_begin(root, request_path, 2)
            self.assertTrue(second["ok"], second)
            current = json.loads((root / ".codex" / "ACCEPTANCE.json").read_text(encoding="utf-8"))
            self.assertEqual(current["execution_control"]["usage"]["total_attempts"], 2)
            self.assertEqual(second["attempt"]["lineage_id"], "LINEAGE-001")

    def test_cli_entrypoint_reserves_and_finishes_the_atomic_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data()
            write_state(root, project_text(), state)
            request_path = root / "request.json"
            result_path = root / "result.json"
            write_json(request_path, attempt_request(state))
            begun = subprocess.run(
                [
                    sys.executable,
                    str(STATE_SCRIPT),
                    "attempt-begin",
                    "--root",
                    str(root),
                    "--request",
                    str(request_path),
                    "--expected-revision",
                    "0",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(begun.returncode, 0, begun.stderr or begun.stdout)
            begun_payload = json.loads(begun.stdout)
            self.assertEqual(begun_payload["revision"], 1)
            write_json(
                result_path,
                attempt_result(
                    attempt_id=begun_payload["attempt"]["id"],
                    outcome="aborted",
                    progress=False,
                ),
            )
            finished = subprocess.run(
                [
                    sys.executable,
                    str(STATE_SCRIPT),
                    "attempt-finish",
                    "--root",
                    str(root),
                    "--result",
                    str(result_path),
                    "--expected-revision",
                    "1",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(finished.returncode, 0, finished.stderr or finished.stdout)
            payload = json.loads(finished.stdout)
            self.assertIsNone(payload["receipt"])

    def test_distinct_failures_consume_the_aggregate_failure_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data()
            state["execution_control"]["limits"]["failed_attempts"] = 2
            state["execution_control"]["limits"]["no_progress_attempts"] = 5
            write_state(root, project_text(), state)
            request_path = root / "request.json"
            result_path = root / "result.json"
            revision = 0
            for boundary in ("decoder-output", "storage-commit"):
                current = json.loads((root / ".codex" / "ACCEPTANCE.json").read_text(encoding="utf-8"))
                write_json(
                    request_path,
                    attempt_request(
                        current,
                        external_run_id=f"run-{boundary}",
                        boundary_id="BOUNDARY-" + boundary.upper().replace("-", "_"),
                    ),
                )
                begun = self.state.attempt_begin(root, request_path, revision)
                self.assertTrue(begun["ok"], begun)
                revision = begun["revision"]
                write_json(
                    result_path,
                    attempt_result(
                        attempt_id=begun["attempt"]["id"],
                        outcome="failed",
                        progress=False,
                        earliest_divergence=f"The {boundary} boundary diverged.",
                    ),
                )
                finished = self.state.attempt_finish(root, result_path, revision)
                self.assertTrue(finished["ok"], finished)
                revision = finished["revision"]
            self.assertEqual(finished["status"], "stopped")
            current = json.loads((root / ".codex" / "ACCEPTANCE.json").read_text(encoding="utf-8"))
            self.assertEqual(len(current["execution_control"]["usage"]["failure_classes"]), 2)

    def test_equivalent_failures_stop_despite_changed_run_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data()
            state["execution_control"]["limits"]["failed_attempts"] = 4
            state["execution_control"]["limits"]["no_progress_attempts"] = 5
            write_state(root, project_text(), state)
            request_path = root / "request.json"
            result_path = root / "result.json"
            revision = 0
            for run_id in ("process-one", "process-two"):
                current = json.loads((root / ".codex" / "ACCEPTANCE.json").read_text(encoding="utf-8"))
                write_json(request_path, attempt_request(current, external_run_id=run_id))
                begun = self.state.attempt_begin(root, request_path, revision)
                revision = begun["revision"]
                write_json(
                    result_path,
                    attempt_result(
                        attempt_id=begun["attempt"]["id"],
                        outcome="failed",
                        progress=False,
                    ),
                )
                finished = self.state.attempt_finish(root, result_path, revision)
                revision = finished["revision"]
            self.assertEqual(finished["status"], "stopped")
            current = json.loads((root / ".codex" / "ACCEPTANCE.json").read_text(encoding="utf-8"))
            self.assertEqual(current["execution_control"]["usage"]["failure_classes"][0]["count"], 2)

    def test_active_attempt_blocks_restart_or_parallel_begin(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data()
            write_state(root, project_text(), state)
            request_path = root / "request.json"
            write_json(request_path, attempt_request(state))
            first = self.state.attempt_begin(root, request_path, 0)
            self.assertTrue(first["ok"], first)
            second = self.state.attempt_begin(root, request_path, 1)
            self.assertFalse(second["ok"])
            self.assertTrue(any("no new attempt" in error for error in second["errors"]))

    def test_stale_result_cannot_finish_a_new_active_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data()
            write_state(root, project_text(), state)
            request_path = root / "request.json"
            result_path = root / "result.json"

            write_json(request_path, attempt_request(state, external_run_id="run-one"))
            first = self.state.attempt_begin(root, request_path, 0)
            write_json(
                result_path,
                attempt_result(
                    attempt_id=first["attempt"]["id"], outcome="aborted", progress=False
                ),
            )
            first_finished = self.state.attempt_finish(
                root, result_path, first["revision"]
            )
            self.assertTrue(first_finished["ok"], first_finished)

            current = json.loads(
                (root / ".codex" / "ACCEPTANCE.json").read_text(encoding="utf-8")
            )
            write_json(request_path, attempt_request(current, external_run_id="run-two"))
            second = self.state.attempt_begin(
                root, request_path, first_finished["revision"]
            )
            self.assertTrue(second["ok"], second)

            write_json(
                result_path,
                attempt_result(
                    attempt_id=first["attempt"]["id"], outcome="passed", progress=True
                ),
            )
            refused = self.state.attempt_finish(root, result_path, second["revision"])
            self.assertFalse(refused["ok"])
            self.assertTrue(any("attempt_id" in error for error in refused["errors"]))
            persisted = json.loads(
                (root / ".codex" / "ACCEPTANCE.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                persisted["execution_control"]["active_attempt"]["id"],
                second["attempt"]["id"],
            )

    def test_higher_tier_requires_same_candidate_predecessor_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data(current_id="REQ-PRE-RELEASE")
            write_state(root, project_text(current_id="REQ-PRE-RELEASE"), state)
            request_path = root / "request.json"
            write_json(
                request_path,
                attempt_request(
                    state, requirement_id="REQ-PRE-RELEASE", tier="pre-release"
                ),
            )
            result = self.state.attempt_begin(root, request_path, 0)
            self.assertFalse(result["ok"])
            self.assertTrue(any("predecessor receipts" in error for error in result["errors"]))

    def test_candidate_rebind_invalidates_receipts_but_preserves_counters(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data()
            state["execution_control"]["usage"].update({
                "total_attempts": 1,
                "failed_attempts": 1,
            })
            failure_identity = {
                "lineage_id": "LINEAGE-001",
                "acceptance_outcome_id": "OUTCOME-001",
                "boundary_id": "BOUNDARY-001",
            }
            failure_fingerprint = "sha256:" + hashlib.sha256(
                json.dumps(
                    failure_identity, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
            ).hexdigest()
            state["execution_control"]["usage"]["failure_classes"] = [{
                "fingerprint": failure_fingerprint,
                "lineage_id": "LINEAGE-001",
                "acceptance_outcome_id": "OUTCOME-001",
                "boundary_id": "BOUNDARY-001",
                "failure_class": "semantic",
                "earliest_divergence": "The acceptance transition diverged.",
                "candidate_fingerprint": "sha256:" + "0" * 64,
                "count": 1,
                "last_observed_utc": "2026-07-16T10:00:00Z",
            }]
            write_state(root, project_text(), state)
            state["execution_control"]["gate_receipts"] = [{
                "id": "RECEIPT-OLD",
                "requirement_id": "REQ-001",
                "tier": "change",
                "lineage_id": "LINEAGE-001",
                "candidate_fingerprint": state["execution_control"]["candidate"]["fingerprint"],
                "evidence_ref": "tests/evidence/old.json",
                "summary": "Old candidate passed.",
                "verified_utc": "2026-07-16T10:00:00Z",
                "evaluation_fingerprint": None,
                "evaluation_role": "none",
            }]
            write_json(root / ".codex" / "ACCEPTANCE.json", state)
            (root / "project.marker").write_text("changed candidate\n", encoding="utf-8")
            rebound = self.state.candidate_bind(root, 0, [])
            self.assertTrue(rebound["ok"], rebound)
            current = json.loads((root / ".codex" / "ACCEPTANCE.json").read_text(encoding="utf-8"))
            self.assertEqual(current["execution_control"]["gate_receipts"], [])
            self.assertEqual(current["execution_control"]["usage"]["total_attempts"], 1)
            self.assertEqual(current["execution_control"]["usage"]["failed_attempts"], 1)

    def test_exposed_evaluation_cannot_be_reused_as_prospective(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data()
            write_state(root, project_text(), state)
            exposed = "sha256:" + "6" * 64
            rebound = self.state.candidate_bind(root, 0, [exposed])
            self.assertTrue(rebound["ok"], rebound)
            current = json.loads((root / ".codex" / "ACCEPTANCE.json").read_text(encoding="utf-8"))
            request_path = root / "request.json"
            write_json(
                request_path,
                attempt_request(
                    current,
                    evaluation_fingerprint=exposed,
                    evaluation_role="prospective",
                ),
            )
            result = self.state.attempt_begin(root, request_path, 1)
            self.assertFalse(result["ok"])
            self.assertTrue(any("exposed evaluation" in error for error in result["errors"]))

    def test_fresh_evaluation_remains_prospective_after_other_input_is_exposed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data()
            write_state(root, project_text(), state)
            self.state.candidate_bind(root, 0, ["sha256:" + "7" * 64])
            current = json.loads((root / ".codex" / "ACCEPTANCE.json").read_text(encoding="utf-8"))
            request_path = root / "request.json"
            write_json(
                request_path,
                attempt_request(
                    current,
                    evaluation_fingerprint="sha256:" + "8" * 64,
                    evaluation_role="prospective",
                ),
            )
            result = self.state.attempt_begin(root, request_path, 1)
            self.assertTrue(result["ok"], result)

    def test_missing_hard_downstream_prerequisite_blocks_admission(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data()
            state["execution_control"]["prerequisites"] = [{
                "id": "PREREQ-OUTPUT",
                "description": "The downstream output envelope is callable and large enough.",
                "status": "missing",
                "evidence_ref": None,
                "verified_utc": None,
                "expires_utc": None,
                "context_fingerprint": "sha256:" + "1" * 64,
                "requirement_ids": ["REQ-001"],
                "action_classes": ["proof"],
                "gate_tiers": ["change"],
            }]
            write_state(root, project_text(), state)
            request_path = root / "request.json"
            write_json(request_path, attempt_request(state))
            result = self.state.attempt_begin(root, request_path, 0)
            self.assertFalse(result["ok"])
            self.assertTrue(any("prerequisites are omitted" in error for error in result["errors"]))

    def test_authorization_for_one_target_cannot_admit_another(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data()
            state["identity_requirements"].append({
                "id": "ENTITY-002",
                "description": "A different exact target.",
                "substitutable": False,
            })
            context = "sha256:" + "9" * 64
            state["execution_control"]["authorizations"] = [{
                "id": "AUTH-001",
                "action": "Stop the named worker.",
                "effect": "Terminate only the named target.",
                "target_identity_ids": ["ENTITY-001"],
                "principal": "The user.",
                "context_fingerprint": context,
                "authorized_utc": "2026-07-16T10:00:00Z",
                "expires_utc": "2099-07-16T10:00:00Z",
                "uses_remaining": 1,
                "status": "active",
            }]
            write_state(root, project_text(), state)
            request_path = root / "request.json"
            write_json(
                request_path,
                attempt_request(
                    state,
                    principal="The user.",
                    action_classes=["local", "external-write"],
                    authorization_id="AUTH-001",
                    target_identity_ids=["ENTITY-002"],
                    action="Stop the named worker.",
                    effect="Terminate only the named target.",
                    context_fingerprint=context,
                ),
            )
            result = self.state.attempt_begin(root, request_path, 0)
            self.assertFalse(result["ok"])
            self.assertTrue(any("target/effect set" in error for error in result["errors"]))

    def test_exact_authorization_is_consumed_at_reservation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data()
            context = "sha256:" + "a" * 64
            state["execution_control"]["authorizations"] = [{
                "id": "AUTH-001",
                "action": "Apply the exact external update.",
                "effect": "Change only the declared target.",
                "target_identity_ids": ["ENTITY-001"],
                "principal": "The user.",
                "context_fingerprint": context,
                "authorized_utc": "2026-07-16T10:00:00Z",
                "expires_utc": "2099-07-16T10:00:00Z",
                "uses_remaining": 1,
                "status": "active",
            }]
            write_state(root, project_text(), state)
            request_path = root / "request.json"
            write_json(
                request_path,
                attempt_request(
                    state,
                    principal="The user.",
                    action_classes=["local", "external-write"],
                    authorization_id="AUTH-001",
                    target_identity_ids=["ENTITY-001"],
                    action="Apply the exact external update.",
                    effect="Change only the declared target.",
                    context_fingerprint=context,
                ),
            )
            result = self.state.attempt_begin(root, request_path, 0)
            self.assertTrue(result["ok"], result)
            current = json.loads((root / ".codex" / "ACCEPTANCE.json").read_text(encoding="utf-8"))
            authorization = current["execution_control"]["authorizations"][0]
            self.assertEqual(authorization["uses_remaining"], 0)
            self.assertEqual(authorization["status"], "consumed")

    def test_support_and_no_progress_limits_stop_more_support(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data()
            state["execution_control"]["limits"]["support_attempts"] = 1
            state["execution_control"]["limits"]["no_progress_attempts"] = 1
            write_state(root, project_text(), state)
            request_path = root / "request.json"
            write_json(request_path, attempt_request(state, action_classes=["local", "support"]))
            begun = self.state.attempt_begin(root, request_path, 0)
            result_path = root / "result.json"
            write_json(
                result_path,
                attempt_result(
                    attempt_id=begun["attempt"]["id"], outcome="aborted", progress=False
                ),
            )
            finished = self.state.attempt_finish(root, result_path, begun["revision"])
            self.assertEqual(finished["status"], "stopped")
            current = json.loads((root / ".codex" / "ACCEPTANCE.json").read_text(encoding="utf-8"))
            write_json(request_path, attempt_request(current, action_classes=["local", "support"]))
            refused = self.state.attempt_begin(root, request_path, finished["revision"])
            self.assertFalse(refused["ok"])

    def test_stale_expected_revision_cannot_mutate_control(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data()
            write_state(root, project_text(), state)
            request_path = root / "request.json"
            write_json(request_path, attempt_request(state))
            result = self.state.attempt_begin(root, request_path, 9)
            self.assertFalse(result["ok"])
            self.assertTrue(any("stale expected revision" in error for error in result["errors"]))

    def test_acceptance_semantic_change_makes_scope_fingerprint_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = acceptance_data()
            write_state(root, project_text(), state)
            state["requirements"][0]["description"] = "A materially different acceptance promise."
            write_json(root / ".codex" / "ACCEPTANCE.json", state)
            result = self.state.validate(root, mode="resume")
            self.assertFalse(result["ok"])
            self.assertTrue(any("scope_fingerprint is stale" in error for error in result["errors"]))

    def test_completion_rejects_incomplete_and_accepts_evidence_backed_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_state(root, project_text(), acceptance_data())
            self.assertFalse(self.state.validate(root, mode="completion")["ok"])

            completed = acceptance_data(
                project_state="complete",
                current_id=None,
                status="passing",
                evidence_level="end-to-end",
            )
            write_state(root, project_text(state="complete", current_id="none"), completed)
            result = self.state.validate(root, mode="completion")
            self.assertTrue(result["ok"], result)


if __name__ == "__main__":
    unittest.main()
