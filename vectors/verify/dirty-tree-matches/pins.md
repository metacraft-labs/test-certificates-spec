# verify/dirty-tree-matches

**Pins:** a modified-worktree claim is matched by **content**, not
by commit identity.

| Rule | Where |
| ---- | ----- |
| With `tree`, the state matches when its canonical content id equals `worktree.tree` | Verification.md §4.1.1 |
| The match holds across commit metadata | Verification.md §4.1.1, Standard.md §3.2.2 |
| `vcs.commit` is the *base*, not the state the certificate describes | Standard.md §3.2.2 |

The certificate names a **different commit** from the one under evaluation. It
was issued against a dirty tree on top of `cc11…`; the developer then committed
that tree, producing `a858…` with a different message, author and parent — and
an identical tree.

That is exactly the workflow the form exists for, and the reason `tree` is
preferred over `patch_digest`: the certificate still covers the commit, with no
re-run.

**Would be wrong if:** the implementation compared `vcs.commit` to the commit
under evaluation and rejected on the mismatch, which is the correct check for a
`clean = true` certificate and the wrong one here.
