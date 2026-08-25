# signature/wrong-key

**Pins:** the signature must verify **against the registered
key**, not merely be a valid signature. **This vector MUST fail.**

| Rule | Where |
| ---- | ----- |
| A certificate is authentic when `key_id` resolves to an active key *and* the signature verifies under that key | Verification.md §3.1 |

The signature is valid, current, and made under the correct namespace — by a
different key (`keys/insecure-other-key`). `key.pub` holds the key a consumer
would have resolved from `key_id`.

**Would be wrong if:** the implementation extracted the public key from the
signature blob itself and verified against that. An SSH signature blob carries
its own public key, so "does this blob verify?" is answerable without any key
store at all — and answering it proves nothing about who signed.
