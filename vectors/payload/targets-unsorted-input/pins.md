# payload/targets-unsorted-input

**Pins:** `targets` is sorted on output even though the input is in run
order — and `argv` is *not*, in the same vector.

| Rule | Where |
| ---- | ----- |
| `targets` is serialized in ascending byte order, not run order | Canonical-Payload.md §3 |
| Array form: `["a", "b"]`, comma + one space, no trailing comma, no inner padding | §3 |
| `argv` is never sorted | §2 rule 7 |

**Would be wrong if:** an implementation preserved the run order (the payload
would start `["t-unit", …]`), or "helpfully" sorted the `--targets` argument
inside `argv` to match.
