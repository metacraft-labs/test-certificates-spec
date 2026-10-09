#!/usr/bin/env python3
"""Reference canonical-payload serializer.

NON-NORMATIVE. See tools/README.md.

    The vectors are the specification's executable half; this file is only
    authoring tooling used to check them. No implementation is required to
    read, port or invoke it. Where this file and Canonical-Payload.md
    disagree, the document wins and this file is a bug.

It exists so that `vectors/payload/*/canonical.txt` — which is hand-derived
from the prose — can be checked mechanically for byte-exactness, and so that
the certificates inside `vectors/verify/` can be signed over payloads that are
genuinely canonical.

Usage:
    python3 tools/reference_serializer.py vectors/payload/minimal/fields.json
        writes the canonical payload bytes to stdout
"""

from __future__ import annotations

import json
import sys
from typing import Any

SCHEMA = "test-certificate.v1"

# Canonical-Payload.md §4. Exactly these seven, and no others. The set is
# identical to JSON's, which is why `jq`'s @json produces conforming TOML basic
# strings for any value this standard permits (see tools/walk-vectors.sh).
_ESCAPES = {
    "\\": "\\\\",
    '"': '\\"',
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
    "\b": "\\b",
    "\f": "\\f",
}

# Canonical key order. Canonical-Payload.md §2 rule 1: fixed, not alphabetical,
# and MUST NOT be re-sorted. Kept as literal tuples rather than derived from the
# input so that a mis-ordered fields.json cannot smuggle a different order out.
_CERT_KEYS = ("framework", "project", "platform", "targets", "result",
              "issued_at", "issuer", "key_id")
_VCS_KEYS = ("repo", "paths", "content", "untracked", "base")


class NotCanonical(ValueError):
    """The input cannot be serialized without repairing it.

    Canonical-Payload.md §5 forbids a verifier from "repairing" a payload into
    validity, so this serializer refuses rather than guessing.
    """


def escape(value: str) -> str:
    """Render a TOML basic string per Canonical-Payload.md §4."""
    out = ['"']
    for ch in value:
        esc = _ESCAPES.get(ch)
        if esc is not None:
            out.append(esc)
            continue
        code = ord(ch)
        # TOML basic strings cannot carry raw control characters, and §4
        # permits no escape for them beyond the seven above. A value holding
        # one is not representable, so it is malformed rather than a
        # serialization choice.
        if code < 0x20 or code == 0x7F:
            raise NotCanonical(
                f"control character U+{code:04X} has no canonical "
                f"representation (Canonical-Payload.md §4)")
        out.append(ch)
    out.append('"')
    return "".join(out)


def _array(values: list[str]) -> str:
    """Inline array form from §3: `["a", "b"]`."""
    return "[" + ", ".join(escape(v) for v in values) + "]"


def sort_dedup(values: list[str]) -> list[str]:
    """Deduplicate, then sort in ascending UTF-8 byte order (§3).

    The sort key is the raw encoded value, *not* its escaped rendering: a value
    containing TAB (0x09) sorts before one containing '!' (0x21), whereas their
    escaped forms would compare '\\' (0x5C) against '!'. See
    vectors/payload/escapes/pins.md.
    """
    seen: dict[str, None] = {}
    for v in values:
        seen.setdefault(v, None)
    return sorted(seen, key=lambda s: s.encode("utf-8"))


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise NotCanonical(msg)


def _str_list(node: Any, what: str) -> list[str]:
    _require(isinstance(node, list) and all(isinstance(v, str) for v in node),
             f"{what} must be an array of strings")
    return node


def serialize(fields: dict) -> bytes:
    """Serialize a fields.json body to canonical payload bytes.

    `fields` mirrors the TOML structure exactly (see vectors/README.md). Values
    are *inputs*: `targets` and `paths` arrive in whatever order the producer
    observed and may contain duplicates.
    """
    _require(fields.get("schema") == SCHEMA,
             f"schema must be {SCHEMA!r} (Standard.md §3.1)")
    cert = fields.get("certificate")
    _require(isinstance(cert, dict), "certificate table is required")

    lines: list[str] = [f"schema = {escape(SCHEMA)}", "", "[certificate]"]

    for key in _CERT_KEYS:
        if key not in cert:
            # `key_id` is the only optional key here, and it is omitted
            # entirely rather than emitted empty (§2 rule 3).
            _require(key == "key_id", f"required field {key!r} is missing")
            continue
        if key == "targets":
            targets = sort_dedup(_str_list(cert["targets"], "targets"))
            _require(len(targets) >= 1,
                     "targets must name at least one target (Standard.md §3.1)")
            lines.append(f"targets = {_array(targets)}")
        else:
            value = cert[key]
            _require(isinstance(value, str), f"{key!r} must be a string")
            _require(value != "" or key != "key_id",
                     "key_id must be omitted when unsigned, not emitted empty")
            lines.append(f"{key} = {escape(value)}")

    vcs = cert.get("vcs")
    _require(isinstance(vcs, dict), "[certificate.vcs] is required")
    lines += ["", "[certificate.vcs]"]
    for key in _VCS_KEYS:
        if key == "paths":
            paths = _str_list(vcs.get("paths", []), "paths")
            # §2 rule 8: omitted entirely for a whole-repository claim, never
            # emitted as []. Standard.md §3.2.1: absent and empty both mean
            # the whole repository, so an empty input list drops the key.
            if paths:
                for p in paths:
                    _require(not p.startswith("./") and not p.endswith("/")
                             and "\\" not in p,
                             f"path {p!r} is not repo-relative /-separated "
                             f"(Standard.md §3.2.1)")
                lines.append(f"paths = {_array(sort_dedup(paths))}")
            continue
        if key == "base":
            # §2 rule 10: optional, omitted entirely when absent, never
            # emitted empty (Standard.md §3.2.3), and last in the table.
            if "base" in vcs:
                _require(isinstance(vcs["base"], str) and vcs["base"] != "",
                         "vcs.base must be omitted, not emitted empty "
                         "(Standard.md §3.2.3)")
                lines.append(f"base = {escape(vcs['base'])}")
            continue
        _require(key in vcs, f"vcs.{key} is required (Standard.md §3.2)")
        value = vcs[key]
        if key == "untracked":
            _require(isinstance(value, bool),
                     "vcs.untracked must be a boolean (§2 rule 4)")
            lines.append(f"untracked = {'true' if value else 'false'}")
        else:
            # `content` is emitted verbatim (§2 rule 9): not split, re-cased
            # or validated here. A malformed content id is the verifier's
            # finding; rewriting it would sign a value nobody computed.
            _require(isinstance(value, str), f"vcs.{key} must be a string")
            lines.append(f"{key} = {escape(value)}")
    for key in vcs:
        # An earlier-draft record has already failed above, on the missing
        # `content`. Its `commit`, `clean` and `worktree` would land here
        # otherwise: dropping them silently would sign a payload the
        # producer never computed (Canonical-Payload.md §7.1).
        _require(key in _VCS_KEYS, f"unknown vcs key {key!r}")

    commands = cert.get("command")
    _require(isinstance(commands, list) and len(commands) >= 1,
             "at least one [[certificate.command]] is required "
             "(Standard.md §3.1)")
    for entry in commands:
        _require(isinstance(entry, dict) and set(entry) == {"argv"},
                 "each command entry carries exactly one key, argv")
        argv = _str_list(entry["argv"], "argv")
        _require(len(argv) >= 1, "argv must carry at least argv[0]")
        # §2 rule 7: never sorted, never deduplicated.
        lines += ["", "[[certificate.command]]", f"argv = {_array(argv)}"]

    for key in cert:
        _require(key in _CERT_KEYS or key in ("vcs", "command"),
                 f"unknown certificate key {key!r}")

    # §1: LF endings, and the payload ends with a newline.
    return ("\n".join(lines) + "\n").encode("utf-8")


def serialize_file(path: str) -> bytes:
    with open(path, "rb") as f:
        return serialize(json.loads(f.read().decode("utf-8")))


def fields_from_document(doc: dict) -> dict:
    """Project a parsed certificate document onto the fields.json shape.

    This is the move Canonical-Payload.md §5 requires: a verifier reconstructs
    the payload from the *parsed values*, never by slicing the received file.
    A received certificate may differ from canonical form in whitespace, key
    order, string style or escaping while parsing to identical values, and it
    must still verify against its own signature.

    The `[certificate.signature]` table is dropped here, which is what
    "excluding the signature block" means in practice.
    """
    cert = doc.get("certificate")
    _require(isinstance(cert, dict), "certificate table is required")
    out_cert: dict[str, Any] = {}
    for key in _CERT_KEYS:
        if key in cert:
            out_cert[key] = cert[key]
    vcs = cert.get("vcs")
    _require(isinstance(vcs, dict), "[certificate.vcs] is required")
    # Every key is carried across, known or not: an unknown one makes
    # serialize() refuse, which is how an earlier-draft record (`commit`,
    # `clean`, no `content`) comes to be rejected rather than quietly
    # translated (Canonical-Payload.md §7.1).
    out_cert["vcs"] = dict(vcs)
    commands = cert.get("command")
    _require(isinstance(commands, list), "[[certificate.command]] is required")
    out_cert["command"] = [{"argv": e["argv"]} for e in commands]
    return {"schema": doc.get("schema"), "certificate": out_cert}


def canonical_from_toml(path: str) -> bytes:
    """Canonical payload bytes for a certificate file, however it was written."""
    import tomllib  # stdlib since Python 3.11

    with open(path, "rb") as f:
        return serialize(fields_from_document(tomllib.load(f)))


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    sys.stdout.buffer.write(serialize_file(argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
