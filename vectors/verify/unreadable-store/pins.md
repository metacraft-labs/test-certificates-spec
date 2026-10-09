# verify/unreadable-store

**Pins:** the third outcome. *We could not tell* is a different
answer from *we could tell, and it is not covered*.

| Rule | Where |
| ---- | ----- |
| Unverifiable covers an unreadable key store | Verification.md §7 |
| Unverifiable MUST NOT be reported as not-covered | Verification.md §7 |
| A consumer MAY treat unverifiable as failure for gating, provided it still *reports* it distinctly | Verification.md §7 |

The certificate here is fine. It is authentic-looking, matches the content, is on the
right platform, covering both required targets. The consumer simply cannot
determine whether its signer is trusted, because the store it would consult is
unreadable.

**Why this is the case implementations collapse.** Both `not-covered` and
`unverifiable` end up failing a gate, so an implementation that returns a
boolean passes its own tests and looks correct. The difference shows up in what
a human is told to do next:

| Outcome | What it tells the operator |
| ------- | -------------------------- |
| not-covered | run the tests |
| unverifiable | fix your configuration; re-running tests changes nothing |

**Contrast with `empty-key-store`:** a store that parses and registers nobody
is fail-closed and **not-covered** — the consumer asked and got an answer. A
store that cannot be parsed yields no answer at all.

**Would be wrong if:** the implementation reported not-covered, or crashed. A
crash is arguably honest and is still wrong: Verification.md §7 requires the
outcome to be *reported*, as one of three values.
