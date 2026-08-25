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
    verify     every vector yields its expected three-valued outcome, and the
               gaps it names
    index      vectors/index.json matches what is on disk
"""

from __future__ import annotations

import json
import os
import sys
import tomllib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
    "unscoped", "dirty-tree", "dirty-patch-only", "clean-no-worktree",
]
REQUIRED_VERIFY = [
    "coverage-union", "wrong-platform", "other-framework", "revoked-key",
    "empty-key-store", "unsigned-required", "dirty-tree-matches",
    "dirty-tree-differs", "dirty-no-worktree", "scope-too-narrow",
    "unreadable-store",
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
    r.check(not missing, "all 16 required cases present",
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
    r.check(not missing, "all 11 required cases present", f"missing: {missing}")

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
    for group in ("payload", "signature", "verify"):
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
