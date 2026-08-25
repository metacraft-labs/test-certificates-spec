#!/usr/bin/env python3
"""Thin wrapper over `ssh-keygen -Y sign` / `-Y verify`.

NON-NORMATIVE authoring tooling. See tools/README.md.

Standard.md §6.1 names OpenSSH ed25519 detached signatures as *the* signing
primitive, so this wrapper shells out to `ssh-keygen` rather than implementing
SSH signature framing. That is deliberate: an independent reimplementation here
could agree with itself and disagree with the tool the standard names.

Two shapes of the same signature appear in this repository:

* the **armored** form `-----BEGIN SSH SIGNATURE-----…`, which is what
  `ssh-keygen` reads and writes;
* the **base64 blob**, which is what a certificate's `signature.value` carries
  (Standard.md §6.1) and what `vectors/signature/*/signature.b64` stores.

`armor()` and `unarmor()` convert between them. The conversion is pure framing:
identical bytes, different wrapper.
"""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
import tempfile

NAMESPACE = "test-certificate-v1"  # Standard.md §6.1
BEGIN = "-----BEGIN SSH SIGNATURE-----"
END = "-----END SSH SIGNATURE-----"

# Any principal works: an SSH signature blob binds the namespace and the public
# key, not an identity. The identity only selects a line in `allowed_signers`.
PRINCIPAL = "vectors@test-certificates.invalid"


def unarmor(armored: str) -> str:
    """Armored signature -> single-line base64 blob (RFC 4648 §4, padded)."""
    lines = [ln.strip() for ln in armored.strip().splitlines()]
    if not lines or lines[0] != BEGIN or lines[-1] != END:
        raise ValueError("not an armored SSH signature")
    return "".join(lines[1:-1])


def armor(b64: str) -> str:
    """Single-line base64 blob -> armored signature.

    `ssh-keygen` accepts any line wrapping inside the armor, so the blob goes
    back in as one line. This direction is what a consumer needs in order to
    check a certificate's `signature.value` with the stock tool.
    """
    return f"{BEGIN}\n{b64.strip()}\n{END}\n"


def _private_key_copy(key_path: str, workdir: str) -> str:
    """Copy a private key into `workdir` with 0600.

    Git records no file mode beyond the executable bit, so a freshly cloned
    private key is world-readable and `ssh-keygen` refuses to load it. Copying
    is simpler than mutating the checkout.
    """
    dest = os.path.join(workdir, "key")
    shutil.copyfile(key_path, dest)
    os.chmod(dest, 0o600)
    return dest


def sign(payload: bytes, private_key_path: str,
         namespace: str = NAMESPACE) -> str:
    """Sign `payload`, returning the single-line base64 blob."""
    with tempfile.TemporaryDirectory() as workdir:
        key = _private_key_copy(private_key_path, workdir)
        msg = os.path.join(workdir, "payload")
        with open(msg, "wb") as f:
            f.write(payload)
        subprocess.run(
            ["ssh-keygen", "-Y", "sign", "-f", key, "-n", namespace, "-q", msg],
            check=True)
        with open(msg + ".sig", encoding="ascii") as f:
            return unarmor(f.read())


def verify(payload: bytes, public_key: str, signature_b64: str,
           namespace: str = NAMESPACE) -> tuple[bool, str]:
    """Verify `payload` against `public_key`. Returns (ok, tool output)."""
    with tempfile.TemporaryDirectory() as workdir:
        allowed = os.path.join(workdir, "allowed_signers")
        with open(allowed, "w", encoding="ascii") as f:
            f.write(f"{PRINCIPAL} {public_key.strip()}\n")
        sig = os.path.join(workdir, "sig")
        with open(sig, "w", encoding="ascii") as f:
            f.write(armor(signature_b64))
        proc = subprocess.run(
            ["ssh-keygen", "-Y", "verify", "-f", allowed, "-I", PRINCIPAL,
             "-n", namespace, "-s", sig],
            input=payload, capture_output=True)
        output = (proc.stdout + proc.stderr).decode("utf-8", "replace").strip()
        return proc.returncode == 0, output


def public_key_of(private_key_path: str) -> str:
    with open(private_key_path + ".pub", encoding="ascii") as f:
        return f.read().strip()


def b64_is_canonical(b64: str) -> bool:
    """True when `b64` is single-line, padded, standard-alphabet base64."""
    if b64 != b64.strip() or any(c.isspace() for c in b64):
        return False
    try:
        return base64.b64encode(base64.b64decode(b64, validate=True)).decode() == b64
    except Exception:
        return False
