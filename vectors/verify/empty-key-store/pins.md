# verify/empty-key-store

**Pins:** an empty key store means "no signers are trusted", never
"no restrictions".

| Rule | Where |
| ---- | ----- |
| An empty or missing store is fail-closed | Verification.md §3.1 |
| It MUST NOT be read as "no restrictions" | Verification.md §3.1 |

The store parses perfectly. It declares `schema = "registered-keys.v1"` and
registers nobody, so the certificate's `key_id` resolves to nothing and the
certificate is rejected.

**Would be wrong if:** the implementation treated an empty registry as "skip
signature checking" — the classic fail-open bug, which turns a misconfigured
verifier into one that accepts anything.

**Contrast with `unreadable-store`:** the store was read, and it said no
signers. That is a decidable answer, so this is **not-covered**, not
unverifiable. The two cases differ by whether the consumer *could tell*.
