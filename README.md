# Test Certificates

A vendor-neutral standard for **test certificates**: small, checkable records
asserting that a named framework ran specific commands, covering specific test
targets, against a specific content of a repository's version-controlled files,
on a specific platform, and that they passed.

A certificate answers one question — *"were the required tests green for exactly
this state?"* — in a form another party can verify without rerunning them.

## Why a standard

Test certificates are useful precisely to the extent that unrelated tools agree
on them. A build system that issues one, a test runner that issues another, a
CI system that decides what to skip, a push gate that decides what to accept, and
a debugger that displays what is currently certified all have to read the same
record and reach the same conclusion about it. That agreement has to be written
down somewhere neutral, or every consumer ends up bound to one producer.

This repository is that neutral definition. It specifies the record, the exact
bytes a signature covers, how verification works, and how certificates travel.
It deliberately does **not** specify who may issue one, when, or what anybody
should do about it — those are policy, and policy belongs to the adopting
project.

It also ships the specification's executable half. `vectors/` holds byte-exact
canonical payloads, real signatures that must verify and must fail, and
verification decisions with their expected outcomes — plain data, no runner, so
an implementation in any language can walk it. Conformance is something an
implementation demonstrates, not something its author concludes from having read
the document carefully.

## Documents

| Document | Contents |
| -------- | -------- |
| [Standard.md](./Standard.md) | The record format, the fields, and conformance requirements |
| [Content-Id.md](./Content-Id.md) | How the tested content is identified: self-describing, order-independent content ids |
| [Canonical-Payload.md](./Canonical-Payload.md) | The exact byte serialization a signature covers |
| [Verification.md](./Verification.md) | Validity, signature checking, key stores, coverage |
| [Transport.md](./Transport.md) | Carrying certificates alongside the content they attest |
| [Conformance.md](./Conformance.md) | What the conformance suite contains, and why |
| [vectors/](./vectors/README.md) | The suite itself — byte-exact vectors, plain data, no runner |

## What is in scope, and what is not

**In scope** — the interoperability surface:

- The certificate record and its fields
- Canonical serialization (byte-exact, so independent implementations agree)
- Signing and signature verification
- Registered-key stores, rotation and revocation
- Content identifiers for the tested state
- The generic validity check: content binding, platform, and coverage as a union
- Transport alongside the content it attests

**Out of scope** — decided by each framework, or by each project:

- *Who* may issue a certificate, and under what preconditions
- What a framework additionally requires of its own lock file or config
- **How several frameworks compose into a gate**, at commit or at push time.
  There is no generic pre-commit or pre-receive hook and this standard does not
  define one (see below)
- Whether a signature is required, and whose keys are trusted
- What consumers do with a valid certificate — gate a push, skip CI work,
  display a status, or merely record it
- How keys are protected

The split is deliberate. The parts above the line have to be identical
everywhere or certificates do not interoperate. The parts below the line are
exactly where projects legitimately differ, and forcing agreement there would
prevent adoption rather than enable it.

## The content is the binding

Every framework's inputs are files under version control — its configuration,
its target definitions, and its lock file. A certificate identifying the content
of those files has therefore, transitively, bound every version-controlled
input, without the standard needing to know what those inputs are.

That is why there is no environment digest or lock hash in the format. A
framework wanting a deeper check resolves **its own lock file in that content**
and applies whatever rules it likes. The standard says *which content*; the
framework says *what that means for me*.

It binds **content, not a commit**. Content is identified by a self-describing
hash — git's own tree id where the VCS has one, or an order-independent manifest
digest this standard defines — so a certificate is valid **before** the commit
is made, and covers whichever commit later records that content, whatever its
message, author or parents. Tests run on the working tree, the certificate is
issued, and the commit follows; nothing is re-run. And because the content of a
commit-to-be is known before it exists, a project can require a certificate at
commit time — a pre-commit gate — as well as at push time.

The corollary matters as much: anything **not** under version control is not
bound by a certificate. A framework depending on such state must refuse to issue
while it is unclean, because no verifier can reconstruct it afterwards.

## Frameworks own their verdicts; projects own the gate

A repository may be tested by several frameworks, and their certificates
coexist. Each names its `framework`; consumers filter on that first, and ignore
what they do not implement rather than rejecting it.

It follows that **a gate is project-specific**, at commit time or at push time.
Deciding "is this commit adequately tested?" means deciding which frameworks
must have certified, which targets and platforms each must cover, and what each
framework's own lock file must say — none of it universal. Each framework ships
a verifier for its own certificates; a project composes them under its own
policy. A generic hook could check only the signature and the content match,
which is necessary but nowhere near sufficient, and passing on that basis would
be actively misleading.

## Assurance is a deployment property, not a format field

The standard defines what a certificate *says* and how to check that it was
signed by a particular key. It does not define, and cannot define, how much that
should be believed.

A certificate signed by a key that the tested process can read is worth less than
one signed by a key it cannot — but both are structurally identical, and no
field could honestly distinguish them, because a producer that would misuse the
key would also misdeclare the field. Assurance therefore comes from **who holds
the signing key and how well it is protected**, which is a property of a
deployment, and it is expressed through **which keys a verifier has registered**.

A project wanting strong assurance requires signatures and registers only keys
held by a component the tested code cannot reach — a privileged service, a
separate account, a remote signer. A project wanting convenience registers a key
the runner holds directly. The record does not change; the trust does.

## Status

Extracted from reprobuild's test-certificate design, whose implementation is
the first conforming producer. The vendor-neutral core is
defined here; reprobuild's issuance preconditions, push gate, CI fast-tracking
and per-project policy remain in that project's own specifications.
