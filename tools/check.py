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
    index      vectors/index.json matches what is on disk
"""

from __future__ import annotations

import hashlib
import json
import os
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


def sorted_missing(report: dict) -> list:
    return sorted((m["framework"], m["platform"], tuple(sorted(m["targets"])))
                  for m in report.get("missing", []))


def named(report: dict, key: str) -> list:
    return sorted(e["certificate"] for e in report.get(key, []))


def check_index(r: Results) -> None:
    print("index: vectors/index.json matches the directories on disk")
    with open(os.path.join(VECTORS, "index.json"), encoding="utf-8") as f:
        index = json.load(f)
    for group in ("payload", "signature", "content", "verify"):
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


GROUPS = {
    "payload": check_payload,
    "signature": check_signature,
    "content": check_content,
    "verify": check_verify,
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
