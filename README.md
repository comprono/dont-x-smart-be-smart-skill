# Don't X Smart, Be Smart Skill

[![Validate](https://github.com/comprono/dont-x-smart-be-smart-skill/actions/workflows/validate.yml/badge.svg)](https://github.com/comprono/dont-x-smart-be-smart-skill/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A community Codex skill for keeping long, complicated project work aligned with the user's real outcome.

Long agent sessions can drift after context compaction, promote an add-on into the main objective, confuse healthy processes with user-visible progress, repeat the same failed patch, or spend more tokens coordinating work than completing it. This repository installs a small two-layer correction:

1. A concise global Codex rule block that activates outcome integrity for nontrivial project work.
2. The `outcome-integrity` skill, which maintains one bounded `.codex/PROJECT_OUTCOME.md` ledger inside each active project.

The ledger preserves the north-star outcome, observable definition of done, current user intent, critical path, add-ons, non-goals, verified state, assumptions, decisions, failure invariants, and current end-to-end slice. It is current state, not a transcript or activity log.

## What It Prevents

- Continuing a stale plan after the user corrects it.
- Treating tests, workers, tool calls, or service health as proof of the requested outcome.
- Repeating the same symptom patch after two failed attempts.
- Letting dashboards, orchestration, safety machinery, or documentation replace the real objective.
- Losing key intent and failed approaches after context compaction.
- Creating project-management overhead for trivial work.

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

For a nontrivial project, Codex reads or creates:

```text
<project-root>/.codex/PROJECT_OUTCOME.md
```

Codex reconciles that ledger with the latest user instruction and current project evidence before substantial planning or editing. The newest explicit correction wins. Observed state wins over stale summaries. Add-ons stay separate from the critical path.

The ledger updates only after a material transition: changed intent, verified progress, a disproven assumption, a confirmed root cause, a changed recovery path, or a new current slice. Routine status and tool activity are excluded.

You can also invoke the skill explicitly:

```text
Use $outcome-integrity. Recover the project's real outcome and continue from verified state.
```

## Failure Circuit Breaker

After the same outcome fails twice, the skill prohibits a third blind retry. Codex must identify the authoritative state, trace the full transition, reproduce the failure, record the violated invariant, and make the next change address that invariant.

## Validation

```powershell
python -m unittest discover -s tests -v
```

The tests cover skill packaging, an idempotent installation, preservation of existing global instructions, rejection of unfilled project ledgers, and acceptance of a complete bounded ledger.

## Guarantee Boundary

No prompt or skill can guarantee that every probabilistic model response will be perfect. This project instead makes the process enforceable and auditable: project intent survives compaction, repeated failures trigger a stop condition, progress claims require matching evidence, and drift has a deterministic recovery path.

The skill runs locally, uses no network service, and does not transmit project ledger contents.

## License

MIT. See [LICENSE](LICENSE).
