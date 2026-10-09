# verify/content-differs

**Pins:** the content comparison is an equality test, failing it is
an ordinary not-covered — and a `base` equal to the commit under evaluation
does not rescue it.

| Rule | Where |
| ---- | ----- |
| The certificate matches only when the two content ids are equal | Verification.md §4.1.1 |
| When they differ, the certificate does not describe this state and is not evidence here | Verification.md §4.1.1 |
| `vcs.base` is never compared with the commit under evaluation | Verification.md §4.1, Standard.md §3.2.3 |

The certificate's `base` is `a858…` — exactly the commit `state.json`
evaluates. Its `content` is a different, well-formed `git-tree-sha1` id. The
tests ran against content that commit `a858…` does not record: a working tree
with uncommitted edits on top of it, say, which were later discarded.

**Would be wrong if:** the implementation fell back to comparing `base`, and
covered the requirement because "it was tested on this commit"; or treated the
mismatch as unverifiable — the consumer computed the id and compared it, so it
*could* tell.
