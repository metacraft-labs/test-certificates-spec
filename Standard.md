# The Test Certificate Standard

> **Status:** Draft v1. Extracted from reprobuild's test-certificate design, made
> vendor-neutral so that any test runner or build system can issue certificates
> and any consumer can verify them.

The key words MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are to be interpreted
as in RFC 2119.

## 1. What a certificate asserts

> *On platform `P`, framework `F` executed commands `C` covering targets `T`,
> which produced result `R`, in repository `repo` whose working tree was in VCS
> state `V`.*

A certificate is a claim about a **specific, identified state**, made by a
**named framework**, about **commands it actually ran**.

The standard deliberately stops there. It does not describe dependency
closures, toolchain versions, container images or environment variables —
because it cannot describe them for every ecosystem, and a field it cannot
define precisely is worse than no field at all.

## 2. Why VCS state is the whole binding

The one thing every framework shares is that its inputs are **files in a
repository at a commit**. A test framework's configuration, its target
definitions, and — critically — **its lock file** are all under version control.

So the commit *already binds* them. A certificate that names a commit and
attests the tree was clean has, transitively, bound every committed input the
framework depends on, without the standard needing to know what those inputs
are or how to digest them.

This is why there is no environment digest, no lock hash, and no
method-tagged binding in this format. A framework that wants to check something
deeper resolves **its own lock file at that commit** and checks it however it
likes ([Verification §4](./Verification.md#4-framework-specific-validity)). The
standard's job is to say *which commit, and was it clean*; the framework's job
is to say *and here is what that means for me*.

The corollary matters just as much: **anything not under version control is not
bound by a certificate.** Uncommitted state, ambient tool versions, network
resources and sibling checkouts outside the repository are outside the claim. A
framework that depends on them must enforce that at issuance time — refusing to
issue when they are unclean — because no verifier can reconstruct them later.

## 3. The record

```toml
schema = "test-certificate.v1"

[certificate]
framework  = "reprobuild"                  # who issued, and whose rules apply
project    = "codetracer"
platform   = "linux/aarch64"               # OS/arch the tests executed on
targets    = ["t-integration", "t-unit"]   # test targets this covers (sorted)
result     = "passed"
issued_at  = "2026-06-23T10:14:33Z"        # RFC 3339, UTC
issuer     = "repro-daemon@build-host-7"   # informational, not a trust input
key_id     = "repro-sign-2026-q2"          # which key signed, when signed

[certificate.vcs]
repo       = "codetracer"
commit     = "a858633c…"                   # exact commit the tests ran against
clean      = true                          # no modifications to tracked files
untracked  = false                         # no untracked files present

[[certificate.command]]
argv = ["repro", "test", "--targets", "t-unit,t-integration"]

[certificate.signature]                    # OPTIONAL — see §6
algorithm = "ed25519"
value     = "base64(detached signature over the canonical payload)"
```

### 3.1 Fields

| Field | Required | Meaning |
| ----- | -------- | ------- |
| `schema` | yes | Format identifier. `test-certificate.v1` for this revision. |
| `framework` | yes | Identifies the issuing framework and therefore whose validity rules apply (§4). |
| `project` | yes | Logical project the targets belong to. |
| `platform` | yes | Platform the tests executed on, as `os/arch`. |
| `targets` | yes | Test targets covered. Sorted and deduplicated in canonical form. |
| `result` | yes | `passed` is the only value supporting a positive claim. |
| `issued_at` | yes | RFC 3339 timestamp, UTC. |
| `issuer` | yes | Free-form identification of the issuing component. Informational. |
| `key_id` | when signed | Identifies the signing key, resolved against a key store. |
| `vcs` | yes | The repository state the tests ran against (§3.2). |
| `command` | yes, ≥1 | The commands actually executed (§3.3). |
| `signature` | no | Detached signature over the canonical payload (§6). |

A conforming producer MUST emit every required field. A conforming verifier MUST
reject a record missing any required field, and MUST reject an unrecognised
`schema`.

### 3.2 `[certificate.vcs]`

| Field | Required | Meaning |
| ----- | -------- | ------- |
| `repo` | yes | Repository the commit belongs to. |
| `commit` | yes | Full commit identifier. |
| `clean` | yes | `true` when no tracked file differed from `commit` at execution time. |
| `untracked` | yes | `true` when untracked files were present. |

`clean` and `untracked` are separate because they mean different things. A
modified tracked file means *the tests did not run against `commit`* — the claim
is unsound. Untracked files usually mean scratch work that did not affect the
run, but can mean a file the build picked up. Producers MUST report both
honestly; consumers decide what to do with each.

A producer MUST NOT issue `clean = true` when it did not check. If it cannot
determine cleanliness, it MUST NOT issue a certificate at all — a guess here
invalidates everything downstream.

### 3.3 `[[certificate.command]]`

One entry per command executed, in execution order.

```toml
[[certificate.command]]
argv = ["ct", "test", "--selector", "tests/test_calc.py::test_add"]
```

`argv` is the argument vector as executed, unshelled. Producers MUST record what
was actually run, not a normalised or idealised form.

Commands make the claim **concrete**: a certificate says not merely "tests
passed" but "*these commands* ran and passed". A reader can see what was
attested without trusting a summary of it.

Producers SHOULD redact values that would leak secrets, replacing the value with
`"[redacted]"` rather than removing the argument, so the shape of the command
survives.

## 4. Frameworks recognise their own certificates

A repository may be tested by several frameworks — a Nim suite under one runner,
a Python suite under another, an integration suite under a build system. Their
certificates coexist, and none of them can evaluate the others.

Therefore:

- A consumer MUST filter by `framework` before applying any framework-specific
  rule. Applying one framework's validity logic to another's certificate is
  always wrong, even when the record parses.
- A consumer MUST ignore certificates whose `framework` it does not recognise,
  rather than rejecting them. An unrecognised framework's certificate is not
  evidence *for* this consumer, and is not evidence *against* anything either.
- Two frameworks MUST NOT claim the same `framework` identifier. Identifiers are
  matched by exact string equality.

The generic parts of verification — signature, key trust, VCS match, coverage
union — are framework-independent and defined in
[Verification](./Verification.md). Everything past that is the framework's own.

## 5. Enforcement is project-specific

A consequence worth stating plainly, because it is the most common way an
adopter gets the architecture wrong:

> **There is no generic pre-receive hook, and this standard does not define
> one.**

A push gate has to decide *"is this commit adequately tested?"*, and that
question is only answerable per project:

- which frameworks must have certified, and which are advisory
- which targets each framework must cover
- which platforms each must cover
- what each framework's own lock file must say at that commit

A project using two frameworks needs both verifiers, composed according to its
own policy. A generic hook could only check the parts in §6 and §3 — signature
and VCS match — which is necessary but nowhere near sufficient, and a hook that
passed on that basis would be actively misleading.

What the standard makes possible is that each framework ships a verifier for its
own certificates, and a project composes them. What it does not do is pretend
the composition is universal.

## 6. Signatures

A signature is **OPTIONAL in the format and MAY be required by a consumer**.
This is the standard's whole position on trust: it defines how to sign and how
to check a signature, and leaves to each project the decision of whether an
unsigned certificate is worth anything.

- An unsigned certificate is well-formed. It carries no protection against
  forgery and MUST NOT be treated as if it did.
- A signed certificate carries a detached signature over the canonical payload
  ([Canonical-Payload](./Canonical-Payload.md)), excluding the signature block.
- Consumers that require signatures MUST reject unsigned certificates outright
  rather than accepting them at reduced confidence. "Signed or not" is decidable
  and MUST be decided.

### 6.1 The signing primitive

Conforming implementations MUST use **OpenSSH ed25519 detached signatures**
(`ssh-keygen -Y sign` / `ssh-keygen -Y verify`) under a **namespace** that
domain-separates test certificates from every other use of the same key
material. The namespace for this schema version is:

```
test-certificate-v1
```

Domain separation is not optional. Without it, a signature obtained for another
purpose can be replayed as a certificate signature over identical bytes.

`algorithm` MUST be `ed25519`; `value` MUST be base64 of the detached signature
blob.

### 6.2 Issuance integrity

The one rule about *issuance* the standard states, because it determines what a
signature is worth rather than being local policy:

> A conforming producer MUST make a signature obtainable **only** as a
> consequence of having actually executed the attested commands. It MUST NOT
> expose any interface that signs a caller-supplied record.

A "sign this blob" entry point makes every certificate from that producer
worthless, because it lets any caller mint a claim about a run that never
happened. A producer offering one is not conforming, whatever else it does
correctly.

How *much* that guarantee is worth is a deployment property (see the README): it
depends on whether the tested code can reach the signing key. The rule above is
what makes it meaningful at all, at any strength.

## 7. Conformance

A **conforming producer**:

- emits records satisfying §3, with honest `vcs` state (§3.2) and the commands
  it actually ran (§3.3)
- claims only targets and platforms it actually ran (§8)
- uses a `framework` identifier that is its own (§4)
- if it signs, uses the primitive and namespace in §6.1 over the canonical
  payload, and satisfies §6.2

A **conforming verifier**:

- rejects records with unknown `schema` or missing required fields
- filters by `framework` and ignores unrecognised ones rather than failing (§4)
- checks the VCS binding (§3.2) and evaluates coverage as a union
  ([Verification](./Verification.md))
- when signatures are required, verifies them per §6.1 and rejects unsigned
  records rather than downgrading them
- does not present itself as a general answer to "is this commit tested?" (§5)

## 8. Partial coverage is normal

A certificate covers exactly the targets that ran, on the platform that ran them.
Producers MUST NOT claim targets that did not run, or a platform they did not run
on.

Full coverage is therefore frequently expressed as **several certificates** —
per platform, per framework, or per partial run — evaluated as a union
([Verification §5](./Verification.md#5-coverage-is-a-union)). This is the normal
case, not a degraded one.
