# signature/minimal

**Pins:** the happy path — the canonical payload of
`vectors/payload/minimal`, signed under the namespace the standard names, and
verifying against the registered public key.

| Rule | Where |
| ---- | ----- |
| OpenSSH ed25519 detached signatures (`ssh-keygen -Y sign` / `-Y verify`) | Standard.md §6.1 |
| The namespace for this schema version is `test-certificate-v1` | Standard.md §6.1 |
| `algorithm` is `ed25519`; `value` is base64 of the detached signature blob | Standard.md §6.1 |
| The signature covers the canonical payload, excluding the signature block | Standard.md §6, Canonical-Payload.md §2 |

`canonical.txt` is byte-identical to `vectors/payload/minimal/canonical.txt`.
The two groups share bytes on purpose: an implementation whose serializer is
off by one byte fails here as well, and the failure says which of the two
things is broken.

**Direction of the test.** An implementation passes by **verifying**, not by
reproducing `signature.b64`. ed25519 is deterministic under RFC 8032, so the
signature bytes are in fact reproducible with the private key in `keys/` — but
SSH signature *framing* is an implementation's own business, so verification is
the normative direction (Conformance.md §2).
