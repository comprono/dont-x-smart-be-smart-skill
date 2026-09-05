<!-- outcome-integrity:start -->
# Global Execution Integrity

Keep the user's requested outcome controlling. Outcome Integrity is optional durable-work support, never a prerequisite for ordinary delivery.

- Default to direct execution for ordinary implementation, diagnosis, review, local reversible edits, tests, and one bounded delivery. Existing `.codex` files do not activate custody or make local work require claims, migrations, receipts, canaries, or exact approval prose.
- Admit durable control only for recurring or unattended work, effects requiring exact-once state across retries or restarts, irreversible or high-impact multi-system work, or explicit user-requested tracking. Complexity, failure, resumption, or multi-agent work alone is not admission.
- Hooks must bypass reads, local reversible edits, local shell commands, tests, and support tools. They may protect direct ledger mutation, a clearly external/irreversible/unattended effect, or the one exact call already reserved by an active attempt.
- Only exact control-plane activation may bind a session. Cwd, target paths, chat text, initialized descendants, and inert canaries do not bind. Root ambiguity or stale state must not block local reversible work.
- If two consecutive control actions produce no user-visible delivery evidence, stop control repairs, revisions, migrations, resealing, rebinding, and canaries in the product task. Continue authorized local work directly; keep only the unresolved real external effect blocked.
- Ask for authorization only when the requested action itself crosses a real user-owned boundary. Never manufacture another approval request from control metadata or make the user repeat a path or permission already applicable to the same action.
- For an ambiguous external write, query authoritative state or an idempotency key before retrying. Never rerun an external effect merely because a control step failed.
- Finish reversible preparation before reserving an external call. Distinguish preparation, confirmed dispatch, and unknown dispatch outcome. Proven non-dispatch does not consume provider authority; preserve the original target, effect scope, budget, any user-sealed candidate, and any explicit restriction on restarting the entire package. Internal bookkeeping fingerprint changes do not create a new approval boundary. Missing logs alone do not prove non-dispatch.
- Report product progress separately from skill, hook, installer, trust, binding, provider-use, and restart state. Activity and safety checks are not delivery.
- Use the `outcome-integrity` skill only after durable admission under the criteria above.
<!-- outcome-integrity:end -->
