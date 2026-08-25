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
  verify/<case>/            three-valued verification decisions
    state.json                the repository state under evaluation
    requirement.json          what the consumer demands
    certificates/*.toml       the certificates found
    registered-keys.toml      the key store
    expected.json             the expected outcome
    pins.md
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
      "commit": "a858633c…",
      "paths": ["src/db-backend"],
      "clean": false,
      "untracked": false,
      "worktree": {
        "tree": "9f8e7d6c…",
        "format": "git-diff --no-renames -U3",
        "patch_digest": "blake3:4a1b…"
      }
    },
    "command": [{"argv": ["example-test", "run"]}]
  }
}
```

The values are **inputs, not canonical output**:

- `targets` and `paths` arrive in whatever order the producer observed them and
  may contain duplicates. Sorting and deduplication are the serializer's job.
- `key_id`, `paths` and `worktree` are absent when they do not apply. `paths`
  may also be present and **empty**, which means the same thing as absent
  (Standard.md §3.2.1) and must still produce no `paths` line.
- Booleans are JSON booleans, and must be emitted as bare TOML booleans.

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

Parsing it MUST produce exactly `canonical.txt`. This is the requirement in
Canonical-Payload.md §5: a verifier reconstructs the payload **from the parsed
fields**, never by slicing the received file, or a cosmetically reformatted
certificate would fail against its own valid signature.

An implementation with no TOML parser can skip this file. One with a TOML
parser should not.

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

## Group 3: `verify/`

An implementation passes by producing the expected **three-valued** outcome.

`state.json` is the world being evaluated:

```json
{
  "repo": "example",
  "commit": "a858633c…",
  "tree": "9f8e7d6c…"
}
```

`tree` is the canonical content id of that state, used to match
modified-worktree claims (Verification.md §4.1.1).

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

Two pairs of cases exist precisely to hold the line:

| Pair | Outcomes | Why they differ |
| ---- | -------- | --------------- |
| `empty-key-store` vs `unreadable-store` | not-covered vs unverifiable | An empty store *answers*: nobody is trusted, fail-closed. An unreadable store answers nothing. |
| `dirty-no-worktree` vs `unknown-schema` | not-covered vs unverifiable | A record missing a required v1 field is decidably invalid. A record in a schema version this consumer does not implement may be perfectly good and simply unreadable here. |

An implementation that returns two values passes neither pair.

`unreadable-store` models unreadability as **unparseable content**, because file
modes do not survive git — only the executable bit is recorded — and a
permission-denied file cannot be shipped as data. What the consumer must do is
identical either way.

## Ambiguities this suite closed

Per Conformance.md, a vector is added whenever an ambiguity is found in the
prose, **in the same change that clarifies the prose**. Authoring this suite
found these, and the listed documents were changed:

| Ambiguity | Resolution | Vector |
| --------- | ---------- | ------ |
| Is `targets` sorted on the raw value bytes or on the escaped rendering? They differ for values containing escapes. | Raw value bytes, before escaping — Canonical-Payload.md §3 | `payload/escapes` |
| What happens to a control character with no escape in the table? §4 says "no other character is escaped", but TOML basic strings cannot carry one raw. | Not representable, therefore malformed — Canonical-Payload.md §4 | (a rejection case, not a serialization one) |
| Is Unicode normalization applied anywhere? | No; values are the exact code points parsed — Canonical-Payload.md §4 | `payload/non-ascii-literal` |
| Is `issued_at` a quoted string or a TOML datetime, and is `Z` required over `+00:00`? | A basic string, copied verbatim; `Z` — Canonical-Payload.md §2 | every payload vector |
| May `targets` or `argv` be empty? | No; at least one each — Canonical-Payload.md §2, §3 | (a rejection case) |
| How is `signature.value` base64 framed — padding, line wrapping? | RFC 4648 §4, padded, single line — Standard.md §6.1 | every `signature/` vector |
| Is `format` compared as an opaque string, and how much must it pin? | Opaque, exact equality; must pin every option affecting the patch bytes — Standard.md §3.2.2 | `payload/dirty-patch-only` |
| Standard.md §7 said a verifier *rejects* an unknown `schema`; Verification.md §7 listed an unimplemented schema version as *unverifiable*. | Unverifiable — Standard.md §7 now defers to Verification.md §7 | `verify/unknown-schema` |
| Verification.md §3.1 called a missing or empty store fail-closed while §7 called an unreadable store unverifiable, without distinguishing them. | Missing/empty answers the question (not-covered); unreadable does not (unverifiable) — Verification.md §3.1 | `verify/empty-key-store`, `verify/unreadable-store` |
| Which outcome wins when one certificate cannot be evaluated and others cover the requirement? | Covered, with the unevaluated record still reported — Verification.md §7 | `verify/unverifiable-but-covered` |
| Where does the *requirement* live in a verification vector? Conformance.md §3 put `platform` in `state.json` and named no home for targets or signature policy. | A separate `requirement.json` — Conformance.md §3 | every `verify/` vector |

## Cases beyond the required set

Conformance.md requires 16 payload cases and 11 verification cases. This suite
adds three, each marked as such in its `pins.md`:

| Case | Why |
| ---- | --- |
| `payload/dirty-tree-and-patch` | The fourth worktree shape. `dirty-tree`, `dirty-patch-only` and `clean-no-worktree` cover three; nothing else shows all three worktree keys in their fixed order. |
| `verify/unknown-schema` | Added with the Standard.md §7 clarification above. |
| `verify/unverifiable-but-covered` | Added with the Verification.md §7 precedence rule above. |

## What this suite does not cover

Stated so that nobody mistakes a gap for a guarantee:

- **Reformatting tolerance in the `verify/` group.** Every certificate there is
  in canonical form. Only `payload/escapes/received.toml` exercises
  Canonical-Payload.md §5.
- **Rejection cases as a group.** Malformed records appear only where a
  decision depends on them (`verify/dirty-no-worktree`). There is no systematic
  "these records MUST be rejected" group yet.
- **Framework-specific validity.** By construction: Verification.md §4.2 says
  there is nothing generic to test there.
- **Transport.** Nothing in [Transport.md](../Transport.md) is covered; the
  vectors start from certificates already in hand.

## The tools directory is not part of the suite

[`tools/`](../tools) holds a reference serializer, a reference verifier, a
signature regenerator, a POSIX-shell walker and a corruption demonstration.
They exist so that the vectors themselves can be checked and re-derived.

**No implementation is required to read, port or invoke any of them**, and
nothing in `tools/` is normative. Where a tool and the prose disagree, the prose
wins and the tool is a bug. `tools/walk-vectors.sh` is worth a look anyway: it
walks all three groups with nothing but POSIX shell, `jq` and `ssh-keygen`,
which is the concrete demonstration that this suite needs no
language-specific tooling.
