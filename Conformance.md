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
| `scoped` | `paths` present, sorted, deduplicated |
| `unscoped` | `paths` omitted entirely, not `[]` |
| `dirty-tree` | `worktree` present with `tree` |
| `dirty-patch-only` | `worktree` present with `patch_digest` only |
| `clean-no-worktree` | `worktree` absent, and must be |

The suite additionally carries `dirty-tree-and-patch`, which shows all three
`worktree` keys in their fixed order — the fourth worktree shape, which none of
the three rows above reaches.

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

### 3. Verification-decision vectors

Each vector is a state, a requirement, a set of certificates and a key store,
with the expected outcome.

```
vectors/verify/<name>/
  state.json           # repo, commit and tree id under evaluation
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
| `dirty-tree-matches` | A `worktree.tree` matching the committed tree covers it |
| `dirty-tree-differs` | Does not cover |
| `dirty-no-worktree` | Rejected: identifies no state |
| `scope-too-narrow` | A scoped certificate does not satisfy a broader requirement |
| `unreadable-store` | **unverifiable**, distinctly from not-covered |

That last one is the reason the outcome is three-valued, and it is the case an
implementation is most likely to collapse.

The suite additionally carries two cases that arrived with prose clarifications,
per "Maintaining the vectors" below: `unknown-schema` (unverifiable — an
unimplemented schema version) and `unverifiable-but-covered` (covered — a record
that could not be read, next to a requirement already met without it).

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
three groups with nothing but POSIX shell, `jq` and `ssh-keygen`, which is the
demonstration that consuming this suite needs no code from this repository.

An implementation claiming conformance MUST run all three groups. Partial
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
  was made over the old bytes.
