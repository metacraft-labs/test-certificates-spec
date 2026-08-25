# payload/targets-single

**Pins:** the one-element array has no separator and no trailing comma.

| Rule | Where |
| ---- | ----- |
| `["a"]` — no separator, no trailing comma, no spaces inside the brackets | Canonical-Payload.md §3 |

**Would be wrong if:** an implementation built the array by appending `", "`
after every element and then failed to trim, giving `["t-unit", ]`, or padded
the brackets as `[ "t-unit" ]`.
