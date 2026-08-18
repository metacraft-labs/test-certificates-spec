# Verification

How a consumer decides whether a certificate, or a set of certificates, supports
the claim it wants to rely on.

## 1. Three questions, in order

Verification answers three questions. They are independent, and conflating them
is the most common way to get this wrong:

1. **Is this certificate mine to evaluate?** — does its `framework` match one I
   implement? (§2)
2. **Is it authentic?** — was it signed by a key I trust? (§3)
3. **Does it cover what I care about?** — does it describe the state in front of
   me, for the targets and platforms I require? (§4, §5)

A certificate can be perfectly authentic and cover nothing relevant. It can
cover exactly the right thing and be unsigned. It can be both and belong to a
framework this consumer knows nothing about. All three MUST be answered; none
implies another.

## 2. Framework filtering comes first

A repository may be tested by several frameworks, and their certificates
coexist. Before any framework-specific rule is applied, a consumer MUST filter
by the `framework` field.

- Certificates whose `framework` this consumer does not implement are
  **ignored** — not rejected. They are not evidence for this consumer, and they
  are not evidence against anything either.
- A consumer MUST NOT apply its own validity rules to another framework's
  certificate, even when the record parses cleanly. The fields are shared; their
  framework-specific meaning is not.

This ordering is deliberate. Checking a signature or a VCS match on a
certificate you were never going to evaluate wastes work and, worse, produces
verdicts about certificates you do not understand.

## 3. Authenticity

### 3.1 Key stores

A consumer that requires signatures resolves `key_id` against a **registered-key
store**:

```toml
schema = "registered-keys.v1"

[[key]]
key_id     = "repro-sign-2026-q2"
public_key = "ssh-ed25519 AAAA…"
status     = "active"          # active | revoked
```

Rules:

- A certificate is authentic when `key_id` resolves to a key with
  `status = "active"` **and** the signature verifies over the canonical payload
  under the namespace in [Standard §6.1](./Standard.md#61-the-signing-primitive).
- **Revocation is a status flip, never a deletion.** A revoked key stays in the
  store; certificates it signed are rejected even though their signatures remain
  cryptographically valid, and the audit trail survives. Removing the entry would
  make old certificates merely *unrecognised* rather than *known bad*.
- **Rotation is additive**: register the new key alongside the old, then revoke
  the old once nothing depends on it.
- **An empty or missing store is fail-closed.** No registered signers means every
  signed certificate is rejected. It MUST NOT be read as "no restrictions".

### 3.2 What authenticity does not tell you

The signature proves the payload was signed by the holder of a registered key.
It says nothing further about whether the tests really ran, beyond the
conformance rule that a producer must not offer a "sign this blob" interface
([Standard §6.2](./Standard.md#62-issuance-integrity)).

How much that is worth depends on whether the tested code could reach the
signing key — a property of the deployment, expressed through **which keys the
consumer registered**. A consumer registering a key held by the test runner
itself has accepted self-attestation; one registering only keys held by a
component the tested code cannot reach has not. Neither decision appears in the
certificate, and neither should be inferred from it.

## 4. Validity against a state

### 4.1 The generic check

Every consumer, whatever its framework, MUST check:

| Field | Rule |
| ----- | ---- |
| `vcs.commit` | Exact equality with the commit under evaluation, **or** the base of a `worktree` claim that matches (§4.1.1) |
| `vcs.clean` | When `true`, the tested state is `commit` itself. When `false`, `worktree` MUST identify it (§4.1.1). |
| `vcs.paths` | When present, the claim covers only those paths. A consumer requiring broader coverage MUST reject it (§4.1.2). |
| `vcs.untracked` | Consumer's choice. Untracked files usually mean scratch work, but can mean a file the build picked up. |
| `platform` | Exact equality with the platform being satisfied |
| `result` | MUST be `passed` |

#### 4.1.1 Matching a modified-worktree claim

A certificate with `clean = false` does not describe `commit`; it describes
`commit` plus the modification in `worktree`. A consumer matches it by comparing
**content**, not commit identity:

- With `tree`: the state under evaluation matches when its canonical content id
  for the scope equals `worktree.tree`. In git this is a tree-oid comparison, and
  it holds across commit metadata — so a certificate issued against a dirty tree
  still covers the commit that tree was later committed as.
- With `patch_digest` only: the consumer must be able to reproduce the patch from
  `commit` to the state under evaluation, under the certificate's `format`, and
  compare digests. A consumer that cannot reproduce that exact format MUST report
  the certificate **unverifiable** (§7), not invalid.

A `clean = false` certificate carrying no `worktree` identifies no state at all
and MUST be rejected outright.

#### 4.1.2 Scoped claims

A certificate with `vcs.paths` covers only those paths, and says nothing about
the rest of the tree. A consumer MUST check that the scope covers what it
requires — a scoped certificate is not a whole-repository certificate, and
treating it as one is the mistake this field exists to prevent.

Whether a given scope is *adequate* for a set of targets is framework knowledge
(§4.2), not something the standard can decide.

### 4.2 Framework-specific validity

Past the generic check, validity is the **framework's own question**, and the
standard defines none of it.

The pattern the standard is built around: a framework resolves **its own lock
file — or config, or target definitions — at `vcs.commit`**, since those are
under version control and therefore bound by the commit, and applies whatever
rules it likes. It might check that its lock is internally consistent, that
declared dependencies resolve, that the target set in the certificate matches
the targets the config defines at that commit, or nothing at all.

Consumers MUST NOT invent a generic substitute for this step. There is no
portable notion of "the environment matched"; there is only "this framework says
its own inputs at this commit are consistent with this certificate".

What the standard guarantees is the precondition that makes the step possible:
`vcs.commit` plus `vcs.clean` means the framework's committed inputs are exactly
recoverable.

### 4.3 Time

`issued_at` is informational. Consumers MAY apply a freshness policy, but MUST
NOT rely on it for correctness: the VCS binding already pins the state, and a
correctly-bound certificate does not become wrong by ageing.

Consumers MUST NOT reject a certificate solely because `issued_at` is in the
future — clock skew is ordinary, and the timestamp is not a trust input.

## 5. Coverage is a union

Required coverage is normally satisfied by **several certificates together**:

```
required: framework=ct-test, targets {unit, integration}
          on platforms {linux/amd64, macos/arm64}

cert A: {unit, integration} on linux/amd64   ✓
cert B: {unit}              on macos/arm64   ─┐ together satisfy macos/arm64
cert C: {integration}       on macos/arm64   ─┘

=> covered
```

The algorithm:

1. Filter to certificates whose `framework` this consumer implements (§2).
2. Discard those failing authenticity (§3) or the VCS/platform match (§4).
3. For each required platform, union the `targets` of the survivors **for that
   platform**.
4. Coverage holds when every required target appears in that union, for every
   required platform.

Rules:

- Certificates for **other platforms** MUST NOT contribute to a platform's union.
  A green Linux run says nothing about macOS.
- Certificates from **other frameworks** MUST NOT contribute. Two frameworks may
  use the same target name for different things.
- A consumer MUST report *what is missing* — which target, on which platform,
  for which framework — not a bare pass/fail. The remedy depends on the gap.
- Duplicate coverage is not an error.

## 6. Composing frameworks

A project using several frameworks composes several verifiers, one per
framework, according to its own policy ([Standard §5](./Standard.md#5-enforcement-is-project-specific)).

The composition is the **project's** to define:

- which frameworks are required and which advisory
- whether a missing framework is a failure or simply nothing to check
- how to report when one framework is covered and another is not

The standard does not define a composition rule, because there is no correct
one: a project may reasonably require all frameworks, any one, or a specific
subset per branch.

## 7. Reporting

A verifier's outcome is three-valued, and collapsing it to two loses the case
that matters most:

| Outcome | Meaning |
| ------- | ------- |
| **Covered** | Authentic certificates cover every requirement |
| **Not covered** | Requirements unmet; the report names the gaps |
| **Unverifiable** | Something could not be evaluated — an unreadable key store, an unimplemented schema version, a framework-specific check that could not run |

**Unverifiable MUST NOT be reported as not-covered.** They call for different
responses: not-covered means *run the tests*, unverifiable means *this consumer
cannot judge* — usually a configuration or version problem, where re-running
tests changes nothing.

A consumer MAY treat unverifiable as failure for gating purposes, provided it
still *reports* it distinctly.

Note that "no certificates from a framework I implement" is **not**
unverifiable — it is simply not covered. Unverifiable is reserved for cases
where evaluation itself broke down.
