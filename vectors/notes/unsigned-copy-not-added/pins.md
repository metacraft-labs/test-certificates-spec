# notes/unsigned-copy-not-added

**Pins:** an unsigned copy of a present signed record is the same payload, so
it is not added, and it never replaces the signed one.

| Rule | Where |
| ---- | ----- |
| Records are identified by their payload, which excludes the signature table | Transport.md §3.1, Canonical-Payload.md §2 |
| An unsigned copy never replaces a present one | Transport.md §3.1, §2.3 |

**Derivation.** `note.txt` is `signed-and-unsigned`'s note. `add.txt` is
`payload/signed` without its signature table — the payload of the first,
signed record. `expected-note.txt` is `note.txt`, unchanged.

**Would be wrong if:** a writer compared whole records rather than payloads and
appended the copy, or replaced the signed record with it and discarded the
signature.
