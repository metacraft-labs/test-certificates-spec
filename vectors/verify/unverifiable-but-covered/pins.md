# verify/unverifiable-but-covered

**Pins:** precedence — unverifiable wins over not-covered, but not
over a requirement already met.

> Beyond the eleven cases required by Conformance.md §3. Added together with
> the precedence paragraph in Verification.md §7 — see vectors/README.md,
> "Ambiguities this suite closed".

| Rule | Where |
| ---- | ----- |
| Report unverifiable when something that could have changed the answer could not be evaluated | Verification.md §7 |
| When the requirement is met by fully evaluated certificates, the outcome is covered, and what could not be evaluated is reported alongside | Verification.md §7 |

`a-unit.toml` and `b-integration.toml` between them cover the requirement, and
both were evaluated end to end. `c-future.toml` could not be read at all — but
it claims `t-bench`, which nobody asked for, and admitting it could only ever
have *added* coverage.

Reporting unverifiable here would be unhelpful in the way the three-valued
outcome exists to avoid: it would tell the operator to go fix a configuration
problem in order to reach a conclusion that is already reached.

**Would be wrong if:** the implementation short-circuited to unverifiable on
first sight of an unreadable record, or silently dropped it from the report.
The record must still be named.
