from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = (
    REPOSITORY_ROOT
    / "skills"
    / "outcome-integrity"
    / "hooks"
    / "outcome_integrity_hook.py"
)
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


class FakeState:
    def __init__(self, *, pre: dict | None = None, post: dict | None = None):
        self.pre_result = pre or {
            "ok": True,
            "command": "hook-pre-claim",
            "decision": "allow",
        }
        self.post_result = post or {
            "ok": True,
            "command": "hook-post-observe",
            "decision": "observed",
        }
        self.pre_calls: list[tuple[Path, dict]] = []
        self.post_calls: list[tuple[Path, dict]] = []

    def hook_requires_claim(self, payload: dict) -> bool:
        return True

    def hook_requires_claim_for_root(
        self, root: Path, payload: dict, *, post: bool = False
    ) -> bool:
        return self.hook_requires_claim(payload)

    def hook_pre_claim(self, root: Path, payload: dict):
        self.pre_calls.append((Path(root), payload))
        return self.pre_result

    def hook_post_observe(self, root: Path, payload: dict):
        self.post_calls.append((Path(root), payload))
        return self.post_result


class ClaimState(FakeState):
    def __init__(self):
        super().__init__()
        self.claim: dict | None = None
        self.observed = False

    def hook_pre_claim(self, root: Path, payload: dict):
        self.pre_calls.append((Path(root), payload))
        if self.claim is not None:
            return {"ok": False, "decision": "deny", "errors": ["active tool claim exists"]}
        self.claim = json.loads(json.dumps(payload))
        return {"ok": True, "decision": "allow", "command": "hook-pre-claim"}

    def hook_post_observe(self, root: Path, payload: dict):
        self.post_calls.append((Path(root), payload))
        identity = {key: payload.get(key) for key in ("tool_use_id", "tool_name", "cwd", "tool_input")}
        if self.claim is None or identity != self.claim:
            return {"ok": False, "decision": "deny", "errors": ["tool claim mismatch"]}
        if self.observed:
            return {"ok": False, "decision": "deny", "errors": ["tool claim already observed"]}
        self.observed = True
        return {"ok": True, "decision": "observed", "command": "hook-post-observe"}


class OutcomeIntegrityHookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.hook = load_module(HOOK_PATH, "outcome_integrity_hook_tests")
        cls.state_module = load_module(STATE_SCRIPT, "outcome_integrity_hook_core_tests")
        cls.support = load_module(SUPPORT_SCRIPT, "outcome_integrity_hook_support_tests")
        cls.self_sha256 = hashlib.sha256(HOOK_PATH.read_bytes()).hexdigest()
        cls.core_sha256 = hashlib.sha256(STATE_SCRIPT.read_bytes()).hexdigest()

    def initialize_project(self, root: Path) -> None:
        state = root / ".codex"
        state.mkdir(parents=True, exist_ok=True)
        (state / "PROJECT_OUTCOME.md").write_text("# Project Outcome\n", encoding="utf-8")
        (state / "ACCEPTANCE.json").write_text("{}\n", encoding="utf-8")

    def payload(
        self,
        root: Path,
        *,
        event: str = "PreToolUse",
        tool_use_id: str = "tool-1",
        tool_name: str = "apply_patch",
        tool_input=None,
        **extra,
    ) -> dict:
        value = {
            "hook_event_name": event,
            "cwd": str(root),
            "tool_use_id": tool_use_id,
            "tool_name": tool_name,
            "tool_input": {"command": "*** Begin Patch\n*** End Patch"}
            if tool_input is None
            else tool_input,
        }
        value.update(extra)
        return value

    def run_hook(
        self,
        payload: dict,
        state: FakeState,
        *,
        owner: str | None = None,
        digest: str | None = None,
        core_digest: str | None = None,
    ) -> tuple[int, str]:
        arguments = [
            "--owner",
            owner or self.hook.OWNER,
            "--self-sha256",
            digest or self.self_sha256,
            "--core-sha256",
            core_digest or self.core_sha256,
        ]
        stdin = io.StringIO(json.dumps(payload))
        stdout = io.StringIO()
        with patch.object(self.hook, "_load_state_module", return_value=state):
            status = self.hook.main(arguments, stdin=stdin, stdout=stdout)
        return status, stdout.getvalue()

    def begin_real_attempt(
        self,
        root: Path,
        *,
        tool_name: str,
        tool_input: object,
        action_classes: list[str] | None = None,
        allowed_paths: list[str] | None = None,
    ) -> dict:
        acceptance = self.support.acceptance_data()
        limits = acceptance["execution_control"]["limits"]
        # Keep this integration fixture compatible while the shared v6 fixture
        # and core evolve together; these are production limits, not bypasses.
        limits.setdefault("max_path_touches", 12)
        limits.setdefault("max_touches_per_path", 3)
        self.support.write_state(root, self.support.project_text(), acceptance)
        request = self.support.attempt_request(
            acceptance,
            tool_name=tool_name,
            tool_input=tool_input,
            action_classes=action_classes,
            allowed_paths=allowed_paths,
        )
        request_path = root / ".codex" / "ATTEMPT_REQUEST.json"
        self.support.write_json(request_path, request)
        begun = self.state_module.attempt_begin(
            root,
            request_path,
            acceptance["execution_control"]["revision"],
        )
        self.assertTrue(begun["ok"], begun)
        return begun

    def test_uninitialized_directories_are_silent_and_unaffected(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            root = Path(temporary)
            (root / ".codex").mkdir()
            (root / ".codex" / "PROJECT_OUTCOME.md").write_text("partial\n", encoding="utf-8")
            state = FakeState(pre={"ok": False, "decision": "deny", "errors": ["must not run"]})
            # The repository that owns this test is itself initialized, so isolate
            # the host boundary explicitly; nearest-root ascent is exercised below.
            with patch.object(self.hook, "find_project_root", return_value=None):
                status, output = self.run_hook(
                    self.payload(root), state, owner="wrong-owner", digest="0" * 64
                )
            self.assertEqual(status, 0)
            self.assertEqual(output, "")
            self.assertEqual(state.pre_calls, [])

    def test_nearest_initialized_root_wins(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            outer = Path(temporary) / "outer"
            inner = outer / "nested" / "project"
            cwd = inner / "src" / "deep"
            cwd.mkdir(parents=True)
            self.initialize_project(outer)
            self.initialize_project(inner)
            state = FakeState()
            status, output = self.run_hook(self.payload(cwd), state)
            self.assertEqual(status, 0)
            self.assertEqual(output, "")
            self.assertEqual(state.pre_calls[0][0], inner.resolve())

    def test_parent_cwd_uses_initialized_child_from_workdir_or_patch_target(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            parent = Path(temporary) / "parent"
            child = parent / "child"
            child_source = child / "src"
            child_source.mkdir(parents=True)
            self.initialize_project(parent)
            self.initialize_project(child)

            workdir_state = FakeState()
            workdir_payload = self.payload(
                parent,
                tool_name="exec_command",
                tool_input={
                    "cmd": "run-child-check",
                    "workdir": str(child_source),
                },
            )
            status, output = self.run_hook(workdir_payload, workdir_state)
            self.assertEqual(status, 0)
            self.assertEqual(output, "")
            self.assertEqual(workdir_state.pre_calls[0][0], child.resolve())
            self.assertEqual(
                Path(workdir_state.pre_calls[0][1]["cwd"]), child_source.resolve()
            )

            patch_state = FakeState(
                pre={
                    "ok": False,
                    "decision": "deny",
                    "errors": ["child target requires child-root admission"],
                }
            )
            patch_payload = self.payload(
                parent,
                tool_use_id="child-patch",
                tool_input={
                    "patch": (
                        "*** Begin Patch\n"
                        "*** Add File: child/src/target.py\n"
                        "+bounded = True\n"
                        "*** End Patch"
                    )
                },
            )
            status, output = self.run_hook(patch_payload, patch_state)
            self.assertEqual(status, 0)
            self.assertEqual(
                json.loads(output)["hookSpecificOutput"]["permissionDecision"],
                "deny",
            )
            self.assertEqual(patch_state.pre_calls[0][0], child.resolve())

    def test_parent_cwd_does_not_auto_select_unique_immediate_child(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            child = parent / "only-project"
            acceptance = self.support.acceptance_data()
            self.support.write_state(child, self.support.project_text(), acceptance)
            acceptance_path = child / ".codex" / "ACCEPTANCE.json"
            before = acceptance_path.read_bytes()
            state = FakeState(
                pre={"ok": False, "decision": "deny", "errors": ["must not run"]}
            )
            payload = self.payload(
                parent,
                tool_name="Bash",
                tool_input={"command": "python -c \"print('bounded check')\""},
            )
            status, output = self.run_hook(payload, state)
            self.assertEqual(status, 0)
            self.assertEqual(output, "")
            self.assertEqual(state.pre_calls, [])
            self.assertEqual(acceptance_path.read_bytes(), before)

    def test_explicit_uninitialized_sibling_and_unactivated_initialized_target_stay_direct(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            initialized = parent / "initialized-project"
            initialized_source = initialized / "src"
            direct = parent / "direct-delivery"
            initialized_source.mkdir(parents=True)
            direct.mkdir()
            acceptance = self.support.acceptance_data()
            self.support.write_state(
                initialized, self.support.project_text(), acceptance
            )
            acceptance_path = initialized / ".codex" / "ACCEPTANCE.json"
            before = acceptance_path.read_bytes()
            registry = parent / "registry"
            session_id = "session-explicit-state-free-sibling"
            state = FakeState(
                pre={"ok": False, "decision": "deny", "errors": ["must not run"]}
            )

            direct_payload = self.payload(
                parent,
                tool_use_id="direct-uninitialized-sibling",
                tool_name="exec_command",
                tool_input={
                    "cmd": "run bounded direct delivery",
                    "workdir": str(direct),
                },
                session_id=session_id,
            )
            with patch.object(self.hook, "REGISTRY_DIRECTORY", registry):
                status, output = self.run_hook(direct_payload, state)
                self.assertEqual(status, 0)
                self.assertEqual(output, "")
                self.assertEqual(state.pre_calls, [])
                self.assertFalse(registry.exists())

                initialized_payload = self.payload(
                    parent,
                    tool_use_id="explicit-initialized-target",
                    tool_name="exec_command",
                    tool_input={
                        "cmd": "inspect initialized target",
                        "workdir": str(initialized_source),
                    },
                    session_id=session_id,
                )
                initialized_output = self.run_hook(
                    initialized_payload, self.state_module
                )[1]
                self.assertEqual(initialized_output, "")
                self.assertFalse(registry.exists())
            self.assertEqual(acceptance_path.read_bytes(), before)

    def test_exact_activation_binds_deep_root_for_later_canonical_bash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = parent / "workspace" / "nested" / "deep-project"
            registry = parent / "registry"
            acceptance = self.support.acceptance_data()
            self.support.write_state(root, self.support.project_text(), acceptance)
            acceptance_path = root / ".codex" / "ACCEPTANCE.json"
            before = acceptance_path.read_bytes()
            session_id = "session-deep-activation"
            activation = self.payload(
                parent,
                tool_use_id="activate-deep-root",
                tool_name="Bash",
                tool_input={
                    "command": (
                        f'"{sys.executable}" "{self.hook.STATE_SCRIPT}" resume '
                        f'--root "{root}"'
                    )
                },
                session_id=session_id,
            )
            with patch.object(self.hook, "REGISTRY_DIRECTORY", registry):
                status, output = self.run_hook(activation, self.state_module)
                self.assertEqual(status, 0)
                self.assertEqual(output, "")
                registry_files = list(registry.glob("*.json"))
                self.assertEqual(len(registry_files), 1)
                self.assertNotIn(
                    session_id,
                    registry_files[0].read_text(encoding="utf-8"),
                )

                later = self.payload(
                    parent,
                    tool_use_id="later-canonical-bash",
                    tool_name="Bash",
                    tool_input={"command": "python -c \"print('later')\""},
                    session_id=session_id,
                )
                status, output = self.run_hook(later, self.state_module)
                self.assertEqual(status, 0)
                self.assertEqual(output, "")
            self.assertEqual(acceptance_path.read_bytes(), before)

    def test_parent_cwd_does_not_auto_select_or_bind_unique_deep_project(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = parent / "area-a" / "nested" / "only-project"
            self.initialize_project(root)
            registry = parent / "registry"
            state = FakeState(
                pre={"ok": False, "decision": "deny", "errors": ["must not run"]}
            )
            payload = self.payload(
                parent,
                tool_name="Bash",
                tool_input={"command": "python -c \"print('state free')\""},
                session_id="session-deep-state-free",
            )
            with patch.object(self.hook, "REGISTRY_DIRECTORY", registry):
                status, output = self.run_hook(payload, state)
            self.assertEqual(status, 0)
            self.assertEqual(output, "")
            self.assertEqual(state.pre_calls, [])
            self.assertFalse(registry.exists())

    def test_session_cross_root_activation_conflict_cannot_switch_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            first = parent / "one" / "deep" / "project"
            second = parent / "two" / "deep" / "project"
            self.initialize_project(first)
            self.initialize_project(second)
            registry = parent / "registry"
            session_id = "session-cross-root"

            def activation(root: Path, tool_use_id: str) -> dict:
                return self.payload(
                    parent,
                    tool_use_id=tool_use_id,
                    tool_name="Bash",
                    tool_input={
                        "command": (
                            f'"{sys.executable}" "{self.hook.STATE_SCRIPT}" resume '
                            f'--root "{root}"'
                        )
                    },
                    session_id=session_id,
                )

            with patch.object(self.hook, "REGISTRY_DIRECTORY", registry):
                self.assertEqual(
                    self.run_hook(
                        activation(first, "activate-first"), self.state_module
                    )[1],
                    "",
                )
                conflict_output = self.run_hook(
                    activation(second, "activate-second"), self.state_module
                )[1]
                self.assertEqual(
                    json.loads(conflict_output)["hookSpecificOutput"][
                        "permissionDecision"
                    ],
                    "deny",
                )
                self.assertIn("conflicts with its bound project root", conflict_output)
                entry = json.loads(next(registry.glob("*.json")).read_text(encoding="utf-8"))
                self.assertEqual(Path(entry["root"]), first.resolve())

                forged_text = self.payload(
                    parent,
                    tool_use_id="forged-command-text",
                    tool_name="Bash",
                    tool_input={
                        "command": (
                            "echo not-an-activation "
                            f'"{sys.executable}" "{self.hook.STATE_SCRIPT}" resume '
                            f'--root "{second}"'
                        )
                    },
                    session_id=session_id,
                )
                forged_output = self.run_hook(forged_text, self.state_module)[1]
                self.assertEqual(forged_output, "")
                entry = json.loads(next(registry.glob("*.json")).read_text(encoding="utf-8"))
                self.assertEqual(Path(entry["root"]), first.resolve())

    def test_stale_session_binding_does_not_block_local_reversible_work(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = parent / "nested" / "project"
            self.initialize_project(root)
            registry = parent / "registry"
            session_id = "session-stale-root"
            activation = self.payload(
                parent,
                tool_name="Bash",
                tool_input={
                    "command": (
                        f'"{sys.executable}" "{self.hook.STATE_SCRIPT}" resume '
                        f'--root "{root}"'
                    )
                },
                session_id=session_id,
            )
            with patch.object(self.hook, "REGISTRY_DIRECTORY", registry):
                self.assertEqual(self.run_hook(activation, self.state_module)[1], "")
                (root / ".codex" / "ACCEPTANCE.json").unlink()
                later = self.payload(
                    parent,
                    tool_use_id="stale-later",
                    tool_name="Bash",
                    tool_input={"command": "python -c \"print('later')\""},
                    session_id=session_id,
                )
                output = self.run_hook(later, self.state_module)[1]
            self.assertEqual(output, "")

    def test_parent_cwd_does_not_auto_select_multiple_immediate_projects(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            self.initialize_project(parent / "first")
            self.initialize_project(parent / "second")
            registry = parent / "registry"
            state = FakeState(
                pre={"ok": False, "decision": "deny", "errors": ["must not run"]}
            )
            payload = self.payload(
                parent,
                tool_name="Bash",
                tool_input={"command": "python -c \"print('which project?')\""},
                session_id="session-multiple-children-state-free",
            )
            with patch.object(self.hook, "REGISTRY_DIRECTORY", registry):
                status, output = self.run_hook(payload, state)
            self.assertEqual(status, 0)
            self.assertEqual(output, "")
            self.assertEqual(state.pre_calls, [])
            self.assertFalse(registry.exists())

    def test_parent_cwd_bash_with_no_initialized_child_stays_silent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            registry = parent / "registry"
            state = FakeState(
                pre={"ok": False, "decision": "deny", "errors": ["must not run"]}
            )
            payload = self.payload(
                parent,
                tool_name="Bash",
                tool_input={"command": "python -c \"print('unrelated')\""},
                session_id="session-no-project",
            )
            with patch.object(self.hook, "REGISTRY_DIRECTORY", registry):
                status, output = self.run_hook(payload, state)
            self.assertEqual(status, 0)
            self.assertEqual(output, "")
            self.assertEqual(state.pre_calls, [])

    def test_targets_in_multiple_initialized_children_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            parent = Path(temporary)
            first = parent / "first"
            second = parent / "second"
            self.initialize_project(first)
            self.initialize_project(second)
            state = FakeState()
            payload = self.payload(
                parent,
                tool_name="exec_command",
                tool_input={
                    "source": {"path": str(first / "input.txt")},
                    "destination": {"path": str(second / "output.txt")},
                },
            )
            status, output = self.run_hook(payload, state)
            self.assertEqual(status, 0)
            result = json.loads(output)
            self.assertEqual(
                result["hookSpecificOutput"]["permissionDecision"], "deny"
            )
            self.assertIn("multiple initialized project roots", output)
            self.assertEqual(state.pre_calls, [])

    def test_pre_denial_emits_only_the_official_shape(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            root = Path(temporary)
            self.initialize_project(root)
            state = FakeState(
                pre={
                    "ok": False,
                    "command": "hook-pre-claim",
                    "decision": "deny",
                    "errors": ["method scope expansion is not admitted"],
                }
            )
            status, output = self.run_hook(self.payload(root), state)
            expected = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "method scope expansion is not admitted",
                }
            }
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output), expected)
            self.assertEqual(output, json.dumps(expected, separators=(",", ":")) + "\n")

    def test_allowed_pre_call_has_no_output(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            root = Path(temporary)
            self.initialize_project(root)
            state = FakeState()
            status, output = self.run_hook(self.payload(root), state)
            self.assertEqual(status, 0)
            self.assertEqual(output, "")
            self.assertEqual(len(state.pre_calls), 1)

    def test_self_hash_or_owner_mismatch_fails_closed_inside_project(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            root = Path(temporary)
            self.initialize_project(root)
            state = FakeState()
            for owner, digest in ((self.hook.OWNER, "0" * 64), ("other-owner", self.self_sha256)):
                with self.subTest(owner=owner, digest=digest):
                    status, output = self.run_hook(
                        self.payload(root), state, owner=owner, digest=digest
                    )
                    self.assertEqual(status, 0)
                    result = json.loads(output)
                    self.assertEqual(
                        result["hookSpecificOutput"]["permissionDecision"], "deny"
                    )
                    self.assertIn(
                        "integrity verification failed",
                        result["hookSpecificOutput"]["permissionDecisionReason"],
                    )
            self.assertEqual(state.pre_calls, [])

    def test_mutated_core_hash_fails_closed_before_import(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            root = Path(temporary)
            self.initialize_project(root)
            mutated_core = root / "mutated_project_outcome.py"
            mutated_core.write_bytes(STATE_SCRIPT.read_bytes() + b"\n# mutation\n")
            state = FakeState()
            with patch.object(self.hook, "STATE_SCRIPT", mutated_core):
                status, output = self.run_hook(self.payload(root), state)
            self.assertEqual(status, 0)
            result = json.loads(output)
            self.assertEqual(
                result["hookSpecificOutput"]["permissionDecision"], "deny"
            )
            self.assertIn(
                "integrity verification failed",
                result["hookSpecificOutput"]["permissionDecisionReason"],
            )
            self.assertEqual(state.pre_calls, [])

    def test_post_payload_drops_tool_response_and_never_leaks_it(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            root = Path(temporary)
            self.initialize_project(root)
            secret = "SECRET-TOOL-RESPONSE-MUST-NOT-LEAK"
            state = FakeState(
                post={"ok": False, "decision": "deny", "errors": ["tool claim mismatch"]}
            )
            payload = self.payload(
                root,
                event="PostToolUse",
                tool_response={"status": "completed", "content": secret},
            )
            status, output = self.run_hook(payload, state)
            self.assertEqual(status, 0)
            self.assertNotIn(secret, output)
            observed = state.post_calls[0][1]
            self.assertNotIn("tool_response", observed)
            self.assertNotIn(secret, json.dumps(observed))

    def test_post_mismatch_emits_official_block_and_context(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            root = Path(temporary)
            self.initialize_project(root)
            state = FakeState(
                post={"ok": False, "decision": "deny", "errors": ["tool claim mismatch"]}
            )
            status, output = self.run_hook(
                self.payload(root, event="PostToolUse", tool_response={"status": "completed"}),
                state,
            )
            result = json.loads(output)
            self.assertEqual(status, 0)
            self.assertEqual(result["decision"], "block")
            self.assertEqual(result["reason"], "tool claim mismatch")
            self.assertEqual(
                result["hookSpecificOutput"],
                {
                    "hookEventName": "PostToolUse",
                    "additionalContext": "tool claim mismatch",
                },
            )

    def test_internal_errors_fail_closed_without_exception_details(self) -> None:
        class BrokenState(FakeState):
            def hook_pre_claim(self, root: Path, payload: dict):
                raise RuntimeError("secret input or traceback detail")

        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            root = Path(temporary)
            self.initialize_project(root)
            status, output = self.run_hook(self.payload(root), BrokenState())
            self.assertEqual(status, 0)
            self.assertNotIn("secret input", output)
            result = json.loads(output)
            self.assertEqual(
                result["hookSpecificOutput"]["permissionDecision"], "deny"
            )
            self.assertIn(
                "failed closed",
                result["hookSpecificOutput"]["permissionDecisionReason"],
            )

    def test_windows_paths_with_spaces_and_exact_control_plane_exemption(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            root = Path(temporary) / "Project With Spaces"
            cwd = root / "Source With Spaces"
            cwd.mkdir(parents=True)
            self.initialize_project(root)
            state = FakeState(
                pre={"ok": False, "decision": "deny", "errors": ["ordinary call denied"]}
            )
            commands = (
                "validate",
                "path",
                "control-status",
                "candidate-bind --expected-revision 0",
                "state-reconcile --request .codex/ATTEMPT_REQUEST.json --expected-revision 0",
            )
            for index, core_command in enumerate(commands):
                command = (
                    f'"{sys.executable}" "{self.hook.STATE_SCRIPT}" {core_command} '
                    f'--root "{root}"'
                )
                payload = self.payload(
                    cwd,
                    tool_use_id=f"control-{index}",
                    tool_name="Bash",
                    tool_input={"command": command},
                )
                status, output = self.run_hook(payload, state)
                self.assertEqual(status, 0)
                self.assertEqual(output, "")
            self.assertEqual(state.pre_calls, [])

            payload["tool_use_id"] = "malicious-control"
            payload["tool_input"] = {"command": command + "; Write-Host bypass"}
            status, output = self.run_hook(payload, state)
            self.assertEqual(status, 0)
            self.assertEqual(
                json.loads(output)["hookSpecificOutput"]["permissionDecision"],
                "deny",
            )
            self.assertEqual(len(state.pre_calls), 1)

            payload["tool_use_id"] = "obsolete-command-name"
            payload["tool_input"] = {
                "command": (
                    f'"{sys.executable}" "{self.hook.STATE_SCRIPT}" status '
                    f'--root "{root}"'
                )
            }
            status, output = self.run_hook(payload, state)
            self.assertEqual(status, 0)
            self.assertEqual(
                json.loads(output)["hookSpecificOutput"]["permissionDecision"],
                "deny",
            )

            payload["tool_use_id"] = "untrusted-interpreter"
            payload["tool_input"] = {
                "command": (
                    f'"{root / "python.exe"}" "{self.hook.STATE_SCRIPT}" validate '
                    f'--root "{root}"'
                )
            }
            status, output = self.run_hook(payload, state)
            self.assertEqual(status, 0)
            self.assertEqual(
                json.loads(output)["hookSpecificOutput"]["permissionDecision"],
                "deny",
            )

    def test_bootstrap_control_input_patch_is_silent_and_uncharged(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            root = Path(temporary)
            self.initialize_project(root)
            state = FakeState(
                pre={"ok": False, "decision": "deny", "errors": ["must not run"]},
                post={"ok": False, "decision": "deny", "errors": ["must not run"]},
            )
            tool_input = {
                "patch": (
                    "*** Begin Patch\n"
                    "*** Add File: .codex/ATTEMPT_REQUEST.json\n"
                    "+{}\n"
                    "*** Add File: .codex/ATTEMPT_RESULT.json\n"
                    "+{}\n"
                    "*** End Patch"
                )
            }
            pre = self.payload(root, tool_input=tool_input)
            status, output = self.run_hook(pre, state)
            self.assertEqual(status, 0)
            self.assertEqual(output, "")

            post = self.payload(
                root,
                event="PostToolUse",
                tool_input=tool_input,
                tool_response={"content": "host response must not be stored"},
            )
            status, output = self.run_hook(post, state)
            self.assertEqual(status, 0)
            self.assertEqual(output, "")
            self.assertEqual(state.pre_calls, [])
            self.assertEqual(state.post_calls, [])

    def test_bootstrap_patch_rejects_mixed_arbitrary_and_traversal_targets(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            root = Path(temporary)
            nested = root / "src"
            nested.mkdir(parents=True)
            self.initialize_project(root)
            state = FakeState(
                pre={
                    "ok": False,
                    "decision": "deny",
                    "errors": ["no active atomic attempt"],
                }
            )
            cases = (
                (
                    root,
                    "*** Add File: .codex/ATTEMPT_REQUEST.json\n+{}\n"
                    "*** Update File: .codex/ACCEPTANCE.json\n+forbidden\n",
                ),
                (root, "*** Add File: .codex/OTHER.json\n+{}\n"),
                (root, "*** Update File: .codex/ATTEMPT_REQUEST.json\n*** Move to: .codex/PROJECT_OUTCOME.md\n"),
                (nested, "*** Add File: ../.codex/ATTEMPT_REQUEST.json\n+{}\n"),
            )
            for index, (cwd, body) in enumerate(cases):
                with self.subTest(index=index):
                    payload = self.payload(
                        cwd,
                        tool_use_id=f"bootstrap-denied-{index}",
                        tool_input={
                            "patch": "*** Begin Patch\n" + body + "*** End Patch"
                        },
                    )
                    status, output = self.run_hook(payload, state)
                    self.assertEqual(status, 0)
                    self.assertEqual(
                        json.loads(output)["hookSpecificOutput"]["permissionDecision"],
                        "deny",
                    )
            # Arbitrary and traversal paths reach ordinary admission. Direct
            # ACCEPTANCE/PROJECT_OUTCOME targets are stopped before core state.
            self.assertEqual(len(state.pre_calls), 2)

    def test_authoritative_state_targets_are_hard_denied_before_core(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            root = Path(temporary)
            self.initialize_project(root)
            state = FakeState()
            cases = (
                self.payload(
                    root,
                    tool_use_id="structured-state-path",
                    tool_name="write_file",
                    tool_input={"path": str(root / ".codex" / "ACCEPTANCE.json")},
                ),
                self.payload(
                    root,
                    tool_use_id="patch-project-outcome",
                    tool_input={
                        "patch": (
                            "*** Begin Patch\n"
                            "*** Update File: .codex/PROJECT_OUTCOME.md\n"
                            "+forbidden\n"
                            "*** End Patch"
                        )
                    },
                ),
                self.payload(
                    root,
                    tool_use_id="shell-state-path",
                    tool_name="Bash",
                    tool_input={
                        "command": "Set-Content .codex/ACCEPTANCE.json forbidden"
                    },
                ),
            )
            for payload in cases:
                with self.subTest(tool_use_id=payload["tool_use_id"]):
                    status, output = self.run_hook(payload, state)
                    self.assertEqual(status, 0)
                    result = json.loads(output)
                    self.assertEqual(
                        result["hookSpecificOutput"]["permissionDecision"], "deny"
                    )
                    self.assertIn("authoritative state", output)
            self.assertEqual(state.pre_calls, [])

            post = dict(cases[0])
            post["hook_event_name"] = "PostToolUse"
            status, output = self.run_hook(post, state)
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output)["decision"], "block")
            self.assertEqual(state.post_calls, [])

    def test_changed_input_and_single_use_post_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            root = Path(temporary)
            self.initialize_project(root)
            state = ClaimState()
            pre = self.payload(root, tool_input={"command": "write bounded file"})
            self.assertEqual(self.run_hook(pre, state)[1], "")

            changed = self.payload(
                root,
                event="PostToolUse",
                tool_input={"command": "replace complete script"},
                tool_response={"status": "completed"},
            )
            self.assertEqual(json.loads(self.run_hook(changed, state)[1])["decision"], "block")

            matched = self.payload(
                root,
                event="PostToolUse",
                tool_input={"command": "write bounded file"},
                tool_response={"status": "completed"},
            )
            self.assertEqual(self.run_hook(matched, state)[1], "")
            repeated_output = self.run_hook(matched, state)[1]
            self.assertEqual(json.loads(repeated_output)["decision"], "block")
            self.assertIn("already observed", repeated_output)

    def test_real_core_binds_exact_tool_input_and_consumes_post_once(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            root = Path(temporary)
            tool_input = {"cmd": "run bounded production-shaped check"}
            self.begin_real_attempt(
                root,
                tool_name="exec_command",
                tool_input=tool_input,
                action_classes=["local", "proof"],
            )

            changed_tool = self.payload(
                root,
                tool_use_id="changed-tool",
                tool_name="Bash",
                tool_input=tool_input,
            )
            changed_tool_output = self.run_hook(
                changed_tool, self.state_module
            )[1]
            self.assertEqual(changed_tool_output, "")

            changed_external = self.payload(
                root,
                tool_use_id="changed-external-tool",
                tool_name="mcp__mail__send_message",
                tool_input={"target": "recipient", "body": "must remain protected"},
            )
            changed_external_output = self.run_hook(
                changed_external, self.state_module
            )[1]
            self.assertEqual(
                json.loads(changed_external_output)["hookSpecificOutput"][
                    "permissionDecision"
                ],
                "deny",
            )
            self.assertIn("tool_name", changed_external_output)

            changed_input = self.payload(
                root,
                tool_use_id="changed-input",
                tool_name="exec_command",
                tool_input={"cmd": "replace the whole script instead"},
            )
            changed_input_output = self.run_hook(
                changed_input, self.state_module
            )[1]
            self.assertEqual(changed_input_output, "")

            changed_protected_input = self.payload(
                root,
                tool_use_id="changed-protected-input",
                tool_name="exec_command",
                tool_input={"cmd": "git push origin main"},
            )
            protected_output = self.run_hook(
                changed_protected_input, self.state_module
            )[1]
            self.assertEqual(
                json.loads(protected_output)["hookSpecificOutput"][
                    "permissionDecision"
                ],
                "deny",
            )
            self.assertIn("tool_input", protected_output)

            exact = self.payload(
                root,
                tool_use_id="exact-tool-use",
                tool_name="exec_command",
                tool_input=tool_input,
            )
            self.assertEqual(self.run_hook(exact, self.state_module)[1], "")

            second_pre = self.payload(
                root,
                tool_use_id="second-pre",
                tool_name="exec_command",
                tool_input=tool_input,
            )
            self.assertIn(
                "already been claimed",
                self.run_hook(second_pre, self.state_module)[1],
            )

            before_changed_post = (root / ".codex" / "ACCEPTANCE.json").read_bytes()
            for changed_fields in (
                {"tool_input": {"cmd": "rg --files"}},
                {"tool_name": "Bash"},
            ):
                changed_post = self.payload(
                    root,
                    event="PostToolUse",
                    tool_use_id="exact-tool-use",
                    tool_name="exec_command",
                    tool_input=tool_input,
                    tool_response={"status": "completed"},
                )
                changed_post.update(changed_fields)
                changed_output = self.run_hook(changed_post, self.state_module)[1]
                self.assertEqual(json.loads(changed_output)["decision"], "block")
                self.assertIn("does not match the claimed call", changed_output)
                self.assertEqual(
                    (root / ".codex" / "ACCEPTANCE.json").read_bytes(),
                    before_changed_post,
                )

            secret = "SECRET-HOST-TOOL-RESPONSE"
            post = self.payload(
                root,
                event="PostToolUse",
                tool_use_id="exact-tool-use",
                tool_name="exec_command",
                tool_input=tool_input,
                tool_response={"status": "completed", "content": secret},
            )
            self.assertEqual(self.run_hook(post, self.state_module)[1], "")
            repeated = self.run_hook(post, self.state_module)[1]
            self.assertEqual(json.loads(repeated)["decision"], "block")

            stored_text = (root / ".codex" / "ACCEPTANCE.json").read_text(
                encoding="utf-8"
            )
            stored = json.loads(stored_text)
            control = stored["execution_control"]
            self.assertNotIn(secret, stored_text)
            self.assertNotIn("tool_response", stored_text)
            self.assertNotIn(tool_input["cmd"], stored_text)
            self.assertEqual(control["usage"]["total_tool_calls"], 1)
            self.assertEqual(control["usage"]["support_tool_calls"], 0)
            self.assertEqual(
                control["active_attempt"]["tool_claim"]["status"], "observed"
            )

    def test_pending_same_name_reservation_leaves_unrelated_local_calls_state_free(self) -> None:
        for activated in (False, True):
            with self.subTest(activated=activated), tempfile.TemporaryDirectory(
                dir=REPOSITORY_ROOT
            ) as temporary:
                root = Path(temporary)
                nested = root / "src"
                nested.mkdir()
                tool_input = {"cmd": "run bounded production-shaped check"}
                self.begin_real_attempt(
                    root,
                    tool_name="exec_command",
                    tool_input=tool_input,
                    action_classes=["local", "proof"],
                )
                registry = root / "registry"
                session_id = "same-name-local-calls"

                def state_bytes() -> dict[str, bytes]:
                    return {
                        str(path.relative_to(root)): path.read_bytes()
                        for directory in (root / ".codex", registry)
                        for path in directory.rglob("*")
                        if path.is_file()
                    }

                exact = self.payload(
                    root,
                    tool_use_id="reserved-call",
                    tool_name="exec_command",
                    tool_input=tool_input,
                    session_id=session_id,
                )
                with patch.object(self.hook, "REGISTRY_DIRECTORY", registry):
                    if activated:
                        activation = self.payload(
                            root,
                            tool_use_id="activate-same-name-session",
                            tool_name="exec_command",
                            tool_input={
                                "cmd": (
                                    f'"{sys.executable}" "{self.hook.STATE_SCRIPT}" '
                                    f'resume --root "{root}"'
                                )
                            },
                            session_id=session_id,
                        )
                        self.assertEqual(self.run_hook(activation, self.state_module)[1], "")
                        self.assertEqual(len(list(registry.glob("*.json"))), 1)

                    for phase in ("unclaimed", "claimed", "observed"):
                        with self.subTest(phase=phase):
                            before = state_bytes()
                            for index, (cwd, local_input) in enumerate(
                                (
                                    (root, {"cmd": "rg --files"}),
                                    (root, {"cmd": "python -m unittest discover -s tests"}),
                                    (root, {"cmd": "Set-Content local.txt repaired"}),
                                    (nested, tool_input),
                                )
                            ):
                                local = self.payload(
                                    cwd,
                                    tool_use_id=f"unrelated-{phase}-{index}",
                                    tool_name="exec_command",
                                    tool_input=local_input,
                                    session_id=session_id,
                                )
                                self.assertEqual(self.run_hook(local, self.state_module)[1], "")
                                local["hook_event_name"] = "PostToolUse"
                                local["tool_response"] = {"status": "completed"}
                                self.assertEqual(self.run_hook(local, self.state_module)[1], "")
                                self.assertEqual(state_bytes(), before)
                            ledger_write = self.payload(
                                root,
                                tool_use_id=f"ledger-write-{phase}",
                                tool_name="exec_command",
                                tool_input={"cmd": "Set-Content .codex/ACCEPTANCE.json forbidden"},
                                session_id=session_id,
                            )
                            denied = self.run_hook(ledger_write, self.state_module)[1]
                            self.assertEqual(
                                json.loads(denied)["hookSpecificOutput"]["permissionDecision"],
                                "deny",
                            )
                            self.assertIn("authoritative state", denied)
                            self.assertEqual(state_bytes(), before)
                            if phase == "unclaimed":
                                self.assertEqual(self.run_hook(exact, self.state_module)[1], "")
                            elif phase == "claimed":
                                exact["hook_event_name"] = "PostToolUse"
                                exact["tool_response"] = {"status": "completed"}
                                self.assertEqual(self.run_hook(exact, self.state_module)[1], "")

                    if not activated:
                        self.assertFalse(registry.exists())
                stored = json.loads((root / ".codex" / "ACCEPTANCE.json").read_bytes())
                self.assertEqual(stored["execution_control"]["usage"]["total_tool_calls"], 1)
                self.assertEqual(
                    stored["execution_control"]["active_attempt"]["tool_claim"]["status"],
                    "observed",
                )

    def test_real_core_read_only_pre_and_post_leave_ledger_bytes_unchanged(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            root = Path(temporary)
            acceptance = self.support.acceptance_data()
            self.support.write_state(root, self.support.project_text(), acceptance)
            acceptance_path = root / ".codex" / "ACCEPTANCE.json"
            before = acceptance_path.read_bytes()
            revision = json.loads(before)["execution_control"]["revision"]

            read_only = self.payload(
                root,
                tool_use_id="read-only-view",
                tool_name="view_image",
                tool_input={"path": str(root / "preview.png")},
            )
            self.assertEqual(self.run_hook(read_only, self.state_module)[1], "")
            read_only["hook_event_name"] = "PostToolUse"
            read_only["tool_response"] = {
                "content": "read-only response must not enter state"
            }
            self.assertEqual(self.run_hook(read_only, self.state_module)[1], "")
            self.assertEqual(acceptance_path.read_bytes(), before)
            self.assertEqual(
                json.loads(acceptance_path.read_bytes())["execution_control"]["revision"],
                revision,
            )

    def test_initialized_unactivated_local_sequence_bypasses_byte_stably(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            root = Path(temporary)
            acceptance = self.support.acceptance_data()
            self.support.write_state(root, self.support.project_text(), acceptance)
            acceptance_path = root / ".codex" / "ACCEPTANCE.json"
            before = acceptance_path.read_bytes()
            registry = root / "registry"

            calls = (
                (
                    "local-inspection",
                    "exec_command",
                    {"cmd": "rg --files", "workdir": str(root)},
                ),
                (
                    "local-patch",
                    "apply_patch",
                    {
                        "patch": (
                            "*** Begin Patch\n"
                            "*** Add File: local.txt\n"
                            "+direct delivery\n"
                            "*** End Patch"
                        )
                    },
                ),
                (
                    "local-python-test",
                    "exec_command",
                    {"cmd": "python -m unittest tests.test_hooks", "workdir": str(root)},
                ),
                (
                    "local-node-provider-regression",
                    "exec_command",
                    {"cmd": "node tests/provider-regression.js", "workdir": str(root)},
                ),
                (
                    "generic-generate-support-tool",
                    "mcp__diagram__generate",
                    {"description": "local diagram fixture"},
                ),
                (
                    "provider-diagnostics-support-tool",
                    "mcp__provider__diagnostics",
                    {"scope": "local configuration"},
                ),
            )
            with patch.object(self.hook, "REGISTRY_DIRECTORY", registry):
                for tool_use_id, tool_name, tool_input in calls:
                    payload = self.payload(
                        root,
                        tool_use_id=tool_use_id,
                        tool_name=tool_name,
                        tool_input=tool_input,
                        session_id="state-free-local-sequence",
                    )
                    self.assertEqual(self.run_hook(payload, self.state_module)[1], "")
                    payload["hook_event_name"] = "PostToolUse"
                    payload["tool_response"] = {"status": "completed"}
                    self.assertEqual(self.run_hook(payload, self.state_module)[1], "")

            self.assertEqual(acceptance_path.read_bytes(), before)
            self.assertFalse(registry.exists())

    def test_provider_shell_execution_requires_an_active_attempt(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            root = Path(temporary)
            acceptance = self.support.acceptance_data()
            self.support.write_state(root, self.support.project_text(), acceptance)
            acceptance_path = root / ".codex" / "ACCEPTANCE.json"
            before = acceptance_path.read_bytes()
            commands = (
                "python scripts/provider-runner.py",
                "node scripts/llm-call.js",
                "openai responses create --model example",
                "curl https://api.openai.com/v1/responses",
                'codex exec "bounded provider task"',
                'codex.exe exec "bounded provider task"',
                '& "C:\\Program Files\\Codex\\codex.exe" exec "bounded provider task"',
                'codex exec "help me inspect code"',
                'codex exec -- --help',
            )

            for index, command in enumerate(commands):
                with self.subTest(command=command):
                    payload = self.payload(
                        root,
                        tool_use_id=f"provider-shell-{index}",
                        tool_name="exec_command",
                        tool_input={"cmd": command, "workdir": str(root)},
                    )
                    output = self.run_hook(payload, self.state_module)[1]
                    self.assertEqual(
                        json.loads(output)["hookSpecificOutput"]["permissionDecision"],
                        "deny",
                    )
                    self.assertIn("no active atomic attempt", output)

            self.assertEqual(acceptance_path.read_bytes(), before)

    def test_codex_inspections_and_prompt_mentions_stay_state_free(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            root = Path(temporary)
            acceptance = self.support.acceptance_data()
            self.support.write_state(root, self.support.project_text(), acceptance)
            acceptance_path = root / ".codex" / "ACCEPTANCE.json"
            before = acceptance_path.read_bytes()
            commands = (
                "codex",
                "codex --help",
                "codex.exe --version",
                "codex help exec",
                "codex diagnostics",
                "codex exec --help",
                "codex.exe exec -h",
                "codex exec --version",
                'Write-Output "codex exec should be protected"',
                'rg "codex exec" README.md',
                'python scripts/check.py "codex exec"',
                "python scripts/codex.py exec",
                "node tests/codex-regression.js",
                "codex.py exec",
            )
            for index, command in enumerate(commands):
                with self.subTest(command=command):
                    payload = self.payload(
                        root,
                        tool_use_id=f"codex-inspection-{index}",
                        tool_name="exec_command",
                        tool_input={"cmd": command, "workdir": str(root)},
                    )
                    self.assertEqual(self.run_hook(payload, self.state_module)[1], "")
                    payload["hook_event_name"] = "PostToolUse"
                    payload["tool_response"] = {"status": "completed"}
                    self.assertEqual(self.run_hook(payload, self.state_module)[1], "")
                    self.assertEqual(acceptance_path.read_bytes(), before)

    def test_provider_and_cost_mcp_tools_require_an_active_attempt(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            root = Path(temporary)
            acceptance = self.support.acceptance_data()
            self.support.write_state(root, self.support.project_text(), acceptance)
            acceptance_path = root / ".codex" / "ACCEPTANCE.json"
            before = acceptance_path.read_bytes()
            tool_names = (
                "mcp__provider__generate",
                "mcp__llm__run_model",
                "image_gen__imagegen",
            )

            for index, tool_name in enumerate(tool_names):
                with self.subTest(tool_name=tool_name):
                    payload = self.payload(
                        root,
                        tool_use_id=f"provider-tool-{index}",
                        tool_name=tool_name,
                        tool_input={"prompt": "bounded provider request"},
                    )
                    output = self.run_hook(payload, self.state_module)[1]
                    self.assertEqual(
                        json.loads(output)["hookSpecificOutput"]["permissionDecision"],
                        "deny",
                    )
                    self.assertIn("no active atomic attempt", output)

            self.assertEqual(acceptance_path.read_bytes(), before)

    def test_real_classifier_ambiguous_roots_bypasses_local_work(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            parent = Path(temporary)
            first = parent / "first"
            second = parent / "second"
            self.initialize_project(first)
            self.initialize_project(second)
            first_ledger = first / ".codex" / "ACCEPTANCE.json"
            second_ledger = second / ".codex" / "ACCEPTANCE.json"
            before = (first_ledger.read_bytes(), second_ledger.read_bytes())
            registry = parent / "registry"
            payload = self.payload(
                parent,
                tool_use_id="ambiguous-local-test",
                tool_name="exec_command",
                tool_input={
                    "cmd": "python -m unittest",
                    "source": {"path": str(first / "input.txt")},
                    "destination": {"path": str(second / "output.txt")},
                },
                session_id="ambiguous-real-classifier",
            )

            with patch.object(self.hook, "REGISTRY_DIRECTORY", registry):
                status, output = self.run_hook(payload, self.state_module)

            self.assertEqual(status, 0)
            self.assertEqual(output, "")
            self.assertEqual(
                (first_ledger.read_bytes(), second_ledger.read_bytes()), before
            )
            self.assertFalse(registry.exists())

    def test_clear_external_effect_still_requires_an_active_attempt(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            root = Path(temporary)
            acceptance = self.support.acceptance_data()
            self.support.write_state(root, self.support.project_text(), acceptance)
            acceptance_path = root / ".codex" / "ACCEPTANCE.json"
            before = acceptance_path.read_bytes()
            payload = self.payload(
                root,
                tool_use_id="external-send",
                tool_name="mcp__mail__send_message",
                tool_input={"target": "exact-recipient", "body": "bounded effect"},
            )

            output = self.run_hook(payload, self.state_module)[1]
            self.assertEqual(
                json.loads(output)["hookSpecificOutput"]["permissionDecision"],
                "deny",
            )
            self.assertIn("no active atomic attempt", output)
            self.assertEqual(acceptance_path.read_bytes(), before)

    def test_exact_exec_command_activation_creates_the_only_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = parent / "project"
            self.initialize_project(root)
            registry = parent / "registry"
            payload = self.payload(
                parent,
                tool_use_id="exec-activation",
                tool_name="exec_command",
                tool_input={
                    "cmd": (
                        f'"{sys.executable}" "{self.hook.STATE_SCRIPT}" resume '
                        f'--root "{root}"'
                    ),
                    "workdir": str(parent),
                },
                session_id="exec-command-activation",
            )

            with patch.object(self.hook, "REGISTRY_DIRECTORY", registry):
                status, output = self.run_hook(payload, self.state_module)

            self.assertEqual(status, 0)
            self.assertEqual(output, "")
            entries = list(registry.glob("*.json"))
            self.assertEqual(len(entries), 1)
            self.assertEqual(
                Path(json.loads(entries[0].read_text(encoding="utf-8"))["root"]),
                root.resolve(),
            )

    def test_incident_replay_keeps_full_script_replacement_denied(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            root = Path(temporary)
            replacement = {
                "patch": (
                    "*** Begin Patch\n"
                    "*** Delete File: bootstrap.py\n"
                    "*** Add File: bootstrap.py\n"
                    "+replacement implementation\n"
                    "*** End Patch"
                )
            }
            self.begin_real_attempt(
                root,
                tool_name="apply_patch",
                tool_input=replacement,
                action_classes=["local"],
                allowed_paths=["bounded.txt"],
            )
            first = self.payload(
                root,
                tool_use_id="incident-item-83",
                tool_input=replacement,
            )
            second = self.payload(
                root,
                tool_use_id="incident-full-replacement",
                tool_input=replacement,
            )
            first_raw = self.run_hook(first, self.state_module)[1]
            second_raw = self.run_hook(second, self.state_module)[1]
            first_output = json.loads(first_raw)
            second_output = json.loads(second_raw)
            self.assertEqual(
                first_output["hookSpecificOutput"]["permissionDecision"], "deny"
            )
            self.assertEqual(
                second_output["hookSpecificOutput"]["permissionDecision"], "deny"
            )
            self.assertIn("outside admission", first_raw)
            self.assertIn("outside admission", second_raw)
            stored = json.loads(
                (root / ".codex" / "ACCEPTANCE.json").read_text(encoding="utf-8")
            )
            control = stored["execution_control"]
            self.assertEqual(control["usage"]["total_tool_calls"], 0)
            self.assertEqual(
                control["active_attempt"]["tool_claim"]["status"], "unclaimed"
            )


if __name__ == "__main__":
    unittest.main()
