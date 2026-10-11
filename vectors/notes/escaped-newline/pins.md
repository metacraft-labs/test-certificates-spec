# notes/escaped-newline

**Pins:** the delimiter cannot occur inside a canonical record, even when a
value contains a newline followed by the delimiter's exact text — the newline
is written as the two characters `\n`, so the text never starts a line.

| Rule | Where |
| ---- | ----- |
| A reader splits on **lines equal to** the delimiter, not on occurrences of its text | Transport.md §3.1 |
| Every newline inside a value is escaped in canonical form | Canonical-Payload.md §4, Transport.md §3.1 |
| Records are written in canonical form: no multi-line strings | Transport.md §3.1 |

**Derivation.** The first record is `vectors/payload/minimal/canonical.txt` with
its `argv` line replaced, by hand, by
`argv = ["example-test", "run", "--message", "first\n# --- test-certificate ---\nlast"]`,
where `\n` is a backslash and an `n`. The argument's value is
`first`, LF, the delimiter text, LF, `last`. It is unsigned and appears in no
payload vector; its bytes are given in full in `expected.json`. The second
record is `payload/minimal`.

The delimiter text occurs three times in `note.txt` and starts a line twice.

**Would be wrong if:** a reader searched for the delimiter as a substring
(yielding three pieces, two of them unparseable), or a writer emitted the value
as a TOML multi-line string, which would put the delimiter on a line of its
own.
