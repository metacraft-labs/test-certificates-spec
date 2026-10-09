# verify/scope-too-narrow

**Pins:** a scoped certificate is not a whole-repository
certificate.

| Rule | Where |
| ---- | ----- |
| When `paths` is present, the claim covers only those paths; a consumer requiring broader coverage MUST reject it | Verification.md §4.1, §4.1.2 |
| Treating a scoped certificate as a whole-repository one is the mistake the field exists to prevent | Verification.md §4.1.2 |
| `content` and `untracked` are relative to `paths` | Standard.md §3.2.1 |

The certificate's `content` is a `git-tree-sha1` id scoped to
`src/db-backend`, and it is telling the truth: `state.json` lists the same id
for that scope. The content *within `src/db-backend`* is exactly what was
tested. The certificate says nothing whatever about the rest of the tree, and
the requirement here (`paths: null`) is the whole repository.

`requirement.json` expresses the needed scope: `null` means the whole
repository, and a list means those paths must fall inside the certificate's
scope. `state.json` lists the scoped id as well as the whole-repository one,
so a consumer that computes ids per scope finds a match and must reject on
scope alone.

**Would be wrong if:** the implementation found the content id matched and
stopped, which is the failure mode scoping introduces — a certificate whose
content binding is perfectly sound and whose claim is narrower than the one
being relied on.
