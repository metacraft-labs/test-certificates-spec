#!/usr/bin/env python3
"""Check the vector suite against the reference implementations.

NON-NORMATIVE. See tools/README.md. This checks the *vectors*; it is not a
conformance harness, and no implementation of the standard is expected to run
it. An implementation walks `vectors/` with its own thin walker
(Conformance.md, "Using the suite"). `tools/walk-vectors.sh` shows what such a
walker looks like with no language-specific tooling at all.

    python3 tools/check.py            # run everything
    python3 tools/check.py payload    # one group

Groups:
    payload    every canonical.txt is byte-exact under the reference
               serializer, and every `received.toml` parses to the same bytes
    signature  every vector verifies or fails exactly as expect.txt says
    content    every content id in expected.json is reproduced from
               entries.json by the reference content-id implementation, which
               builds git objects by hand rather than asking git
    verify     every vector yields its expected three-valued outcome, and the
               gaps it names
    store      every expected-path.txt is the Transport.md §2.2 path derived
               from certificate.toml: the content id split at its first `:`,
               and the SHA-256 of the payload rebuilt from the parsed fields
    notes      every note.txt splits, per Transport.md §3.1, into the records
               and skipped pieces expected.json lists; every writer case's
               expected-note.txt is what adding add.txt to note.txt produces
    index      vectors/index.json matches what is on disk
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tomllib
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import reference_content_id as cid  # noqa: E402
import reference_serializer as rs  # noqa: E402
import reference_verifier as rv  # noqa: E402
import ssh_sig  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VECTORS = os.path.join(ROOT, "vectors")

# The cases Conformance.md requires, spelled out here so that deleting a
# directory is a failure rather than a silent reduction in coverage.
REQUIRED_PAYLOAD = [
    "minimal", "signed", "targets-unsorted-input", "targets-duplicates",
    "targets-single", "targets-unicode", "escapes", "non-ascii-literal",
    "multiple-commands", "argv-duplicates", "argv-empty-string", "scoped",
    "unscoped", "base-present", "content-manifest", "untracked-true",
    "crlf-multiline",
]
REQUIRED_CONTENT = [
    "order-independent", "byte-order", "modes", "scope-keeps-paths",
    "empty-scope", "non-ascii-path", "sha256-object-format",
]
REQUIRED_VERIFY = [
    "coverage-union", "wrong-platform", "other-framework", "revoked-key",
    "empty-key-store", "unsigned-required", "content-matches-other-base",
    "content-differs", "content-malformed", "content-unknown-algorithm",
    "earlier-draft-record", "scope-too-narrow", "unreadable-store",
]
REQUIRED_STORE = [
    "unsigned", "signed", "signed-non-canonical",
    "signed-non-canonical-no-block", "manifest-content", "scoped",
]

REQUIRED_NOTES = [
    "single-unsigned", "signed-and-unsigned", "escaped-newline",
    "corrupt-middle", "foreign-preamble", "appended",
    "signed-replaces-unsigned", "duplicate-not-added",
    "unsigned-copy-not-added", "signed-copy-not-replaced", "signed-duplicate-protects",
]

# Each store case's canonical.txt is a copy of a hand-derived payload vector,
# named in its pins.md. Checked byte for byte so the two cannot drift apart.
STORE_PAYLOAD_SOURCE = {
    "unsigned": "minimal",
    "unsigned-empty-block": "minimal",
    "signed": "signed",
    "signed-non-canonical": "signed",
    "signed-non-canonical-no-block": "signed",
    "manifest-content": "content-manifest",
    "scoped": "scoped",
}

# key_id -> the published public key a store certificate is verified against.
STORE_KEYS = {
    "example-key-2026-q2": os.path.join(VECTORS, "signature", "keys",
                                        "insecure-test-key.pub"),
}

GROUPS_ON_DISK = ("payload", "signature", "content", "verify", "store",
                  "notes")


class Results:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.checks = 0

    def check(self, ok: bool, label: str, detail: str = "") -> None:
        self.checks += 1
        if ok:
            print(f"  ok    {label}")
        else:
            print(f"  FAIL  {label}" + (f"\n          {detail}" if detail else ""))
            self.failures.append(label)


def cases(group: str) -> list[str]:
    d = os.path.join(VECTORS, group)
    return sorted(n for n in os.listdir(d)
                  if os.path.isdir(os.path.join(d, n)) and n != "keys")


def check_payload(r: Results) -> None:
    print("payload: canonical.txt is byte-exact under the reference serializer")
    present = cases("payload")
    missing = [c for c in REQUIRED_PAYLOAD if c not in present]
    r.check(not missing, f"all {len(REQUIRED_PAYLOAD)} required cases present",
            f"missing: {missing}")
    for name in present:
        d = os.path.join(VECTORS, "payload", name)
        with open(os.path.join(d, "canonical.txt"), "rb") as f:
            want = f.read()
        try:
            got = rs.serialize_file(os.path.join(d, "fields.json"))
        except rs.NotCanonical as exc:
            r.check(False, f"payload/{name}", f"serializer refused: {exc}")
            continue
        detail = ""
        if got != want:
            detail = f"first difference at byte {first_diff(got, want)}"
        r.check(got == want, f"payload/{name}", detail)

        # §1 invariants, checked directly against the bytes rather than
        # against the serializer, so a serializer bug cannot hide them.
        r.check(want.endswith(b"\n") and b"\r" not in want
                and not want.startswith(b"\xef\xbb\xbf")
                and not any(line.rstrip() != line
                            for line in want.decode("utf-8").split("\n")),
                f"payload/{name} §1 encoding invariants")

        received = os.path.join(d, "received.toml")
        if os.path.exists(received):
            got = rs.canonical_from_toml(received)
            r.check(got == want, f"payload/{name} received.toml -> canonical",
                    "a non-canonical rendering of the same values must "
                    "reconstruct to the same payload (Canonical-Payload.md §5)")


    # Pin the reason for crlf-multiline independently of the serializer: a
    # canonical-only case or a rewritten LF input would no longer test §5.
    received = os.path.join(VECTORS, "payload", "crlf-multiline",
                            "received.toml")
    r.check(os.path.isfile(received),
            "payload/crlf-multiline has the required received.toml")
    if os.path.isfile(received):
        with open(received, "rb") as f:
            raw = f.read()
        r.check(b'"""\r\nx\r\ny"""' in raw
                and b"'''\r\nx\r\ny'''" in raw
                and b"\r\n" in raw
                and b"\n" not in raw.replace(b"\r\n", b""),
                "payload/crlf-multiline uses physical CRLF in both string styles")
        cert = tomllib.loads(raw.decode("utf-8"))["certificate"]
        r.check(cert["project"] == cert["issuer"] == "x\ny",
                "payload/crlf-multiline physical newlines read as LF")
        r.check(b'"a\\rb"' in raw and b'"""a\\u000Db"""' in raw
                and b'"""a\\r\\nb"""' in raw
                and cert["command"][0]["argv"]
                == ["example-test", "a\rb", "a\rb", "a\r\nb"],
                "payload/crlf-multiline preserves escaped CR and CRLF")


def first_diff(a: bytes, b: bytes) -> int:
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return min(len(a), len(b))


def check_content(r: Results) -> None:
    print("content: every content id is reproduced from entries.json")
    present = cases("content")
    missing = [c for c in REQUIRED_CONTENT if c not in present]
    r.check(not missing, f"all {len(REQUIRED_CONTENT)} required cases present",
            f"missing: {missing}")
    algorithms = set()
    for name in present:
        d = os.path.join(VECTORS, "content", name)
        entries = cid.load_entries(os.path.join(d, "entries.json"))
        with open(os.path.join(d, "expected.json"), encoding="utf-8") as f:
            expected = json.load(f)
        for e in expected:
            algorithms.add(e["algorithm"])
            got = cid.compute(entries, e["algorithm"], e["paths"])
            scope = "whole repo" if e["paths"] is None else e["paths"]
            r.check(got == e["id"], f"content/{name} {e['algorithm']} {scope}",
                    f"got {got}")
            r.check(cid.parse(e["id"])[0] == e["algorithm"],
                    f"content/{name} id is well-formed and names its algorithm")
    r.check(algorithms == set(cid.DIGEST_LENGTH),
            "every algorithm in Content-Id.md §4 is exercised",
            f"saw {sorted(algorithms)}")
    pinned_facts(r)


def pinned_facts(r: Results) -> None:
    """The facts the content cases' pins.md files claim, asserted directly.

    A vector whose expected ids are right but whose stated reason is false
    teaches the wrong lesson, so the reasons are checked too.
    """
    def load(name):
        return cid.load_entries(os.path.join(VECTORS, "content", name,
                                             "entries.json"))

    # byte-order: `a.b` < `a/b` < `a0` on raw bytes, which is NOT what a walk
    # sorting each directory's names alone produces (it reaches `a/b` first).
    entries = load("byte-order")
    order = [p for p, _, _ in sorted(entries, key=lambda e: e[0])]
    r.check(order == [b"a.b", b"a/b", b"a0"],
            "content/byte-order: a.b sorts before a/b, which sorts before a0",
            f"{order}")
    r.check([p for p, _, _ in entries] != order,
            "content/byte-order: entries.json is not already in byte order")

    # order-independent: same ids whatever order the entries arrive in.
    entries = load("order-independent")
    for alg in ("git-tree-sha1", "manifest-v1-sha256"):
        r.check(cid.compute(entries, alg, None)
                == cid.compute(list(reversed(entries)), alg, None)
                == cid.compute(sorted(entries), alg, None),
                f"content/order-independent: {alg} ignores input order")
    r.check([p for p, _, _ in entries] != sorted(p for p, _, _ in entries),
            "content/order-independent: entries.json is out of order")

    # scope-keeps-paths: the scoped id is not the id of the subtree object,
    # and `src/db` does not take in `src/dbx`.
    entries = load("scope-keeps-paths")
    scoped = cid.compute(entries, "git-tree-sha1", ["src/db"])
    sub = [(p[len(b"src/db/"):], m, c) for p, m, c in entries
           if p.startswith(b"src/db/")]
    subtree = "git-tree-sha1:" + cid.git_tree(sub, "sha1")
    r.check(scoped != subtree,
            "content/scope-keeps-paths: scoped id is not the subtree id")
    r.check(scoped != cid.compute(entries, "git-tree-sha1", ["lib/db"]),
            "content/scope-keeps-paths: identical subtrees at different "
            "paths have different scoped ids")
    r.check(not any(cid.in_scope(p, ["src/db"]) for p, _, _ in entries
                    if p.startswith(b"src/dbx/")),
            "content/scope-keeps-paths: src/db excludes src/dbx")

    # empty-scope: the empty tree, and the digest of no records.
    entries = load("empty-scope")
    r.check(cid.compute(entries, "git-tree-sha1", ["src/d"])
            == "git-tree-sha1:4b825dc642cb6eb9a060e54bf8d69288fbee4904"
            and cid.compute(entries, "manifest-v1-sha256", ["src/d"])
            == "manifest-v1-sha256:" + hashlib.sha256(b"").hexdigest(),
            "content/empty-scope: src/d matches nothing, not src/db")

    # non-ascii-path: the precomposed and decomposed names are two files.
    entries = load("non-ascii-path")
    r.check(len({unicodedata.normalize("NFC", p.decode()) for p, _, _ in
                 entries}) < len(entries),
            "content/non-ascii-path: two paths differ only in normalization")

    # sha256-object-format: same entries as order-independent; the manifest
    # does not depend on the object format, the git tree id does.
    with open(os.path.join(VECTORS, "content", "sha256-object-format",
                           "entries.json"), "rb") as a, \
         open(os.path.join(VECTORS, "content", "order-independent",
                           "entries.json"), "rb") as b:
        r.check(a.read() == b.read(),
                "content/sha256-object-format uses order-independent's entries")


def check_signature(r: Results) -> None:
    print("signature: each vector verifies, or fails, as expect.txt says")
    saw_failing = False
    for name in cases("signature"):
        d = os.path.join(VECTORS, "signature", name)
        with open(os.path.join(d, "canonical.txt"), "rb") as f:
            payload = f.read()
        with open(os.path.join(d, "key.pub"), encoding="ascii") as f:
            pub = f.read().strip()
        with open(os.path.join(d, "signature.b64"), encoding="ascii") as f:
            b64 = f.read().strip()
        with open(os.path.join(d, "expect.txt"), encoding="ascii") as f:
            expect = f.read().strip()
        saw_failing = saw_failing or expect == "fail"

        r.check(ssh_sig.b64_is_canonical(b64),
                f"signature/{name} signature.b64 is single-line padded base64")
        ok, detail = ssh_sig.verify(payload, pub, b64)
        r.check(ok == (expect == "verify"), f"signature/{name} ({expect})",
                detail)

        if name == "wrong-namespace":
            # It must fail for the *right* reason. A vector that failed
            # because its bytes differ would prove nothing about domain
            # separation, so the reason is part of the assertion.
            r.check("namespace does not match" in detail,
                    "signature/wrong-namespace fails on the namespace, not "
                    "on the bytes", detail)
            # ... and the same signature must verify under the namespace it
            # was actually made with, proving the bytes and key are sound.
            ok_git, _ = ssh_sig.verify(payload, pub, b64, namespace="git")
            r.check(ok_git,
                    "signature/wrong-namespace is a genuine signature under "
                    "its own namespace")

        if name == "mutated-payload":
            # This vector is only worth something if the payload was mutated
            # *after* signing. Signed after mutation, it would verify happily
            # and prove nothing — the bug this assertion exists to keep out.
            # The proof is positive: the stored signature must verify over the
            # unmutated bytes it was really made over.
            with open(os.path.join(VECTORS, "payload", "minimal",
                                   "canonical.txt"), "rb") as f:
                original = f.read()
            r.check(payload != original,
                    "signature/mutated-payload really is mutated")
            ok_orig, detail_orig = ssh_sig.verify(original, pub, b64)
            r.check(ok_orig,
                    "signature/mutated-payload was signed BEFORE the mutation",
                    detail_orig)
    r.check(saw_failing, "at least one signature vector MUST fail "
                         "(Conformance.md §2)")


def check_verify(r: Results) -> None:
    print("verify: each vector yields its expected three-valued outcome")
    present = cases("verify")
    missing = [c for c in REQUIRED_VERIFY if c not in present]
    r.check(not missing, f"all {len(REQUIRED_VERIFY)} required cases present",
            f"missing: {missing}")

    outcomes = set()
    for name in present:
        d = os.path.join(VECTORS, "verify", name)
        with open(os.path.join(d, "expected.json"), encoding="utf-8") as f:
            expected = json.load(f)
        got = rv.decide(d)
        outcomes.add(expected["outcome"])
        r.check(got["outcome"] == expected["outcome"],
                f"verify/{name} -> {expected['outcome']}",
                f"got {got['outcome']}")
        r.check(sorted_missing(got) == sorted_missing(expected),
                f"verify/{name} names the same gaps",
                f"got {sorted_missing(got)} want {sorted_missing(expected)}")
        for key in ("ignored", "rejected", "unevaluated"):
            r.check(named(got, key) == named(expected, key),
                    f"verify/{name} {key} names the same certificates",
                    f"got {named(got, key)} want {named(expected, key)}")

    r.check(outcomes == {"covered", "not-covered", "unverifiable"},
            "all three outcomes occur in the suite", f"saw {sorted(outcomes)}")

    # The distinction the whole third value exists for. Both stores deny the
    # certificate; only one of them could not answer.
    with open(os.path.join(VECTORS, "verify", "empty-key-store",
                           "expected.json"), encoding="utf-8") as f:
        empty = json.load(f)["outcome"]
    with open(os.path.join(VECTORS, "verify", "unreadable-store",
                           "expected.json"), encoding="utf-8") as f:
        unreadable = json.load(f)["outcome"]
    r.check(empty == "not-covered" and unreadable == "unverifiable",
            "empty-key-store and unreadable-store do not collapse",
            f"{empty} / {unreadable}")

    # The §7.1 relevance pair. Both cases carry an unevaluable record that
    # looks like it is about another platform; they differ only in whether the
    # consumer can interpret the record and so is entitled to believe that.
    # An implementation that treats every unevaluable record as decisive
    # answers both "unverifiable" and fails this.
    def outcome_of(case: str) -> str:
        with open(os.path.join(VECTORS, "verify", case, "expected.json"),
                  encoding="utf-8") as f:
            return json.load(f)["outcome"]

    # A malformed content id is decidably invalid; a well-formed one in an
    # algorithm the consumer cannot compute is not a mismatch (§4.1.1). The
    # same pair, read the other way, is the one a boolean verifier collapses.
    malformed = outcome_of("content-malformed")
    uncomputable = outcome_of("content-unknown-algorithm")
    r.check(malformed == "not-covered" and uncomputable == "unverifiable",
            "content-malformed and content-unknown-algorithm do not collapse",
            f"{malformed} / {uncomputable}")
    r.check(outcome_of("unknown-schema") == "unverifiable",
            "content-malformed and unknown-schema do not collapse")

    uninterpretable = outcome_of("unknown-schema-off-platform")
    interpretable = outcome_of("unreadable-store-off-platform")
    r.check(uninterpretable == "unverifiable"
            and interpretable == "not-covered",
            "an unevaluable record drives the outcome only when it is "
            "potentially relevant (Verification.md §7.1)",
            f"{uninterpretable} / {interpretable}")


def store_path(cert_path: str) -> tuple[str, bytes, dict]:
    """Transport.md §2.2, from a certificate file however it was written.

    The payload is rebuilt from the parsed fields (Canonical-Payload.md §5);
    the file's own bytes are never hashed.
    """
    with open(cert_path, "rb") as f:
        doc = tomllib.load(f)
    payload = rs.serialize(rs.fields_from_document(doc))
    algorithm, digest = cid.parse(doc["certificate"]["vcs"]["content"])
    name = hashlib.sha256(payload).hexdigest()
    return f"v1/{algorithm}/{digest}/{name}.toml", payload, doc


def check_store(r: Results) -> None:
    print("store: each certificate's Transport.md §2.2 path is derived "
          "and compared")
    present = cases("store")
    missing = [c for c in REQUIRED_STORE if c not in present]
    r.check(not missing, f"all {len(REQUIRED_STORE)} required cases present",
            f"missing: {missing}")
    paths: dict[str, str] = {}
    files: dict[str, bytes] = {}
    docs: dict[str, dict] = {}
    for name in present:
        d = os.path.join(VECTORS, "store", name)
        with open(os.path.join(d, "expected-path.txt"), "rb") as f:
            raw = f.read()
        with open(os.path.join(d, "certificate.toml"), "rb") as f:
            files[name] = f.read()
        r.check(re.fullmatch(rb"v1/[a-z0-9-]+/[0-9a-f]+/[0-9a-f]{64}\.toml\n",
                             raw) is not None,
                f"store/{name} path file is one LF-terminated line "
                f"of the §2.2 form", repr(raw))
        want = raw.decode("utf-8").rstrip("\n")
        paths[name] = want
        try:
            got, payload, doc = store_path(os.path.join(d, "certificate.toml"))
        except (rs.NotCanonical, cid.Malformed, KeyError) as exc:
            r.check(False, f"store/{name}", f"cannot derive a path: {exc}")
            continue
        docs[name] = doc
        r.check(got == want, f"store/{name} -> {want}", f"got {got}")

        # The diagnostic payload is the one the name was derived from, and is
        # the hand-derived payload vector it says it copies.
        with open(os.path.join(d, "canonical.txt"), "rb") as f:
            canonical = f.read()
        r.check(canonical == payload,
                f"store/{name} canonical.txt is certificate.toml's payload")
        source = STORE_PAYLOAD_SOURCE.get(name)
        r.check(source is not None
                and canonical == open(os.path.join(
                    VECTORS, "payload", source, "canonical.txt"), "rb").read(),
                f"store/{name} canonical.txt is payload/{source}'s bytes")

        # A signed certificate carries a real signature over that payload, by
        # the published key its key_id names.
        sig = doc["certificate"].get("signature") or {}
        if sig.get("algorithm") or sig.get("value"):
            key_id = doc["certificate"].get("key_id")
            pub_path = STORE_KEYS.get(key_id)
            ok = pub_path is not None and sig.get("algorithm") == "ed25519"
            detail = f"key_id {key_id!r}, algorithm {sig.get('algorithm')!r}"
            if ok:
                with open(pub_path, encoding="ascii") as f:
                    pub = f.read().strip()
                ok, detail = ssh_sig.verify(payload, pub, sig.get("value", ""))
            r.check(ok, f"store/{name} signature verifies over the payload",
                    detail)

    if not all(n in docs for n in REQUIRED_STORE + ["unsigned-empty-block"]):
        return
    # The relationships the cases exist for, asserted directly, so that a
    # case whose path is right but whose reason is gone fails here.
    def content_dir(n: str) -> str:
        return paths[n].rsplit("/", 1)[0]

    r.check(paths["signed"] != paths["unsigned"]
            and content_dir("signed") == content_dir("unsigned"),
            "store/signed and store/unsigned: same content directory, "
            "different names")
    unsigned_c = docs["unsigned"]["certificate"]
    signed_c = docs["signed"]["certificate"]
    r.check({k: v for k, v in signed_c.items()
             if k not in ("key_id", "signature")} == unsigned_c
            and "key_id" in signed_c and "key_id" not in unsigned_c,
            "store/signed and store/unsigned differ only by key_id and the "
            "signature")

    # The trap the signed cases set: hashing the file is a different name.
    r.check(hashlib.sha256(files["signed"]).hexdigest()
            not in paths["signed"],
            "store/signed: the file's own hash is not the name")

    for twin in ("signed-non-canonical", "signed-non-canonical-no-block"):
        r.check(paths[twin] == paths["signed"]
                and files[twin] != files["signed"],
                f"store/{twin}: different bytes, store/signed's name")
    def as_set(c: dict) -> dict:
        # `targets` is a set (Canonical-Payload.md §3); the rendering may list
        # it in any order.
        return {**c, "targets": sorted(set(c["targets"]))}
    r.check(as_set(docs["signed-non-canonical"]["certificate"])
            == as_set(signed_c),
            "store/signed-non-canonical parses to store/signed's values, "
            "signature included")
    nc = files["signed-non-canonical"]
    r.check(b"\r\n" in nc and nc.find(b"[certificate.signature]")
            < nc.find(b"[certificate]"),
            "store/signed-non-canonical is CRLF with the signature block "
            "before the payload tables")
    no_block = docs["signed-non-canonical-no-block"]["certificate"]
    r.check("signature" not in no_block
            and no_block == {k: v for k, v in signed_c.items()
                             if k != "signature"},
            "store/signed-non-canonical-no-block is store/signed's values "
            "without the block, key_id kept")

    empty = docs["unsigned-empty-block"]["certificate"]
    r.check(paths["unsigned-empty-block"] == paths["unsigned"]
            and empty.get("signature") == {"algorithm": "", "value": ""}
            and files["unsigned-empty-block"] != files["unsigned"],
            "store/unsigned-empty-block: the empty block keeps "
            "store/unsigned's name")

    r.check(paths["manifest-content"].startswith("v1/manifest-v1-sha256/"),
            "store/manifest-content is under manifest-v1-sha256/")
    scoped_vcs = docs["scoped"]["certificate"]["vcs"]
    r.check(bool(scoped_vcs.get("paths"))
            and content_dir("scoped") != content_dir("unsigned")
            and content_dir("scoped") == "v1/" + scoped_vcs["content"]
            .replace(":", "/", 1),
            "store/scoped is under its own scoped content id")


NOTE_DELIMITER = b"# --- test-certificate ---\n"   # Transport.md §3.1


def split_note(blob: bytes) -> tuple[bytes, list[bytes]]:
    """Transport.md §3.1: split on lines equal to the delimiter.

    Returns the piece before the first delimiter (empty in a conforming note)
    and every piece after it, in order.
    """
    lines = re.findall(rb"[^\n]*\n|[^\n]+\Z", blob)
    pieces: list[list[bytes]] = [[]]
    for line in lines:
        if line == NOTE_DELIMITER:
            pieces.append([])
        else:
            pieces[-1].append(line)
    joined = [b"".join(p) for p in pieces]
    return joined[0], joined[1:]


def parse_record(piece: bytes):
    """One piece -> (payload, signature table or None), or None if it does
    not parse. The payload is rebuilt from the parsed fields
    (Canonical-Payload.md §5), never sliced out of the piece."""
    try:
        doc = tomllib.loads(piece.decode("utf-8"))
        payload = rs.serialize(rs.fields_from_document(doc))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError, rs.NotCanonical,
            KeyError, TypeError, ValueError):
        return None
    sig = doc.get("certificate", {}).get("signature")
    if sig is not None and not sig.get("algorithm"):
        sig = None                        # Canonical-Payload.md §6
    return payload, sig


def read_note(blob: bytes) -> list:
    """What a reader yields: a record per parsed piece, None per skipped."""
    lead, pieces = split_note(blob)
    out: list = [None] if lead else []    # a non-empty lead is never parsed
    out += [parse_record(p) for p in pieces]
    return out


def record_bytes(payload: bytes, sig) -> bytes:
    """The §3.1 record form: payload, then (signed) a blank line and the
    signature table, in the payload's formatting rules."""
    if sig is None:
        return payload
    return (payload + b"\n[certificate.signature]\n"
            + f"algorithm = {rs.escape(sig['algorithm'])}\n".encode()
            + f"value = {rs.escape(sig['value'])}\n".encode())


def write_note(blob: bytes, record: bytes) -> bytes:
    """Transport.md §3.1, writer side: add one record to a note."""
    new = parse_record(record)
    assert new is not None, "the record being added must parse"
    lead, pieces = split_note(blob)
    matches = [(i, old) for i, piece in enumerate(pieces)
               if (old := parse_record(piece)) is not None and old[0] == new[0]]
    if not matches:
        pieces.append(record)
    elif new[1] is not None and not any(old[1] is not None for _, old in matches):
        pieces[matches[0][0]] = record  # a signed relay upgrades an unsigned copy
    return lead + b"".join(NOTE_DELIMITER + p for p in pieces)


def check_notes(r: Results) -> None:
    print("notes: each note splits into the records expected.json lists, "
          "and each writer case produces expected-note.txt")
    present = cases("notes")
    missing = [c for c in REQUIRED_NOTES if c not in present]
    r.check(not missing, f"all {len(REQUIRED_NOTES)} required cases present",
            f"missing: {missing}")
    pub = open(STORE_KEYS["example-key-2026-q2"], encoding="ascii").read()
    for name in present:
        d = os.path.join(VECTORS, "notes", name)
        with open(os.path.join(d, "note.txt"), "rb") as f:
            blob = f.read()
        with open(os.path.join(d, "expected.json"), encoding="utf-8") as f:
            want = json.load(f)["pieces"]

        r.check(blob.endswith(b"\n") and b"\r" not in blob
                and not blob.endswith(NOTE_DELIMITER)
                and (blob.startswith(NOTE_DELIMITER)
                     or name == "foreign-preamble"),
                f"notes/{name} note.txt is LF-only, begins with the delimiter "
                f"and does not end with one")

        got = read_note(blob)
        r.check(len(got) == len(want),
                f"notes/{name} yields {len(want)} piece(s)",
                f"got {len(got)}")
        _, pieces = split_note(blob)
        offset = len(got) - len(pieces)
        for i, (g, w) in enumerate(zip(got, want)):
            label = f"notes/{name} piece {i + 1}"
            if w.get("skipped"):
                r.check(g is None, f"{label} is reported and skipped",
                        "it parsed")
                continue
            wp = w["payload"].encode("utf-8")
            if g is None:
                r.check(False, label, "did not parse")
                continue
            payload, sig = g
            r.check(payload == wp, f"{label} payload",
                    f"first difference at byte {first_diff(payload, wp)}")
            r.check((sig is not None) == w["signed"],
                    f"{label} is {'signed' if w['signed'] else 'unsigned'}")
            # Written by a conforming writer: exactly the record form.
            r.check(pieces[i - offset] == record_bytes(wp, sig),
                    f"{label} is in the §3.1 record form")
            if sig is not None:
                ok, detail = ssh_sig.verify(payload, pub.strip(),
                                            sig.get("value", ""))
                r.check(ok and sig.get("algorithm") == "ed25519",
                        f"{label} signature verifies over the payload",
                        detail)
            vec = w.get("payload_vector")
            if vec is not None:
                with open(os.path.join(VECTORS, "payload", vec,
                                       "canonical.txt"), "rb") as f:
                    r.check(f.read() == wp,
                            f"{label} payload is payload/{vec}'s bytes")

        add = os.path.join(d, "add.txt")
        if os.path.exists(add):
            with open(add, "rb") as f:
                record = f.read()
            with open(os.path.join(d, "expected-note.txt"), "rb") as f:
                expected_note = f.read()
            parsed = parse_record(record)
            r.check(parsed is not None
                    and record == record_bytes(parsed[0], parsed[1]),
                    f"notes/{name} add.txt is one record in the §3.1 form")
            got_note = write_note(blob, record)
            r.check(got_note == expected_note,
                    f"notes/{name} adding add.txt yields expected-note.txt",
                    f"first difference at byte "
                    f"{first_diff(got_note, expected_note)}")

    # The facts the cases' pins.md files claim, asserted directly.
    def blob_of(n: str, f: str = "note.txt") -> bytes:
        with open(os.path.join(VECTORS, "notes", n, f), "rb") as fh:
            return fh.read()
    esc = blob_of("escaped-newline")
    r.check(esc.count(NOTE_DELIMITER[:-1]) == 3
            and len(split_note(esc)[1]) == 2,
            "notes/escaped-newline: the delimiter text occurs three times, "
            "starts a line twice")
    r.check("\n# --- test-certificate ---\n" in
            tomllib.loads(split_note(esc)[1][0].decode())
            ["certificate"]["command"][0]["argv"][3],
            "notes/escaped-newline: the value really holds LF, the delimiter, LF")
    sau = read_note(blob_of("signed-and-unsigned"))
    r.check(len(sau) == 2 and sau[0][0] != sau[1][0],
            "notes/signed-and-unsigned: two different payloads")
    sru = read_note(blob_of("signed-replaces-unsigned"))
    added = parse_record(blob_of("signed-replaces-unsigned", "add.txt"))
    r.check(sru[0][1] is None and added[1] is not None
            and sru[0][0] == added[0],
            "notes/signed-replaces-unsigned: the present record is the "
            "unsigned form of the added payload")
    ucn = read_note(blob_of("unsigned-copy-not-added"))
    added = parse_record(blob_of("unsigned-copy-not-added", "add.txt"))
    r.check(ucn[0][1] is not None and added[1] is None
            and ucn[0][0] == added[0],
            "notes/unsigned-copy-not-added: the added record is the unsigned "
            "form of a present signed one")
    lead, _ = split_note(blob_of("foreign-preamble"))
    r.check(bool(lead) and parse_record(lead) is not None,
            "notes/foreign-preamble: the leading piece would parse, and is "
            "still skipped")
    for n in ("duplicate-not-added", "unsigned-copy-not-added"):
        r.check(blob_of(n) == blob_of(n, "expected-note.txt"),
                f"notes/{n}: the note is unchanged")


def sorted_missing(report: dict) -> list:
    return sorted((m["framework"], m["platform"], tuple(sorted(m["targets"])))
                  for m in report.get("missing", []))


def named(report: dict, key: str) -> list:
    return sorted(e["certificate"] for e in report.get(key, []))


def check_index(r: Results) -> None:
    print("index: vectors/index.json matches the directories on disk")
    with open(os.path.join(VECTORS, "index.json"), encoding="utf-8") as f:
        index = json.load(f)
    for group in GROUPS_ON_DISK:
        listed = [c["name"] for c in index["groups"][group]]
        r.check(listed == cases(group), f"index lists every {group} case",
                f"index {listed} vs disk {cases(group)}")
        r.check(all(c["pins"] for c in index["groups"][group]),
                f"every {group} case states what it pins")


def check_structure(r: Results) -> None:
    print("structure: every case carries the files the contract requires")
    for name in cases("payload"):
        d = os.path.join(VECTORS, "payload", name)
        r.check(all(os.path.exists(os.path.join(d, f))
                    for f in ("fields.json", "canonical.txt", "pins.md")),
                f"payload/{name} has fields.json, canonical.txt, pins.md")
    for name in cases("signature"):
        d = os.path.join(VECTORS, "signature", name)
        r.check(all(os.path.exists(os.path.join(d, f))
                    for f in ("canonical.txt", "key.pub", "signature.b64",
                              "expect.txt", "pins.md")),
                f"signature/{name} has the five required files")
    for name in cases("content"):
        d = os.path.join(VECTORS, "content", name)
        r.check(all(os.path.exists(os.path.join(d, f))
                    for f in ("entries.json", "expected.json", "pins.md")),
                f"content/{name} has entries.json, expected.json, pins.md")
    for name in cases("verify"):
        d = os.path.join(VECTORS, "verify", name)
        r.check(all(os.path.exists(os.path.join(d, f))
                    for f in ("state.json", "requirement.json",
                              "registered-keys.toml", "expected.json",
                              "pins.md"))
                and os.path.isdir(os.path.join(d, "certificates")),
                f"verify/{name} has the required files")
    for name in cases("notes"):
        d = os.path.join(VECTORS, "notes", name)
        r.check(all(os.path.exists(os.path.join(d, f))
                    for f in ("note.txt", "expected.json", "pins.md"))
                and os.path.exists(os.path.join(d, "add.txt"))
                == os.path.exists(os.path.join(d, "expected-note.txt")),
                f"notes/{name} has note.txt, expected.json, pins.md, and "
                f"add.txt only with expected-note.txt")
    for name in cases("store"):
        d = os.path.join(VECTORS, "store", name)
        r.check(all(os.path.exists(os.path.join(d, f))
                    for f in ("certificate.toml", "expected-path.txt",
                              "canonical.txt", "pins.md")),
                f"store/{name} has certificate.toml, expected-path.txt, "
                f"canonical.txt, pins.md")


GROUPS = {
    "payload": check_payload,
    "signature": check_signature,
    "content": check_content,
    "verify": check_verify,
    "store": check_store,
    "notes": check_notes,
    "index": check_index,
    "structure": check_structure,
}


def main(argv: list[str]) -> int:
    wanted = argv[1:] or list(GROUPS)
    unknown = [g for g in wanted if g not in GROUPS]
    if unknown:
        print(f"unknown group(s): {unknown}", file=sys.stderr)
        return 2
    r = Results()
    for group in wanted:
        GROUPS[group](r)
        print()
    if r.failures:
        print(f"{len(r.failures)} of {r.checks} checks FAILED")
        for f in r.failures:
            print(f"  - {f}")
        return 1
    print(f"all {r.checks} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
