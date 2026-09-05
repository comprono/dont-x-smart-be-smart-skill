from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Any, TextIO


OWNER = "outcome-integrity-v1"
PRE_TOOL_USE = "PreToolUse"
POST_TOOL_USE = "PostToolUse"
SHELL_TOOL_NAMES = {"Bash", "bash", "exec_command", "functions.exec_command"}
STATE_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "project_outcome.py"
PROJECT_FILES = (
    Path(".codex") / "PROJECT_OUTCOME.md",
    Path(".codex") / "ACCEPTANCE.json",
)
CONTROL_COMMANDS = {
    "attempt-begin",
    "attempt-finish",
    "candidate-bind",
    "completion",
    "control-status",
    "hook-post-observe",
    "hook-pre-claim",
    "path",
    "resume",
    "scope-fingerprint",
    "state-reconcile",
    "state-transition",
    "failure-fingerprint-migrate",
    "limit-extend",
    "validate",
}
ACTIVATION_COMMANDS = {
    "resume",
    "attempt-begin",
    "state-reconcile",
    "state-transition",
    "failure-fingerprint-migrate",
    "limit-extend",
}
ACTIVATION_REQUEST_INPUTS = {
    "attempt-begin": Path(".codex") / "ATTEMPT_REQUEST.json",
    "state-reconcile": Path(".codex") / "ATTEMPT_REQUEST.json",
    "state-transition": Path(".codex") / "STATE_TRANSITION_REQUEST.json",
    "failure-fingerprint-migrate": Path(".codex") / "FAILURE_FINGERPRINT_MIGRATION_REQUEST.json",
    "limit-extend": Path(".codex") / "LIMIT_EXTENSION_REQUEST.json",
}
BOOTSTRAP_CONTROL_INPUTS = (
    Path(".codex") / "ATTEMPT_REQUEST.json",
    Path(".codex") / "ATTEMPT_RESULT.json",
    Path(".codex") / "STATE_TRANSITION_REQUEST.json",
    Path(".codex") / "FAILURE_FINGERPRINT_MIGRATION_REQUEST.json",
    Path(".codex") / "LIMIT_EXTENSION_REQUEST.json",
)
AUTHORITATIVE_STATE_FILES = (
    Path(".codex") / "ACCEPTANCE.json",
    Path(".codex") / "PROJECT_OUTCOME.md",
)
_SHA256_PATTERN = re.compile(r"(?:sha256:)?([0-9a-fA-F]{64})\Z")
_codex_home = os.environ.get("CODEX_HOME")
REGISTRY_DIRECTORY = (
    Path(_codex_home).expanduser() if _codex_home else Path.home() / ".codex"
) / "outcome-integrity" / "session-roots-v2"
SESSION_REGISTRY_VERSION = 2
SESSION_BINDING_KIND = "explicit-activation"
SESSION_ID_MAX_LENGTH = 512


def _json_line(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n"


def _write_json(stdout: TextIO, value: dict[str, Any]) -> None:
    stdout.write(_json_line(value))
    stdout.flush()


def _pre_denial(reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": PRE_TOOL_USE,
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def _post_block(reason: str) -> dict[str, Any]:
    return {
        "decision": "block",
        "reason": reason,
        "hookSpecificOutput": {
            "hookEventName": POST_TOOL_USE,
            "additionalContext": reason,
        },
    }


def _event_name(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get("hook_event_name", payload.get("hookEventName"))
    return value if value in {PRE_TOOL_USE, POST_TOOL_USE} else None


def _host_cwd(payload: object) -> Path:
    value = payload.get("cwd") if isinstance(payload, dict) else None
    raw = value if isinstance(value, str) and value.strip() else os.getcwd()
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve(strict=False)


def find_project_root(cwd: str | Path) -> Path | None:
    current = Path(cwd).expanduser()
    if not current.is_absolute():
        current = Path.cwd() / current
    current = current.resolve(strict=False)
    if current.exists() and current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if all((candidate / marker).is_file() for marker in PROJECT_FILES):
            return candidate
    return None


def _path_key(path: Path) -> str:
    return os.path.normcase(str(path.resolve(strict=False)))


def _deduplicate_paths(paths: list[Path]) -> list[Path]:
    unique: dict[str, Path] = {}
    for path in paths:
        unique.setdefault(_path_key(path), path.resolve(strict=False))
    return list(unique.values())


def _is_link_directory(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        return bool(is_junction()) if callable(is_junction) else False
    except OSError:
        return True


def _valid_session_id(payload: object) -> str | None:
    value = payload.get("session_id") if isinstance(payload, dict) else None
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized or len(normalized) > SESSION_ID_MAX_LENGTH:
        return None
    return normalized


def _session_hash(session_id: str) -> str:
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()


def _registry_path(session_id: str) -> Path:
    return REGISTRY_DIRECTORY / (_session_hash(session_id) + ".json")


def _path_has_link_component(path: Path) -> bool:
    absolute = path.expanduser()
    if not absolute.is_absolute():
        absolute = Path.cwd() / absolute
    for candidate in (absolute, *absolute.parents):
        if _is_link_directory(candidate):
            return True
    return False


def _validate_bound_root(root: Path) -> str | None:
    if not root.is_absolute():
        return "Outcome Integrity session registry contains a non-absolute root."
    if _path_has_link_component(root):
        return "Outcome Integrity refuses a session root reached through a link or junction."
    if not all((root / marker).is_file() for marker in PROJECT_FILES):
        return "Outcome Integrity session root is stale or no longer initialized."
    return None


def _read_session_root(
    session_id: str | None,
) -> tuple[Path | None, str | None, bool]:
    if session_id is None:
        return None, None, False
    path = _registry_path(session_id)
    if not path.exists() and not path.is_symlink():
        return None, None, False
    if path.is_symlink() or _path_has_link_component(path.parent):
        return None, "Outcome Integrity session registry is link-unsafe.", True
    try:
        if path.stat().st_size > 4096:
            raise ValueError("registry entry is oversized")
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None, "Outcome Integrity session registry entry is invalid.", True
    expected_hash = _session_hash(session_id)
    if (
        not isinstance(value, dict)
        or value.get("version") != SESSION_REGISTRY_VERSION
        or value.get("binding_kind") != SESSION_BINDING_KIND
    ):
        return None, "Outcome Integrity session registry entry is invalid.", True
    if value.get("owner") != OWNER or value.get("session_hash") != expected_hash:
        return None, "Outcome Integrity session registry identity does not match.", True
    raw_root = value.get("root")
    if not isinstance(raw_root, str):
        return None, "Outcome Integrity session registry root is invalid.", True
    root = Path(raw_root).expanduser()
    error = _validate_bound_root(root)
    if error is not None:
        return None, error, True
    return root.resolve(strict=False), None, True


def _bind_session_root(session_id: str | None, root: Path) -> str | None:
    if session_id is None:
        return "Outcome Integrity cannot persist a project root without a valid host session ID."
    root = root.resolve(strict=False)
    root_error = _validate_bound_root(root)
    if root_error is not None:
        return root_error
    try:
        REGISTRY_DIRECTORY.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError:
        return "Outcome Integrity could not create its session registry."
    if _path_has_link_component(REGISTRY_DIRECTORY):
        return "Outcome Integrity session registry is link-unsafe."
    existing, error, present = _read_session_root(session_id)
    if present:
        if error is not None:
            return error
        if existing is None or not _same_path(existing, root):
            return (
                "Outcome Integrity session is already bound to another project root; "
                "chat text and tool arguments cannot rebind it, so start a fresh task "
                "at the intended root."
            )
        return None
    path = _registry_path(session_id)
    payload = _json_line(
        {
            "version": SESSION_REGISTRY_VERSION,
            "binding_kind": SESSION_BINDING_KIND,
            "owner": OWNER,
            "session_hash": _session_hash(session_id),
            "root": str(root),
        }
    ).encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        existing, error, present = _read_session_root(session_id)
        if error is not None:
            return error
        if not present or existing is None or not _same_path(existing, root):
            return (
                "Outcome Integrity session is already bound to another project root; "
                "chat text and tool arguments cannot rebind it, so start a fresh task "
                "at the intended root."
            )
        return None
    except OSError:
        return "Outcome Integrity could not reserve its session registry entry."
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        return "Outcome Integrity could not persist its session root binding."
    return None


def _field_path_strings(value: object, field_names: set[str]) -> list[str]:
    if isinstance(value, dict):
        paths: list[str] = []
        for key, item in value.items():
            if key.casefold() in field_names:
                if isinstance(item, str) and item.strip():
                    paths.append(item)
                elif isinstance(item, list):
                    paths.extend(
                        entry for entry in item if isinstance(entry, str) and entry.strip()
                    )
            if isinstance(item, (dict, list)):
                paths.extend(_field_path_strings(item, field_names))
        return paths
    if isinstance(value, list):
        paths = []
        for item in value:
            paths.extend(_field_path_strings(item, field_names))
        return paths
    return []


def _absolute_tool_path(value: str, base: Path) -> Path:
    path = Path(value.strip()).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve(strict=False)


def _patch_header_targets(value: object) -> list[str]:
    targets: list[str] = []
    for source in _patch_sources(value):
        targets.extend(
            match.group(1).strip()
            for match in re.finditer(
                r"(?m)^\*\*\* (?:(?:Add|Update|Delete) File:|Move to:) (.+?)\s*$",
                source,
            )
        )
    return targets


def resolve_project_context(
    payload: object,
) -> tuple[Path | None, Path, list[Path], str | None, Path | None]:
    """Resolve one initialized root from execution context and concrete targets."""
    host_cwd = _host_cwd(payload)
    tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
    declared_cwds = _deduplicate_paths(
        [
            _absolute_tool_path(value, host_cwd)
            for value in _field_path_strings(tool_input, {"workdir", "cwd"})
        ]
    )
    target_bases = declared_cwds or [host_cwd]
    direct_targets: list[Path] = []
    for value in _field_path_strings(tool_input, {"path"}):
        direct_targets.extend(_absolute_tool_path(value, base) for base in target_bases)
    for value in _patch_header_targets(tool_input):
        direct_targets.extend(_absolute_tool_path(value, base) for base in target_bases)
    direct_targets = _deduplicate_paths(direct_targets)

    effective_cwd = declared_cwds[0] if len(declared_cwds) == 1 else host_cwd
    activation_root = (
        _exact_activation_root(payload, effective_cwd)
        if isinstance(payload, dict)
        else None
    )
    explicit_paths = [*declared_cwds, *direct_targets]
    explicit_roots = _deduplicate_paths(
        [root for path in explicit_paths if (root := find_project_root(path)) is not None]
    )
    if activation_root is not None and all(
        (activation_root / marker).is_file() for marker in PROJECT_FILES
    ):
        explicit_roots = _deduplicate_paths([*explicit_roots, activation_root])
    host_root = find_project_root(host_cwd)
    session_id = _valid_session_id(payload)
    bound_root, registry_error, _ = _read_session_root(session_id)
    if registry_error is not None:
        return None, effective_cwd, direct_targets, registry_error, None
    initialized_context = bool(explicit_roots or host_root or bound_root)
    if len(declared_cwds) > 1 and initialized_context:
        return (
            None,
            host_cwd,
            direct_targets,
            "Outcome Integrity found ambiguous tool working directories.",
            None,
        )
    if len(explicit_roots) > 1:
        return (
            None,
            effective_cwd,
            direct_targets,
            "Outcome Integrity found targets in multiple initialized project roots.",
            None,
        )
    explicit_root = explicit_roots[0] if explicit_roots else None
    if bound_root is not None and explicit_root is not None and not _same_path(
        bound_root, explicit_root
    ):
        return (
            None,
            effective_cwd,
            direct_targets,
            "Outcome Integrity session target conflicts with its bound project root; chat text and tool arguments cannot rebind it, so start a fresh task at the intended root.",
            None,
        )
    if bound_root is not None and host_root is not None and not _same_path(
        bound_root, host_root
    ):
        try:
            bound_is_nested = bound_root.is_relative_to(host_root)
        except ValueError:
            bound_is_nested = False
        if not bound_is_nested:
            return (
                None,
                effective_cwd,
                direct_targets,
                "Outcome Integrity session cwd conflicts with its bound project root; start a fresh task at the intended root.",
                None,
            )
    if bound_root is not None:
        return bound_root, effective_cwd, direct_targets, None, None
    if explicit_roots:
        bind_root = (
            explicit_root
            if activation_root is not None
            and explicit_root is not None
            and _same_path(activation_root, explicit_root)
            else None
        )
        return explicit_root, effective_cwd, direct_targets, None, bind_root
    if host_root is not None:
        return host_root, effective_cwd, direct_targets, None, None
    return None, effective_cwd, direct_targets, None, None


def _parse_args(argv: list[str]) -> tuple[str | None, str | None, str | None]:
    owner: str | None = None
    expected_sha256: str | None = None
    expected_core_sha256: str | None = None
    index = 0
    while index < len(argv):
        item = argv[index]
        if item == "--owner" and index + 1 < len(argv):
            owner = argv[index + 1]
            index += 2
        elif item == "--self-sha256" and index + 1 < len(argv):
            expected_sha256 = argv[index + 1]
            index += 2
        elif item == "--core-sha256" and index + 1 < len(argv):
            expected_core_sha256 = argv[index + 1]
            index += 2
        else:
            return None, None, None
    return owner, expected_sha256, expected_core_sha256


def _verify_file(path: Path, expected_sha256: str | None) -> bool:
    if not isinstance(expected_sha256, str):
        return False
    match = _SHA256_PATTERN.fullmatch(expected_sha256.strip())
    if match is None:
        return False
    try:
        actual = hashlib.sha256(path.resolve().read_bytes()).hexdigest()
    except OSError:
        return False
    return hmac.compare_digest(actual, match.group(1).lower())


def _verify_integrity(
    owner: str | None,
    expected_sha256: str | None,
    expected_core_sha256: str | None,
) -> bool:
    return (
        owner == OWNER
        and _verify_file(Path(__file__), expected_sha256)
        and _verify_file(STATE_SCRIPT, expected_core_sha256)
    )


def _load_state_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "outcome_integrity_hook_state", STATE_SCRIPT
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Outcome Integrity state module is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _strip_token_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left.resolve(strict=False))) == os.path.normcase(
        str(right.resolve(strict=False))
    )


def _control_plane_invocation(
    payload: dict[str, Any], effective_cwd: Path
) -> tuple[str, Path, Path, list[str]] | None:
    if payload.get("tool_name") not in SHELL_TOOL_NAMES:
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    command = tool_input.get("command", tool_input.get("cmd"))
    if not isinstance(command, str) or not command.strip():
        return None
    if any(character in command for character in "\r\n;&|><"):
        return None
    try:
        tokens = [_strip_token_quotes(item) for item in shlex.split(command, posix=False)]
    except ValueError:
        return None
    if len(tokens) < 5:
        return None
    interpreter = Path(tokens[0]).expanduser()
    if not interpreter.is_absolute() or not _same_path(interpreter, Path(sys.executable)):
        return None
    script = Path(tokens[1]).expanduser()
    if not script.is_absolute():
        script = effective_cwd / script
    if not _same_path(script, STATE_SCRIPT):
        return None
    if tokens[2] not in CONTROL_COMMANDS:
        return None
    root_positions = [index for index, value in enumerate(tokens) if value == "--root"]
    if len(root_positions) != 1 or root_positions[0] + 1 >= len(tokens):
        return None
    requested_root = Path(tokens[root_positions[0] + 1]).expanduser()
    if not requested_root.is_absolute():
        requested_root = effective_cwd / requested_root
    return (
        tokens[2],
        requested_root.resolve(strict=False),
        requested_root,
        tokens,
    )


def _is_control_plane_call(
    root: Path, payload: dict[str, Any], effective_cwd: Path
) -> bool:
    invocation = _control_plane_invocation(payload, effective_cwd)
    return invocation is not None and _same_path(invocation[1], root)


def _exact_activation_root(
    payload: dict[str, Any], effective_cwd: Path
) -> Path | None:
    invocation = _control_plane_invocation(payload, effective_cwd)
    if invocation is None:
        return None
    command, root, lexical_root, tokens = invocation
    if command not in ACTIVATION_COMMANDS or _path_has_link_component(lexical_root):
        return None
    options: dict[str, str] = {}
    flags: set[str] = set()
    index = 3
    while index < len(tokens):
        token = tokens[index]
        if token == "--json":
            if token in flags:
                return None
            flags.add(token)
            index += 1
            continue
        if token not in {"--root", "--request", "--expected-revision"}:
            return None
        if token in options or index + 1 >= len(tokens):
            return None
        options[token] = tokens[index + 1]
        index += 2
    if "--root" not in options:
        return None
    if command == "resume":
        if set(options) != {"--root"}:
            return None
    else:
        if set(options) != {"--root", "--request", "--expected-revision"}:
            return None
        try:
            if int(options["--expected-revision"]) < 0:
                return None
        except ValueError:
            return None
        request_path = Path(options["--request"]).expanduser()
        if not request_path.is_absolute():
            request_path = effective_cwd / request_path
        expected_relative = ACTIVATION_REQUEST_INPUTS.get(command)
        if expected_relative is None:
            return None
        expected_request = root / expected_relative
        if _path_has_link_component(request_path) or not _same_path(
            request_path, expected_request
        ):
            return None
    return root


def _patch_sources(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        sources: list[str] = []
        for key in sorted(value):
            sources.extend(_patch_sources(value[key]))
        return sources
    if isinstance(value, list):
        sources = []
        for item in value:
            sources.extend(_patch_sources(item))
        return sources
    return []


def _is_bootstrap_control_patch(
    root: Path, payload: dict[str, Any], effective_cwd: Path
) -> bool:
    if payload.get("tool_name") not in {"apply_patch", "functions.apply_patch"}:
        return False
    raw_targets = _patch_header_targets(payload.get("tool_input"))
    if not raw_targets:
        return False
    allowed = [root / relative for relative in BOOTSTRAP_CONTROL_INPUTS]
    for raw_target in raw_targets:
        normalized = raw_target.replace("\\", "/")
        declared = Path(normalized)
        if ".." in declared.parts:
            return False
        candidate = declared if declared.is_absolute() else effective_cwd / declared
        if candidate.is_symlink() or candidate.parent.is_symlink():
            return False
        if not any(_same_path(candidate, expected) for expected in allowed):
            return False
    return True


def _directly_targets_authoritative_state(
    root: Path, payload: dict[str, Any], direct_targets: list[Path]
) -> bool:
    protected = [root / relative for relative in AUTHORITATIVE_STATE_FILES]
    if any(
        _same_path(target, protected_path)
        for target in direct_targets
        for protected_path in protected
    ):
        return True
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return False
    command_values = _field_path_strings(tool_input, {"command", "cmd", "chars"})
    protected_fragments = {
        relative.as_posix().casefold() for relative in AUTHORITATIVE_STATE_FILES
    }
    for command in command_values:
        normalized = command.replace("\\", "/").casefold()
        if any(fragment in normalized for fragment in protected_fragments):
            return True
    return False


def _targets_any_authoritative_state(
    payload: dict[str, Any], direct_targets: list[Path]
) -> bool:
    """Detect protected ledger targets even when root resolution is ambiguous."""
    protected_suffixes = {
        tuple(part.casefold() for part in relative.parts)
        for relative in AUTHORITATIVE_STATE_FILES
    }
    for target in direct_targets:
        folded_parts = tuple(part.casefold() for part in target.parts)
        if any(
            len(folded_parts) >= len(suffix)
            and folded_parts[-len(suffix) :] == suffix
            for suffix in protected_suffixes
        ):
            return True
    tool_input = payload.get("tool_input")
    command_values = _field_path_strings(tool_input, {"command", "cmd", "chars"})
    fragments = {
        relative.as_posix().casefold() for relative in AUTHORITATIVE_STATE_FILES
    }
    return any(
        fragment in command.replace("\\", "/").casefold()
        for command in command_values
        for fragment in fragments
    )


def _core_payload(payload: dict[str, Any], cwd: Path) -> dict[str, Any]:
    return {
        "tool_use_id": payload.get("tool_use_id"),
        "tool_name": payload.get("tool_name"),
        "cwd": str(cwd),
        "tool_input": payload.get("tool_input"),
    }


def _post_outcome(payload: dict[str, Any]) -> str:
    explicit = payload.get("outcome")
    if explicit in {"completed", "failed", "aborted"}:
        return explicit
    response = payload.get("tool_response")
    if isinstance(response, dict):
        status = response.get("status")
        if isinstance(status, str):
            normalized = status.casefold()
            if normalized in {"aborted", "cancelled", "canceled", "interrupted"}:
                return "aborted"
            if normalized in {"error", "failed", "failure"}:
                return "failed"
        if response.get("isError") is True or response.get("is_error") is True:
            return "failed"
        for field in ("exitCode", "exit_code"):
            value = response.get(field)
            if isinstance(value, int) and not isinstance(value, bool) and value != 0:
                return "failed"
    return "completed"


def _post_payload(payload: dict[str, Any], cwd: Path) -> dict[str, Any]:
    sanitized = _core_payload(payload, cwd)
    sanitized["outcome"] = _post_outcome(payload)
    duration = payload.get("duration_seconds")
    if isinstance(duration, (int, float)) and not isinstance(duration, bool) and duration >= 0:
        sanitized["duration_seconds"] = duration
    return sanitized


def _safe_reason(result: object, fallback: str) -> str:
    if isinstance(result, dict):
        errors = result.get("errors")
        if isinstance(errors, list):
            clean = [
                " ".join(item.split())
                for item in errors
                if isinstance(item, str) and item.strip()
            ]
            if clean:
                return "; ".join(clean)[:1200]
    return fallback


def _handle_pre(
    root: Path,
    effective_cwd: Path,
    direct_targets: list[Path],
    payload: dict[str, Any],
    state: Any,
    stdout: TextIO,
) -> int:
    if _is_control_plane_call(root, payload, effective_cwd) or _is_bootstrap_control_patch(
        root, payload, effective_cwd
    ):
        return 0
    if _directly_targets_authoritative_state(root, payload, direct_targets):
        _write_json(
            stdout,
            _pre_denial(
                "Direct mutation of Outcome Integrity authoritative state is denied; use the exact state-reconcile control plane."
            ),
        )
        return 0
    core_payload = _core_payload(payload, effective_cwd)
    if state.hook_requires_claim_for_root(root, core_payload) is False:
        return 0
    result = state.hook_pre_claim(root, core_payload)
    if (
        isinstance(result, dict)
        and result.get("decision") in {"allow", "bypass"}
        and result.get("ok") is True
    ):
        return 0
    reason = _safe_reason(result, "Outcome Integrity denied this tool call.")
    _write_json(stdout, _pre_denial(reason))
    return 0


def _handle_post(
    root: Path,
    effective_cwd: Path,
    direct_targets: list[Path],
    payload: dict[str, Any],
    state: Any,
    stdout: TextIO,
) -> int:
    if _is_control_plane_call(root, payload, effective_cwd) or _is_bootstrap_control_patch(
        root, payload, effective_cwd
    ):
        return 0
    if _directly_targets_authoritative_state(root, payload, direct_targets):
        reason = (
            "A tool directly targeted Outcome Integrity authoritative state outside the exact state-reconcile control plane; stop and recover authoritative state."
        )
        _write_json(stdout, _post_block(reason))
        return 0
    core_payload = _post_payload(payload, effective_cwd)
    if state.hook_requires_claim_for_root(root, core_payload, post=True) is False:
        return 0
    result = state.hook_post_observe(root, core_payload)
    if (
        isinstance(result, dict)
        and result.get("decision") in {"observed", "bypass"}
        and result.get("ok") is True
    ):
        return 0
    reason = _safe_reason(
        result,
        "Outcome Integrity could not reconcile the completed tool call; stop and recover authoritative state.",
    )
    _write_json(stdout, _post_block(reason))
    return 0


def main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    input_stream = sys.stdin if stdin is None else stdin
    output_stream = sys.stdout if stdout is None else stdout
    try:
        payload = json.load(input_stream)
    except Exception:
        payload = None

    (
        root,
        effective_cwd,
        direct_targets,
        resolution_error,
        binding_root,
    ) = resolve_project_context(payload)
    if root is None and resolution_error is None:
        return 0

    event = _event_name(payload)
    failure_output = _post_block if event == POST_TOOL_USE else _pre_denial
    owner, expected_sha256, expected_core_sha256 = _parse_args(arguments)
    if not _verify_integrity(owner, expected_sha256, expected_core_sha256):
        _write_json(
            output_stream,
            failure_output("Outcome Integrity hook integrity verification failed."),
        )
        return 0
    if not isinstance(payload, dict) or event not in {PRE_TOOL_USE, POST_TOOL_USE}:
        _write_json(
            output_stream,
            failure_output("Outcome Integrity received an invalid hook payload."),
        )
        return 0
    if binding_root is not None and event == PRE_TOOL_USE:
        binding_error = _bind_session_root(_valid_session_id(payload), binding_root)
        if binding_error is not None:
            _write_json(output_stream, _pre_denial(binding_error))
            return 0

    try:
        state = _load_state_module()
        if resolution_error is not None:
            core_payload = (
                _post_payload(payload, effective_cwd)
                if event == POST_TOOL_USE
                else _core_payload(payload, effective_cwd)
            )
            protected_call = bool(
                _control_plane_invocation(payload, effective_cwd)
                or _targets_any_authoritative_state(payload, direct_targets)
                or state.hook_requires_claim(core_payload)
            )
            if protected_call:
                _write_json(output_stream, failure_output(resolution_error))
            return 0
        if event == PRE_TOOL_USE:
            return _handle_pre(
                root,
                effective_cwd,
                direct_targets,
                payload,
                state,
                output_stream,
            )
        return _handle_post(
            root,
            effective_cwd,
            direct_targets,
            payload,
            state,
            output_stream,
        )
    except Exception:
        reason = "Outcome Integrity hook failed closed before policy reconciliation."
        _write_json(output_stream, failure_output(reason))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
