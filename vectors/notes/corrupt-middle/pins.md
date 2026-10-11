# notes/corrupt-middle

**Pins:** a piece that does not parse is reported and skipped, and the records
on either side of it are still yielded.

| Rule | Where |
| ---- | ----- |
| A piece that does not parse is reported and skipped | Transport.md §3.1 |
| It does not invalidate its neighbours | Transport.md §3.1 |

**Derivation.** `note.txt` is three pieces: `payload/signed` with its signature
table (as in `signed-and-unsigned`), a record truncated in the middle of its
`targets` array — the first seven lines of `payload/targets-single`, then
`targets = ["t-un` and LF, an unterminated string that no TOML parser accepts
— and `payload/minimal`.

**Would be wrong if:** a reader parsed the whole blob as one TOML document and
lost every record to the one bad piece, stopped at the first failure and lost
the third record, or silently dropped the bad piece without reporting it.
