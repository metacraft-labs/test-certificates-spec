# content/non-ascii-path

**Pins:** a path is the byte sequence the VCS records — no Unicode
normalisation, no case folding — so two names that render identically are two
different files.

| Rule | Where |
| ---- | ----- |
| `path` is the byte sequence the VCS records for the file — no Unicode normalisation, no case folding | Content-Id.md §4.2 |
| Records sort by raw path bytes | Content-Id.md §4.2 |
| Values are the exact code points parsed; no normalisation | Canonical-Payload.md §4 |

`entries.json` is written with `\u` escapes so the difference is visible:

| Path | Bytes |
| ---- | ----- |
| `café.txt` (precomposed, NFC) | `63 61 66 C3 A9 2E …` |
| `café.txt` (decomposed, NFD) | `63 61 66 65 CC 81 2E …` |
| `日本語/説明.md` | three-byte UTF-8 throughout |

The two `café` files are distinct tracked files with different content. On raw
bytes the decomposed one sorts first (`65` < `C3`). The scoped ids are for the
**precomposed** name only and must not take in the decomposed one.

macOS file systems historically normalised names, and git's
`core.precomposeUnicode` exists because of it. That is a question about what
the VCS records; once recorded, the bytes are the path.

**Would be wrong if:** the implementation normalised paths to NFC (merging the
two files or rejecting the duplicate), compared scope paths after
normalisation, sorted by code point after decoding through UTF-16, or escaped
non-ASCII in a record.
