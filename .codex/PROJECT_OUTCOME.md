<!-- Managed with the outcome-integrity skill. Keep this current, not chronological. -->
# Project Outcome

Updated: 2026-07-16T00:41:04Z
State: active

## North Star

- Outcome: Upgrade and publish Outcome Integrity so Codex preserves project intent and proves outcomes across compaction, failures, and selective delegation.
- Why it matters: Instruction-only continuity can still drift, retry the wrong failure, or claim progress from proxy evidence.

## Done Means

- Authority: .codex/ACCEPTANCE.json
- Summary: Intent, acceptance evidence, recovery, delegation, installation, and publication are verified through reproducible checks.

## User Intent

- Priorities: Apply researched solutions without adding another orchestration system.
- Working preferences: Implement, test, install, publish, and report verified results concisely.
- Explicit corrections: Preserve project truth across compaction using maintained project files, not a project-specific AGENTS.md.
- Non-negotiables: Stay token-efficient, globally reusable, and honest about guarantee boundaries.

## Work Map

### Critical Path

- Add a machine-verifiable acceptance registry and mature recovery/delegation gates.
- Test deterministic behavior and fresh-agent behavior, then publish and install the exact release.

### Add-ons

- Improve public documentation only where required to explain the upgraded contract.

### Non-goals

- Building a workflow engine, model router, manager loop, or project-specific integration.

## Verified State

- Public repository main matches local commit d38bd09 | Evidence: clean git status and origin/main | Verified: 2026-07-16T00:31:42Z
- Current release has one Markdown ledger validator and a two-failure rule | Evidence: source inspection | Verified: 2026-07-16T00:31:42Z
- Existing package tests and GitHub CI passed before this upgrade | Evidence: prior local and GitHub Actions results | Verified: 2026-07-16T00:31:42Z
- Dual-file state validation passes eight deterministic tests | Evidence: python -m unittest discover -s tests -v | Verified: 2026-07-16T00:38:55Z
- Failure classification and delegation admission pass three fresh-agent scenarios on GPT-5.6 Luna low | Evidence: agent results recorded in ACCEPTANCE.json | Verified: 2026-07-16T00:41:04Z

## Context Pointers

- Architecture or project map: README.md and skills/outcome-integrity/SKILL.md
- Active specification: .codex/PROJECT_OUTCOME.md and .codex/ACCEPTANCE.json
- Verification commands: python -m unittest discover -s tests -v
- Evidence roots: tests, Git history, and GitHub Actions

## Assumptions To Test

- A two-file contract remains simpler and more reliable than a larger runtime | Falsifier: validation or behavioral tests require orchestration state | Next check: implement and forward-test
- JSON acceptance status resists silent completion drift | Falsifier: invalid evidence can pass deterministic validation | Next check: adversarial unit fixtures

## Decisions

- Keep Markdown for human intent and JSON for acceptance state | Why: readability and mechanical enforcement have different needs | Revisit when: either source duplicates authority
- Use Git for history and keep project files current | Why: append-only progress logs create context growth | Revisit when: resume tests cannot reconstruct state

## Failure Memory

- Instruction-only continuity | Root cause: no machine-verifiable acceptance registry | Invariant: completion requires validated evidence-bearing acceptance items | Do not repeat: treating Markdown checkboxes as proof
- Blanket retry handling | Root cause: transient and semantic failures were conflated | Invariant: classify before retry | Do not repeat: identical semantic retry

## Current Slice

- Acceptance ID: REQ-PACKAGE
- Objective: Run complete package, privacy, metadata, and installation verification before publication.
- Acceptance evidence: All deterministic checks pass and no private data is present.
- Protect: Short global instructions, trivial-task proportionality, installer idempotency, and local privacy.
- Status: active

## Next

- Action: Run the full local validation matrix and inspect the complete diff.
- Why now: State, recovery, and delegation behavior pass; package integrity is the next dependency.
- Blocker and recovery: None.
