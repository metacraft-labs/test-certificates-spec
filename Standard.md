# The Test Certificate Standard

> **Status:** Draft v1. Extracted from reprobuild's test-certificate design, made
> vendor-neutral so that any test runner or build system can issue certificates
> and any consumer can verify them.
>
> **Revised 2026-10-09:** the binding moved from a commit to the content of the
> tracked files (§2.1, [Content-Id](./Content-Id.md)). `commit`, `clean` and
> `worktree` are gone; `content` is required and `base` is optional. The schema
> id is unchanged because v1 is still a draft. Records issued under the earlier
> draft lack `content`, are therefore invalid under this revision, and are
> re-issued by re-running the tests
> ([Canonical-Payload §7](./Canonical-Payload.md#7-revisions-and-known-divergences)).

The key words MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are to be interpreted
as in RFC 2119.

## 1. What a certificate asserts

> *On platform `P`, framework `F` executed commands `C` covering targets `T`,
> which produced result `R`, in repository `repo` whose version-controlled files
> had content `V`.*

A certificate is a claim about a **specific, identified state**, made by a
**named framework**, about **commands it actually ran**.

The standard deliberately stops there. It does not describe dependency
closures, toolchain versions, container images or environment variables —
because it cannot describe them for every ecosystem, and a field it cannot
define precisely is worse than no field at all.

## 2. Why content is the whole binding

The one thing every framework shares is that its inputs are **files under
version control**. A test framework's configuration, its target definitions,
and — critically — **its lock file** are all tracked by the VCS.

So the content of those files *already binds* them. A certificate that
identifies the content of the tracked files has, transitively, bound every
version-controlled input the framework depends on, without the standard needing
to know what those inputs are or how to digest them.

This is why there is no environment digest, no lock hash, and no
method-tagged binding in this format. A framework that wants to check something
deeper resolves **its own lock file in that content** and checks it however it
likes ([Verification §4.2](./Verification.md#42-framework-specific-validity)).
The standard's job is to say *which content*; the framework's job is to say
*and here is what that means for me*.

### 2.1 Content, not commit

A commit is content plus metadata: a message, an author, timestamps, parents.
None of the metadata was tested, and none of it can make a test pass or fail.
Binding a certificate to the commit binds it to things the run never saw, and
it imposes an order — commit first, certify afterwards — that withholds the
certificate at the one moment it is most useful: when deciding whether the
work is fit to commit at all.

Binding to content removes both problems:

- **A certificate exists before the commit.** A developer, or an agent, tests
  the working tree and holds a valid certificate for it; committing that
  content needs no second run.
- **It covers every commit with that content.** Rewording a message, amending
  an author or re-parenting a commit leaves the content — and therefore the
  coverage — unchanged. A rebase or cherry-pick onto a different base changes
  the content, and correctly loses it.
- **Commits can be gated.** The content a commit is about to record is
  computable before the commit exists, so a project can require a certificate
  at commit time, not only at push time (§5.1).

How content is identified — a self-describing hash, using the VCS's own content
id where it has one — is defined in [Content-Id.md](./Content-Id.md).

The corollary matters just as much: **anything not under version control is not
bound by a certificate.** Untracked files, ambient tool versions, network
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
content    = "git-tree-sha1:9f8e7d6c…"     # the tested content of tracked files
untracked  = false                         # no untracked files present
base       = "a858633c…"                   # OPTIONAL: HEAD at issuance, informational

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
| `vcs` | yes | The repository content the tests ran against (§3.2). |
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
| `repo` | yes | Repository the content belongs to. |
| `paths` | no | Repo-relative paths the claim is **scoped to**. Absent or empty means the whole repository (§3.2.1). |
| `content` | yes | Self-describing id of the tracked files within scope, as they were when the commands executed ([Content-Id](./Content-Id.md)). |
| `untracked` | yes | `true` when untracked files were present within scope. |
| `base` | no | The commit checked out when the certificate was issued. Informational only (§3.2.3). |

`content` identifies exactly what was tested: every tracked file with its
working-tree content, newly added files included and deleted ones absent. There
is no separate notion of a "clean" or "dirty" certificate. A certificate never
claims to be about a commit, so modifications relative to one are not a special
case — they are simply part of the content.

`untracked` is reported because untracked files are **not** part of `content`.
They usually mean scratch work that did not affect the run, but can mean a file
the build picked up — in which case committing the tracked content alone may
not reproduce the result. Producers MUST report it honestly, and a producer that
knows its tests consumed an untracked file MUST NOT issue at all: `content` does
not bind that file, so nothing could verify it (§2.1).

Producers:

- MUST compute `content` from the state the commands **actually executed
  against**, as [Content-Id §2](./Content-Id.md#2-what-is-identified) defines
  it. A content id captured before or after the run, with edits in between,
  attests to something that was never tested.
- MUST therefore compute it both **before and after** the run, and MUST NOT
  issue when the two differ. An edit that lands during the run — an editor
  saving, a generator rewriting a tracked file — leaves no single tested state.
- MUST NOT issue when the state has no content id
  ([Content-Id §3](./Content-Id.md#3-when-there-is-no-content-id)), or when
  they did not check for untracked files. A guess here invalidates everything
  downstream.

#### 3.2.1 Scoping the claim to paths

Attesting the *whole* repository is often stricter than the claim needs to be,
and in a monorepo or multi-project workspace it is stricter than is useful: a
developer editing one component would produce a certificate for another that no
commit will ever match, because the unrelated work in progress is part of the
content.

`paths` narrows the claim to the part of the tree the tests depend on:

```toml
[certificate.vcs]
repo      = "codetracer"
paths     = ["Cargo.lock", "src/db-backend"]
content   = "git-tree-sha1:3c1f…"   # within `paths`
untracked = false                   # within `paths`
```

Such a certificate says nothing whatever about the rest of the repository, and
says so explicitly. That is the point: an honest narrow claim rather than a
dishonest broad one.

Rules:

- `content` and `untracked` are always **relative to `paths`**: the content id
  covers exactly the in-scope tracked files
  ([Content-Id §4](./Content-Id.md#4-algorithms)).
- A path naming a directory scopes the subtree beneath it; a path naming a file
  scopes that file.
- Paths are repo-relative, use `/` separators, never begin with `./` or end with
  `/`, and are sorted and deduplicated in canonical form.
- **A producer MUST NOT declare a scope narrower than the inputs it knows the
  tests read.** This is the rule the feature rests on: a scope excluding a file
  the tests actually consumed yields a certificate that is formally valid and
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

#### 3.2.2 Certifying before the commit

The intended workflow is: **test, then commit.**

1. Edit the working tree.
2. Run the tests. A passing run issues a certificate whose `content` identifies
   the tracked files as they were, and publishes it to the local certificate
   store ([Transport §2](./Transport.md#2-the-local-certificate-store-required)),
   outside the working tree.
3. Commit. When the commit records exactly the content that was tested, its
   tree has that content id, and the certificate covers it — no second run.

The certificate covers the commit only when the commit records **what was
tested**, and several ordinary actions break that. Each is a correct outcome,
not a defect, because in each the commit is not what ran:

- **Partial staging.** Committing some of the tested changes (`git add -p`)
  records content that was never tested as a whole.
- **Forgotten files.** A new file the tests used but that was never added stays
  untracked; it was outside `content`, and the commit lacks it.
- **Rewriting at commit time.** A hook that changes tracked content while the
  commit is being formed — a formatter, a lock-file refresh — produces content
  the tests never saw.

The remedy is ordering, not a looser match. Steps that rewrite tracked files
belong **before** the test run — inside the test command, or run and followed
by a re-test — so the content tested is the content committed. A framework with
content-based incremental testing makes that re-test nearly free: unchanged
inputs re-run nothing.

#### 3.2.3 `base`

`base` names the commit checked out (`HEAD`) when the certificate was issued. It
exists for people and tools — "tested on top of `a858633c`" says where the work
started, and helps find a certificate's origin — and for nothing else.

It is **not evidence**. A verifier MUST NOT require it, MUST NOT match on it, and
MUST NOT reject a certificate because `base` differs from the commit under
evaluation: a certificate issued on top of one commit routinely covers the next
one, which is the whole point of §2.1. A producer MAY omit it, and MUST omit it
rather than emit an empty value when there is no commit to name — the first
commit of a repository is certified on top of nothing.

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

> **There is no generic pre-receive or pre-commit hook, and this standard does
> not define one.**

A gate has to decide *"is this commit adequately tested?"*, and that question is
only answerable per project:

- which frameworks must have certified, and which are advisory
- which targets each framework must cover
- which platforms each must cover
- what each framework's own lock file must say in that content

A project using two frameworks needs both verifiers, composed according to its
own policy. A generic hook could only check the parts in §6 and §3 — signature
and content match — which is necessary but nowhere near sufficient, and a hook
that passed on that basis would be actively misleading.

What the standard makes possible is that each framework ships a verifier for its
own certificates, and a project composes them. What it does not do is pretend
the composition is universal.

### 5.1 Gating at commit time

Because a certificate is bound to content (§2.1), the question can be asked
**before a commit exists**. The content a commit is about to record is the index
being committed, and its content id is computable in a pre-commit hook
([Content-Id §5](./Content-Id.md#5-computing-the-id-of-the-state-under-evaluation)).
A project MAY therefore compose its verifiers into a **pre-commit gate**, in
addition to the push-time or pre-receive gate, and refuse a commit whose content
no certificate covers. The gate finds candidates in the local certificate store
([Transport §2](./Transport.md#2-the-local-certificate-store-required)), which
every conforming producer populates, so it needs no knowledge of which producer
issued them or how to ask it.

The two gates are not interchangeable:

- **A pre-commit gate is the early answer, not the enforcement point.** It runs
  on the committer's machine, and `git commit --no-verify` skips it. Its value is
  that the refusal arrives while the work is still in hand, rather than at push
  time against a commit already made. The gate that enforces policy is still the
  one on the receiving side.
- **A pre-commit gate MUST evaluate the content actually being committed**, and
  so MUST run after every step of the commit that changes the index. A hook that
  stages a rewritten file after the gate has checked produces a commit the gate
  never saw — and one whose content no certificate covers, since the tests never
  saw it either (§3.2.2).

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
> consequence of the attested commands having actually executed. It MUST NOT
> expose any interface that signs a caller-supplied record.

A "sign this blob" entry point makes every certificate from that producer
worthless, because it lets any caller mint a claim about a run that never
happened. A producer offering one is not conforming, whatever else it does
correctly.

How *much* that guarantee is worth is a deployment property (see the README): it
depends on whether the tested code can reach the signing key. The rule above is
what makes it meaningful at all, at any strength.

#### 6.2.1 Reusing a recorded execution

A framework with content-based incremental testing does not re-run a command
whose inputs have not changed (§3.2.2). It reuses a record of the earlier
execution instead. That record satisfies §6.2: the command did execute, over
the same inputs. A producer MAY therefore attest a command whose result it
reused, provided all of the following hold:

- **The record covers the inputs.** It was produced by an execution whose
  inputs, as the framework observed them, are byte-identical to the inputs the
  command would read in the content being certified. Re-using a result after an
  input changed attests a run that never happened.
- **The record came from an execution the producer trusts.** That means one the
  producer itself observed, or one whose record is signed by a key the
  producer's project has registered for that purpose. The trust decision is the
  project's, like the trust in certificate keys (Verification §3). A record
  from an unauthenticated shared cache is a caller-supplied claim, and §6.2
  forbids signing it.
- **The record reports success.** A reused failure is a failure.

The certificate's `[[certificate.command]]` entries still list the commands
the claim rests on, reused or not. A reused command is not marked differently.
The certificate attests that the commands passed over this content, not when
or where they ran. Where provenance matters, it belongs in the trust the
consumer places in the producer's key, not in the record.

## 7. Conformance

A **conforming producer**:

- emits records satisfying §3, with honest `vcs` state (§3.2) and the commands
  it actually ran (§3.3)
- computes `content` as [Content-Id](./Content-Id.md) defines it, from the state
  it executed against, and refuses where that document says no content id exists
- delivers every certificate it issues to the local certificate store of the
  user on whose behalf the tests ran, never writing into another account's
  directories or into a working tree
  ([Transport §2.3](./Transport.md#23-writing))
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
- checks the content binding (§3.2) by computing the certificate's content-id
  algorithm over the state under evaluation, never by comparing `base`, and
  evaluates coverage as a union ([Verification](./Verification.md))
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
