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

Certificates attach to the commit they attest, in a dedicated notes ref:

```
refs/notes/<vendor>/certificates
```

A note is data attached to a commit **without changing its SHA**, which is what
makes this work: a certificate can be produced after the commit exists — indeed
it must be, since it attests to that exact commit — without rewriting history.

- The notes tree maps `<commit-sha>` to a blob holding the certificate(s).
- **Multiple certificates per commit are normal**, typically one per platform.
  A carrier MUST support several, and a verifier MUST evaluate their union
  ([Verification §4](./Verification.md#4-coverage-is-a-union)).
- **Notes are not pushed or fetched by default.** Producers must push the notes
  ref explicitly, and verifiers must fetch it. Forgetting this is the most common
  operational failure with this carrier, and it presents as "no certificates"
  rather than as an error.
- **Notes are mutable** — anyone with push access can rewrite them. This is
  exactly why §1 holds: a note's contents are worth what their signature is
  worth, and nothing more.

A verifier MUST ignore notes whose `commit` field does not match the commit they
are attached to. Attaching a valid certificate for commit A to commit B is
otherwise a trivial confusion attack, and both records look individually fine.

### 2.1 Multiple records in one note

When several certificates share a note blob, they MUST be framed so a reader can
split them unambiguously without parsing TOML — a delimiter line that cannot
occur inside a certificate. Implementations MUST NOT rely on blank-line
separation, since a certificate may legitimately contain blank lines.

## 3. Other carriers

| Carrier | Notes |
| ------- | ----- |
| A dedicated ref (`refs/certificates/<commit>`) | Immutable-by-convention; needs its own push/fetch discipline |
| A file beside the lock or in the build output | Simple; travels with an artifact rather than with history |
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
