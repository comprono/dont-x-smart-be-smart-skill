# Don't X Smart, Be Smart Skill

[![Validate](https://github.com/comprono/dont-x-smart-be-smart-skill/actions/workflows/validate.yml/badge.svg)](https://github.com/comprono/dont-x-smart-be-smart-skill/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A community Codex skill for keeping long, complicated project work aligned with the user's real outcome.

Long agent sessions can drift after context compaction, promote an add-on into the main objective, mistake momentum for focus, fixate on a method, confuse activity with progress, repeat the same failed patch, or spend more tokens coordinating work than completing it. This repository provides three layers:

1. A concise global Codex rule block that activates outcome integrity for nontrivial project work.
2. The `outcome-integrity` skill, which maintains bounded human intent and machine-verifiable acceptance inside each active project.
3. An optional synchronous Codex hook that denies covered material tool calls unless the real tool proposal consumes an exact, bounded schema-v6 reservation.

`PROJECT_OUTCOME.md` preserves the north star, current stage, active slice, user intent, causal boundary, stop constraints, facts, failures, and next action. Schema-v6 `ACCEPTANCE.json` owns the parent chain plus permanent capability floors, balanced fitness dimensions, proof ladders, exact identities, evidence, and a candidate-bound atomic attempt ledger. Git owns history; neither state file is an activity transcript.

The human file points to, but never duplicates, mutable ledger state: `- Mutable execution-control ledger: .codex/ACCEPTANCE.json#execution_control (sole authority)`.

## What It Prevents

- Treating a review, demo, test, pilot, plan, or orchestration step as the product outcome when the user's real goal is broader.
- Treating a matching display name or capability as proof that an explicitly named entity is the same one.
- Routing around contradictory evidence or presenting a fallback as resolution.
- Resuming from a nearby parent, child, plugin, or sibling project's state because its topic looks related.
- Continuing a stale plan after the user corrects it.
- Continuing a stale task contract after a correction or stopping merely because one worker or method was rejected.
- Letting unattended loops consume storage, quota, money, or memory without verified outcome progress.
- Treating tests, workers, tool calls, or service health as proof of the requested outcome.
- Repeating the same symptom patch after two failed attempts.
- Retrying semantic failures as though they were transient network errors.
- Letting dashboards, orchestration, safety machinery, or documentation replace the real objective.
- Losing key intent and failed approaches after context compaction.
- Marking requirements complete without sufficient evidence.
- Creating project-management overhead for trivial work.
- Burying a simple answer under investigation detail, jargon, or an unnecessary plan.
- Mixing product progress, plugin or tooling state, model or restart state, and communication state in one ambiguous status.
- Continuing an explanation loop after the user says the answer is confusing or restates it more simply.
- Treating every correction or question as a new task and losing ownership of the active project.
- Stopping at advice, analysis, or a plan and forcing the user to repeatedly say "do it", "continue", or "what next".
- Persisting blindly when duties, evidence, authority, or irreversible consequences conflict.
- Letting attachment to a preferred result, tool, worker, or architecture distort evidence.
- Losing focus through analytical fixation, restless activity, or avoidant inaction.
- Assigning total credit or blame to one model when environment, access, tools, efforts, and external conditions also caused the result.

## Install

Requires Python 3.11 or newer.

```powershell
git clone https://github.com/comprono/dont-x-smart-be-smart-skill.git
cd dont-x-smart-be-smart-skill
python scripts/install.py --enable-user-hooks
```

The installer:

- copies the skill to `~/.codex/skills/outcome-integrity`;
- adds or updates one managed block in `~/.codex/AGENTS.md`;
- preserves unrelated existing global instructions;
- is safe to run again when updating the skill.

The recommended command opts into mechanical interception for initialized Outcome Integrity projects. If you deliberately want the skill and global rules without a tool-dispatch hook, run `python scripts/install.py`; that mode remains advisory at the execution boundary.

```powershell
python scripts/install.py --enable-user-hooks
```

This transaction installs the same skill/rules plus owned synchronous `PreToolUse` and `PostToolUse` handlers in `~/.codex/hooks.json`, preserving unrelated hook configuration. Codex does not run a new or changed non-managed hook until you review and trust its exact definition. Start a new task, open `/hooks`, inspect the Outcome Integrity handlers, and trust them. Until that is done—or when hooks are disabled—the installer reports the protection as inactive.

Check the installed definition at any time:

```powershell
python scripts/install.py --hook-health
```

The health result distinguishes absent, disabled, stale, and exact configuration. `configured-exact-trust-unverified` means the runtime, core, sidecar, and hashes match on disk; it is deliberately not reported as active enforcement. Only a trusted hook plus a fresh task canary that observes an actual allow or denial proves live dispatch.

To remove only the owned handlers while preserving the skill, global rules, and unrelated hooks:

```powershell
python scripts/install.py --disable-user-hooks
```

Start a new Codex task after installation. Restarting the Codex application is the safest way to refresh skill discovery.

To install without changing global instructions:

```powershell
python scripts/install.py --skip-global-rules
```

## How It Works

Before substantive work, Codex forms a parented outcome stack: enduring north star, current delivery stage, capability milestone, acceptance slice, and next action. Every action must close a named descendant gap. A passing slice cannot complete its stage, and a complete stage cannot achieve the north star without declared coverage.

Accepted behavior that later work must not break becomes a permanent capability floor. Each floor gets a cheap deterministic change gate, a representative pre-release canary, and a whole-system release checkpoint. The cheap gate must start at the real upstream producer and cross the same decision boundary; a fixture cannot inject the already-correct state whose creation is under test. The fitness function keeps useful output, quality, efficiency, and safety visible together, while optional profiles, caches, and learned history must pass a clean-state independence gate.

During an active project, Codex also maintains a compact control frame containing the current deliverable and stage, latest correction, next Codex-owned action, genuine blocker, and missing completion evidence. Questions and corrections update that project rather than silently ending it. After answering an interruption, Codex discerns whether duties, evidence, authority, or irreversible effects conflict, then resumes the next safe authorized action instead of waiting for another "do it" instruction.

Focus is implemented as repeated return, not forced concentration. When attention wanders into add-ons, excessive research, tool exploration, orchestration, or polishing, Codex preserves useful discoveries but returns to the current verified gap. It distinguishes analytical fixation, restless activity without evidence progress, and avoidant inaction. Detachment from a preferred method never weakens responsibility for the product outcome or its evidence.

For a simple question—such as whether one copy is newer, what a result means, or what happens next—Codex answers with a direct plain-language conclusion first. Communication must be truthful, useful, proportionate, and free of unnecessary agitation. A user should not need to simplify their own question to get the actual answer.

For status updates, Codex names the layer being discussed. Package, installer, model, restart, worker, and project-outcome states are not interchangeable. If an explanation confuses the user or the same question repeats, Codex treats that as drift and returns to a short conclusion, distinction, and next-action frame before continuing.

Before recurring or unattended work is enabled, Codex records a proportional operational envelope: progress identity, idempotency, retry cadence, resource cap and reserve, retention, cleanup, no-progress stop, and restart behavior. Read-only bounded polling stays lightweight; accumulating side effects fail closed when evidence stops improving.

Explicitly named people, accounts, tools, providers, runtimes, repositories, credentials, sessions, systems, files, and resources remain distinct until substitution is authorized or equivalence is proven. Conflicting observations are retained as counterevidence and reconciled on the same identity and access surface; a convenient alternative does not erase the conflict.

For a nontrivial project, Codex reads or creates:

```text
<project-root>/.codex/
├── PROJECT_OUTCOME.md
└── ACCEPTANCE.json
```

Codex first verifies that declared root markers belong to the selected project, then reconciles both files with the latest user instruction and current evidence. The newest explicit correction wins. Contradictions remain visible until resolved. Add-ons and proof slices stay separate from the product outcome.

Project state updates only after a material transition: changed intent, verified progress, a disproven assumption, a confirmed root cause, a changed recovery path, or a new current slice. Routine status and tool activity are excluded.

Resume and completion are executable gates:

```powershell
python ~/.codex/skills/outcome-integrity/scripts/project_outcome.py resume --root .
python ~/.codex/skills/outcome-integrity/scripts/project_outcome.py completion --root .
```

Material calls are executable gates. A JSON request binds the current slice, candidate, lineage, live north-star outcome, structured boundary, allowed paths, one exact tool claim, prerequisites, evaluation exposure, cumulative budgets, and any target/effect authorization. Recovery fields are null for an initial method. One requirement can have only one active family; it cannot be abandoned, and a stopped family permits at most one evidence-backed replacement naming that predecessor with fresh method-change evidence and a distinct lower-complexity comparison. When the optional hook is trusted, it checks the host-observed tool, cwd, and arguments at `PreToolUse`, consumes the claim once, and charges before execution. `PostToolUse` verifies the same call against an external full-ledger preclaim snapshot before a passing finish; unexpected state drift restores the preclaim ledger and stops for recovery:

```powershell
python ~/.codex/skills/outcome-integrity/scripts/project_outcome.py attempt-begin --root . --request attempt.json --expected-revision 0
python ~/.codex/skills/outcome-integrity/scripts/project_outcome.py attempt-finish --root . --result result.json --expected-revision 1
```

Copy `assets/ATTEMPT_REQUEST.template.json` and `assets/ATTEMPT_RESULT.template.json` rather than inventing either contract. The begin response supplies the exact `attempt_id`; actual tool/input fingerprints and structured failure identities are derived, not caller-chosen.

New runs, workers, candidates, stages, compactions, recreated files, changed wording, or renamed boundaries do not reset cumulative tool/support/method-family counters. Candidate changes clear proof receipts while preserving usage, and evaluations used to shape a candidate become diagnostic. Local candidate-changing work cannot mint proof. State reconciliation cannot rename away active or stopped family history, and stopped control reopens only through the separately authorized state-transition path. Recovery authorization content is single-use across limit extensions, migrations, and state transitions even when copied to a new path or ID. New recovery history uses compact hash-bound usage anchors so enforcement state grows with events rather than repeatedly embedding the entire ledger.

You can also invoke the skill explicitly:

```text
Use $outcome-integrity. Recover the project's real outcome and continue from verified state.
```

## Failure Circuit Breaker

Failures are classified before retrying. Transient failures get at most two bounded retries; reasoning failures require a changed input or approach; user-fixable failures receive an owner and recovery transition; semantic and unexpected failures require diagnosis. Ambiguous external writes must be checked through authoritative state or an idempotency key before retrying.

After the same structured acceptance outcome and boundary fail twice, the ledger stops even if code, tool, worker, run, or wording changed. Two failures or bounded no-progress inside one method family stop that family even when boundaries differ. A family cannot be abandoned while active. Continuing permits one evidence-backed replacement only and requires causal evidence, an explicit lower-complexity alternative comparison, and a production-shaped gate for the changed boundary; failure of that replacement ends the method path for the requirement.

## Delegation Gate

Delegation is admitted only when work is parallel, disjoint, tied to an acceptance ID, independently verifiable, integration-bounded, and cheaper than direct execution. Sequential critical-path reasoning stays with the current Codex agent.

## Validation

```powershell
python -m unittest discover -s tests -v
```

The tests cover packaging, token bounds, installation, legacy recovery, parent integrity, permanent floors, balanced fitness, production-path fidelity, proof-tier strength, clean-state independence, whole-system gates, exact identities, counterevidence, blockers, and evidence-backed completion.

## Design Basis

The design incorporates published patterns from [Anthropic's long-running agent harness](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents), [OpenAI's harness engineering](https://openai.com/index/harness-engineering/), [Manus context engineering](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus), [Microsoft PROBE](https://www.microsoft.com/en-us/research/publication/debugging-the-debuggers-failure-anchored-structured-recovery-for-software-engineering-agents/), and [LangGraph durable execution guidance](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph).

## Guarantee Boundary

No prompt, skill, or user hook can guarantee every response or intercept every platform path. [Codex hook documentation](https://learn.chatgpt.com/docs/hooks#tool-coverage) covers shell/unified exec, `apply_patch`, MCP, agent spawning, and most local function tools; hosted tools and specialized opt-outs may bypass hooks. Non-managed hooks are also disableable and inactive until trusted. A hook cannot preempt a Bash process already running, so bounded work must use a native deadline and avoid open-ended interactive sessions.

Within those limits, the synchronous hook makes covered admission mechanical rather than voluntary. It resolves an exact initialized ancestor or explicit target and binds the host session to that root. An unbound session uses a bounded, link-safe descendant search only when exactly one initialized project exists; multiple roots, conflicts, unsafe links, or search-cap exhaustion fail closed. Directories with no initialized project remain unaffected.

The session registry and preclaim snapshots are fail-closed same-user guardrails, not cryptographic custody against another process already controlling that operating-system account.

Recovery authorization references are hash-bound, single-use evidence; a local file does not cryptographically prove human authorship under the same operating-system account. If authorship or provenance is uncertain, stop and obtain a platform-visible or independently protected approval before recovery.

The skill runs locally, uses no network service, and does not transmit project ledger contents.

## License

MIT. See [LICENSE](LICENSE).
