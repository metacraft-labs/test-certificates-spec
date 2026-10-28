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
An implementation with a TOML reader MUST also reconstruct `canonical.txt`
from each supplied `received.toml`, including the physical newline and escape
distinction in `crlf-multiline`.

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
| `crlf-multiline` | Physical CRLF in multi-line basic and literal strings becomes LF; escaped CR and CRLF remain unchanged |
| `non-ascii-literal` | UTF-8 emitted literally, never `\uXXXX` |
| `multiple-commands` | Execution order preserved, not sorted |
| `argv-duplicates` | Repeated arguments retained |
| `argv-empty-string` | An empty argument survives |
| `scoped` | `paths` present, sorted, deduplicated, before `content` |
| `unscoped` | `paths` omitted entirely, not `[]` |
| `base-present` | `base` present, last in `[certificate.vcs]`, after `untracked` |
| `content-manifest` | `content` emitted verbatim for a non-git algorithm; `base` absent |
| `content-unknown-algorithm` | A relay serializes an opaque, well-formed unknown content id verbatim |
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
| `content-algorithm-name` | **not-covered** — non-portable algorithm identifiers are malformed before algorithm lookup |
| `content-unknown-algorithm` | **unverifiable** — an algorithm the consumer cannot compute is not a mismatch |
| `earlier-draft-record` | A record in the pre-2026-10-09 shape (`commit`, `clean`, no `content`) is decidably invalid: not covered |
| `scope-too-narrow` | A scoped certificate does not satisfy a broader requirement |
| `unreadable-store` | **unverifiable**, distinctly from not-covered |

That last one is the reason the outcome is three-valued, and it is the case an
implementation is most likely to collapse.

The suite additionally carries five cases that arrived with prose
clarifications, per "Maintaining the vectors" below:

| Vector | Expected |
| ------ | -------- |
| `unknown-keys` | **not-covered** — unknown keys and tables at every record level, including root and signature, are malformed even when signatures are optional (Standard §3.4) |
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

### 5. Store-path vectors

Each vector is a certificate and the path, relative to the store root, at which
[Transport §2.2](./Transport.md#22-layout) places it.

```
vectors/store/<name>/
  certificate.toml   # the certificate as a producer would write it
  expected-path.txt  # v1/<algorithm>/<digest>/<payload-hash>.toml, one line
  canonical.txt      # the canonical payload whose hash names it, for diagnosis
  pins.md
```

An implementation passes by deriving the path from `certificate.toml` —
reconstructing the canonical payload from the parsed fields
([Canonical-Payload §5](./Canonical-Payload.md#5-verifying-against-the-payload)),
never hashing the file — and comparing strings. `expected-path.txt` holds one
line terminated by a single LF, with `/` separating the components whatever
the platform's own separator; the LF is not part of the path.
`canonical.txt` is not an input: it is there to show where a mismatch begins,
and for a walker with no TOML parser.

Required coverage:

| Vector | What it pins |
| ------ | ------------ |
| `unsigned` | The layout: the content id split at its first `:`, the name the SHA-256 of the canonical payload |
| `signed` | The same fields plus `key_id` and a signature: a different payload, so a different name beside `unsigned`'s |
| `signed-non-canonical` | `signed`'s certificate rendered non-canonically, signature block included: `signed`'s name, since the payload, not the file, is hashed |
| `signed-non-canonical-no-block` | `signed`'s certificate with its signature block removed, non-canonically: still `signed`'s name, since `key_id` stays in the payload and the block never was |
| `manifest-content` | A `manifest-v1-sha256` content id |
| `scoped` | A scoped certificate, stored under its scoped content id |
| `unknown-algorithm` | A relay stores an opaque, well-formed unknown algorithm and one-digit digest verbatim |

The suite additionally carries `unsigned-empty-block`: the empty-signature-block
form of `unsigned` (Canonical-Payload §6), under `unsigned`'s name.

Algorithm-name runtime tests must drive both `put` and `find --content`.
Malformed prefixes must be rejected before store access; valid unknown names
must round-trip without rewriting, including the 64-character boundary and
names adjacent to reserved devices (`com0`, `con-v2`). Outside-store sentinels
must remain untouched.

Root resolution (Transport §2.1) depends on the environment and the platform and
is not a vector; implementations test it at runtime. Tests must cover absolute,
relative, empty and unset values for every variable read on each supported
platform, including `HOME`, `LOCALAPPDATA` and `ProgramData`; a drive-relative
Windows path is relative. They must show that a relative value is reported and
ignored, an available absolute fallback is used, and exhausting the fallbacks
leaves a reported unresolved root without consulting the current directory.
An absolute override must still work when its unused fallbacks are relative.
Reader and writer integration tests must show that an unresolved root
contributes no candidates while the other root is still searched, that an
incomplete empty search is reported distinctly from a completed empty search,
and that a writer needing the unresolved root fails without creating a store
relative to the current directory. A platform-independent resolver may test
other platforms' rules by taking the platform and environment as inputs; the
native reader and writer must also be exercised with a real environment.

Store access (Transport §2.3, §2.5) also needs runtime tests: ownership,
permission bits and access-control entries do not survive vector transport.
Use distinct producer and recipient accounts for system-partition tests, and
exercise the actual writer and pruner, with sentinel files outside the store
to detect redirected writes or deletion. Required cases are:

| Setup | Required result |
| ----- | --------------- |
| Missing system partition | Writer fails without creating it; pruner performs no mutation. |
| Partition owned by another account, or writable by its recipient through owner, group, other or ACL permissions | Writer and pruner report refusal before creating synchronization metadata, writing, renaming or deleting anything. |
| Safe partition with a foreign-owned or recipient-writable existing directory, or unsafe existing synchronization metadata | Writer and pruner refuse to enter or mutate the unsafe directory; writer refuses the unsafe metadata. Existing ownership, permissions and outside sentinels remain unchanged. |
| Valid producer-owned partition with recipient read/traverse access | Writer succeeds; recipient can discover and read the record but cannot create, replace or delete it. Pruner can remove an old unrelated content directory as a positive control. |
| The same valid partition, with writer umask `077` | Every newly created directory and record preserves the partition's intended reader access; records have no execute permission. Cover group access with an inherited group different from the producer's primary group, and ACL access on platforms supporting it. |
| Symbolic link at the partition, `v1`, algorithm or digest directory, or in a tree selected for pruning | No operation follows it; outside sentinels remain byte-identical, with no new outside files. |
| Existing user root owned by another account | Writer and pruner report refusal without changing that root or its contents. |
| Existing user root owned by the caller, and a newly created user root | Existing root ownership is accepted; on POSIX, newly created directories and files grant owner-only access. Both permit a write and ordinary pruning as positive controls. |

ACL cases must check effective access as the recipient, rather than merely
comparing mode bits. A platform that cannot safely inspect or reproduce a
required access policy must exercise its explicit refusal, not silently skip
the check or report successful system-store support. Re-run the refusal cases
against a deliberately unchecked writer/pruner to establish that their failure
is caused by the missing access check rather than an unrelated I/O error.

Pruning protection (Transport §2.5) likewise needs a live repository and store.
Integration tests must distinguish the unscoped `HEAD` and declared scopes in
both the native git-tree algorithm and `manifest-v1-sha256`, preserve those
directories even with `--keep 0`, and remove old unrelated directories as a
control. They must distinguish `HEAD` from staged and working-tree changes and
prove that an id-computation failure aborts before deletion. These are runtime
tests rather than store-path vectors.

Replacement tests (Transport §2.3) must relay a certificate carrying a real
verifying signature, then an altered signature over the same payload, and
assert the original bytes still verify. They must also cover absent and empty
signature blocks upgraded by a signed relay, an unsigned relay preserving a
signed copy, and an explicit signing writer repairing a failing copy. Relay
attempts over unreadable, malformed or misnamed existing files must report
failure without replacing them. Concurrent-process tests must demonstrate
that `.write-lock` serializes inspection and publication across writers,
including an unsigned-to-signed upgrade racing another signed writer.

### 6. Note-framing vectors

Each vector is a git-note blob holding several certificates, framed as
[Transport §3.1](./Transport.md#31-multiple-records-in-one-note) requires, and
the records a reader must find in it. Some are also a writer case: a record to
add, and the exact blob the note must become.

```
vectors/notes/<name>/
  note.txt           # the note blob, exact bytes; final LF may be absent
  expected.json      # the pieces a reader yields, in order: each a record
                     # (its canonical payload, and whether it is signed) or
                     # a piece reported and skipped
  pins.md
  add.txt            # OPTIONAL: one record a writer adds to note.txt
  expected-note.txt  # with add.txt: the blob after adding it, exact bytes
```

An implementation passes the reader half by splitting `note.txt` on lines equal
to the delimiter, parsing each piece, and comparing what it yields with
`expected.json`: the same number of pieces, a skipped piece where one is
listed, and otherwise the same canonical payload — rebuilt from the parsed
fields — and the same signedness, with every signature verifying under the
published vector key. It passes the writer half as a **relay** by adding
`add.txt` to `note.txt` and comparing the result with `expected-note.txt` byte
for byte.

Required coverage:

| Vector | What it pins |
| ------ | ------------ |
| `single-unsigned` | One record: a leading delimiter, nothing after the record |
| `signed-and-unsigned` | Two records with different payloads; a signed record's table follows one blank line; blank lines are not separators |
| `escaped-newline` | A value holding LF, the delimiter's text and LF: canonical escaping keeps it off a line of its own, so the split is on whole lines |
| `corrupt-middle` | A piece that does not parse is reported and skipped; its neighbours are still read |
| `foreign-preamble` | Text before the first delimiter — here a record framed with another tool's delimiter — is reported and skipped, never parsed, though it would parse |
| `appended` | Writer: a new payload goes after the last piece, behind its own delimiter |
| `signed-replaces-unsigned` | Writer: a signed copy of a present unsigned payload replaces it in place |
| `duplicate-not-added` | Writer: a payload already present is not added again |
| `unsigned-copy-not-added` | Writer: the unsigned copy of a present signed payload is not added, and does not replace it |
| `signed-copy-not-replaced` | Relay: an altered signed copy cannot replace a present signed payload |
| `signed-duplicate-protects` | Relay: a signed duplicate protects the payload even when an earlier matching record is unsigned |
| `unterminated-preamble`, `unterminated-corrupt`, `unterminated-record` | Append supplies exactly one LF after an unterminated foreign piece, corrupt piece or parsed record |
| `unterminated-duplicate` | A duplicate does not repair an unterminated record |
| `eof-delimiter`, `eof-delimiter-only` | An exact delimiter at EOF is a delimiter line; its empty trailing piece is skipped and preserved before an append |
| `eof-delimiter-duplicate` | A duplicate leaves the missing LF on an EOF delimiter unchanged |

The reader's signed records carry verifying signatures. The two signed-relay
writer cases deliberately alter `add.txt`'s signature without changing its
payload; the writer must preserve `note.txt` byte for byte without needing a
verifier. Signing-writer replacement is a runtime test with an explicitly
made signature, rather than a relay vector.

Two-blob merges use `notes/merge-*/{base.txt,other.txt,expected-note.txt,
expected.json,pins.md}` instead of the reader/writer layout above. An
implementation MUST produce the exact expected bytes with `base.txt` as the
published side, report the categories listed in `expected.json`, and leave the
bytes unchanged when merging `other.txt` again. See the directory contract in
[vectors/README.md](./vectors/README.md#two-blob-merge-cases).
Required cases cover piece order and corrupt preservation (`merge-order`),
signed upgrades and downgrades (`merge-signed-upgrade`, `merge-empty-signature-upgrade`,
`merge-unsigned-downgrade`), reported signed ties including duplicates
(`merge-signed-conflict`, `merge-signed-duplicate`), whole-line leading-block
containment (`merge-leading`, `merge-leading-present`,
`merge-leading-substring`), corrupt-piece LF equality (`merge-corrupt-lf`),
and repaired versus preserved EOF boundaries (`merge-eof-append`,
`merge-eof-delimiter`, `merge-eof-noop`, `merge-leading-eof`,
`merge-replacement-eof`).

Pushing, fetching and merging the notes ref, and finding a note by tree id,
need a live repository and are not vectors. Tests must cover relaying a
failing signature through notes publication and store import without losing
an existing verifying copy, a stale notes update racing another writer, and
reporting an LF repair when a merge appends after an unterminated piece.

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
groups with nothing but POSIX shell, `jq`, `ssh-keygen`, `git` and
`sha256sum`, which is the demonstration that consuming this suite needs no code
from this repository.

An implementation claiming conformance MUST run every group. Partial
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
