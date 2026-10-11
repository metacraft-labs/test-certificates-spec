# notes/appended

**Pins:** a writer adds a record whose payload is not yet present after the
last piece, behind its own delimiter, leaving every existing byte unchanged.

| Rule | Where |
| ---- | ----- |
| A new record goes after the last piece, behind its own delimiter | Transport.md §3.1 |
| Every other piece is kept byte for byte | Transport.md §3.1 |

**Derivation.** `note.txt` is the delimiter and `payload/signed` with its
signature table. `add.txt` is `payload/minimal`. `expected-note.txt` is
`note.txt` followed by the delimiter and `add.txt`, assembled by hand.

**Would be wrong if:** a writer inserted the new record first, sorted the
records, put a blank line before the delimiter, or rewrote existing records.
