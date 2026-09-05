#!/usr/bin/env python3
"""Install Outcome Integrity without overwriting unrelated Codex settings."""

from __future__ import annotations

import argparse
import copy
import ctypes
import hashlib
import json
import os
import re
import shlex
import shutil
import socket
import stat
import subprocess
import sys
import time
import tomllib
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, NamedTuple


START_MARKER = "<!-- outcome-integrity:start -->"
END_MARKER = "<!-- outcome-integrity:end -->"
LOCK_NAME = ".outcome-integrity-install.lock"
LOCK_OWNER_NAME = "owner.json"
LOCK_STALE_SECONDS = 15 * 60
IGNORED_DIRECTORY_NAMES = {"__pycache__"}
HOOK_OWNER = "outcome-integrity-v1"
HOOK_SIDECAR_NAME = ".outcome-integrity-hook-install.json"
HOOK_SIDECAR_VERSION = 1
HOOK_RUNTIME_RELATIVE_PATH = Path("hooks") / "outcome_integrity_hook.py"
HOOK_CORE_RELATIVE_PATH = Path("scripts") / "project_outcome.py"
HOOK_EVENTS = ("PreToolUse", "PostToolUse")
HOOK_TIMEOUT_SECONDS = 10
TEXT_SKILL_SUFFIXES = {".json", ".md", ".py", ".toml", ".txt", ".yaml", ".yml"}
ABSOLUTE_USER_PATH_PATTERN = re.compile(
    r"(?i)(?:\b[a-z]:[\\/]users[\\/](?![<{])[^\\/\s\"']+|"
    r"/home/(?![<{])[^/\s\"']+)"
)
CODEX_THREAD_PATTERN = re.compile(r"(?i)codex://threads/[0-9a-f-]{16,}")
EXACT_SHA256_PATTERN = re.compile(
    r"(?i)(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])"
)
FIRST_PERSON_AUTHORIZATION_PATTERN = re.compile(
    r"(?i)\bI\s+(?:explicitly\s+)?authori[sz]e\b"
)
INSTANCE_IDENTIFIER_PATTERN = re.compile(
    r"\b(?:ACTIVATION|ATTEMPT|AUTH|LINEAGE|METHOD|MIGRATION|RECEIPT|RECOVERY)-"
    r"[A-Z0-9][A-Z0-9_-]{3,}\b"
)
PINNED_PROJECT_CONSTANT_PATTERN = re.compile(
    r"(?m)^[A-Z][A-Z0-9_]*(?:PROJECT_ID|PROJECT_ROOT|USER_AUTHORIZATION)\s*="
)


class FileMutation(NamedTuple):
    path: Path
    before_exists: bool
    before_bytes: bytes
    after_bytes: bytes | None
    label: str


class HookPlan(NamedTuple):
    mutations: tuple[FileMutation, ...]
    hooks_path: Path
    sidecar_path: Path
    warnings: tuple[str, ...]
    expected_skill_hashes: tuple[tuple[Path, str], ...] = ()


def default_codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


def _repository_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _path_lexists(path: Path) -> bool:
    return os.path.lexists(path)


def _is_reparse_point(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    file_attributes = getattr(metadata, "st_file_attributes", 0)
    is_junction = getattr(path, "is_junction", None)
    return (
        stat.S_ISLNK(metadata.st_mode)
        or bool(file_attributes & reparse_flag)
        or bool(is_junction and is_junction())
    )


def _require_plain_directory(path: Path, label: str, *, allow_missing: bool = False) -> None:
    if _is_reparse_point(path):
        raise ValueError(f"Refusing {label} because it is a symlink, junction, or reparse point: {path}")
    if not _path_lexists(path):
        if allow_missing:
            return
        raise FileNotFoundError(f"Missing {label}: {path}")
    if not path.is_dir():
        raise ValueError(f"Expected {label} to be a directory: {path}")


def _require_plain_file(path: Path, label: str, *, allow_missing: bool = False) -> None:
    if _is_reparse_point(path):
        raise ValueError(f"Refusing {label} because it is a symlink, junction, or reparse point: {path}")
    if not _path_lexists(path):
        if allow_missing:
            return
        raise FileNotFoundError(f"Missing {label}: {path}")
    if not path.is_file():
        raise ValueError(f"Expected {label} to be a regular file: {path}")


def _paths_overlap(first: Path, second: Path) -> bool:
    first_resolved = first.resolve()
    second_resolved = second.resolve()
    return (
        first_resolved == second_resolved
        or first_resolved in second_resolved.parents
        or second_resolved in first_resolved.parents
    )


def _require_disjoint_trees(skill_source: Path, skill_target: Path) -> None:
    if _paths_overlap(skill_source, skill_target):
        raise ValueError(
            "Refusing installation because the source and target skill trees overlap: "
            f"{skill_source} and {skill_target}"
        )


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_tree_manifest(root: Path) -> dict[str, tuple[object, ...]]:
    """Return a type-and-content manifest while refusing link-like tree entries."""
    _require_plain_directory(root, "skill tree")
    manifest: dict[str, tuple[object, ...]] = {}
    pending: list[tuple[Path, Path, bool]] = [(root, Path(), True)]
    while pending:
        directory, relative_directory, include_entries = pending.pop()
        with os.scandir(directory) as entries:
            ordered_entries = sorted(entries, key=lambda entry: entry.name.casefold())
        for entry in ordered_entries:
            path = Path(entry.path)
            relative = relative_directory / entry.name
            metadata = entry.stat(follow_symlinks=False)
            reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            if entry.is_symlink() or bool(
                getattr(metadata, "st_file_attributes", 0) & reparse_flag
            ):
                raise ValueError(
                    "Refusing a skill tree containing a symlink, junction, or reparse point: "
                    f"{path}"
                )
            key = relative.as_posix()
            if stat.S_ISDIR(metadata.st_mode):
                child_included = include_entries and entry.name not in IGNORED_DIRECTORY_NAMES
                if child_included:
                    manifest[key] = ("directory",)
                pending.append((path, relative, child_included))
            elif stat.S_ISREG(metadata.st_mode):
                if include_entries and path.suffix != ".pyc":
                    manifest[key] = ("file", metadata.st_size, _hash_file(path))
            else:
                raise ValueError(f"Refusing a non-regular skill tree entry: {path}")
    return manifest


def validate_reusable_skill_tree(root: Path) -> None:
    """Refuse project-owned identities or evidence in a user-wide skill bundle."""
    manifest = canonical_tree_manifest(root)
    violations: list[str] = []
    for relative_text, entry in sorted(manifest.items()):
        if entry[0] != "file":
            continue
        relative = Path(relative_text)
        if relative.suffix.casefold() not in TEXT_SKILL_SUFFIXES:
            continue
        path = root / relative
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in (
            ("absolute user-home path", ABSOLUTE_USER_PATH_PATTERN),
            ("Codex task identity", CODEX_THREAD_PATTERN),
            ("exact SHA-256 evidence binding", EXACT_SHA256_PATTERN),
            ("embedded user authorization prose", FIRST_PERSON_AUTHORIZATION_PATTERN),
        ):
            if pattern.search(text):
                violations.append(f"{relative.as_posix()}: {label}")
        if relative.parts and relative.parts[0] in {"hooks", "scripts"}:
            for label, pattern in (
                ("exact project/effect identifier", INSTANCE_IDENTIFIER_PATTERN),
                ("pinned project or authorization constant", PINNED_PROJECT_CONSTANT_PATTERN),
            ):
                if pattern.search(text):
                    violations.append(f"{relative.as_posix()}: {label}")
    if violations:
        raise ValueError(
            "Refusing project-specific content in the user-wide Outcome Integrity skill: "
            + "; ".join(violations)
        )


def _managed_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    cursor = 0
    while cursor < len(text):
        start = text.find(START_MARKER, cursor)
        stray_end = text.find(END_MARKER, cursor)
        if start < 0:
            if stray_end >= 0:
                raise ValueError("AGENTS.md has an Outcome Integrity end marker without a start marker")
            break
        if 0 <= stray_end < start:
            raise ValueError("AGENTS.md has Outcome Integrity markers in the wrong order")
        end = text.find(END_MARKER, start + len(START_MARKER))
        nested_start = text.find(START_MARKER, start + len(START_MARKER))
        if end < 0 or (0 <= nested_start < end):
            raise ValueError("AGENTS.md has malformed or nested Outcome Integrity markers")
        span_end = end + len(END_MARKER)
        spans.append((start, span_end))
        cursor = span_end
    return spans


def _preferred_newline(text: str) -> str:
    newline = text.find("\n")
    if newline > 0 and text[newline - 1] == "\r":
        return "\r\n"
    if newline >= 0:
        return "\n"
    return "\r\n" if os.name == "nt" else "\n"


def _render_managed_block(block: str, newline: str) -> str:
    normalized = block.replace("\r\n", "\n").replace("\r", "\n").strip()
    spans = _managed_spans(normalized)
    if spans != [(0, len(normalized))]:
        raise ValueError("The packaged global rule snippet must contain exactly one complete managed block")
    return normalized.replace("\n", newline)


def merge_managed_block(current: str, block: str) -> str:
    """Replace only managed spans, preserving every unrelated character exactly."""
    newline = _preferred_newline(current)
    rendered_block = _render_managed_block(block, newline)
    spans = _managed_spans(current)
    if not spans:
        if not current:
            return rendered_block + newline
        if current.endswith(("\r\n\r\n", "\n\n", "\r\r")):
            separator = ""
        elif current.endswith(("\r\n", "\n", "\r")):
            separator = newline
        else:
            separator = newline * 2
        return current + separator + rendered_block + newline

    pieces = [current[: spans[0][0]], rendered_block]
    cursor = spans[0][1]
    for start, end in spans[1:]:
        pieces.append(current[cursor:start])
        cursor = end
    pieces.append(current[cursor:])
    return "".join(pieces)


def _read_plain_bytes(path: Path, label: str) -> tuple[bool, bytes]:
    exists = _path_lexists(path)
    _require_plain_file(path, label, allow_missing=True)
    return exists, path.read_bytes() if exists else b""


def _load_json_bytes(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"Refusing malformed {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Refusing {label} because its top level is not an object")
    return value


def _render_json_bytes(value: dict[str, Any], *, sort_keys: bool = False) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=sort_keys) + "\n"
    ).encode("utf-8")


def _load_toml_file(path: Path, label: str) -> dict[str, Any]:
    exists, raw = _read_plain_bytes(path, label)
    if not exists:
        return {}
    try:
        value = tomllib.loads(raw.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"Refusing malformed {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Refusing {label} because its top level is not a table")
    return value


def _hook_config_preflight(codex_home: Path) -> list[str]:
    config = _load_toml_file(codex_home / "config.toml", "Codex config.toml")
    warnings: list[str] = []
    hooks = config.get("hooks")
    if hooks is not None:
        if not isinstance(hooks, dict) or set(hooks) - {"state"}:
            raise ValueError(
                "Refusing user-hook installation because config.toml contains inline "
                "hook definitions; use hooks.json for lifecycle definitions"
            )
        hook_state = hooks.get("state", {})
        if not isinstance(hook_state, dict):
            raise ValueError("Refusing config.toml because [hooks.state] is not a table")
        disabled_owned_events = {
            event
            for key, value in hook_state.items()
            if isinstance(key, str)
            and isinstance(value, dict)
            and value.get("enabled") is False
            for event in HOOK_EVENTS
            if f":{event.replace('ToolUse', '_tool_use').casefold()}:"
            in key.casefold()
            and str((codex_home / "hooks.json").resolve()).casefold()
            in key.casefold()
        }
        if disabled_owned_events == set(HOOK_EVENTS):
            warnings.append(
                "Outcome Integrity handlers are disabled in host /hooks state; "
                "the installed hook remains inactive."
            )

    features = config.get("features")
    if isinstance(features, dict) and (
        features.get("hooks") is False
        or ("hooks" not in features and features.get("codex_hooks") is False)
    ):
        warnings.append(
            "Codex hooks are disabled in config.toml; the installed hook will remain inactive."
        )

    requirements_path = codex_home / "requirements.toml"
    requirements = _load_toml_file(requirements_path, "Codex requirements.toml")
    required_features = requirements.get("features")
    if isinstance(required_features, dict) and (
        required_features.get("hooks") is False
        or (
            "hooks" not in required_features
            and required_features.get("codex_hooks") is False
        )
    ):
        warnings.append(
            "Managed requirements disable Codex hooks; the installed hook will remain inactive."
        )
    if requirements.get("allow_managed_hooks_only") is True:
        warnings.append(
            "Managed requirements allow managed hooks only; this user hook will remain inactive."
        )
    return warnings


def _validate_hooks_document(value: dict[str, Any]) -> dict[str, list[Any]]:
    hooks = value.get("hooks")
    if hooks is None:
        hooks = {}
        value["hooks"] = hooks
    if not isinstance(hooks, dict):
        raise ValueError("Refusing hooks.json because hooks is not an object")
    for event, groups in hooks.items():
        if not isinstance(event, str) or not isinstance(groups, list):
            raise ValueError(
                "Refusing hooks.json because every hook event must map to an array"
            )
    return hooks


def _group_uses_owner(group: object) -> bool:
    if not isinstance(group, dict):
        return False
    handlers = group.get("hooks")
    if not isinstance(handlers, list):
        return False
    marker = f"--owner {HOOK_OWNER}"
    return any(
        isinstance(handler, dict)
        and any(
            isinstance(handler.get(field), str) and marker in handler[field]
            for field in ("command", "commandWindows", "command_windows")
        )
        for handler in handlers
    )


def _hook_commands(
    python_path: Path,
    runtime_path: Path,
    runtime_sha256: str,
    core_sha256: str,
) -> tuple[str, str]:
    args = [
        str(python_path),
        str(runtime_path),
        "--owner",
        HOOK_OWNER,
        "--self-sha256",
        runtime_sha256,
        "--core-sha256",
        core_sha256,
    ]
    return " ".join(shlex.quote(part) for part in args), subprocess.list2cmdline(args)


def _owned_hook_group(
    event: str,
    python_path: Path,
    runtime_path: Path,
    runtime_sha256: str,
    core_sha256: str,
) -> dict[str, Any]:
    command, command_windows = _hook_commands(
        python_path, runtime_path, runtime_sha256, core_sha256
    )
    status = (
        "Checking Outcome Integrity admission"
        if event == "PreToolUse"
        else "Recording Outcome Integrity result"
    )
    return {
        "matcher": "*",
        "hooks": [
            {
                "type": "command",
                "command": command,
                "commandWindows": command_windows,
                "timeout": HOOK_TIMEOUT_SECONDS,
                "statusMessage": status,
            }
        ],
    }


def _validate_sidecar(value: dict[str, Any]) -> list[dict[str, Any]]:
    if value.get("schema_version") != HOOK_SIDECAR_VERSION:
        raise ValueError("Refusing an unsupported Outcome Integrity hook ownership sidecar")
    if value.get("owner") != HOOK_OWNER:
        raise ValueError("Refusing a hook ownership sidecar for another owner")
    if not isinstance(value.get("hooks_file_created"), bool):
        raise ValueError("Refusing a hook ownership sidecar without hooks_file_created")
    entries = value.get("entries")
    if not isinstance(entries, list) or len(entries) != len(HOOK_EVENTS):
        raise ValueError("Refusing a hook ownership sidecar with invalid entries")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Refusing a hook ownership sidecar with a non-object entry")
        event = entry.get("event")
        group = entry.get("group")
        if event not in HOOK_EVENTS or event in seen or not isinstance(group, dict):
            raise ValueError("Refusing a hook ownership sidecar with an invalid owned group")
        if not _group_uses_owner(group):
            raise ValueError("Refusing a hook ownership sidecar without the owner marker")
        seen.add(event)
        normalized.append({"event": event, "group": group})
    if seen != set(HOOK_EVENTS):
        raise ValueError("Refusing a hook ownership sidecar missing a hook event")
    return normalized


def _remove_owned_groups(
    hooks: dict[str, list[Any]], previous_entries: list[dict[str, Any]] | None
) -> None:
    previous_by_event = {
        entry["event"]: entry["group"] for entry in (previous_entries or [])
    }
    owner_groups: list[tuple[str, object]] = []
    for event, groups in hooks.items():
        owner_groups.extend((event, group) for group in groups if _group_uses_owner(group))

    if previous_entries is None:
        if owner_groups:
            raise ValueError(
                "Refusing untracked Outcome Integrity hook entries without an ownership sidecar"
            )
        return

    for event in HOOK_EVENTS:
        previous_group = previous_by_event[event]
        exact_count = sum(group == previous_group for group in hooks.get(event, []))
        if exact_count == 0:
            raise ValueError(
                f"Refusing to replace a user-modified owned {event} hook entry"
            )

    for event, group in owner_groups:
        if previous_by_event.get(event) != group:
            raise ValueError(
                f"Refusing to replace a user-modified owned {event} hook entry"
            )

    for event, previous_group in previous_by_event.items():
        hooks[event] = [group for group in hooks[event] if group != previous_group]
        if not hooks[event]:
            del hooks[event]


def _prepare_hook_enable(
    codex_home: Path, skill_source: Path, skill_target: Path
) -> HookPlan:
    warnings = _hook_config_preflight(codex_home)
    runtime_source = skill_source / HOOK_RUNTIME_RELATIVE_PATH
    _require_plain_file(runtime_source, "Outcome Integrity runtime hook")
    runtime_sha256 = _hash_file(runtime_source)
    runtime_target = (skill_target / HOOK_RUNTIME_RELATIVE_PATH).absolute()
    core_source = skill_source / HOOK_CORE_RELATIVE_PATH
    _require_plain_file(core_source, "Outcome Integrity core policy script")
    core_sha256 = _hash_file(core_source)
    core_target = (skill_target / HOOK_CORE_RELATIVE_PATH).absolute()
    python_path = Path(sys.executable).expanduser().resolve()
    _require_plain_file(python_path, "Python interpreter")

    hooks_path = codex_home / "hooks.json"
    sidecar_path = codex_home / HOOK_SIDECAR_NAME
    hooks_existed, hooks_before = _read_plain_bytes(hooks_path, "Codex hooks.json")
    sidecar_existed, sidecar_before = _read_plain_bytes(
        sidecar_path, "Outcome Integrity hook ownership sidecar"
    )
    hooks_document = (
        _load_json_bytes(hooks_before, "hooks.json")
        if hooks_existed
        else {"hooks": {}}
    )
    hooks = _validate_hooks_document(hooks_document)

    previous_entries: list[dict[str, Any]] | None = None
    hooks_file_created = not hooks_existed
    if sidecar_existed:
        sidecar = _load_json_bytes(sidecar_before, "hook ownership sidecar")
        previous_entries = _validate_sidecar(sidecar)
        hooks_file_created = sidecar["hooks_file_created"]
    _remove_owned_groups(hooks, previous_entries)

    entries: list[dict[str, Any]] = []
    for event in HOOK_EVENTS:
        group = _owned_hook_group(
            event,
            python_path,
            runtime_target,
            runtime_sha256,
            core_sha256,
        )
        hooks.setdefault(event, []).append(group)
        entries.append({"event": event, "group": copy.deepcopy(group)})

    sidecar_document = {
        "schema_version": HOOK_SIDECAR_VERSION,
        "owner": HOOK_OWNER,
        "hooks_file_created": hooks_file_created,
        "runtime_path": str(runtime_target),
        "runtime_sha256": runtime_sha256,
        "core_path": str(core_target),
        "core_sha256": core_sha256,
        "entries": entries,
    }
    hooks_after = _render_json_bytes(hooks_document)
    sidecar_after = _render_json_bytes(sidecar_document, sort_keys=True)
    mutations = tuple(
        mutation
        for mutation in (
            FileMutation(
                sidecar_path,
                sidecar_existed,
                sidecar_before,
                sidecar_after,
                "hook ownership sidecar",
            ),
            FileMutation(
                hooks_path,
                hooks_existed,
                hooks_before,
                hooks_after,
                "Codex hooks.json",
            ),
        )
        if not mutation.before_exists or mutation.before_bytes != mutation.after_bytes
    )
    return HookPlan(
        mutations=mutations,
        hooks_path=hooks_path,
        sidecar_path=sidecar_path,
        warnings=tuple(warnings),
        expected_skill_hashes=(
            (HOOK_RUNTIME_RELATIVE_PATH, runtime_sha256),
            (HOOK_CORE_RELATIVE_PATH, core_sha256),
        ),
    )


def _hooks_document_is_otherwise_empty(value: dict[str, Any]) -> bool:
    hooks = value.get("hooks")
    return set(value) <= {"hooks"} and isinstance(hooks, dict) and not hooks


def _prepare_hook_disable(codex_home: Path) -> HookPlan:
    hooks_path = codex_home / "hooks.json"
    sidecar_path = codex_home / HOOK_SIDECAR_NAME
    hooks_existed, hooks_before = _read_plain_bytes(hooks_path, "Codex hooks.json")
    sidecar_existed, sidecar_before = _read_plain_bytes(
        sidecar_path, "Outcome Integrity hook ownership sidecar"
    )
    if not hooks_existed and not sidecar_existed:
        return HookPlan((), hooks_path, sidecar_path, ())
    if not hooks_existed:
        raise ValueError("Refusing hook disable because hooks.json is missing")

    hooks_document = _load_json_bytes(hooks_before, "hooks.json")
    hooks = _validate_hooks_document(hooks_document)
    if not sidecar_existed:
        _remove_owned_groups(hooks, None)
        return HookPlan((), hooks_path, sidecar_path, ())

    sidecar = _load_json_bytes(sidecar_before, "hook ownership sidecar")
    previous_entries = _validate_sidecar(sidecar)
    _remove_owned_groups(hooks, previous_entries)
    hooks_after: bytes | None
    if sidecar["hooks_file_created"] and _hooks_document_is_otherwise_empty(hooks_document):
        hooks_after = None
    else:
        hooks_after = _render_json_bytes(hooks_document)

    mutations = (
        FileMutation(
            hooks_path,
            hooks_existed,
            hooks_before,
            hooks_after,
            "Codex hooks.json",
        ),
        FileMutation(
            sidecar_path,
            True,
            sidecar_before,
            None,
            "hook ownership sidecar",
        ),
    )
    return HookPlan(mutations, hooks_path, sidecar_path, ())


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name != "nt":
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    from ctypes import wintypes

    process_query_limited_information = 0x1000
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if handle:
        kernel32.CloseHandle(handle)
        return True
    return ctypes.get_last_error() == 5


def _lock_is_stale(lock_path: Path, stale_after_seconds: float) -> bool:
    age = max(0.0, time.time() - lock_path.stat().st_mtime)
    if age < stale_after_seconds:
        return False
    owner_path = lock_path / LOCK_OWNER_NAME
    owner_written = False
    try:
        _require_plain_file(owner_path, "install lock owner")
        owner = json.loads(owner_path.read_bytes().decode("utf-8"))
    except (OSError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return True
    if owner.get("hostname") == socket.gethostname():
        try:
            if _pid_is_running(int(owner.get("pid", 0))):
                return False
        except (TypeError, ValueError):
            pass
    return True


def _remove_lock_directory(lock_path: Path) -> None:
    _require_plain_directory(lock_path, "install lock")
    entries = list(lock_path.iterdir())
    if any(entry.name != LOCK_OWNER_NAME for entry in entries):
        raise OSError(f"Refusing to remove an install lock with unexpected contents: {lock_path}")
    for entry in entries:
        _require_plain_file(entry, "install lock owner")
        entry.unlink()
    lock_path.rmdir()


@contextmanager
def install_lock(
    codex_home: Path, *, stale_after_seconds: float = LOCK_STALE_SECONDS
) -> Iterator[None]:
    lock_path = codex_home / LOCK_NAME
    token = uuid.uuid4().hex
    acquired = False
    for _ in range(3):
        try:
            lock_path.mkdir()
            acquired = True
            break
        except FileExistsError:
            _require_plain_directory(lock_path, "install lock")
            if not _lock_is_stale(lock_path, stale_after_seconds):
                raise OSError(f"Another Outcome Integrity installation holds the lock: {lock_path}")
            quarantine = codex_home / f"{LOCK_NAME}.stale.{uuid.uuid4().hex}"
            try:
                os.replace(lock_path, quarantine)
            except FileNotFoundError:
                continue
            _remove_lock_directory(quarantine)
    if not acquired:
        raise OSError(f"Could not acquire the Outcome Integrity install lock: {lock_path}")

    owner_path = lock_path / LOCK_OWNER_NAME
    try:
        owner = {
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "token": token,
            "created_unix": time.time(),
        }
        owner_path.write_bytes((json.dumps(owner, sort_keys=True) + "\n").encode("utf-8"))
        owner_written = True
        yield
    finally:
        if acquired and _path_lexists(lock_path):
            if not owner_written:
                _remove_lock_directory(lock_path)
            else:
                try:
                    recorded = json.loads(owner_path.read_bytes().decode("utf-8"))
                except (OSError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
                    recorded = None
                if isinstance(recorded, dict) and recorded.get("token") == token:
                    _remove_lock_directory(lock_path)


def _replace_path(source: Path, target: Path) -> None:
    os.replace(source, target)


def _remove_generated_path(path: Path) -> None:
    if not _path_lexists(path):
        return
    if _is_reparse_point(path):
        raise OSError(f"Refusing to clean a link-like transaction artifact: {path}")
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def _transactional_install(
    skill_source: Path,
    skill_target: Path,
    agents_path: Path,
    snippet: str | None,
    extra_file_mutations: tuple[FileMutation, ...] = (),
    expected_skill_hashes: tuple[tuple[Path, str], ...] = (),
) -> None:
    token = uuid.uuid4().hex
    target_parent = skill_target.parent
    skill_stage = target_parent / f".{skill_target.name}.stage.{token}"
    skill_backup = target_parent / f".{skill_target.name}.backup.{token}"
    failed_skill = target_parent / f".{skill_target.name}.failed.{token}"

    source_manifest = canonical_tree_manifest(skill_source)
    validate_reusable_skill_tree(skill_source)
    if source_manifest.get("SKILL.md", (None,))[0] != "file":
        raise FileNotFoundError(f"Skill source is incomplete: {skill_source}")

    target_existed = _path_lexists(skill_target)
    if target_existed:
        canonical_tree_manifest(skill_target)

    agents_existed = _path_lexists(agents_path)
    current_agents = b""
    file_mutations: list[FileMutation] = []
    if snippet is not None:
        _require_plain_file(agents_path, "global AGENTS.md", allow_missing=True)
        current_agents = agents_path.read_bytes() if agents_existed else b""
        current_text = current_agents.decode("utf-8")
        merged_text = merge_managed_block(current_text, snippet)
        encoded = merged_text.encode("utf-8")
        if encoded != current_agents:
            file_mutations.append(
                FileMutation(
                    agents_path,
                    agents_existed,
                    current_agents,
                    encoded,
                    "global AGENTS.md",
                )
            )
    file_mutations.extend(extra_file_mutations)

    file_states: list[dict[str, Any]] = []
    for index, mutation in enumerate(file_mutations):
        file_states.append(
            {
                "mutation": mutation,
                "stage": mutation.path.parent
                / f".{mutation.path.name}.stage.{token}.{index}",
                "backup": mutation.path.parent
                / f".{mutation.path.name}.backup.{token}.{index}",
                "activated": False,
            }
        )

    old_skill_moved = False
    new_skill_active = False
    rollback_failed = False
    succeeded = False
    try:
        shutil.copytree(
            skill_source,
            skill_stage,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        staged_manifest = canonical_tree_manifest(skill_stage)
        stable_source_manifest = canonical_tree_manifest(skill_source)
        if staged_manifest != source_manifest or stable_source_manifest != source_manifest:
            raise OSError("Skill source changed during staging or the staged manifest is not exact")
        validate_reusable_skill_tree(skill_stage)
        for relative_path, expected_hash in expected_skill_hashes:
            staged_path = skill_stage / relative_path
            _require_plain_file(staged_path, f"staged bound skill file {relative_path}")
            if _hash_file(staged_path) != expected_hash:
                raise OSError(
                    f"Staged bound skill file changed after hook planning: {relative_path}"
                )

        for state in file_states:
            mutation: FileMutation = state["mutation"]
            stage: Path = state["stage"]
            backup: Path = state["backup"]
            if mutation.after_bytes is not None:
                stage.write_bytes(mutation.after_bytes)
                if stage.read_bytes() != mutation.after_bytes:
                    raise OSError(f"The staged {mutation.label} failed byte verification")
            if mutation.before_exists:
                _require_plain_file(mutation.path, mutation.label)
                if mutation.path.read_bytes() != mutation.before_bytes:
                    raise OSError(f"{mutation.label} changed while its backup was being prepared")
                shutil.copy2(mutation.path, backup, follow_symlinks=False)
                if backup.read_bytes() != mutation.before_bytes:
                    raise OSError(f"The {mutation.label} backup failed byte verification")

        if target_existed:
            canonical_tree_manifest(skill_target)
        for state in file_states:
            mutation = state["mutation"]
            _require_plain_file(mutation.path, mutation.label, allow_missing=True)
            if _path_lexists(mutation.path) != mutation.before_exists:
                raise OSError(f"{mutation.label} changed existence during installation")
            if mutation.before_exists and mutation.path.read_bytes() != mutation.before_bytes:
                raise OSError(f"{mutation.label} changed during installation")

        if target_existed:
            _replace_path(skill_target, skill_backup)
            old_skill_moved = True
        _replace_path(skill_stage, skill_target)
        new_skill_active = True
        for state in file_states:
            mutation = state["mutation"]
            if mutation.after_bytes is None:
                mutation.path.unlink()
            else:
                _replace_path(state["stage"], mutation.path)
            state["activated"] = True
            if mutation.after_bytes is None:
                if _path_lexists(mutation.path):
                    raise OSError(f"{mutation.label} was not removed")
            elif mutation.path.read_bytes() != mutation.after_bytes:
                raise OSError(f"Installed {mutation.label} failed byte verification")

        if canonical_tree_manifest(skill_target) != source_manifest:
            raise OSError("Installed skill manifest does not match the source manifest")
        for relative_path, expected_hash in expected_skill_hashes:
            installed_path = skill_target / relative_path
            _require_plain_file(installed_path, f"installed bound skill file {relative_path}")
            if _hash_file(installed_path) != expected_hash:
                raise OSError(
                    f"Installed bound skill file does not match its hook hash: {relative_path}"
                )
        succeeded = True
    except Exception as exc:
        rollback_errors: list[str] = []
        for state in reversed(file_states):
            if not state["activated"]:
                continue
            mutation = state["mutation"]
            try:
                if mutation.before_exists:
                    _replace_path(state["backup"], mutation.path)
                else:
                    _require_plain_file(mutation.path, mutation.label)
                    mutation.path.unlink()
                state["activated"] = False
            except OSError as rollback_exc:
                rollback_errors.append(f"{mutation.label} rollback failed: {rollback_exc}")
        if new_skill_active:
            try:
                _replace_path(skill_target, failed_skill)
                new_skill_active = False
            except OSError as rollback_exc:
                rollback_errors.append(f"new skill quarantine failed: {rollback_exc}")
        if old_skill_moved and not _path_lexists(skill_target):
            try:
                _replace_path(skill_backup, skill_target)
                old_skill_moved = False
            except OSError as rollback_exc:
                rollback_errors.append(f"previous skill restore failed: {rollback_exc}")
        rollback_failed = bool(rollback_errors)
        if rollback_errors:
            file_backups = ", ".join(str(state["backup"]) for state in file_states)
            locations = f"skill backup={skill_backup}; file backups={file_backups}"
            raise OSError(
                f"Installation failed ({exc}); rollback was incomplete: "
                f"{' | '.join(rollback_errors)}; recovery artifacts: {locations}"
            ) from exc
        raise
    finally:
        cleanup_paths = [skill_stage]
        cleanup_paths.extend(state["stage"] for state in file_states)
        if succeeded or not rollback_failed:
            cleanup_paths.extend([skill_backup, failed_skill])
            cleanup_paths.extend(state["backup"] for state in file_states)
        for path in cleanup_paths:
            try:
                _remove_generated_path(path)
            except OSError:
                pass


def _transactional_file_mutations(mutations: tuple[FileMutation, ...]) -> None:
    if not mutations:
        return
    token = uuid.uuid4().hex
    states: list[dict[str, Any]] = []
    succeeded = False
    rollback_failed = False
    for index, mutation in enumerate(mutations):
        states.append(
            {
                "mutation": mutation,
                "stage": mutation.path.parent
                / f".{mutation.path.name}.stage.{token}.{index}",
                "backup": mutation.path.parent
                / f".{mutation.path.name}.backup.{token}.{index}",
                "activated": False,
            }
        )
    try:
        for state in states:
            mutation: FileMutation = state["mutation"]
            if mutation.after_bytes is not None:
                state["stage"].write_bytes(mutation.after_bytes)
                if state["stage"].read_bytes() != mutation.after_bytes:
                    raise OSError(f"The staged {mutation.label} failed byte verification")
            _require_plain_file(mutation.path, mutation.label, allow_missing=True)
            if _path_lexists(mutation.path) != mutation.before_exists:
                raise OSError(f"{mutation.label} changed existence during hook update")
            if mutation.before_exists:
                if mutation.path.read_bytes() != mutation.before_bytes:
                    raise OSError(f"{mutation.label} changed during hook update")
                shutil.copy2(mutation.path, state["backup"], follow_symlinks=False)
                if state["backup"].read_bytes() != mutation.before_bytes:
                    raise OSError(f"The {mutation.label} backup failed byte verification")

        for state in states:
            mutation = state["mutation"]
            if mutation.after_bytes is None:
                mutation.path.unlink()
            else:
                _replace_path(state["stage"], mutation.path)
            state["activated"] = True
            if mutation.after_bytes is None:
                if _path_lexists(mutation.path):
                    raise OSError(f"{mutation.label} was not removed")
            elif mutation.path.read_bytes() != mutation.after_bytes:
                raise OSError(f"Installed {mutation.label} failed byte verification")
        succeeded = True
    except Exception as exc:
        rollback_errors: list[str] = []
        for state in reversed(states):
            if not state["activated"]:
                continue
            mutation = state["mutation"]
            try:
                if mutation.before_exists:
                    _replace_path(state["backup"], mutation.path)
                else:
                    _require_plain_file(mutation.path, mutation.label)
                    mutation.path.unlink()
                state["activated"] = False
            except OSError as rollback_exc:
                rollback_errors.append(f"{mutation.label} rollback failed: {rollback_exc}")
        rollback_failed = bool(rollback_errors)
        if rollback_errors:
            backups = ", ".join(str(state["backup"]) for state in states)
            raise OSError(
                f"Hook update failed ({exc}); rollback was incomplete: "
                f"{' | '.join(rollback_errors)}; recovery artifacts: {backups}"
            ) from exc
        raise
    finally:
        cleanup_paths = [state["stage"] for state in states]
        if succeeded or not rollback_failed:
            cleanup_paths.extend(state["backup"] for state in states)
        for path in cleanup_paths:
            try:
                _remove_generated_path(path)
            except OSError:
                pass


def install(
    codex_home: Path,
    skip_global_rules: bool = False,
    *,
    enable_user_hooks: bool = False,
    advisory_only: bool = False,
    warnings: list[str] | None = None,
) -> tuple[Path, Path | None]:
    if enable_user_hooks and advisory_only:
        raise ValueError("hook enforcement and advisory-only mode are mutually exclusive")
    repository_root = _repository_root()
    skill_source = repository_root / "skills" / "outcome-integrity"
    snippet_path = repository_root / "global" / "AGENTS.snippet.md"
    codex_home = codex_home.expanduser().resolve()
    skill_target = codex_home / "skills" / "outcome-integrity"
    agents_path = codex_home / "AGENTS.md"

    _require_plain_directory(skill_source, "skill source")
    validate_reusable_skill_tree(skill_source)
    _require_disjoint_trees(skill_source, skill_target)
    snippet: str | None = None
    if not skip_global_rules:
        _require_plain_file(snippet_path, "global rule snippet")
        snippet = snippet_path.read_bytes().decode("utf-8")
        _render_managed_block(snippet, "\n")

    codex_home_existed = _path_lexists(codex_home)
    _require_plain_directory(codex_home, "Codex home", allow_missing=True)
    codex_home.mkdir(parents=True, exist_ok=True)
    try:
        with install_lock(codex_home):
            sidecar_path = codex_home / HOOK_SIDECAR_NAME
            persisted_hook_opt_in = (
                not enable_user_hooks
                and not advisory_only
                and _path_lexists(sidecar_path)
            )
            if advisory_only:
                hook_plan = _prepare_hook_disable(codex_home)
            elif enable_user_hooks or persisted_hook_opt_in:
                hook_plan = _prepare_hook_enable(
                    codex_home, skill_source, skill_target
                )
            else:
                hook_plan = HookPlan(
                    (), codex_home / "hooks.json", sidecar_path, ()
                )
            skills_directory = skill_target.parent
            skills_directory_existed = _path_lexists(skills_directory)
            _require_plain_directory(
                skills_directory, "skills directory", allow_missing=True
            )
            skills_directory.mkdir(parents=True, exist_ok=True)
            try:
                _transactional_install(
                    skill_source,
                    skill_target,
                    agents_path,
                    snippet,
                    hook_plan.mutations,
                    hook_plan.expected_skill_hashes,
                )
            except Exception:
                if not skills_directory_existed and _path_lexists(skills_directory):
                    try:
                        _require_plain_directory(skills_directory, "created skills directory")
                        skills_directory.rmdir()
                    except (OSError, ValueError):
                        pass
                raise
            if warnings is not None:
                warnings.extend(hook_plan.warnings)
                if persisted_hook_opt_in and any(
                    mutation.path == hook_plan.hooks_path
                    for mutation in hook_plan.mutations
                ):
                    warnings.append(
                        "Existing Outcome Integrity user-hook commands were upgraded. "
                        "Open /hooks, review the changed commands, and renew trust before "
                        "relying on enforcement."
                    )
    except Exception:
        if not codex_home_existed and _path_lexists(codex_home):
            try:
                _require_plain_directory(codex_home, "created Codex home")
                codex_home.rmdir()
            except (OSError, ValueError):
                pass
        raise

    return skill_target, None if skip_global_rules else agents_path


def disable_user_hooks(
    codex_home: Path, *, warnings: list[str] | None = None
) -> bool:
    codex_home = codex_home.expanduser().resolve()
    _require_plain_directory(codex_home, "Codex home", allow_missing=True)
    if not _path_lexists(codex_home):
        return False
    with install_lock(codex_home):
        plan = _prepare_hook_disable(codex_home)
        _transactional_file_mutations(plan.mutations)
        if warnings is not None:
            warnings.extend(plan.warnings)
        return bool(plan.mutations)


def inspect_hook_health(codex_home: Path) -> dict[str, Any]:
    """Inspect configured parity without claiming that Codex trusted or dispatched it."""
    codex_home = codex_home.expanduser().resolve()
    hooks_path = codex_home / "hooks.json"
    sidecar_path = codex_home / HOOK_SIDECAR_NAME
    result: dict[str, Any] = {
        "state": "absent",
        "configured_exact": False,
        "source_exact": False,
        "active_verified": False,
        "trust": "unverified",
        "hooks_path": str(hooks_path),
        "sidecar_path": str(sidecar_path),
        "definition_fingerprint": None,
        "warnings": [],
        "errors": [],
    }
    hooks_exists = _path_lexists(hooks_path)
    sidecar_exists = _path_lexists(sidecar_path)
    if not hooks_exists and not sidecar_exists:
        return result
    if hooks_exists != sidecar_exists:
        result["state"] = "configured-stale"
        result["errors"].append(
            "hooks.json and the Outcome Integrity ownership sidecar must both exist"
        )
        return result
    try:
        _, hooks_raw = _read_plain_bytes(hooks_path, "Codex hooks.json")
        _, sidecar_raw = _read_plain_bytes(
            sidecar_path, "Outcome Integrity hook ownership sidecar"
        )
        hooks_document = _load_json_bytes(hooks_raw, "hooks.json")
        hooks = _validate_hooks_document(hooks_document)
        sidecar = _load_json_bytes(sidecar_raw, "hook ownership sidecar")
        entries = _validate_sidecar(sidecar)
        expected_by_event = {
            entry["event"]: entry["group"] for entry in entries
        }
        for event in HOOK_EVENTS:
            owned = [
                group for group in hooks.get(event, []) if _group_uses_owner(group)
            ]
            if owned != [expected_by_event[event]]:
                raise ValueError(
                    f"Configured {event} owner group does not exactly match its sidecar"
                )
        runtime_path = Path(str(sidecar.get("runtime_path", "")))
        core_path = Path(str(sidecar.get("core_path", "")))
        if not runtime_path.is_absolute() or not core_path.is_absolute():
            raise ValueError("Hook sidecar runtime and core paths must be absolute")
        _require_plain_file(runtime_path, "installed Outcome Integrity hook runtime")
        _require_plain_file(core_path, "installed Outcome Integrity hook core")
        installed_runtime_sha256 = _hash_file(runtime_path)
        installed_core_sha256 = _hash_file(core_path)
        if installed_runtime_sha256 != sidecar.get("runtime_sha256"):
            raise ValueError("Installed hook runtime hash differs from its configured hash")
        if installed_core_sha256 != sidecar.get("core_sha256"):
            raise ValueError("Installed hook core hash differs from its configured hash")
        source_skill = _repository_root() / "skills" / "outcome-integrity"
        source_runtime = source_skill / HOOK_RUNTIME_RELATIVE_PATH
        source_core = source_skill / HOOK_CORE_RELATIVE_PATH
        _require_plain_file(source_runtime, "source Outcome Integrity hook runtime")
        _require_plain_file(source_core, "source Outcome Integrity hook core")
        if installed_runtime_sha256 != _hash_file(source_runtime):
            raise ValueError(
                "Installed hook runtime differs from this installer package"
            )
        if installed_core_sha256 != _hash_file(source_core):
            raise ValueError("Installed hook core differs from this installer package")
        warnings = _hook_config_preflight(codex_home)
        result["warnings"] = warnings
        result["definition_fingerprint"] = "sha256:" + hashlib.sha256(
            json.dumps(
                {
                    "entries": entries,
                    "runtime_sha256": sidecar.get("runtime_sha256"),
                    "core_sha256": sidecar.get("core_sha256"),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        result["configured_exact"] = True
        result["source_exact"] = True
        if warnings:
            result["state"] = "configured-disabled"
            return result
        result["state"] = "configured-exact-trust-unverified"
        return result
    except (OSError, ValueError, UnicodeError) as exc:
        result["state"] = "configured-stale"
        result["errors"].append(str(exc))
        return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--codex-home",
        type=Path,
        default=default_codex_home(),
        help="Codex home directory; defaults to CODEX_HOME or ~/.codex",
    )
    parser.add_argument(
        "--skip-global-rules",
        action="store_true",
        help="Install the skill without updating the global AGENTS.md file",
    )
    hook_group = parser.add_mutually_exclusive_group()
    hook_group.add_argument(
        "--enable-user-hooks",
        action="store_true",
        help=(
            "Opt in to synchronous user-level PreToolUse and PostToolUse hooks; "
            "manual /hooks review is still required"
        ),
    )
    hook_group.add_argument(
        "--disable-user-hooks",
        action="store_true",
        help="Remove only hook entries owned by Outcome Integrity",
    )
    hook_group.add_argument(
        "--advisory-only",
        action="store_true",
        help=(
            "Atomically install the current skill and global rules while removing "
            "only Outcome Integrity-owned user hooks"
        ),
    )
    hook_group.add_argument(
        "--hook-health",
        action="store_true",
        help=(
            "Inspect hook files, policy, and hashes without claiming live trust or dispatch"
        ),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    warnings: list[str] = []
    if (args.disable_user_hooks or args.hook_health) and args.skip_global_rules:
        print(
            "Installation failed: --skip-global-rules does not apply to hook status or disable",
            file=sys.stderr,
        )
        return 1
    try:
        if args.hook_health:
            health = inspect_hook_health(args.codex_home)
            print(json.dumps(health, indent=2, sort_keys=True))
            return 0 if health["configured_exact"] else 1
        if args.disable_user_hooks:
            changed = disable_user_hooks(args.codex_home, warnings=warnings)
        else:
            skill_path, agents_path = install(
                args.codex_home,
                args.skip_global_rules,
                enable_user_hooks=args.enable_user_hooks,
                advisory_only=args.advisory_only,
                warnings=warnings,
            )
    except (OSError, ValueError, UnicodeError) as exc:
        print(f"Installation failed: {exc}", file=sys.stderr)
        return 1

    for warning in warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    if args.disable_user_hooks:
        if changed:
            print("Disabled Outcome Integrity user hooks; skill and global rules unchanged.")
        else:
            print("Outcome Integrity user hooks were not enabled; nothing changed.")
        return 0

    print(f"Installed skill: {skill_path}")
    if agents_path:
        print(f"Updated global rules: {agents_path}")
    else:
        print("Global rules unchanged")
    if args.enable_user_hooks:
        hooks_path = args.codex_home.expanduser().resolve() / "hooks.json"
        print(f"Configured user hooks: {hooks_path}")
        print(
            "User hooks are not trusted automatically. Open /hooks, review the exact "
            "commands, and trust them before relying on enforcement."
        )
    elif args.advisory_only:
        print("Advisory-only mode: Outcome Integrity user hooks removed.")
    print("Start a new Codex task to load the updated skill and rules.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
