<!-- Managed with the outcome-integrity skill. Keep this current, not chronological. -->
# Project Outcome

Updated: 2026-07-18T22:31:03Z
State: blocked

## North Star

- Outcome: Upgrade and publish Outcome Integrity so Codex frames the real outcome, answers simple user questions directly, stops confusing reply loops with layer-separated status, bounds autonomous resource use, preserves intent, and proves outcomes across corrections, compaction, failures, and selective delegation.
- User-visible proof: A future task answers a simple status or meaning question in plain language before technical detail, names separate project/tooling/restart/communication layers when relevant, stops expansion when the user is confused, keeps the user's actual result authoritative, and cannot run accumulating autonomous side effects without explicit progress, resource, retention, and stop bounds.
- Methods, not outcomes: Review, planning, testing, delegation, installation, and publication.
- Why it matters: A sound recovery system can still fail if it formalizes the wrong task before recovery begins.

## Done Means

- Authority: .codex/ACCEPTANCE.json
- Summary: Intent, acceptance evidence, recovery, delegation, installation, and publication are verified through reproducible checks.

## User Intent

- Priorities: Apply researched solutions without adding another orchestration system.
- Working preferences: Implement, test, install, publish, and report verified results concisely; give the answer first when the user asks a simple question; stop clarification loops by restating the conclusion, distinction, and next owned action.
- Explicit corrections: This is a separate global skill; prevent method-outcome substitution, buried answers, and unbounded recurring side effects without adding project-specific rules.
- Non-negotiables: Stay token-efficient, globally reusable, and honest about guarantee boundaries.

## Work Map

### Critical Path

- Add a pre-work outcome frame and stale-contract correction gate.
- Add a proportional bounded-autonomy gate for recurring, unattended, scheduled, retrying, and resource-producing work.
- Preserve the machine-verifiable acceptance registry and mature recovery/delegation gates.
- Add and verify direct-answer-first and confusing-reply-loop rules for simple status, meaning, alignment, ownership, and next-action questions.
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
- Bounded-autonomy rules and operational-envelope template passed local and public validation at commit c0c46d2 | Evidence: 11 package tests, Codex skill validator, GitHub Actions run 29536198974, privacy scan, exact installed SHA256 comparison | Verified: 2026-07-16T21:30:51Z
- Direct-answer-first behavior passes 12 local deterministic tests and the active state validates and resumes | Evidence: python -m unittest discover -s tests -v; project_outcome.py validate and resume | Verified: 2026-07-18T22:01:07Z
- Confusing-reply-loop and layer-separated-status behavior passes 13 local deterministic tests and the active state validates and resumes | Evidence: TEMP/TMP=C:\tmp python -m unittest discover -s tests -v; project_outcome.py validate and resume | Verified: 2026-07-18T22:30:19Z

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
- Recurring side effect without progress | Root cause: observation cadence directly triggered mutation with no resource envelope | Invariant: recurring work requires idempotency, budget, retention, no-progress stop, and restart-safe recovery | Do not repeat: unlimited retries under broad authorization
- Buried/confusing reply loop | Root cause: communication presented process detail or mixed project/tooling/model/restart layers before the plain conclusion, forcing repeated clarification | Invariant: answer conclusion first, name the layer, and stop expansion when the user is confused | Do not repeat: leading with hashes, paths, process narration, or long architecture/status history

## Current Slice

- Acceptance ID: REQ-PACKAGE
- Objective: Publish and verify the direct-answer-first and communication-loop release.
- Acceptance evidence: GitHub CI verifies the current commit after the local 13-test result.
- Protect: Accuracy, necessary qualifications, short global instructions, layer-separated status, trivial-task proportionality, and unrelated user changes.
- Status: blocked

## Next

- Action: Await the user's authorization to commit, push, and then install the verified direct-answer-first and communication-loop release.
- Why now: The source change is locally verified by 13 deterministic tests, but publishing and changing the active Codex installation are external writes requiring user direction.
- Blocker and recovery: Owner: user | Trigger: explicit authorization to publish and/or install | Recovery: commit and push the scoped release, verify CI, then run the installer and compare hashes.
