# store/manifest-content

**Pins:** a `manifest-v1-sha256` content id is split like any other, giving a
`manifest-v1-sha256` directory and a 64-digit digest directory.

| Rule | Where |
| ---- | ----- |
| `<algorithm>` and `<digest>` are the halves of `content`, split at the first `:` | Transport.md §2.2, Content-Id.md §1 |
| `manifest-v1-sha256` is a content-id algorithm with a 64-digit digest | Content-Id.md §4 |

**Derivation.** `canonical.txt` is a byte-for-byte copy of
`vectors/payload/content-manifest/canonical.txt` (hand-derived), and
`certificate.toml` is that file unchanged: an unsigned certificate in
canonical form. `expected-path.txt` was written from `canonical.txt` with
`sha256sum` and the `content` line split at its first `:`.

**Would be wrong if:** the implementation assumed every content id is a git
tree id — a `git-tree-sha1` directory, or a digest truncated to 40 digits — or
split the id anywhere but the first `:`.
