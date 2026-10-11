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

This ordering is deliberate. Checking a signature or a content match on a
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
- **An unreadable store is a different failure.** Empty and missing stores
  *answer* the question — nobody is trusted — so the certificates they deny are
  **not covered** (§7). A store that cannot be read or parsed answers nothing,
  and the outcome is **unverifiable**. Collapsing the two sends an operator to
  re-run tests when the actual fault is a corrupt configuration file.

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
| `vcs.content` | Equal to the content id of the state under evaluation, computed with the certificate's algorithm over the certificate's scope (§4.1.1) |
| `vcs.paths` | When present, the claim covers only those paths. A consumer requiring broader coverage MUST reject it (§4.1.2). |
| `vcs.untracked` | Consumer's choice. Untracked files are outside `content`; they usually mean scratch work, but can mean a file the build picked up. |
| `vcs.repo`, `project` | Consumer's choice. A consumer MAY require them to equal its own names for the repository and project; the content binding does not depend on them, so a certificate for identical content issued under another name — a fork, a renamed clone — matches by content alone. |
| `vcs.base` | **Not checked.** It MUST NOT be compared with the commit under evaluation (§4.1.1). |
| `platform` | Exact equality with the platform being satisfied |
| `result` | MUST be `passed` |

#### 4.1.1 Matching content

A certificate describes **content**, not a commit, so a consumer matches it by
comparing content ids:

1. Take the algorithm from the certificate's `content`
   ([Content-Id §1](./Content-Id.md#1-form)).
2. Compute that algorithm, over the certificate's `paths`, for the state under
   evaluation — a commit's tree, the index a pre-commit gate is about to
   commit, or a working tree
   ([Content-Id §5](./Content-Id.md#5-computing-the-id-of-the-state-under-evaluation)).
3. The certificate matches when the two ids are equal.

The match holds across everything that is not content. A certificate issued on
top of commit `cc11…`, against a working tree later committed as `a858…` with
its own message, author and parents, covers `a858…` — and so does any later
commit that records the same content. Comparing `base`, or any commit id, to the
state under evaluation is therefore always wrong: it rejects exactly the
certificates this design exists to make valid.

Three outcomes besides a match:

- **The ids differ.** The certificate does not describe this state. It is
  discarded, like a certificate for another platform: it is not evidence here,
  and it is not evidence against anything.
- **The content id is malformed** — no `:`, a digest that is not lowercase
  hex, a digest of the wrong length for an algorithm Content-Id §4 defines; the
  full rule, including where the algorithm ends, is in
  [Content-Id §1](./Content-Id.md#1-form). The record is **decidably invalid**
  and is rejected, without repair.
- **The consumer cannot compute the algorithm** for this state — an algorithm it
  does not implement, an algorithm Content-Id §4 does not define, or
  `git-tree-sha256` against a repository in the SHA-1 object format. It has not established a mismatch, so the certificate is
  **unverifiable** (§7), not invalid, and §7.1 decides whether that affects the
  outcome. A consumer meets such a record only through a carrier it
  reads in full. Lookups keyed by content id never return one
  ([Transport §5.1](./Transport.md#51-lookup-is-by-the-consumers-own-content-id)).

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
file — or config, or target definitions — in the content under evaluation**,
since those are under version control and therefore bound by `vcs.content`, and
applies whatever rules it likes. It might check that its lock is internally consistent, that
declared dependencies resolve, that the target set in the certificate matches
the targets the config defines in that content, or nothing at all.

Consumers MUST NOT invent a generic substitute for this step. There is no
portable notion of "the environment matched"; there is only "this framework says
its own inputs in this content are consistent with this certificate".

What the standard guarantees is the precondition that makes the step possible:
once `vcs.content` matches, the framework's version-controlled inputs are
exactly recoverable from the state in front of it — the commit's tree, or the
index being committed — whether or not the certificate's own `base` still
exists.

### 4.3 Time

`issued_at` is informational. Consumers MAY apply a freshness policy, but MUST
NOT rely on it for correctness: the content binding already pins the state, and a
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
2. Discard those failing authenticity (§3) or the content/platform match (§4).
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

Nor is a record that is decidably invalid. A malformed content id, a missing
required field, a revoked key, a scope narrower than the requirement: in each of
those the consumer asked the question and got an answer. Unverifiable is for the
cases where it could not ask — an unreadable key store, a schema version it does
not implement, a content id in an algorithm it cannot compute.

### 7.1 Precedence

A single evaluation can produce several of these at once, so the order is fixed:

1. **Covered** wins when every requirement is met by certificates that were
   evaluated end to end. The unevaluated records MUST still be named in the
   report.
2. Otherwise **unverifiable**, if any record that could not be evaluated is
   **potentially relevant** in the sense defined below. "Run the tests" would be
   the wrong instruction while an unread certificate might already cover the
   gap.
3. Otherwise **not covered**, naming the gaps (§5).

#### Why rule 1 is safe: coverage is monotonic

Rule 1 rests on an invariant worth stating explicitly, because a future schema
version could break it: **in v1, coverage only ever grows.** Every certificate
either adds targets to a platform's union (§5) or contributes nothing. None can
subtract: a record that is not evidence — wrong platform, revoked key, `result`
other than `passed` — is discarded, never counted *against* anything, and this
format defines no record that revokes or contradicts another.

So a record the consumer could not read could only ever have *added* coverage.
Reporting unverifiable once the requirement is already met would send an
operator to fix a configuration problem in order to reach a conclusion that has
already been reached. A schema version introducing a negative claim — a
withdrawal, a contradiction, a failing result that vetoes a passing one — would
invalidate this reasoning and would need a different rule.

#### Potential relevance is only assessable for a record you can interpret

The two ways evaluation breaks down are not alike, and the difference decides
rule 2:

- **A record the consumer cannot interpret** — an unimplemented `schema`
  version — MUST be treated as potentially relevant, whatever its fields appear
  to say. Reading `platform` or `targets` out of a v2 record with a v1 parser
  and concluding the record was irrelevant means trusting an interpretation the
  consumer has just admitted it does not have. A later version may redefine what
  those fields mean, or add a field that widens what the record covers.
  **Relevance is itself a schema-dependent judgement**, so for an
  uninterpretable record it is undecidable, and MUST be assumed.

- **A record the consumer can interpret but could not verify** — one denied an
  answer by an unreadable key store (§3.1), or carrying a content id in an
  algorithm it cannot compute (§4.1.1) — is potentially relevant **only if its
  interpreted scope could satisfy some part of the requirement**. Its fields are
  readable, in a schema this consumer implements, so a certificate for a
  platform that is not required, or naming no required target, could not have
  changed the answer whatever its signature would have said. Such a record MUST
  still be named in the report, but it MUST NOT on its own make the outcome
  unverifiable.

The distinction is between *"I could not tell whether this mattered"* and *"I
could tell that it did not."* Collapsing it in either direction is a defect.
Treating every unevaluable record as decisive reports unverifiable — and sends
an operator after a configuration fault — for something that could not have
affected the verdict. Treating an uninterpretable one as irrelevant silently
discards a certificate that might have covered the gap, which is the failure
this whole section exists to prevent.
