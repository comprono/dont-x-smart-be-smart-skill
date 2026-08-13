from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


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
    schema_version: int = 4,
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
    if schema_version == 4:
        data["outcome_hierarchy"]["north_star"]["fitness_dimensions"] = [
            {"id": "FIT-UTILITY", "description": "Useful verified output advances."},
            {"id": "FIT-EFFICIENCY", "description": "Resources and time remain proportionate."},
        ]
        data["outcome_hierarchy"]["delivery_stages"][0]["preserves_capability_ids"] = ["CAP-001"]
        data["outcome_capabilities"][0]["preservation"] = "permanent"
        requirement["gate_tiers"] = ["change"]
        requirement["system_scope"] = "component"
        requirement["minimum_evidence_level"] = "focused-test"
        pre_release = json.loads(json.dumps(requirement))
        pre_release["id"] = "REQ-PRE-RELEASE"
        pre_release["description"] = "The representative interaction path passes."
        pre_release["gate_tiers"] = ["pre-release"]
        pre_release["system_scope"] = "interaction"
        pre_release["minimum_evidence_level"] = "integration"
        pre_release["acceptance_steps"] = [{"id": "STEP-PRE-RELEASE", "description": "Exercise the interaction path."}]
        release = json.loads(json.dumps(requirement))
        release["id"] = "REQ-RELEASE"
        release["description"] = "The complete user flow passes."
        release["gate_tiers"] = ["release"]
        release["system_scope"] = "end-to-end"
        release["minimum_evidence_level"] = "end-to-end"
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
    return data

def write_state(root: Path, project: str, acceptance: dict[str, object]) -> None:
    state_dir = root / ".codex"
    state_dir.mkdir(parents=True, exist_ok=True)
    (root / "project.marker").write_text("test project\n", encoding="utf-8")
    (state_dir / "PROJECT_OUTCOME.md").write_text(project, encoding="utf-8")
    (state_dir / "ACCEPTANCE.json").write_text(
        json.dumps(acceptance, indent=2) + "\n", encoding="utf-8"
    )


class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.state = load_module(STATE_SCRIPT, "project_outcome")

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
        self.assertIn("advance the next efficient accountable authorized slice", openai_yaml)

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

        self.assertIn("Separate product outcome, tooling or plugin state", global_rules)
        self.assertIn("conclusion, material distinction, and next owned action", global_rules)
        self.assertIn("Continuing an explanation loop", readme)
        self.assertIn("short conclusion, distinction, and next-action frame", readme)
        self.assertIn("preserve the full parented outcome stack", openai_yaml)

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
            "idempotency identity",
            "Stop producers when resources grow",
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
        self.assertIn("return attention to the verified gap", openai_yaml)

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

        self.assertLessEqual(len(skill.split()), 3186)
        self.assertLessEqual(len(global_rules.split()), 700)
        for project_specific in ("Bhagavad", "Krishna", "Arjuna", "Claude", "Antigravity"):
            self.assertNotIn(project_specific.casefold(), skill.casefold())
            self.assertNotIn(project_specific.casefold(), global_rules.casefold())


    def test_schema_v4_template_declares_capability_preservation_fields(self) -> None:
        acceptance_template = (
            REPOSITORY_ROOT
            / "skills"
            / "outcome-integrity"
            / "assets"
            / "ACCEPTANCE.template.json"
        ).read_text(encoding="utf-8")
        for phrase in (
            '"schema_version": 4',
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
            '"outcome_capabilities"',
            '"identity_requirements"',
            '"capability_ids"',
            '"identity_ids"',
            '"proof_scope"',
            '"proof_limits"',
            '"counterevidence"',
        ):
            self.assertIn(phrase, acceptance_template)
    def test_installer_is_idempotent_and_preserves_existing_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary) / ".codex"
            codex_home.mkdir()
            agents = codex_home / "AGENTS.md"
            agents.write_text("# Existing rule\n\nKeep this line.\n", encoding="utf-8")

            command = [sys.executable, str(INSTALLER), "--codex-home", str(codex_home)]
            subprocess.run(command, check=True, capture_output=True, text=True)
            subprocess.run(command, check=True, capture_output=True, text=True)

            installed = codex_home / "skills" / "outcome-integrity"
            merged = agents.read_text(encoding="utf-8")
            self.assertTrue((installed / "SKILL.md").is_file())
            self.assertTrue((installed / "assets" / "ACCEPTANCE.template.json").is_file())
            self.assertIn("Keep this line.", merged)
            self.assertEqual(merged.count("<!-- outcome-integrity:start -->"), 1)
            self.assertEqual(merged.count("<!-- outcome-integrity:end -->"), 1)

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
            self.assertTrue(any("older" in error for error in result["errors"]))
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
            self.assertTrue(any("schema_version 4" in error for error in result["errors"]))

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
            self.assertTrue(any("schema_version 4" in error for error in result["errors"]))

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
            self.assertTrue(any("must belong to its delivery stage" in error for error in result["errors"]))

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
