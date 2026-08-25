# verify/dirty-no-worktree

**Pins:** a dirty certificate with no `worktree` is malformed, and
malformed is decidably invalid — not unverifiable.

| Rule | Where |
| ---- | ----- |
| `worktree` is REQUIRED when `clean = false` | Standard.md §3.2.2 |
| A dirty certificate without it identifies no state at all and MUST be rejected | Standard.md §3.2.2, Verification.md §4.1.1 |
| A verifier MUST NOT "repair" a record into validity | Canonical-Payload.md §5 |

This certificate carries no `key_id` and the requirement does not demand
signatures, so nothing else can be blamed for the rejection: the record itself
is invalid.

Note that the file is authored literally rather than through the reference
serializer, because the serializer refuses to emit it. That refusal is the
producer-side half of the same rule.

**Would be wrong if:** the implementation guessed that `clean = false` with no
worktree meant "compare `vcs.commit` anyway" (repairing), or reported
unverifiable — a missing required field is something the consumer *can* judge,
and Verification.md §7 reserves unverifiable for evaluation breaking down.
