# payload/argv-duplicates

**Pins:** repeated arguments are retained, in place.

| Rule | Where |
| ---- | ----- |
| `argv` is never sorted or deduplicated | Canonical-Payload.md §2 rule 7 |
| Producers record what was actually run, not a normalised form | Standard.md §3.3 |

`--filter` appears three times and `slow` twice, adjacently. Both repetitions
are meaningful: `--filter slow --filter slow` is what the process was actually
given, and a certificate that silently reported `--filter slow --filter fast`
would be describing a command that never ran.

**Would be wrong if:** the implementation reused its `targets` pipeline
(sort + dedup) for `argv`, collapsed adjacent duplicates, or normalised
repeated flags into a set.
