# verify/unknown-schema-off-platform

**Pins:** a record the consumer cannot interpret is **potentially relevant
whatever its fields appear to say**, so the outcome is `unverifiable` even
though the record looks irrelevant.

| Rule | Where |
| ---- | ----- |
| Unverifiable wins over not-covered when an unevaluable record is potentially relevant | Verification.md §7.1 rule 2 |
| Relevance is a schema-dependent judgement, so it is undecidable for an uninterpretable record and MUST be assumed | Verification.md §7.1, "Potential relevance is only assessable for a record you can interpret" |
| An unimplemented schema version is unverifiable, not invalid | Verification.md §7, Standard.md §7 |

Beyond the required set (Conformance.md §3): added with the Verification.md
§7.1 relevance rule it defends.

The requirement asks for `t-integration` and `t-unit` on `linux/amd64`. The one
record present is `test-certificate.v2` and *appears* to be about `t-bench` on
`macos/arm64` — that is, it appears to be irrelevant, and a consumer that
believed the appearance would report `not-covered`.

It MUST NOT believe it. Those fields were read with a v1 parser out of a record
the consumer has just declared it cannot interpret. A v2 might redefine what
`platform` means, or add a field that widens what the record covers, or express
its targets somewhere this parser never looked. The consumer cannot tell whether
this record mattered, and "I cannot tell" is exactly what `unverifiable`
reports.

**Would be wrong if:** the implementation peeked at `platform` or `targets` in
an unimplemented schema version to rule the record out, and reported
`not-covered` — sending an operator to run tests when the fix is to implement
or upgrade a schema version.

**The mirror of this case is `unreadable-store-off-platform`**, where the record
*is* interpretable and the same apparent irrelevance is real, so the outcome is
`not-covered`. The two together are the pair: an implementation that answers
both the same way has collapsed the distinction in one direction or the other.
