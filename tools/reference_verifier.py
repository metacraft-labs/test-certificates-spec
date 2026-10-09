#!/usr/bin/env python3
"""Reference three-valued verifier.

NON-NORMATIVE. See tools/README.md.

    Authoring tooling used to check that `vectors/verify/*` is self-consistent
    and that its expected outcomes are the ones Verification.md requires. No
    implementation is required to read, port or invoke it. Where this file and
    Verification.md disagree, the document wins and this file is a bug.

It implements the generic half of Verification.md — framework filtering,
authenticity, the VCS/platform/scope check, and coverage as a union — and
nothing framework-specific, because §4.2 says there is nothing generic to
implement there.

Usage:
    python3 tools/reference_verifier.py vectors/verify/coverage-union
"""

from __future__ import annotations

import json
import os
import sys
import tomllib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import reference_content_id as cid  # noqa: E402
import reference_serializer as rs  # noqa: E402
import ssh_sig  # noqa: E402

COVERED = "covered"
NOT_COVERED = "not-covered"
UNVERIFIABLE = "unverifiable"


class Report:
    """A verdict plus the detail Verification.md §5 requires it to carry."""

    def __init__(self) -> None:
        self.ignored: list[dict] = []      # other frameworks (§2)
        self.rejected: list[dict] = []     # evaluated, and not evidence (§4)
        self.unevaluated: list[dict] = []  # evaluation broke down (§7)
        # Names of unevaluated records that are *potentially relevant* (§7.1).
        # Only these can make the outcome unverifiable; the rest are reported
        # but could not have changed the answer.
        self.blocking: list[str] = []
        self.store_unreadable: str | None = None
        self.missing: list[dict] = []
        self.outcome = NOT_COVERED

    def as_dict(self) -> dict:
        out = {"outcome": self.outcome, "missing": self.missing}
        if self.ignored:
            out["ignored"] = self.ignored
        if self.rejected:
            out["rejected"] = self.rejected
        if self.unevaluated:
            out["unevaluated"] = self.unevaluated
        return out


def load_store(path: str) -> tuple[dict | None, str | None]:
    """Parse a registered-key store.

    Returns (keys_by_id, unreadable_reason). Verification.md draws the line
    this function encodes:

    * a store that is **missing or empty** is fail-closed — it answers the
      question with "nobody is trusted" (§3.1), which is decidable;
    * a store that cannot be **read or parsed** answers nothing, and makes the
      outcome unverifiable (§7).
    """
    if not os.path.exists(path):
        return {}, None  # missing store: fail-closed, not unreadable
    try:
        with open(path, "rb") as f:
            doc = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return None, f"{os.path.basename(path)} could not be read: {exc}"
    if doc.get("schema") != "registered-keys.v1":
        return None, f"unknown key-store schema {doc.get('schema')!r}"
    keys = {}
    for entry in doc.get("key", []):
        keys[entry["key_id"]] = entry
    return keys, None


def within_scope(required_paths: list[str] | None,
                 cert_paths: list[str] | None) -> bool:
    """Does a certificate's scope cover what the consumer requires? (§4.1.2)

    A certificate with no `paths` covers the whole repository and therefore
    covers anything. A scoped certificate covers a required path only when that
    path lies inside one of its scope entries — a scope entry naming a
    directory covers the subtree beneath it (Standard.md §3.2.1).
    """
    if not cert_paths:
        return True
    if required_paths is None:
        return False  # whole repository required, scoped certificate offered
    return all(any(r == c or r.startswith(c + "/") for c in cert_paths)
               for r in required_paths)


def scope_key(paths: list[str] | None) -> tuple[str, ...]:
    """A scope in comparable form: absent and empty both mean the whole
    repository (Standard.md §3.2.1), and order and duplicates are not part of
    it."""
    return tuple(sorted(set(paths or []), key=lambda p: p.encode("utf-8")))


def could_satisfy(cert: dict, requirement: dict) -> bool:
    """Could this record, if it had verified, have met part of the requirement?

    Verification.md §7.1. This is only ever asked of a record the consumer can
    **interpret** — a v1 record whose fields mean what this consumer thinks
    they mean. For a record in a schema version it does not implement the
    question is not asked at all, because the answer would be read out of
    fields it has just admitted it cannot interpret.
    """
    if cert.get("platform") not in requirement["platforms"]:
        return False
    return bool(set(cert.get("targets", [])) & set(requirement["targets"]))


def evaluate(cert_path: str, doc: dict, state: dict, requirement: dict,
             keys: dict | None, store_unreadable: str | None,
             report: Report) -> dict | None:
    """Evaluate one candidate certificate.

    Returns the certificate's contribution ({platform, targets}) when it is
    evidence, and None when it is not. Anything that could not be judged is
    recorded on `report.unevaluated` rather than rejected.
    """
    name = os.path.basename(cert_path)

    def reject(why: str) -> None:
        report.rejected.append({"certificate": name, "why": why})

    def unevaluated(why: str, *, relevant: bool) -> None:
        """Record a breakdown, and whether it can drive the outcome (§7.1)."""
        report.unevaluated.append({"certificate": name, "why": why})
        if relevant:
            report.blocking.append(name)

    # An unimplemented schema version is an evaluation breakdown, not a
    # verdict: the record may be perfectly good in a dialect we do not speak.
    #
    # It is ALWAYS potentially relevant (§7.1). We must not look at its
    # `platform` or `targets` to decide it was irrelevant: reading them with a
    # v1 parser means trusting an interpretation we have just said we do not
    # have, and a later version may redefine those fields or widen the record's
    # scope with a field this parser never looks at.
    if doc.get("schema") != rs.SCHEMA:
        unevaluated(f"schema {doc.get('schema')!r} is not implemented",
                    relevant=True)
        return None

    cert = doc.get("certificate", {})
    vcs = cert.get("vcs", {})

    # Missing required fields, by contrast, are decidably invalid under v1.
    try:
        payload = rs.serialize(rs.fields_from_document(doc))
    except rs.NotCanonical as exc:
        reject(f"malformed: {exc}")
        return None

    if cert.get("result") != "passed":
        reject(f"result is {cert.get('result')!r}, not 'passed'")
        return None
    if vcs.get("repo") != state["repo"]:
        reject(f"vcs.repo {vcs.get('repo')!r} is a different repository")
        return None

    # --- Scope (§4.1.2) ---------------------------------------------------
    # Decidable from the record alone, so it comes before the content match:
    # a certificate too narrow for the requirement is rejected whether or not
    # its content id could have been computed.
    if not within_scope(requirement.get("paths"), vcs.get("paths")):
        reject(f"vcs.paths scopes the claim to {vcs.get('paths')!r}, narrower "
               f"than what is required")
        return None

    # --- Content binding (§4.1, §4.1.1) ----------------------------------
    # `base` is never consulted: comparing it, or any commit id, with the
    # state under evaluation rejects exactly the certificates the content
    # binding exists to make valid.
    try:
        algorithm, _ = cid.parse(vcs.get("content"))
    except cid.Malformed as exc:
        # Decidably invalid, and never repaired: no lowercasing, no prefix
        # matching of an abbreviated digest, no assumed algorithm.
        reject(f"malformed content id: {exc}")
        return None
    computable = [c for c in state["content"] if c["algorithm"] == algorithm]
    if not computable:
        # Not a mismatch: the consumer cannot compute this algorithm for the
        # state, so it has established nothing (§4.1.1). The record is
        # interpretable, so §7.1 lets us ask whether it could have mattered.
        unevaluated(f"content id algorithm {algorithm!r} cannot be computed "
                    f"by this consumer", relevant=could_satisfy(cert,
                                                                requirement))
        return None
    scope = scope_key(vcs.get("paths"))
    ours = [c["id"] for c in computable if scope_key(c["paths"]) == scope]
    if not ours:
        raise ValueError(f"state.json lists {algorithm} but not for scope "
                         f"{scope!r}; the vector is incomplete")
    if vcs["content"] != ours[0]:
        reject("vcs.content does not equal the content id of the state "
               "under evaluation")
        return None

    # --- Authenticity (§3) -----------------------------------------------
    if requirement.get("require_signature"):
        sig = doc.get("certificate", {}).get("signature") or {}
        key_id = cert.get("key_id")
        # Canonical-Payload.md §6: an absent block and an empty block both
        # mean unsigned, and are treated identically.
        if not key_id or not sig.get("value") or not sig.get("algorithm"):
            reject("unsigned, and this consumer requires signatures")
            return None
        if store_unreadable is not None:
            # The store could not answer, but this record IS interpretable, so
            # §7.1 lets us say whether the answer could have mattered. A
            # certificate for a platform nobody asked about contributes nothing
            # however its signature would have checked out.
            unevaluated(f"authenticity undecidable: {store_unreadable}",
                        relevant=could_satisfy(cert, requirement))
            return None
        entry = (keys or {}).get(key_id)
        if entry is None:
            reject(f"key_id {key_id!r} resolves to no registered key")
            return None
        if entry.get("status") != "active":
            reject(f"key_id {key_id!r} has status {entry.get('status')!r}")
            return None
        if sig.get("algorithm") != "ed25519":
            reject(f"algorithm {sig.get('algorithm')!r} is not ed25519")
            return None
        ok, detail = ssh_sig.verify(payload, entry["public_key"], sig["value"])
        if not ok:
            reject(f"signature does not verify: {detail}")
            return None

    return {"platform": cert.get("platform"),
            "targets": sorted(set(cert.get("targets", [])))}


def decide(case_dir: str) -> dict:
    """Run the Verification.md algorithm over one vector directory."""
    with open(os.path.join(case_dir, "state.json"), encoding="utf-8") as f:
        state = json.load(f)
    with open(os.path.join(case_dir, "requirement.json"),
              encoding="utf-8") as f:
        requirement = json.load(f)
    keys, store_unreadable = load_store(
        os.path.join(case_dir, "registered-keys.toml"))

    report = Report()
    contributions: list[dict] = []
    cert_dir = os.path.join(case_dir, "certificates")
    for fname in sorted(os.listdir(cert_dir)):
        if not fname.endswith(".toml"):
            continue
        path = os.path.join(cert_dir, fname)
        with open(path, "rb") as f:
            doc = tomllib.load(f)
        framework = doc.get("certificate", {}).get("framework")
        # §2: framework filtering comes first, before any other check.
        if framework not in requirement["frameworks_implemented"]:
            report.ignored.append(
                {"certificate": fname,
                 "why": f"framework {framework!r} is not implemented by this "
                        f"consumer"})
            continue
        if framework != requirement["framework"]:
            report.ignored.append(
                {"certificate": fname,
                 "why": f"framework {framework!r} is not the one this "
                        f"requirement is about"})
            continue
        contribution = evaluate(path, doc, state, requirement, keys,
                                store_unreadable, report)
        if contribution is not None:
            contributions.append(contribution)

    # --- Coverage as a union, per platform (§5) --------------------------
    for platform in requirement["platforms"]:
        union: set[str] = set()
        for c in contributions:
            if c["platform"] == platform:
                union.update(c["targets"])
        gap = [t for t in requirement["targets"] if t not in union]
        if gap:
            report.missing.append({"framework": requirement["framework"],
                                   "platform": platform,
                                   "targets": gap})

    # --- Precedence (§7.1) ------------------------------------------------
    # 1. Covered wins when the requirement is met by certificates that were
    #    fully evaluated. v1 coverage is monotonic — nothing subtracts — so a
    #    record we could not read could only have added coverage, and telling
    #    an operator to fix their configuration in order to reach a conclusion
    #    already reached is the unhelpfulness the third value exists to avoid.
    # 2. Otherwise a breakdown outranks not-covered, but only for records that
    #    are *potentially relevant*: uninterpretable ones always, interpretable
    #    ones only when their scope could have met part of the requirement.
    # 3. Otherwise not-covered, naming the gaps.
    if not report.missing:
        report.outcome = COVERED
    elif report.blocking:
        report.outcome = UNVERIFIABLE
        report.missing = []
    else:
        report.outcome = NOT_COVERED
    return report.as_dict()


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    print(json.dumps(decide(argv[1]), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
