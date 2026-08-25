# payload/multiple-commands

**Pins:** command entries stay in execution order, each preceded by
exactly one blank line.

| Rule | Where |
| ---- | ----- |
| `[[certificate.command]]` entries appear in execution order and MUST NOT be sorted | Canonical-Payload.md §2 rule 6 |
| Each entry is preceded by one blank line | §2 rule 6 |
| No blank lines other than the table separators | §2 rule 5 |

The execution order here is deliberately not any sorted order: sorting the
entries by `argv` would move `example-test report` to the front and swap `t-integration`
ahead of `t-unit`. The payload keeps the order the commands ran in, because
that order is part of the claim.

**Would be wrong if:** the implementation sorted the entries, deduplicated the
two `example-test run` invocations, separated entries with two blank lines, or emitted
the array-of-tables as a single inline array.
