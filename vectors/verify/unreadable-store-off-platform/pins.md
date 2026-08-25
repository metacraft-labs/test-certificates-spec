# verify/unreadable-store-off-platform

**Pins:** a record the consumer **can** interpret but could not verify makes the
outcome `unverifiable` **only if its interpreted scope could satisfy some part
of the requirement**. This one cannot, so the outcome is `not-covered`.

| Rule | Where |
| ---- | ----- |
| Unverifiable wins only when an unevaluable record is *potentially relevant* | Verification.md §7.1 rule 2 |
| For an interpretable record, relevance is assessable, and an out-of-scope record is not potentially relevant | Verification.md §7.1, second bullet |
| An unreadable store answers nothing about the certificates it covers | Verification.md §3.1 |
| The record MUST still be named in the report | Verification.md §7.1 |

Beyond the required set (Conformance.md §3): added with the Verification.md
§7.1 relevance rule it defends.

The key store is unparseable, exactly as in `unreadable-store`, so the consumer
cannot decide whether the certificate's signer is trusted. The difference is
what the certificate claims: `t-bench` on `macos/arm64`, while the requirement
asks for `t-integration` and `t-unit` on `linux/amd64`.

Here the fields *can* be trusted — this is a `test-certificate.v1` record, in
the schema this consumer implements. So the consumer can say something stronger
than "I could not check the signature": it can say the signature **would not
have mattered**. However that check had come out, this certificate contributes
nothing to `linux/amd64`. The gap is real, it is known, and the honest report is
`not-covered` with the gap named — plus the unevaluated record listed, because
the operator should still fix the corrupt store.

**Would be wrong if:** the implementation treated any unevaluable record as
decisive and reported `unverifiable` — telling an operator to go fix a
configuration file when the actual problem is that nobody has run
`t-integration` or `t-unit` on `linux/amd64`. That instruction wastes the one
thing the third outcome exists to protect: the operator's ability to trust what
the report tells them to do.

**The mirror of this case is `unknown-schema-off-platform`**, where the record
looks equally irrelevant but cannot be interpreted, so its irrelevance cannot be
established and the outcome is `unverifiable`.
