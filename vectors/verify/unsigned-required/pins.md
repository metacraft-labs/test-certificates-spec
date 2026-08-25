# verify/unsigned-required

**Pins:** a consumer that requires signatures rejects unsigned
certificates outright — and both spellings of "unsigned" mean the same thing.

| Rule | Where |
| ---- | ----- |
| Consumers requiring signatures MUST reject unsigned certificates rather than accepting them at reduced confidence | Standard.md §6 |
| "Signed or not" is decidable and MUST be decided | Standard.md §6 |
| An omitted signature block and an empty one both mean unsigned, and MUST be treated identically | Canonical-Payload.md §6 |
| An unsigned certificate is well-formed but carries no protection against forgery | Standard.md §6 |

The two certificates differ only in how they spell "unsigned":
`a-no-signature-block.toml` omits `[certificate.signature]` entirely, while
`b-empty-signature-block.toml` carries it with empty `algorithm` and `value`.
Between them they would cover the requirement if signatures were not required.

Neither has a `key_id`, and neither has a signature block in its canonical
payload — the block is excluded from the payload in both cases, so the two
files' payloads are distinguished only by their targets.

**Would be wrong if:** the implementation accepted these "at lower confidence",
or accepted the empty-block form because a `[certificate.signature]` table
exists.
