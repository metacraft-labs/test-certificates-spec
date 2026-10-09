# store/unsigned

**Pins:** an unsigned certificate is stored at
`v1/<algorithm>/<digest>/<payload-hash>.toml`, with the content id split at
its first `:` and the name the SHA-256 of the canonical payload.

| Rule | Where |
| ---- | ----- |
| The layout is `<root>/v1/<algorithm>/<digest>/<payload-hash>.toml` | Transport.md §2.2 |
| `<algorithm>` and `<digest>` are the halves of `content`, split at the first `:` | Transport.md §2.2, Content-Id.md §1 |
| `<payload-hash>` is the lowercase hex SHA-256 of the canonical payload | Transport.md §2.2, Canonical-Payload.md |
| `key_id` is omitted from an unsigned payload | Canonical-Payload.md §2 rule 3 |

**Derivation.** `canonical.txt` is a byte-for-byte copy of
`vectors/payload/minimal/canonical.txt`, which was derived by hand from
Canonical-Payload.md. `certificate.toml` is that same file: an unsigned
certificate in canonical form with no signature block. `expected-path.txt` was
written from `canonical.txt` with no serializer involved: the `content` line
split at its first `:`, and `sha256sum < canonical.txt`.

**Paired with `signed`:** the same field values plus `key_id` and a signature.
The two payloads differ by one line, so the names differ, under the same
content directory.

**Would be wrong if:** the implementation used the content id as one directory
name (`git-tree-sha1:9f8e…`, illegal on Windows), uppercased the hash, or hashed
something other than the canonical payload.
