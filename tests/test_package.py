from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
INSTALLER = REPOSITORY_ROOT / "scripts" / "install.py"
LEDGER_SCRIPT = REPOSITORY_ROOT / "skills" / "outcome-integrity" / "scripts" / "project_outcome.py"
SKILL = REPOSITORY_ROOT / "skills" / "outcome-integrity" / "SKILL.md"

VALID_LEDGER = """<!-- Managed with the outcome-integrity skill. Keep this current, not chronological. -->
# Project Outcome

Updated: 2026-07-16T10:00:00Z
State: active

## North Star
- Outcome: Produce the requested verified result.
- Why it matters: The user needs the real outcome, not proxy activity.

## Done Means
- [ ] The real user path passes.

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

## Assumptions To Test
- State transition is invalid | Falsifier: valid transition trace | Next check: trace it

## Decisions
- Trace before editing | Why: repeated failure | Revisit when: reproduced

## Failure Memory
- Symptom patch | Root cause: state not traced | Invariant: trace state | Do not repeat: blind retry

## Current Slice
- Objective: Reproduce the invalid transition.
- Acceptance evidence: Deterministic failure at one boundary.
- Protect: Existing passing behavior.
- Status: active

## Next
- Action: Trace the transition.
- Why now: It tests the root cause.
- Blocker and recovery: None.
"""


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PackageTests(unittest.TestCase):
    def test_skill_metadata_is_valid(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nname: outcome-integrity\n"))
        self.assertIn("description:", text.split("---", 2)[1])
        self.assertNotIn("REPLACE_ME", text)

    def test_installer_is_idempotent_and_preserves_existing_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary) / ".codex"
            codex_home.mkdir()
            agents = codex_home / "AGENTS.md"
            agents.write_text("# Existing rule\n\nKeep this line.\n", encoding="utf-8")

            command = [sys.executable, str(INSTALLER), "--codex-home", str(codex_home)]
            subprocess.run(command, check=True, capture_output=True, text=True)
            subprocess.run(command, check=True, capture_output=True, text=True)

            installed = codex_home / "skills" / "outcome-integrity" / "SKILL.md"
            merged = agents.read_text(encoding="utf-8")
            self.assertTrue(installed.is_file())
            self.assertIn("Keep this line.", merged)
            self.assertEqual(merged.count("<!-- outcome-integrity:start -->"), 1)
            self.assertEqual(merged.count("<!-- outcome-integrity:end -->"), 1)

    def test_ledger_rejects_placeholders_and_accepts_complete_state(self) -> None:
        ledger = load_module(LEDGER_SCRIPT, "project_outcome")
        with tempfile.TemporaryDirectory() as temporary:
            initialized = ledger.initialize(temporary)
            self.assertTrue(initialized["created"])
            self.assertFalse(ledger.validate(temporary)["ok"])

            target = Path(temporary) / ".codex" / "PROJECT_OUTCOME.md"
            target.write_text(VALID_LEDGER, encoding="utf-8")
            result = ledger.validate(temporary)
            self.assertTrue(result["ok"], result)


if __name__ == "__main__":
    unittest.main()
