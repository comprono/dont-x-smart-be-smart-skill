<!-- Managed with the outcome-integrity skill. Keep this current, not chronological. -->
# Project Outcome

Updated: 2026-07-29T19:22:03Z
State: active

## North Star

- Product outcome: Improve and publicly release the standalone Outcome Integrity skill so Codex preserves the user's full outcome, distinguishes it from a proof slice, preserves exact named-entity identity, reconciles contradictory evidence, resumes from the correct project root, and communicates and executes with less wasted work.
- User-visible proof: Generic state validation and regression tests reject invalid completion, the exact verified source is merged into GitHub main, public CI succeeds, and GitHub shows v2.0.0 as the latest release for that implementation revision.
- Active proof slice: Publish the verified standalone changes through a GitHub pull request, confirm CI, and create the first GitHub Release as v2.0.0.
- Proof limits: The release proves public source, CI, tag, and release alignment; it does not guarantee perfect behavior from every probabilistic model in every future project.
- Methods, not outcomes: Auditing prior tasks, editing instructions, changing schemas, testing, installation, and reporting.
- Why it matters: Efficient execution is impossible when a convenient test, similarly named resource, stale state file, or unresolved contradiction is allowed to replace the user's real objective.

## Done Means

- Authority: .codex/ACCEPTANCE.json
- Summary: Every required capability has mapped evidence, the standalone package passes locally and in public CI, the verified source is merged to main, and GitHub v2.0.0 is published as the latest release.

## User Intent

- Priorities: Improve the reusable skill from real post-release behavior, not from hypothetical examples or one plugin.
- Working preferences: Make the safeguards mechanical, concise, globally reusable, token-efficient, and honest about proof boundaries.
- Explicit corrections: The skill is separate from every plugin and project; publish this verified standalone upgrade to GitHub and update the repository's latest release.
- Non-negotiables: Do not edit the plugin, encode provider-specific names, or claim success from phrase-presence tests alone.

## Work Map

### Critical Path

- Separate product capabilities from active proof slices and their limits.
- Bind evidence to exact acceptance steps and reject unresolved counterevidence.
- Preserve explicitly named identity and validate the selected project root.
- Add generic behavioral regression fixtures, validate the package, and install the verified standalone skill.
- Merge the exact verified source to GitHub main and publish v2.0.0 as the latest release.

### Add-ons

- Clarify public documentation only where needed to explain the stronger reusable contract.

### Non-goals

- Changing any plugin, provider integration, application project, model router, or resource orchestrator.

## Operational Envelope

- Applies to: This bounded local skill upgrade; no recurring or unattended process is authorized.
- Progress signal and side-effect key: A named acceptance step changes from failing to evidence-backed passing; installation remains idempotent.
- Cadence and retry eligibility: Run deterministic validation after coherent edits; diagnose failed invariants before retrying.
- Resource budget, reserve, and retention: One local repository, one installed skill copy, no worker fan-out, no generated activity logs.
- No-progress stop, restart, cancellation, and recovery: Stop repeated edits after two failures of the same acceptance outcome; resume from these two state files and the current diff.

## Verified State

- The prior release passes structural tests but post-release task evidence shows outcome-to-proof collapse, same-name identity substitution, unreconciled contradictory evidence, premature stopping, and excessive coordination | Evidence: closed-window audit of Codex task records after f331bfd | Verified: 2026-07-29T18:53:50Z
- The repository was clean at commit 056d1a9 before this upgrade | Evidence: git status, branch, and log inspection | Verified: 2026-07-29T18:53:50Z
- Twenty-three deterministic tests pass for schema-v2 mechanics and existing behavior | Evidence: TEMP/TMP=C:\tmp python -m unittest discover -s tests -v | Verified: 2026-07-29T19:10:35Z
- The official skill validator, Python compilation, project validate/resume gates, isolated double-install test, active installation, exact five-file SHA256 comparison, and one normalized managed global rule block pass | Evidence: local command outputs and installed-source comparison | Verified: 2026-07-29T19:10:35Z
- Generic-source scanning found no names from the motivating provider/plugin case in the skill, validator, templates, tests, global rules, or README | Evidence: case-insensitive repository scan | Verified: 2026-07-29T19:10:35Z

## Context Pointers

- Architecture or project map: README.md and skills/outcome-integrity/SKILL.md
- Active specification: .codex/PROJECT_OUTCOME.md and .codex/ACCEPTANCE.json
- Verification commands: python -m unittest discover -s tests -v; project_outcome.py validate, resume, and completion; quick_validate.py
- Evidence roots: tests, current diff, isolated installer output, and installed-source hash comparison

## Assumptions To Test

- Capability mapping plus step-bound evidence prevents a narrow proof slice from completing a broader outcome | Falsifier: a fixture completes while a required capability or step is uncovered | Next check: adversarial completion tests
- Explicit identity constraints prevent same-label substitution without encoding project-specific names | Falsifier: an unknown or substitutable identity can satisfy a non-substitutable requirement | Next check: schema validation tests

## Decisions

- Upgrade to acceptance schema version 2 while keeping legacy state readable for resume | Why: existing projects need recovery, but new completion claims need stronger proof | Revisit when: migration burden exceeds the integrity gain
- Put reusable invariants in the skill and global rules, and enforcement details in the validator | Why: keep prompting concise while making completion mechanical | Revisit when: a rule cannot be tested mechanically
- Use v2.0.0 for the first GitHub Release | Why: schema version 2 introduces a deliberately stronger completion contract while keeping schema-v1 recovery compatibility | Revisit when: a future breaking contract change is released

## Failure Memory

- Proof slice promoted to product outcome | Class: semantic | Evidence: post-release project audit | Invariant: required product capabilities remain authoritative across demos, tests, pilots, and other proof methods | Do not repeat: rewriting the outcome to match the convenient test
- Same-label entity substitution | Class: semantic | Evidence: post-release project audit | Invariant: explicitly named entities are non-substitutable until equivalence is proven | Do not repeat: treating a matching display name or capability as identity proof
- Contradictory evidence routed around | Class: evidence conflict | Evidence: observed state conflicted with an explicit user assertion | Invariant: reconcile the exact entity, surface, session, and principal or retain counterevidence | Do not repeat: treating a fallback as resolution

## Current Slice

- Acceptance ID: REQ-PUBLISH
- Objective: Merge the verified standalone source, pass public CI, and publish GitHub release v2.0.0.
- Acceptance evidence: Local package evidence passes; GitHub merge, public CI, tag, and latest-release evidence are pending.
- Protect: Standalone packaging, token efficiency, backward-readable project state, unrelated projects, and user-owned changes.
- Status: active

## Next

- Action: Commit the scoped changes on a publication branch, open and merge the GitHub pull request after CI, then create and verify v2.0.0.
- Why now: The user explicitly extended the completed local upgrade to public GitHub publication.
- Blocker and recovery: None.