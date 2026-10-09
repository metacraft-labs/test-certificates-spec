# content/byte-order

**Pins:** `manifest-v1` sorts by the raw bytes of the **full path**,
so `a.b` precedes `a/b`, which precedes `a0`.

| Rule | Where |
| ---- | ----- |
| Records are in ascending byte order of `path` — a plain unsigned comparison of the raw bytes | Content-Id.md §4.2 |
| That is not the order of a walk that sorts each directory's names alone | Content-Id.md §4.2 |
| A scope path names a file or a subtree, not a string prefix: `a` takes `a/b` and nothing else | Standard.md §3.2.1 |

On raw bytes, `.` (`2E`) < `/` (`2F`) < `0` (`30`), so the record order is
`a.b`, `a/b`, `a0`. Two natural ways of building the list get it wrong:

- **A per-directory walk** that sorts each directory's entry names and
  recurses. At the top level it sees the names `a`, `a.b`, `a0`, puts `a`
  first because it is a prefix of the others, and so emits `a/b` before `a.b`.
- **Files before directories** (or after): `a.b`, `a0`, then `a/b`.

The order **does** coincide with the order git lists the same paths in —
`git ls-files`, and `git ls-tree -r`. git sorts a subtree within its parent as
if its name ended in `/`, which is exactly what makes a recursive walk of a
tree come out in full-path byte order. So the `git-tree-sha1` id here is
listed too: the same entries, the same order, a different encoding.

`entries.json` is supplied in reverse (`a0`, `a/b`, `a.b`), so an
implementation that forgets to sort at all fails too.

**Would be wrong if:** the implementation walked directories and sorted names
per level, grouped files and directories, sorted with locale collation (which
may ignore punctuation entirely), or matched the scope `a` as a string prefix
and took `a.b` and `a0` with it.
