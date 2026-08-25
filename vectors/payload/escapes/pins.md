# payload/escapes

**Pins:** every escape in the table, only those escapes, and the fact that
sorting happens **before** escaping.

| Rule | Where |
| ---- | ----- |
| The seven escapes `\\ \" \n \r \t \b \f` and no others | Canonical-Payload.md §4 |
| Characters outside the table are emitted raw | §4 |
| `targets` sorts on the raw UTF-8 bytes of the value, before escaping | §3 |

`project` carries a backslash and a double quote. `issuer` carries all five
whitespace/control escapes: TAB, LF, CR, BS, FF. Note that the LF in `issuer`
becomes the two characters `\n` — it does **not** become a physical newline, so
the payload's line count is unchanged.

`argv` carries `/`, `$`, `'`, `#` and a bare `=`. None of them is escaped:
`/` is a JSON-optional escape that TOML does not use, `'` is TOML's
literal-string delimiter but has no meaning inside a basic string, and `#`
starts a comment only outside a string.

**The sort-order trap.** The two targets are `t-a<TAB>b` and `t-a!b`. On raw
bytes, TAB (`09`) sorts before `!` (`21`), so the TAB target comes first. If an
implementation escapes first and then sorts the rendered text, it compares `\`
(`5C`) against `!` (`21`) and emits them the other way round. Same values, same
prose, different signed bytes.

**Would be wrong if:** the implementation emitted `\u0009` instead of `\t`,
escaped `/` as `\/` (a JSON habit), escaped `'`, or sorted after escaping.

## `received.toml`

This case carries an extra, optional file: the same field values written as
non-canonically as TOML allows. CRLF line endings, aligned `=`, tables and keys
in a scrambled order, `project` as a TOML *literal* string (where `\` and `"`
carry no special meaning at all), the `\u0009` and `\u0021` escapes in place of
the characters they denote, `paths = []`, a multi-line `argv` array with a
trailing comma, and an empty `[certificate.signature]` block.

Parsing it MUST produce exactly `canonical.txt`.

| Rule | Where |
| ---- | ----- |
| A verifier reconstructs the payload from the **parsed fields**, never by slicing the received file | Canonical-Payload.md §5 |
| `\uXXXX` MUST be accepted on input, and MUST NOT be produced on output | Canonical-Payload.md §4 |
| An empty signature block means unsigned, and does not affect the payload | Canonical-Payload.md §6 |
| `paths = []` means the whole repository, and drops the key | Canonical-Payload.md §2 rule 8 |

**Would be wrong if:** the implementation verified signatures against the bytes
it received. A certificate that has passed through a formatter, an editor with
a different newline setting, or a TOML round-trip would then fail against its
own valid signature — and the diagnosis ("your certificate does not verify")
would point at the wrong thing entirely.
