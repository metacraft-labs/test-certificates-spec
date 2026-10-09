# store/scoped

**Pins:** a scoped certificate is stored under its own, **scoped** content id:
the directory is the certificate's `content`, never the whole-repository id of
the same tree.

| Rule | Where |
| ---- | ----- |
| A scoped certificate is stored under its scoped content id | Transport.md §2.2 |
| A scoped id identifies only the in-scope files | Content-Id.md §4, Standard.md §3.2.1 |
| `paths` is part of the payload, so it changes the name too | Canonical-Payload.md §2 rule 8 |

**Derivation.** `canonical.txt` is a byte-for-byte copy of
`vectors/payload/scoped/canonical.txt` (hand-derived), and `certificate.toml`
is that file unchanged. `expected-path.txt` was written from `canonical.txt`
with `sha256sum` and the `content` line split at its first `:`.

The content id here (`git-tree-sha1:3c1f5e0a…`) is not the one in
`store/unsigned` (`git-tree-sha1:9f8e7d6c…`), although both describe the same
example working tree: a reader finds this certificate only by computing the
id for this scope (Transport.md §2.2).

**Would be wrong if:** a producer filed the certificate under the
whole-repository id it had to hand, where a reader computing the scoped id
would never look.
