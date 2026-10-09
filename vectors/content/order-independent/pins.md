# content/order-independent

**Pins:** the entries arrive in no particular order, and the ids do
not depend on it.

| Rule | Where |
| ---- | ----- |
| `manifest-v1` records are concatenated in ascending byte order of `path`, so the digest is independent of listing order | Content-Id.md §4.2 |
| A `git-tree-*` id is the id of the tree a commit of the state would record — a function of the entries, not of how they were listed | Content-Id.md §4.1 |
| A scoped id covers exactly the in-scope entries | Content-Id.md §4, Standard.md §3.2.1 |

`entries.json` lists `src/main.c`, `README.md`, `src/lib/util.c`,
`docs/guide.md`, `Makefile` — the order a filesystem walk might happen to
produce, and not sorted by any rule. Two producers walking the same tree on
different filesystems see different orders and must compute the same id.

The ids are listed whole-repository and scoped to `src`, in both
`git-tree-sha1` and `manifest-v1-sha256`.

**Would be wrong if:** the implementation hashed the records in input order,
or sorted only within a directory and concatenated directories in the order
they were met. Either passes a vector whose input happens to be sorted, which
is why this one's is not.
