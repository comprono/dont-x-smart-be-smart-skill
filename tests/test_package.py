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
- Outcome: Produce the requested verified result.
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
) -> dict[str, object]:
    evidence = []
    if evidence_level:
        evidence.append(
            {
                "level": evidence_level,
                "ref": "tests/evidence/result.json",
                "summary": "The reproducible path produced the expected result.",
                "verified_utc": updated,
            }
        )
    return {
        "schema_version": 1,
        "updated_utc": updated,
        "project_state": project_state,
        "current_slice_requirement_id": current_id,
        "requirements": [
            {
                "id": "REQ-001",
                "description": "The real user path passes.",
                "required": True,
                "status": status,
                "minimum_evidence_level": minimum_level,
                "acceptance_steps": ["Exercise the real path and inspect the result."],
                "evidence": evidence,
                "blocker": blocker,
            }
        ],
    }


def write_state(root: Path, project: str, acceptance: dict[str, object]) -> None:
    state_dir = root / ".codex"
    state_dir.mkdir(parents=True, exist_ok=True)
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
            "Frame The Outcome Before The Method",
            "if every proposed method completed successfully",
            "cancel or replace it safely",
            "replan from the outcome",
        ):
            self.assertIn(phrase, skill)

        for phrase in (
            "Before the first substantive tool call or durable task contract",
            "A correction that changes the outcome invalidates",
            "After a worker or method is rejected",
        ):
            self.assertIn(phrase, global_rules)

        self.assertIn("- User-visible proof:", template)
        self.assertIn("- Methods, not outcomes:", template)
        self.assertIn("Separate the user's outcome from methods", openai_yaml)

    def test_recurring_work_has_a_bounded_operational_envelope(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        global_rules = GLOBAL_RULES.read_text(encoding="utf-8")
        template = PROJECT_TEMPLATE.read_text(encoding="utf-8")
        readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
        openai_yaml = OPENAI_YAML.read_text(encoding="utf-8")

        for phrase in (
            "Bound Autonomous And Recurring Work",
            "Authorization to continue does not authorize unbounded resource use",
            "Observe frequently; mutate only on state change",
            "resource usage grows while the acceptance state does not improve",
        ):
            self.assertIn(phrase, skill)

        for phrase in (
            "Before enabling recurring, unattended, scheduled, retrying, or automatic recovery work",
            "Observed state may be checked frequently",
            "Stop and fail closed when resources grow",
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
        self.assertIn("bound recurring side effects", openai_yaml)

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
