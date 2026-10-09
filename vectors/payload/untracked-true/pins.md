# payload/untracked-true

**Pins:** `untracked = true` is emitted as a bare TOML boolean, and
moves independently of `content`.

| Rule | Where |
| ---- | ----- |
| `untracked` is a TOML boolean, emitted as bare `true` / `false`, never quoted | Canonical-Payload.md §2 rule 4 |
| Every value is a quoted string *except* `untracked` | §2 rule 11 |
| Untracked files are not part of `content`, and are reported separately | Standard.md §3.2, Content-Id.md §2 |

The `content` id is byte-identical to `minimal`'s. That is the point: untracked
files are outside the content, so a working tree with scratch output lying
around has the same content id as one without, and only `untracked` tells them
apart. An implementation that folds untracked files into the content id, or
that derives `untracked` from anything about `content`, fails here.

`true` here and `false` everywhere else cover rule 4 in both directions —
`untracked` is the only boolean left in the payload, so this is the only
`true` the group contains.

**Would be wrong if:** the implementation emitted `untracked = "true"` (rule 11
read as "every value is quoted"), `untracked = True` or `untracked = 1`, or
changed the content id because untracked files were present.
