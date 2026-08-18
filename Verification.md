# Verification

How a consumer decides whether a certificate, or a set of certificates, supports
the claim it wants to rely on.

## 1. The two questions

Verification answers two independent questions, and conflating them is the most
common way to get this wrong:

1. **Is this certificate authentic?** — was it signed by a key this consumer
   trusts? (§2)
2. **Does it cover what I care about?** — does it describe the state in front of
   me, for the targets and platforms I require? (§3, §4)

A certificate can be perfectly authentic and cover nothing relevant. It can also
cover exactly the right thing and be unsigned or signed by an unknown key. Both
questions MUST be answered; neither implies the other.

## 2. Authenticity

### 2.1 Key stores

A consumer that requires signatures resolves `key_id` against a **registered-key
store**:

```toml
schema = "registered-keys.v1"

[[key]]
key_id     = "repro-sign-2026-q2"
public_key = "ssh-ed25519 AAAA…"
status     = "active"          # active | revoked

[[key]]
key_id     = "repro-sign-2026-q1"
public_key = "ssh-ed25519 AAAA…"
status     = "revoked"
```

Rules:

- A certificate is authentic when `key_id` resolves to a key with
  `status = "active"` **and** the signature verifies over the canonical payload
  under the namespace in [Standard §5.1](./Standard.md#51-the-signing-primitive).
- **Revocation is a status flip, never a deletion.** A revoked key stays in the
  store. Certificates it signed are rejected even though their signatures remain
  cryptographically valid, and the audit trail survives — removing the entry
  would make old certificates merely unrecognised rather than *known bad*.
- **Rotation is additive**: register the new key alongside the old, then revoke
  the old once nothing depends on it.
- **An empty or missing store is fail-closed.** No registered signers means every
  signed certificate is rejected. It MUST NOT be interpreted as "no restrictions".

### 2.2 What authenticity does not tell you

The signature proves the payload was signed by the holder of a registered key.
It says nothing about whether the tests really ran, beyond the conformance rule
that a producer must not offer a "sign this blob" interface
([Standard §5.2](./Standard.md#52-issuance-integrity)).

How much that is worth depends on whether the tested code could reach the
signing key — a property of the deployment, expressed through **which keys the
consumer chose to register**. A consumer that registers a key held by the test
runner itself has decided to accept self-attestation; a consumer that registers
only keys held by a component the tested code cannot reach has decided not to.
Neither decision is visible in the certificate, and neither should be inferred
from it.

## 3. Validity against a state

A certificate is **valid for a state** when every binding field matches:

| Field | Match rule |
| ----- | ---------- |
| `commit` | Exact equality with the commit under evaluation |
| `platform` | Exact equality with the platform being satisfied |
| `targets` | Each required target is present (see §4) |
| `environment` | Comparable method, and equal under that method's rule |

`result` MUST be `passed`. A certificate recording any other result never
supports a positive claim, whatever else matches.

### 3.1 Environment comparison

- Bindings with **different methods are incomparable**. The certificate is
  *unverifiable* in this consumer's terms, not invalid, and the consumer MUST
  report it as such rather than as a failure of the certificate.
- `method = "none"` is incomparable to any bound method. A consumer requiring an
  environment binding MUST reject it; one not requiring a binding MAY accept it.
  It MUST NOT be treated as matching.
- A consumer that does not implement a method it encounters MUST NOT guess. An
  unimplemented method is unverifiable.

### 3.2 Time

`issued_at` is informational. Consumers MAY apply a freshness policy (for
example, ignoring certificates older than some age), but MUST NOT rely on
`issued_at` for correctness: the binding fields already pin the state, and a
correctly-bound certificate does not become wrong by ageing.

Consumers MUST NOT reject a certificate solely because `issued_at` is in the
future — clock skew is ordinary, and the timestamp is not a trust input.

## 4. Coverage is a union

Required coverage is normally satisfied by **several certificates together**, not
by one:

```
required: targets {unit, integration} on platforms {linux/amd64, macos/arm64}

cert A: {unit, integration} on linux/amd64   ✓
cert B: {unit}              on macos/arm64   ─┐ together satisfy macos/arm64
cert C: {integration}       on macos/arm64   ─┘

=> covered
```

The algorithm:

1. Discard certificates failing authenticity (§2) or whose `commit`/`environment`
   do not match the state (§3).
2. For each required platform, union the `targets` of the surviving certificates
   for that platform.
3. Coverage holds when every required target appears in that union, for every
   required platform.

Rules:

- Certificates for **other** platforms MUST NOT contribute to a platform's union.
  This is the mistake worth guarding: a green Linux run does not say anything
  about macOS.
- A consumer MUST report *what is missing* — which target on which platform —
  rather than a bare pass/fail. The remedy depends entirely on the gap.
- Duplicate coverage is not an error.

## 5. Reporting

A verifier's outcome is three-valued, and collapsing it to two loses the case
that matters most:

| Outcome | Meaning |
| ------- | ------- |
| **Covered** | Authentic certificates cover every requirement |
| **Not covered** | Requirements are unmet; the report names the gaps |
| **Unverifiable** | Something could not be evaluated — an unknown environment method, an unimplemented schema version, an unreadable key store |

**Unverifiable MUST NOT be reported as not-covered.** They call for different
responses: not-covered means *run the tests*, while unverifiable means *this
consumer cannot judge* — often a configuration or version problem, where
re-running tests changes nothing.

A consumer MAY treat unverifiable as failure for gating purposes, provided it
still *reports* it distinctly.
