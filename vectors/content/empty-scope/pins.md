# content/empty-scope

**Pins:** a scope matching no tracked entry has a well-defined id —
the empty tree, or the digest of no records — and `src/d` matches nothing
although it is a string prefix of `src/db`.

| Rule | Where |
| ---- | ----- |
| A scope matching no tracked entry yields the empty tree | Content-Id.md §4.1 |
| An empty `manifest-v1` scope is the SHA-256 of the empty string | Content-Id.md §4.2 |
| A scope path names a file or the subtree beneath it | Standard.md §3.2.1 |

| Algorithm | Empty id |
| --------- | -------- |
| `git-tree-sha1` | `4b825dc642cb6eb9a060e54bf8d69288fbee4904` |
| `git-tree-sha256` | `6ef19b41225c5369f1c104d45d8d85efa9b057b53b14b4b9b939dd74decc5321` |
| `manifest-v1-sha256` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

The scope `missing` names nothing at all. The scope `src/d` is subtler: it is a
string prefix of `src/db/a.c`, but not a path component of it, so it matches
nothing too. `src/db`, listed for contrast, matches the one file.

The empty-tree id is a real, usable value: a producer scoped to a directory
that does not exist yet has tested nothing there, and says so precisely.

**Would be wrong if:** the implementation refused to compute an id for an empty
scope, emitted an empty digest, fell back to the whole-repository id, or
matched `src/d` as a string prefix and took `src/db/a.c`.
