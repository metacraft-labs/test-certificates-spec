# verify/content-matches-other-base

**Pins:** a certificate is matched by **content**, never by commit —
one whose `base` is not the commit under evaluation, but whose `content`
matches, covers it.

| Rule | Where |
| ---- | ----- |
| `vcs.content` must equal the content id of the state under evaluation, computed with the certificate's algorithm over its scope | Verification.md §4.1, §4.1.1 |
| `vcs.base` is not checked, and MUST NOT be compared with the commit under evaluation | Verification.md §4.1, §4.1.1; Standard.md §3.2.3 |
| A certificate covers every commit that records the same content | Standard.md §2.1 |

The certificate was issued against a working tree on top of `cc11…` (its
`base`). The developer then committed exactly that content, producing `a858…`
with its own message, author and parent. `state.json` evaluates `a858…`, whose
`git-tree-sha1` id equals the certificate's `content`.

This is the test-then-commit workflow the content binding exists for
(Standard.md §3.2.2): the certificate is valid for the commit with no second
run.

**Would be wrong if:** the implementation compared `base` (or any commit id) to
the commit under evaluation and rejected on the mismatch — the habit the
earlier draft's `commit` field taught, and the one this revision removes.

**Paired with `content-differs`:** there, `base` *is* the commit under
evaluation and the content is not, and the verdict flips.
