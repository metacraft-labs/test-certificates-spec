# Conformance Vectors

> **Status:** ☑ Present. This document specifies the suite; the suite itself
> lives in [`vectors/`](./vectors/README.md), whose README is the directory
> contract a consumer in any language walks it by.

## Why this exists

[Canonical-Payload.md](./Canonical-Payload.md) is normative down to the byte,
because two implementations that disagree by one byte produce signatures neither
can verify while appearing to agree about everything else.

Prose cannot enforce that. Two implementations will be written — reprobuild's,
and CodeTracer's `ct test` — from the same document, by different people, in
different languages, at different times. Every ambiguity in the text becomes a
silent divergence that shows up as "your certificate does not verify here", with
no indication which side is wrong.

The vectors are the executable half of the specification. An implementation is
conformant when it reproduces them, not when its author believes it read the
document correctly.

## What the suite contains

### 1. Canonical payload vectors

Each vector is a certificate's field values plus the **exact bytes** its
canonical payload must serialize to.

```
vectors/payload/<name>/
  fields.json      # the field values, as data
  canonical.txt    # the exact expected bytes, LF, trailing newline
  pins.md          # the rule this case exists to pin, with citations
  received.toml    # OPTIONAL: a non-canonical rendering of the same values,
                   # which MUST parse to canonical.txt (Canonical-Payload §5)
```

An implementation passes by serializing `fields.json` and comparing bytes.

Required coverage — every one of these is a place the prose can be misread:

| Vector | What it pins |
| ------ | ------------ |
| `minimal` | Only required fields; `key_id` absent |
| `signed` | `key_id` present |
| `targets-unsorted-input` | Input in run order, output sorted |
| `targets-duplicates` | Duplicates removed before sorting |
| `targets-single` | One target, no separator |
| `targets-unicode` | Sorting is by UTF-8 **bytes**, not by collation |
| `escapes` | Every escape in the table, and only those |
| `non-ascii-literal` | UTF-8 emitted literally, never `\uXXXX` |
| `multiple-commands` | Execution order preserved, not sorted |
| `argv-duplicates` | Repeated arguments retained |
| `argv-empty-string` | An empty argument survives |
| `scoped` | `paths` present, sorted, deduplicated, before `content` |
| `unscoped` | `paths` omitted entirely, not `[]` |
| `base-present` | `base` present, last in `[certificate.vcs]`, after `untracked` |
| `content-manifest` | `content` emitted verbatim for a non-git algorithm; `base` absent |
| `untracked-true` | `untracked = true` emitted as a bare boolean |

### 2. Signature vectors

```
vectors/signature/<name>/
  canonical.txt    # payload bytes
  key.pub          # the public key
  signature.b64    # the expected detached signature, base64, one line
  expect.txt       # `verify` or `fail`
  pins.md
```

An implementation passes by **verifying** each. It is not required to reproduce
the signature bytes — ed25519 signing is deterministic under RFC 8032, but
producing an SSH signature blob involves framing an implementation may
legitimately vary — so the normative direction is verification.

Must include at least one vector that MUST **fail**: a signature made under a
different namespace, proving the implementation actually applies domain
separation rather than ignoring it. Such a vector has to fail for the *right
reason* — the namespace, not the bytes — so the signature it carries is a
genuine one, over exactly the payload in `canonical.txt`, by exactly the key in
`key.pub`.

The signing keys are published in `vectors/signature/keys/` so that anyone can
re-derive the group and confirm it was not fabricated. They are worthless as
keys and MUST NOT be registered anywhere.

### 3. Content-id vectors

Each vector is a set of tracked entries and the content ids they must produce
([Content-Id](./Content-Id.md)), whole-repository and scoped.

```
vectors/content/<name>/
  entries.json     # tracked entries: path, mode, content (base64), in arbitrary order
  expected.json    # content ids, per algorithm and per scope
  pins.md
```

An implementation passes by computing every listed id from `entries.json` and
comparing strings. The `git-tree-*` ids are additionally re-derivable with git
itself, which is the check that the vector was not fabricated.

Required coverage:

| Vector | What it pins |
| ------ | ------------ |
| `order-independent` | Entries supplied out of order yield the same ids |
| `byte-order` | `manifest-v1` sorts by raw full-path bytes, not by a per-directory walk: `a.b` precedes `a/b`, which precedes `a0` |
| `modes` | Regular, executable, symlink and nested-repository entries |
| `scope-keeps-paths` | A scoped `git-tree` id keeps full paths, and is not the subtree id; `src/db` excludes `src/dbx` |
| `empty-scope` | A scope matching nothing yields the empty tree / the digest of no records |
| `non-ascii-path` | Paths are raw bytes: no Unicode normalisation |
| `sha256-object-format` | `git-tree-sha256` for the same entries |

### 4. Verification-decision vectors

Each vector is a state, a requirement, a set of certificates and a key store,
with the expected outcome.

```
vectors/verify/<name>/
  state.json           # repo, commit, and the content ids the consumer can compute
  requirement.json     # framework(s), targets, platforms, signature policy, scope
  certificates/*.toml
  registered-keys.toml
  expected.json        # {"outcome": "covered" | "not-covered" | "unverifiable", …}
  pins.md
```

The state and the requirement are separate files because they are different
kinds of thing. A commit is not "on" a platform: platforms, targets, the
required scope and whether signatures are demanded are all the *consumer's*
choices, and a different consumer evaluating the same tree may reach a different
and equally correct verdict.

Required coverage:

| Vector | Expected |
| ------ | -------- |
| `coverage-union` | Two partial certificates together cover one platform |
| `wrong-platform` | A Linux certificate does not cover macOS |
| `other-framework` | An unrecognised framework is **ignored**, not rejected |
| `revoked-key` | Rejected although the signature is cryptographically valid |
| `empty-key-store` | Fail-closed: everything rejected |
| `unsigned-required` | Rejected outright, not downgraded |
| `content-matches-other-base` | A certificate whose `base` is not the commit under evaluation, but whose `content` matches, covers it |
| `content-differs` | Does not cover |
| `content-malformed` | Rejected: decidably invalid, so not covered |
| `content-unknown-algorithm` | **unverifiable** — an algorithm the consumer cannot compute is not a mismatch |
| `earlier-draft-record` | A record in the pre-2026-10-09 shape (`commit`, `clean`, no `content`) is decidably invalid: not covered |
| `scope-too-narrow` | A scoped certificate does not satisfy a broader requirement |
| `unreadable-store` | **unverifiable**, distinctly from not-covered |

That last one is the reason the outcome is three-valued, and it is the case an
implementation is most likely to collapse.

The suite additionally carries four cases that arrived with prose
clarifications, per "Maintaining the vectors" below:

| Vector | Expected |
| ------ | -------- |
| `unknown-schema` | **unverifiable** — an unimplemented schema version |
| `unverifiable-but-covered` | **covered** — a record that could not be read, next to a requirement already met without it |
| `unknown-schema-off-platform` | **unverifiable** — a record that *looks* irrelevant but cannot be interpreted, so its irrelevance cannot be established |
| `unreadable-store-off-platform` | **not-covered** — a record that could not be verified but *can* be interpreted, and its scope could not have met the requirement |

The last two are a deliberate pair, like `empty-key-store` / `unreadable-store`
before them. Both carry an unevaluable record that appears to be about another
platform entirely; they differ only in whether the consumer is entitled to
believe the appearance ([Verification §7.1](./Verification.md#71-precedence)).
An implementation that answers them the same way has collapsed the distinction
in one direction or the other.

## Using the suite

The vectors are plain data with no runner, so any language can consume them.
Each implementation writes a thin test that walks the directories and asserts.
[`vectors/README.md`](./vectors/README.md) is the directory contract: file
names, field shapes, and what each expected value means.

There is deliberately **no harness here for implementations to invoke**. The
`tools/` directory holds a reference serializer, a reference verifier and a
signature regenerator, used to check that the vectors themselves are correct
and to re-derive the signatures. None of it is normative, and no implementation
is required to read, port or run any of it. `tools/walk-vectors.sh` walks all
four groups with nothing but POSIX shell, `jq`, `ssh-keygen`, `git` and
`sha256sum`, which is the demonstration that consuming this suite needs no code
from this repository.

An implementation claiming conformance MUST run all four groups. Partial
conformance is not a status the standard recognises: an implementation that
passes the payload vectors but collapses `unverifiable` into `not-covered`
produces wrong answers in exactly the situation where a human most needs a
correct one.

## Maintaining the vectors

- A vector is **added** whenever an ambiguity is found in the prose, in the same
  change that clarifies the prose. The vector is what stops the ambiguity
  returning.
- A vector is **never edited to match an implementation.** If an implementation
  disagrees with a vector, either the implementation is wrong or the standard is
  — and deciding which is the whole point of having them.
- Changing a vector's expected bytes is a **breaking change to the standard**
  and requires a schema version bump, because every previously issued signature
  was made over the old bytes. The one exception was made while v1 was a draft:
  the 2026-10-09 revision replaced the commit binding with a content binding
  under the same schema id
  ([Canonical-Payload §7.1](./Canonical-Payload.md#71-the-2026-10-09-revision-content-replaces-commit)).
  Once v1 leaves draft, there are no more.
