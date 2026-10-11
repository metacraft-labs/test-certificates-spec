# notes/signed-replaces-unsigned

**Pins:** a signed record whose payload is already present, unsigned, replaces
the present record in place.

| Rule | Where |
| ---- | ----- |
| Records with byte-identical payloads are the same claim | Transport.md §3.1 |
| A signed copy replaces the present one, whose signature may be absent | Transport.md §3.1, §2.3 |
| A replacement takes the replaced record's place; other pieces are kept byte for byte | Transport.md §3.1 |
| The signature table is not part of the payload; `key_id` is | Canonical-Payload.md §2, §6 |

**Derivation.** `note.txt` is the delimiter, `payload/signed` **without** a
signature table — `key_id` present, so the same payload as the signed record,
but unsigned — then the delimiter and `payload/minimal`. `add.txt` is
`payload/signed` with its signature table. `expected-note.txt` is `note.txt`
with the first record's bytes replaced by `add.txt`'s, so the signed record
stays first. The signature is by the published key, made by
`tools/regenerate.py`.

**Would be wrong if:** a writer appended the signed copy beside the unsigned
one (two records for one claim), kept the unsigned one and discarded the
signature, or moved the record to the end.
