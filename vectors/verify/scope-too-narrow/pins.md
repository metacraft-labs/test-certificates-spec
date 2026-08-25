# verify/scope-too-narrow

**Pins:** a scoped certificate is not a whole-repository
certificate.

| Rule | Where |
| ---- | ----- |
| When `paths` is present, the claim covers only those paths; a consumer requiring broader coverage MUST reject it | Verification.md §4.1, §4.1.2 |
| Treating a scoped certificate as a whole-repository one is the mistake the field exists to prevent | Verification.md §4.1.2 |
| `clean` and `untracked` are relative to `paths` | Standard.md §3.2.1 |

The certificate says `clean = true`, and it is telling the truth — *within
`src/db-backend`*. It says nothing whatever about the rest of the tree, and the
requirement here (`paths: null`) is the whole repository.

`requirement.json` expresses the needed scope: `null` means the whole
repository, and a list means those paths must fall inside the certificate's
scope.

**Would be wrong if:** the implementation read `clean = true` and stopped,
which is the failure mode scoping introduces — a certificate that is formally
clean and substantively narrower than the claim being relied on.
