# verify/content-unknown-algorithm

**Pins:** an algorithm the consumer cannot compute is **not a
mismatch** — the record is unevaluated and the outcome is unverifiable.

| Rule | Where |
| ---- | ----- |
| A consumer that cannot compute the certificate's algorithm for this state has not established a mismatch; the certificate is unverifiable, not invalid | Verification.md §4.1.1, Content-Id.md §5 |
| Content ids in different algorithms are never compared | Content-Id.md §1 |
| An interpretable record that could not be evaluated is decisive only if it could have satisfied part of the requirement | Verification.md §7.1 |
| Unverifiable MUST NOT be reported as not-covered | Verification.md §7 |

`state.json` lists only a `git-tree-sha1` id: this consumer computes nothing
else. Both certificates are signed by an active key, on the required platform:

| Certificate | Covers | `content` algorithm |
| ----------- | ------ | ------------------- |
| `a-manifest.toml` | `t-unit` | `manifest-v1-sha256` — defined by this standard, not implemented by this consumer |
| `b-unknown-algorithm.toml` | `t-integration` | `blake3-manifest-v1` — defined by no revision of this standard |

Together they would cover the requirement, if either id matched. The consumer
cannot tell whether they do, so it cannot say "run the tests": the remedy is a
consumer that implements the algorithm.

`b-unknown-algorithm.toml` pins that an algorithm unknown to the *standard* is
handled the same way: its id has a `:` and a lowercase hex digest, so it is
well-formed, and its length cannot be judged because only the algorithm
defines it (Content-Id.md §1). It is unevaluated, not rejected.

**Would be wrong if:** the implementation compared the ids as strings against
the `git-tree-sha1` id it has and reported not-covered; treated a
`manifest-v1-sha256` id as malformed because it is not a git tree id; rejected
`blake3-manifest-v1` as malformed; or translated between algorithms.

**Paired with `content-malformed`:** the same "no match was found", reached for
the opposite reason.
