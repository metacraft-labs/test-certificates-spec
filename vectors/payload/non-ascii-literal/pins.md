# payload/non-ascii-literal

**Pins:** UTF-8 is emitted literally, and no Unicode normalization is
applied.

| Rule | Where |
| ---- | ----- |
| Non-ASCII characters are emitted literally, never as `\uXXXX` | Canonical-Payload.md §4 |
| The payload is UTF-8 with no BOM | §1 |
| Values are emitted as the exact code points parsed; no normalization | §4 |

`project` mixes a 2-byte (`ö`), 3-byte (`日本語`) and 4-byte (`😀`) sequence, so
an implementation that re-encodes through UTF-16 or escapes above the BMP shows
up here.

**The normalization trap.** Two of the three targets *look* identical:

| Target | Code points | Bytes after `t-` |
| ------ | ----------- | ---------------- |
| `t-ascii` | `61 73 63 69 69` | `61 …` |
| `t-é` (second) | `U+0065 U+0301` | `65 CC 81` |
| `t-é` (third) | `U+00E9` | `C3 A9` |

They are different values. They MUST NOT be normalized into each other and MUST
NOT be deduplicated: the array keeps both, decomposed first because `65 < C3`.

**Would be wrong if:** the implementation emitted `\u00e9` or
`\ud83d\ude00`, applied NFC/NFD anywhere in the pipeline (which would collapse
the array to two elements, or reorder it), or wrote a BOM.
