# notes/signed-and-unsigned

**Pins:** two records with different payloads share a note: a signed one, whose
signature table follows its payload after one blank line, and an unsigned one.

| Rule | Where |
| ---- | ----- |
| A signed record is its canonical payload, one blank line, and `[certificate.signature]` with `algorithm` then `value` | Transport.md §3.1 |
| Nothing — not even a blank line — between a record and the next delimiter | Transport.md §3.1 |
| Blank lines inside a record are not separators | Transport.md §3.1 |
| Several certificates per note are normal; a reader yields them all | Transport.md §3 |

**Derivation.** `note.txt` is the delimiter, `vectors/payload/signed/canonical.txt`
followed by a blank line and its signature table, the delimiter, and
`vectors/payload/minimal/canonical.txt`. The signature is a real ed25519
signature over the `signed` payload, by the published key
`vectors/signature/keys/insecure-test-key` (`key_id` `example-key-2026-q2`),
made by `tools/regenerate.py`.

The two payloads differ by the `key_id` line, so they are two claims, not one
claim signed and unsigned: the signed one does not replace the other
(as `store/signed` and `store/unsigned` are two files).

**Would be wrong if:** a reader split on blank lines (yielding seven pieces),
treated the signature table as part of the payload, or merged the two records
because their fields otherwise agree.
