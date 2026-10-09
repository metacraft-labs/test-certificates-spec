# content/scope-keeps-paths

**Pins:** a scoped `git-tree` id keeps **full repository paths** — it
is not the id of the subtree at the scoped directory — and the scope `src/db`
does not take in `src/dbx`.

| Rule | Where |
| ---- | ----- |
| A scoped id is the id of the tree holding only the in-scope entries, at their full repository paths | Content-Id.md §4.1 |
| It is not the tree object `T:src/db`, which has lost its path | Content-Id.md §4.1 |
| Keeping full paths makes `["src/db"]` and `["lib/db"]` distinct when their directories hold identical files | Content-Id.md §4.1 |
| A scope path names a file or the subtree beneath it | Standard.md §3.2.1 |
| Pathspecs MUST be literal | Content-Id.md §4.1 |
| `manifest-v1` scoping keeps full paths by construction | Content-Id.md §4.2 |

`src/db/` and `lib/db/` hold byte-identical files, so in the whole-repository
tree `T`, `T:src/db` and `T:lib/db` are **the same tree object**
(`58b96ac8…`). Their scoped ids differ (`c4e13945…` and `9292a4cf…`), and
neither equals `58b96ac8…`. A certificate scoped to `src/db` therefore cannot
be satisfied by a state where only `lib/db` holds those files — which is the
point of naming the scope.

`src/dbx/extra.c` sits next to the scope with a name that extends it as a
string. It is outside: `src/db` scopes the directory `src/db`, not every path
beginning with those six characters. The scope `["README.md", "src/db"]` shows
a file and a directory scoped together.

To re-derive with git, use the recipe in Content-Id.md §4.1 verbatim;
`tools/walk-vectors.sh` does.

**Would be wrong if:** the implementation returned `git rev-parse T:src/db`
for a scoped id, matched scopes as string prefixes, or passed the scope to git
as a glob pathspec.
