# store/signed

**Pins:** a signed certificate is named by the hash of its canonical payload,
which includes `key_id` and excludes the signature block — so it is stored
next to, not on top of, its unsigned twin.

| Rule | Where |
| ---- | ----- |
| `<payload-hash>` covers the canonical payload, which excludes the signature block | Transport.md §2.2, Canonical-Payload.md §2 |
| `key_id` is emitted when the certificate is signed | Canonical-Payload.md §2 rule 3 |
| Each certificate is its own file; none replaces another | Transport.md §2.2 |

**Derivation.** `canonical.txt` is a byte-for-byte copy of
`vectors/payload/signed/canonical.txt` (hand-derived). `certificate.toml` is
`canonical.txt` followed by a blank line and a `[certificate.signature]` block
whose `value` is a real ed25519 signature over `canonical.txt`, made with the
published key `vectors/signature/keys/insecure-test-key` (`key_id`
`example-key-2026-q2`) by `tools/regenerate.py`. `expected-path.txt` was
written from `canonical.txt` alone: the `content` line split at its first `:`,
and `sha256sum < canonical.txt`. Note that `sha256sum < certificate.toml` is a
different value; it is the wrong answer this case exists to catch.

**Paired with `unsigned`:** otherwise equal fields, different payload,
different name. **Paired with `signed-non-canonical` and
`signed-non-canonical-no-block`:** different file bytes, the same payload, the
same name.

**Would be wrong if:** the implementation hashed the file it was about to
write, signature block included, or left `key_id` out of the hashed payload.
