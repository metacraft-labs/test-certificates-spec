#!/bin/sh
# Prove the suite detects its own corruption.
#
# NON-NORMATIVE. See tools/README.md.
#
# A conformance suite that passes whatever you feed it pins nothing. This
# script takes a throwaway copy of the repository, damages one thing at a time,
# and asserts that the checks go red — once for a canonical payload, once for a
# signature, and once for a signature inside a verification vector, so all
# three groups are shown to be load-bearing. A fourth flips a record's schema
# version to show that the §7.1 relevance distinction is load-bearing too,
# which no amount of signature checking would catch.
#
# Every check is run twice per corruption: with the Python reference tools and
# with the POSIX-shell walker. A corruption caught by only one of them would
# mean one of the two is not really checking.
#
#   sh tools/corruption-demo.sh

set -eu

here=$(dirname "$0")
root=$(cd "$here/.." && pwd)

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT INT TERM
cp -R "$root/vectors" "$root/tools" "$work/"

pass=0
fail=0

# The assertion is inverted on purpose: these commands MUST fail.
expect_red() { # <label> <command…>
  label=$1
  shift
  if "$@" > "$work/out" 2>&1; then
    fail=$((fail + 1))
    printf '  NOT DETECTED  %s\n' "$label"
    tail -3 "$work/out" | sed 's/^/          /'
  else
    pass=$((pass + 1))
    printf '  detected      %s\n' "$label"
    grep -m2 -E 'FAIL|expected' "$work/out" | sed 's/^/          /' || true
  fi
}

expect_green() { # <label> <command…>
  label=$1
  shift
  if "$@" > "$work/out" 2>&1; then
    pass=$((pass + 1))
    printf '  clean         %s\n' "$label"
  else
    fail=$((fail + 1))
    printf '  UNEXPECTED RED %s\n' "$label"
    tail -5 "$work/out" | sed 's/^/          /'
  fi
}

# Flip one byte in place, in a way that leaves the file otherwise plausible.
corrupt() { # <file> <from> <to>
  python3 - "$1" "$2" "$3" <<'PY'
import sys
path, old, new = sys.argv[1], sys.argv[2].encode(), sys.argv[3].encode()
data = open(path, 'rb').read()
assert data.count(old) == 1, f"{path}: {old!r} occurs {data.count(old)} times"
assert len(old) == len(new)
open(path, 'wb').write(data.replace(old, new))
PY
}

printf 'baseline: the untouched copy is green\n'
expect_green "reference checks"  python3 "$work/tools/check.py"
expect_green "POSIX-shell walker" sh "$work/tools/walk-vectors.sh"
printf '\n'

# --- 1. one byte of a canonical payload ------------------------------------
# `untracked = false` -> `untracked = falsE`. The file still parses as TOML
# in shape, and no human reading it would notice.
printf '1. one byte flipped in vectors/payload/minimal/canonical.txt\n'
target=$work/vectors/payload/minimal/canonical.txt
cp "$target" "$work/payload.orig"
corrupt "$target" 'untracked = false' 'untracked = falsE'
expect_red "reference serializer disagrees" \
  python3 "$work/tools/check.py" payload
expect_red "jq serializer disagrees" \
  sh "$work/tools/walk-vectors.sh" payload
cp "$work/payload.orig" "$target"
printf '\n'

# --- 2. one byte of a signature --------------------------------------------
printf '2. one base64 character changed in vectors/signature/minimal/signature.b64\n'
target=$work/vectors/signature/minimal/signature.b64
cp "$target" "$work/sig.orig"
# The first payload byte of the blob after the fixed SSHSIG header; any single
# change is enough, and this one keeps the base64 well-formed.
corrupt "$target" 'U1NIU0lH' 'U1NIU0lI'
expect_red "reference signature check" \
  python3 "$work/tools/check.py" signature
expect_red "ssh-keygen via the shell walker" \
  sh "$work/tools/walk-vectors.sh" signature
cp "$work/sig.orig" "$target"
printf '\n'

# --- 3. one byte of a certificate inside a verification vector -------------
# The certificate still parses, still claims the right targets on the right
# platform, and is still signed by an active registered key. Only the
# signature bytes are wrong, so a verifier that skipped the signature check
# would still report `covered` — which is the point of corrupting it here
# rather than in the signature group.
printf '3. one byte of a signature inside vectors/verify/coverage-union\n'
target=$work/vectors/verify/coverage-union/certificates/a-unit.toml
cp "$target" "$work/cert.orig"
corrupt "$target" 'value = "U1NIU0lH' 'value = "U1NIU0lI'
expect_red "reference verifier stops reporting covered" \
  python3 "$work/tools/check.py" verify
expect_red "shell walker stops reporting covered" \
  sh "$work/tools/walk-vectors.sh" verify
cp "$work/cert.orig" "$target"
printf '\n'

# --- 4. the §7.1 relevance distinction -------------------------------------
# Not a byte flip but a property flip, and the only one of these corruptions
# that a fully working signature check would sail straight past.
#
# `unknown-schema-off-platform` reports unverifiable *because* its record
# cannot be interpreted: its platform and targets look irrelevant, but a v1
# parser is not entitled to that reading. Declare the very same record v1 and
# the reading becomes legitimate, the record becomes provably irrelevant, and
# the outcome MUST fall to not-covered. An implementation that assumed every
# unevaluable record was decisive would report unverifiable both ways and
# never notice.
printf '4. schema version flipped in vectors/verify/unknown-schema-off-platform\n'
target=$work/vectors/verify/unknown-schema-off-platform/certificates/future-macos.toml
cp "$target" "$work/schema.orig"
corrupt "$target" 'schema = "test-certificate.v2"' 'schema = "test-certificate.v1"'
expect_red "reference verifier stops reporting unverifiable" \
  python3 "$work/tools/check.py" verify
expect_red "shell walker stops reporting unverifiable" \
  sh "$work/tools/walk-vectors.sh" verify
cp "$work/schema.orig" "$target"
printf '\n'

printf '%d as expected, %d wrong\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
