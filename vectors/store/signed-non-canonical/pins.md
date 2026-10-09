# store/signed-non-canonical

**Pins:** the name is the hash of the canonical payload reconstructed from the
parsed fields, never of the file bytes — a non-canonical rendering of
`store/signed`, signature block included, is stored under `store/signed`'s
name.

| Rule | Where |
| ---- | ----- |
| `<payload-hash>` is the SHA-256 of the canonical payload | Transport.md §2.2 |
| The payload is reconstructed from the parsed fields, never sliced from the file | Canonical-Payload.md §5 |
| The signature block is excluded wherever it appears in the file | Canonical-Payload.md §2 |

**Derivation.** `canonical.txt` is a byte-for-byte copy of
`vectors/payload/signed/canonical.txt` (hand-derived), and `expected-path.txt`
is identical to `store/signed/expected-path.txt`, written from that file with
`sha256sum` and the `content` line split at its first `:`. `certificate.toml`
was written by hand to carry exactly `store/signed`'s field values: CRLF line
endings, a comment header, the `[certificate.signature]` table *first*, the
`[[certificate.command]]` table before `[certificate]`, keys in a different
order, aligned and tab-separated `=`, literal (`'…'`) and multi-line (`"""…"""`)
strings, `\u0040` and `\u002F` escapes (in `issuer` and `platform`), a
multi-line `argv` with a trailing comma, and `targets` in reverse order. Its signature `value` is the same
signature as `store/signed`'s, written in place by `tools/regenerate.py`, which
signs `canonical.txt` and touches nothing else in the file.

**Would be wrong if:** the implementation hashed the file bytes, cut the file
at the `[certificate.signature]` header (which here would discard almost the
whole payload), or normalised only line endings before hashing.
