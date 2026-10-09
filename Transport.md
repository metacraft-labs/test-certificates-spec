# Transport

How certificates travel from the machine that issued them to whoever needs to
check them.

## 1. The signed payload is the unit of trust

Transport is **not** a trust boundary. A certificate's integrity comes entirely
from its signature over the canonical payload; it does not come from where the
certificate was found, who put it there, or how it arrived.

This has one practical consequence worth stating plainly, because it is easy to
get backwards: **the existence of a certificate in a trusted location proves
nothing.** A verifier MUST check the signature regardless of provenance, and MUST
NOT accept a certificate merely because it appeared somewhere only authorised
parties can write.

It follows that carriers are interchangeable, and that a project may use several
at once. The rest of this document describes carriers, not requirements.

## 2. Git notes (recommended)

Certificates attach to the **tree object their content id names**, in a
dedicated notes ref:

```
refs/notes/<vendor>/certificates
```

A note is data attached to a git object without changing it, and the annotated
object may be any object — a tree as readily as a commit. For a certificate
whose `content` is `git-tree-sha1:<oid>` or `git-tree-sha256:<oid>`
([Content-Id §4.1](./Content-Id.md#41-git-tree-sha1-and-git-tree-sha256)), the
note is keyed by `<oid>`.

Keying by content rather than by commit is what the content binding requires:

- **At issuance there is no commit to attach to.** The certificate is produced
  before the commit is made ([Standard §3.2.2](./Standard.md#322-certifying-before-the-commit)).
  The tree object exists — computing the content id with `git write-tree` wrote
  it — so the note can be added immediately.
- **One note serves every commit with that content.** A verifier evaluating
  commit `C` looks up the notes on `C^{tree}`; a pre-commit gate looks up the
  notes on the tree `git write-tree` returns for the index being committed.
  Neither needs to know which commit, if any, the producer was on.

Rules:

- The notes tree maps `<tree-oid>` to a blob holding the certificate(s).
- **Multiple certificates per content are normal**, typically one per platform.
  A carrier MUST support several, and a verifier MUST evaluate their union
  ([Verification §5](./Verification.md#5-coverage-is-a-union)).
- **A scoped certificate is keyed by its scoped tree**, the tree holding only
  the in-scope entries ([Content-Id §4.1](./Content-Id.md#41-git-tree-sha1-and-git-tree-sha256)).
  A consumer therefore finds it only by computing that scoped id for the state
  in front of it — which requires knowing the scope. Scopes a framework
  declares in its version-controlled configuration are known in advance; a
  consumer that accepts other scopes has to enumerate the notes ref instead.
  Scoping trades discoverability for a narrower claim, and a producer SHOULD
  only scope when its consumers can find the result.
- **Notes are not pushed or fetched by default.** Producers must push the notes
  ref explicitly, and verifiers must fetch it. Forgetting this is the most common
  operational failure with this carrier, and it presents as "no certificates"
  rather than as an error. A pre-commit gate needs only the local notes ref; a
  receiving-side gate needs it pushed alongside the commits it covers.
- **Notes are mutable** — anyone with push access can rewrite them. This is
  exactly why §1 holds: a note's contents are worth what their signature is
  worth, and nothing more.
- **An annotated tree need not be reachable**, and the notes ref does not keep it
  alive. That costs nothing: a verifier computes the content id of the state in
  front of it and looks the note up by that id, so it never needs the producer's
  tree object.

A verifier MUST ignore a note whose certificate's `content` does not name the
object the note is attached to, and SHOULD report it. The content check would
reject such a certificate anyway; the rule is stated so that a misattached
record is reported as a carrier fault rather than as untested content.

`manifest-v1-sha256` content ids name no git object, and travel by the other
carriers (§3).

### 2.1 Multiple records in one note

When several certificates share a note blob, they MUST be framed so a reader can
split them unambiguously without parsing TOML — a delimiter line that cannot
occur inside a certificate. Implementations MUST NOT rely on blank-line
separation, since a certificate may legitimately contain blank lines.

## 3. Other carriers

| Carrier | Notes |
| ------- | ----- |
| A dedicated ref (`refs/certificates/<algorithm>/<digest>`) | Keyed by content id, for any algorithm; immutable-by-convention; needs its own push/fetch discipline |
| A directory of files named by content id | Simple; local to a checkout or travels with an artifact rather than with history. Must not be tracked: a tracked certificate would change the content it attests |
| A CI artifact | Natural where the issuer is CI; needs an out-of-band way to find it |
| An HTTP endpoint | Useful for central verification; the endpoint is not a trust input |

All are equally acceptable. The signature is what is checked in every case.

## 4. Discovery

A verifier needs to find candidate certificates before it can evaluate them.
Whatever the carrier, discovery MUST be:

- **Explicit** about what it searched. "No certificates found" and "certificates
  found but none matched" are different outcomes and MUST be reported
  differently — the first usually means a fetch or push was missed, the second
  means the state genuinely is not covered.
- **Non-fatal when empty.** An absent certificate store is a normal state for a
  project that does not use certificates, and MUST NOT be an error in itself.
  Whether *absence* blocks anything is a consumer policy decision, made after
  discovery, not during it.
