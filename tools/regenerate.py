#!/usr/bin/env python3
"""Re-derive every signature in the suite, and rebuild vectors/index.json.

Signed certificates live in four places: signature/<case>/signature.b64,
verify/<case>/certificates/*.toml, store/<case>/certificate.toml, and the
records inside notes/<case>/{note,expected-note,add}.txt.

NON-NORMATIVE authoring tooling. See tools/README.md.

Signatures are the one part of the suite that cannot be authored by hand, so
this script is the documented way to re-derive them. It is **idempotent**:
ed25519 is deterministic under RFC 8032 and OpenSSH's signature framing adds
nothing random, so re-running it over unchanged inputs rewrites byte-identical
files. If this script produces a diff, an input changed.

    python3 tools/regenerate.py            # rewrite in place
    python3 tools/regenerate.py --check    # fail if anything would change

Changing a vector's expected bytes is a breaking change to the standard
(Conformance.md, "Maintaining the vectors"). `--check` is what stops it
happening by accident.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import reference_serializer as rs  # noqa: E402
import ssh_sig  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VECTORS = os.path.join(ROOT, "vectors")
KEYS = os.path.join(VECTORS, "signature", "keys")

# key_id -> private key file. The key_id is the certificate's own field, so a
# certificate carries everything needed to find its signer.
KEY_FOR_ID = {
    "example-key-2026-q2": os.path.join(KEYS, "insecure-test-key"),
    "example-key-2025-q4": os.path.join(KEYS, "insecure-other-key"),
}

# Signature-vector manifest. `payload_from` names the payload vector whose
# canonical bytes are signed, so the two groups cannot drift apart.
#
#   sign_key      which private key made the signature
#   sign_ns       the namespace it was made under (the verifier always uses
#                 Standard.md §6.1's `test-certificate-v1`)
#   verify_key    the public key a consumer checks against
#   mutate        (find, replace) applied to the payload AFTER signing, so the
#                 stored signature covers the original bytes; or None
#   expect        "verify" or "fail"
SIGNATURE_VECTORS = {
    "minimal": dict(payload_from="minimal", sign_key="insecure-test-key",
                    sign_ns=ssh_sig.NAMESPACE, verify_key="insecure-test-key",
                    mutate=None, expect="verify"),
    "unicode": dict(payload_from="targets-unicode",
                    sign_key="insecure-test-key", sign_ns=ssh_sig.NAMESPACE,
                    verify_key="insecure-test-key", mutate=None,
                    expect="verify"),
    "escapes": dict(payload_from="escapes", sign_key="insecure-test-key",
                    sign_ns=ssh_sig.NAMESPACE, verify_key="insecure-test-key",
                    mutate=None, expect="verify"),
    "wrong-namespace": dict(payload_from="minimal",
                            sign_key="insecure-test-key", sign_ns="git",
                            verify_key="insecure-test-key", mutate=None,
                            expect="fail"),
    "wrong-key": dict(payload_from="minimal", sign_key="insecure-other-key",
                      sign_ns=ssh_sig.NAMESPACE,
                      verify_key="insecure-test-key", mutate=None,
                      expect="fail"),
    # One hex digit of the content id, changed after signing: still a
    # well-formed certificate, attesting to different content.
    "mutated-payload": dict(
        payload_from="minimal", sign_key="insecure-test-key",
        sign_ns=ssh_sig.NAMESPACE, verify_key="insecure-test-key",
        mutate=(b"git-tree-sha1:9f8e7d6c5b4a3928170695e4d3c2b1a099887766",
                b"git-tree-sha1:9f8e7d6c5b4a3928170695e4d3c2b1a099887767"),
        expect="fail"),
}


class Writer:
    """Writes files, or reports what would change under --check."""

    def __init__(self, check_only: bool) -> None:
        self.check_only = check_only
        self.changed: list[str] = []

    def write(self, path: str, data: bytes) -> None:
        rel = os.path.relpath(path, ROOT)
        old = None
        if os.path.exists(path):
            with open(path, "rb") as f:
                old = f.read()
        if old == data:
            return
        self.changed.append(rel)
        if self.check_only:
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)


def payload_bytes(name: str) -> bytes:
    with open(os.path.join(VECTORS, "payload", name, "canonical.txt"),
              "rb") as f:
        return f.read()


def regenerate_signature_vectors(w: Writer) -> None:
    for name, spec in SIGNATURE_VECTORS.items():
        d = os.path.join(VECTORS, "signature", name)
        data = payload_bytes(spec["payload_from"])

        # Sign the original bytes first. Mutating before signing would produce
        # a signature that covers the mutation, which verifies happily and
        # tests nothing — the bug this ordering exists to prevent.
        sign_key = os.path.join(KEYS, spec["sign_key"])
        b64 = ssh_sig.sign(data, sign_key, namespace=spec["sign_ns"])

        if spec["mutate"] is not None:
            find, replace = spec["mutate"]
            assert data.count(find) == 1, f"{name}: mutation is not unique"
            assert len(find) == len(replace)
            data = data.replace(find, replace)
        w.write(os.path.join(d, "canonical.txt"), data)
        assert ssh_sig.b64_is_canonical(b64)
        w.write(os.path.join(d, "signature.b64"), (b64 + "\n").encode("ascii"))

        pub = ssh_sig.public_key_of(os.path.join(KEYS, spec["verify_key"]))
        w.write(os.path.join(d, "key.pub"), (pub + "\n").encode("ascii"))
        w.write(os.path.join(d, "expect.txt"),
                (spec["expect"] + "\n").encode("ascii"))


def certificate_text(payload: bytes, algorithm: str, value: str) -> bytes:
    """Certificate file = canonical payload + the excluded signature block."""
    block = (f"\n[certificate.signature]\n"
             f"algorithm = {rs.escape(algorithm)}\n"
             f"value = {rs.escape(value)}\n")
    return payload + block.encode("utf-8")


def resign_certificates(w: Writer) -> None:
    """Re-sign every verify-vector certificate that names a key.

    The certificate file itself is the source: its payload is reconstructed
    from the parsed fields (Canonical-Payload.md §5), signed, and written back
    with a fresh signature block. Certificates without a `key_id` are left
    exactly as authored — that includes the deliberately malformed ones and
    the earlier-draft record, which has no payload under this revision.
    """
    root = os.path.join(VECTORS, "verify")
    for case in sorted(os.listdir(root)):
        cert_dir = os.path.join(root, case, "certificates")
        if not os.path.isdir(cert_dir):
            continue
        for fname in sorted(os.listdir(cert_dir)):
            if not fname.endswith(".toml"):
                continue
            path = os.path.join(cert_dir, fname)
            with open(path, "rb") as f:
                doc = tomllib.load(f)
            if doc.get("schema") != rs.SCHEMA:
                # Authored literally for the unknown-schema cases: there is no
                # canonical payload for a version this repository does not
                # define, so there is nothing to sign.
                continue
            key_id = doc.get("certificate", {}).get("key_id")
            if key_id is None:
                continue
            if key_id not in KEY_FOR_ID:
                raise SystemExit(f"{path}: no signing key for {key_id!r}")
            payload = rs.serialize(rs.fields_from_document(doc))
            b64 = ssh_sig.sign(payload, KEY_FOR_ID[key_id])
            w.write(path, certificate_text(payload, "ed25519", b64))


_SIG_HEADER = re.compile(
    rb"^[ \t]*\[[ \t]*certificate[ \t]*\.[ \t]*signature[ \t]*\][ \t]*\r?$",
    re.MULTILINE)
_SIG_VALUE = re.compile(
    rb"^([ \t]*value[ \t]*=[ \t]*)(\"[^\"\r\n]*\"|'[^'\r\n]*')",
    re.MULTILINE)


def resign_store_certificates(w: Writer) -> None:
    """Re-sign every store-vector certificate that carries a signature block.

    Unlike the verify group, the bytes signed are the case's own hand-derived
    `canonical.txt`, never a serializer's output, and the certificate file is
    edited in place: only the string after `value =` in its
    `[certificate.signature]` table changes, so a deliberately non-canonical
    rendering (CRLF, reordered tables, literal strings) stays exactly as it was
    authored. A block with an empty `algorithm` is the unsigned form
    (Canonical-Payload.md §6) and is left alone.
    """
    root = os.path.join(VECTORS, "store")
    for case in sorted(os.listdir(root)):
        d = os.path.join(root, case)
        path = os.path.join(d, "certificate.toml")
        if not os.path.isfile(path):
            continue
        with open(path, "rb") as f:
            text = f.read()
        doc = tomllib.loads(text.decode("utf-8"))
        cert = doc.get("certificate", {})
        sig = cert.get("signature")
        if not sig or not sig.get("algorithm"):
            continue
        key_id = cert.get("key_id")
        if key_id not in KEY_FOR_ID:
            raise SystemExit(f"{path}: no signing key for {key_id!r}")
        if sig["algorithm"] != "ed25519":
            raise SystemExit(f"{path}: cannot sign {sig['algorithm']!r}")
        with open(os.path.join(d, "canonical.txt"), "rb") as f:
            payload = f.read()
        b64 = ssh_sig.sign(payload, KEY_FOR_ID[key_id])
        assert ssh_sig.b64_is_canonical(b64)

        headers = list(_SIG_HEADER.finditer(text))
        assert len(headers) == 1, f"{path}: expected one signature header"
        start = headers[0].end()
        # The block ends at the next table header, or at the end of the file.
        nxt = re.compile(rb"^[ \t]*\[", re.MULTILINE).search(text, start)
        end = nxt.start() if nxt else len(text)
        block = text[start:end]
        values = list(_SIG_VALUE.finditer(block))
        assert len(values) == 1, f"{path}: expected one signature value"
        m = values[0]
        quote = m.group(2)[:1]
        new_block = (block[:m.start(2)] + quote + b64.encode("ascii") + quote
                     + block[m.end(2):])
        w.write(path, text[:start] + new_block + text[end:])


NOTE_DELIMITER = b"# --- test-certificate ---\n"   # Transport.md §3.1
_NOTE_BLOCK = re.compile(
    rb"\n\[certificate\.signature\]\nalgorithm = \"ed25519\"\n"
    rb"value = \"[^\"\n]*\"\n\Z")
_NOTE_KEY_ID = re.compile(rb"^key_id = \"([^\"\n]*)\"$", re.MULTILINE)


def resign_note_records(w: Writer) -> None:
    """Re-sign every signed record in the notes group.

    Each note-shaped file (note.txt, expected-note.txt, add.txt) is split on
    the Transport.md §3.1 delimiter line; a piece ending in a signature table
    is signed over the bytes before that table — the hand-derived payload, not
    a serializer's output — and only the `value` string is rewritten. Pieces
    without a table, and the deliberately corrupt ones, are left alone.
    """
    root = os.path.join(VECTORS, "notes")
    if not os.path.isdir(root):
        return
    for case in sorted(os.listdir(root)):
        for fname in ("note.txt", "expected-note.txt", "add.txt"):
            path = os.path.join(root, case, fname)
            if not os.path.isfile(path):
                continue
            with open(path, "rb") as f:
                text = f.read()
            # add.txt is one record with no delimiter in front of it.
            framed = fname != "add.txt"
            pieces = (re.split(rb"(?:^|(?<=\n))" + re.escape(NOTE_DELIMITER),
                               text) if framed else [text])
            out = []
            for piece in pieces:
                m = _NOTE_BLOCK.search(piece)
                if m:
                    payload = piece[:m.start()]
                    ids = _NOTE_KEY_ID.findall(payload)
                    assert len(ids) == 1, f"{path}: signed record, no key_id"
                    key_id = ids[0].decode()
                    if key_id not in KEY_FOR_ID:
                        raise SystemExit(f"{path}: no signing key for {key_id!r}")
                    b64 = ssh_sig.sign(payload, KEY_FOR_ID[key_id])
                    assert ssh_sig.b64_is_canonical(b64)
                    piece = (payload + b"\n[certificate.signature]\n"
                             b"algorithm = \"ed25519\"\nvalue = \""
                             + b64.encode("ascii") + b"\"\n")
                out.append(piece)
            w.write(path, NOTE_DELIMITER.join(out) if framed else out[0])


def rebuild_index(w: Writer) -> None:
    """A directory listing with each case's one-line purpose.

    Lets a walker notice that a case has gone missing, which a plain directory
    scan cannot: a vector that is not there simply is not tested.
    """
    index: dict[str, object] = {
        "schema": "test-certificate-vectors.v1",
        "namespace": ssh_sig.NAMESPACE,
        "groups": {},
    }
    for group in ("payload", "signature", "content", "verify", "store",
                  "notes"):
        cases = []
        for name in sorted(os.listdir(os.path.join(VECTORS, group))):
            d = os.path.join(VECTORS, group, name)
            if not os.path.isdir(d) or name == "keys":
                continue
            cases.append({"name": name, "pins": first_pin_line(d)})
        index["groups"][group] = cases
    w.write(os.path.join(VECTORS, "index.json"),
            (json.dumps(index, indent=2, ensure_ascii=False) + "\n")
            .encode("utf-8"))


def first_pin_line(case_dir: str) -> str:
    """The `**Pins:** …` sentence from a case's pins.md, as one line."""
    path = os.path.join(case_dir, "pins.md")
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    marker = "**Pins:**"
    if marker not in text:
        return ""
    tail = text.split(marker, 1)[1]
    para = tail.split("\n\n", 1)[0]
    return " ".join(para.split()).rstrip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="report what would change; write nothing")
    args = ap.parse_args()

    w = Writer(args.check)
    regenerate_signature_vectors(w)
    resign_certificates(w)
    resign_store_certificates(w)
    resign_note_records(w)
    rebuild_index(w)

    if not w.changed:
        print("up to date")
        return 0
    verb = "would rewrite" if args.check else "rewrote"
    for rel in w.changed:
        print(f"{verb}: {rel}")
    return 1 if args.check else 0


if __name__ == "__main__":
    raise SystemExit(main())
