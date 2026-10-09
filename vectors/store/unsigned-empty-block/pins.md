# store/unsigned-empty-block

**Pins:** the empty-signature-block form of an unsigned certificate is stored
under the same name as the form with no block at all.

> Beyond the cases Conformance.md §5 requires: it pins the store half of
> Canonical-Payload.md §6, which promises the two unsigned forms are one
> payload.

| Rule | Where |
| ---- | ----- |
| An absent block and an empty block both mean unsigned | Canonical-Payload.md §6 |
| Neither form affects the canonical payload | Canonical-Payload.md §6 |
| The name is the hash of the canonical payload | Transport.md §2.2 |

**Derivation.** `canonical.txt` is a byte-for-byte copy of
`vectors/payload/minimal/canonical.txt` (hand-derived). `certificate.toml` is
`canonical.txt`, a blank line, and `[certificate.signature]` with
`algorithm = ""` and `value = ""`. `expected-path.txt` is identical to
`store/unsigned/expected-path.txt`, written from `canonical.txt` with
`sha256sum` and the `content` line split at its first `:`.

**Would be wrong if:** the implementation hashed the file, or treated the empty
block as part of the payload.
