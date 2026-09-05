---
name: outcome-integrity
description: "Preserve outcomes for explicitly admitted durable work: recurring or unattended workflows, high-impact external effects spanning retries or restarts, or work the user explicitly asks to track durably. Do not invoke for ordinary implementation, diagnosis, local reversible edits or tests, a single bounded delivery, or merely because work is complex, resumed, multi-agent, or failing."
---

# Outcome Integrity

Keep the user's real outcome authoritative without turning the control system into the work. This skill is an optional durable-work discipline, not a prerequisite for normal delivery.

## Route To Direct Delivery First

Use direct delivery for ordinary implementation, diagnosis, review, research, editing, testing, and one bounded external action. This remains true when the repository already contains `.codex` files.

The direct lane is:

`deliverable -> one proportionate acceptance check`

On this lane:

- create no Outcome Integrity state, binding, migration, attempt, receipt, canary, worker, framework, or control-plane artifact;
- do not run `resume`, `validate`, or `completion` merely because state files exist;
- do not require an atomic claim for reads, local reversible edits, local commands, tests, or support tools;
- do not ask for an exact approval unless the requested action itself crosses an external, irreversible, costly, or otherwise user-owned boundary;
- after answering a question or correction, continue safe work already authorized instead of making the user repeat "do it.";

Complexity, a failure, a resumed conversation, multi-agent work, or an attractive architecture does not by itself justify durable control.

A later external step does not put earlier local diagnosis, preparation, or tests under durable control. A project-specific compatibility controller or historical attempt limit cannot override this boundary. When its bookkeeping rejects local work, continue that work directly without repairing the ledger first.

## Admit Durable Control Narrowly

Use durable state only when at least one intrinsic outcome property requires it:

- recurring or unattended execution;
- effects that must remain exactly-once across retries, turns, or restarts;
- dependent delivery across multiple systems that cannot be safely reconstructed;
- irreversible or high-impact work needing a persistent effect ledger; or
- an explicit user request for durable Outcome Integrity tracking.

Name the admission reason. If no reason applies, remain on the direct lane. Existing `.codex` files are historical data, not automatic custody of the current task.

For admitted work, keep one compact parent chain:

`next action -> acceptance slice -> capability -> delivery stage -> north star`

Use `.codex/PROJECT_OUTCOME.md` for bounded human-readable intent and `.codex/ACCEPTANCE.json` for mechanical acceptance and execution control. Use the packaged templates and CLI instead of hand-editing the ledger.

Keep this sole mutable-ledger pointer in `PROJECT_OUTCOME.md`: `- Mutable execution-control ledger: .codex/ACCEPTANCE.json#execution_control (sole authority)`.

```powershell
python <skill-dir>/scripts/project_outcome.py init --root <project-root> --durable-reason <reason>
python <skill-dir>/scripts/project_outcome.py resume --root <project-root>
```

An exact activation applies only to that durable task and session. A normal tool call, cwd, target path, chat message, or inert canary must not create a session binding.

## Keep The Control Plane Off The Critical Path

Control work is support, never product progress. Apply this circuit breaker:

1. If two consecutive control-plane actions produce no user-visible delivery evidence, stop repairing, migrating, resealing, rebinding, or canarying the control plane in the product task.
2. Continue authorized local reversible work directly.
3. Keep only the real external or irreversible effect blocked if its authority or idempotency remains unresolved.
4. Report one concise control warning; do not manufacture another authorization request from control metadata.

Never perform revisions or migrations only to make Outcome Integrity accept its own prior state. Repair the skill or ledger only when that repair is itself the user's requested outcome or is strictly necessary before a real protected effect.

No provider call, token count, safety check, migration, receipt, hook repair, or canary is product progress unless it changes the user's accepted outcome.

## Optional Hook Boundary

The user-level hook is opt-in. Its job is narrow:

- protect direct mutation of Outcome Integrity's authoritative state;
- check admission for clearly external, irreversible, or unattended effects when optional enforcement is enabled; and
- consume and settle the one exact tool call already reserved by an active attempt.

It must bypass ordinary reads, local reversible edits, local shell commands, tests, and support tools, even in an initialized or explicitly bound root. Root ambiguity, a stale binding, or invalid project state must not block those local reversible calls. It may still fail closed for a protected effect or direct ledger mutation.

A hook refusal blocks only the protected effect. It does not admit the current task to durable control or require local work to enter custody. Historical initialization alone is never admission.

Provider and costly execution is protected only from narrow host-visible facts: a provider/cost marker paired with an execution token in the tool name, a direct provider CLI or recognized provider API URL, or a directly invoked Python/Node runner whose basename contains both provider and execution markers. Do not infer risk from arbitrary prompt text or broadly classify generic `create`, `generate`, Python, or Node calls. If an admitted durable task's protected effect uses a renamed, wrapped, or otherwise opaque runner, reserve that exact call because the hook cannot infer hidden script behavior. Ordinary local runners remain on the direct lane.

No binding is the expected result of a direct-lane canary. Only an exact control-plane activation may create one. Hook installation, disk parity, trust, binding, and a claimed protected call are distinct states; never report one as proof of another.

## Protect Real Effects Without Approval Churn

For a protected external effect:

1. Confirm the exact action, target, principal, and effect authority from the applicable user instructions. Earlier authorization remains applicable unless superseded, exhausted, or outside the current action's scope.
2. Use an idempotency key or query authoritative external state before retrying an ambiguous write.
3. If durable exact-once enforcement is necessary, reserve the one actual call immediately before it.
4. Consume external-effect authorization at actual dispatch and settle the call once; local preparation alone does not consume it.
5. Never turn a failed control-plane operation into permission to rerun the external effect.

Complete local input validation and other reversible preparation before reserving the external call. Track preparation, actual dispatch, and an unknown dispatch outcome separately; creating a task or a local claim is not evidence that the provider executed.

When authoritative evidence proves dispatch never occurred, repair local preparation and continue the still-authorized action within its original target, effect scope, budget, and any candidate the user explicitly fixed or sealed. Do not require another authorization solely because local bookkeeping called the preparation an attempt or changed an internal fingerprint. If the user explicitly forbade restarting the entire sealed package, that wider restriction still applies. A changed user-specified target or sealed candidate also requires its own authority.

For a dispatched call or an unknown dispatch outcome, preserve the no-rerun restriction and query authoritative state or the idempotency key. Missing logs or receipts alone do not prove that no external effect occurred. Never clear or recycle a consumed or ambiguous claim merely to resume work.

```powershell
python <skill-dir>/scripts/project_outcome.py attempt-begin --root <project-root> --request <request.json> --expected-revision <n>
python <skill-dir>/scripts/project_outcome.py attempt-finish --root <project-root> --result <result.json> --expected-revision <n>
```

Use `assets/ATTEMPT_REQUEST.template.json` and `assets/ATTEMPT_RESULT.template.json`. The reservation binds the candidate, outcome, boundary, exact tool input, allowed paths, budgets, prerequisites, and any external target authorization.

## Preserve Outcome And Evidence

The latest explicit user correction outranks prior plans and state. Current authoritative runtime or project evidence outranks summaries and worker reports. Treat named accounts, tools, providers, repositories, files, sessions, and targets as exact identities; a convenient alternative is not proof of equivalence.

Distinguish:

- action completed;
- acceptance slice passed;
- delivery stage completed; and
- north star achieved.

Tests, hooks, receipts, workers, provider inactivity, and elapsed time are not substitutes for the required user-visible outcome. Keep contradictory evidence visible until reconciled on the same identity and surface.

For admitted durable work, validate after a material state transition and use completion only for a real completion claim:

```powershell
python <skill-dir>/scripts/project_outcome.py validate --root <project-root>
python <skill-dir>/scripts/project_outcome.py completion --root <project-root>
```

Do not weaken requirements or capability floors to obtain a green result.

## Retry And Delegation Limits

Classify failure before retrying:

- transient and idempotent: at most two bounded retries with backoff;
- reasoning-recoverable: one changed-input or changed-approach retry;
- user-owned authority or decision: block only the affected effect and continue other ready work;
- semantic or unexpected: diagnose the earliest divergent transition before another attempt;
- ambiguous external write: query authoritative state before retrying.

After two equivalent failures or no-progress attempts, stop that method family. A replacement needs new causal evidence and a materially changed boundary; a new revision, worker, prompt, or authorization sentence is not a new method.

Delegate only parallel, disjoint work whose expected contribution exceeds coordination cost. Current Codex remains on the delivery-critical path.

## Communicate Proportionately

Lead with the product outcome and the material evidence change. Separate product state from hook, installer, model, restart, and communication state. If the user says the process is confusing or obstructive, stop expanding the framework and return to the smallest authorized delivery action.

When genuinely blocked, name the exact user-owned decision or external fact required. Never use Outcome Integrity's own bookkeeping as the reason to stop local work.
