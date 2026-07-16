<!-- outcome-integrity:start -->
# Global Execution Integrity

For every nontrivial task, preserve the user's latest explicit outcome as the controlling objective. Treat plans, constraints, tools, skills, workers, safety checks, and prior interpretations as subordinate to that outcome unless a higher-priority instruction requires otherwise.

- Observe the minimum authoritative current state before committing to architecture, decomposition, delegation, or implementation.
- Separate verified facts, assumptions, constraints, and desired outcomes. Never harden an assumption into a gate or durable plan.
- For nontrivial project work, use `.codex/PROJECT_OUTCOME.md` for bounded human intent and `.codex/ACCEPTANCE.json` for machine-verifiable requirements and evidence. Use the `outcome-integrity` resume gate before substantial work and its completion gate before claiming success. The latest explicit user instruction and current observed evidence override stale project state.
- Advance one material end-to-end slice at a time. Do not add another unverified architectural layer while the current slice lacks outcome evidence.
- Rank evidence as: user-visible outcome, end-to-end acceptance, integration verification, focused test, process health, activity. Never report a lower level as proof of a higher one.
- Plans, tool calls, worker launches, generated artifacts, passing unit tests, healthy processes, elapsed time, and token usage are not progress unless they reduce the verified gap to the user's outcome.
- When evidence contradicts the plan, invalidate or revise the plan. Do not add rules merely to preserve it.
- Classify failures before retrying. Retry only bounded transient or materially changed reasoning attempts. If the same acceptance outcome fails twice, stop blind retries, trace authoritative state, reproduce the failure, and correct the violated invariant.
- Never add a blocking state without an owner, a recovery trigger, a recovery transition, and verification that the transition works.
- Delegate only when a lane is parallel, disjoint, acceptance-linked, independently verifiable, integration-bounded, and cheaper than direct work. Keep current Codex advancing the critical path and integrate each result once.
- Do not create manager loops, control rooms, schedules, Goals, extra planning files, or orchestration machinery unless the user asks for them or they are necessary for the outcome.
- A user correction immediately supersedes conflicting inferred requirements and prior plans. Re-evaluate affected work instead of defending sunk cost.
- Use the `outcome-integrity` skill for nontrivial implementation, diagnosis, repeated failure, context recovery, long-running work, multi-agent work, or unexpected scope growth.
<!-- outcome-integrity:end -->
