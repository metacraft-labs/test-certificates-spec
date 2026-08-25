# payload/dirty-patch-only

**Pins:** worktree shape 2 of 4 — the portable fallback, with no `tree`.

| Rule | Where |
| ---- | ----- |
| Absent worktree keys are omitted; `tree` does not appear | Canonical-Payload.md §2 rule 9 |
| Worktree key order is `tree`, `format`, `patch_digest` — so `format` precedes `patch_digest` | §2 rule 1 and the §2 skeleton |
| `format` is REQUIRED when `patch_digest` is present | Standard.md §3.2.2 |
| `patch_digest` is `<algo>:<hex>` | Standard.md §3.2.2 |
| `format` is an opaque identifier that must pin every option affecting the patch bytes | Standard.md §3.2.2 |

`untracked = true` here alongside `clean = false`, so the two booleans are
exercised independently rather than always moving together.

**Would be wrong if:** the implementation emitted `format` after
`patch_digest` (alphabetical order would), emitted a bare hex digest with no
algorithm prefix, or omitted `format` on the grounds that "everyone uses git".
