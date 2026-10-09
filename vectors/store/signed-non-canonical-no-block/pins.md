# store/signed-non-canonical-no-block

**Pins:** removing a signed certificate's signature block does not change its
name — `key_id` is part of the payload and stays, the block never was — so
the stripped copy and the signed one land on the same name.

| Rule | Where |
| ---- | ----- |
| The signature block is excluded from the payload; `key_id` is not | Canonical-Payload.md §2, rule 3 |
| An absent block means unsigned, and does not affect the payload | Canonical-Payload.md §6 |
| An existing file holding an unsigned copy is replaced by a signed one, never kept over it | Transport.md §2.3 |

**Derivation.** `canonical.txt` is a byte-for-byte copy of
`vectors/payload/signed/canonical.txt` (hand-derived), and `expected-path.txt`
is identical to `store/signed/expected-path.txt`, written from that file with
`sha256sum` and the `content` line split at its first `:`.
`certificate.toml` was written by hand to carry `store/signed`'s field values
with no `[certificate.signature]` table: quoted keys, the `vcs` table and the
`command` array as inline tables, literal strings, a `\u0070` escape (in
`project`) and a trailing comma in `targets`.

**Why the same name matters.** Transport.md §2.3 lets a producer keep a file
that already exists under the final name. Before this case, its justification
("either signature verifies over the same payload") assumed both copies were
signed; this case shows a copy without a signature has the same name, and
§2.3 now says such a copy never displaces, nor is kept over, a signed one —
see vectors/README.md, "Ambiguities this suite closed".

**Would be wrong if:** the implementation dropped `key_id` when the signature
block is absent (it would land on `store/unsigned`'s name), or hashed the file
bytes.
