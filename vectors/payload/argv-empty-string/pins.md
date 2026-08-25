# payload/argv-empty-string

**Pins:** an empty argument survives as `""`.

| Rule | Where |
| ---- | ----- |
| `argv` is the argument vector as executed, unshelled | Standard.md §3.3 |
| `argv` is never sorted or deduplicated | Canonical-Payload.md §2 rule 7 |

An empty argument is an ordinary argument. `example-test run --selector "" --prefix ""`
selected everything with no prefix; dropping the empty strings would describe
`example-test run --selector --prefix -v`, a different and probably invalid command.

Two empty arguments appear, so an implementation that deduplicates `argv` is
caught here as well as by `argv-duplicates`.

**Would be wrong if:** the implementation filtered falsy elements out of the
vector — the single most common way this breaks, since `""` is falsy in most
languages — or collapsed the two empty strings into one.
