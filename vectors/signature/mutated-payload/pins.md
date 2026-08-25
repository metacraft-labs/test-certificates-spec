# signature/mutated-payload

**Pins:** the signature covers the payload bytes, and
one flipped bit is enough. **This vector MUST fail.**

| Rule | Where |
| ---- | ----- |
| The signature is over the canonical payload | Standard.md §6 |
| A verifier MUST NOT "repair" a payload into validity | Canonical-Payload.md §5 |

`canonical.txt` is `vectors/payload/minimal/canonical.txt` with the last hex
digit of the commit id changed from `…b5c4` to `…b5c5`. `signature.b64` is the
signature over the *original* payload, unmodified.

The mutation is deliberately invisible to everything except the signature: the
result is still a well-formed v1 certificate, still `passed`, still clean, with
a perfectly plausible 40-hex commit id. Nothing but the cryptography can tell
that it now attests to a commit nobody tested. That is the substitution a
signature exists to prevent, and this vector is one character wide because that
is how wide the real attack is.

This is also the suite's self-test: a conformance suite that cannot detect its
own corruption pins nothing. If your walker reports this vector as verifying,
your walker is not actually checking anything.
