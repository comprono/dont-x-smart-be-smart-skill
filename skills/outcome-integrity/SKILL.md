---
name: outcome-integrity
description: Preserve project intent and prevent objective drift, context-compaction loss, proxy progress, repeated symptom patches, and wasteful orchestration. Use for nontrivial project implementation or diagnosis, resumed or compacted work, user corrections, long-running or multi-agent work, repeated failures, unexpected scope growth, disproportionate token use, or work the user says is irrelevant. Maintain a bounded .codex/PROJECT_OUTCOME.md ledger, reconcile it with current evidence and the latest user instruction, advance one material end-to-end slice, and stop repeated failure through a root-cause circuit breaker.
---

# Outcome Integrity

Keep the user's actual outcome authoritative across long work, context compaction, corrections, and changing project state. Use one short project ledger as working memory; do not turn the workflow into another management system.

## Establish Authority

Use this order when sources conflict:

1. The latest explicit user instruction or correction.
2. Current authoritative project or runtime evidence.
3. Reconciled `.codex/PROJECT_OUTCOME.md` content.
4. Existing plans, documentation, chat summaries, memories, and worker reports.

Never let an old plan, add-on, safety mechanism, worker result, or inferred preference silently replace the north-star outcome. Preserve compatible verified work, but invalidate conclusions that depended on a corrected or disproven assumption.

## Maintain Durable Project State

For nontrivial project work, use `<project-root>/.codex/PROJECT_OUTCOME.md`. Do not create it for a trivial question, one-off command, or work outside a project.

At the start of work:

1. Read the latest user instruction.
2. Read the ledger if it exists.
3. Inspect the current diff and the smallest authoritative surface needed to check ledger accuracy.
4. Reconcile stale or conflicting entries before substantial planning or editing.

If the ledger is missing, first observe enough current state to avoid recording guesses as facts. Then run:

```powershell
python <skill-dir>/scripts/project_outcome.py init --root <project-root>
```

Fill the generated ledger with evidence-backed content. Validate it after material updates:

```powershell
python <skill-dir>/scripts/project_outcome.py validate --root <project-root>
```

Keep the ledger current rather than chronological. Replace stale entries; do not append routine activity, tool calls, unchanged status, or chat transcripts. Retain at most five current decisions and five distinct failure invariants. Keep it under the validator's size limit.

Update the ledger only when one of these changes materially:

- the north-star outcome or definition of done;
- an explicit user preference, correction, non-goal, or authorization;
- a verified milestone or current project state;
- an assumption is proved or disproved;
- a root cause or failed invariant is established;
- the active end-to-end slice, blocker owner, or recovery transition changes.

## Recover After Compaction Or Resume

After compaction, interruption, handoff, or a long pause, do not continue from the conversation summary alone.

1. Re-read the latest user message and project ledger.
2. Inspect the current diff and one authoritative state surface.
3. Mark stale ledger claims as stale or replace them.
4. Reconstruct the current slice from the remaining verified gap.
5. Continue only after the proposed action agrees with the north star and current evidence.

This recovery is a bounded read, not a broad rescan of the project or its entire history.

## Detect Divergence Before Spending

Before a large edit, delegation, new subsystem, or expensive investigation, answer internally:

1. Which `Done Means` item does this action advance?
2. Is it critical-path work, an add-on, or a non-goal?
3. What current evidence makes it necessary now?
4. What result would disprove the approach?
5. Has the same symptom or acceptance failure already occurred twice?
6. What existing behavior must remain intact?

Stop and reconcile the ledger when any of these conditions appears:

- the proposed action advances no definition-of-done item;
- an add-on has become the de facto objective;
- the plan relies on a stale assumption or summary;
- activity, health, tests, or worker completion is being treated as user-visible progress;
- coordination or evaluation costs more than the contribution it can add;
- a user correction conflicts with the current plan;
- the same failed outcome is being attempted a third time without new root-cause evidence.

## Advance One Material Slice

Choose the smallest end-to-end change or diagnostic that materially reduces the verified gap to the north star. Record it under `Current Slice` with:

- one objective;
- observable acceptance evidence;
- behavior that must be protected;
- current status.

Keep at most one unverified architectural layer in flight. Scaffolding, planning, process health, and generated artifacts are not material slices unless they are the requested deliverable.

Work directly by default. Delegate only after observation establishes an independent lane with a bounded output and one integration point, and only when expected contribution exceeds coordination and review cost. Keep current Codex advancing the critical path. Verify and integrate a worker result once; do not create review chains or polling loops.

## Match Claims To Evidence

Use this evidence hierarchy:

1. User-visible or externally authoritative outcome.
2. End-to-end acceptance through the real path.
3. Integration verification across affected boundaries.
4. Focused regression or unit checks.
5. Process, service, or runtime health.
6. Activity such as plans, edits, tool calls, workers, artifacts, elapsed time, or token use.

Never use a lower level to claim a higher one. Report material progress only when accepted evidence reduces the remaining outcome gap.

## Break Repeated Failure

When the same symptom, blocker, or failed acceptance condition occurs twice:

1. Stop retries, repeated status checks, and further symptom patches.
2. Identify the single authoritative state for the failed outcome.
3. Trace the complete transition from input to that state.
4. Reproduce the failure at the narrowest reliable boundary.
5. State the violated invariant in `Failure Memory`.
6. Make the next change address that invariant and verify the full transition.

A third attempt without new root-cause evidence is prohibited.

Every blocking or parked state introduced by the work must record why it exists, who or what owns resolution, the recovery trigger, the transition back to executable work, and evidence that recovery works. A gate without recovery is an accumulating dead end.

## Finish Honestly

Completion requires the ledger's definition-of-done evidence, adjusted only by explicit user correction or newly observed reality. Never redefine success downward to match what was built.

If blocked, identify the external or user-only condition, its owner, the required action, and why no dependency-ready local work can still improve the outcome. Difficulty, uncertainty, exhausted workers, or a failed tool is not automatically a genuine blocker.

Communicate concisely as `Done / Active / Blocked / Next` when structure helps. Omit routine narration, repeated plans, unchanged status, and token-expensive self-review.
