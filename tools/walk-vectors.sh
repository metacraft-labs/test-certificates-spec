#!/bin/sh
# Walk the whole vector suite with nothing but POSIX shell, jq, ssh-keygen,
# git and sha256sum.
#
# NON-NORMATIVE, and a DEMONSTRATION rather than a harness. See tools/README.md.
# No implementation of the standard is expected to invoke this script; each one
# writes its own thin walker in its own language (Conformance.md, "Using the
# suite"). What this script is for is proving the claim that makes that
# possible: the vectors are plain data, and consuming them needs no
# language-specific tooling and no code from this repository.
#
# It is also a second, independent serializer. tools/reference_serializer.py is
# written in Python against Canonical-Payload.md; the jq program below is
# written separately against the same document. When both agree with the
# hand-derived bytes in vectors/payload/*/canonical.txt, three independent
# derivations agree.
#
# Likewise for content ids: tools/reference_content_id.py builds git objects
# by hand in Python, while the content group below asks git itself (the
# Content-Id.md §4.1 recipe, verbatim) and derives manifest-v1 with printf and
# sha256sum.
#
# Store paths (Transport.md §2.2) are derived with sed, shell parameter
# expansion and sha256sum, against expected-path.txt files written by hand.
#
# Usage:
#   sh tools/walk-vectors.sh                    # all five groups
#   sh tools/walk-vectors.sh payload signature  # selected groups
#
# Exit status is 0 when every case behaved as its vector says.

set -eu

here=$(dirname "$0")
root=$(cd "$here/.." && pwd)
vectors="$root/vectors"
namespace="test-certificate-v1"       # Standard.md §6.1
principal="vectors@test-certificates.invalid"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT INT TERM

pass=0
fail=0

ok()   { pass=$((pass + 1)); printf '  ok    %s\n' "$1"; }
bad()  { fail=$((fail + 1)); printf '  FAIL  %s\n' "$1"
         [ $# -lt 2 ] || printf '          %s\n' "$2"; }

# ---------------------------------------------------------------------------
# The canonical payload serializer, as a jq program.
#
# Two things make this shorter than it looks:
#
#   * jq's @json produces exactly a TOML basic string for every value this
#     standard permits. JSON's escape set is the same seven escapes as
#     Canonical-Payload.md §4, and jq emits non-ASCII literally, which §4
#     requires.
#   * jq's `unique` sorts and deduplicates in one step, and jq compares strings
#     by their UTF-8 bytes, which is the order §3 specifies.
# ---------------------------------------------------------------------------
cat > "$tmp/canonical.jq" <<'JQ'
def q: @json;
def arr: "[" + (map(q) | join(", ")) + "]";
def b: if . then "true" else "false" end;

. as $f
| $f.certificate as $c
| $c.vcs as $v
| [ "schema = " + ($f.schema | q),
    "",
    "[certificate]",
    "framework = "  + ($c.framework  | q),
    "project = "    + ($c.project    | q),
    "platform = "   + ($c.platform   | q),
    "targets = "    + ($c.targets | unique | arr),
    "result = "     + ($c.result     | q),
    "issued_at = "  + ($c.issued_at  | q),
    "issuer = "     + ($c.issuer     | q) ]
  # §2 rule 3: omitted entirely when unsigned, never emitted empty.
+ (if $c.key_id == null then [] else [ "key_id = " + ($c.key_id | q) ] end)
+ [ "",
    "[certificate.vcs]",
    "repo = " + ($v.repo | q) ]
  # §2 rule 8: an empty scope is a whole-repository claim; the key is dropped.
+ (if (($v.paths // []) | length) == 0 then []
   else [ "paths = " + ($v.paths | unique | arr) ] end)
  # §2 rule 9: content verbatim. Rule 4: untracked is a bare boolean.
+ [ "content = "   + ($v.content   | q),
    "untracked = " + ($v.untracked | b) ]
  # §2 rule 10: base is last, and omitted entirely when absent.
+ (if $v.base == null then [] else [ "base = " + ($v.base | q) ] end)
  # §2 rules 6 and 7: execution order, one blank line each, argv untouched.
+ ($c.command | map([ "", "[[certificate.command]]", "argv = " + (.argv | arr) ])
              | add)
| join("\n") + "\n"
JQ

# ---------------------------------------------------------------------------
# Group 1: canonical payload
# ---------------------------------------------------------------------------
walk_payload() {
  printf 'payload: serialize fields.json with jq and compare bytes\n'
  for d in "$vectors"/payload/*/; do
    name=$(basename "$d")
    jq -j -f "$tmp/canonical.jq" "$d/fields.json" > "$tmp/got"
    if cmp -s "$tmp/got" "$d/canonical.txt"; then
      ok "payload/$name"
    else
      bad "payload/$name" "$(cmp "$tmp/got" "$d/canonical.txt" 2>&1 | head -1)"
    fi
  done
}

# ---------------------------------------------------------------------------
# Group 2: signatures
#
# `signature.b64` holds the base64 blob a certificate's `signature.value`
# carries (Standard.md §6.1). ssh-keygen reads the armored form, and the
# conversion is pure framing: BEGIN line, the blob, END line.
# ---------------------------------------------------------------------------
armor() {
  printf -- '-----BEGIN SSH SIGNATURE-----\n'
  cat "$1"
  printf -- '-----END SSH SIGNATURE-----\n'
}

ssh_verify() { # <payload-file> <pubkey-file> <sig.b64-file> <namespace>
  printf '%s %s\n' "$principal" "$(cat "$2")" > "$tmp/allowed_signers"
  armor "$3" > "$tmp/sig"
  ssh-keygen -Y verify -f "$tmp/allowed_signers" -I "$principal" \
             -n "$4" -s "$tmp/sig" < "$1" 2>&1
}

walk_signature() {
  printf 'signature: verify each vector with ssh-keygen\n'
  saw_fail=0
  for d in "$vectors"/signature/*/; do
    name=$(basename "$d")
    [ "$name" = keys ] && continue
    expect=$(cat "$d/expect.txt")
    [ "$expect" = fail ] && saw_fail=1

    if out=$(ssh_verify "$d/canonical.txt" "$d/key.pub" \
                        "$d/signature.b64" "$namespace"); then
      got=verify
    else
      got=fail
    fi
    if [ "$got" = "$expect" ]; then
      ok "signature/$name ($expect)"
    else
      bad "signature/$name: expected $expect, got $got" "$out"
    fi

    # The wrong-namespace vector has to fail for the right reason. A vector
    # that failed because its bytes differ would say nothing about domain
    # separation.
    if [ "$name" = wrong-namespace ]; then
      case "$out" in
        *"namespace does not match"*)
          ok "signature/wrong-namespace fails on the namespace, not the bytes";;
        *) bad "signature/wrong-namespace failed for the wrong reason" "$out";;
      esac
      if ssh_verify "$d/canonical.txt" "$d/key.pub" "$d/signature.b64" git \
           > /dev/null 2>&1; then
        ok "signature/wrong-namespace is genuine under its own namespace"
      else
        bad "signature/wrong-namespace is not a genuine signature at all"
      fi
    fi
  done
  [ "$saw_fail" = 1 ] \
    && ok "at least one signature vector must fail" \
    || bad "no signature vector is expected to fail"
}

# ---------------------------------------------------------------------------
# Group 3: content ids
#
# git-tree ids come from git: every entry is written as an object with
# `git hash-object -w`, staged into a scratch index with
# `git update-index --index-info`, and the tree is `git write-tree`. A scoped
# id follows Content-Id.md §4.1 to the letter. manifest-v1 is printf and
# sha256sum.
#
# Contents are decoded with jq's @base64d, which yields a string, so this
# walker can only handle entries whose content is valid UTF-8 without NUL.
# Every entry in the suite is. A walker in a real language has no such limit.
# ---------------------------------------------------------------------------
tab=$(printf '\t')

# jq: the entries in scope, as "index<TAB>mode<TAB>path", in byte order.
# jq compares strings by their UTF-8 bytes, the order Content-Id.md §4.2 needs.
cat > "$tmp/inscope.jq" <<'JQ'
($scope[0]) as $s
| to_entries
| map(select(.value.path as $p
             | ($s == null) or (($s | length) == 0)
               or any($s[]; . as $x | $p == $x or ($p | startswith($x + "/")))))
| sort_by(.value.path)
| .[]
| "\(.key)\t\(.value.mode)\t\(.value.path)"
JQ

manifest_id() { # <case dir> -> manifest-v1-sha256 digest
  jq -r --slurpfile scope "$tmp/scope.json" -f "$tmp/inscope.jq" \
     "$1/entries.json" > "$tmp/inscope"
  : > "$tmp/records"
  while IFS="$tab" read -r idx mode path; do
    hex=$(sha256sum < "$tmp/blob.$idx" | cut -d' ' -f1)
    printf '%s %s %s\0' "$mode" "$hex" "$path" >> "$tmp/records"
  done < "$tmp/inscope"
  sha256sum < "$tmp/records" | cut -d' ' -f1
}

git_tree_id() { # <case dir> <object format> -> tree id
  repo=$tmp/repo
  rm -rf "$repo" "$tmp/index" "$tmp/scoped-index"
  git init -q --object-format="$2" "$repo"
  jq -r --slurpfile scope "$tmp/null.json" -f "$tmp/inscope.jq" \
     "$1/entries.json" > "$tmp/all"
  : > "$tmp/index-info"
  while IFS="$tab" read -r idx mode path; do
    if [ "$mode" = 160000 ]; then
      oid=$(cat "$tmp/blob.$idx")   # a gitlink records the revision itself
    else
      oid=$(git -C "$repo" hash-object -w --stdin < "$tmp/blob.$idx")
    fi
    printf '%s %s\t%s\0' "$mode" "$oid" "$path" >> "$tmp/index-info"
  done < "$tmp/all"
  GIT_INDEX_FILE=$tmp/index git -C "$repo" update-index -z --index-info \
    < "$tmp/index-info"
  T=$(GIT_INDEX_FILE=$tmp/index git -C "$repo" write-tree)
  if [ "$(jq 'length' "$tmp/scope.json")" = 0 ] \
     || [ "$(jq -c '.' "$tmp/scope.json")" = null ]; then
    printf '%s\n' "$T"
    return
  fi
  set --
  while IFS= read -r p; do set -- "$@" "$p"; done <<EOF
$(jq -r '.[]' "$tmp/scope.json")
EOF
  GIT_INDEX_FILE=$tmp/scoped-index git -C "$repo" read-tree --empty
  git -C "$repo" --literal-pathspecs ls-tree -r -z --full-tree "$T" -- "$@" \
    | GIT_INDEX_FILE=$tmp/scoped-index git -C "$repo" update-index -z \
        --index-info
  GIT_INDEX_FILE=$tmp/scoped-index git -C "$repo" write-tree
}

walk_content() {
  printf 'content: compute each id with git and sha256sum, compare\n'
  printf 'null\n' > "$tmp/null.json"
  for d in "$vectors"/content/*/; do
    d=${d%/}
    name=$(basename "$d")
    n=$(jq length "$d/entries.json")
    i=0
    while [ "$i" -lt "$n" ]; do
      jq -j --argjson i "$i" '.[$i].content_b64 | @base64d' \
         "$d/entries.json" > "$tmp/blob.$i"
      i=$((i + 1))
    done
    count=$(jq length "$d/expected.json")
    k=0
    while [ "$k" -lt "$count" ]; do
      alg=$(jq -r --argjson k "$k" '.[$k].algorithm' "$d/expected.json")
      want=$(jq -r --argjson k "$k" '.[$k].id' "$d/expected.json")
      jq -c --argjson k "$k" '.[$k].paths' "$d/expected.json" \
        > "$tmp/scope.json"
      label="content/$name $alg $(cat "$tmp/scope.json")"
      case "$alg" in
        manifest-v1-sha256) got=$alg:$(manifest_id "$d");;
        git-tree-sha1)      got=$alg:$(git_tree_id "$d" sha1);;
        git-tree-sha256)    got=$alg:$(git_tree_id "$d" sha256);;
        *)                  got="(unknown algorithm)";;
      esac
      if [ "$got" = "$want" ]; then
        ok "$label"
      else
        bad "$label" "got $got"
      fi
      k=$((k + 1))
    done
  done
}

# ---------------------------------------------------------------------------
# Group 4: verification decisions
#
# The certificates are in canonical form, which is line-oriented and has one
# `key = value` per line, so `sed` is enough to read them here. A real verifier
# MUST NOT work this way: Canonical-Payload.md §5 requires it to reconstruct
# the payload from parsed fields, because a received certificate may be
# formatted differently and must still verify. See
# vectors/payload/escapes/received.toml for a certificate that would defeat
# every sed expression below and must nonetheless verify.
# ---------------------------------------------------------------------------
tval()  { sed -n "s/^$2 = \"\(.*\)\"\$/\1/p" "$1" | head -1; }
tbool() { sed -n "s/^$2 = \(true\|false\)\$/\1/p" "$1" | head -1; }
tlist() { # array of strings -> one element per line
  sed -n "s/^$2 = \[\(.*\)\]\$/\1/p" "$1" | head -1 \
    | sed 's/", "/\n/g; s/^"//; s/"$//'
}

# The payload a signature covers: the file without its signature block.
# Command substitution strips trailing newlines; printf puts exactly one back.
cert_payload() {
  printf '%s\n' "$(sed '/^\[certificate\.signature\]$/,$d' "$1")"
}

# A key store this reader understands: comments, blanks, and the four line
# shapes Verification.md §3.1 defines. Anything else and it cannot answer,
# which is a different thing from answering "nobody is trusted".
store_readable() {
  [ -f "$1" ] || return 0
  grep -vE '^[[:space:]]*(#.*)?$' "$1" \
    | grep -qvE '^(schema = "[^"]*"|\[\[key\]\]|(key_id|public_key|status) = "[^"]*")$' \
    && return 1
  [ "$(tval "$1" schema)" = "registered-keys.v1" ] || return 1
  return 0
}

# Could this record, if it had verified, have met part of the requirement?
# (§7.1) Only ever asked of a record we can INTERPRET — never of one whose
# schema version we do not implement, where the fields would be read with the
# wrong parser.
could_satisfy() { # <cert> -> 0 when potentially relevant
  cs_platform=$(tval "$1" platform)
  grep -qxF "$cs_platform" "$tmp/req_platforms" || return 1
  tlist "$1" targets | sed '/^$/d' > "$tmp/cert_targets"
  grep -qxFf "$tmp/cert_targets" "$tmp/req_targets"
}

store_lookup() { # <store> <key_id> -> "status<TAB>public_key"
  awk -v want="$2" '
    /^\[\[key\]\]$/            { id=""; st=""; pk=""; next }
    /^key_id = /               { id=$0; sub(/^key_id = "/,"",id);     sub(/"$/,"",id) }
    /^status = /               { st=$0; sub(/^status = "/,"",st);     sub(/"$/,"",st) }
    /^public_key = /           { pk=$0; sub(/^public_key = "/,"",pk); sub(/"$/,"",pk) }
    { if (id == want && st != "" && pk != "") { print st "\t" pk; exit } }
  ' "$1"
}

decide() { # <case dir> -> prints the outcome
  case_dir=$1
  st=$case_dir/state.json
  rq=$case_dir/requirement.json
  store=$case_dir/registered-keys.toml

  s_repo=$(jq -r .repo "$st")
  r_framework=$(jq -r .framework "$rq")
  r_signature=$(jq -r .require_signature "$rq")
  jq -r '.frameworks_implemented[]' "$rq" > "$tmp/implemented"
  jq -r '.targets[]'   "$rq" > "$tmp/req_targets"
  jq -r '.platforms[]' "$rq" > "$tmp/req_platforms"
  # `(.paths // [])[]` and not `if .paths == null then "" else …`: the latter
  # writes a blank line, which makes the file non-empty, which makes an
  # emptiness test read "a scope was required" when none was. That mistake
  # turns vectors/verify/scope-too-narrow from not-covered into covered.
  jq -r '(.paths // [])[]' "$rq" > "$tmp/req_paths"

  store_ok=1
  store_readable "$store" || store_ok=0

  : > "$tmp/contrib"      # surviving "platform<TAB>target" pairs
  blocking=0              # a POTENTIALLY RELEVANT record could not be evaluated

  for cert in "$case_dir"/certificates/*.toml; do
    fw=$(tval "$cert" framework)
    # §2: framework filtering comes first. Unimplemented -> ignored, silently.
    grep -qxF "$fw" "$tmp/implemented" || continue
    [ "$fw" = "$r_framework" ] || continue

    # An unimplemented schema version is an evaluation breakdown (§7), not a
    # verdict about coverage -- and it is ALWAYS potentially relevant (§7.1).
    # Reading this record's platform or targets to rule it out would mean
    # trusting a v1 parser on a record we just said we cannot interpret.
    if [ "$(tval "$cert" schema)" != "test-certificate.v1" ]; then
      blocking=1; continue
    fi
    [ "$(tval "$cert" result)" = passed ] || continue
    [ "$(tval "$cert" repo)" = "$s_repo" ] || continue

    # Scope (§4.1.2). A certificate with no `paths` covers everything; a
    # scoped one covers a required path only if that path is inside its scope.
    # Decidable from the record alone, so it precedes the content match.
    : > "$tmp/cert_paths"
    if grep -q '^paths = ' "$cert"; then
      tlist "$cert" paths > "$tmp/cert_paths"
      [ -s "$tmp/req_paths" ] || continue      # whole repository required
      uncovered=0
      while IFS= read -r want; do
        [ -n "$want" ] || continue
        inside=0
        while IFS= read -r have; do
          case "$want" in "$have"|"$have"/*) inside=1;; esac
        done < "$tmp/cert_paths"
        [ "$inside" = 1 ] || uncovered=1
      done < "$tmp/req_paths"
      [ "$uncovered" = 0 ] || continue
    fi

    # Content (§4.1.1). `base` is never looked at. The form is checked first,
    # and a malformed id is decidably invalid -- never lowercased, never
    # matched as an abbreviation, never assumed to be git-tree-sha1.
    cid=$(tval "$cert" content)
    [ -n "$cid" ] || continue                  # no content: an earlier draft
    case "$cid" in *:*) ;; *) continue;; esac  # no algorithm
    alg=${cid%%:*}                             # up to the FIRST ':'
    dig=${cid#*:}
    [ -n "$alg" ] || continue
    case "$dig" in ''|*[!0123456789abcdef]*) continue;; esac
    case "$alg" in
      git-tree-sha1) [ "${#dig}" -eq 40 ] || continue;;
      git-tree-sha256|manifest-v1-sha256) [ "${#dig}" -eq 64 ] || continue;;
    esac
    # An algorithm state.json does not list is one this consumer cannot
    # compute: not a mismatch, but an evaluation breakdown. The record is
    # interpretable, so §7.1 lets us ask whether it could have mattered.
    if ! jq -e --arg a "$alg" 'any(.content[]; .algorithm == $a)' "$st" \
         > /dev/null; then
      if could_satisfy "$cert"; then blocking=1; fi
      continue
    fi
    want_id=$(jq -r --arg a "$alg" --rawfile p "$tmp/cert_paths" '
        ($p | split("\n") | map(select(. != "")) | unique) as $scope
        | [ .content[]
            | select(.algorithm == $a and ((.paths // []) | unique) == $scope)
            | .id ][0] // ""' "$st")
    if [ -z "$want_id" ]; then
      printf 'vector-error: state.json lists %s but not this scope\n' "$alg"
      return
    fi
    [ "$cid" = "$want_id" ] || continue

    # Authenticity (§3).
    if [ "$r_signature" = true ]; then
      key_id=$(tval "$cert" key_id)
      sig=$(tval "$cert" value)
      alg=$(tval "$cert" algorithm)
      # Canonical-Payload.md §6: absent block and empty block both mean unsigned.
      [ -n "$key_id" ] && [ -n "$sig" ] && [ -n "$alg" ] || continue
      if [ "$store_ok" = 0 ]; then
        # The store could not answer, but this record is interpretable, so
        # §7.1 lets us say whether that answer could have mattered.
        if could_satisfy "$cert"; then blocking=1; fi
        continue
      fi
      entry=$(store_lookup "$store" "$key_id")
      [ -n "$entry" ] || continue              # fail-closed (§3.1)
      status=$(printf '%s' "$entry" | cut -f1)
      pubkey=$(printf '%s' "$entry" | cut -f2)
      [ "$status" = active ] || continue       # revoked (§3.1)
      [ "$alg" = ed25519 ] || continue
      cert_payload "$cert" > "$tmp/payload"
      printf '%s\n' "$pubkey" > "$tmp/pub"
      printf '%s\n' "$sig" > "$tmp/sigb64"
      ssh_verify "$tmp/payload" "$tmp/pub" "$tmp/sigb64" "$namespace" \
        > /dev/null 2>&1 || continue
    fi

    platform=$(tval "$cert" platform)
    tlist "$cert" targets | while IFS= read -r t; do
      [ -n "$t" ] && printf '%s\t%s\n' "$platform" "$t"
    done >> "$tmp/contrib"
  done

  # Coverage is a union, per platform (§5).
  covered=1
  while IFS= read -r platform; do
    [ -n "$platform" ] || continue
    while IFS= read -r target; do
      [ -n "$target" ] || continue
      grep -qxF "$(printf '%s\t%s' "$platform" "$target")" "$tmp/contrib" \
        || covered=0
    done < "$tmp/req_targets"
  done < "$tmp/req_platforms"

  # Precedence (§7.1): covered when the requirement is met by what was fully
  # evaluated -- v1 coverage is monotonic, so an unread record could only have
  # added to it. Otherwise a breakdown outranks not-covered, but only for a
  # record that was potentially relevant.
  if [ "$covered" = 1 ]; then
    printf 'covered\n'
  elif [ "$blocking" = 1 ]; then
    printf 'unverifiable\n'
  else
    printf 'not-covered\n'
  fi
}

walk_verify() {
  printf 'verify: decide each case and compare the three-valued outcome\n'
  for d in "$vectors"/verify/*/; do
    name=$(basename "$d")
    want=$(jq -r .outcome "$d/expected.json")
    got=$(decide "$d")
    if [ "$got" = "$want" ]; then
      ok "verify/$name -> $want"
    else
      bad "verify/$name: expected $want, got $got"
    fi
  done
}

# ---------------------------------------------------------------------------
# Group 5: store paths
#
# Transport.md §2.2 with sed and sha256sum: the content id split at its FIRST
# `:` by shell parameter expansion, and the name the SHA-256 of the canonical
# payload. This walker has no TOML parser, so it takes the payload from the
# case's canonical.txt and then ties canonical.txt to certificate.toml in the
# two ways open to it: a certificate in canonical form must be canonical.txt
# plus at most a signature block, and a signed one must carry a signature that
# ssh-keygen verifies over canonical.txt. A walker with a TOML parser rebuilds
# the payload from certificate.toml itself (Canonical-Payload.md §5), as
# tools/check.py does.
# ---------------------------------------------------------------------------
# A string value from a certificate in any rendering this suite uses: basic or
# literal quotes, any spacing around `=`, LF or CRLF.
tany() {
  tr -d '\r' < "$1" \
    | sed -n "s/^[[:space:]]*\"\{0,1\}$2\"\{0,1\}[[:space:]]*=[[:space:]]*[\"']\([^\"']*\)[\"'][[:space:]]*\$/\1/p" \
    | head -1
}

store_pub() { # <key_id> -> the published public key file, or nothing
  case "$1" in
    example-key-2026-q2) printf '%s\n' "$vectors/signature/keys/insecure-test-key.pub";;
  esac
}

walk_store() {
  printf 'store: derive each path with sed and sha256sum, compare\n'
  for d in "$vectors"/store/*/; do
    d=${d%/}
    name=$(basename "$d")

    # expected-path.txt is exactly one LF-terminated line.
    if [ "$(wc -l < "$d/expected-path.txt")" -eq 1 ] \
       && [ "$(tail -c 1 "$d/expected-path.txt" | od -An -c | tr -d ' ')" = '\n' ]; then
      want=$(cat "$d/expected-path.txt")
    else
      bad "store/$name: expected-path.txt is not one LF-terminated line"
      continue
    fi

    cid=$(tval "$d/canonical.txt" content)
    alg=${cid%%:*}                             # up to the FIRST ':'
    dig=${cid#*:}
    hash=$(sha256sum < "$d/canonical.txt" | cut -d' ' -f1)
    got="v1/$alg/$dig/$hash.toml"
    if [ "$got" = "$want" ]; then
      ok "store/$name -> $want"
    else
      bad "store/$name: path differs" "got $got"
    fi

    # The trap: the file's own hash is never the name, unless the file IS the
    # payload (an unsigned certificate in canonical form, with no block).
    filehash=$(sha256sum < "$d/certificate.toml" | cut -d' ' -f1)
    if cmp -s "$d/certificate.toml" "$d/canonical.txt" \
       || [ "$filehash" != "$hash" ]; then
      ok "store/$name: the name is the payload's hash, not the file's"
    else
      bad "store/$name: the file hashes to the name but is not the payload"
    fi

    # Tie canonical.txt to certificate.toml.
    tied=0
    cert_payload "$d/certificate.toml" > "$tmp/store-payload"
    if cmp -s "$tmp/store-payload" "$d/canonical.txt"; then
      ok "store/$name: canonical form, payload is the file minus its signature block"
      tied=1
    fi
    sig=$(tany "$d/certificate.toml" value)
    if [ -n "$sig" ]; then
      key_id=$(tany "$d/certificate.toml" key_id)
      pub=$(store_pub "$key_id")
      if [ -z "$pub" ]; then
        bad "store/$name: no published key for key_id '$key_id'"
      elif printf '%s\n' "$sig" > "$tmp/store-sig" \
           && ssh_verify "$d/canonical.txt" "$pub" "$tmp/store-sig" \
                         "$namespace" > "$tmp/store-out" 2>&1; then
        ok "store/$name: its signature verifies over canonical.txt"
        tied=1
      else
        bad "store/$name: its signature does not verify over canonical.txt" \
            "$(head -1 "$tmp/store-out")"
      fi
    fi
    if [ "$tied" = 0 ]; then
      printf '  note  store/%s: non-canonical and unsigned; canonical.txt is\n' "$name"
      printf '          its payload only on tools/check.py'"'"'s TOML reconstruction\n'
    fi
  done
}

# ---------------------------------------------------------------------------
groups=${*:-"payload signature content verify store"}
for g in $groups; do
  case "$g" in
    payload)   walk_payload;;
    signature) walk_signature;;
    content)   walk_content;;
    verify)    walk_verify;;
    store)     walk_store;;
    *) printf 'unknown group: %s\n' "$g" >&2; exit 2;;
  esac
  printf '\n'
done

printf '%d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
