# payload/content-manifest

**Pins:** `content` is emitted **verbatim**, whatever its algorithm —
here `manifest-v1-sha256`, the non-git one — and `base` is absent.

| Rule | Where |
| ---- | ----- |
| `content` is emitted verbatim, as the self-describing string; the serializer does not split, re-case or validate it | Canonical-Payload.md §2 rule 9 |
| A content id is `<algorithm>:<lowercase hex>` | Content-Id.md §1 |
| `manifest-v1-sha256` is one of the three algorithms | Content-Id.md §4, §4.2 |
| `base` is omitted entirely when absent | Canonical-Payload.md §2 rule 10 |

The id is real: it is the `manifest-v1-sha256` of the entries in
`vectors/content/order-independent`. A repository under a VCS other than git
has no commit id to put in `base`, and a producer for it simply omits the key.

Every other payload vector uses a `git-tree-sha1` id. An implementation that
treats `content` as "a git tree id with a prefix" — storing the digest alone
and re-attaching `git-tree-sha1:` on output, or validating the length against
40 — fails here and passes everywhere else.

**Would be wrong if:** the implementation rewrote the algorithm prefix, split
`content` into an algorithm field and a digest field and re-joined them
differently, upper-cased the digest, or refused to serialize an algorithm it
does not itself compute (that is a verifier's finding, Verification.md §4.1.1,
not a serializer's).
