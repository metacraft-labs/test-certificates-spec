# payload/scoped

**Pins:** `paths` is present, sorted, deduplicated, and sits between
`repo` and `content`.

| Rule | Where |
| ---- | ----- |
| `paths` is sorted and deduplicated like `targets` | Canonical-Payload.md §2 rule 8 |
| Key order inside `[certificate.vcs]` is fixed: `repo`, `paths`, `content`, `untracked`, `base` | §2 rule 1 and the §2 skeleton |
| Paths are repo-relative, `/`-separated, no leading `./`, no trailing `/` | Standard.md §3.2.1 |
| `content` and `untracked` are relative to `paths` | Standard.md §3.2.1, Content-Id.md §4 |

Input is `["src/db-backend", "Cargo.lock", "src/db-backend"]` — unsorted, with a
duplicate. Byte order puts `Cargo.lock` first (`43` < `73`), which is also where
an ASCII-case-insensitive sort would *not* put it if the other entry began with
a letter between `c` and `s`.

The `content` id differs from the one in `minimal`: a scoped id covers only the
in-scope files, so the same working tree has a different id under a different
scope. The serializer neither knows nor checks that — it emits the value it is
given — but it is why `paths` has to precede `content`: a reader meets the scope
before the id that depends on it.

**Would be wrong if:** the implementation placed `paths` after `content` or
`untracked` (alphabetical or table-order habit), skipped deduplication because
`paths` runs through a different code path than `targets`, or emitted a leading
`./`.
