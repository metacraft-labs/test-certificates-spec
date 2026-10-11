# notes/foreign-preamble

**Pins:** text before the first delimiter is reported and skipped, never
parsed as a record — even when, as here, it would parse.

| Rule | Where |
| ---- | ----- |
| The blob begins with a delimiter line | Transport.md §3.1 |
| A non-empty piece before the first delimiter is reported and skipped, and never parsed | Transport.md §3.1 |

**Derivation.** `note.txt` is the line `# --- reprobuild-certificate ---` — the
delimiter reprobuild invented before Transport.md §3.1 named one — followed by
`payload/minimal`, then the standard delimiter and `payload/signed` with its
signature table. The first piece is a TOML comment followed by a valid
certificate; a TOML parser accepts it. It is still not a record: the framing is
fixed, and a blob that does not begin with the delimiter was not written by a
conforming writer.

The rule this case pins was added to Transport.md §3.1 in the same change as
the case: the first text of §3.1 told a reader to drop "the empty piece before
the first" delimiter without saying what to do when that piece is not empty.

**Would be wrong if:** a reader parsed the leading piece and yielded
`payload/minimal` as a record, or treated the foreign delimiter as a
delimiter.
