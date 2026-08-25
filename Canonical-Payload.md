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
commit = "<commit>"
paths = ["<p1>", "<p2>"]
clean = true
untracked = false

[certificate.vcs.worktree]
tree = "<content-id>"
format = "<patch-format>"
patch_digest = "<algo>:<hex>"

[[certificate.command]]
argv = ["<arg0>", "<arg1>"]
```

Rules:

1. **Key order is fixed** exactly as shown. It is not alphabetical and MUST NOT
   be re-sorted.
2. **One space either side of `=`.**
3. `key_id` is **omitted entirely** when the certificate is unsigned — not
   emitted empty. An omitted key and an empty key are different payloads.
4. `clean` and `untracked` are TOML booleans, emitted as bare `true` / `false`,
   never as quoted strings.
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
9. `[certificate.vcs.worktree]` is **present only when `clean = false`**, follows
   the `[certificate.vcs]` table after one blank line, and omits any of its three
   keys that are absent.
10. **Every value is a quoted string except `clean` and `untracked`.** In
    particular `issued_at` is a TOML *basic string*, never a bare TOML datetime,
    and its characters are copied verbatim — nothing re-formats the timestamp.
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

**No normalization is applied.** Values are emitted as the exact sequence of
code points parsed. A precomposed `é` (`U+00E9`) and a decomposed `e` +
`U+0301` are different values: they are not folded together, not deduplicated
against each other in `targets`, and they sort by their bytes like anything
else. Normalizing would silently change what a signature covers.

## 5. Verifying against the payload

A verifier MUST reconstruct the canonical payload **from the parsed fields**,
not by slicing the received file. A received file may differ from canonical form
in whitespace, key order or escaping while parsing to identical values;
signature checking has to happen against the canonical rendering of those
values, or a cosmetically reformatted certificate would fail against its own
valid signature.

Equally, a verifier MUST NOT "repair" a payload into validity: if the canonical
rendering of the parsed fields does not verify, the certificate does not verify.

## 6. Unsigned certificates

An unsigned certificate MAY omit the `[certificate.signature]` block entirely,
or MAY emit it with empty `algorithm` and `value`. Both mean unsigned, and a
verifier MUST treat them identically.

The empty-block form exists because it keeps the on-disk shape stable between an
unsigned record and the signed record it later becomes. Neither form affects the
canonical payload, since the signature block is excluded from it in both cases.

## 7. Known divergences from reprobuild's current implementation

reprobuild is the first conforming producer, and its shipped implementation
predates this standard. The differences below are **breaking** and require
migration; they are recorded here so nobody assumes byte-compatibility that does
not exist.

| | reprobuild today | This standard |
| --- | --- | --- |
| Schema id | `reprobuild.test-certificate.v1` | `test-certificate.v1` |
| Framework id | absent | `framework` field, required |
| Repo state | `repo` + `commit` flat, plus `lock = "blake3:…"` | `[certificate.vcs]` with `repo`, `commit`, `clean`, `untracked`; no lock digest |
| Commands | not recorded | `[[certificate.command]]`, at least one, required |
| `targets` order | as observed/run | sorted, deduplicated |
| Signature namespace | `reprobuild-test-certificate-v1` | `test-certificate-v1` |

Two of these deserve comment.

**The lock digest is gone, not moved.** reprobuild's `repro.lock` is committed
per repo, so `vcs.commit` already binds it: a verifier that wants to check the
lock resolves it at that commit itself. The digest field was carrying
information the commit already implied, at the cost of making the format
ecosystem-specific.

**`targets` sorting changes the signed bytes** for any certificate whose targets
did not happen to run in sorted order. Certificates issued before migration
cannot be verified under this standard and MUST be **re-issued**, never
translated — translating would mean re-signing a payload the original signer
never saw.
