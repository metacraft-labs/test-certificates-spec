# verify/revoked-key

**Pins:** revocation beats cryptography, and it is a status flip
rather than a deletion.

| Rule | Where |
| ---- | ----- |
| Authentic requires `status = "active"` **and** a verifying signature | Verification.md §3.1 |
| Revocation is a status flip, never a deletion — the entry stays in the store | Verification.md §3.1 |

The signature over this certificate **does** verify: check it with
`ssh-keygen -Y verify` against the key in the store and it passes. The
certificate is rejected anyway.

The revoked key is still listed in `registered-keys.toml`, which is the point of
the rule: deleting it would make the certificate merely *unrecognised* rather
than *known bad*, and would erase the audit trail.

**Would be wrong if:** the implementation checked the signature and stopped, or
implemented revocation by removing the entry.

**Contrast with `unreadable-store`:** here the store answered the question, and
the answer was no. That is decidable, so the outcome is not-covered.
