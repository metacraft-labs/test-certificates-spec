# payload/dirty-tree-and-patch

**Pins:** worktree shape 4 of 4 — all three keys, in the fixed order.

> Beyond the sixteen cases required by Conformance.md §1. It exists because
> rules 1 and 9 together fix an order that no other vector shows in full.

| Rule | Where |
| ---- | ----- |
| Worktree key order is `tree`, `format`, `patch_digest` | Canonical-Payload.md §2 rule 1 and the §2 skeleton |
| A producer MAY supply both identifiers | Standard.md §3.2.2 |
| No blank line separates keys within the table | §2 rule 5 |

Alphabetical order would be `format`, `patch_digest`, `tree` — the exact
reverse of the required order at both ends, so an implementation that sorts keys
cannot accidentally pass this vector.

**Would be wrong if:** the implementation sorted the three keys, or emitted
`tree` last because it was appended after the patch fields were computed.
