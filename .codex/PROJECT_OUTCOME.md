<!-- Managed with the outcome-integrity skill. Keep this current, not chronological. -->
# Project Outcome

Updated: 2026-07-16T21:01:02Z
State: complete

## North Star

- Outcome: Upgrade and publish Outcome Integrity so Codex frames the real outcome before methods, preserves intent, and proves outcomes across corrections, compaction, failures, and selective delegation.
- User-visible proof: A future task keeps the user's actual result authoritative before tools or delegation and immediately replaces stale contracts after correction.
- Methods, not outcomes: Review, planning, testing, delegation, installation, and publication.
- Why it matters: A sound recovery system can still fail if it formalizes the wrong task before recovery begins.

## Done Means

- Authority: .codex/ACCEPTANCE.json
- Summary: Intent, acceptance evidence, recovery, delegation, installation, and publication are verified through reproducible checks.

## User Intent

- Priorities: Apply researched solutions without adding another orchestration system.
- Working preferences: Implement, test, install, publish, and report verified results concisely.
- Explicit corrections: This is a separate global skill; prevent intermediate methods from replacing the actual user outcome before any task contract is created.
- Non-negotiables: Stay token-efficient, globally reusable, and honest about guarantee boundaries.

## Work Map

### Critical Path

- Add a pre-work outcome frame and stale-contract correction gate.
- Preserve the machine-verifiable acceptance registry and mature recovery/delegation gates.
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
- Public CI passed commit 2c85453 and the installed local skill matches every repository file hash | Evidence: GitHub Actions run 29462178379 and local SHA256 comparison | Verified: 2026-07-16T00:43:15Z
- Outcome-framing rules, stale-contract invalidation, and method-rejection replanning passed local and public validation at commit 143d005 | Evidence: 10 package tests, Codex skill validator, GitHub Actions run 29534222570, installed SHA256 comparison | Verified: 2026-07-16T21:01:02Z

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
- Method promoted to outcome | Root cause: the task contract formed before the real result was distinguished from review, testing, or orchestration | Invariant: frame outcome and proof before substantive work | Do not repeat: completing an intermediate method as though it solved the problem

## Current Slice

- Acceptance ID: none
- Objective: Outcome-framing revision is released and verified.
- Acceptance evidence: All six required acceptance items pass at their required evidence levels.
- Protect: Short global instructions, trivial-task proportionality, installer idempotency, and local privacy.
- Status: complete

## Next

- Action: Start a new Codex task after restart to exercise the updated global framing rule.
- Why now: Implementation, public CI, exact installation, and completion evidence are verified.
- Blocker and recovery: None.
