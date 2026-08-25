# payload/signed

**Pins:** `key_id` is present and last in `[certificate]`, after `issuer`.

| Rule | Where |
| ---- | ----- |
| `key_id` is emitted when the certificate is signed | Canonical-Payload.md §2 rule 3 |
| `key_id` follows `issuer`; the order is fixed, not alphabetical | §2 rule 1 |
| The signature block is excluded from the payload | §2 |

**Would be wrong if:** an implementation placed `key_id` alphabetically (it
would land between `issuer` and `platform`), or folded the signature block into
the payload.

**Paired with `minimal`:** identical except for the single `key_id` line. An
implementation that produces both correctly has proved rule 3 in both
directions.
