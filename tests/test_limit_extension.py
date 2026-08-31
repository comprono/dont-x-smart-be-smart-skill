from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
STATE_SCRIPT = REPOSITORY_ROOT / "skills" / "outcome-integrity" / "scripts" / "project_outcome.py"
HOOK_SCRIPT = REPOSITORY_ROOT / "skills" / "outcome-integrity" / "hooks" / "outcome_integrity_hook.py"
SUPPORT_SCRIPT = REPOSITORY_ROOT / "tests" / "test_package.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


SUPPORT = load_module(SUPPORT_SCRIPT, "limit_extension_support")
STATE = load_module(STATE_SCRIPT, "limit_extension_state")
HOOK = load_module(HOOK_SCRIPT, "limit_extension_hook")


@contextmanager
def workspace_temporary_directory():
    """Avoid non-traversable Windows temp directories in managed sandboxes."""
    root = REPOSITORY_ROOT / f".limit-extension-test-{uuid.uuid4().hex}"
    root.mkdir()
    try:
        yield root
    finally:
        shutil.rmtree(root)


class LimitExtensionTests(unittest.TestCase):
    def test_lock_and_preclaim_snapshot_are_project_local_on_windows(self) -> None:
        with workspace_temporary_directory() as root:
            acceptance = SUPPORT.acceptance_data()
            SUPPORT.write_state(root, SUPPORT.project_text(), acceptance)

            with STATE.acceptance_lock(root):
                lock_dir = root / ".codex" / ".outcome-integrity-locks"
                self.assertTrue(lock_dir.is_dir())
                self.assertTrue(any(path.name.endswith(".lease") for path in lock_dir.iterdir()))

            acceptance_path = root / ".codex" / "ACCEPTANCE.json"
            active = json.loads(acceptance_path.read_text(encoding="utf-8"))
            control = active["execution_control"]
            control["status"] = "running"
            control["active_attempt"] = {
                "id": "ATTEMPT-LOCAL-SNAPSHOT",
                "tool_claim": {
                    "status": "claimed",
                    "tool_use_id": "tool-local-snapshot",
                },
            }
            snapshot = STATE.write_preclaim_control_snapshot(root, active)
            self.assertTrue(snapshot.is_file())
            self.assertTrue(str(snapshot).startswith(str(root / ".codex")))
            loaded, loaded_path, errors = STATE.load_preclaim_control_snapshot(root)
            self.assertEqual(errors, [])
            self.assertEqual(loaded_path, snapshot)
            self.assertEqual(loaded["attempt_id"], "ATTEMPT-LOCAL-SNAPSHOT")
            STATE.clear_preclaim_control_snapshot(snapshot)
            self.assertFalse(snapshot.exists())

    def make_blocked_state(self, root: Path) -> dict:
        blocker = {
            "owner": "user",
            "reason": "The prior no-progress ceiling is exhausted.",
            "recovery_trigger": "An explicit bounded monotonic extension is recorded.",
            "recovery_action": "Extend ceilings without resetting usage, then reconcile active state.",
        }
        state = SUPPORT.acceptance_data(
            project_state="blocked",
            status="blocked",
            blocker=blocker,
        )
        control = state["execution_control"]
        control["limits"].update({
            "total_attempts": 2,
            "failed_attempts": 2,
            "expensive_attempts": 1,
            "support_attempts": 1,
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
        })
        control["usage"].update({
            "total_attempts": 2,
            "no_progress_attempts": 2,
        })
        control["status"] = "stopped"
        control["stop_reason"] = "aggregate no-progress limit reached"
        SUPPORT.write_state(root, SUPPORT.project_text(state="blocked"), state)
        return state

    def request(self, root: Path, state: dict, *, extension_id: str = "LIMIT-EXT-001") -> Path:
        evidence = root / ".codex" / "evidence"
        evidence.mkdir(parents=True, exist_ok=True)
        authorization = evidence / "user-approval.md"
        authorization.write_text(
            "The user authorizes only this monotonic zero-provider control recovery.\n",
            encoding="utf-8",
        )
        control = state["execution_control"]
        limits = copy.deepcopy(control["limits"])
        limits.update({
            "total_attempts": 4,
            "failed_attempts": 3,
            "expensive_attempts": 2,
            "support_attempts": 2,
            "no_progress_attempts": 3,
            "total_tool_calls": 40,
            "support_tool_calls": 12,
            "active_attempt_seconds": 7200,
            "spawned_workers": 3,
            "scope_growth_actions": 2,
            "direct_delivery_reserved_calls": 8,
            "max_path_touches": 24,
            "max_touches_per_path": 6,
        })
        request = {
            "kind": STATE.LIMIT_EXTENSION_KIND,
            "id": extension_id,
            "reason": "Continue one bounded recovery method without resetting history.",
            "authorization_ref": ".codex/evidence/user-approval.md",
            "receipt_ref": ".codex/evidence/limit-extension-receipt.json",
            "expected_lineage_id": control["lineage"]["id"],
            "expected_candidate_fingerprint": control["candidate"]["fingerprint"],
            "expected_scope_fingerprint": control["lineage"]["scope_fingerprint"],
            "limits": limits,
        }
        path = root / ".codex" / "LIMIT_EXTENSION_REQUEST.json"
        path.write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
        return path

    def test_monotonic_extension_preserves_stopped_history_then_reconciles_ready(self) -> None:
        with workspace_temporary_directory() as root:
            state = self.make_blocked_state(root)
            request_path = self.request(root, state)
            before = json.loads((root / ".codex" / "ACCEPTANCE.json").read_text(encoding="utf-8"))

            result = STATE.limit_extend(root, request_path, 0)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["revision"], 1)
            self.assertEqual(result["status"], "stopped")
            after = json.loads((root / ".codex" / "ACCEPTANCE.json").read_text(encoding="utf-8"))
            self.assertEqual(after["execution_control"]["usage"], before["execution_control"]["usage"])
            self.assertEqual(after["execution_control"]["candidate"], before["execution_control"]["candidate"])
            self.assertEqual(after["execution_control"]["lineage"], before["execution_control"]["lineage"])
            self.assertEqual(len(after["execution_control"]["limit_extensions"]), 1)
            extension = after["execution_control"]["limit_extensions"][0]
            self.assertEqual(extension["kind"], STATE.LIMIT_EXTENSION_KIND)
            self.assertNotIn("usage_snapshot", extension)
            self.assertIn("usage_anchor", extension)
            self.assertLess(len(json.dumps(extension, separators=(",", ":"))), 6000)
            receipt = root / ".codex" / "evidence" / "limit-extension-receipt.json"
            self.assertTrue(receipt.is_file())
            self.assertTrue(STATE.validate(root)["ok"], STATE.validate(root))

            evidence = root / ".codex" / "evidence"
            transition_authorization = evidence / "state-transition-approval.md"
            transition_authorization.write_text(
                "The user separately authorizes activation after the bounded extension.\n",
                encoding="utf-8",
            )
            transition_request = {
                "kind": STATE.STATE_TRANSITION_KIND,
                "id": "STATE-TRANSITION-ACTIVE-001",
                "reason": "Activate only after the bounded extension cleared the fired limit.",
                "authorization_ref": ".codex/evidence/state-transition-approval.md",
                "recovery_evidence_ref": ".codex/evidence/limit-extension-receipt.json",
                "target_project_state": "active",
                "expected_lineage_id": after["execution_control"]["lineage"]["id"],
                "expected_candidate_fingerprint": after["execution_control"]["candidate"]["fingerprint"],
                "expected_scope_fingerprint": after["execution_control"]["lineage"]["scope_fingerprint"],
            }
            transition_path = root / ".codex" / "STATE_TRANSITION_REQUEST.json"
            transition_path.write_text(
                json.dumps(transition_request, indent=2) + "\n", encoding="utf-8"
            )
            transitioned = STATE.state_transition(root, transition_path, 1)
            self.assertTrue(transitioned["ok"], transitioned)
            self.assertEqual(transitioned["status"], "ready")

            active = json.loads(
                (root / ".codex" / "ACCEPTANCE.json").read_text(encoding="utf-8")
            )
            proposed = copy.deepcopy(active)
            proposed["requirements"][0]["status"] = "failing"
            proposed["requirements"][0]["blocker"] = None
            reconcile_request = {
                "project_outcome_md": SUPPORT.project_text(state="active"),
                "acceptance": proposed,
                "recovery_evidence_ref": None,
            }
            reconcile_path = root / ".codex" / "ATTEMPT_REQUEST.json"
            reconcile_path.write_text(
                json.dumps(reconcile_request, indent=2) + "\n", encoding="utf-8"
            )
            reconciled = STATE.state_reconcile(root, reconcile_path, 2)
            self.assertTrue(reconciled["ok"], reconciled)
            self.assertEqual(reconciled["revision"], 3)
            self.assertEqual(reconciled["status"], "ready")
            self.assertTrue(STATE.validate(root)["ok"], STATE.validate(root))

    def test_exact_total_attempt_admission_stop_can_extend_but_manual_stop_cannot(self) -> None:
        with workspace_temporary_directory() as root:
            state = self.make_blocked_state(root)
            control = state["execution_control"]
            control["usage"]["no_progress_attempts"] = 0
            control["status"] = "stopped"
            control["stop_reason"] = "attempt admission exhausted: total_attempts"
            state["project_state"] = "active"
            SUPPORT.write_state(root, SUPPORT.project_text(state="active"), state)

            evidence = root / ".codex" / "evidence"
            evidence.mkdir(parents=True, exist_ok=True)
            authorization = evidence / "total-attempt-approval.md"
            authorization.write_text("Explicit total-attempt recovery authorization.\n", encoding="utf-8")
            block_request = {
                "kind": STATE.STATE_TRANSITION_KIND,
                "id": "TOTAL-ATTEMPT-BLOCK-001",
                "reason": "The exact total-attempt admission stop is being recorded before bounded recovery.",
                "authorization_ref": ".codex/evidence/total-attempt-approval.md",
                "recovery_evidence_ref": None,
                "target_project_state": "blocked",
                "expected_lineage_id": control["lineage"]["id"],
                "expected_candidate_fingerprint": control["candidate"]["fingerprint"],
                "expected_scope_fingerprint": control["lineage"]["scope_fingerprint"],
            }
            block_path = root / ".codex" / "TOTAL_ATTEMPT_BLOCK_REQUEST.json"
            block_path.write_text(json.dumps(block_request, indent=2) + "\n", encoding="utf-8")
            blocked = STATE.state_transition(root, block_path, 0)
            self.assertTrue(blocked["ok"], blocked)

            blocked_state = json.loads((root / ".codex" / "ACCEPTANCE.json").read_text(encoding="utf-8"))
            request_path = self.request(root, blocked_state, extension_id="LIMIT-EXT-TOTAL-001")
            result = STATE.limit_extend(root, request_path, 1)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["limits"]["total_attempts"], 4)

        with workspace_temporary_directory() as root:
            state = self.make_blocked_state(root)
            control = state["execution_control"]
            control["usage"]["no_progress_attempts"] = 0
            control["status"] = "stopped"
            control["stop_reason"] = "manually stopped at total attempts"
            SUPPORT.write_state(root, SUPPORT.project_text(state="blocked"), state)

            request_path = self.request(root, state, extension_id="LIMIT-EXT-TOTAL-MANUAL-001")
            result = STATE.limit_extend(root, request_path, 0)
            self.assertFalse(result["ok"])
            self.assertIn("exact total-attempt admission exhaustion", " ".join(result["errors"]))

    def test_rejects_stale_or_weakening_requests_without_mutation(self) -> None:
        with workspace_temporary_directory() as root:
            state = self.make_blocked_state(root)
            request_path = self.request(root, state)
            acceptance_path = root / ".codex" / "ACCEPTANCE.json"
            project_path = root / ".codex" / "PROJECT_OUTCOME.md"
            before_acceptance = acceptance_path.read_bytes()
            before_project = project_path.read_bytes()

            stale = STATE.limit_extend(root, request_path, 1)
            self.assertFalse(stale["ok"])
            self.assertEqual(acceptance_path.read_bytes(), before_acceptance)
            self.assertEqual(project_path.read_bytes(), before_project)

            request = json.loads(request_path.read_text(encoding="utf-8"))
            request["limits"]["equivalent_failures"] = 3
            request_path.write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
            weak = STATE.limit_extend(root, request_path, 0)
            self.assertFalse(weak["ok"])
            self.assertIn("permanent floor", " ".join(weak["errors"]))
            self.assertEqual(acceptance_path.read_bytes(), before_acceptance)
            self.assertEqual(project_path.read_bytes(), before_project)

    def test_limit_authorization_content_cannot_be_replayed_under_a_new_path(self) -> None:
        with workspace_temporary_directory() as root:
            state = self.make_blocked_state(root)
            first_request = self.request(root, state)
            first = STATE.limit_extend(root, first_request, 0)
            self.assertTrue(first["ok"], first)

            acceptance_path = root / ".codex" / "ACCEPTANCE.json"
            project_path = root / ".codex" / "PROJECT_OUTCOME.md"
            current = json.loads(acceptance_path.read_text(encoding="utf-8"))
            control = current["execution_control"]
            control["usage"]["no_progress_attempts"] = control["limits"]["no_progress_attempts"]
            control["status"] = "stopped"
            control["stop_reason"] = "aggregate no-progress limit reached"
            SUPPORT.write_json(acceptance_path, current)

            evidence = root / ".codex" / "evidence"
            original = evidence / "user-approval.md"
            replayed = evidence / "replayed-approval.md"
            replayed.write_bytes(original.read_bytes())
            limits = copy.deepcopy(control["limits"])
            for field in (
                "total_attempts",
                "failed_attempts",
                "expensive_attempts",
                "support_attempts",
                "no_progress_attempts",
                "total_tool_calls",
                "support_tool_calls",
                "active_attempt_seconds",
                "spawned_workers",
                "scope_growth_actions",
                "direct_delivery_reserved_calls",
                "max_path_touches",
                "max_touches_per_path",
            ):
                limits[field] += 1
            second_request = {
                "kind": STATE.LIMIT_EXTENSION_KIND,
                "id": "LIMIT-EXT-REPLAY-002",
                "reason": "Attempt to replay prior authority under a new filename.",
                "authorization_ref": ".codex/evidence/replayed-approval.md",
                "receipt_ref": ".codex/evidence/limit-extension-replay-receipt.json",
                "expected_lineage_id": control["lineage"]["id"],
                "expected_candidate_fingerprint": control["candidate"]["fingerprint"],
                "expected_scope_fingerprint": control["lineage"]["scope_fingerprint"],
                "limits": limits,
            }
            request_path = root / ".codex" / "LIMIT_EXTENSION_REQUEST.json"
            SUPPORT.write_json(request_path, second_request)
            before_acceptance = acceptance_path.read_bytes()
            before_project = project_path.read_bytes()

            refused = STATE.limit_extend(root, request_path, 1)

            self.assertFalse(refused["ok"])
            self.assertTrue(
                any("authorization has already been consumed" in error for error in refused["errors"]),
                refused,
            )
            self.assertEqual(acceptance_path.read_bytes(), before_acceptance)
            self.assertEqual(project_path.read_bytes(), before_project)
            self.assertFalse((evidence / "limit-extension-replay-receipt.json").exists())

    def test_hook_allows_only_the_exact_limit_extension_request_path(self) -> None:
        with workspace_temporary_directory() as root:
            self.make_blocked_state(root)
            allowed_request = root / ".codex" / "LIMIT_EXTENSION_REQUEST.json"
            command = (
                f'"{sys.executable}" "{STATE_SCRIPT}" limit-extend --root "{root}" '
                f'--request "{allowed_request}" --expected-revision 0'
            )
            payload = {"tool_name": "Bash", "tool_input": {"command": command}}
            self.assertEqual(HOOK._exact_activation_root(payload, root), root.resolve())
            denied = command.replace("LIMIT_EXTENSION_REQUEST.json", "ATTEMPT_REQUEST.json")
            self.assertIsNone(
                HOOK._exact_activation_root(
                    {"tool_name": "Bash", "tool_input": {"command": denied}}, root
                )
            )

    def test_failure_fingerprint_migration_splits_only_proven_legacy_v1_history(self) -> None:
        with workspace_temporary_directory() as root:
            state = self.make_blocked_state(root)
            control = state["execution_control"]
            source = {
                "fingerprint": STATE.canonical_failure_fingerprint_v1(
                    control["lineage"]["id"],
                    "OUTCOME-TEST",
                    "BOUNDARY-TEST",
                ),
                "lineage_id": control["lineage"]["id"],
                "failure_class": "reasoning-recoverable",
                "acceptance_outcome_id": "OUTCOME-TEST",
                "boundary_id": "BOUNDARY-TEST",
                "earliest_divergence": "Nested child process was denied before the check ran.",
                "candidate_fingerprint": control["candidate"]["fingerprint"],
                "count": 2,
                "last_observed_utc": "2026-01-01T00:00:02Z",
            }
            control["usage"]["failed_attempts"] = 2
            control["usage"]["failure_classes"] = [source]
            control["status"] = "stopped"
            control["stop_reason"] = "equivalent-failure limit reached"
            SUPPORT.write_state(root, SUPPORT.project_text(state="blocked"), state)

            evidence = root / ".codex" / "evidence"
            evidence.mkdir(parents=True, exist_ok=True)
            authorization = evidence / "migration-approval.md"
            authorization.write_text("Explicit one-time ledger split authorization.\n", encoding="utf-8")
            provenance = {
                "kind": STATE.FAILURE_IDENTITY_PROVENANCE_KIND,
                "source": {
                    "kind": "codex-session-transcript",
                    "path": "C:/recovered/session.jsonl",
                    "snapshot_observed_utc": "2026-01-01T00:00:03Z",
                    "snapshot_sha256": "sha256:" + "a" * 64,
                    "custody": "recovered-mutable-transcript",
                },
                "legacy_failure_class": source,
                "attempts": [
                    {
                        "attempt_id": "ATTEMPT-000001",
                        "earliest_divergence": source["earliest_divergence"],
                        "last_observed_utc": "2026-01-01T00:00:01Z",
                        "transcript_line_hashes": ["sha256:" + "b" * 64],
                    },
                    {
                        "attempt_id": "ATTEMPT-000002",
                        "earliest_divergence": "Post-claim revision was stale after the check passed.",
                        "last_observed_utc": "2026-01-01T00:00:02Z",
                        "transcript_line_hashes": ["sha256:" + "c" * 64],
                    },
                ],
            }
            provenance_path = evidence / "recovered-provenance.json"
            provenance_path.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
            request = {
                "kind": STATE.FAILURE_IDENTITY_MIGRATION_KIND,
                "id": "FAILURE-MIGRATION-001",
                "reason": "Split only the proven distinct historic failures without resetting controls.",
                "authorization_ref": ".codex/evidence/migration-approval.md",
                "provenance_ref": ".codex/evidence/recovered-provenance.json",
                "receipt_ref": ".codex/evidence/migration-receipt.json",
                "expected_lineage_id": control["lineage"]["id"],
                "expected_candidate_fingerprint": control["candidate"]["fingerprint"],
                "expected_scope_fingerprint": control["lineage"]["scope_fingerprint"],
                "legacy_fingerprint": source["fingerprint"],
            }
            request_path = root / ".codex" / "FAILURE_FINGERPRINT_MIGRATION_REQUEST.json"
            request_path.write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
            before = json.loads((root / ".codex" / "ACCEPTANCE.json").read_text(encoding="utf-8"))

            result = STATE.failure_fingerprint_migrate(root, request_path, 0)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["revision"], 1)
            after = json.loads((root / ".codex" / "ACCEPTANCE.json").read_text(encoding="utf-8"))
            self.assertEqual(after["execution_control"]["usage"]["failed_attempts"], 2)
            self.assertEqual(after["execution_control"]["limits"], before["execution_control"]["limits"])
            self.assertEqual(
                after["execution_control"]["usage"]["method_families"],
                before["execution_control"]["usage"]["method_families"],
            )
            migrated = after["execution_control"]["usage"]["failure_classes"]
            self.assertEqual(len(migrated), 2)
            self.assertTrue(all(entry["failure_identity_version"] == 2 for entry in migrated))
            self.assertTrue(all(entry["count"] == 1 for entry in migrated))
            self.assertNotEqual(migrated[0]["fingerprint"], migrated[1]["fingerprint"])
            self.assertEqual(len(after["execution_control"]["failure_identity_migrations"]), 1)
            migration_record = after["execution_control"]["failure_identity_migrations"][0]
            self.assertEqual(migration_record["kind"], STATE.FAILURE_IDENTITY_MIGRATION_KIND)
            self.assertNotIn("usage_snapshot", migration_record)
            self.assertIn("usage_anchor", migration_record)
            self.assertIn("result_usage_anchor", migration_record)
            self.assertLess(
                len(json.dumps(migration_record, separators=(",", ":"))),
                6000,
            )
            self.assertTrue(STATE.validate(root)["ok"], STATE.validate(root))

            reset_errors: list[str] = []
            reset_usage = copy.deepcopy(after["execution_control"]["usage"])
            reset_usage["total_attempts"] -= 1
            STATE.validate_usage_monotonic_extension(
                after["execution_control"]["usage"],
                reset_usage,
                "migration-reset",
                reset_errors,
            )
            self.assertTrue(any("total_attempts cannot decrease" in error for error in reset_errors))

            extension_path = self.request(root, after, extension_id="LIMIT-EXT-MIGRATION-001")
            extended = STATE.limit_extend(root, extension_path, 1)
            self.assertTrue(extended["ok"], extended)
            extended_state = json.loads(
                (root / ".codex" / "ACCEPTANCE.json").read_text(encoding="utf-8")
            )

            transition_authorization = evidence / "migration-state-transition-approval.md"
            transition_authorization.write_text(
                "The user separately authorizes activation after migration recovery.\n",
                encoding="utf-8",
            )
            transition_request = {
                "kind": STATE.STATE_TRANSITION_KIND,
                "id": "STATE-TRANSITION-MIGRATION-001",
                "reason": "Activate only after migration and bounded extension are recorded.",
                "authorization_ref": ".codex/evidence/migration-state-transition-approval.md",
                "recovery_evidence_ref": ".codex/evidence/limit-extension-receipt.json",
                "target_project_state": "active",
                "expected_lineage_id": extended_state["execution_control"]["lineage"]["id"],
                "expected_candidate_fingerprint": extended_state["execution_control"]["candidate"]["fingerprint"],
                "expected_scope_fingerprint": extended_state["execution_control"]["lineage"]["scope_fingerprint"],
            }
            transition_path = root / ".codex" / "STATE_TRANSITION_REQUEST.json"
            transition_path.write_text(
                json.dumps(transition_request, indent=2) + "\n", encoding="utf-8"
            )
            transitioned = STATE.state_transition(root, transition_path, 2)
            self.assertTrue(transitioned["ok"], transitioned)

            active_state = json.loads(
                (root / ".codex" / "ACCEPTANCE.json").read_text(encoding="utf-8")
            )
            proposed = copy.deepcopy(active_state)
            proposed["requirements"][0]["status"] = "failing"
            proposed["requirements"][0]["blocker"] = None
            reconcile_request = {
                "project_outcome_md": SUPPORT.project_text(state="active"),
                "acceptance": proposed,
                "recovery_evidence_ref": None,
            }
            reconcile_path = root / ".codex" / "ATTEMPT_REQUEST.json"
            reconcile_path.write_text(json.dumps(reconcile_request, indent=2) + "\n", encoding="utf-8")
            reconciled = STATE.state_reconcile(root, reconcile_path, 3)
            self.assertTrue(reconciled["ok"], reconciled)

            (root / "project.marker").write_text("changed candidate\n", encoding="utf-8")
            rebound = STATE.candidate_bind(root, 4, [])
            self.assertTrue(rebound["ok"], rebound)
            self.assertTrue(STATE.validate(root)["ok"], STATE.validate(root))

    def test_hook_allows_only_the_exact_failure_migration_request_path(self) -> None:
        with workspace_temporary_directory() as root:
            self.make_blocked_state(root)
            allowed_request = root / ".codex" / "FAILURE_FINGERPRINT_MIGRATION_REQUEST.json"
            command = (
                f'"{sys.executable}" "{STATE_SCRIPT}" failure-fingerprint-migrate --root "{root}" '
                f'--request "{allowed_request}" --expected-revision 0'
            )
            payload = {"tool_name": "Bash", "tool_input": {"command": command}}
            self.assertEqual(HOOK._exact_activation_root(payload, root), root.resolve())
            denied = command.replace("FAILURE_FINGERPRINT_MIGRATION_REQUEST.json", "ATTEMPT_REQUEST.json")
            self.assertIsNone(
                HOOK._exact_activation_root(
                    {"tool_name": "Bash", "tool_input": {"command": denied}}, root
                )
            )


if __name__ == "__main__":
    unittest.main()
