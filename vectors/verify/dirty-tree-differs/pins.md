# verify/dirty-tree-differs

**Pins:** the content comparison is an equality test, and failing
it is an ordinary not-covered.

| Rule | Where |
| ---- | ----- |
| The state matches only when its canonical content id equals `worktree.tree` | Verification.md §4.1.1 |
| `result = "passed"` for a different tree is not evidence about this one | Verification.md §4.1 |

Identical to `dirty-tree-matches` except for the tree id. Something was tested;
it was not this.

**Would be wrong if:** the implementation fell back to comparing `vcs.commit`,
or treated a `tree` mismatch as unverifiable — the consumer knew both ids and
could compare them, so it *could* tell.
