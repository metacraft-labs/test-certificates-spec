# Vector signing keys

> **These private keys are published. They are worthless as keys, and using one
> anywhere outside this vector suite is a security incident.**
>
> Never register `insecure-test-key.pub` or `insecure-other-key.pub` in a real
> registered-key store. Anyone who has read this repository — which is
> everyone — can mint a certificate that verifies against them.

| File | Role |
| ---- | ---- |
| `insecure-test-key` / `.pub` | The "good" signer. Registered as `example-key-2026-q2`, status `active`, in the verify vectors' key stores. |
| `insecure-other-key` / `.pub` | A second, unrelated signer. Registered as `example-key-2025-q4`, status `revoked`, and used by `signature/wrong-key`. |

## Why the private keys are here at all

Conformance.md §2 makes verification the normative direction: an implementation
passes the signature vectors by checking them, never by reproducing the bytes.
Nothing about running the suite needs a private key.

They are published anyway so that the vectors are **auditable and
re-derivable**. A reader who suspects a signature vector was fabricated — that
`wrong-namespace` fails because someone corrupted the bytes rather than because
the namespace differs — can regenerate the whole group and compare:

```sh
python3 tools/regenerate.py --check    # exits non-zero if anything would change
```

That is only possible with the signing keys in hand, and a vector suite nobody
can check is exactly the thing this repository exists to replace.

## Determinism

ed25519 signatures are deterministic (RFC 8032 §5.1.6: the nonce is derived
from the key and the message, not from randomness), and OpenSSH's signature
framing adds nothing random. Signing the same payload with the same key
therefore reproduces the same bytes, on any machine, forever — which is what
makes `--check` meaningful.

## File modes

Git records no file mode beyond the executable bit, so these private keys
arrive world-readable from a clone and `ssh-keygen` refuses to load them.
`tools/ssh_sig.py` copies a key to a temporary directory with mode `0600`
rather than mutating the checkout. A consumer doing this by hand needs the
same step:

```sh
install -m 600 vectors/signature/keys/insecure-test-key /tmp/k
```
