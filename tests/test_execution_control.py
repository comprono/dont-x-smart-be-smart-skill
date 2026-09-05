from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
STATE_SCRIPT = (
    REPOSITORY_ROOT
    / "skills"
    / "outcome-integrity"
    / "scripts"
    / "project_outcome.py"
)
SUPPORT_SCRIPT = REPOSITORY_ROOT / "tests" / "test_package.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExecutionControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.state = load_module(STATE_SCRIPT, "execution_control_state")
        cls.support = load_module(SUPPORT_SCRIPT, "execution_control_support")

    def setUp(self) -> None:
        self.attempt_inputs: dict[str, tuple[dict, object]] = {}

    @staticmethod
    def complete_attempt_request(request: dict) -> dict:
        for field in (
            "prior_method_family_id",
            "method_change_evidence_ref",
            "lower_complexity_comparison_ref",
        ):
            request.setdefault(field, None)
        return request

    def write_active(self, root: Path):
        acceptance = self.support.acceptance_data()
        project = self.support.project_text()
        self.assertIn(self.state.EXECUTION_CONTROL_AUTHORITY_LINE, project.splitlines())
        self.support.write_state(root, project, acceptance)
        snapshot_directory = self.state.control_snapshot_directory(root)
        self.addCleanup(shutil.rmtree, snapshot_directory, True)
        return acceptance

    def begin(self, root: Path, acceptance: dict, **request_options):
        request_path = root / "request.json"
        tool_input = request_options.get("tool_input", {"cmd": "run-generic-gate"})
        request = self.complete_attempt_request(
            self.support.attempt_request(acceptance, **request_options)
        )
        self.support.write_json(
            request_path,
            request,
        )
        result = self.state.attempt_begin(root, request_path, acceptance["execution_control"]["revision"])
        self.assertTrue(result["ok"], result)
        self.attempt_inputs[result["attempt"]["id"]] = (request, tool_input)
        return result

    def claim_and_observe(
        self,
        root: Path,
        begun: dict,
        *,
        outcome: str = "completed",
        duration: int = 1,
        produce_evidence: bool = True,
    ) -> tuple[dict, dict]:
        request, tool_input = self.attempt_inputs[begun["attempt"]["id"]]
        payload = {
            "tool_use_id": "tool-" + begun["attempt"]["id"],
            "tool_name": request["tool_binding"]["tool_name"],
            "cwd": str(root / request["tool_binding"]["cwd_relative"]),
            "tool_input": tool_input,
        }
        claimed = self.state.hook_pre_claim(root, payload)
        self.assertTrue(claimed["ok"], claimed)
        evidence_ref = request.get("causal_evidence_ref")
        if produce_evidence and "proof" in request["action_classes"] and evidence_ref:
            evidence_path = root / evidence_ref
            evidence_path.parent.mkdir(parents=True, exist_ok=True)
            evidence_path.write_text(
                json.dumps({"attempt_id": begun["attempt"]["id"], "passed": True}),
                encoding="utf-8",
            )
        observed = self.state.hook_post_observe(
            root,
            {**payload, "outcome": outcome, "duration_seconds": duration},
        )
        self.assertTrue(observed["ok"], observed)
        begun["revision"] = observed["revision"]
        return claimed, observed

    def finish(self, root: Path, begun: dict, result: dict):
        result_path = root / "result.json"
        self.support.write_json(result_path, result)
        return self.state.attempt_finish(root, result_path, begun["revision"])

    def test_receipt_cannot_satisfy_another_requirement_or_evidence_ref(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = self.support.acceptance_data(
                project_state="complete",
                current_id=None,
                status="passing",
                evidence_level="end-to-end",
            )
            self.support.write_state(
                root,
                self.support.project_text(state="complete", current_id="none"),
                state,
            )
            receipt = state["execution_control"]["gate_receipts"][0]
            state["execution_control"]["gate_receipts"] = [receipt]
            for requirement in state["requirements"]:
                requirement["evidence"][0]["gate_receipt_id"] = receipt["id"]
            self.support.write_json(root / ".codex" / "ACCEPTANCE.json", state)

            result = self.state.validate(root, mode="completion")
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("receipt binding mismatches" in error for error in result["errors"]),
                result,
            )

            state = self.support.acceptance_data(
                project_state="complete",
                current_id=None,
                status="passing",
                evidence_level="end-to-end",
            )
            self.support.write_state(
                root,
                self.support.project_text(state="complete", current_id="none"),
                state,
            )
            state["requirements"][0]["evidence"][0]["ref"] = "different/result.json"
            self.support.write_json(root / ".codex" / "ACCEPTANCE.json", state)
            result = self.state.validate(root, mode="completion")
            self.assertFalse(result["ok"])
            self.assertTrue(any("evidence_ref" in error for error in result["errors"]), result)

    def test_control_status_exposes_minimum_attempt_bootstrap_context(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = self.write_active(root)

            status = self.state.control_status(root)

            self.assertTrue(status["ok"], status)
            self.assertEqual(
                status["outcome_id"], state["outcome_hierarchy"]["north_star"]["id"]
            )
            self.assertEqual(
                status["current_stage_id"],
                state["outcome_hierarchy"]["current_stage_id"],
            )
            requirement = next(
                entry
                for entry in state["requirements"]
                if entry["id"] == state["current_slice_requirement_id"]
            )
            self.assertEqual(
                status["current_slice"]["requirement_id"], requirement["id"]
            )
            self.assertEqual(
                status["current_slice"]["predecessor_requirement_ids"],
                requirement["predecessor_requirement_ids"],
            )
            self.assertEqual(
                status["lineage"]["scope_fingerprint"],
                state["execution_control"]["lineage"]["scope_fingerprint"],
            )
            self.assertEqual(
                status["candidate_fingerprint"],
                state["execution_control"]["candidate"]["fingerprint"],
            )
            self.assertEqual(
                status["usage"],
                self.state.compact_usage_anchor(state["execution_control"]["usage"]),
            )
            self.assertNotIn("failure_classes", status["usage"])
            self.assertNotIn("method_families", status["usage"])
            self.assertEqual(status["gate_receipt_count"], 0)

            verbose = self.state.control_status(root, verbose=True)
            self.assertEqual(
                verbose["usage"], state["execution_control"]["usage"]
            )
            self.assertNotIn("manifest_paths", json.dumps(status))

    def test_finish_rejects_a_correction_after_reservation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = self.write_active(root)
            begun = self.begin(root, state)
            (root / ".codex" / "PROJECT_OUTCOME.md").write_text(
                self.support.project_text(updated="2026-07-16T10:00:01Z"),
                encoding="utf-8",
            )
            finished = self.finish(
                root,
                begun,
                self.support.attempt_result(
                    attempt_id=begun["attempt"]["id"],
                    outcome="passed",
                    progress=True,
                ),
            )
            self.assertFalse(finished["ok"])
            self.assertTrue(
                any("reconciliation timestamps" in error for error in finished["errors"]),
                finished,
            )

    def test_schema_v6_uses_one_static_mutable_ledger_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = self.write_active(root)
            project_path = root / ".codex" / "PROJECT_OUTCOME.md"
            project_path.write_text(
                project_path.read_text(encoding="utf-8").replace(
                    self.state.EXECUTION_CONTROL_AUTHORITY_LINE,
                    self.state.EXECUTION_CONTROL_AUTHORITY_LINE
                    + "\n- Execution-control revision: 0",
                ),
                encoding="utf-8",
            )
            result = self.state.validate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("forbids duplicated mutable" in error for error in result["errors"]),
                result,
            )

    def test_scope_fingerprint_includes_north_star_and_fitness_definitions(self) -> None:
        state = self.support.acceptance_data()
        original = self.state.calculate_scope_fingerprint(state)
        state["outcome_hierarchy"]["north_star"]["description"] = "A changed controlling outcome."
        self.assertNotEqual(original, self.state.calculate_scope_fingerprint(state))
        state = self.support.acceptance_data()
        original = self.state.calculate_scope_fingerprint(state)
        state["outcome_hierarchy"]["north_star"]["fitness_dimensions"][0][
            "description"
        ] = "A changed fitness definition."
        self.assertNotEqual(original, self.state.calculate_scope_fingerprint(state))

    def test_failure_fingerprint_is_canonical_and_caller_cannot_change_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = self.write_active(root)
            state["execution_control"]["limits"]["no_progress_attempts"] = 5
            self.support.write_state(root, self.support.project_text(), state)
            begun = self.begin(root, state)
            bad = self.support.attempt_result(
                attempt_id=begun["attempt"]["id"],
                outcome="failed",
                progress=False,
                earliest_divergence="  Same   Boundary  ",
            )
            bad["failure_fingerprint"] = "sha256:" + "f" * 64
            refused = self.finish(root, begun, bad)
            self.assertFalse(refused["ok"])
            self.assertTrue(
                any("canonical failure identity" in error for error in refused["errors"]),
                refused,
            )

            good = self.support.attempt_result(
                attempt_id=begun["attempt"]["id"],
                outcome="failed",
                progress=False,
                earliest_divergence="same boundary",
            )
            finished = self.finish(root, begun, good)
            self.assertTrue(finished["ok"], finished)
            current = json.loads(
                (root / ".codex" / "ACCEPTANCE.json").read_text(encoding="utf-8")
            )
            recorded = current["execution_control"]["usage"]["failure_classes"][0]
            self.assertEqual(recorded["failure_identity_version"], 3)
            expected = self.state.canonical_failure_fingerprint(
                begun["attempt"], "Same Boundary"
            )
            self.assertEqual(recorded["fingerprint"], expected)
            self.assertEqual(
                expected,
                self.state.canonical_failure_fingerprint(
                    begun["attempt"], "Different earliest divergence"
                ),
            )

    def test_acceptance_outcome_identity_is_bound_to_the_live_north_star(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = self.write_active(root)
            request = self.complete_attempt_request(
                self.support.attempt_request(
                    state,
                    acceptance_outcome_id="OUTCOME-SUBSTITUTE",
                )
            )
            request_path = root / "substituted-outcome.json"
            self.support.write_json(request_path, request)

            refused = self.state.attempt_begin(root, request_path, 0)

            self.assertFalse(refused["ok"])
            self.assertTrue(
                any("north-star outcome" in error for error in refused["errors"]),
                refused,
            )

    def test_completed_failed_evaluation_is_exposed_automatically(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = self.write_active(root)
            state["execution_control"]["limits"]["no_progress_attempts"] = 5
            self.support.write_state(root, self.support.project_text(), state)
            evaluation = "sha256:" + "6" * 64
            begun = self.begin(
                root,
                state,
                evaluation_fingerprint=evaluation,
                evaluation_role="prospective",
            )
            finished = self.finish(
                root,
                begun,
                self.support.attempt_result(
                    attempt_id=begun["attempt"]["id"],
                    outcome="failed",
                    progress=False,
                ),
            )
            self.assertTrue(finished["ok"], finished)
            current = json.loads(
                (root / ".codex" / "ACCEPTANCE.json").read_text(encoding="utf-8")
            )
            self.assertIn(
                evaluation,
                current["execution_control"]["diagnostic_evaluation_fingerprints"],
            )
            request_path = root / "second-request.json"
            self.support.write_json(
                request_path,
                self.complete_attempt_request(self.support.attempt_request(
                    current,
                    evaluation_fingerprint=evaluation,
                    evaluation_role="prospective",
                )),
            )
            refused = self.state.attempt_begin(
                root, request_path, finished["revision"]
            )
            self.assertFalse(refused["ok"])
            self.assertTrue(any("exposed evaluation" in error for error in refused["errors"]), refused)

    def test_aborted_effectful_attempt_stops_for_authoritative_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = self.support.acceptance_data()
            context = "sha256:" + "9" * 64
            state["execution_control"]["authorizations"] = [
                {
                    "id": "AUTH-001",
                    "action": "Apply the exact external update.",
                    "effect": "Change only the declared target.",
                    "target_identity_ids": ["ENTITY-001"],
                    "principal": "Codex",
                    "context_fingerprint": context,
                    "authorized_utc": "2026-07-16T10:00:00Z",
                    "expires_utc": "2099-07-16T10:00:00Z",
                    "uses_remaining": 2,
                    "status": "active",
                }
            ]
            self.support.write_state(root, self.support.project_text(), state)
            begun = self.begin(
                root,
                state,
                action_classes=["local", "external-write"],
                authorization_id="AUTH-001",
                target_identity_ids=["ENTITY-001"],
                action="Apply the exact external update.",
                effect="Change only the declared target.",
                context_fingerprint=context,
            )
            finished = self.finish(
                root,
                begun,
                self.support.attempt_result(
                    attempt_id=begun["attempt"]["id"],
                    outcome="aborted",
                    progress=False,
                ),
            )
            self.assertTrue(finished["ok"], finished)
            self.assertEqual(finished["status"], "stopped")
            self.assertIn("authoritative state", finished["stop_reason"])

    def test_broad_manifest_excludes_internal_state_and_lock_is_external(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = self.support.acceptance_data()
            state["execution_control"]["candidate"]["manifest_paths"] = ["."]
            self.support.write_state(root, self.support.project_text(), state)
            result = self.state.validate(root, mode="resume")
            self.assertTrue(result["ok"], result)
            with self.state.acceptance_lock(root):
                pass
            self.assertFalse((root / ".codex" / "ACCEPTANCE.lock").exists())
            self.assertTrue(self.state.validate(root, mode="resume")["ok"])

    def test_future_and_misordered_control_times_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = self.support.acceptance_data()
            state["execution_control"]["authorizations"] = [
                {
                    "id": "AUTH-001",
                    "action": "Apply an update.",
                    "effect": "Change one target.",
                    "target_identity_ids": ["ENTITY-001"],
                    "principal": "Codex",
                    "context_fingerprint": "sha256:" + "1" * 64,
                    "authorized_utc": "2099-01-01T00:00:00Z",
                    "expires_utc": "2100-01-01T00:00:00Z",
                    "uses_remaining": 1,
                    "status": "active",
                }
            ]
            self.support.write_state(root, self.support.project_text(), state)
            result = self.state.validate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("cannot be in the future" in error for error in result["errors"]), result)

            state = self.support.acceptance_data()
            state["execution_control"]["prerequisites"] = [
                {
                    "id": "PREREQ-001",
                    "description": "The downstream boundary is ready.",
                    "status": "verified",
                    "evidence_ref": "tests/evidence/prerequisite.json",
                    "verified_utc": "2026-07-16T10:00:00Z",
                    "expires_utc": "2026-07-15T10:00:00Z",
                    "context_fingerprint": "sha256:" + "1" * 64,
                    "requirement_ids": ["REQ-001"],
                    "action_classes": ["proof"],
                    "gate_tiers": ["change"],
                }
            ]
            self.support.write_state(root, self.support.project_text(), state)
            result = self.state.validate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("later than verified_utc" in error for error in result["errors"]), result)

    def test_caller_progress_lie_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = self.write_active(root)
            begun = self.begin(root, state)
            failed = self.finish(
                root,
                begun,
                self.support.attempt_result(
                    attempt_id=begun["attempt"]["id"],
                    outcome="failed",
                    progress=True,
                ),
            )
            self.assertTrue(failed["ok"], failed)
            self.assertFalse(failed["derived_acceptance_progress"])
            self.assertTrue(failed["caller_acceptance_progress"])

    def test_unreserved_forged_single_use_and_missing_post_are_denied(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = self.write_active(root)
            payload = {
                "tool_use_id": "tool-one",
                "tool_name": "Bash",
                "cwd": str(root),
                "tool_input": {"cmd": "echo proof"},
            }
            unreserved_local = self.state.hook_pre_claim(root, payload)
            self.assertTrue(unreserved_local["ok"], unreserved_local)
            self.assertEqual(unreserved_local["decision"], "bypass")
            unreserved_external = self.state.hook_pre_claim(
                root,
                {
                    **payload,
                    "tool_name": "mcp__mail__send_message",
                    "tool_input": {"target": "recipient", "body": "protected"},
                },
            )
            self.assertFalse(unreserved_external["ok"], unreserved_external)

            begun = self.begin(root, state)
            request, tool_input = self.attempt_inputs[begun["attempt"]["id"]]
            exact = {
                "tool_use_id": "tool-one",
                "tool_name": request["tool_binding"]["tool_name"],
                "cwd": str(root),
                "tool_input": tool_input,
            }
            ledger_path = root / ".codex" / "ACCEPTANCE.json"
            before = ledger_path.read_bytes()
            unrelated = self.state.hook_pre_claim(
                root, {**exact, "tool_input": {"cmd": "other"}}
            )
            self.assertTrue(unrelated["ok"], unrelated)
            self.assertEqual(unrelated["decision"], "bypass")
            self.assertEqual(ledger_path.read_bytes(), before)
            forged = self.state.hook_pre_claim(
                root,
                {**exact, "tool_input": {"cmd": 'codex exec "different protected action"'}},
            )
            self.assertFalse(forged["ok"])
            self.assertEqual(ledger_path.read_bytes(), before)
            claimed = self.state.hook_pre_claim(root, exact)
            self.assertTrue(claimed["ok"], claimed)
            self.assertFalse(self.state.hook_pre_claim(root, exact)["ok"])
            missing_post = self.finish(
                root,
                {**begun, "revision": claimed["revision"]},
                self.support.attempt_result(
                    attempt_id=begun["attempt"]["id"], outcome="passed", progress=True
                ),
            )
            self.assertFalse(missing_post["ok"])
            mismatch = self.state.hook_post_observe(
                root,
                {**exact, "tool_use_id": "wrong", "outcome": "completed"},
            )
            self.assertFalse(mismatch["ok"])

    def test_read_only_hook_bypass_is_byte_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_active(root)
            path = root / ".codex" / "ACCEPTANCE.json"
            before = path.read_bytes()
            payload = {
                "tool_use_id": "read-one",
                "tool_name": "view_image",
                "cwd": str(root),
                "tool_input": {"path": "image.png"},
            }
            self.assertEqual(self.state.hook_pre_claim(root, payload)["decision"], "bypass")
            self.assertEqual(
                self.state.hook_post_observe(
                    root, {**payload, "outcome": "completed", "duration_seconds": 1}
                )["decision"],
                "bypass",
            )
            self.assertEqual(path.read_bytes(), before)

    def test_passing_proof_mints_receipt_without_support_no_progress_charge(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = self.write_active(root)
            begun = self.begin(root, state)
            self.claim_and_observe(root, begun)
            finished = self.finish(
                root,
                begun,
                self.support.attempt_result(
                    attempt_id=begun["attempt"]["id"], outcome="passed", progress=False
                ),
            )
            self.assertTrue(finished["ok"], finished)
            self.assertIsNotNone(finished["receipt"])
            current = json.loads((root / ".codex" / "ACCEPTANCE.json").read_text())
            self.assertEqual(current["execution_control"]["usage"]["support_no_progress_calls"], 0)

    def test_external_write_tool_cannot_be_labeled_local(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = self.write_active(root)
            request_path = root / "request.json"
            self.support.write_json(
                request_path,
                self.complete_attempt_request(self.support.attempt_request(
                    state,
                    action_classes=["local"],
                    tool_name="mcp__github__create_issue",
                )),
            )
            refused = self.state.attempt_begin(root, request_path, 0)
            self.assertFalse(refused["ok"])
            self.assertTrue(any("cannot lower" in error for error in refused["errors"]), refused)

    def test_move_destination_outside_allowed_paths_is_denied(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = self.write_active(root)
            patch = "*** Begin Patch\n*** Update File: project.marker\n*** Move to: escaped.marker\n@@\n-test project\n+changed\n*** End Patch"
            begun = self.begin(
                root,
                state,
                action_classes=["local"],
                tool_name="apply_patch",
                allowed_paths=["project.marker"],
                tool_input={"patch": patch},
            )
            request, tool_input = self.attempt_inputs[begun["attempt"]["id"]]
            refused = self.state.hook_pre_claim(
                root,
                {
                    "tool_use_id": "move-one",
                    "tool_name": "apply_patch",
                    "cwd": str(root),
                    "tool_input": tool_input,
                },
            )
            self.assertFalse(refused["ok"])
            self.assertTrue(any("escaped.marker" in error for error in refused["errors"]), refused)
            current = json.loads((root / ".codex" / "ACCEPTANCE.json").read_text())
            self.assertEqual(current["execution_control"]["usage"]["path_touches"], 0)

    def test_control_state_targets_cannot_be_authorized_as_tool_paths(self) -> None:
        patch_cases = (
            (
                "ledger-source",
                "*** Begin Patch\n*** Update File: .codex/ACCEPTANCE.json\n@@\n-{}\n+{}\n*** End Patch",
                ".codex/ACCEPTANCE.json",
            ),
            (
                "ledger-move",
                "*** Begin Patch\n*** Update File: project.marker\n*** Move to: .codex/PROJECT_OUTCOME.md\n@@\n-test project\n+changed\n*** End Patch",
                ".codex/PROJECT_OUTCOME.md",
            ),
            (
                "custody-receipt",
                "*** Begin Patch\n*** Add File: .codex/.outcome-integrity-control-snapshots/forged.json\n+{}\n*** End Patch",
                ".codex/.outcome-integrity-control-snapshots/forged.json",
            ),
        )
        for label, patch, expected_path in patch_cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                state = self.write_active(root)
                begun = self.begin(
                    root,
                    state,
                    action_classes=["local"],
                    tool_name="apply_patch",
                    allowed_paths=["."],
                    tool_input={"patch": patch},
                    causal_evidence_ref=None,
                )
                _, tool_input = self.attempt_inputs[begun["attempt"]["id"]]
                refused = self.state.hook_pre_claim(
                    root,
                    {
                        "tool_use_id": "control-state-" + label,
                        "tool_name": "apply_patch",
                        "cwd": str(root),
                        "tool_input": tool_input,
                    },
                )
                self.assertFalse(refused["ok"])
                self.assertTrue(
                    any(
                        "use state-reconcile" in error and expected_path in error
                        for error in refused["errors"]
                    ),
                    refused,
                )
                current = json.loads(
                    (root / ".codex" / "ACCEPTANCE.json").read_text()
                )
                self.assertEqual(
                    current["execution_control"]["usage"]["path_touches"], 0
                )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = self.write_active(root)
            command = (
                "Set-Content -LiteralPath .codex/ACCEPTANCE.json -Value '{}'"
            )
            begun = self.begin(
                root,
                state,
                action_classes=["local"],
                tool_input={"cmd": command},
                causal_evidence_ref=None,
            )
            _, tool_input = self.attempt_inputs[begun["attempt"]["id"]]
            refused = self.state.hook_pre_claim(
                root,
                {
                    "tool_use_id": "shell-ledger-write",
                    "tool_name": "exec_command",
                    "cwd": str(root),
                    "tool_input": tool_input,
                },
            )
            self.assertFalse(refused["ok"])
            self.assertTrue(any("use state-reconcile" in error for error in refused["errors"]))

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = self.write_active(root)
            command = (
                "Set-Content -LiteralPath "
                ".codex/.outcome-integrity-control-snapshots/forged.json -Value '{}'"
            )
            begun = self.begin(
                root,
                state,
                action_classes=["local"],
                tool_input={"cmd": command},
                causal_evidence_ref=None,
            )
            _, tool_input = self.attempt_inputs[begun["attempt"]["id"]]
            refused = self.state.hook_pre_claim(
                root,
                {
                    "tool_use_id": "shell-custody-write",
                    "tool_name": "exec_command",
                    "cwd": str(root),
                    "tool_input": tool_input,
                },
            )
            self.assertFalse(refused["ok"])
            self.assertTrue(any("use state-reconcile" in error for error in refused["errors"]))

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = self.write_active(root)
            documentation = (
                "Write-Output 'Documentation: .codex/ACCEPTANCE.json is reconciled state'"
            )
            begun = self.begin(
                root,
                state,
                action_classes=["local"],
                tool_input={"cmd": documentation},
                causal_evidence_ref=None,
            )
            _, tool_input = self.attempt_inputs[begun["attempt"]["id"]]
            allowed = self.state.hook_pre_claim(
                root,
                {
                    "tool_use_id": "docs-mention",
                    "tool_name": "exec_command",
                    "cwd": str(root),
                    "tool_input": tool_input,
                },
            )
            self.assertTrue(allowed["ok"], allowed)

    def test_indirect_execution_control_tamper_is_restored_and_stopped(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = self.write_active(root)
            private_marker = "RAW-PRIVATE-TOOL-CONTENT"
            tool_input = {
                "cmd": "python mutate_state.py",
                "private_output": private_marker,
            }
            begun = self.begin(root, state, tool_input=tool_input)
            request, exact_input = self.attempt_inputs[begun["attempt"]["id"]]
            payload = {
                "tool_use_id": "indirect-tamper",
                "tool_name": request["tool_binding"]["tool_name"],
                "cwd": str(root),
                "tool_input": exact_input,
            }
            claimed = self.state.hook_pre_claim(root, payload)
            self.assertTrue(claimed["ok"], claimed)

            snapshot_files = list(
                self.state.control_snapshot_directory(root).glob("*.pending.json")
            )
            self.assertEqual(len(snapshot_files), 1)
            self.assertNotIn(
                private_marker,
                snapshot_files[0].read_text(encoding="utf-8"),
            )

            acceptance_path = root / ".codex" / "ACCEPTANCE.json"
            tampered = json.loads(acceptance_path.read_text(encoding="utf-8"))
            tampered_control = tampered["execution_control"]
            tampered_control["limits"]["total_tool_calls"] = 999999
            tampered_control["usage"]["total_tool_calls"] = 0
            tampered_control["usage"]["active_attempt_seconds"] = 0
            tampered_control["usage"]["method_families"] = []
            tampered_control["active_attempt"]["tool_claim"]["tool_use_id"] = "forged"
            tampered_control["revision"] = 0
            tampered["requirements"][0]["status"] = "passing"
            tampered["requirements"][0]["evidence"] = []
            self.support.write_json(acceptance_path, tampered)

            observed = self.state.hook_post_observe(
                root,
                {**payload, "outcome": "completed", "duration_seconds": 1},
            )
            self.assertFalse(observed["ok"], observed)
            self.assertEqual(observed["status"], "stopped")
            self.assertTrue(any("drift" in error for error in observed["errors"]))

            restored = json.loads(acceptance_path.read_text(encoding="utf-8"))[
                "execution_control"
            ]
            self.assertEqual(restored["limits"]["total_tool_calls"], 24)
            self.assertEqual(restored["usage"]["total_tool_calls"], 1)
            self.assertEqual(restored["usage"]["active_attempt_seconds"], 0)
            self.assertEqual(len(restored["usage"]["method_families"]), 1)
            self.assertIsNone(restored["active_attempt"])
            self.assertEqual(restored["status"], "stopped")
            self.assertEqual(restored["revision"], claimed["revision"] + 1)
            self.assertEqual(
                restored["last_integrity_incident"]["tool_use_id"],
                "indirect-tamper",
            )
            restored_state = json.loads(acceptance_path.read_text(encoding="utf-8"))
            self.assertEqual(restored_state["requirements"][0]["status"], "failing")
            self.assertFalse(snapshot_files[0].exists())

    def test_candidate_change_settles_without_counting_activity_as_progress(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = self.write_active(root)
            patch = "*** Begin Patch\n*** Update File: project.marker\n@@\n-test project\n+changed\n*** End Patch"
            begun = self.begin(
                root,
                state,
                action_classes=["local"],
                tool_name="apply_patch",
                allowed_paths=["project.marker"],
                tool_input={"patch": patch},
                causal_evidence_ref=None,
            )
            request, tool_input = self.attempt_inputs[begun["attempt"]["id"]]
            payload = {
                "tool_use_id": "patch-one",
                "tool_name": "apply_patch",
                "cwd": str(root),
                "tool_input": tool_input,
            }
            claimed = self.state.hook_pre_claim(root, payload)
            self.assertTrue(claimed["ok"], claimed)
            (root / "project.marker").write_text("changed\n", encoding="utf-8")
            observed = self.state.hook_post_observe(
                root, {**payload, "outcome": "completed", "duration_seconds": 1}
            )
            self.assertTrue(observed["ok"], observed)
            self.assertTrue(observed["candidate_changed"])
            self.assertFalse(observed["progress_observed"])
            begun["revision"] = observed["revision"]
            finished = self.finish(
                root,
                begun,
                self.support.attempt_result(
                    attempt_id=begun["attempt"]["id"], outcome="passed", progress=True
                ),
            )
            self.assertTrue(finished["ok"], finished)
            self.assertIsNone(finished["receipt"])
            self.assertFalse(finished["derived_acceptance_progress"])

    def test_project_cumulative_elapsed_budget_stops_next_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = self.write_active(root)
            state["execution_control"]["limits"]["active_attempt_seconds"] = 2
            self.support.write_state(root, self.support.project_text(), state)
            begun = self.begin(root, state)
            self.claim_and_observe(root, begun, duration=2)
            finished = self.finish(
                root,
                begun,
                self.support.attempt_result(
                    attempt_id=begun["attempt"]["id"], outcome="passed", progress=True
                ),
            )
            self.assertTrue(finished["ok"], finished)
            self.assertEqual(finished["status"], "stopped")
            self.assertIn("active-attempt time", finished["stop_reason"])
            current = json.loads((root / ".codex" / "ACCEPTANCE.json").read_text())
            current["requirements"][0]["status"] = "failing"
            current["requirements"][0]["evidence"] = []
            current["execution_control"]["gate_receipts"] = []
            self.support.write_json(root / ".codex" / "ACCEPTANCE.json", current)
            request_path = root / "request.json"
            self.support.write_json(
                request_path,
                self.complete_attempt_request(
                    self.support.attempt_request(current)
                ),
            )
            refused = self.state.attempt_begin(root, request_path, finished["revision"])
            self.assertFalse(refused["ok"])
            self.assertTrue(any("stopped" in error for error in refused["errors"]), refused)

    def test_repeated_green_proof_without_fresh_evidence_is_no_progress(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = self.write_active(root)
            first = self.begin(root, state)
            self.claim_and_observe(root, first)
            first_finished = self.finish(
                root,
                first,
                self.support.attempt_result(
                    attempt_id=first["attempt"]["id"], outcome="passed", progress=True
                ),
            )
            self.assertIsNotNone(first_finished["receipt"])
            current = json.loads((root / ".codex" / "ACCEPTANCE.json").read_text())
            second = self.begin(root, current, external_run_id="repeat")
            self.claim_and_observe(root, second, produce_evidence=False)
            repeated = self.finish(
                root,
                second,
                self.support.attempt_result(
                    attempt_id=second["attempt"]["id"], outcome="passed", progress=True
                ),
            )
            self.assertTrue(repeated["ok"], repeated)
            self.assertIsNone(repeated["receipt"])
            self.assertFalse(repeated["derived_acceptance_progress"])

    def test_method_family_breaks_after_two_failures_across_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = self.write_active(root)
            state["execution_control"]["limits"]["failed_attempts"] = 5
            state["execution_control"]["limits"]["no_progress_attempts"] = 5
            self.support.write_state(root, self.support.project_text(), state)
            revision = 0
            for index, boundary in enumerate(("BOUNDARY-ONE", "BOUNDARY-TWO")):
                current = json.loads((root / ".codex" / "ACCEPTANCE.json").read_text())
                current["execution_control"]["revision"] = revision
                begun = self.begin(root, current, boundary_id=boundary, external_run_id=f"run-{index}")
                finished = self.finish(
                    root,
                    begun,
                    self.support.attempt_result(
                        attempt_id=begun["attempt"]["id"], outcome="failed", progress=False
                    ),
                )
                self.assertTrue(finished["ok"], finished)
                revision = finished["revision"]
            self.assertEqual(finished["method_family_status"], "stopped")

    def test_method_family_relabel_is_denied_but_evidence_backed_change_is_admitted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = self.write_active(root)
            state["execution_control"]["limits"]["failed_attempts"] = 8
            state["execution_control"]["limits"]["no_progress_attempts"] = 8
            self.support.write_state(root, self.support.project_text(), state)
            revision = 0
            for index, boundary in enumerate(("BOUNDARY-ONE", "BOUNDARY-TWO")):
                current = json.loads(
                    (root / ".codex" / "ACCEPTANCE.json").read_text()
                )
                begun = self.begin(
                    root,
                    current,
                    boundary_id=boundary,
                    external_run_id=f"family-stop-{index}",
                )
                finished = self.finish(
                    root,
                    begun,
                    self.support.attempt_result(
                        attempt_id=begun["attempt"]["id"],
                        outcome="failed",
                        progress=False,
                    ),
                )
                self.assertTrue(finished["ok"], finished)
                revision = finished["revision"]
            current = json.loads(
                (root / ".codex" / "ACCEPTANCE.json").read_text()
            )
            prior = current["execution_control"]["usage"]["method_families"][0]
            self.assertEqual(prior["status"], "stopped")

            change_path = root / "evidence" / "method-change.json"
            comparison_path = root / "evidence" / "lower-complexity.json"
            change_path.parent.mkdir(parents=True, exist_ok=True)
            change_path.write_text('{"changed_boundary": true}', encoding="utf-8")
            comparison_path.write_text('{"lower_complexity": true}', encoding="utf-8")
            recovery_fields = {
                "prior_method_family_id": prior["id"],
                "method_change_evidence_ref": "evidence/method-change.json",
                "lower_complexity_comparison_ref": (
                    "evidence/lower-complexity.json"
                ),
            }

            relabel = self.complete_attempt_request(
                self.support.attempt_request(
                    current,
                    method_family_id="METHOD-RELABEL",
                    external_run_id="relabel",
                )
            )
            relabel.update(recovery_fields)
            request_path = root / "relabel.json"
            self.support.write_json(request_path, relabel)
            refused = self.state.attempt_begin(root, request_path, revision)
            self.assertFalse(refused["ok"])
            self.assertTrue(
                any("cannot relabel canonical family" in error for error in refused["errors"]),
                refused,
            )

            changed_method = self.complete_attempt_request(
                self.support.attempt_request(
                    current,
                    method_family_id="METHOD-CHANGED",
                    external_run_id="changed-method",
                    action="Run the evidence-backed lower-complexity method.",
                    effect="Compare the changed boundary with a smaller causal gate.",
                )
            )
            changed_method.update(recovery_fields)
            request_path = root / "changed-method.json"
            self.support.write_json(request_path, changed_method)
            admitted = self.state.attempt_begin(root, request_path, revision)
            self.assertTrue(admitted["ok"], admitted)
            self.assertNotEqual(
                admitted["attempt"]["method_family_fingerprint"],
                prior["method_family_fingerprint"],
            )
            persisted = json.loads(
                (root / ".codex" / "ACCEPTANCE.json").read_text()
            )["execution_control"]["usage"]["method_families"][-1]
            self.assertEqual(persisted["prior_method_family_id"], prior["id"])
            self.assertTrue(
                self.state.valid_fingerprint(
                    persisted["method_change_evidence_fingerprint"]
                )
            )
            self.assertTrue(
                self.state.valid_fingerprint(
                    persisted["lower_complexity_comparison_fingerprint"]
                )
            )

    def test_new_method_family_cannot_abandon_an_active_sibling(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = self.write_active(root)
            state["execution_control"]["limits"]["failed_attempts"] = 8
            state["execution_control"]["limits"]["no_progress_attempts"] = 8
            self.support.write_state(root, self.support.project_text(), state)

            begun = self.begin(root, state, external_run_id="first-family")
            self.claim_and_observe(root, begun, produce_evidence=False)
            finished = self.finish(
                root,
                begun,
                self.support.attempt_result(
                    attempt_id=begun["attempt"]["id"],
                    outcome="failed",
                    progress=False,
                ),
            )
            self.assertTrue(finished["ok"], finished)
            current = json.loads(
                (root / ".codex" / "ACCEPTANCE.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                current["execution_control"]["usage"]["method_families"][0]["status"],
                "active",
            )

            request = self.complete_attempt_request(
                self.support.attempt_request(
                    current,
                    method_family_id="METHOD-HOP",
                    action="Rename the same unresolved approach.",
                    effect="Continue without first reaching the active family breaker.",
                    external_run_id="family-hop",
                )
            )
            request_path = root / "family-hop.json"
            self.support.write_json(request_path, request)
            refused = self.state.attempt_begin(
                root, request_path, finished["revision"]
            )

            self.assertFalse(refused["ok"])
            self.assertTrue(
                any("active method family" in error for error in refused["errors"]),
                refused,
            )

    def test_only_one_evidence_backed_replacement_family_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = self.write_active(root)
            state["execution_control"]["limits"]["no_progress_attempts"] = 12
            state["execution_control"]["limits"]["total_attempts"] = 12
            self.support.write_state(root, self.support.project_text(), state)

            revision = 0
            for index in range(2):
                current = json.loads(
                    (root / ".codex" / "ACCEPTANCE.json").read_text(encoding="utf-8")
                )
                begun = self.begin(
                    root,
                    current,
                    action_classes=["local"],
                    causal_evidence_ref=None,
                    external_run_id=f"initial-no-progress-{index}",
                )
                self.claim_and_observe(root, begun, produce_evidence=False)
                finished = self.finish(
                    root,
                    begun,
                    self.support.attempt_result(
                        attempt_id=begun["attempt"]["id"],
                        outcome="passed",
                        progress=False,
                    ),
                )
                self.assertTrue(finished["ok"], finished)
                revision = finished["revision"]

            current = json.loads(
                (root / ".codex" / "ACCEPTANCE.json").read_text(encoding="utf-8")
            )
            first_family = current["execution_control"]["usage"]["method_families"][0]
            self.assertEqual(first_family["status"], "stopped")
            evidence = root / "evidence"
            evidence.mkdir(parents=True, exist_ok=True)
            (evidence / "change-1.json").write_text('{"cause":"changed"}', encoding="utf-8")
            (evidence / "compare-1.json").write_text('{"comparison":"smaller"}', encoding="utf-8")

            recovery = {
                "prior_method_family_id": first_family["id"],
                "method_change_evidence_ref": "evidence/change-1.json",
                "lower_complexity_comparison_ref": "evidence/compare-1.json",
            }
            for index in range(2):
                current = json.loads(
                    (root / ".codex" / "ACCEPTANCE.json").read_text(encoding="utf-8")
                )
                request = self.complete_attempt_request(
                    self.support.attempt_request(
                        current,
                        method_family_id="METHOD-SECOND",
                        action="Run the single evidence-backed replacement.",
                        effect="Test the lower-complexity changed boundary.",
                        action_classes=["local"],
                        causal_evidence_ref=None,
                        external_run_id=f"replacement-no-progress-{index}",
                    )
                )
                if index == 0:
                    request.update(recovery)
                request_path = root / f"replacement-{index}.json"
                self.support.write_json(request_path, request)
                begun = self.state.attempt_begin(root, request_path, revision)
                self.assertTrue(begun["ok"], begun)
                self.attempt_inputs[begun["attempt"]["id"]] = (
                    request,
                    {"cmd": "run-generic-gate"},
                )
                self.claim_and_observe(root, begun, produce_evidence=False)
                finished = self.finish(
                    root,
                    begun,
                    self.support.attempt_result(
                        attempt_id=begun["attempt"]["id"],
                        outcome="passed",
                        progress=False,
                    ),
                )
                self.assertTrue(finished["ok"], finished)
                revision = finished["revision"]

            current = json.loads(
                (root / ".codex" / "ACCEPTANCE.json").read_text(encoding="utf-8")
            )
            second_family = current["execution_control"]["usage"]["method_families"][-1]
            self.assertEqual(second_family["status"], "stopped")
            (evidence / "change-2.json").write_text('{"cause":"changed-again"}', encoding="utf-8")
            (evidence / "compare-2.json").write_text('{"comparison":"smaller-again"}', encoding="utf-8")
            third = self.complete_attempt_request(
                self.support.attempt_request(
                    current,
                    method_family_id="METHOD-THIRD",
                    action="Try a second replacement family.",
                    effect="Continue method churn after two stopped families.",
                    action_classes=["local"],
                    causal_evidence_ref=None,
                    external_run_id="third-family",
                )
            )
            third.update(
                {
                    "prior_method_family_id": second_family["id"],
                    "method_change_evidence_ref": "evidence/change-2.json",
                    "lower_complexity_comparison_ref": "evidence/compare-2.json",
                }
            )
            request_path = root / "third-family.json"
            self.support.write_json(request_path, third)
            refused = self.state.attempt_begin(root, request_path, revision)

            self.assertFalse(refused["ok"])
            self.assertTrue(
                any("replacement-family limit" in error for error in refused["errors"]),
                refused,
            )

    def test_evidence_backed_method_family_can_continue_without_redeclaring_recovery_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = self.write_active(root)
            state["execution_control"]["limits"]["failed_attempts"] = 8
            state["execution_control"]["limits"]["no_progress_attempts"] = 8
            self.support.write_state(root, self.support.project_text(), state)

            revision = 0
            for index, boundary in enumerate(("BOUNDARY-ONE", "BOUNDARY-TWO")):
                current = json.loads((root / ".codex" / "ACCEPTANCE.json").read_text())
                begun = self.begin(
                    root,
                    current,
                    boundary_id=boundary,
                    external_run_id=f"family-stop-{index}",
                )
                finished = self.finish(
                    root,
                    begun,
                    self.support.attempt_result(
                        attempt_id=begun["attempt"]["id"],
                        outcome="failed",
                        progress=False,
                    ),
                )
                self.assertTrue(finished["ok"], finished)
                revision = finished["revision"]

            current = json.loads((root / ".codex" / "ACCEPTANCE.json").read_text())
            prior = current["execution_control"]["usage"]["method_families"][0]
            change_path = root / "evidence" / "method-change.json"
            comparison_path = root / "evidence" / "lower-complexity.json"
            change_path.parent.mkdir(parents=True, exist_ok=True)
            change_path.write_text('{"changed_boundary": true}', encoding="utf-8")
            comparison_path.write_text('{"lower_complexity": true}', encoding="utf-8")
            action = "Run the evidence-backed lower-complexity method."
            effect = "Compare the changed boundary with a smaller causal gate."
            changed = self.complete_attempt_request(
                self.support.attempt_request(
                    current,
                    method_family_id="METHOD-CHANGED",
                    external_run_id="changed-method",
                    action=action,
                    effect=effect,
                )
            )
            changed.update(
                {
                    "prior_method_family_id": prior["id"],
                    "method_change_evidence_ref": "evidence/method-change.json",
                    "lower_complexity_comparison_ref": "evidence/lower-complexity.json",
                }
            )
            changed_path = root / "changed.json"
            self.support.write_json(changed_path, changed)
            admitted = self.state.attempt_begin(root, changed_path, revision)
            self.assertTrue(admitted["ok"], admitted)
            settled = self.finish(
                root,
                admitted,
                self.support.attempt_result(
                    attempt_id=admitted["attempt"]["id"],
                    outcome="failed",
                    progress=False,
                ),
            )
            self.assertTrue(settled["ok"], settled)

            current = json.loads((root / ".codex" / "ACCEPTANCE.json").read_text())
            continuation = self.complete_attempt_request(
                self.support.attempt_request(
                    current,
                    method_family_id="METHOD-CHANGED",
                    external_run_id="changed-method-continuation",
                    action=action,
                    effect=effect,
                )
            )
            continuation_path = root / "continuation.json"
            self.support.write_json(continuation_path, continuation)
            continued = self.state.attempt_begin(root, continuation_path, settled["revision"])
            self.assertTrue(continued["ok"], continued)
            validated = self.state.validate(root, mode="admit")
            self.assertTrue(validated["ok"], validated)

    def test_state_reconcile_preserves_cumulative_usage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = self.write_active(root)
            state["execution_control"]["usage"]["total_tool_calls"] = 3
            state["execution_control"]["usage"]["active_attempt_seconds"] = 7
            self.support.write_state(root, self.support.project_text(), state)
            request_path = root / ".codex" / "ATTEMPT_REQUEST.json"
            self.support.write_json(
                request_path,
                {
                    "project_outcome_md": self.support.project_text(),
                    "acceptance": state,
                    "recovery_evidence_ref": None,
                },
            )
            reconciled = self.state.state_reconcile(root, request_path, 0)
            self.assertTrue(reconciled["ok"], reconciled)
            current = json.loads((root / ".codex" / "ACCEPTANCE.json").read_text())
            self.assertEqual(current["execution_control"]["usage"]["total_tool_calls"], 3)
            self.assertEqual(current["execution_control"]["usage"]["active_attempt_seconds"], 7)

    def test_state_reconcile_cannot_rename_away_active_method_history(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = self.write_active(root)
            begun = self.begin(
                root,
                state,
                action_classes=["local"],
                causal_evidence_ref=None,
            )
            self.claim_and_observe(root, begun, produce_evidence=False)
            finished = self.finish(
                root,
                begun,
                self.support.attempt_result(
                    attempt_id=begun["attempt"]["id"],
                    outcome="passed",
                    progress=False,
                ),
            )
            self.assertTrue(finished["ok"], finished)

            acceptance_path = root / ".codex" / "ACCEPTANCE.json"
            before = acceptance_path.read_bytes()
            current = json.loads(before)
            proposed = json.loads(json.dumps(current))
            renamed = json.loads(json.dumps(proposed["requirements"][0]))
            renamed["id"] = "REQ-RENAMED"
            proposed["requirements"].append(renamed)
            proposed["current_slice_requirement_id"] = "REQ-RENAMED"
            request_path = root / ".codex" / "ATTEMPT_REQUEST.json"
            self.support.write_json(
                request_path,
                {
                    "project_outcome_md": self.support.project_text(
                        current_id="REQ-RENAMED"
                    ),
                    "acceptance": proposed,
                    "recovery_evidence_ref": None,
                },
            )

            reconciled = self.state.state_reconcile(
                root, request_path, finished["revision"]
            )

            self.assertFalse(reconciled["ok"])
            self.assertIn(
                "cannot replace a current slice",
                " ".join(reconciled["errors"]),
            )
            self.assertEqual(acceptance_path.read_bytes(), before)

            proposed["requirements"][0]["status"] = "passing"
            proposed["requirements"][0]["blocker"] = None
            self.support.write_json(
                request_path,
                {
                    "project_outcome_md": self.support.project_text(
                        current_id="REQ-RENAMED"
                    ),
                    "acceptance": proposed,
                    "recovery_evidence_ref": None,
                },
            )
            forged_passing = self.state.state_reconcile(
                root, request_path, finished["revision"]
            )
            self.assertFalse(forged_passing["ok"])
            self.assertIn(
                "invalidate its proof",
                " ".join(forged_passing["errors"]),
            )
            self.assertEqual(acceptance_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
