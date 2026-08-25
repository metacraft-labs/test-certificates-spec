# signature/wrong-namespace

**Pins:** domain separation is applied, not ignored.
**This vector MUST fail.**

| Rule | Where |
| ---- | ----- |
| The namespace for this schema version is `test-certificate-v1` | Standard.md §6.1 |
| "Domain separation is not optional. Without it, a signature obtained for another purpose can be replayed as a certificate signature over identical bytes." | Standard.md §6.1 |

The signature here is **genuine**: made by the key in `key.pub`, over exactly
the bytes in `canonical.txt`, with no tampering anywhere. The only difference
from `minimal` is that it was produced under the namespace `git` — the
namespace OpenSSH uses for git commit and tag signatures.

So this vector is the replay attack, spelled out: a developer who signs commits
with their SSH key has produced signatures over arbitrary bytes under `git`. If
a verifier checks the signature but not the namespace, any of those becomes a
test certificate.

**It must fail for the right reason.** `ssh-keygen -Y verify` reports
`namespace does not match` — not a bad signature, not a bad key, not different
bytes. An implementation that fails this vector because it compared the payload
wrongly is failing it by accident and has not proved anything. Check the reason
your implementation gives.

**Would be wrong if:** the implementation passed the certificate's own
namespace through from a field, used the empty namespace, or reused a generic
"verify this SSH signature" helper whose namespace argument defaults to
something else.
