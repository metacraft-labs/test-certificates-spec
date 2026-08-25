# payload/unscoped

**Pins:** an empty scope is a whole-repository claim, and is omitted from
the payload entirely.

| Rule | Where |
| ---- | ----- |
| `paths` is omitted entirely when the claim covers the whole repository — never emitted as `[]` | Canonical-Payload.md §2 rule 8 |
| An omitted key and an empty array are different payloads | §2 rule 8 |
| Consumers MUST treat absent or empty `paths` as a whole-repository claim | Standard.md §3.2.1 |

The input deliberately carries `"paths": []` rather than omitting the key, so
the vector tests the interesting direction: a producer holding an empty scope
list must drop the key rather than serialize the empty array.

**Would be wrong if:** the implementation emitted `paths = []`. That is a
*different payload*, so it produces a different signature, and a verifier
reconstructing the canonical form from the parsed fields would reject the
certificate against its own valid signature.

**Paired with `scoped`:** same claim shape, opposite side of rule 8.
