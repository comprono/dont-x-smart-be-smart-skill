from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import shlex
import shutil
import subprocess
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
INSTALLER_PATH = REPOSITORY_ROOT / "scripts" / "install.py"
SPEC = importlib.util.spec_from_file_location("outcome_integrity_hook_installer", INSTALLER_PATH)
assert SPEC and SPEC.loader
INSTALLER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = INSTALLER
SPEC.loader.exec_module(INSTALLER)


@contextmanager
def workspace_temporary_directory() -> Iterator[Path]:
    """Avoid TemporaryDirectory's non-traversable Windows ACL in managed sandboxes."""
    path = REPOSITORY_ROOT / f".hook-installer-test-{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path)


class HookInstallerTests(unittest.TestCase):
    def make_package(
        self,
        root: Path,
        *,
        runtime: bytes = b"print('hook')\n",
        core: bytes = b"print('core')\n",
    ) -> Path:
        package = root / "package"
        skill = package / "skills" / "outcome-integrity"
        (skill / "hooks").mkdir(parents=True)
        (package / "global").mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: outcome-integrity\n---\n", encoding="utf-8")
        (skill / INSTALLER.HOOK_RUNTIME_RELATIVE_PATH).write_bytes(runtime)
        (skill / INSTALLER.HOOK_CORE_RELATIVE_PATH).parent.mkdir(parents=True)
        (skill / INSTALLER.HOOK_CORE_RELATIVE_PATH).write_bytes(core)
        (package / "global" / "AGENTS.snippet.md").write_text(
            "<!-- outcome-integrity:start -->\nmanaged rule\n"
            "<!-- outcome-integrity:end -->\n",
            encoding="utf-8",
        )
        return package

    def install(
        self,
        package: Path,
        codex_home: Path,
        *,
        enable: bool = False,
        advisory_only: bool = False,
        warnings: list[str] | None = None,
    ) -> tuple[Path, Path | None]:
        with mock.patch.object(INSTALLER, "_repository_root", return_value=package):
            return INSTALLER.install(
                codex_home,
                enable_user_hooks=enable,
                advisory_only=advisory_only,
                warnings=warnings,
            )

    def hook_document(self, codex_home: Path) -> dict[str, object]:
        return json.loads((codex_home / "hooks.json").read_text(encoding="utf-8"))

    def hook_health(self, package: Path, codex_home: Path) -> dict[str, object]:
        with mock.patch.object(INSTALLER, "_repository_root", return_value=package):
            return INSTALLER.inspect_hook_health(codex_home)

    def owner_groups(self, document: dict[str, object], event: str) -> list[object]:
        return [
            group
            for group in document["hooks"].get(event, [])
            if INSTALLER._group_uses_owner(group)
        ]

    def assert_no_transaction_artifacts(self, codex_home: Path) -> None:
        artifacts = [
            path
            for path in codex_home.rglob("*")
            if any(token in path.name for token in (".stage.", ".backup.", ".failed."))
            or path.name.startswith(INSTALLER.LOCK_NAME)
        ]
        self.assertEqual(artifacts, [])

    def test_repository_skill_tree_is_project_neutral(self) -> None:
        INSTALLER.validate_reusable_skill_tree(
            REPOSITORY_ROOT / "skills" / "outcome-integrity"
        )

    def test_project_specific_content_is_rejected_before_install_mutates_target(self) -> None:
        cases = (
            ("absolute-path", "notes.md", r"C:\Users\specific-user\Documents\project"),
            (
                "task-identity",
                "notes.md",
                "codex://threads/01a05813-84f8-70e1-b475-89cbb017e3f0",
            ),
            ("evidence-hash", "notes.md", "a" * 64),
            ("authorization", "notes.md", "I explicitly authorize this install."),
            (
                "instance-id",
                "scripts/project_outcome.py",
                "RECOVERY-SPECIFIC-PROJECT-R42 = True\n",
            ),
            (
                "pinned-project",
                "scripts/project_outcome.py",
                "SPECIFIC_PROJECT_ID = 'project-42'\n",
            ),
        )
        for label, relative, content in cases:
            with self.subTest(label=label), workspace_temporary_directory() as temporary:
                root = Path(temporary)
                package = self.make_package(root)
                skill = package / "skills" / "outcome-integrity"
                target = skill / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                codex_home = root / ".codex"
                installed = codex_home / "skills" / "outcome-integrity"
                installed.mkdir(parents=True)
                sentinel = installed / "SKILL.md"
                sentinel.write_text("existing target\n", encoding="utf-8")

                with self.assertRaisesRegex(ValueError, "project-specific content"):
                    self.install(package, codex_home, enable=True)

                self.assertEqual(sentinel.read_text(encoding="utf-8"), "existing target\n")
                self.assertFalse((codex_home / "hooks.json").exists())
                self.assert_no_transaction_artifacts(codex_home)

    def test_generic_placeholders_and_authorization_guidance_are_allowed(self) -> None:
        with workspace_temporary_directory() as temporary:
            root = Path(temporary)
            package = self.make_package(root)
            skill = package / "skills" / "outcome-integrity"
            (skill / "notes.md").write_text(
                "Use C:\\Users\\<user> or /home/<user>.\n"
                "Reference codex://threads/<thread-id> and sha256:<64-hex>.\n"
                "Obtain explicit user authorization before the bounded effect.\n",
                encoding="utf-8",
            )

            INSTALLER.validate_reusable_skill_tree(skill)

    def test_enable_renders_official_synchronous_shape_and_exact_commands(self) -> None:
        with workspace_temporary_directory() as temporary:
            root = Path(temporary)
            package = self.make_package(root, runtime=b"runtime with spaces\n")
            codex_home = root / "Codex Home With Spaces" / ".codex"
            codex_home.mkdir(parents=True)

            self.install(package, codex_home, enable=True)

            document = self.hook_document(codex_home)
            sidecar = json.loads(
                (codex_home / INSTALLER.HOOK_SIDECAR_NAME).read_text(encoding="utf-8")
            )
            runtime_source = (
                package / "skills" / "outcome-integrity" / INSTALLER.HOOK_RUNTIME_RELATIVE_PATH
            )
            runtime_target = (
                codex_home
                / "skills"
                / "outcome-integrity"
                / INSTALLER.HOOK_RUNTIME_RELATIVE_PATH
            ).absolute()
            core_source = (
                package / "skills" / "outcome-integrity" / INSTALLER.HOOK_CORE_RELATIVE_PATH
            )
            core_target = (
                codex_home
                / "skills"
                / "outcome-integrity"
                / INSTALLER.HOOK_CORE_RELATIVE_PATH
            ).absolute()
            digest = hashlib.sha256(runtime_source.read_bytes()).hexdigest()
            core_digest = hashlib.sha256(core_source.read_bytes()).hexdigest()
            expected_args = [
                str(Path(sys.executable).resolve()),
                str(runtime_target),
                "--owner",
                INSTALLER.HOOK_OWNER,
                "--self-sha256",
                digest,
                "--core-sha256",
                core_digest,
            ]
            expected_command = shlex.join(expected_args)
            expected_windows = subprocess.list2cmdline(expected_args)

            self.assertEqual(sidecar["schema_version"], 1)
            self.assertEqual(sidecar["owner"], INSTALLER.HOOK_OWNER)
            self.assertTrue(sidecar["hooks_file_created"])
            self.assertEqual(sidecar["runtime_path"], str(runtime_target))
            self.assertEqual(sidecar["runtime_sha256"], digest)
            self.assertEqual(sidecar["core_path"], str(core_target))
            self.assertEqual(sidecar["core_sha256"], core_digest)
            self.assertTrue(Path(sidecar["runtime_path"]).is_absolute())
            self.assertTrue(Path(sidecar["core_path"]).is_absolute())
            self.assertIn(f'"{runtime_target}"', expected_windows)
            for event in INSTALLER.HOOK_EVENTS:
                groups = self.owner_groups(document, event)
                self.assertEqual(len(groups), 1)
                group = groups[0]
                self.assertEqual(group["matcher"], "*")
                self.assertEqual(len(group["hooks"]), 1)
                handler = group["hooks"][0]
                self.assertEqual(handler["type"], "command")
                self.assertEqual(handler["command"], expected_command)
                self.assertEqual(handler["commandWindows"], expected_windows)
                self.assertEqual(handler["timeout"], 10)
                self.assertNotIn("async", handler)
                self.assertIn(f"--owner {INSTALLER.HOOK_OWNER}", handler["command"])
                self.assertIn(f"--self-sha256 {digest}", handler["command"])
                self.assertIn(f"--core-sha256 {core_digest}", handler["command"])
                owned_entry = next(
                    entry for entry in sidecar["entries"] if entry["event"] == event
                )
                self.assertEqual(owned_entry["group"], group)
            self.assertTrue(runtime_target.is_file())
            self.assertTrue(core_target.is_file())
            self.assert_no_transaction_artifacts(codex_home)

    def test_normal_install_never_reads_or_mutates_hook_files(self) -> None:
        with workspace_temporary_directory() as temporary:
            root = Path(temporary)
            package = self.make_package(root)
            codex_home = root / ".codex"
            codex_home.mkdir()
            hooks = codex_home / "hooks.json"
            sidecar = codex_home / INSTALLER.HOOK_SIDECAR_NAME
            hooks.write_bytes(b"{ deliberately malformed hooks")

            self.install(package, codex_home)

            self.assertEqual(hooks.read_bytes(), b"{ deliberately malformed hooks")
            self.assertFalse(sidecar.exists())
            self.assert_no_transaction_artifacts(codex_home)

    def test_enable_preserves_unrelated_groups_collapses_owned_duplicates_and_is_exact(self) -> None:
        with workspace_temporary_directory() as temporary:
            root = Path(temporary)
            package = self.make_package(root)
            codex_home = root / ".codex"
            codex_home.mkdir()
            unrelated_pre = {
                "matcher": "Bash",
                "hooks": [{"type": "command", "command": "other-pre"}],
            }
            unrelated_session = {
                "matcher": "startup",
                "hooks": [{"type": "command", "command": "other-session"}],
            }
            initial = {
                "description": "keep this metadata",
                "custom": {"preserve": [1, 2, 3]},
                "hooks": {
                    "PreToolUse": [copy.deepcopy(unrelated_pre)],
                    "SessionStart": [copy.deepcopy(unrelated_session)],
                },
            }
            (codex_home / "hooks.json").write_text(
                json.dumps(initial, indent=4) + "\n", encoding="utf-8"
            )

            self.install(package, codex_home, enable=True)
            first = self.hook_document(codex_home)
            sidecar = json.loads(
                (codex_home / INSTALLER.HOOK_SIDECAR_NAME).read_text(encoding="utf-8")
            )
            for entry in sidecar["entries"]:
                first["hooks"][entry["event"]].append(copy.deepcopy(entry["group"]))
            (codex_home / "hooks.json").write_text(
                json.dumps(first, indent=2) + "\n", encoding="utf-8"
            )

            self.install(package, codex_home, enable=True)
            collapsed = self.hook_document(codex_home)
            self.assertEqual(collapsed["description"], initial["description"])
            self.assertEqual(collapsed["custom"], initial["custom"])
            self.assertIn(unrelated_pre, collapsed["hooks"]["PreToolUse"])
            self.assertEqual(collapsed["hooks"]["SessionStart"], [unrelated_session])
            for event in INSTALLER.HOOK_EVENTS:
                self.assertEqual(len(self.owner_groups(collapsed, event)), 1)

            hooks_exact = (codex_home / "hooks.json").read_bytes()
            sidecar_exact = (codex_home / INSTALLER.HOOK_SIDECAR_NAME).read_bytes()
            self.install(package, codex_home, enable=True)
            self.assertEqual((codex_home / "hooks.json").read_bytes(), hooks_exact)
            self.assertEqual(
                (codex_home / INSTALLER.HOOK_SIDECAR_NAME).read_bytes(), sidecar_exact
            )
            self.assert_no_transaction_artifacts(codex_home)

    def test_core_policy_change_rotates_handler_hash_with_unchanged_runtime(self) -> None:
        with workspace_temporary_directory() as temporary:
            root = Path(temporary)
            package = self.make_package(
                root,
                runtime=b"stable runtime\n",
                core=b"core policy v1\n",
            )
            codex_home = root / ".codex"
            codex_home.mkdir()

            self.install(package, codex_home, enable=True)
            first = self.hook_document(codex_home)
            first_handler = self.owner_groups(first, "PreToolUse")[0]["hooks"][0]
            first_sidecar = json.loads(
                (codex_home / INSTALLER.HOOK_SIDECAR_NAME).read_text(encoding="utf-8")
            )
            runtime_digest = first_sidecar["runtime_sha256"]

            core_source = (
                package / "skills" / "outcome-integrity" / INSTALLER.HOOK_CORE_RELATIVE_PATH
            )
            core_source.write_bytes(b"core policy v2\n")
            expected_core_digest = hashlib.sha256(core_source.read_bytes()).hexdigest()
            warnings: list[str] = []
            self.install(package, codex_home, warnings=warnings)

            second = self.hook_document(codex_home)
            second_handler = self.owner_groups(second, "PreToolUse")[0]["hooks"][0]
            second_sidecar = json.loads(
                (codex_home / INSTALLER.HOOK_SIDECAR_NAME).read_text(encoding="utf-8")
            )
            self.assertEqual(second_sidecar["runtime_sha256"], runtime_digest)
            self.assertEqual(second_sidecar["core_sha256"], expected_core_digest)
            self.assertNotEqual(second_handler["command"], first_handler["command"])
            self.assertNotEqual(
                second_handler["commandWindows"], first_handler["commandWindows"]
            )
            self.assertIn(
                f"--core-sha256 {expected_core_digest}", second_handler["command"]
            )
            self.assertTrue(any("/hooks" in warning for warning in warnings))
            installed_core = (
                codex_home
                / "skills"
                / "outcome-integrity"
                / INSTALLER.HOOK_CORE_RELATIVE_PATH
            )
            self.assertEqual(installed_core.read_bytes(), b"core policy v2\n")
            hooks_exact = (codex_home / "hooks.json").read_bytes()
            sidecar_exact = (codex_home / INSTALLER.HOOK_SIDECAR_NAME).read_bytes()
            repeated_warnings: list[str] = []
            self.install(package, codex_home, warnings=repeated_warnings)
            self.assertEqual((codex_home / "hooks.json").read_bytes(), hooks_exact)
            self.assertEqual(
                (codex_home / INSTALLER.HOOK_SIDECAR_NAME).read_bytes(), sidecar_exact
            )
            self.assertFalse(any("/hooks" in warning for warning in repeated_warnings))
            self.assert_no_transaction_artifacts(codex_home)

    def test_hook_health_distinguishes_exact_configuration_from_active_enforcement(self) -> None:
        with workspace_temporary_directory() as temporary:
            root = Path(temporary)
            package = self.make_package(root)
            codex_home = root / ".codex"
            codex_home.mkdir()
            self.install(package, codex_home, enable=True)

            exact = self.hook_health(package, codex_home)
            self.assertEqual(exact["state"], "configured-exact-trust-unverified")
            self.assertTrue(exact["configured_exact"])
            self.assertTrue(exact["source_exact"])
            self.assertFalse(exact["active_verified"])

            installed_core = (
                codex_home
                / "skills"
                / "outcome-integrity"
                / INSTALLER.HOOK_CORE_RELATIVE_PATH
            )
            installed_core.write_bytes(b"changed outside the transactional installer\n")
            stale = self.hook_health(package, codex_home)
            self.assertEqual(stale["state"], "configured-stale")
            self.assertFalse(stale["configured_exact"])
            self.assertFalse(stale["source_exact"])
            self.assertFalse(stale["active_verified"])

    def test_hook_health_rejects_self_consistent_noncanonical_live_core(self) -> None:
        with workspace_temporary_directory() as temporary:
            root = Path(temporary)
            package = self.make_package(root)
            codex_home = root / ".codex"
            codex_home.mkdir()
            self.install(package, codex_home, enable=True)
            installed_core = (
                codex_home
                / "skills"
                / "outcome-integrity"
                / INSTALLER.HOOK_CORE_RELATIVE_PATH
            )
            old_digest = hashlib.sha256(installed_core.read_bytes()).hexdigest()
            installed_core.write_bytes(b"project-specific compatibility core\n")
            new_digest = hashlib.sha256(installed_core.read_bytes()).hexdigest()
            for path in (
                codex_home / "hooks.json",
                codex_home / INSTALLER.HOOK_SIDECAR_NAME,
            ):
                text = path.read_text(encoding="utf-8")
                self.assertIn(old_digest, text)
                path.write_text(text.replace(old_digest, new_digest), encoding="utf-8")

            health = self.hook_health(package, codex_home)

            self.assertEqual(health["state"], "configured-stale")
            self.assertFalse(health["configured_exact"])
            self.assertFalse(health["source_exact"])
            self.assertTrue(
                any("differs from this installer package" in error for error in health["errors"])
            )

    def test_state_only_hook_metadata_is_preserved_and_reports_disabled_owned_hooks(self) -> None:
        with workspace_temporary_directory() as temporary:
            root = Path(temporary)
            package = self.make_package(root)
            codex_home = root / ".codex"
            codex_home.mkdir()
            self.install(package, codex_home, enable=True)

            hooks_path = (codex_home / "hooks.json").absolute()
            config = codex_home / "config.toml"
            config.write_text(
                "[hooks.state]\n\n"
                f"[hooks.state.'{hooks_path}:pre_tool_use:0:0']\n"
                'trusted_hash = "sha256:pre-tool-use-definition"\n'
                "enabled = false\n\n"
                f"[hooks.state.'{hooks_path}:post_tool_use:0:0']\n"
                'trusted_hash = "sha256:post-tool-use-definition"\n'
                "enabled = false\n",
                encoding="utf-8",
            )
            config_before = config.read_bytes()
            warnings: list[str] = []

            self.install(package, codex_home, enable=True, warnings=warnings)

            self.assertEqual(config.read_bytes(), config_before)
            self.assertTrue(any("disabled" in warning.lower() for warning in warnings))
            health = self.hook_health(package, codex_home)
            self.assertEqual(health["state"], "configured-disabled")
            self.assertTrue(health["configured_exact"])
            self.assertFalse(health["active_verified"])
            self.assertEqual(health["errors"], [])
            self.assertIsNotNone(health["definition_fingerprint"])
            self.assertTrue(
                any("disabled" in warning.lower() for warning in health["warnings"])
            )
            self.assertEqual(config.read_bytes(), config_before)
            self.assert_no_transaction_artifacts(codex_home)

    def test_malformed_inline_and_reparse_preflight_refuse_before_installation(self) -> None:
        for case in ("malformed", "inline", "reparse"):
            with self.subTest(case=case), workspace_temporary_directory() as temporary:
                root = Path(temporary)
                package = self.make_package(root)
                codex_home = root / ".codex"
                codex_home.mkdir()
                hooks = codex_home / "hooks.json"
                if case == "malformed":
                    hooks.write_text("{ not json", encoding="utf-8")
                elif case == "inline":
                    (codex_home / "config.toml").write_text(
                        "[[hooks.PreToolUse]]\n"
                        'matcher = "*"\n\n'
                        "[[hooks.PreToolUse.hooks]]\n"
                        'type = "command"\n'
                        'command = "inline-pre-tool-use"\n',
                        encoding="utf-8",
                    )
                else:
                    hooks.write_text('{"hooks": {}}\n', encoding="utf-8")

                real_reparse = INSTALLER._is_reparse_point

                def is_reparse(path: Path) -> bool:
                    return case == "reparse" and path == hooks or real_reparse(path)

                with mock.patch.object(INSTALLER, "_is_reparse_point", side_effect=is_reparse):
                    with self.assertRaisesRegex(ValueError, "malformed|inline|reparse"):
                        self.install(package, codex_home, enable=True)
                self.assertFalse((codex_home / "skills").exists())
                self.assertFalse((codex_home / "AGENTS.md").exists())
                self.assertFalse((codex_home / INSTALLER.HOOK_SIDECAR_NAME).exists())
                self.assert_no_transaction_artifacts(codex_home)

    def test_hook_activation_failure_rolls_back_hook_sidecar_agents_and_skill(self) -> None:
        with workspace_temporary_directory() as temporary:
            root = Path(temporary)
            package = self.make_package(root, runtime=b"old runtime\n")
            codex_home = root / ".codex"
            codex_home.mkdir()
            hooks = codex_home / "hooks.json"
            hooks.write_bytes(b'{"description":"unrelated","hooks":{}}\n')
            self.install(package, codex_home)
            installed = codex_home / "skills" / "outcome-integrity"
            (installed / "previous-only.txt").write_bytes(b"restore me\n")
            skill_before = INSTALLER.canonical_tree_manifest(installed)
            agents_before = (codex_home / "AGENTS.md").read_bytes()
            hooks_before = hooks.read_bytes()
            (package / "global" / "AGENTS.snippet.md").write_text(
                "<!-- outcome-integrity:start -->\nnew managed rule\n"
                "<!-- outcome-integrity:end -->\n",
                encoding="utf-8",
            )
            (
                package
                / "skills"
                / "outcome-integrity"
                / INSTALLER.HOOK_RUNTIME_RELATIVE_PATH
            ).write_bytes(b"new runtime\n")
            real_replace = INSTALLER._replace_path

            def fail_hooks_stage(source: Path, target: Path) -> None:
                if target == hooks and ".stage." in source.name:
                    raise OSError("injected hooks activation failure")
                real_replace(source, target)

            with mock.patch.object(INSTALLER, "_replace_path", side_effect=fail_hooks_stage):
                with self.assertRaisesRegex(OSError, "injected hooks activation failure"):
                    self.install(package, codex_home, enable=True)

            self.assertEqual(INSTALLER.canonical_tree_manifest(installed), skill_before)
            self.assertEqual((codex_home / "AGENTS.md").read_bytes(), agents_before)
            self.assertEqual(hooks.read_bytes(), hooks_before)
            self.assertFalse((codex_home / INSTALLER.HOOK_SIDECAR_NAME).exists())
            self.assert_no_transaction_artifacts(codex_home)

    def test_fresh_hook_activation_failure_leaves_no_installation_directories(self) -> None:
        with workspace_temporary_directory() as temporary:
            root = Path(temporary)
            package = self.make_package(root)
            codex_home = root / ".codex"
            hooks = codex_home / "hooks.json"
            real_replace = INSTALLER._replace_path

            def fail_hooks_stage(source: Path, target: Path) -> None:
                if target == hooks and ".stage." in source.name:
                    raise OSError("injected fresh hooks activation failure")
                real_replace(source, target)

            with mock.patch.object(INSTALLER, "_replace_path", side_effect=fail_hooks_stage):
                with self.assertRaisesRegex(
                    OSError, "injected fresh hooks activation failure"
                ):
                    self.install(package, codex_home, enable=True)

            self.assertFalse(codex_home.exists())

    def test_disable_removes_only_owned_semantics_and_keeps_skill(self) -> None:
        with workspace_temporary_directory() as temporary:
            root = Path(temporary)
            package = self.make_package(root)
            codex_home = root / ".codex"
            codex_home.mkdir()
            unrelated = {
                "description": "unrelated",
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [{"type": "command", "command": "keep-me"}],
                        }
                    ]
                },
            }
            (codex_home / "hooks.json").write_text(
                json.dumps(unrelated, indent=2) + "\n", encoding="utf-8"
            )
            self.install(package, codex_home, enable=True)
            installed = codex_home / "skills" / "outcome-integrity"
            skill_before = INSTALLER.canonical_tree_manifest(installed)

            self.assertTrue(INSTALLER.disable_user_hooks(codex_home))

            self.assertEqual(self.hook_document(codex_home), unrelated)
            self.assertFalse((codex_home / INSTALLER.HOOK_SIDECAR_NAME).exists())
            self.assertEqual(INSTALLER.canonical_tree_manifest(installed), skill_before)
            self.assert_no_transaction_artifacts(codex_home)

    def test_advisory_install_updates_package_and_removes_only_owned_hooks(self) -> None:
        with workspace_temporary_directory() as temporary:
            root = Path(temporary)
            package = self.make_package(root)
            codex_home = root / ".codex"
            codex_home.mkdir()
            self.install(package, codex_home, enable=True)
            hooks = self.hook_document(codex_home)
            hooks["hooks"].setdefault("PreToolUse", []).insert(
                0,
                {
                    "matcher": "unrelated",
                    "hooks": [{"type": "command", "command": "keep-me"}],
                },
            )
            (codex_home / "hooks.json").write_text(
                json.dumps(hooks, indent=2) + "\n", encoding="utf-8"
            )
            source_skill = package / "skills" / "outcome-integrity" / "SKILL.md"
            source_skill.write_text(
                "---\nname: outcome-integrity\n---\nrepaired advisory skill\n",
                encoding="utf-8",
            )
            source_rules = package / "global" / "AGENTS.snippet.md"
            source_rules.write_text(
                "<!-- outcome-integrity:start -->\nrepaired advisory rule\n"
                "<!-- outcome-integrity:end -->\n",
                encoding="utf-8",
            )

            self.install(package, codex_home, advisory_only=True)

            document = self.hook_document(codex_home)
            self.assertEqual(
                document["hooks"]["PreToolUse"],
                [
                    {
                        "matcher": "unrelated",
                        "hooks": [{"type": "command", "command": "keep-me"}],
                    }
                ],
            )
            self.assertNotIn("PostToolUse", document["hooks"])
            self.assertFalse((codex_home / INSTALLER.HOOK_SIDECAR_NAME).exists())
            self.assertEqual(
                (
                    codex_home / "skills" / "outcome-integrity" / "SKILL.md"
                ).read_text(encoding="utf-8"),
                source_skill.read_text(encoding="utf-8"),
            )
            self.assertIn(
                "repaired advisory rule",
                (codex_home / "AGENTS.md").read_text(encoding="utf-8"),
            )
            self.assert_no_transaction_artifacts(codex_home)

    def test_disable_deletes_only_package_created_empty_hooks_file(self) -> None:
        with workspace_temporary_directory() as temporary:
            root = Path(temporary)
            package = self.make_package(root)
            codex_home = root / ".codex"
            codex_home.mkdir()
            self.install(package, codex_home, enable=True)
            self.assertTrue(INSTALLER.disable_user_hooks(codex_home))
            self.assertFalse((codex_home / "hooks.json").exists())
            self.assertFalse((codex_home / INSTALLER.HOOK_SIDECAR_NAME).exists())

    def test_modified_owned_entry_refuses_enable_and_disable_without_mutation(self) -> None:
        with workspace_temporary_directory() as temporary:
            root = Path(temporary)
            package = self.make_package(root)
            codex_home = root / ".codex"
            codex_home.mkdir()
            self.install(package, codex_home, enable=True)
            document = self.hook_document(codex_home)
            owner = self.owner_groups(document, "PreToolUse")[0]
            owner["hooks"][0]["statusMessage"] = "user changed this"
            (codex_home / "hooks.json").write_text(
                json.dumps(document, indent=2) + "\n", encoding="utf-8"
            )
            hooks_before = (codex_home / "hooks.json").read_bytes()
            sidecar_before = (codex_home / INSTALLER.HOOK_SIDECAR_NAME).read_bytes()

            with self.assertRaisesRegex(ValueError, "user-modified owned"):
                self.install(package, codex_home)
            with self.assertRaisesRegex(ValueError, "user-modified owned"):
                self.install(package, codex_home, enable=True)
            with self.assertRaisesRegex(ValueError, "user-modified owned"):
                INSTALLER.disable_user_hooks(codex_home)

            self.assertEqual((codex_home / "hooks.json").read_bytes(), hooks_before)
            self.assertEqual(
                (codex_home / INSTALLER.HOOK_SIDECAR_NAME).read_bytes(), sidecar_before
            )
            self.assert_no_transaction_artifacts(codex_home)

    def test_disabled_and_managed_only_policy_warns_without_config_mutation(self) -> None:
        with workspace_temporary_directory() as temporary:
            root = Path(temporary)
            package = self.make_package(root)
            codex_home = root / ".codex"
            codex_home.mkdir()
            config = codex_home / "config.toml"
            requirements = codex_home / "requirements.toml"
            config.write_text(
                "allow_managed_hooks_only = true\n[features]\nhooks = false\n",
                encoding="utf-8",
            )
            requirements.write_text(
                "allow_managed_hooks_only = true\n[features]\nhooks = false\n",
                encoding="utf-8",
            )
            config_before = config.read_bytes()
            requirements_before = requirements.read_bytes()
            warnings: list[str] = []

            self.install(package, codex_home, enable=True, warnings=warnings)

            self.assertEqual(len(warnings), 3)
            self.assertTrue(any("disabled" in warning for warning in warnings))
            self.assertTrue(any("managed hooks only" in warning for warning in warnings))
            self.assertEqual(config.read_bytes(), config_before)
            self.assertEqual(requirements.read_bytes(), requirements_before)


if __name__ == "__main__":
    unittest.main()
