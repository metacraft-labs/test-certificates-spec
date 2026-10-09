# Content Identifiers

A certificate is bound to the **content of the version-controlled files** the
tests ran against, not to a commit ([Standard §2](./Standard.md#2-why-content-is-the-whole-binding)).
This document defines how that content is identified: the value of
`[certificate.vcs] content`.

Everything below is normative. A producer and a verifier that compute a content
id differently do not disagree loudly — the verifier simply finds that nothing
matches, and reports the state as untested.

## 1. Form

A content id is **self-describing**: it names the algorithm that produced it,
then the digest.

```
<algorithm>:<digest>
```

- `<algorithm>` is one of the identifiers in §4, compared by exact string
  equality.
- `<digest>` is **lowercase** hexadecimal, of exactly the length the algorithm
  defines.

The algorithm is everything before the **first** `:`, and the digest is
everything after it. A content id is **malformed** when it has no `:`, nothing
before the `:`, a digest that is empty or contains anything but `0`–`9` and
`a`–`f`, or — for an algorithm in §4 — a digest of the wrong length. A
malformed id is decidably invalid
([Verification §4.1.1](./Verification.md#411-matching-content)). A verifier
MUST NOT repair one into validity — by lowercasing an uppercase digest, by
matching an abbreviated digest as git matches abbreviated object ids, or by
assuming an algorithm for a bare digest.

A well-formed id naming an algorithm that is **not** in §4 is not malformed.
Its digest length cannot be judged, since only the algorithm defines it, and a
later revision may define the algorithm. A verifier treats it as an algorithm
it cannot compute (§5). Producers MUST NOT emit one.

The algorithm is part of the claim. Two content ids with different algorithms
are never compared, even where both describe the same files: a verifier
evaluates a certificate by computing **the certificate's** algorithm over the
state in front of it, or reports that it cannot (§5).

## 2. What is identified

The identified state is the set of **tracked** files within the certificate's
scope ([Standard §3.2.1](./Standard.md#321-scoping-the-claim-to-paths)), each
with the content and mode it had **in the working tree** when the commands
executed.

- **Tracked** means known to the VCS at execution time. In git, that is every
  index entry — including a file added with `git add` and not yet committed.
  Untracked and ignored files are **not** part of the content. Whether
  untracked files were present is reported separately, in `untracked`
  ([Standard §3.2](./Standard.md#32-certificatevcs)).
- **Working-tree content**, not the last committed or staged content. A modified
  tracked file contributes its modified bytes; a tracked file deleted from the
  working tree contributes nothing.
- **As the VCS would record it.** Content is taken in the form the VCS would
  store if the file were committed now, after its normalisation — line-ending
  conversion and clean filters, in git's case. Two working trees that differ
  only in ways the VCS normalises away have the same content id, which is the
  point: they would produce the same commit.

The state is identified **at execution time**. A content id computed before the
run, with edits in between, identifies something that was never tested
([Standard §3.2](./Standard.md#32-certificatevcs)).

## 3. When there is no content id

Some working-tree states have no content id that identifies them honestly. A
producer MUST NOT issue a certificate when, within scope:

- **The index has unmerged entries.** A conflicted path has no single content.
  (`git write-tree` refuses, for the same reason.)
- **The VCS has been told not to look.** An entry marked `assume-unchanged`, or
  marked `skip-worktree` while the file is present in the working tree, has
  working-tree content git will not observe — so the content id would describe
  the indexed bytes while the tests read different ones.
- **A nested repository has modified content.** A nested repository is
  identified by its checked-out revision alone (§4). Uncommitted changes inside
  it are not represented, so a content id would attest a state the tests did
  not see.
- **A path cannot be represented** — a path containing NUL, for `manifest-v1`.

Refusing is the only conforming response. A content id that silently omits what
the tests read is a certificate that is formally valid and substantively false.

## 4. Algorithms

| Algorithm | Digest | Use |
| --------- | ------ | --- |
| `git-tree-sha1` | 40 hex digits | git repositories using the SHA-1 object format |
| `git-tree-sha256` | 64 hex digits | git repositories using the SHA-256 object format |
| `manifest-v1-sha256` | 64 hex digits | any VCS; defined in full in §4.2 |

A producer in a git repository SHOULD use the `git-tree-*` algorithm matching
the repository's object format. It is what git already computes for every
commit, a verifier can compute it with plumbing git ships, and it lets
certificates be keyed by a git object ([Transport §3](./Transport.md#3-git-notes-recommended-for-pushing)).
`manifest-v1-sha256` is for every other VCS, and for any producer that wants an
identifier with no VCS dependency at all.

### 4.1 `git-tree-sha1` and `git-tree-sha256`

The digest is the **git tree object id** of the identified state (§2), under the
repository's object format — the tree a commit of exactly that state would
record.

**Unscoped**, this is what `git write-tree` returns for an index holding the
state. Producers SHOULD compute it in a **temporary index**, so the user's
staging area is neither read as the tested state nor modified:

```sh
tmp=$(mktemp)
cp "$(git rev-parse --git-path index)" "$tmp"   # start from what is tracked
GIT_INDEX_FILE=$tmp git add --update -- :/      # take working-tree content
GIT_INDEX_FILE=$tmp git write-tree              # the content id's digest
```

`git add --update` refreshes every tracked entry from the working tree and
removes deleted ones, and adds nothing untracked — which is §2 exactly. A
repository with no index yet tracks nothing; its content is the empty tree.

**Scoped**, the digest is the id of the tree holding **only the in-scope
entries, at their full repository paths**. Starting from the unscoped tree `T`:

```sh
GIT_INDEX_FILE=$scoped git read-tree --empty
git --literal-pathspecs ls-tree -r -z --full-tree "$T" -- <paths…> \
  | GIT_INDEX_FILE=$scoped git update-index -z --index-info
GIT_INDEX_FILE=$scoped git write-tree
```

Two consequences implementers get wrong:

- A scoped id is **not** the id of the subtree at a scoped directory. Scoping
  `src/db` yields a tree containing `src/`, containing `db/` — not the tree
  object `T:src/db`, which has lost its path. Keeping full paths is what makes
  scopes `["src/db"]` and `["lib/db"]` distinct when their directories happen
  to hold identical files.
- Pathspecs MUST be literal. A scoped path containing `*`, `?` or `[` names that
  file, not a pattern.

A scope matching no tracked entry yields the empty tree, whose id is well
defined (`4b825dc642cb6eb9a060e54bf8d69288fbee4904` under SHA-1).

A nested repository (a git submodule) appears as the gitlink entry git records
for it: its checked-out commit. §3 forbids issuance when its content is
modified.

### 4.2 `manifest-v1-sha256`

A VCS-independent identifier, defined so that two machines listing the same
files in different orders compute the same digest.

**Entries.** One entry per tracked path in scope, each a triple
`(path, mode, content)`:

| Mode | Meaning | `content` |
| ---- | ------- | --------- |
| `100644` | regular file | its bytes, as the VCS would record them (§2) |
| `100755` | executable file | its bytes, as the VCS would record them |
| `120000` | symbolic link | the link target as a byte string, unresolved |
| `160000` | nested repository | its checked-out revision id as the nested VCS spells it, in ASCII (lowercase hex, for git) |

The modes are git's, chosen because they are already familiar, not because the
algorithm depends on git. Directories are not entries; an empty directory
contributes nothing, as it does in every mainstream VCS.

`path` is repo-relative, uses `/` separators, never begins with `./` or `/`, and
is the byte sequence the VCS records for the file — no Unicode normalisation,
no case folding. Paths are unique.

**Records.** Each entry serializes to one record:

```
<mode> SP <hex(sha256(content))> SP <path> NUL
```

`SP` is a single space (`0x20`), `NUL` is `0x00`, and the hex digest is
lowercase. There is no other separator, header or trailer.

**Order.** Records are concatenated in **ascending byte order of `path`** — a
plain unsigned comparison of the raw bytes, the same order
[Canonical-Payload §3](./Canonical-Payload.md#3-targets-is-sorted) uses for
`targets`, applied to the full path. It is not locale collation, and it is not
the order of a walk that sorts each directory's entry names on their own: such a
walk meets the directory `a` before the file `a.b`, and so emits `a/b` before
`a.b`, where byte order puts `a.b` (`2E`) before `a/b` (`2F`). It does coincide
with the order git lists paths in — `git ls-files`, `git ls-tree -r` — because
git sorts a directory within its tree as if its name ended in `/`, precisely so
that a recursive walk comes out in full-path byte order. Sorting is what makes
the digest independent of the order a filesystem happens to list entries in.

**Digest.** The content id is `manifest-v1-sha256:` followed by the lowercase
hex SHA-256 of the concatenated records. An empty scope is the SHA-256 of the
empty string.

**Scoped**, the entries are simply those within scope — no restructuring, since
the records already carry full paths.

## 5. Computing the id of the state under evaluation

A verifier computes the certificate's algorithm, over the certificate's scope,
for whatever state it is evaluating:

| State | Computed from |
| ----- | ------------- |
| A commit | The commit's tree (`<commit>^{tree}`), scoped as in §4 |
| A commit being made — a pre-commit gate | The index being committed, via `git write-tree`. git points `GIT_INDEX_FILE` at a temporary index for `commit -a` and `commit <paths>`, and `write-tree` honours it, so this is exactly the tree the commit will record. |
| A working tree — a status display | As a producer would (§4.1), in a temporary index |

For a commit there is nothing to normalise or refuse: the tree already holds
exactly what a producer would have computed for the same files.

A verifier that cannot compute the algorithm for the state in front of it — an
algorithm it does not implement, or `git-tree-sha256` against a repository in
the SHA-1 object format — has not established a mismatch. It reports the
certificate **unverifiable**
([Verification §7](./Verification.md#7-reporting)), not invalid.
