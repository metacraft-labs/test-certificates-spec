# signature/mutated-payload

**Pins:** the signature covers the payload bytes, and
one flipped bit is enough. **This vector MUST fail.**

| Rule | Where |
| ---- | ----- |
| The signature is over the canonical payload | Standard.md §6 |
| A verifier MUST NOT "repair" a payload into validity | Canonical-Payload.md §5 |

`canonical.txt` is `vectors/payload/minimal/canonical.txt` with the last hex
digit of the content id changed from `…7766` to `…7767`. `signature.b64` is the
signature over the *original* payload, unmodified.

The mutation is deliberately invisible to everything except the signature: the
result is still a well-formed v1 certificate, still `passed`, with a perfectly
plausible `git-tree-sha1` content id of the right length. Nothing but the
cryptography can tell that it now attests to content nobody tested — content
that some other, untested working tree might well have. That is the
substitution a signature exists to prevent, and this vector is one character
wide because that is how wide the real attack is.

This is also the suite's self-test: a conformance suite that cannot detect its
own corruption pins nothing. If your walker reports this vector as verifying,
your walker is not actually checking anything.
