# signature/unicode

**Pins:** a signature over a payload full of multi-byte UTF-8,
so an implementation that re-encodes or escapes non-ASCII fails at the
signature rather than silently producing a different claim.

| Rule | Where |
| ---- | ----- |
| The payload is UTF-8 with no BOM | Canonical-Payload.md §1 |
| Non-ASCII is emitted literally, never as `\uXXXX` | Canonical-Payload.md §4 |
| The signature covers those exact bytes | Standard.md §6 |

`canonical.txt` is byte-identical to
`vectors/payload/targets-unicode/canonical.txt`, whose targets are ordered by
UTF-8 byte value.

An implementation that sorted by UTF-16 code units, escaped above the BMP, or
normalized to NFC produces different bytes and therefore a signature failure —
which is the honest outcome, and much easier to diagnose than a
"cosmetic" difference that quietly changes what was signed.
