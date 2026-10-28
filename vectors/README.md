# Conformance vectors

The executable half of this standard. [Conformance.md](../Conformance.md) says
why these exist; this file is the **directory contract** — everything needed to
walk the suite from any language, without reading a line of anyone's
implementation.

The vectors are **plain data and there is no runner**. Each implementation
writes its own thin walker. Nothing in this repository has to be invoked,
imported, ported or trusted in order to claim conformance.

## Layout

```
vectors/
  index.json                every case, with the one-line rule it pins
  payload/<case>/           canonical serialization
    fields.json               input field values
    canonical.txt             the exact expected bytes
    pins.md                   which rule this case exists to pin
    received.toml             OPTIONAL, see "Non-canonical input" below
  signature/<case>/         signature verification
    canonical.txt             the signed payload bytes
    key.pub                   the public key to verify against
    signature.b64             the detached signature, base64
    expect.txt                `verify` or `fail`
    pins.md
  signature/keys/           the (published, worthless) signing keys
  content/<case>/           content ids (Content-Id.md)
    entries.json              tracked entries, in arbitrary order
    expected.json             the ids they must produce, per algorithm and scope
    pins.md
  verify/<case>/            three-valued verification decisions
    state.json                the repository state under evaluation
    requirement.json          what the consumer demands
    certificates/*.toml       the certificates found
    registered-keys.toml      the key store
    expected.json             the expected outcome
    pins.md
  store/<case>/             store paths (Transport.md §2.2)
    certificate.toml          a certificate as a producer would write it
    expected-path.txt         where it is stored, relative to the store root
    canonical.txt             the payload whose hash names it (diagnostic)
    pins.md
  notes/<case>/             note framing (Transport.md §3.1)
    note.txt                  a git-note blob holding several records
    expected.json             the pieces a reader yields from it
    pins.md
    add.txt                   OPTIONAL: a record a writer adds to note.txt
    expected-note.txt         with add.txt: the blob after adding it
```

Rules for a walker:

- **Directory names are case ids.** They are stable; treat a rename as a new
  case.
- **Ignore files you do not recognise.** New optional files will appear, and a
  walker that fails on them is a walker that cannot be updated.
- **Every case directory carries a `pins.md`** naming the rule it exists to
  pin, with citations into the prose and a "would be wrong if" note describing
  the implementation that fails it. Read the one for a case you fail — it is
  usually faster than reading the standard.
- `index.json` lists every case. Compare it against what you walked: a case
  that has silently gone missing is a case that stops testing anything.

## Group 1: `payload/`

An implementation passes by serializing `fields.json` and comparing the result
byte for byte with `canonical.txt`.

`fields.json` mirrors the TOML structure of a certificate exactly, so a reader
can hold the two side by side:

```json
{
  "schema": "test-certificate.v1",
  "certificate": {
    "framework": "example-framework",
    "project": "example",
    "platform": "linux/amd64",
    "targets": ["t-unit", "t-integration"],
    "result": "passed",
    "issued_at": "2026-06-23T10:14:33Z",
    "issuer": "example-runner@build-host-1",
    "key_id": "example-key-2026-q2",
    "vcs": {
      "repo": "example",
      "paths": ["src/db-backend"],
      "content": "git-tree-sha1:3c1f5e0a…",
      "untracked": false,
      "base": "a858633c…"
    },
    "command": [{"argv": ["example-test", "run"]}]
  }
}
```

The values are **inputs, not canonical output**:

- `targets` and `paths` arrive in whatever order the producer observed them and
  may contain duplicates. Sorting and deduplication are the serializer's job.
- `key_id`, `paths` and `base` are absent when they do not apply. `paths`
  may also be present and **empty**, which means the same thing as absent
  (Standard.md §3.2.1) and must still produce no `paths` line.
- `content` is an opaque string to the serializer, emitted verbatim
  (Canonical-Payload.md §2 rule 9). Computing it is the content group's
  business, not this one's.
- `untracked` is a JSON boolean, and must be emitted as a bare TOML boolean.

`canonical.txt` is the byte sequence a signature covers. It is UTF-8, LF-only,
BOM-free, has no trailing whitespace on any line, and ends with exactly one
newline.

> `.gitattributes` marks the whole directory `-text` so no checkout, on any
> platform, can rewrite these bytes.

### Non-canonical input

`vectors/payload/escapes/received.toml` is an OPTIONAL extra file: a
deliberately non-canonical rendering of the *same field values*. It uses CRLF
line endings, aligned `=`, tables and keys in a different order, a TOML literal
string, `\uXXXX` escapes, and an empty signature block.

`vectors/payload/crlf-multiline/received.toml` additionally uses multi-line
basic and literal strings containing physical CRLF newlines, which MUST be
read as LF. Escaped CR and CRLF in the same document MUST remain unchanged.

Parsing each `received.toml` MUST produce its case's exact `canonical.txt`. This is the requirement in
Canonical-Payload.md §5: a verifier reconstructs the payload **from the parsed
fields**, never by slicing the received file, or a cosmetically reformatted
certificate would fail against its own valid signature.

An implementation with no TOML parser can skip `received.toml` files. An
implementation with a TOML parser MUST check every one.

## Group 2: `signature/`

An implementation passes by **verifying**, not by reproducing `signature.b64`.
Conformance.md §2 sets that direction deliberately: SSH signature framing is an
implementation's own business, while verification is what interoperability
actually needs.

`expect.txt` holds one word:

| `expect.txt` | Meaning |
| ------------ | ------- |
| `verify` | The signature MUST verify over `canonical.txt`, under the namespace `test-certificate-v1`, against `key.pub`. |
| `fail` | It MUST NOT verify. Read `pins.md` for the reason it must fail *for*. |

`signature.b64` is the base64 of the detached signature blob — the same string a
certificate carries in `signature.value` (Standard.md §6.1). It is standard
RFC 4648 §4 base64, padded, on a single line, with no embedded whitespace.

`ssh-keygen` reads the armored form instead, and the conversion is pure framing:

```sh
{ printf -- '-----BEGIN SSH SIGNATURE-----\n'
  cat signature.b64
  printf -- '-----END SSH SIGNATURE-----\n'; } > /tmp/sig

printf 'anyone@example.invalid %s\n' "$(cat key.pub)" > /tmp/allowed_signers

ssh-keygen -Y verify -f /tmp/allowed_signers -I anyone@example.invalid \
           -n test-certificate-v1 -s /tmp/sig < canonical.txt
```

The identity is arbitrary. An SSH signature blob binds the namespace and the
public key, not a principal; the principal only selects a line in
`allowed_signers`.

### The failing vectors are the point

`signature/wrong-namespace` is a **genuine** signature, by the right key, over
exactly these bytes — made under the namespace `git`, the one OpenSSH uses for
commit and tag signing. It must fail, and it must fail *because the namespace
does not match*. Developers who sign commits have produced signatures over
arbitrary bytes under `git`; without domain separation, any of them is a test
certificate (Standard.md §6.1).

If your implementation fails that vector because it compared the payload
wrongly, it has not demonstrated domain separation. Check the reason you
report, not only the verdict.

### Re-deriving the signatures

The signing keys are published in `signature/keys/` — see the warning in that
directory's README before you go anywhere near them. ed25519 is deterministic
under RFC 8032 and OpenSSH's framing adds nothing random, so signing the same
payload with the same key reproduces the same bytes on any machine:

```sh
python3 tools/regenerate.py --check    # non-zero if any signature would change
```

## Group 3: `content/`

An implementation passes by computing every id in `expected.json` from
`entries.json` and comparing the strings.

`entries.json` is the set of tracked files, in **arbitrary order**:

```json
[
  {"path": "src/main.c", "mode": "100644", "content_b64": "aW50IHJ1bih2b2lkKTsK…"},
  {"path": "current",    "mode": "120000", "content_b64": "bGliLmM="},
  {"path": "vendor/dep", "mode": "160000", "content_b64": "M2YyYTljMWU1Yjdk…"}
]
```

| Field | Meaning |
| ----- | ------- |
| `path` | The repo-relative path, as a JSON string; its UTF-8 encoding is the path's bytes (Content-Id.md §4.2). Never normalise it. |
| `mode` | One of `100644`, `100755`, `120000`, `160000` (Content-Id.md §4.2). |
| `content_b64` | Standard base64 of the entry's content: the file's bytes, a symlink's target, or — for `160000` — the nested repository's revision id as ASCII hex. |

`expected.json` lists the ids those entries must produce:

```json
[
  {"algorithm": "git-tree-sha1",      "paths": null,     "id": "git-tree-sha1:6904711a…"},
  {"algorithm": "manifest-v1-sha256", "paths": ["src"],  "id": "manifest-v1-sha256:2c353274…"}
]
```

`paths` is the scope, exactly as a certificate's `vcs.paths` would carry it:
`null` is the whole repository. `id` is the full self-describing content id
(Content-Id.md §1). An implementation need only compute the algorithms it
implements, and should say which it skipped; but a producer or verifier that
implements an algorithm and skips its vectors has tested nothing.

The `git-tree-*` ids are **re-derivable with git**, which is the check that
they were not fabricated. Write each entry as an object (`git hash-object -w`;
a `160000` entry is not an object, its revision is used as is), stage them into
a scratch index with `git update-index -z --index-info`, and `git write-tree`
— in a repository made with `git init --object-format=sha256` for
`git-tree-sha256`. A scoped id then follows the recipe in Content-Id.md §4.1
verbatim. `tools/walk-vectors.sh` does exactly this.

## Group 4: `verify/`

An implementation passes by producing the expected **three-valued** outcome.

`state.json` is the world being evaluated:

```json
{
  "repo": "example",
  "commit": "a858633c…",
  "content": [
    {"algorithm": "git-tree-sha1", "paths": null,              "id": "git-tree-sha1:9f8e7d6c…"},
    {"algorithm": "git-tree-sha1", "paths": ["src/db-backend"], "id": "git-tree-sha1:3c1f5e0a…"}
  ]
}
```

| Field | Meaning |
| ----- | ------- |
| `commit` | The commit under evaluation. **Informational**: nothing compares a certificate with it (Verification.md §4.1.1), and an implementation that does fails `content-matches-other-base` and `content-differs`. |
| `content` | The content ids this consumer can compute for the state, per algorithm and per scope — what Content-Id.md §5 would produce. |

An algorithm absent from `content` is one this consumer **cannot compute**: a
certificate in it is unevaluated, not mismatched (Verification.md §4.1.1).
Whenever an algorithm is listed, every scope used by a certificate of that
algorithm in the case is listed too, so a walker never has to compute an id
itself. Match a certificate by looking up the entry with its algorithm and its
scope (`paths` sorted and deduplicated; absent, empty and `null` are all the
whole repository), then comparing `id` with `vcs.content` as strings.

`requirement.json` is what the consumer demands. It is separate from the state
on purpose: a commit is not "on" a platform, and platforms, targets and
signature policy are all the consumer's choices, not properties of the tree.

```json
{
  "frameworks_implemented": ["example-framework"],
  "framework": "example-framework",
  "targets": ["t-integration", "t-unit"],
  "platforms": ["linux/amd64"],
  "require_signature": true,
  "paths": null
}
```

| Field | Meaning |
| ----- | ------- |
| `frameworks_implemented` | Frameworks this consumer implements. Certificates from any other framework are **ignored**, not rejected (Verification.md §2). |
| `framework` | The framework this particular requirement is about. |
| `targets` / `platforms` | What must be covered, on which platforms. |
| `require_signature` | When true, unsigned certificates are rejected outright rather than downgraded (Standard.md §6). |
| `paths` | The scope that must be covered. `null` means the whole repository. A scoped certificate satisfies it only when every required path lies inside the certificate's scope (Verification.md §4.1.2). |

`expected.json` holds the outcome and the detail the report must carry:

```json
{
  "outcome": "not-covered",
  "reason": "prose for a human; not compared",
  "missing":     [{"framework": "…", "platform": "…", "targets": ["…"]}],
  "ignored":     [{"certificate": "…", "why": "prose"}],
  "rejected":    [{"certificate": "…", "why": "prose"}],
  "unevaluated": [{"certificate": "…", "why": "prose"}]
}
```

- **`outcome` is normative**, and is one of `covered`, `not-covered`,
  `unverifiable`.
- **`missing` is normative in content.** Verification.md §5 requires a consumer
  to report *what* is missing — which target, on which platform, for which
  framework — not a bare pass/fail. The rendering is yours; the gaps are not.
- **`ignored` / `rejected` / `unevaluated` are normative in which certificates
  they name**, because those three fates are the ones an implementation
  confuses. Your wording will differ; the classification should not.
- `reason` and every `why` are prose for humans. Do not compare them.

### `unverifiable` is not `not-covered`

This is the distinction the third value exists for, and the one an
implementation is most likely to collapse — because both fail a gate, so a
boolean verifier passes its own tests and looks correct.

| Outcome | The consumer… | What the operator should do |
| ------- | ------------- | --------------------------- |
| `covered` | could tell, and it is covered | nothing |
| `not-covered` | **could tell**, and it is not | run the tests |
| `unverifiable` | **could not tell** | fix the configuration; re-running tests changes nothing |

Four pairs of cases exist precisely to hold the line:

| Pair | Outcomes | Why they differ |
| ---- | -------- | --------------- |
| `empty-key-store` vs `unreadable-store` | not-covered vs unverifiable | An empty store *answers*: nobody is trusted, fail-closed. An unreadable store answers nothing. |
| `content-malformed` vs `unknown-schema` | not-covered vs unverifiable | A record carrying a malformed required v1 field is decidably invalid. A record in a schema version this consumer does not implement may be perfectly good and simply unreadable here. |
| `content-malformed` vs `content-unknown-algorithm` | not-covered vs unverifiable | A malformed content id is wrong, and the consumer can say so. A well-formed id in an algorithm it cannot compute may match perfectly; the consumer cannot tell. |
| `unreadable-store-off-platform` vs `unknown-schema-off-platform` | not-covered vs unverifiable | Both carry an unevaluable record that *appears* to be about another platform. Only in the first can the consumer interpret the record, and so actually know the appearance is true (Verification.md §7.1). |

An implementation that returns two values passes none of the first three
pairs. The fourth catches a subtler error that a three-valued implementation can
still make: treating every record it could not evaluate as decisive, and
reporting `unverifiable` for a configuration fault that could not have changed
the verdict.

`unreadable-store` models unreadability as **unparseable content**, because file
modes do not survive git — only the executable bit is recorded — and a
permission-denied file cannot be shipped as data. What the consumer must do is
identical either way.

## Group 5: `store/`

An implementation passes by deriving, from `certificate.toml`, the path at
which [Transport.md §2.2](../Transport.md#22-layout) stores it, and comparing
the string with `expected-path.txt`:

```
v1/<algorithm>/<digest>/<payload-hash>.toml
```

| File | Meaning |
| ---- | ------- |
| `certificate.toml` | The certificate, as a producer would deliver it to the store — signature block included when it has one. Some are deliberately **not** in canonical form: CRLF, tables in another order, the signature block first, literal strings, `\uXXXX` escapes, inline tables. |
| `expected-path.txt` | One line, terminated by a single LF that is not part of the path. Relative to the store root; components separated by `/` on every platform, so a walker on Windows converts before comparing with a path it built natively. |
| `canonical.txt` | The canonical payload of `certificate.toml`, byte for byte — a copy of the hand-derived `payload/` vector its `pins.md` names. **Not an input**: it shows where a mismatch starts, and lets a walker with no TOML parser check the hashing half. |

What a walker does, per case:

1. Parse `certificate.toml` and rebuild the canonical payload from the parsed
   fields, exactly as a verifier does
   ([Canonical-Payload.md §5](../Canonical-Payload.md#5-verifying-against-the-payload)).
   The signature block is not part of it, wherever it appears in the file.
2. `<payload-hash>` is the lowercase hex SHA-256 of those bytes — never of the
   file. `sha256sum certificate.toml` is wrong for every signed case, and for
   every non-canonical one.
3. Split `vcs.content` at its **first** `:`
   ([Content-Id.md §1](../Content-Id.md#1-form)): `<algorithm>`, then `<digest>`.
4. Join `v1`, `<algorithm>`, `<digest>` and `<payload-hash>.toml` with `/`.

The cases come in groups that share a name, which is the point of them:

| Name | Cases | Why they agree |
| ---- | ----- | -------------- |
| `…/2bdea115….toml` | `unsigned`, `unsigned-empty-block` | An absent and an empty signature block are the same unsigned payload (Canonical-Payload.md §6). |
| `…/de22c2c4….toml` | `signed`, `signed-non-canonical`, `signed-non-canonical-no-block` | Three different files, one payload: the rendering is not hashed, and neither is the signature block. `key_id` *is* in the payload, so stripping the block does not make the certificate `unsigned`'s twin. |

`signed` and `unsigned` share a content directory and differ in name: the same
claim, signed and not, is two payloads. A store that keeps both has two files,
and neither replaces the other.

The signatures in `signed` and `signed-non-canonical` are real: made over
`canonical.txt` with the published key `signature/keys/insecure-test-key`
(`key_id` `example-key-2026-q2`) and re-derivable with
`python3 tools/regenerate.py`. A walker need not verify them to pass this
group; they are there so that a non-canonical file is provably the certificate
it claims to be.

## Group 6: `notes/`

An implementation passes by reading `note.txt` as
[Transport.md §3.1](../Transport.md#31-multiple-records-in-one-note) requires
and yielding exactly the pieces `expected.json` lists; and, for a case that has
an `add.txt`, by adding that record to `note.txt` and producing
`expected-note.txt` byte for byte.

| File | Meaning |
| ---- | ------- |
| `note.txt` | The note blob, exact bytes, LF. Each record is preceded by the line `# --- test-certificate ---`; `foreign-preamble` deliberately does not begin with one. |
| `expected.json` | `{"pieces": [...]}`, in blob order. A record is `{"payload": "<the canonical payload, as a JSON string>", "signed": true \| false}`, with `payload_vector` naming the `payload/` case whose `canonical.txt` it copies, when it copies one. A skipped piece is `{"skipped": true, "why": "prose"}`. |
| `add.txt` | One record in the §3.1 record form — canonical payload, and when signed a blank line and the signature table — with no delimiter. |
| `expected-note.txt` | The blob after adding `add.txt`. Present exactly when `add.txt` is. |

What a walker does, per case:

1. Split `note.txt` on lines **equal to** the delimiter — never on occurrences
   of its text (`escaped-newline`).
2. The piece before the first delimiter is empty in a conforming note and is
   dropped. When it is not empty it is the first entry of `pieces`, and is
   skipped: it is never parsed, even when it would parse (`foreign-preamble`).
3. Parse every other piece as one certificate. A piece that does not parse is
   a `skipped` entry, reported; the next piece is still read
   (`corrupt-middle`).
4. For each record, rebuild the canonical payload from the parsed fields and
   compare it with `payload` byte for byte; compare whether it carries a
   signature table with `signed`. Every signed record carries a real ed25519
   signature over its payload by the published key
   `signature/keys/insecure-test-key` (`key_id` `example-key-2026-q2`); verify
   it.
5. For a writer case, add `add.txt`: if a piece's payload equals its payload,
   act as a relay: keep the note unchanged if any matching piece is signed;
   otherwise replace the first matching piece when `add.txt` is signed and
   leave the note alone when it is not. If no payload matches, append the
   delimiter and `add.txt`. Every other piece stays byte for byte. Compare
   with `expected-note.txt`.
   `signed-copy-not-replaced` and `signed-duplicate-protects` deliberately
   carry an altered signature in `add.txt`: no writer verification is needed,
   and the existing verifying signature must survive.

`payload` and `signed` are normative; `why` is prose. A walker with no TOML
parser can treat "parses" as "is in the §3.1 record form", since that is what
a conforming writer produces — `tools/walk-vectors.sh` does — but a real reader
parses.

The writer cases share their notes with the reader cases, and the pairs are the
point:

| Cases | Why they differ |
| ----- | --------------- |
| `signed-replaces-unsigned` vs `unsigned-copy-not-added` | The same payload, signed and not, in opposite directions: a signed copy replaces an unsigned one in place; an unsigned copy never replaces a signed one. |
| `signed-copy-not-replaced` vs `signed-duplicate-protects` | A relay preserves a signed match, including when an unsigned duplicate appears first; the altered incoming signature must not displace the verifying one. |
| `appended` vs `duplicate-not-added` | `payload/minimal` added to a note that lacks it, and to one that has it. |

## Ambiguities this suite closed

Per Conformance.md, a vector is added whenever an ambiguity is found in the
prose, **in the same change that clarifies the prose**. Authoring this suite
found these, and the listed documents were changed. Three were found while
moving the suite to the 2026-10-09 content binding, the two about the
signature block and the store while adding the `store/` group, and the three
about note framing while adding the `notes/` group:

| Ambiguity | Resolution | Vector |
| --------- | ---------- | ------ |
| Can an unknown algorithm contain path syntax or a non-portable directory name, and may a relay store it? | Algorithm identifiers are 1–64 lowercase ASCII letters, digits or hyphens, excluding Windows device names; invalid names are malformed. Relays and explicit lookups accept unknown well-formed ids verbatim, although producers cannot issue them — Content-Id §1, Transport §2.2, Tooling §2 | `verify/content-algorithm-name`, `store/unknown-algorithm` |
| Is `targets` sorted on the raw value bytes or on the escaped rendering? They differ for values containing escapes. | Raw value bytes, before escaping — Canonical-Payload.md §3 | `payload/escapes` |
| What happens to a control character with no escape in the table? §4 says "no other character is escaped", but TOML basic strings cannot carry one raw. | Not representable, therefore malformed — Canonical-Payload.md §4 | (a rejection case, not a serialization one) |
| Is Unicode normalization applied anywhere? | No; after the physical newline rule in §5, values are the exact code points parsed — Canonical-Payload.md §4 | `payload/non-ascii-literal` |
| May a TOML reader choose platform-specific newlines inside multi-line strings? | No; physical LF and CRLF are read as LF, while escaped CR and CRLF are preserved — Canonical-Payload.md §5 | `payload/crlf-multiline` |
| Is `issued_at` a quoted string or a TOML datetime, and is `Z` required over `+00:00`? | A basic string, copied verbatim; `Z` — Canonical-Payload.md §2 | every payload vector |
| May `targets` or `argv` be empty? | No; at least one each — Canonical-Payload.md §2, §3 | (a rejection case) |
| How is `signature.value` base64 framed — padding, line wrapping? | RFC 4648 §4, padded, single line — Standard.md §6.1 | every `signature/` vector |
| Is `format` compared as an opaque string, and how much must it pin? | Opaque, exact equality; must pin every option affecting the patch bytes. *Superseded:* the 2026-10-09 revision removed `format` with the rest of `[certificate.vcs.worktree]` (Canonical-Payload.md §7.1) | (`payload/dirty-patch-only`, removed with it) |
| Standard.md §7 said a verifier *rejects* an unknown `schema`; Verification.md §7 listed an unimplemented schema version as *unverifiable*. | Unverifiable — Standard.md §7 now defers to Verification.md §7 | `verify/unknown-schema` |
| Verification.md §3.1 called a missing or empty store fail-closed while §7 called an unreadable store unverifiable, without distinguishing them. | Missing/empty answers the question (not-covered); unreadable does not (unverifiable) — Verification.md §3.1 | `verify/empty-key-store`, `verify/unreadable-store` |
| Which outcome wins when one certificate cannot be evaluated and others cover the requirement? | Covered, with the unevaluated record still reported — Verification.md §7 | `verify/unverifiable-but-covered` |
| Does an unevaluable record that looks irrelevant still force `unverifiable`? §7.1 said "anything that could have changed the answer" without saying who may judge that. | Only a record you can **interpret** can be judged irrelevant; an uninterpretable one is potentially relevant by default — Verification.md §7.1 | `verify/unknown-schema-off-platform`, `verify/unreadable-store-off-platform` |
| Where does the *requirement* live in a verification vector? Conformance.md §3 put `platform` in `state.json` and named no home for targets or signature policy. | A separate `requirement.json` — Conformance.md §4 (then §3) | every `verify/` vector |
| Where does a content id's algorithm end? Content-Id.md §1 defined the form `<algorithm>:<digest>` without saying which `:` separates them, and `git-tree-sha1:sha1:…` is malformed under one reading and an uncomputable algorithm (unverifiable) under the other. | At the **first** `:` — Content-Id.md §1 | `verify/content-malformed` (`d-second-colon.toml`) |
| Is a content id naming an algorithm the standard does not define malformed or unverifiable? Content-Id.md §1 listed "an unknown algorithm" among the malformed forms, while Verification.md §4.1.1 listed only the form errors as malformed and called an algorithm the consumer cannot compute unverifiable; and "a digest of the wrong length" cannot be judged for an algorithm that defines no length. | Unverifiable: well-formed, uncomputable, length not judged; producers still MUST NOT emit one — Content-Id.md §1, Verification.md §4.1.1 | `verify/content-unknown-algorithm` (`b-unknown-algorithm.toml`) |
| Conformance.md §5 asked for "the same certificate with and without its signature block in non-canonical form" next to "a signed and an unsigned certificate", which reads either as the signed/unsigned twins again or as a signed certificate whose block was removed — and the two land on different names. | A signed certificate with its block removed keeps `key_id`, so keeps its payload and its name; Conformance.md §5 now lists the with-block and without-block renderings as separate cases | `store/signed-non-canonical`, `store/signed-non-canonical-no-block` |
| Transport.md §2.3 let a producer keep an existing file under the final name because "for a signed one either signature verifies over the same payload" — but the name is the payload's hash and the signature block is outside the payload, so a signed certificate and the same record without its block share a name, and keeping the existing file could discard the signature. §2.4 likewise evaluated a name found in both roots "once" without saying which copy. | A signing writer delivering its own signed copy replaces the existing file, whose signature may be absent, emptied or failing; a relay only upgrades unsigned copies; an unsigned write may keep it; a reader evaluates every copy of a name that is not byte-identical to one already evaluated, so no copy hides another — Transport.md §2.3, §2.4 | `store/signed-non-canonical-no-block` |
| Is `manifest-v1`'s path order "not git's tree order"? Content-Id.md §4.2 said so, but git's recursive tree order — which sorts a directory as if its name ended in `/` — *is* full-path byte order: `git ls-tree -r` lists `a.b`, `a/b`, `a0`, exactly as `manifest-v1` does. The order that differs is a walk sorting each directory's names on their own, which emits `a/b` first. | Byte order of the full path, which coincides with git's listing order and differs from a per-directory walk — Content-Id.md §4.2, Conformance.md §3 | `content/byte-order` |
| Transport.md §3.1 required unambiguous framing but named no delimiter or record form — implementations invented their own (reprobuild used `# --- reprobuild-certificate ---`). | A fixed delimiter line, `# --- test-certificate ---`, before every record, and records in canonical form so the delimiter cannot occur inside one; a reader splits on whole lines and reports and skips a piece that does not parse — Transport.md §3.1, Tooling.md | every `notes/` vector |
| Transport.md §3.1, as first drafted in this change (never published), told a reader to drop "the empty piece before the first" delimiter without saying what to do when it is not empty, said nothing about what lies between records, and said nothing about where a writer puts a new or replacing record — so two conforming writers could produce different blobs for the same note. | A non-empty leading piece is reported and skipped, never parsed; nothing lies between a record's last LF and the next delimiter; a new record is appended, a replacement takes the replaced record's place, and every other piece is kept byte for byte — Transport.md §3.1 | `notes/foreign-preamble`, `notes/appended`, `notes/signed-replaces-unsigned` |
| Transport.md §3.1, as first drafted in this change (never published), replaced a present record only when "the new copy is signed and the present one is not, … as in the local store (§2.3)" — but §2.3 has a signing producer replace the existing copy whatever its block, since a present signature may fail. | As clarified in §2.3: a signing writer replaces the present copy, while a relay upgrades only unsigned copies; an unsigned copy never replaces — Transport.md §3.1 | `notes/signed-replaces-unsigned`, `notes/unsigned-copy-not-added` |
| Does Content-Id.md §4.1's recipe (`cp` the index, `git add --update`, `git write-tree`) see every working-tree change? It did not: in the copy, git trusted stat data that the user's index would have re-checked — a same-size edit in the second of the last index write read as clean, so the digest named the old content (found by a 1-in-3 flake in a producer's status display). | The copy is dated one second after the epoch and the filesystem monitor is off, so git compares every tracked file's content — Content-Id.md §4.1 | (none: a vector's file timestamps do not survive `git archive`, so the state cannot be shipped; producers test it with explicit timestamps) |
| Transport.md §2.1 ignored relative overrides and `XDG_STATE_HOME` but did not say whether relative `HOME`, `LOCALAPPDATA` or `ProgramData` were usable, or what happened when no fallback resolved a root. | Every variable read must yield a non-empty absolute path; relative values are reported and ignored. An unresolved root is reported, contributes no certificates to a reader's search, and is an error for a writer that requires it; the other root remains usable — Transport.md §2.1 | (none: root resolution and reader/writer behaviour are runtime checks, required by Conformance.md §5) |
| The schema did not say whether unknown keys were extensions or malformed, and a reader could drop unsigned claims before reconstructing the payload. | Every v1 table is closed, including root and signature; unknown keys and tables are malformed even when signatures are optional — Standard.md §3.4, Canonical-Payload.md §5 | `verify/unknown-keys` |
| Does receiving a signature establish that a writer may replace an existing signed copy? | Only a writer delivering its own freshly made signature knows it verifies. A relay preserves any signed match and only upgrades unsigned copies; all store writers serialize inspection and publication — Transport.md §2.3, §3.1 | `notes/signed-copy-not-replaced`, `notes/signed-duplicate-protects`; store and ref races are runtime checks required by Conformance.md §5, §6 |
| May a system writer create its partition, what permissions do its descendants receive, and are existing roots checked before writing or pruning? | A system partition must already exist, belong to the effective producer account and give its distinct recipient read/traverse but no effective write access. Newly created descendants preserve its group or ACL reader policy independently of umask; regular records have no execute bits. Writers and pruners check ownership of existing user roots and refuse foreign roots. Unsafe or unsupported checks fail before mutation — Transport.md §2.3, §2.5 | (none: ownership, effective access, umask and link confinement require the runtime access matrix in Conformance.md §5) |

## Cases beyond the required set

Conformance.md requires 17 payload cases, 7 content-id cases, 14
verification cases, 7 store-path cases and 11 note-framing cases, and itself
lists the cases below
that go beyond them. Each is marked as such in its `pins.md`:

| Case | Why |
| ---- | --- |
| `verify/unknown-keys` | Closed v1 records reject unknown keys and tables at every level. |
| `verify/unknown-schema` | Added with the Standard.md §7 clarification above. |
| `verify/unverifiable-but-covered` | Added with the Verification.md §7 precedence rule above. |
| `verify/unknown-schema-off-platform` | Added with the Verification.md §7.1 relevance rule above. |
| `verify/unreadable-store-off-platform` | Its mirror, and the reason the rule is not simply "assume everything unevaluable mattered". |
| `store/unsigned-empty-block` | The store half of Canonical-Payload.md §6: the empty-block form of an unsigned certificate is the same payload, so the same name. |

## What this suite does not cover

Stated so that nobody mistakes a gap for a guarantee:

- **Reformatting tolerance in the `verify/` group.** Every certificate there is
  in canonical form. `payload/escapes/received.toml` and
  `payload/crlf-multiline/received.toml` exercise Canonical-Payload.md §5.
- **Rejection cases as a group.** Malformed records appear only where a
  decision depends on them (`verify/content-malformed`,
  `verify/earlier-draft-record`). There is no systematic "these records MUST be
  rejected" group yet.
- **Producing a content id from a working tree.** The content group starts from
  a list of tracked entries. What belongs in that list — index entries, not
  untracked files; working-tree bytes after the VCS's normalisation; refusal on
  unmerged, `assume-unchanged` or `skip-worktree` entries and modified nested
  repositories (Content-Id.md §2, §3) — is a property of a live repository and
  is not exercised. Nor is the before-and-after comparison a producer makes
  around the run (Standard.md §3.2).
- **Binary content and NUL in the content group.** Every entry's content is
  valid UTF-8 text, so that a walker using only `jq` can decode it. Content-Id
  treats content as bytes, and an implementation must; the vectors do not
  prove that it does.
- **Computing the state's content id in the `verify/` group.** `state.json`
  hands the consumer its ids ready-made; the content group is where computing
  them is tested.
- **Framework-specific validity.** By construction: Verification.md §4.2 says
  there is nothing generic to test there.
- **Transport, beyond the store layout and note framing.** The `store/` group
  pins where [Transport.md §2.2](../Transport.md#22-layout) puts a certificate,
  and the `notes/` group how §3.1 frames several in one note. Root resolution
  (§2.1) depends on the environment, and atomic writing, reading both roots
  and pruning (§2.3–§2.5) on a live file system; finding a note by tree id,
  pushing, fetching and merging the notes ref (§3, Tooling.md) on a live
  repository. None of them is a vector — in particular, the order of records
  after a merge of two sides' notes is not pinned.
  In particular, Transport §2.5's protection of computed `HEAD` ids includes
  declared scopes and multiple algorithms; the live-repository checks in
  Conformance §5, rather than a store-path vector, pin that pruning policy.
- **Issuing unknown content algorithms.** `store/unknown-algorithm` pins relay
  layout, not issuance; Content-Id §1 still forbids issuing such a claim.

## The tools directory is not part of the suite

[`tools/`](../tools) holds a reference serializer, a reference content-id
implementation, a reference verifier, a signature regenerator, a POSIX-shell
walker and a corruption demonstration.
They exist so that the vectors themselves can be checked and re-derived.

**No implementation is required to read, port or invoke any of them**, and
nothing in `tools/` is normative. Where a tool and the prose disagree, the prose
wins and the tool is a bug. `tools/walk-vectors.sh` is worth a look anyway: it
walks all six groups with nothing but POSIX shell, `jq`, `ssh-keygen`, `git`
and `sha256sum`, which is the concrete demonstration that this suite needs no
language-specific tooling.
