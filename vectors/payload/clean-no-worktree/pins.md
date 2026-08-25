# payload/clean-no-worktree

**Pins:** worktree shape 3 of 4 — absent, and required to be absent; plus
`untracked` moving independently of `clean`.

| Rule | Where |
| ---- | ----- |
| `worktree` MUST be absent when `clean = true` | Standard.md §3.2.2, Canonical-Payload.md §2 rule 9 |
| `clean` and `untracked` mean different things and are reported independently | Standard.md §3.2 |
| Both are bare TOML booleans | Canonical-Payload.md §2 rule 4 |

`clean = true` with `untracked = true` is the ordinary "no tracked file
differs from `commit`, but there is scratch output lying around" state. An
implementation that derives one boolean from the other, or that treats any
untracked file as dirtiness, produces `clean = false` here and fails.

**Why the input carries no `worktree` object.** It would be tempting to feed
this vector an illegal `worktree` alongside `clean = true` and require the
serializer to drop it. That would be teaching exactly the behaviour
Canonical-Payload.md §5 forbids — a verifier MUST NOT "repair" a payload into
validity. Such an input is a malformed certificate, and the correct handling is
rejection, not silent omission; that is a rejection case, not a serialization
case, so it does not belong in this group.

**Would be wrong if:** the implementation emitted an empty
`[certificate.vcs.worktree]` header for symmetry with the dirty cases, or set
`clean = false` because untracked files were present.
