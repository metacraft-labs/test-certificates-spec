# payload/dirty-tree

**Pins:** worktree shape 1 of 4 — `tree` alone.

| Rule | Where |
| ---- | ----- |
| `[certificate.vcs.worktree]` is present only when `clean = false` | Canonical-Payload.md §2 rule 9 |
| It follows `[certificate.vcs]` after one blank line, and precedes the commands | §2 rule 9 and the §2 skeleton |
| Absent worktree keys are omitted, not emitted empty | §2 rule 9 |
| At least one of `tree` and `patch_digest` MUST be present | Standard.md §3.2.2 |
| `format` is required only when `patch_digest` is present | Standard.md §3.2.2 |

`clean = false` is emitted as a bare boolean, so the true/false pair across this
vector and `minimal` covers rule 4 in both directions.

**Would be wrong if:** the implementation emitted `format = ""` and
`patch_digest = ""` to keep the table rectangular, placed the worktree table
after the commands, or required `format` when there is no patch to describe.

**The four worktree shapes** are `clean-no-worktree` (absent), this vector
(`tree` only), `dirty-patch-only` (`format` + `patch_digest`) and
`dirty-tree-and-patch` (all three).
