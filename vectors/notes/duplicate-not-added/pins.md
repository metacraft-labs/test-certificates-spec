# notes/duplicate-not-added

**Pins:** a writer does not add a record whose payload is already present —
publishing the same certificate twice changes nothing.

| Rule | Where |
| ---- | ----- |
| A writer MUST NOT add a record whose payload is already present | Transport.md §3.1 |
| Publishing twice adds nothing | Tooling.md (`notes publish`) |

**Derivation.** `note.txt` is `signed-and-unsigned`'s note. `add.txt` is
`payload/minimal`, byte-identical to the second record. `expected-note.txt` is
`note.txt`, unchanged.

**Would be wrong if:** a writer appended a second copy of the record.
