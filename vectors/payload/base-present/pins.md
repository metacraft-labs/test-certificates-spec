# payload/base-present

**Pins:** `base`, when present, is the **last** key of
`[certificate.vcs]`, after `untracked`, and is covered by the signature like
everything else.

| Rule | Where |
| ---- | ----- |
| `base` is omitted entirely when absent, never emitted empty | Canonical-Payload.md §2 rule 10 |
| It is the last key of `[certificate.vcs]` | §2 rule 10, §2 rule 1 and the §2 skeleton |
| Being informational, it is still covered by the signature | §2 rule 10 |
| `base` is the commit checked out at issuance; it is not evidence and is never matched | Standard.md §3.2.3, Verification.md §4.1 |

`base` is the one optional key the table gained in the 2026-10-09 revision, and
it lands somewhere easy to get wrong: not next to `repo`, where the old
`commit` sat, and not in alphabetical order (which would put it first), but at
the end, after the boolean.

The `base` here (`cc11…`) is deliberately not the commit any other vector
mentions. A serializer has no business knowing that, and a verifier must not
care (`verify/content-matches-other-base`).

**Would be wrong if:** the implementation emitted `base` where `commit` used to
be (straight after `repo`), sorted the vcs keys alphabetically, dropped `base`
from the payload because it is "only informational" — which would leave it
unsigned and freely rewritable — or emitted `base = ""` in the other vectors.

**Paired with `minimal`:** the two canonical `[certificate.vcs]` tables differ
by exactly the `base` line.
