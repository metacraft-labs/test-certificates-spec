#!/usr/bin/env python3
"""Reference content-id computation.

NON-NORMATIVE. See tools/README.md.

    Authoring tooling used to check `vectors/content/*`. No implementation is
    required to read, port or invoke it. Where this file and Content-Id.md
    disagree, the document wins and this file is a bug.

It computes all three algorithms in Content-Id.md §4 from a list of tracked
entries, in plain Python, **without git**. The `git-tree-*` ids are built from
git's object format directly — blob and tree objects hashed by hand — so that
they are an independent derivation of what `tools/walk-vectors.sh` obtains
from git itself. Two routes to one id; if they disagree, one of them is wrong.

It also parses a content id's form (Content-Id.md §1), which the reference
verifier uses to tell a malformed id from one it merely cannot compute.

Usage:
    python3 tools/reference_content_id.py vectors/content/modes
        prints every id in expected.json as computed here
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sys

# Content-Id.md §4: algorithm -> digest length in hex digits.
DIGEST_LENGTH = {
    "git-tree-sha1": 40,
    "git-tree-sha256": 64,
    "manifest-v1-sha256": 64,
}

_ALGORITHM_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789-")
_RESERVED_ALGORITHMS = {"con", "prn", "aux", "nul"} | {
    f"{stem}{i}" for stem in ("com", "lpt") for i in range(1, 10)
}

_HEX = frozenset("0123456789abcdef")
_MODES = ("100644", "100755", "120000", "160000")


class Malformed(ValueError):
    """A content id that is decidably invalid (Verification.md §4.1.1)."""


def parse(content_id: object) -> tuple[str, str]:
    """Split a content id into (algorithm, digest), or raise Malformed.

    Content-Id.md §1. The algorithm is everything before the FIRST `:`. The
    digest must be non-empty lowercase hex; for an algorithm this standard
    defines it must also have that algorithm's length. For an algorithm it
    does not define, the length cannot be judged — only the algorithm defines
    it — so such an id is well-formed and merely uncomputable. Nothing here
    repairs anything: no lowercasing, no trimming, no prefix matching.
    """
    if not isinstance(content_id, str) or ":" not in content_id:
        raise Malformed(f"{content_id!r} has no ':' separating algorithm "
                        f"and digest")
    algorithm, digest = content_id.split(":", 1)
    if not algorithm:
        raise Malformed(f"{content_id!r} names no algorithm")
    if (len(algorithm) > 64 or not set(algorithm) <= _ALGORITHM_CHARS
            or algorithm in _RESERVED_ALGORITHMS):
        raise Malformed(f"{content_id!r}: algorithm identifier is not portable")
    if not digest or not set(digest) <= _HEX:
        raise Malformed(f"{content_id!r}: digest is not lowercase hex")
    want = DIGEST_LENGTH.get(algorithm)
    if want is not None and len(digest) != want:
        raise Malformed(f"{content_id!r}: {algorithm} digests are {want} hex "
                        f"digits, not {len(digest)}")
    return algorithm, digest


def load_entries(path: str) -> list[tuple[bytes, str, bytes]]:
    """entries.json -> [(path bytes, mode, content bytes)], order as given."""
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    out = []
    seen = set()
    for e in raw:
        p = e["path"].encode("utf-8")
        mode = e["mode"]
        if mode not in _MODES:
            raise ValueError(f"{e['path']!r}: mode {mode!r} is not one of "
                             f"{_MODES} (Content-Id.md §4.2)")
        if p in seen:
            raise ValueError(f"{e['path']!r} appears twice; paths are unique")
        if (not p or p.startswith(b"/") or p.startswith(b"./")
                or p.endswith(b"/") or b"\0" in p or b"//" in p):
            raise ValueError(f"{e['path']!r} is not a repo-relative path")
        seen.add(p)
        out.append((p, mode, base64.b64decode(e["content_b64"],
                                              validate=True)))
    return out


def in_scope(path: bytes, scope: list[str] | None) -> bool:
    """Standard.md §3.2.1: a scope path names that file or the subtree under
    it. Compared on raw bytes, literally — `src/d` is not a prefix of
    `src/db/x`, and `*` is an ordinary character."""
    if not scope:
        return True
    for s in scope:
        sb = s.encode("utf-8")
        if path == sb or path.startswith(sb + b"/"):
            return True
    return False


# --- manifest-v1-sha256 (Content-Id.md §4.2) ------------------------------

def manifest_records(entries) -> bytes:
    """The concatenated records, in ascending byte order of path."""
    out = []
    for path, mode, content in sorted(entries, key=lambda e: e[0]):
        digest = hashlib.sha256(content).hexdigest()
        out.append(mode.encode("ascii") + b" " + digest.encode("ascii")
                   + b" " + path + b"\0")
    return b"".join(out)


def manifest_v1_sha256(entries) -> str:
    return hashlib.sha256(manifest_records(entries)).hexdigest()


# --- git-tree-sha1 / git-tree-sha256 (Content-Id.md §4.1) ------------------
#
# Built from git's object format, not from git: an object id is the hash of
# `<type> SP <decimal length> NUL <body>`, and a tree body is a sequence of
# `<mode> SP <name> NUL <raw id>` entries, sorted with each subtree's name
# compared as if it ended in `/`. Subtrees are mode `40000` (no leading zero).

def _object_id(kind: bytes, body: bytes, hash_name: str) -> bytes:
    h = hashlib.new(hash_name)
    h.update(kind + b" " + str(len(body)).encode("ascii") + b"\0" + body)
    return h.digest()


def git_tree(entries, hash_name: str) -> str:
    root: dict = {}
    for path, mode, content in entries:
        *dirs, name = path.split(b"/")
        node = root
        for d in dirs:
            node = node.setdefault(d, {})
            if not isinstance(node, dict):
                raise ValueError(f"{path!r} lies under a non-directory")
        if name in node:
            raise ValueError(f"{path!r} collides with a directory")
        if mode == "160000":
            # A gitlink records the nested repository's revision itself.
            oid = bytes.fromhex(content.decode("ascii"))
        else:
            oid = _object_id(b"blob", content, hash_name)
        node[name] = (mode.encode("ascii"), oid)

    def write(node: dict) -> bytes:
        items = []
        for name, value in node.items():
            if isinstance(value, dict):
                items.append((name + b"/", b"40000", name, write(value)))
            else:
                mode, oid = value
                items.append((name, mode, name, oid))
        items.sort(key=lambda i: i[0])
        body = b"".join(mode + b" " + name + b"\0" + oid
                        for _, mode, name, oid in items)
        return _object_id(b"tree", body, hash_name)

    return write(root).hex()


def compute(entries, algorithm: str, scope: list[str] | None) -> str:
    """The content id of the in-scope entries under `algorithm`.

    A scoped git tree keeps full repository paths (Content-Id.md §4.1): it is
    the tree of the in-scope entries, not the subtree at the scope path.
    """
    chosen = [e for e in entries if in_scope(e[0], scope)]
    if algorithm == "manifest-v1-sha256":
        digest = manifest_v1_sha256(chosen)
    elif algorithm == "git-tree-sha1":
        digest = git_tree(chosen, "sha1")
    elif algorithm == "git-tree-sha256":
        digest = git_tree(chosen, "sha256")
    else:
        raise ValueError(f"algorithm {algorithm!r} is not implemented")
    return f"{algorithm}:{digest}"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    entries = load_entries(os.path.join(argv[1], "entries.json"))
    with open(os.path.join(argv[1], "expected.json"), encoding="utf-8") as f:
        expected = json.load(f)
    for e in expected:
        print(json.dumps(e["paths"], ensure_ascii=False),
              compute(entries, e["algorithm"], e["paths"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
