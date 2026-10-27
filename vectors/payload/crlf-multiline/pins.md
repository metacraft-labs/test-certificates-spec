# CRLF multi-line string input

**Pins:** A physical newline inside a multi-line basic or literal string is
LF regardless of the document's line endings; escaped CR and CRLF values
are preserved (Canonical-Payload.md §5, §4).

`received.toml` uses CRLF for every physical newline. Both `project` (basic)
and `issuer` (literal) start with a newline immediately after the opening
triple quote, which TOML trims. Their remaining physical newline is LF in
the field value: `x`, LF, `y`. Both therefore render as `"x\ny"`.

The last three arguments are `a`, CR, `b`; `a`, CR, `b`; and `a`, CR, LF,
`b`. The first comes from `\r` in a single-line string, the second from
`\u000D` in a multi-line basic string, and the third from `\r\n` in a
multi-line basic string. These escape-produced characters are not physical
newlines and MUST NOT be normalized. Their canonical renderings are
`"a\rb"`, `"a\rb"`, and `"a\r\nb"`.

The expected bytes are derived by hand from `payload/minimal/canonical.txt`:
replace `project` and `issuer` with `"x\ny"`, and the argument array with
`["example-test", "a\rb", "a\rb", "a\r\nb"]`; keep every other byte.
The canonical file remains LF-only with its final LF, and the values in
`fields.json` contain the corresponding decoded code points.

**Would be wrong if:** A parser retained physical CRLF inside multi-line
strings, rendering `project` and `issuer` as `"x\r\ny"`; or a reader
normalized every decoded CRLF to LF, changing the last argument from
`"a\r\nb"` to `"a\nb"`. Normalizing every decoded CR to LF would also
change the two `"a\rb"` arguments. Each produces different signed bytes.
