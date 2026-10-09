# verify/earlier-draft-record

**Pins:** a record in the pre-2026-10-09 shape — `commit`, `clean`,
no `content` — is **decidably invalid**: not covered, never unverifiable, and
never translated.

| Rule | Where |
| ---- | ----- |
| `content` is a required field of `[certificate.vcs]` | Standard.md §3.2 |
| A record missing a required v1 field is decidably invalid and contributes nothing | Standard.md §7, Verification.md §7 |
| An earlier-draft record shares the schema id `test-certificate.v1`, lacks `content`, and is decidably invalid — not covered, never unverifiable | Canonical-Payload.md §7.1 |
| Earlier-draft records MUST NOT be translated into the new shape | Canonical-Payload.md §7.1 |

The record is exactly what `ct test` shipped before the revision: a clean-tree
certificate naming `commit = "a858…"` — the very commit `state.json` evaluates
— with `clean = true`. Read with the earlier draft's rules, it would cover the
requirement.

It declares `schema = "test-certificate.v1"`, the schema this consumer
implements, so it is not an unknown schema version and is not unverifiable. It
is a v1 record missing a required field. The remedy is to run the tests again,
which issues a record in the current shape.

It is unsigned, and the requirement does not demand signatures, so nothing
else can be blamed for the rejection.

**Would be wrong if:** the implementation translated `commit` into a content id
(`a858…^{tree}`) and matched it — the record's signer, had there been one,
never signed that payload; accepted `clean = true` as evidence; or reported
unverifiable because the shape is "from another version".
