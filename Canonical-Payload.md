# Canonical Payload

The canonical payload is the **exact byte sequence** a signature covers. It is
the most unforgiving part of this standard: two implementations that disagree
here by a single byte produce signatures neither can verify, while agreeing
perfectly about everything else.

Everything below is normative.

## 1. Encoding

- The payload is **UTF-8**, with no byte-order mark.
- Line endings are **LF** (`\n`). Never CRLF, on any platform.
- The payload **ends with a newline**.
- No trailing whitespace on any line.

## 2. Structure

The payload is the `schema` line and the `[certificate]` table, in the exact
order below, and **nothing else**. The signature block is excluded — it cannot
cover itself.

```
schema = "test-certificate.v1"

[certificate]
project = "<project>"
repo = "<repo>"
commit = "<commit>"
platform = "<platform>"
targets = ["<t1>", "<t2>"]
result = "<result>"
issued_at = "<rfc3339>"
issuer = "<issuer>"
key_id = "<key-id>"

[certificate.environment]
method = "<method>"
value = "<value>"
```

Rules:

1. **Key order is fixed** exactly as shown. It is not alphabetical and MUST NOT
   be re-sorted.
2. **One space either side of `=`.**
3. `key_id` is **omitted entirely** when the certificate is unsigned — not
   emitted empty. An omitted key and an empty key are different payloads.
4. The `[certificate.environment]` table is separated from the body by exactly
   one blank line, and is always present (`method = "none"` when unbound).
5. Exactly one blank line follows the `schema` line. No other blank lines.

## 3. `targets` is sorted

`targets` MUST be serialized in **ascending byte order** (a plain lexicographic
sort over the UTF-8 bytes), not in the order the targets ran.

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
predates this standard. Two differences are **breaking** and require migration;
they are recorded here so nobody assumes byte-compatibility that does not exist.

| | reprobuild today | This standard |
| --- | --- | --- |
| Schema id | `reprobuild.test-certificate.v1` | `test-certificate.v1` |
| Environment | flat `lock = "blake3:…"` in `[certificate]` | `[certificate.environment]` with `method` + `value` |
| `targets` order | as observed/run | sorted, deduplicated |
| Signature namespace | `reprobuild-test-certificate-v1` | `test-certificate-v1` |

The `targets` change is the subtle one: it is not merely a rename, it changes
the signed bytes for any certificate whose targets did not happen to run in
sorted order. Certificates issued before migration cannot be verified under this
standard, and MUST be re-issued rather than translated — translating them would
mean re-signing a payload the original signer never saw.
