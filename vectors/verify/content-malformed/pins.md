# verify/content-malformed

**Pins:** a malformed content id is **decidably invalid** — rejected,
never repaired, and never unverifiable.

| Rule | Where |
| ---- | ----- |
| A content id is `<algorithm>:<digest>`; the algorithm ends at the first `:`, and the digest is lowercase hex of exactly the algorithm's length | Content-Id.md §1 |
| A malformed content id makes the record decidably invalid; it is rejected without repair | Verification.md §4.1.1, Content-Id.md §1 |
| A decidably invalid record is not unverifiable | Verification.md §7 |
| A verifier MUST NOT "repair" a record into validity | Canonical-Payload.md §5, Content-Id.md §1 |

Four certificates, each claiming both required targets, each one plausible
repair away from matching the state's `git-tree-sha1:9f8e7d6c…`:

| Certificate | `content` | The tempting repair |
| ----------- | --------- | ------------------- |
| `a-uppercase.toml` | `git-tree-sha1:9F8E7D6C…` | lowercase it |
| `b-abbreviated.toml` | `git-tree-sha1:9f8e7d6c5b4a` | match it as an abbreviation, as git does for object ids |
| `c-no-algorithm.toml` | `9f8e7d6c…` | assume `git-tree-sha1`, as the earlier draft's bare tree ids were |
| `d-second-colon.toml` | `git-tree-sha1:sha1:9f8e7d6c…` | split at the *last* `:` |

The last one also pins where the algorithm ends. Split at the first `:`, the
digest is `sha1:9f8e…`, which is not hex: malformed, rejected. Split at the
last, the algorithm becomes `git-tree-sha1:sha1` — one this consumer cannot
compute — and the record would be unevaluated and the outcome
**unverifiable**. The first `:` is the rule.

None of the certificates is signed and the requirement does not demand
signatures, so nothing else can be blamed for the rejections: the records
themselves are invalid.

**Would be wrong if:** the implementation repaired any of the four into a
match, or reported unverifiable for any of them — a malformed field is
something the consumer *can* judge.

**Paired with `content-unknown-algorithm`:** a *well-formed* id in an algorithm
the consumer cannot compute is unverifiable. And with `unknown-schema`, the
original form of the pair: a record that is wrong is not a record that cannot
be read.
