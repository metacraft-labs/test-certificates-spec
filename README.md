# Test Certificates

A vendor-neutral standard for **test certificates**: small, checkable records
asserting that a project's required tests passed against a specific commit, on
a specific platform, with a specific environment state.

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

## Documents

| Document | Contents |
| -------- | -------- |
| [Standard.md](./Standard.md) | The record format, the fields, and conformance requirements |
| [Canonical-Payload.md](./Canonical-Payload.md) | The exact byte serialization a signature covers |
| [Verification.md](./Verification.md) | Validity, signature checking, key stores, coverage |
| [Transport.md](./Transport.md) | Carrying certificates alongside commits |

## What is in scope, and what is not

**In scope** — the interoperability surface:

- The certificate record and its fields
- Canonical serialization (byte-exact, so independent implementations agree)
- Signing and signature verification
- Registered-key stores, rotation and revocation
- Validity and coverage evaluation
- Transport alongside a commit

**Out of scope** — every adopting project decides these for itself:

- *Who* may issue a certificate, and under what preconditions
- Whether issuance requires a clean working tree, a lock, a sandbox, or nothing
- Whether a signature is required, and whose keys are trusted
- What consumers do with a valid certificate — gate a push, skip CI work,
  display a status, or merely record it
- How keys are protected

The split is deliberate. The parts above the line have to be identical
everywhere or certificates do not interoperate. The parts below the line are
exactly where projects legitimately differ, and forcing agreement there would
prevent adoption rather than enable it.

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
