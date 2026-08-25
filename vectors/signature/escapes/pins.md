# signature/escapes

**Pins:** a signature over a payload containing every escape in
the table, including the sort-before-escape ordering trap.

| Rule | Where |
| ---- | ----- |
| The seven escapes, and only those | Canonical-Payload.md §4 |
| `targets` sorts on raw value bytes, not on the escaped rendering | Canonical-Payload.md §3 |

`canonical.txt` is byte-identical to `vectors/payload/escapes/canonical.txt`.
See that vector's `pins.md` for why the two targets are ordered as they are;
here the consequence is concrete — get the order wrong and the signature does
not verify.
