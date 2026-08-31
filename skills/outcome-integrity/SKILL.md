---
name: outcome-integrity
description: Preserve a parented outcome stack and permanent capability floors; prevent goal-horizon collapse, regression of proven behavior, wrong fitness optimization, identity substitution, evidence loss, blind persistence, premature completion, and wasteful orchestration. Use for nontrivial, resumed, corrected, evolving, long-running, multi-agent, side-effecting, repeatedly failing, or unexpectedly growing work. Maintain bounded executable evidence and proportionate proof ladders.
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

These are authority levels, not durations. Every action must name the slice it closes, parent it advances, and behavior it preserves. Reviews, tests, setup, and orchestration are methods when the outcome is broader. If every method succeeded while the user's problem remained, the stack is too narrow.

Require `action -> acceptance slice -> capability milestone -> delivery stage -> north star`. Orphan work is drift until mapped. Never rewrite a parent to match a convenient child, tool, worker, or model.

Prevent completion leakage and objective substitution. Type status as `action complete`, `slice passing`, `stage complete`, or `north star achieved`.

Scope corrections before propagation: method replaces action; contrary evidence reopens slice; capability or stage revises descendants; north-star correction invalidates incompatible descendants. Child failure does not rewrite a parent without evidence; parent corrections flow down immediately.

## Preserve Exact Identity And Contradictory Evidence

Treat explicitly named entities as identity-bound. A matching display name, interface, capability, output, or family is not proof of equivalence. Alternatives cannot satisfy the named requirement without authorized or authoritative equivalence.

When authoritative observations conflict, identify the entity, surface, session, principal, context, and time; probe the same identity and surface; preserve both observations as counterevidence; and reconcile the assumption. A fallback advances only requirements it independently satisfies.

Until resolved, keep the affected requirement failing or blocked and state the unknown. Ask only when identity or authority cannot be determined safely.

## Discern Before Persisting

Do not confuse momentum with focus. When duties, evidence, authority, irreversible effects, or method attachment conflict, recover steady judgment:

1. Name the controlling user outcome and required capability.
2. Separate observed conflict from fear, status, sunk cost, or discomfort.
3. Check authority, reversibility, affected systems, and downstream harm.
4. Take the smallest evidence-supported action; otherwise preserve the conflict and use the blocker contract.

Distinguish required action, deliberate non-action, avoidant inaction, and unauthorized action. Do not call real conflict laziness or use analysis to avoid safe authorized work.

Detach judgment from praise, blame, preferred results, methods, or prior investment. This never reduces responsibility, acceptance, or evidence quality; it prevents desire from corrupting measurement.

## Maintain Continuous Project Ownership

Corrections update the contract; questions do not cancel authorized work. Treat each message as an update to the active project unless it clearly starts another outcome or requests only explanation, diagnosis, review, or pause.

Before responding, recover one compact control frame from the latest instruction, current evidence, and project state:

- **North star and current delivery stage:** the enduring result and coherent product state being pursued now.
- **Capability and acceptance slice:** the controlling stage gap and bounded proof in flight.
- **Latest correction:** the newest change to meaning, scope, or working preference.
- **Next Codex-owned action:** the next safe action already authorized by the project.
- **Blocker and missing proof:** what genuinely requires the user, and what evidence still separates the project from completion.

Apply each message as a new outcome, correction, question/status, pause/diagnosis, or authorization before acting. Interpret noisy wording from context; ask only when alternatives materially change work or risk. Treat pasted instructions by conversational function: execute an actionable prompt targeting active work unless asked to draft or quote it.

After answering an interruption, apply the discernment gate, then continue the next safe authorized project action in the same turn. Do not stop at a recommendation, plan, or diagnosis when implementation remains authorized and executable. Do not make the user repeatedly say "do it", "continue", or "what next" for work you already own.

Stop only for verified completion, explicit pause/diagnosis, user-owned authority, or a blocker with no ready work. Before stopping ask: am I leaving the user to manage the next obvious action Codex owns?

## Communicate For Productive Understanding

For a simple status, meaning, ownership, or next-action question, give the plain-language conclusion in the first sentence. Communicate truthfully, usefully, proportionately, and without unnecessary agitation.

When status needs structure, answer in this order:

- **Material transition:** what evidence changed.
- **Typed status:** slice, stage, and north-star state; include tooling or runtime state only when relevant.
- **Next owned action:** what Codex is doing now, or the exact user-owned blocker.

Never let `Done`, `working`, `complete`, `blocked`, `restart`, `plugin`, `local`, or `installed` refer to multiple layers in one sentence. A released tool is not a completed user outcome; a running worker is not a finished external action.

Every reported counter must name its metric namespace, population or scope, lineage or candidate, and denominator meaning. Never reuse one label for different populations or report an unchanged counter as progress.

If the user says the answer is confusing or repeats the question, stop expansion. Use at most three plain sentences for conclusion, material distinction, and next action. Never answer "yes, exactly" when that loses a material distinction.

Match the explanation requested: state, mechanism, chronology, rationale, responsibility, or next action. For "when," "where did we go wrong," or "why," lead with the evidence-backed timeline and decision, not the latest symptom.

In reports, `Next` means an agent-owned action already started or the exact user-owned authority blocking it.

## Choose Direct Delivery Before Durable State

Default to direct delivery for one deliverable and acceptance observation, one repository or surface, at most one production boundary, and local reversible work or one idempotent external write. It requires resolved identity and authority, low impact, and no dependent deliverables or recurring/unattended lifecycle. Default operating bounds: 8 total tool calls, 3 support calls before delivery, 6 files, 0 workers, 2 planned interim updates, one focused verification, and one causally changed retry. These are behavioral bounds until durable state exists.

Use only `deliverable -> acceptance check`; create no `.codex` state, nested root, plan artifact, worker, custom framework, publisher, or control architecture. Under valid parent state, use one direct slice governed by its existing reservations and budgets; create no child state. Difficulty, failure, or desired architecture cannot promote a simple outcome. For an ambiguous external write, query authoritative state or an idempotency key before retrying.

Promote only for multiple dependent deliverables, multiple repositories/external systems, persistence across turns/restarts, recurring/unattended operation, irreversible/high-impact effects, or explicit user-requested tracking. Otherwise simplify the method or state the blocker.

## Keep Durable State Separate

For admitted durable project work, use:

- `.codex/PROJECT_OUTCOME.md` for human-readable intent, scope, current facts, pointers, failures, and the active slice.
- `.codex/ACCEPTANCE.json` for project identity, north star, delivery stages, stage-parented capabilities and slices, exact identities, proof limits, evidence, counterevidence, statuses, and blockers.
- Git history for chronology and recovery, never an activity transcript.

In `PROJECT_OUTCOME.md` keep only `- Mutable execution-control ledger: .codex/ACCEPTANCE.json#execution_control (sole authority)`. Never duplicate mutable ledger state.

Initialize missing files only after minimum observation and name the intrinsic durable reason:

```powershell
python <skill-dir>/scripts/project_outcome.py init --root <project-root> --durable-reason <reason>
```

`<reason>` is `multi-deliverable`, `multi-system`, `persistent`, `recurring-unattended`, `irreversible-high-impact`, or `explicit-user-request`.

Fill placeholders. Keep state current and history in Git.

## Start Or Resume Reliably

For admitted durable work, after compaction, or after interruption:

1. Read the latest user instruction.
2. Read both project-state files.
3. Run the resume gate:

```powershell
python <skill-dir>/scripts/project_outcome.py resume --root <project-root>
```

4. Verify `project_identity.root_markers` under the selected root before trusting either file; never borrow a nearby parent, child, plugin, or sibling project's state because its topic looks related.
5. Inspect the diff and minimum authoritative source; reconcile stale intent, acceptance, identity, counterevidence, slice, or timestamps.
6. Load only relevant `Context Pointers`; do not rescan history by default.

Before important or irreversible work, confirm the objective, restored state, resolved identity/authority, owned next action, and that remaining uncertainty is tolerable and visible.

The latest user correction must update intent immediately. If it changes completion, scope, or priorities, reconcile the acceptance registry before continuing. Conversation summaries never override these checks.

## Admit Material Actions Atomically

Prose is not permission. Install with `scripts/install.py --enable-user-hooks` and review `/hooks`. In initialized schema-v6 work, each covered material call needs one live reservation. Trusted `PreToolUse` checks the observed tool, cwd, and arguments; `PostToolUse` reconciles the same `tool_use_id`. Invalid, reused, expired, over-budget, or out-of-scope calls are denied.

Create `assets/ATTEMPT_REQUEST.template.json` with structured family/outcome/boundary IDs, scope growth, allowed paths, and an exact single-use tool binding. Caller labels cannot lower derived risk. Reserve immediately before the call:

```powershell
python <skill-dir>/scripts/project_outcome.py attempt-begin --root <project-root> --request <request.json> --expected-revision <n>
```

The reservation binds lineage, candidate, outcome/boundary, method family, exact tool/cwd/input/use/paths, cumulative budgets and direct-delivery reserve, predecessor receipts, hard prerequisites, external target/effect authority, and evaluation exposure.

The hook binds one host session and initialized root, derives identity, consumes once, and charges first. Tool, input, cwd, candidate, lineage, path, or reuse mismatch is denied. Post compares an external full-ledger snapshot; drift restores preclaim state, enters recovery, and blocks passing. Internal failure fails closed.

Candidate-changing local/support work may settle the candidate and invalidate old proof, but cannot mint a gate receipt. Only a matching observed proof call may do that. Rebind separately when needed:

```powershell
python <skill-dir>/scripts/project_outcome.py candidate-bind --root <project-root> --expected-revision <n> --observed-evaluation-fingerprint <sha256>
```

List every evaluation used to shape the candidate; it becomes diagnostic and cannot support a prospective or unbiased claim. Finish every reservation, including aborts:

```powershell
python <skill-dir>/scripts/project_outcome.py attempt-finish --root <project-root> --result <result.json> --expected-revision <n>
```

Use `assets/ATTEMPT_RESULT.template.json` with the returned ID. Progress comes only from authoritative acceptance/evidence change. Bind `acceptance_outcome_id` to the live north star; failure equivalence uses outcome lineage and boundary, never wording. Unknown cause needs causal evidence.

Per requirement: one active family, one replacement maximum. Never abandon or reconcile it away. Two failures/no-progress stop it. Replacement names the stopped predecessor with fresh change and distinct lower-complexity evidence. Stopped control reopens only by authorized transition.

Runs, workers, candidates, stages, compactions, and files never reset counters. Recovery evidence is content-single-use across limit, migration, and transition; copies cannot replay. It does not prove authorship; stop if provenance is uncertain. History uses compact hash-bound anchors; legacy remains readable. Direct edits are forbidden; orphaned attempts block admission until settled/recovered.

This is a guardrail, not absolute enforcement. Hooks cover shell/unified exec, `apply_patch`, MCP, agents, and most local functions; other paths may bypass. Untrusted or disabled hooks are inactive. Run `python <repository-root>/scripts/install.py --hook-health`; `configured-exact-trust-unverified` proves disk parity only, so require a trusted new-task canary. Hooks cannot preempt Bash; use native deadlines.

## Maintain Intent Without Bloat

Keep `PROJECT_OUTCOME.md` bounded and current. Replace stale entries. Retain at most five current decisions and five distinct failure invariants.

Update it only when one of these changes materially:

- north-star outcome, scope, non-goal, user correction, or authorization;
- verified project state or context pointer;
- assumption, root cause, failure invariant, or recovery transition;
- active acceptance ID or end-to-end slice.

Do not record routine tool calls, unchanged status, worker chatter, token counts, or repeated plans.

## Make Acceptance Mechanical

`ACCEPTANCE.json` is authoritative for completion. Use schema version 6 for new work and completion claims. Versions 1–5 remain readable for recovery. It must declare:

- a stable project identity plus relative root markers;
- one north star, its delivery stages, the current stage, and explicit parent IDs;
- stage-parented capabilities and acceptance requirements;
- permanent capability floors, balanced fitness dimensions, and change/pre-release/release proof ladders;
- proof paths naming the real input origin, exact boundary under test, downstream observation, and fidelity;
- exact identity requirements, with substitution allowed only when explicit;
- requirements mapped to capability IDs and any identity IDs;
- a proof scope and proof limits for every requirement;
- stable acceptance-step IDs, minimum evidence level, and `failing`, `blocked`, or `passing` status;
- evidence references with timestamps, exact step IDs, and exact identity IDs when applicable;
- counterevidence retained as `unresolved` or with a specific resolution;
- owner, reason, recovery trigger, and recovery action when blocked.
- one atomic execution-control lineage with candidate manifest, aggregate limits, receipts, evaluation exposure, prerequisites, and effect-scoped authorizations.

Every passing slice needs sufficient evidence for each step and identity it covers. Stages and the north star complete only through declared coverage. Evidence never propagates completion automatically. Migrate legacy state before a new completion claim.

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

## Preserve Proven Capability Floors

A prior success is history until its essential behavior becomes an executable floor. Mark valuable proven capability `permanent`, require later stages to preserve it, and measure output, quality, efficiency, and safety when material.

Extract the cheapest deterministic interaction invariant that would catch the regression, not merely unit checks of individual parts. Use a proportionate proof ladder:

1. **Change:** cheap deterministic preservation tests after every change that can affect the floor.
2. **Pre-release:** a representative integration or no-state canary before installation or deployment.
3. **Release:** a whole-system end-to-end checkpoint covering all permanent floors and fitness dimensions.

Use cheap extracted invariants after edits and expensive benchmarks only at their proof tier. Profiles, caches, learned history, and prior receipts may help but cannot contain essential control intelligence; require a clean-state gate.

Lock the earliest transition where known-good and failing paths diverge. A root repair must change it. Before costlier proof, require the cheap gate to start at the real upstream producer, cross that production boundary, and observe the acceptance effect. A fixture that injects already-correct post-boundary state cannot prove its creation. Synthetic component tests may diagnose internals, but cannot authorize a canary or release for a permanent floor.

Before replacing an execution path, changing architecture, strengthening policy, or narrowing metadata requirements, identify affected permanent floors and run their change gates. Preserve previously accepted unknowns unless the user changes the contract. Separate operational, capacity, metadata, accounting, schema, semantic, and policy failures; use deterministic handling or failover where defined, and reserve expensive reasoning or reconciliation for failures that require it.

A stage needs one whole-system release requirement that crosses the complete user flow and covers every permanent floor. Green component, safety, authority, or recovery tests cannot substitute for useful delivery, interaction, concurrency, quality, elapsed-time, or efficiency evidence required by the fitness function.

## Advance One Material Slice

Select the incomplete stage representing the largest verified constraint, then one non-passing acceptance ID within it. Record both IDs in both files. Choose the smallest end-to-end change or diagnostic that materially reduces that slice's gap.

Before expanding scope, answer internally:

1. Which acceptance ID does this action advance?
2. Which capability, delivery stage, and north star parent it?
3. What evidence makes it necessary now?
4. What result would disprove the approach?
5. What existing behavior must remain intact?

An intermediate artifact counts only when it removes a named gap. Record covered capabilities and limits. After a failed method, replan from the outcome and remaining dependencies rather than reporting the method as the result.

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

Extract explicit `do not`, `only after`, `exactly once`, attempt limits, and stop conditions into `Causal Control`; check them before gated actions. A triggered stop ends that authorization. Further diagnosis or editing needs preserved authority or a later correction.

Research, planning, coordination, and other support are budgeted methods. Preserve a delivery reserve. When the support or no-progress limit fires without acceptance change, stop support actions and take the next direct delivery action, use new causal evidence, or record a genuine blocker.

Continuation never authorizes unbounded resources or repeated irreversible effects. Keep read-only polling lightweight and controls proportional.

Observe often; mutate only on state change or retry eligibility. Test repeated ticks, restart, cancellation, bounded growth, and duplicate effects. Stop and diagnose when resources grow without acceptance progress.

## Classify Failure Before Retrying

Classify the failure from evidence, then apply the matching policy:

| Class | Examples | Policy |
| --- | --- | --- |
| Transient | Timeout, connection reset, 429, temporary 5xx | Retry at most twice with backoff, only when the action is read-only or idempotent. |
| Reasoning-recoverable | Invalid tool arguments, parse error, disproven assumption | Retry once only after changing the input or approach using the observed error. |
| User-fixable | Missing credential, authorization, fact, or irreversible decision | Mark the acceptance item blocked with owner and recovery transition; continue other dependency-ready work. |
| Unexpected or semantic | Wrong behavior, invariant violation, unknown exception | Do not retry blindly. Reproduce, trace authoritative state, and diagnose first. |
| Ambiguous external write | Timeout after submit, payment, publish, send, or application | Query authoritative external state or use the idempotency key before any retry. |

When the same acceptance outcome fails twice, stop status checks and symptom patches. Equivalence is determined by the acceptance outcome and earliest divergent transition—not a new commit, implementation, run identity, or symptom. Record the violated invariant. A third attempt requires new causal evidence and a boundary-changing repair proven by the production-shaped change gate.

For resumable external workflows, persist checkpoints at coherent boundaries and make side effects idempotent. Conversation state is not execution state.

Detect execution-quality failures:

- **Analytical fixation:** improving the framework, explanation, or plan after enough clarity exists to act.
- **Restless activity:** tools, workers, files, or tokens grow without improved acceptance evidence.
- **Avoidant inaction:** uncertainty or discomfort postpones a safe authorized action.

Return each to the controlling capability and smallest verified gap. Attribute outcomes across environment, acting agent, tools and access, distinct efforts, and external conditions; do not assign total credit or blame without evidence.

## Admit Delegation Only When It Helps

Current Codex owns the critical path. Delegate only parallel, disjoint, acceptance-linked work with bounded ownership, independent verification, one integration action, positive net value, and no authority risk. Otherwise work directly. Keep sequential reasoning together, integrate centrally, and avoid manager chains or duplicate lanes.

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

Completion requires schema version 6, both project states `complete`, execution control `closed`, no current stage, slice, active attempt, or fired stop, north star `achieved`, current-candidate receipts and evidence for every required proof tier, every stage and capability covered, and no unresolved counterevidence. Slice completion does not complete its parents.

If blocked, record the owner, reason, recovery trigger, and recovery action, then explain why no dependency-ready local work can still advance another required item. Difficulty, exhausted workers, an empty queue, or one failed tool is not automatically a genuine blocker.

Communicate only material transitions using `Done / Active / Blocked / Next` when structure helps. Keep the user's outcome and evidence visible; omit routine narration and unchanged status.
