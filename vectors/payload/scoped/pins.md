# payload/scoped

**Pins:** `paths` is present, sorted, deduplicated, and sits between
`commit` and `clean`.

| Rule | Where |
| ---- | ----- |
| `paths` is sorted and deduplicated like `targets` | Canonical-Payload.md §2 rule 8 |
| Key order inside `[certificate.vcs]` is fixed: `repo`, `commit`, `paths`, `clean`, `untracked` | §2 rule 1 and the §2 skeleton |
| Paths are repo-relative, `/`-separated, no leading `./`, no trailing `/` | Standard.md §3.2.1 |
| `clean` and `untracked` are relative to `paths` | Standard.md §3.2.1 |

Input is `["src/db-backend", "Cargo.lock", "src/db-backend"]` — unsorted, with a
duplicate. Byte order puts `Cargo.lock` first (`43` < `73`), which is also where
an ASCII-case-insensitive sort would *not* put it if the other entry began with
a letter between `c` and `s`.

**Would be wrong if:** the implementation placed `paths` after `untracked`
(alphabetical or table-order habit), skipped deduplication because `paths` runs
through a different code path than `targets`, or emitted a leading `./`.
