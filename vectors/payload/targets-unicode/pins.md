# payload/targets-unicode

**Pins:** sorting is over UTF-8 **bytes** — not locale collation, and not
UTF-16 code units.

| Rule | Where |
| ---- | ----- |
| Ascending byte order, a plain lexicographic sort over the UTF-8 bytes | Canonical-Payload.md §3 |
| Non-ASCII is emitted literally as UTF-8 | §4 |

The eight targets share the prefix `t-`; the first differing byte decides:

| Target | First differing byte(s) |
| ------ | ----------------------- |
| `t-Zebra` | `5A` |
| `t-apple` | `61` |
| `t-banana` | `62` |
| `t-zebra` | `7A` |
| `t-Ápple` (U+00C1) | `C3 81` |
| `t-äpple` (U+00E4) | `C3 A4` |
| `t-Ａpple` (U+FF21) | `EF BC A1` |
| `t-😀` (U+1F600) | `F0 9F 98 80` |

**Would be wrong if:**

- the implementation used locale collation — `en_US` would produce
  `apple, Ápple, äpple, banana, zebra, Zebra, …`, mixing case and folding
  accents;
- the implementation compared **UTF-16 code units** — U+1F600 encodes as the
  surrogate pair `D83D DE00`, and `D83D < FF21`, so `t-😀` would sort *before*
  `t-Ａpple`. This is the default string comparison in several languages, and
  it is the failure this vector exists to catch;
- the implementation sorted by grapheme, by case-folded value, or by any
  normalized form.
