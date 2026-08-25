# verify/unknown-schema

**Pins:** an unimplemented schema version is unverifiable, not
not-covered.

> Beyond the eleven cases required by Conformance.md §3. Added together with
> the clarification to Standard.md §7 that resolves a conflict between it and
> Verification.md §7 — see vectors/README.md, "Ambiguities this suite closed".

| Rule | Where |
| ---- | ----- |
| Unverifiable covers an unimplemented schema version | Verification.md §7 |
| A verifier does not accept a record whose `schema` it does not recognise as evidence | Standard.md §7 |

The record may well be a perfectly good certificate that covers everything
required. This consumer cannot read it, and cannot honestly say either that it
covers the requirement or that the requirement is uncovered.

The signature `value` here is deliberately not a real signature: no v1 verifier
should ever get far enough to look at it. An implementation that reports
"signature invalid" has read fields out of a record it already declared it
cannot interpret.

**Contrast with `other-framework`:** an unrecognised *framework* is somebody
else's business and is ignored, leaving a clean not-covered. An unrecognised
*schema* is this framework's business in a dialect this consumer does not
speak.
