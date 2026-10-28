# notes/eof-delimiter

**Pins:** An exact delimiter at EOF creates a skipped empty piece, preserved before an append.

**Rule:** Transport.md §3.1: a final non-empty line without LF is a line;
appending first supplies one LF when needed, and otherwise preserves bytes.

**Derivation.** Start with the delimiter bytes `# --- test-certificate ---`
and the hand-derived `payload/minimal` record or the signed record copied
from `notes/appended`, as present in `note.txt`. Remove only the final LF.
For the foreign or corrupt piece use the literal bytes visible in `note.txt`.
`expected.json` lists the canonical payload of each parsed record and each
unparseable piece, including the empty piece after an EOF delimiter.
`add.txt` copies the other payload above, except in the duplicate cases,
where it copies the present payload. The expected output is the original blob
unchanged for a duplicate; otherwise it is the original blob, exactly one LF,
a new LF-terminated delimiter, then `add.txt`. These expected bytes were
assembled directly, without either reference writer.

**Would be wrong if:** the writer joined delimiter text to an unterminated
piece, repaired a duplicate without appending, dropped an empty piece, or the
reader required a delimiter's final LF.
