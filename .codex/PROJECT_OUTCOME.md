<!-- Managed with the outcome-integrity skill. Keep this current, not chronological. -->
# Project Outcome

Updated: 2026-08-08T00:47:51Z
State: active

## North Star

- North-star outcome: Improve and publicly release the standalone Outcome Integrity skill so Codex preserves the user's enduring outcome, current delivery stage, capability milestones, acceptance slices, and immediate actions without completion leaking between levels.
- Current delivery stage: Release the schema-v3 outcome-stack contract as a backward-readable major upgrade of the standalone skill.
- Stage completion boundary: Generic instructions, schema enforcement, adversarial tests, local installation, GitHub main, passing public CI, and the latest v3.0.0 release all identify the exact verified source; behavior from every future probabilistic model remains outside this stage's guarantee.
- User-visible proof: New projects initialize the parent chain; v1/v2 projects resume; invalid cross-stage mappings and premature completion fail; the installed copy matches source; GitHub publishes the passing revision as v3.0.0.
- Active acceptance slice: Publish the exact locally verified schema-v3 source through GitHub main, public CI, and the v3.0.0 release.
- Slice proof limits: Publication proves repository and release identity, not behavior in every future task.
- Methods, not outcomes: Plugin-task auditing, editing instructions, schema migration, tests, installation, commits, CI, and release operations.
- Why it matters: Without explicit parent levels, an immediate success can silently replace a milestone or the larger user outcome.

## Done Means

- Authority: .codex/ACCEPTANCE.json
- Summary: Every required v3.0.0 capability and slice passes, the north star is achieved for this release, and the exact verified revision is installed locally and published as GitHub's latest release.

## User Intent

- Priorities: Strengthen the skill beyond a three-time-horizon explanation by enforcing parent relationships, typed completion, correction scope, and evidence isolation.
- Working preferences: Keep the skill generic, concise, token-efficient, productive, and independent of the plugin project that revealed the defect.
- Explicit corrections: Update the skill locally and on GitHub now.
- Non-negotiables: Do not change the plugin, encode plugin/provider names, weaken backward recovery, or claim publication before external verification.

## Work Map

### Critical Path

- Enforce north star -> delivery stage -> capability -> acceptance slice parent integrity.
- Reject completion leakage, cross-stage substitution, and incompatible current-stage selection.
- Preserve v1/v2 recovery, validate and install locally, then publish the exact passing revision as v3.0.0.

### Add-ons

- None before release evidence passes.

### Non-goals

- Changing any plugin, provider integration, application, or project-specific orchestrator.

## Operational Envelope

- Applies to: One bounded standalone skill release; no recurring process.
- Progress signal and side-effect key: A named acceptance step becomes evidence-backed; local installation remains idempotent and GitHub publication is keyed by exact commit and v3.0.0 tag.
- Cadence and retry eligibility: Diagnose a failed validation, CI, push, or release invariant before retrying.
- Resource budget, reserve, and retention: One repository, one installed skill copy, no worker fan-out, no generated activity archive.
- No-progress stop, restart, cancellation, and recovery: Resume from these state files and the Git diff; stop unchanged publication retries after two failures.

## Verified State

- All 21 exposed plugin-project tasks and one adjacent projectless task were audited without modifying the plugin | Evidence: task-history audit, 86 pages and 735 substantive exact-project turns | Verified: 2026-08-08T00:30:00Z
- The audit isolated goal-horizon aliasing and untyped completion propagation as a generic failure class | Evidence: repeated product, stage, proof, release, and next-action substitutions in task history | Verified: 2026-08-08T00:30:00Z
- The schema-v3 implementation passes 29 deterministic tests and keeps the invoked skill at 3,157 words and global rules at 650 words | Evidence: python -m unittest discover -s tests -v and local word counts | Verified: 2026-08-08T00:46:01Z
- Official skill validation, compilation, project validation/resume, isolated double-install, active double-install, exact five-file SHA-256 parity, one managed global block, and generic-source isolation pass | Evidence: local validation and installation outputs | Verified: 2026-08-08T00:47:51Z

## Context Pointers

- Architecture or project map: README.md and skills/outcome-integrity/SKILL.md
- Active specification: .codex/PROJECT_OUTCOME.md and .codex/ACCEPTANCE.json
- Verification commands: python -m unittest discover -s tests -v; project_outcome.py validate, resume, and completion; quick_validate.py
- Evidence roots: tests, current diff, isolated installer output, installed-source hashes, GitHub CI and release metadata

## Assumptions To Test

- Explicit stage parents prevent a passing slice from completing a broader stage | Falsifier: an incomplete stage validates as complete | Next check: adversarial stage-coverage tests
- Schema v2 remains usable for recovery | Falsifier: a valid v2 fixture cannot resume | Next check: legacy-resume regression

## Decisions

- Release as v3.0.0 and require schema v3 for new completion claims | Why: parented completion changes the durable contract while preserving v1/v2 recovery | Revisit when: migration evidence shows unacceptable recovery cost
- Reuse capabilities and requirements as milestone and slice layers beneath new north-star and delivery-stage objects | Why: adds the missing hierarchy without a third state file or duplicate registry | Revisit when: real projects need a richer dependency graph
- Keep the plugin solely as audit evidence | Why: the skill must remain independently reusable | Revisit when: never unless the user explicitly changes product scope

## Failure Memory

- Slice completion promoted to stage or product completion | Class: goal-horizon collapse | Evidence: post-v2.1 task audit | Invariant: evidence moves upward only through declared parent coverage | Do not repeat: unqualified completion language
- Current proof project substituted for the universal product | Class: downward objective replacement | Evidence: repeated user corrections in plugin history | Invariant: delivery stages advance but never redefine the north star | Do not repeat: rewriting a parent to match a convenient child

## Current Slice

- Delivery Stage ID: STAGE-V3-RELEASE
- Acceptance ID: REQ-V3-PUBLISH
- Objective: Commit, merge, verify public CI, and publish the exact passing schema-v3 source as GitHub's latest v3.0.0 release.
- Acceptance evidence: The local source and active installed copy pass every package gate and match exactly; GitHub publication remains.
- Protect: Backward recovery, token bounds, generic wording, unrelated repositories, and the plugin boundary.
- Status: active

## Next

- Action: Create the focused release branch and commit, push it, merge a pull request after CI, then create and verify v3.0.0.
- Why now: Local package identity is proven; external publication is the only remaining acceptance slice.
- Blocker and recovery: None.
