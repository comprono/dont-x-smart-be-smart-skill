# Don't X Smart, Be Smart Skill

[![Validate](https://github.com/comprono/dont-x-smart-be-smart-skill/actions/workflows/validate.yml/badge.svg)](https://github.com/comprono/dont-x-smart-be-smart-skill/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A community Codex skill for keeping long, complicated project work aligned with the user's real outcome.

Long agent sessions can drift after context compaction, promote an add-on into the main objective, confuse healthy processes with user-visible progress, turn unclear replies into repeated clarification loops, repeat the same failed patch, or spend more tokens coordinating work than completing it. This repository installs a small two-layer correction:

1. A concise global Codex rule block that activates outcome integrity for nontrivial project work.
2. The `outcome-integrity` skill, which maintains bounded human intent and machine-verifiable acceptance inside each active project.

`PROJECT_OUTCOME.md` preserves the north-star outcome, user intent, scope, current facts, context pointers, failure invariants, and active slice. `ACCEPTANCE.json` owns stable requirements, reproducible acceptance steps, evidence levels, status, and blocker recovery. Git owns history; neither project file is an activity transcript.

## What It Prevents

- Treating a review, test, plan, or orchestration step as the final outcome when the user's real goal is broader.
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

## Install

```powershell
git clone https://github.com/comprono/dont-x-smart-be-smart-skill.git
cd dont-x-smart-be-smart-skill
python scripts/install.py
```

The installer:

- copies the skill to `~/.codex/skills/outcome-integrity`;
- adds or updates one managed block in `~/.codex/AGENTS.md`;
- preserves unrelated existing global instructions;
- is safe to run again when updating the skill.

Start a new Codex task after installation. Restarting the Codex application is the safest way to refresh skill discovery.

To install without changing global instructions:

```powershell
python scripts/install.py --skip-global-rules
```

## How It Works

Before substantive work, Codex forms a compact outcome frame: the final outcome, acceptable proof, intermediate methods, and constraints. It asks whether completing every proposed method would actually solve the user's problem. If not, it reframes the task before spending tokens or assigning workers.

During an active project, Codex also maintains a compact control frame containing the current deliverable and stage, latest correction, next Codex-owned action, genuine blocker, and missing completion evidence. Questions and corrections update that project rather than silently ending it. After answering an interruption, Codex resumes the next safe authorized action in the same turn instead of waiting for another "do it" instruction.

For a simple question—such as whether one copy is newer, what a result means, or what happens next—Codex answers the direct plain-language conclusion first. It distinguishes ambiguous terms briefly and only expands when asked or needed for accuracy. A user should not need to simplify their own question to get the actual answer.

For status updates, Codex names the layer being discussed. Package, installer, model, restart, worker, and project-outcome states are not interchangeable. If an explanation confuses the user or the same question repeats, Codex treats that as drift and returns to a short conclusion, distinction, and next-action frame before continuing.

Before recurring or unattended work is enabled, Codex records a proportional operational envelope: progress identity, idempotency, retry cadence, resource cap and reserve, retention, cleanup, no-progress stop, and restart behavior. Read-only bounded polling stays lightweight; accumulating side effects fail closed when evidence stops improving.

For a nontrivial project, Codex reads or creates:

```text
<project-root>/.codex/
├── PROJECT_OUTCOME.md
└── ACCEPTANCE.json
```

Codex reconciles both files with the latest user instruction and current evidence before substantial planning or editing. The newest explicit correction wins. Observed state wins over stale summaries. Add-ons stay separate from the critical path.

Project state updates only after a material transition: changed intent, verified progress, a disproven assumption, a confirmed root cause, a changed recovery path, or a new current slice. Routine status and tool activity are excluded.

Resume and completion are executable gates:

```powershell
python ~/.codex/skills/outcome-integrity/scripts/project_outcome.py resume --root .
python ~/.codex/skills/outcome-integrity/scripts/project_outcome.py completion --root .
```

You can also invoke the skill explicitly:

```text
Use $outcome-integrity. Recover the project's real outcome and continue from verified state.
```

## Failure Circuit Breaker

Failures are classified before retrying. Transient failures get at most two bounded retries; reasoning failures require a changed input or approach; user-fixable failures receive an owner and recovery transition; semantic and unexpected failures require diagnosis. Ambiguous external writes must be checked through authoritative state or an idempotency key before retrying.

After the same acceptance outcome fails twice, the skill prohibits an unchanged third attempt. Codex must trace the authoritative transition, reproduce the failure, record the violated invariant, and use new root-cause evidence or a materially changed approach.

## Delegation Gate

Delegation is admitted only when work is parallel, disjoint, tied to an acceptance ID, independently verifiable, integration-bounded, and cheaper than direct execution. Sequential critical-path reasoning stays with the current Codex agent.

## Validation

```powershell
python -m unittest discover -s tests -v
```

The tests cover skill packaging, idempotent installation, dual-file initialization, stale resume state, slice mismatch, insufficient passing evidence, incomplete blocker recovery, and evidence-backed completion.

## Design Basis

The design incorporates published patterns from [Anthropic's long-running agent harness](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents), [OpenAI's harness engineering](https://openai.com/index/harness-engineering/), [Manus context engineering](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus), [Microsoft PROBE](https://www.microsoft.com/en-us/research/publication/debugging-the-debuggers-failure-anchored-structured-recovery-for-software-engineering-agents/), and [LangGraph durable execution guidance](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph).

## Guarantee Boundary

No prompt or skill can guarantee that every probabilistic model response will be perfect. This project instead makes the process enforceable and auditable: project intent survives compaction, repeated failures trigger a stop condition, progress claims require matching evidence, and drift has a deterministic recovery path.

The skill runs locally, uses no network service, and does not transmit project ledger contents.

## License

MIT. See [LICENSE](LICENSE).
