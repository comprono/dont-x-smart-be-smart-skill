---
name: outcome-integrity
description: Preserve project intent and prevent objective drift, method-outcome confusion, context-compaction loss, premature completion, proxy progress, repeated failure, unbounded autonomous side effects, and wasteful orchestration. Use for nontrivial project implementation or diagnosis, resumed or compacted work, user corrections, long-running or multi-agent work, recurring loops, schedulers, watchdogs, automatic recovery, external side effects, repeated failures, unexpected scope growth, disproportionate resource use, or work the user says is irrelevant. Maintain bounded .codex/PROJECT_OUTCOME.md intent and .codex/ACCEPTANCE.json evidence state, reconcile them with current reality, classify failures before retrying, bound recurring work, advance one verified end-to-end slice, and admit delegation only when it reduces total work.
---

# Outcome Integrity

Keep the user's actual outcome authoritative across long work, corrections, compaction, failures, and delegation. This is a lightweight execution discipline, not a manager loop or workflow engine.

## Use The Correct Authority

Resolve conflicts in this order:

1. Latest explicit user instruction or correction.
2. Current authoritative project, runtime, or external evidence.
3. Reconciled `.codex/PROJECT_OUTCOME.md` and `.codex/ACCEPTANCE.json`.
4. Existing plans, documentation, summaries, memories, and worker reports.

Never let an old plan, inferred preference, add-on, safety mechanism, or worker result silently replace the north-star outcome. Preserve independently verified work and invalidate only conclusions that depended on stale assumptions.

## Frame The Outcome Before The Method

Before the first substantive tool call, edit, delegation, or durable task contract, form a compact internal outcome frame:

- **Outcome:** the real user-visible or external state ultimately wanted.
- **Proof:** the observable evidence the user would accept.
- **Methods:** intermediate actions such as reviewing, researching, planning, testing, orchestrating, migrating, or setting up.
- **Constraints:** boundaries that shape the work without replacing the outcome.

Treat review, test, inspect, analyze, plan, coordinate, monitor, document, and set up as methods when the existing project outcome is broader, unless the user explicitly asks for that artifact as the final deliverable. Apply this counterfactual: **if every proposed method completed successfully, would the user's actual problem be solved?** If not, the frame is too narrow.

Do not narrow the outcome to fit the capabilities of a tool, skill, worker, or convenient next action. For continuation work, read the nearest authoritative project outcome before creating a task contract. If intent is discoverable, reconcile it directly; ask only when materially different outcomes remain plausible.

When the user corrects the outcome or interpretation, immediately invalidate or revise every dependent plan, worker assignment, Goal, orchestration contract, acceptance item, and current slice. If a tool cannot update stale work, cancel or replace it safely rather than continuing under the old contract.

## Keep Three Kinds Of State Separate

For nontrivial project work, use:

- `.codex/PROJECT_OUTCOME.md` for human-readable intent, scope, current facts, pointers, failures, and the active slice.
- `.codex/ACCEPTANCE.json` for stable requirement IDs, reproducible acceptance steps, statuses, minimum evidence levels, evidence references, and recoverable blockers.
- Git history for chronology and recovery. Do not grow an append-only activity transcript.

Do not create these files for a trivial question, one-off command, or work outside a project.

Initialize missing files after minimal observation:

```powershell
python <skill-dir>/scripts/project_outcome.py init --root <project-root>
```

Fill all placeholders. Keep project state current rather than chronological and keep historical detail in Git.

## Start Or Resume Reliably

At the start of nontrivial work, after compaction, or after interruption:

1. Read the latest user instruction.
2. Read both project-state files.
3. Run the resume gate:

```powershell
python <skill-dir>/scripts/project_outcome.py resume --root <project-root>
```

4. Inspect the current diff and the smallest authoritative source needed to check the state files.
5. Reconcile stale intent, acceptance, current-slice, or timestamp data before substantial planning or editing.
6. Load only the relevant sources named under `Context Pointers`; do not rescan the full history or project by default.

The latest user correction must update intent immediately. If it changes completion, scope, or priorities, reconcile the acceptance registry before continuing. Conversation summaries never override these checks.

## Maintain Intent Without Bloat

Keep `PROJECT_OUTCOME.md` bounded and current. Replace stale entries. Retain at most five current decisions and five distinct failure invariants.

Update it only when one of these changes materially:

- north-star outcome, scope, non-goal, user correction, or authorization;
- verified project state or context pointer;
- assumption, root cause, failure invariant, or recovery transition;
- active acceptance ID or end-to-end slice.

Do not record routine tool calls, unchanged status, worker chatter, token counts, or repeated plans.

## Make Acceptance Mechanical

`ACCEPTANCE.json` is authoritative for completion. Each requirement must have:

- a stable ID and observable description;
- `required: true` or `false`;
- `failing`, `blocked`, or `passing` status;
- reproducible acceptance steps;
- a minimum evidence level;
- evidence references with timestamps when passing;
- owner, reason, recovery trigger, and recovery action when blocked.

Never delete or weaken a required item merely to make completion possible. Change acceptance only when the latest user instruction changes the outcome or current evidence disproves the requirement. A previously passing item must return to failing when its evidence is invalidated.

Evidence levels, strongest first:

1. `user-visible`
2. `end-to-end`
3. `integration`
4. `focused-test`
5. `process-health`
6. `activity`

A requirement cannot pass unless its recorded evidence meets or exceeds its minimum level. Plans, edits, workers, healthy processes, and elapsed time are never substitutes for higher-level evidence.

Validate after material state changes:

```powershell
python <skill-dir>/scripts/project_outcome.py validate --root <project-root>
```

## Advance One Material Slice

Select one non-passing required acceptance ID and record it as the current slice in both files. Choose the smallest end-to-end change or diagnostic that materially reduces that requirement's verified gap.

Before expanding scope, answer internally:

1. Which acceptance ID does this action advance?
2. Is it critical-path work, an add-on, or a non-goal?
3. What evidence makes it necessary now?
4. What result would disprove the approach?
5. What existing behavior must remain intact?

Also run an outcome-distance check: an intermediate artifact counts as progress only when it removes a named acceptance gap. After a rejected delegation or failed method, replan from the outcome and the remaining dependency graph instead of stopping or reporting the rejected method as the result.

Keep at most one unverified architectural layer in flight. A plan, scaffold, monitoring surface, or generated artifact is not a material slice unless it is itself the accepted outcome.

After a coherent verified slice, update both state files and use a focused Git commit when repository policy and the user's working tree permit it. Never stage unrelated user changes.

## Bound Autonomous And Recurring Work

Before enabling or resuming a loop, watcher, scheduler, unattended worker, retrying supervisor, or automatic recovery that can outlive the current turn or accumulate side effects, define a proportional operational envelope in .codex/PROJECT_OUTCOME.md:

- **Progress signal:** name the authoritative state change tied to an acceptance ID. Repeated checks, attempts, and unchanged health are not progress.
- **Side-effect identity:** use a stable idempotency key or observed-state fingerprint so the same condition becomes a no-op.
- **Cadence and retry:** observe frequently if useful; mutate only on a state transition or explicit retry eligibility with bounded cooldown or backoff.
- **Resource limits:** cap relevant disk, file count, API calls, tokens, money, RAM, and concurrency while preserving a minimum reserve or free-space floor.
- **Retention and lifecycle:** set maximum count, bytes, or age; prune before allocating near a limit; clean up after success, cancellation, crash recovery, and startup when appropriate.
- **Stop and recovery:** define a no-progress threshold, fail-closed or degraded transition, owner, recovery trigger, and restart behavior. Persist safety-critical retry and budget state; an in-memory timer alone is insufficient for accumulating or irreversible effects.

Authorization to continue does not authorize unbounded resource use or repeated irreversible side effects. Keep a bounded read-only poll lightweight; add only the controls proportional to its possible harm.

Observe frequently; mutate only on state change or explicit retry eligibility. Before acceptance, test repeated identical ticks plus restart and cancellation, and assert bounded resource growth with no duplicate side effects. If resource usage grows while the acceptance state does not improve, stop the producer, preserve evidence, and diagnose before resuming.

## Classify Failure Before Retrying

Classify the failure from evidence, then apply the matching policy:

| Class | Examples | Policy |
| --- | --- | --- |
| Transient | Timeout, connection reset, 429, temporary 5xx | Retry at most twice with backoff, only when the action is read-only or idempotent. |
| Reasoning-recoverable | Invalid tool arguments, parse error, disproven assumption | Retry once only after changing the input or approach using the observed error. |
| User-fixable | Missing credential, authorization, fact, or irreversible decision | Mark the acceptance item blocked with owner and recovery transition; continue other dependency-ready work. |
| Unexpected or semantic | Wrong behavior, invariant violation, unknown exception | Do not retry blindly. Reproduce, trace authoritative state, and diagnose first. |
| Ambiguous external write | Timeout after submit, payment, publish, send, or application | Query authoritative external state or use the idempotency key before any retry. |

When the same acceptance outcome fails twice, stop repeated status checks and symptom patches. Record the evidence and violated invariant in `Failure Memory`. A third attempt requires new root-cause evidence, a changed state, or a materially changed approach.

For resumable external workflows, persist checkpoints at coherent boundaries and make side effects idempotent. Conversation state is not execution state.

## Admit Delegation Only When It Helps

Current Codex owns the critical path. Delegate only when every condition is true:

1. The lane is genuinely parallel and does not block the current next action.
2. Its files, state, or external effects are disjoint and explicitly owned.
3. It has one bounded deliverable tied to an acceptance ID.
4. It has independent verification and one defined integration action.
5. Expected contribution exceeds prompt, waiting, review, and integration cost.
6. Failure cannot corrupt authoritative state; uncertain lanes are read-only.

If any condition is false, work directly. Keep sequential reasoning in one agent. Use centralized integration, verify each worker result once, and never create worker review chains, heartbeat loops, or duplicate lanes.

## Detect And Correct Drift

Stop and reconcile before spending more when:

- an action advances no required acceptance ID;
- an add-on becomes the practical objective;
- the plan relies on stale summaries or assumptions;
- lower-level evidence is being reported as completion;
- coordination costs more than its likely contribution;
- a user correction conflicts with the active slice;
- the same failure is approaching an unchanged third attempt.

Correct the state files first, then choose the next slice from the remaining verified gap. Do not preserve a bad plan by adding more rules, and do not swing to a full rebuild unless evidence requires it.

## Complete Or Block Honestly

Before claiming completion, run:

```powershell
python <skill-dir>/scripts/project_outcome.py completion --root <project-root>
```

Completion requires both project states to be `complete`, no current slice, and every required acceptance item passing with sufficient evidence. Do not redefine success downward to match what was built.

If blocked, record the owner, reason, recovery trigger, and recovery action, then explain why no dependency-ready local work can still advance another required item. Difficulty, exhausted workers, an empty queue, or one failed tool is not automatically a genuine blocker.

Communicate only material transitions using `Done / Active / Blocked / Next` when structure helps. Keep the user's outcome and evidence visible; omit routine narration and unchanged status.
