# The Test Certificate Standard

> **Status:** Draft v1. Extracted from reprobuild's test-certificate design, made
> vendor-neutral so that any test runner or build system can issue certificates
> and any consumer can verify them.

The key words MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are to be interpreted
as in RFC 2119.

## 1. What a certificate asserts

> *On platform `P`, the test targets `T` for project `prj` produced result `R`,
> with the repository at commit `C` and its environment in the state described
> by binding `E`.*

A certificate is a claim about a **specific, identified state**. Everything in
the record exists either to identify that state precisely enough to check the
claim against it, or to say who made the claim.

## 2. The record

```toml
schema = "test-certificate.v1"

[certificate]
project     = "codetracer"
repo        = "codetracer"
commit      = "a858633c…"                  # exact commit the tests ran against
platform    = "linux/aarch64"              # OS/arch the tests executed on
targets     = ["t-unit", "t-integration"]  # the test targets this covers
result      = "passed"
issued_at   = "2026-06-23T10:14:33Z"       # RFC 3339, UTC
issuer      = "repro-daemon@build-host-7"  # who observed and issued
key_id      = "repro-sign-2026-q2"         # which key signed, when signed

[certificate.environment]
method = "reprobuild-lock"                 # how the binding was computed
value  = "blake3:9f2c…"                    # the binding itself

[certificate.signature]                    # OPTIONAL — see §5
algorithm = "ed25519"
value     = "base64(detached signature over the canonical payload)"
```

### 2.1 Fields

| Field | Required | Meaning |
| ----- | -------- | ------- |
| `schema` | yes | Format identifier. `test-certificate.v1` for this revision. |
| `project` | yes | Logical project the targets belong to. |
| `repo` | yes | Repository the commit belongs to. |
| `commit` | yes | Full commit identifier the tests ran against. |
| `platform` | yes | Platform the tests executed on, as `os/arch`. |
| `targets` | yes | Test targets covered. Order is not significant; canonicalization sorts them. |
| `result` | yes | `passed` is the only value that can support a positive claim. |
| `issued_at` | yes | RFC 3339 timestamp, UTC. |
| `issuer` | yes | Free-form identification of the issuing component. Informational; it is **not** a trust input. |
| `key_id` | when signed | Identifies the signing key, resolved against a key store (§5). |
| `environment` | yes | The environment binding (§3). |
| `signature` | no | Detached signature over the canonical payload (§5). |

A conforming producer MUST emit every required field. A conforming verifier MUST
reject a record missing any required field, and MUST reject an unrecognised
`schema`.

### 2.2 Binding fields

`commit`, `environment`, `platform` and `targets` are the **binding fields**.
They are what make a certificate checkable rather than merely assertive: a
verifier confirms the certificate describes the state actually in front of it.

A verifier MUST compare all four. A certificate that matches on `commit` alone
says nothing about whether the same dependencies, or the same platform, or the
same tests were involved.

## 3. The environment binding

A test result is only meaningful together with what the tests ran *against*.
Different ecosystems identify that differently — a lock file, a dependency
closure, a container digest, a Nix derivation, or nothing at all — so the
standard treats the binding as **opaque, with a declared method**.

```toml
[certificate.environment]
method = "reprobuild-lock"
value  = "blake3:9f2c…"
```

- `method` names how `value` was computed and therefore how it must be compared.
- `value` is an opaque string, meaningful only under its `method`.

Rules:

- A verifier MUST NOT compare bindings across different `method` values. Two
  bindings with different methods are **incomparable**, not unequal — a verifier
  that cannot evaluate a certificate's method MUST treat it as unverifiable
  rather than invalid, and say so.
- A method whose comparison is not plain string equality MUST define its
  comparison rule in its own specification.
- `method = "none"` declares that the issuer bound no environment state. Such a
  certificate is still well-formed, and still says something real about a commit
  on a platform. Consumers that require an environment binding MUST reject it;
  consumers that do not, MAY accept it. It MUST NOT be silently treated as
  equivalent to a bound certificate.

The registry of methods is deliberately open. Known values at v1:

| `method` | Comparison | Defined by |
| -------- | ---------- | ---------- |
| `none` | Always incomparable to a bound certificate | This document |
| `lockfile-digest` | String equality over `<algo>:<hex>` of the lock file bytes | This document |
| `reprobuild-lock` | String equality over the resolved workspace lock digest | reprobuild |

## 4. Partial coverage is normal

A certificate covers exactly the targets that ran, on the platform that ran them.
Producers MUST NOT claim targets that did not run, or a platform they did not
run on.

It follows that full coverage is frequently expressed as **several
certificates** — one per platform, or one per partial run — and that consumers
evaluate the **union** (§ [Verification](./Verification.md)). This is the normal
case, not a degraded one: a developer with a Linux box and a macOS box produces
two certificates, and neither is deficient.

## 5. Signatures

A signature is **OPTIONAL in the format and MAY be required by a consumer**.
This is the standard's whole position on trust: it defines how to sign and how
to check a signature, and leaves to each project the decision of whether an
unsigned certificate is worth anything.

- An unsigned certificate is well-formed. It carries no protection against
  forgery and MUST NOT be treated as if it did. It is useful where the producer
  and consumer are the same party, or where the certificate is informational.
- A signed certificate carries a detached signature over the canonical payload
  (§ [Canonical-Payload](./Canonical-Payload.md)), excluding the signature block
  itself.
- Consumers that require signatures MUST reject unsigned certificates outright,
  rather than accepting them at reduced confidence. "Signed or not" is a
  decidable question and MUST be decided.

### 5.1 The signing primitive

Conforming implementations MUST use **OpenSSH ed25519 detached signatures**
(`ssh-keygen -Y sign` / `ssh-keygen -Y verify`) under a **namespace** that
domain-separates test certificates from every other use of the same key
material. The namespace for this schema version is:

```
test-certificate-v1
```

Domain separation is not optional. Without it, a signature obtained for one
purpose can be replayed as a certificate signature over identical bytes.

`algorithm` MUST be `ed25519`; `value` MUST be the base64 of the detached
signature blob.

### 5.2 Issuance integrity

This is the one rule about *issuance* the standard does state, because it is
what a signature is worth rather than a matter of local policy:

> A conforming producer MUST make a signature obtainable **only** as a
> consequence of having actually executed the tests being attested. It MUST NOT
> expose any interface that signs a caller-supplied record.

A "sign this blob" entry point makes every certificate from that producer
worthless, because it lets any caller mint a claim about a test run that never
happened. A producer that offers one is not conforming, whatever else it does
correctly.

The *strength* of that guarantee is a deployment property (see the README):
it depends on whether the tested code can reach the signing key. The rule above
is what makes the guarantee meaningful at all, at any strength.

## 6. Conformance

A **conforming producer**:

- emits records satisfying §2 with a valid environment binding per §3
- claims only targets and platforms it actually ran (§4)
- if it signs, uses the primitive and namespace in §5.1 over the canonical
  payload, and satisfies the issuance-integrity rule in §5.2

A **conforming verifier**:

- rejects records with unknown `schema` or missing required fields
- compares all four binding fields (§2.2)
- treats unevaluable environment methods as unverifiable, not invalid (§3)
- evaluates coverage as a union across certificates
  (§ [Verification](./Verification.md))
- when signatures are required, verifies them per §5.1 and rejects unsigned
  records rather than downgrading them

Neither role requires implementing transport (§ [Transport](./Transport.md));
carriers are interchangeable and the signed payload is the unit of trust.
