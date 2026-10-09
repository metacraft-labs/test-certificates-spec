# content/sha256-object-format

**Pins:** `git-tree-sha256` — the same entries as
`order-independent`, under git's SHA-256 object format.

| Rule | Where |
| ---- | ----- |
| `git-tree-sha256` is the tree id under the SHA-256 object format; its digest is 64 hex digits | Content-Id.md §4, §4.1 |
| A producer SHOULD use the `git-tree-*` algorithm matching the repository's object format | Content-Id.md §4 |
| Two content ids with different algorithms are never compared | Content-Id.md §1 |
| `manifest-v1-sha256` does not depend on any VCS | Content-Id.md §4.2 |

`entries.json` is byte-identical to `order-independent`'s. The listed ids show
what changes with the object format and what does not:

- `git-tree-sha256` is not `git-tree-sha1` with a longer hash. Blob ids,
  subtree ids and the tree's own id all change, because every tree entry embeds
  a 32-byte id where SHA-1 embeds 20. Re-derive with
  `git init --object-format=sha256`.
- `git-tree-sha1` is listed again and equals `order-independent`'s.
- `manifest-v1-sha256` is listed again and equals `order-independent`'s. It
  hashes file content, never git objects, so the object format cannot affect it.

**Would be wrong if:** the implementation computed SHA-256 over SHA-1 tree
objects, or over objects carrying 20-byte embedded ids; or treated a
`git-tree-sha256` id as comparable to a `git-tree-sha1` one for the same files.
