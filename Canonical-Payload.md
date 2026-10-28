# Canonical Payload

The canonical payload is the **exact byte sequence** a signature covers. It is
the most unforgiving part of this standard: two implementations that disagree
here by a single byte produce signatures neither can verify, while agreeing
perfectly about everything else.

Everything below is normative. Every rule here is pinned by a byte-exact vector
in [`vectors/payload/`](./vectors/README.md); when the prose and a vector
appear to disagree, that is a defect worth reporting, not a choice to make.

## 1. Encoding

- The payload is **UTF-8**, with no byte-order mark.
- Line endings are **LF** (`\n`). Never CRLF, on any platform.
- The payload **ends with a newline**.
- No trailing whitespace on any line.

## 2. Structure

The payload is the `schema` line, the `[certificate]` table, the
`[certificate.vcs]` table and the `[[certificate.command]]` entries, in the exact
order below, and **nothing else**. The signature block is excluded — it cannot
cover itself.

```
schema = "test-certificate.v1"

[certificate]
framework = "<framework>"
project = "<project>"
platform = "<platform>"
targets = ["<t1>", "<t2>"]
result = "<result>"
issued_at = "<rfc3339>"
issuer = "<issuer>"
key_id = "<key-id>"

[certificate.vcs]
repo = "<repo>"
paths = ["<p1>", "<p2>"]
content = "<algorithm>:<digest>"
untracked = false
base = "<commit>"

[[certificate.command]]
argv = ["<arg0>", "<arg1>"]
```

Rules:

1. **Key order is fixed** exactly as shown. It is not alphabetical and MUST NOT
   be re-sorted.
2. **One space either side of `=`.**
3. `key_id` is **omitted entirely** when the certificate is unsigned — not
   emitted empty. An omitted key and an empty key are different payloads.
4. `untracked` is a TOML boolean, emitted as bare `true` / `false`, never as a
   quoted string.
5. Tables are separated by exactly one blank line. Exactly one blank line follows
   the `schema` line. No other blank lines.
6. `[[certificate.command]]` entries appear **in execution order**, which is part
   of the claim and MUST NOT be sorted. Each entry is preceded by one blank line.
   At least one entry is required.
7. `argv` arrays are serialized like `targets` (§3) but **are never sorted or
   deduplicated** — an argument vector is ordered by nature, and repeated
   arguments are meaningful. Each entry carries at least `argv[0]`; an empty
   `argv` describes no command and MUST NOT be emitted. An empty *argument*,
   by contrast, is an ordinary argument and is emitted as `""`.
8. `paths` is sorted and deduplicated like `targets`, and is **omitted entirely**
   when the claim covers the whole repository — never emitted as `[]`. An omitted
   key and an empty array are different payloads.
9. `content` is emitted **verbatim**, as the self-describing string
   [Content-Id §1](./Content-Id.md#1-form) defines. The serializer does not
   split, re-case or validate it; a malformed content id is the verifier's
   finding ([Verification §4.1.1](./Verification.md#411-matching-content)), and
   rewriting it here would sign a value the producer never computed.
10. `base` is **omitted entirely** when absent — never emitted empty — and,
    being informational, is still covered by the signature like every other
    field. It is the last key of `[certificate.vcs]`.
11. **Every value is a quoted string except `untracked`.** In particular
    `issued_at` is a TOML *basic string*, never a bare TOML datetime, and its
    characters are copied verbatim — nothing re-formats the timestamp.
    Since RFC 3339 spells the same instant as both `Z` and `+00:00`, and the two
    are different bytes and therefore different signatures, producers MUST use
    the `Z` form.

## 3. `targets` is sorted

`targets` MUST be serialized in **ascending byte order** (a plain lexicographic
sort over the UTF-8 bytes), not in the order the targets ran. It MUST contain at
least one target: a certificate covering nothing supports no claim, and
`targets = []` is not a payload this standard defines.

Three things the sort is **not**, each of which is some language's default:

- It is not **locale collation**. Collation folds case and accents, so `Zebra`
  would sort next to `zebra` and `äpple` next to `apple`.
- It is not **UTF-16 code-unit order**. A character above the BMP encodes as a
  surrogate pair beginning `D800`–`DBFF`, which compares *below* `E000`–`FFFF`,
  reversing the byte order for those pairs.
- It is not a sort of the **escaped rendering**. Escaping happens after
  sorting, over values already in order. The two differ whenever a value
  contains an escapable character: a value containing TAB sorts by `09`, while
  its rendering `\t` would sort by `5C`.

Equivalently: sort by the raw UTF-8 bytes of the value, then escape (§4), then
join.

The array form is `["a", "b"]` — an inline array, elements separated by a comma
and a single space, no trailing comma, no spaces inside the brackets.

This matters more than it looks. Run order is an accident of scheduling: the
same suite, the same commit, the same result can produce a different order on
the next run, and with it a different payload and a different signature for an
identical claim. Sorting makes the payload a function of *what was attested*
rather than of *how it happened to be scheduled*, which is what lets a verifier
compare, cache and deduplicate certificates.

Duplicate target names MUST be removed before sorting.

## 4. String escaping

Values are TOML basic strings. Only these escapes are produced:

| Character | Escape |
| --------- | ------ |
| `\` | `\\` |
| `"` | `\"` |
| newline | `\n` |
| carriage return | `\r` |
| tab | `\t` |
| backspace | `\b` |
| form feed | `\f` |

No other character is escaped — in particular, non-ASCII characters are emitted
literally as UTF-8, never as `\uXXXX`. A verifier MUST accept `\uXXXX` on input
for interoperability, but MUST NOT produce it when re-serializing for signature
checking.

**The table above is the authority.** A character absent from it is emitted
literally, and no other escape is ever produced.

These seven are also JSON's *mandatory* escapes, which is convenient but is not
a licence to hand the job to a JSON encoder unchecked. JSON additionally
**permits** `\/`, and `/` is an ordinary character here that appears in almost
every certificate: `platform` is `os/arch`, and every multi-segment entry in
`paths` contains one. An encoder that escapes it produces `linux\/amd64`, which
is valid JSON, invalid here, and a different signature. A JSON string encoder
may therefore be reused only if it emits non-ASCII literally **and** leaves `/`
alone. Where an encoder and this table disagree, the table wins.

**Other control characters are not representable.** A TOML basic string cannot
carry a raw control character, and this table defines no escape for the ones it
omits, so a value containing any character in `U+0000`–`U+001F` other than the
five above, or `U+007F`, has no canonical form. Producers MUST NOT emit one; a
verifier encountering one MUST reject the record as malformed rather than invent
an escape for it. Inventing one would be a repair, which §5 forbids.

**No Unicode normalization is applied.** After reading physical newlines as
§5 requires, values are emitted as the exact sequence of code points parsed.
A precomposed `é` (`U+00E9`) and a decomposed `e` +
`U+0301` are different values: they are not folded together, not deduplicated
against each other in `targets`, and they sort by their bytes like anything
else. Normalizing would silently change what a signature covers.

## 5. Verifying against the payload

Before reconstructing the payload, a verifier MUST reject unknown keys and
tables throughout the record as malformed, including the root and the
signature block ([Standard §3.4](./Standard.md#34-unknown-keys-and-tables)).
Excluding the signature block from the payload does not exempt it from schema
validation. No payload is defined for a record rejected by this rule.

A verifier MUST reconstruct the canonical payload **from the parsed fields**,
not by slicing the received file. A received file may differ from canonical form
in whitespace, key order or escaping while parsing to identical values;
signature checking has to happen against the canonical rendering of those
values, or a cosmetically reformatted certificate would fail against its own
valid signature.

**Physical newlines in multi-line strings MUST be read as LF**, on every
platform, whether the received document uses LF or CRLF. This applies to
both TOML multi-line basic strings and multi-line literal strings, including
strings inside arrays. TOML's permission to choose a platform-specific newline
normalization does not apply to this standard. TOML's rules for trimming an
initial newline and, in multi-line basic strings, line-ending backslash
continuations still apply.

This rule concerns physical newlines in the source, **not characters produced
by escapes**. For example, `\r` and `\u000D` still produce CR, and `\r\n`
still produces CR followed by LF; §4 emits them as `\r` and `\r\n`,
respectively. An implementation MUST preserve this distinction while parsing;
replacing CRLF in all decoded string values would silently change escaped
values and is forbidden. A parser that already reads physical newlines as LF
needs no additional conversion.

Equally, a verifier MUST NOT "repair" a payload into validity: if the canonical
rendering of the parsed fields does not verify, the certificate does not verify.

## 6. Unsigned certificates

An unsigned certificate MAY omit the `[certificate.signature]` block entirely,
or MAY emit it with empty `algorithm` and `value`. Both mean unsigned, and a
verifier MUST treat them identically.

The empty-block form exists because it keeps the on-disk shape stable between an
unsigned record and the signed record it later becomes. Neither form affects the
canonical payload, since the signature block is excluded from it in both cases.

## 7. Revisions and known divergences

### 7.1 The 2026-10-09 revision: content replaces commit

v1 was revised in place while still a draft: `[certificate.vcs]` no longer names
a `commit` with a `clean` flag and an optional `worktree` table, but carries a
required `content` id and an optional, informational `base`
([Standard §2.1](./Standard.md#21-content-not-commit)).

| | Earlier draft | This revision |
| --- | --- | --- |
| Binding | `commit`, `clean`, and `[certificate.vcs.worktree]` (`tree`, `format`, `patch_digest`) when dirty | `content`, required, self-describing ([Content-Id](./Content-Id.md)) |
| Commit | `commit`, required, matched exactly | `base`, optional, never matched |
| Key order | `repo`, `commit`, `paths`, `clean`, `untracked` | `repo`, `paths`, `content`, `untracked`, `base` |

The schema id did not change, so the two shapes share `test-certificate.v1`. A
record in the earlier shape lacks the required `content` field and is therefore
**decidably invalid** under this revision (Standard §7) — not covered, never
unverifiable. That is the intended outcome: the remedy is to run the tests
again, which issues a record in the current shape. Earlier-draft records MUST
NOT be translated into the new shape, for the reason given for reprobuild
below — the translation would be a payload its signer never saw.

`ct test` is the producer this affects: it shipped earlier-draft clean-tree
records before the revision.

### 7.2 reprobuild's migrations

reprobuild is the first conforming producer, and its original implementation
predates this standard. It has migrated once and owes a second migration; both
are recorded here so nobody assumes byte-compatibility that does not exist.

**First migration (done).** reprobuild
moved from its own format to the earlier draft of `test-certificate.v1`:

| | reprobuild before the first migration | Earlier draft |
| --- | --- | --- |
| Schema id | `reprobuild.test-certificate.v1` | `test-certificate.v1` |
| Framework id | absent | `framework` field, required |
| Repo state | `repo` + `commit` flat, plus `lock = "blake3:…"` | `[certificate.vcs]` with `repo`, `commit`, `clean`, `untracked`; no lock digest |
| Commands | not recorded | `[[certificate.command]]`, at least one, required |
| `targets` order | as observed/run | sorted, deduplicated |
| Signature namespace | `reprobuild-test-certificate-v1` | `test-certificate-v1` |

**Second migration (owed).** As of
reprobuild `a6522604` it still issues and matches earlier-draft records bound to
a commit. Moving to the content binding is §7.1 for reprobuild: its records are
re-issued, never translated.

Two of these deserve comment.

**The lock digest is gone, not moved.** reprobuild's `repro.lock` is tracked
per repo, so `vcs.content` already binds it: a verifier that wants to check the
lock resolves it from the content under evaluation itself. The digest field
was carrying information the content already implied, at the cost of making the
format ecosystem-specific.

**`targets` sorting changes the signed bytes** for any certificate whose targets
did not happen to run in sorted order. Certificates issued before migration
cannot be verified under this standard and MUST be **re-issued**, never
translated — translating would mean re-signing a payload the original signer
never saw.
