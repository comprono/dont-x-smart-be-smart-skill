#!/usr/bin/env python3
"""Install Outcome Integrity without overwriting unrelated Codex settings."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


START_MARKER = "<!-- outcome-integrity:start -->"
END_MARKER = "<!-- outcome-integrity:end -->"


def default_codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


def merge_managed_block(current: str, block: str) -> str:
    start_count = current.count(START_MARKER)
    end_count = current.count(END_MARKER)
    if start_count != end_count or start_count > 1:
        raise ValueError("AGENTS.md has malformed Outcome Integrity markers; repair them manually")

    block = block.strip()
    if start_count == 0:
        return f"{current.rstrip()}\n\n{block}\n" if current.strip() else f"{block}\n"

    start = current.index(START_MARKER)
    end = current.index(END_MARKER, start) + len(END_MARKER)
    before = current[:start].rstrip()
    after = current[end:].lstrip()
    parts = [part for part in (before, block, after) if part]
    return "\n\n".join(parts).rstrip() + "\n"


def install(codex_home: Path, skip_global_rules: bool = False) -> tuple[Path, Path | None]:
    repository_root = Path(__file__).resolve().parent.parent
    skill_source = repository_root / "skills" / "outcome-integrity"
    skill_target = codex_home / "skills" / "outcome-integrity"

    if not (skill_source / "SKILL.md").is_file():
        raise FileNotFoundError(f"Skill source is incomplete: {skill_source}")

    codex_home.mkdir(parents=True, exist_ok=True)
    skill_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        skill_source,
        skill_target,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )

    if skip_global_rules:
        return skill_target, None

    snippet_path = repository_root / "global" / "AGENTS.snippet.md"
    snippet = snippet_path.read_text(encoding="utf-8")
    agents_path = codex_home / "AGENTS.md"
    current = agents_path.read_text(encoding="utf-8") if agents_path.exists() else ""
    merged = merge_managed_block(current, snippet)
    if merged != current:
        agents_path.write_text(merged, encoding="utf-8", newline="\n")
    return skill_target, agents_path


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
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        skill_path, agents_path = install(args.codex_home.expanduser().resolve(), args.skip_global_rules)
    except (OSError, ValueError) as exc:
        print(f"Installation failed: {exc}", file=sys.stderr)
        return 1

    print(f"Installed skill: {skill_path}")
    if agents_path:
        print(f"Updated global rules: {agents_path}")
    else:
        print("Global rules unchanged")
    print("Start a new Codex task to load the updated skill and rules.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
