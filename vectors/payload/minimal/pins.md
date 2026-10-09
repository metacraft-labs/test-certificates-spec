# payload/minimal

**Pins:** the baseline shape — required fields only, every optional key
absent rather than empty.

| Rule | Where |
| ---- | ----- |
| Key order is fixed and is not alphabetical | Canonical-Payload.md §2 rule 1 |
| One space either side of `=` | §2 rule 2 |
| `key_id` is omitted entirely when unsigned, never emitted empty | §2 rule 3 |
| `untracked` is a bare TOML boolean, never quoted | §2 rule 4 |
| One blank line after `schema`, one between tables, no others | §2 rule 5 |
| At least one `[[certificate.command]]`, preceded by a blank line | §2 rule 6 |
| `paths` omitted entirely for a whole-repository claim, never `[]` | §2 rule 8 |
| `content` emitted verbatim, as a quoted string | §2 rules 9, 11 |
| `base` omitted entirely when absent, never emitted empty | §2 rule 10 |
| LF endings, trailing newline, no BOM, no trailing whitespace | §1 |

**Would be wrong if:** an implementation sorted keys alphabetically, emitted
`key_id = ""`, emitted `paths = []` or `base = ""`, quoted `untracked`, or
omitted the final newline.

**Paired with `signed`:** the two canonical payloads differ by exactly one line.
