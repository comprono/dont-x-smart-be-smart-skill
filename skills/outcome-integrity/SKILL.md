---
name: outcome-integrity
description: Preserve a parented outcome stack and prevent goal-horizon collapse, identity substitution, evidence loss, wrong-project resume, blind persistence, attention drift, premature completion, repeated failure, unbounded effects, and wasteful orchestration. Use for nontrivial, resumed, corrected, long-running, multi-agent, side-effecting, repeatedly failing, or unexpectedly growing work. Maintain bounded .codex evidence, return attention to one verified slice, and delegate only when it reduces total work.
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

## Build A Parented Outcome Stack

Before substantive work, form this internal stack:

- **North-star outcome:** the enduring user-visible state ultimately wanted.
- **Delivery stage:** the coherent useful product state being delivered now; it advances but does not replace the north star.
- **Capability milestone:** one independently necessary property of that stage.
- **Acceptance slice:** a bounded end-to-end proof of part of one milestone, with explicit limits.
- **Next action:** the immediate operation closing a named slice gap; methods and constraints are not outcomes.

These are authority levels, not durations. Every action must answer: **if it succeeds, which slice closes, which parent advances, and what remains unchanged?** Reviews, tests, plans, demos, setup, and orchestration are methods or slices when the outcome is broader. If every method succeeded but the user's problem remained, the stack is too narrow.

Require `action -> acceptance slice -> capability milestone -> delivery stage -> north star`. Orphan work is drift until mapped. Never rewrite a parent to match a convenient child, tool, worker, or model.

Prevent upward completion leakage, downward objective replacement, horizontal substitution, and stage inversion. Type completion as `action complete`, `slice passing`, `stage complete`, or `north star achieved`; never use unqualified status when levels could be confused.

Scope corrections before propagation: method replaces action; contrary evidence reopens slice; capability or stage revises descendants; north-star correction invalidates incompatible descendants. Child failure does not rewrite a parent without evidence; parent corrections flow down immediately.

## Preserve Exact Identity And Contradictory Evidence

Treat an explicitly named person, account, tool, provider, runtime, repository, credential, session, system, file, or resource as an identity-bound requirement. A matching display name, interface, capability, output, or family is not proof of equivalence. An alternative may advance unrelated requirements, but it cannot satisfy the named requirement unless the user authorizes substitution or authoritative evidence proves the identities equivalent.

When observed evidence conflicts with the user's explicit statement or another authoritative observation, do not choose the convenient side or route around the conflict. Identify the exact entity, access surface, session, principal, context, and observation time; probe the same identity and surface; preserve both observations as counterevidence; and reconcile the violated assumption. A fallback is progress only for requirements it independently satisfies, not resolution of the contradiction.

Neither a user assertion nor one probe is automatically infallible. Until the conflict is resolved, keep the affected requirement failing or blocked and state what remains unknown. Ask the user only when the exact identity or authority cannot be determined safely from available evidence.

## Discern Before Persisting

Do not confuse momentum with focus. When duties, evidence, authority, irreversible effects, or method attachment conflict, recover steady judgment:

1. Name the controlling user outcome and required capability.
2. Separate observed conflict from fear, status, sunk cost, or discomfort.
3. Check authority, reversibility, affected systems, and downstream harm.
4. Take the smallest evidence-supported action; otherwise preserve the conflict and use the blocker contract.

Distinguish required action, deliberate non-action, avoidant inaction, and unauthorized action. Do not call real conflict laziness or use analysis to avoid safe authorized work.

Detach judgment from praise, blame, preferred results, methods, or prior investment. This never reduces responsibility, acceptance, or evidence quality; it prevents desire from corrupting measurement.

## Maintain Continuous Project Ownership

Treat each message in an active project as an update to the existing project unless the user explicitly starts a different outcome or asks only for explanation, diagnosis, review, or a pause. Do not reset ownership merely because the user asks a question, corrects wording, or interrupts the work.

Before responding, recover one compact control frame from the latest instruction, current evidence, and project state:

- **North star and current delivery stage:** the enduring result and coherent product state being pursued now.
- **Capability and acceptance slice:** the controlling stage gap and bounded proof in flight.
- **Latest correction:** the newest change to meaning, scope, or working preference.
- **Next Codex-owned action:** the next safe action already authorized by the project.
- **Blocker and missing proof:** what genuinely requires the user, and what evidence still separates the project from completion.

Classify the new message as one or more of: new outcome, correction, question or status, pause or diagnosis-only, or authorization or continuation. Apply it to the control frame before acting. A correction updates the active contract; a question does not cancel authorized work; a request to read, inspect, explain, or plan is a method rather than the project outcome unless the user explicitly makes that artifact the final deliverable.

Interpret noisy, voice-transcribed, or imprecise wording from the available conversation and project evidence. When one interpretation clearly preserves the established outcome, proceed under it and state only any necessary assumption. Ask a clarifying question only when multiple materially different outcomes remain plausible and choosing one would change the work or create meaningful risk.

After answering an interruption, apply the discernment gate, then continue the next safe authorized project action in the same turn. Do not stop at a recommendation, plan, or diagnosis when implementation remains authorized and executable. Do not make the user repeatedly say "do it", "continue", or "what next" for work you already own.

Stop only for verified completion, an explicit pause or diagnosis-only request, a genuinely user-owned decision or authorization, or a blocker with no dependency-ready work. Before ending a turn, ask internally: **am I leaving the user to manage the next obvious action that Codex already owns?** If yes, continue the work instead of handing it back.

## Communicate For Productive Understanding

For a simple status, meaning, ownership, alignment, or next-action question, give the plain-language conclusion in the first sentence. Communicate truthfully, usefully, proportionately, and without unnecessary agitation. Technically correct wording that makes the user repeat, simplify, or decode the answer is an execution defect.

When status needs structure, answer in this order:

- **Material transition:** what evidence changed.
- **Typed status:** slice, stage, and north-star state; include tooling or runtime state only when relevant.
- **Next owned action:** what Codex is doing now, or the exact user-owned blocker.

Never let `Done`, `working`, `complete`, `blocked`, `restart`, `plugin`, `local`, or `installed` refer to multiple layers in one sentence. Name the layer. A released tool is not a completed user outcome; a running worker is not a finished external action.

If the user says the answer is confusing, repeats the question, or restates it more simply, stop expansion. Use at most three plain sentences for the conclusion, material distinction, and next action. Never answer "yes, exactly" to an interpretation that loses a material distinction.

In project reports, `Next` means an agent-owned action already started or immediately executable. Do safe authorized work instead of assigning it back to the user; otherwise name the exact user-owned decision or authority.

## Keep Three Kinds Of State Separate

For nontrivial project work, use:

- `.codex/PROJECT_OUTCOME.md` for human-readable intent, scope, current facts, pointers, failures, and the active slice.
- `.codex/ACCEPTANCE.json` for project identity, north star, delivery stages, stage-parented capabilities and slices, exact identities, proof limits, evidence, counterevidence, statuses, and blockers.
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

4. Verify `project_identity.root_markers` under the selected root before trusting either file; never borrow a nearby parent, child, plugin, or sibling project's state because its topic looks related.
5. Inspect the current diff and the smallest authoritative source needed to check the state files.
6. Reconcile stale intent, acceptance, identity, counterevidence, current-slice, or timestamp data before substantial planning or editing.
7. Load only the relevant sources named under `Context Pointers`; do not rescan the full history or project by default.

Before an important or irreversible slice, confirm that the objective is remembered correctly, relevant state is restored, identity or authority conflicts are resolved, remaining uncertainty is tolerable and visible, and the next action is consciously owned. Do not demand certainty that the evidence cannot provide.

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

`ACCEPTANCE.json` is authoritative for completion. Use schema version 3 for new work and completion claims. Versions 1 and 2 remain readable for recovery. It must declare:

- a stable project identity plus relative root markers;
- one north star, its delivery stages, the current stage, and explicit parent IDs;
- stage-parented capabilities and acceptance requirements;
- exact identity requirements, with substitution allowed only when explicit;
- requirements mapped to capability IDs and any identity IDs;
- a proof scope and proof limits for every requirement;
- stable acceptance-step IDs, minimum evidence level, and `failing`, `blocked`, or `passing` status;
- evidence references with timestamps, exact step IDs, and exact identity IDs when applicable;
- counterevidence retained as `unresolved` or with a specific resolution;
- owner, reason, recovery trigger, and recovery action when blocked.

Every passing slice needs sufficient evidence for each step and identity it covers. A stage can complete only when its required capabilities have passing coverage and its required slices pass. The north star can be achieved only when every required stage completes. Evidence moves upward only through declared coverage; activity never propagates completion. Migrate legacy state before a new completion claim.

Never delete or weaken a capability or required item merely to make completion possible. Change acceptance only when the latest user instruction changes the outcome or current evidence disproves the requirement. A previously passing item must return to failing when its evidence is invalidated or contradicted.

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

Select the incomplete stage representing the largest verified constraint, then one non-passing acceptance ID within it. Record both IDs in both files. Choose the smallest end-to-end change or diagnostic that materially reduces that slice's gap.

Before expanding scope, answer internally:

1. Which acceptance ID does this action advance?
2. Which capability, delivery stage, and north star parent it?
3. What evidence makes it necessary now?
4. What result would disprove the approach?
5. What existing behavior must remain intact?

Also run an outcome-distance check: an intermediate artifact counts as progress only when it removes a named acceptance gap. Record which product capabilities the slice proves and its proof limits before treating it as acceptance evidence. After a rejected delegation or failed method, replan from the outcome and the remaining dependency graph instead of stopping or reporting the rejected method as the result.

Keep at most one unverified architectural layer in flight. A plan, scaffold, monitoring surface, or generated artifact is not a material slice unless it is itself the accepted outcome.

When attention wanders into add-ons, excessive research, tool exploration, orchestration, or polishing, return to the current acceptance gap. Preserve a useful off-path discovery without pursuing every branch, resume the smallest gap-reducing action, and do not rewrite the plan merely because attention wandered.

After a coherent verified slice, update both state files and use a focused Git commit when repository policy and the user's working tree permit it. Never stage unrelated user changes.

## Bound Autonomous And Recurring Work

Before work can outlive the turn or accumulate side effects, define a proportional operational envelope in `.codex/PROJECT_OUTCOME.md`:

- **Progress:** authoritative acceptance-linked state change, not checks, attempts, or unchanged health.
- **Identity:** stable idempotency key or state fingerprint so repeated conditions become no-ops.
- **Cadence:** mutate only on state transition or bounded retry eligibility.
- **Resources:** cap disk, files, calls, tokens, money, RAM, and concurrency; preserve a reserve.
- **Lifecycle:** bound retention and clean up after success, cancellation, crash, and startup.
- **Recovery:** define no-progress stop, owner, trigger, transition, restart behavior, and persistent safety-critical budget state.

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

Also detect execution-quality failures:

- **Analytical fixation:** improving the framework, explanation, or plan after enough clarity exists to act.
- **Restless activity:** tools, workers, files, or tokens grow without improved acceptance evidence.
- **Avoidant inaction:** uncertainty or discomfort postpones a safe authorized action.

Correct each by returning to the controlling capability and the smallest verified gap. When explaining success or failure, consider the environment, acting agent, tools and access, distinct efforts, and external conditions; do not assign total credit or blame to one model, worker, or intervention without evidence.

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
- a proof slice or add-on becomes the practical product outcome;
- a same-label alternative is treated as the explicitly named entity without equivalence proof;
- contradictory evidence is ignored, downgraded, or routed around;
- project state was loaded from a root whose declared markers do not match;
- the plan relies on stale summaries or assumptions;
- lower-level evidence is being reported as completion;
- a current action, slice, capability, or stage lacks an explicit parent;
- an action completes but its status leaks upward, or a child failure silently rewrites its parent;
- status language mixes product outcome, tooling state, model or restart state, and communication state;
- coordination costs more than its likely contribution;
- a user correction conflicts with the active slice;
- the user says the answer is confusing, repeats the same question, or has to translate the reply into simpler words;
- the same failure is approaching an unchanged third attempt.

Correct the state files first, then choose the next slice from the remaining verified gap. Do not preserve a bad plan by adding more rules, and do not swing to a full rebuild unless evidence requires it.

## Complete Or Block Honestly

Before claiming completion, run:

```powershell
python <skill-dir>/scripts/project_outcome.py completion --root <project-root>
```

Completion requires schema version 3, both project states `complete`, no current stage or slice, the north star `achieved`, every required stage `complete`, every required capability covered by passing slices, sufficient step and identity evidence, and no unresolved counterevidence. Slice completion does not mean stage completion; stage completion does not mean north-star achievement.

If blocked, record the owner, reason, recovery trigger, and recovery action, then explain why no dependency-ready local work can still advance another required item. Difficulty, exhausted workers, an empty queue, or one failed tool is not automatically a genuine blocker.

Communicate only material transitions using `Done / Active / Blocked / Next` when structure helps. Keep the user's outcome and evidence visible; omit routine narration and unchanged status.
