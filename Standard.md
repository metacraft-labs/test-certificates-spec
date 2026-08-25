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

The alignment above is for readability. It is **not** canonical form, which
puts exactly one space either side of `=`
([Canonical-Payload §2](./Canonical-Payload.md#2-structure)). A certificate may
be written either way and must verify either way, because a verifier
reconstructs the payload from the parsed fields rather than from the received
bytes ([Canonical-Payload §5](./Canonical-Payload.md#5-verifying-against-the-payload)).

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

A conforming producer MUST emit every required field, and MUST name at least one
target and at least one command — a certificate covering nothing, or recording
no command, asserts nothing.

A conforming verifier MUST reject a record missing any required field, and MUST
NOT treat a record with an unrecognised `schema` as evidence. The two are not
the same failure: see §7.

### 3.2 `[certificate.vcs]`

| Field | Required | Meaning |
| ----- | -------- | ------- |
| `repo` | yes | Repository the commit belongs to. |
| `commit` | yes | Commit the tested state is expressed relative to. |
| `clean` | yes | `true` when no tracked file differed from `commit` at execution time. |
| `untracked` | yes | `true` when untracked files were present. |
| `paths` | no | Repo-relative paths the claim is **scoped to**. Absent or empty means the whole repository (§3.2.1). |
| `worktree` | when `clean = false` | Identifies the exact modified state that was tested (§3.2.2). |

`clean` and `untracked` are separate because they mean different things. A
modified tracked file means the tests ran against something other than `commit`.
Untracked files usually mean scratch work that did not affect the run, but can
mean a file the build picked up. Producers MUST report both honestly.

A producer MUST NOT issue `clean = true` when it did not check. If it cannot
determine cleanliness, it MUST NOT issue a certificate at all — a guess here
invalidates everything downstream.

#### 3.2.1 Scoping the claim to paths

Requiring the *whole* repository to be clean is often stricter than the claim
needs to be, and in a monorepo or multi-project workspace it is stricter than is
achievable: a developer editing one component cannot certify another without
first stashing unrelated work, and untracked build output anywhere blocks
everything.

`paths` narrows the claim to the part of the tree the tests depend on:

```toml
[certificate.vcs]
repo      = "codetracer"
commit    = "a858633c…"
paths     = ["Cargo.lock", "src/db-backend"]
clean     = true      # within `paths`
untracked = false     # within `paths`
```

Such a certificate says nothing whatever about the rest of the repository, and
says so explicitly. That is the point: an honest narrow claim rather than a
dishonest broad one.

Rules:

- `clean`, `untracked` and `worktree` are always **relative to `paths`**.
- A path naming a directory scopes the subtree beneath it; a path naming a file
  scopes that file.
- Paths are repo-relative, use `/` separators, never begin with `./` or end with
  `/`, and are sorted and deduplicated in canonical form.
- **A producer MUST NOT declare a scope narrower than the inputs it knows the
  tests read.** This is the rule the feature rests on: a scope excluding a file
  the tests actually consumed yields a certificate that is formally clean and
  substantively false.
- **A producer that cannot bound its tests' input set MUST NOT use scoping** and
  MUST attest the whole repository instead. Scoping is for frameworks that know
  what their tests read — through dependency capture, trace-based discovery, or
  explicit declaration in their own config — and for no others.
- Consumers MUST treat absent or empty `paths` as a whole-repository claim.

The standard cannot verify that a scope is adequate; that is framework knowledge
by construction. What it does is make the scope **explicit and signed**, so an
inadequate scope is a stated claim that can be reviewed and disputed rather than
an unstated assumption.

#### 3.2.2 Testing a modified working tree

**A clean-tree certificate is the normal output, and producers SHOULD aim for
one.** The intended workflow is: run the tests, commit once they pass, then run
them again to certify.

That second run is not the tax it appears to be. Committing changes no file
content, so a framework with content-based incremental testing finds every one
of its per-test hashes unchanged and re-runs **nothing** — the second invocation
is a hash comparison, not a test run. Frameworks with that property (reprobuild
via `repro test`, CodeTracer via `ct test`) turn "commit, then certify" into a
near-free step rather than a second full suite.

Producers SHOULD therefore prefer the clean-tree form, and tooling SHOULD guide
users toward it, because it is the form every consumer can evaluate with a plain
commit comparison and no reconstruction.

The modified-worktree form below exists for the cases that remain: attesting
work that genuinely cannot be committed yet, a framework without incremental
testing where re-running is expensive, or an environment where the commit
happens elsewhere. It is a supported form, not the recommended default.

A certificate MAY express the tested state as **`commit` plus the modification
applied on top of it**:

```toml
[certificate.vcs]
repo      = "codetracer"
commit    = "a858633c…"     # the base
clean     = false           # the tree differed from that base
untracked = false

[certificate.vcs.worktree]
tree      = "9f8e7d6c…"     # canonical content id of what was actually tested
format    = "git-diff --no-renames -U3"   # how `patch_digest` was produced
patch_digest = "blake3:4a1b…"   # over the exact patch bytes
```

| Field | Required | Meaning |
| ----- | -------- | ------- |
| `tree` | when the VCS provides one | The VCS's canonical content identifier for the tested state **within scope** (in git, a tree object id). |
| `format` | when `patch_digest` is present | How the patch was produced, pinning the exact diff semantics. |
| `patch_digest` | no | `<algo>:<hex>` over the exact bytes of the patch from `commit` to the tested state. |

At least one of `tree` and `patch_digest` MUST be present.

**Prefer `tree`.** Where the VCS has a canonical content identifier — git's tree
object id does — it identifies the tested content exactly, is cheap to compute
(`git write-tree`), and is stable by construction. Verification becomes a single
comparison: the commit being evaluated has this tree, so its content *is* what
was tested, whatever its message, author or parents.

That last point is what makes the form usable at all. A developer tests a dirty
tree, commits it, and pushes: the resulting commit is not the one the
certificate names, but its tree is identical, so the certificate still covers
it — no re-run required, even for a framework that would otherwise have to
repeat the suite.

**`patch_digest` is the portable fallback**, for VCSs without a canonical
content id and for cases where a reviewer wants to see the change. It is
strictly more fragile: diff output is not canonical, and the same change can
serialize differently under different context, rename-detection or whitespace
settings. A producer using it MUST pin those semantics in `format`, and a
verifier MUST NOT compare digests across differing `format` values. This is
exactly the fragility `tree` avoids, which is why it is the fallback and not the
primary.

`format` is an **opaque identifier compared by exact string equality**. The
standard defines no vocabulary for it and parses no structure out of it, so a
producer MUST choose a value that pins *every* option affecting the patch bytes
— context lines, rename detection, whitespace handling, the tool and its
version if they matter. A bare `"git-diff"` is a poor value precisely because
two producers can both claim it and disagree on the bytes, and exact-equality
comparison would then match digests that were never comparable.

A certificate MAY additionally carry the patch itself out of band; the standard
does not embed it, because certificates travel in places (git notes) where an
arbitrarily large blob is a poor fit.

Rules:

- `worktree` is REQUIRED when `clean = false` and MUST be absent when
  `clean = true`. A dirty certificate without it identifies no state at all and
  MUST be rejected.
- Untracked files are part of the tested state when they are part of `tree`. A
  producer MUST NOT report `untracked = false` merely because it excluded them
  from `tree`; the two fields describe the tree, not the producer's intentions.
- A producer MUST compute `tree` / `patch_digest` from the state it actually
  executed against, not from the state at any other moment. A tree captured
  before or after the run, with edits in between, attests to something that was
  never tested.
- **Scoping and modification compose.** When `paths` is present, `tree` covers
  exactly the scope, and `patch_digest` is taken over a patch restricted to it.
  Where the VCS cannot express the scope as one canonical content id, a producer
  MUST use `patch_digest` rather than a whole-tree id, which would attest more
  than the scope and less than the truth.

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
blob — RFC 4648 §4 (the standard alphabet), padded, on a single line, with no
embedded whitespace and no armor. `ssh-keygen` writes the armored
`-----BEGIN SSH SIGNATURE-----` form; converting between the two is pure
framing, and the blob is what the field carries.

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

- accepts no record with an unknown `schema` or a missing required field as
  evidence — but distinguishes the two when reporting. A record missing a
  required v1 field is decidably invalid and contributes nothing; a record
  declaring a `schema` version this verifier does not implement may be a
  perfectly good certificate it cannot read, and is reported **unverifiable**
  ([Verification §7](./Verification.md#7-reporting))
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
