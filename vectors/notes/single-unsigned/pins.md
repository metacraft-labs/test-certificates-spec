# notes/single-unsigned

**Pins:** the framing of a one-record note — a delimiter line, then the
record, and nothing after it.

| Rule | Where |
| ---- | ----- |
| Every record is preceded by `# --- test-certificate ---` and LF; the blob begins with it | Transport.md §3.1 |
| There is no delimiter after the last record | Transport.md §3.1 |
| An unsigned record is its canonical payload alone, with no signature table | Transport.md §3.1, Canonical-Payload.md §2 |
| The empty piece before the first delimiter is dropped | Transport.md §3.1 |

**Derivation.** `note.txt` is the delimiter line followed by a byte-for-byte
copy of `vectors/payload/minimal/canonical.txt` (hand-derived).

**Would be wrong if:** a reader yielded the empty leading piece as a second,
unparseable record; or a writer omitted the leading delimiter for a note with
only one record, or wrote one after the record.
