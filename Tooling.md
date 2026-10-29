# Reference Tooling

> **Status:** Implemented by
> [test-certificates-tools](https://github.com/metacraft-labs/test-certificates-tools).
> This document specifies a helper tool. It is not normative for producers or
> verifiers: anything it does can be done natively by following
> [Transport](./Transport.md), and conformance is decided by the vectors, not
> by using this tool.

Producers issue certificates and frameworks verify them; neither is the
business of this project, and both stay framework-specific
([Standard §4, §5](./Standard.md#4-frameworks-recognise-their-own-certificates)).
What is **not** framework-specific is the plumbing in between: finding the
local certificate store, writing to it correctly, pruning it, and propagating
certificates through git notes when content is pushed. Every adopter needs that
plumbing, it is easy to get subtly wrong — a non-atomic write, a notes ref that
is never pushed, a merge that drops another framework's records — and getting it
wrong presents as "no certificates" rather than as an error.

The `test-certificates` tool provides that plumbing, as a command-line tool and
as a library with the same operations.

## 1. What it does not do

- **It does not verify.** It never decides whether a certificate is authentic,
  matches, or covers anything. `find` returns candidates; a framework's
  verifier judges them. All its writes are relay writes (Transport §2.3, §3.1):
  it preserves an existing signed copy rather than judging its authenticity.
  A generic "is this covered?" command would be exactly
  the generic hook [Standard §5](./Standard.md#5-enforcement-is-project-specific)
  rules out.
- **It does not issue or sign.** It moves certificates other components issued.
  In particular it exposes no signing interface
  ([Standard §6.2](./Standard.md#62-issuance-integrity)).
- **It does not interpret frameworks.** It handles every framework's
  certificates identically and never drops one it does not recognise.

## 2. Store operations

Each implements the corresponding part of
[Transport §2](./Transport.md#2-the-local-certificate-store-required) exactly.

| Command | Does |
| ------- | ---- |
| `test-certificates store-root` | Prints the resolved user root and system root (Transport §2.1). |
| `test-certificates put <file>…` | Parses each file as a certificate, requires a well-formed `content`, and writes it atomically under its §2.2 name to the user root — or, with `--system <user>`, to that user's system root, for a privileged producer with no client (Transport §2.3). Prints each resulting path. For producers that would rather not implement §2.3 themselves, and for the client half of a daemon's delivery: the client pipes the certificate the daemon returned into `put -`. |
| `test-certificates find <state> [--paths <p>…]` | Prints the paths of the candidate certificates stored for a state's content id, from both roots. `<state>` is `--content <id>`, `--commit <rev>`, `--staged` or `--worktree`; the last three compute the content id as [Content-Id §5](./Content-Id.md#5-computing-the-id-of-the-state-under-evaluation) prescribes, with the repository's `git-tree-*` algorithm unless `--algorithm` says otherwise, scoped by `--paths`. The exit statuses and their precedence are defined below. |
| `test-certificates prune [--keep <n>] [--system <user>] [--paths <p>…]…` | Removes content directories beyond the newest `n` (default 20) from the user root — or from a system partition, when run by its owner — protecting the current repository's computed `HEAD` content ids as described below; each removed directory is renamed aside to a `.`-prefixed name, then deleted, and leftovers of an interrupted prune are deleted too (Transport §2.5). |

`put` and `find --content` accept every well-formed content id, including an
algorithm outside Content-Id §4. They relay and discover existing claims; they
do not issue claims or compute an unknown algorithm. They preserve both id
components verbatim. An invalid algorithm identifier is malformed: `put`
refuses it before writing, and `find --content` returns 2 before searching.
The computation forms of `find` still require an implemented algorithm.

`prune` protects the unscoped `HEAD` content id in both the repository's native
`git-tree-*` algorithm and `manifest-v1-sha256`. Each occurrence of `--paths`
declares an additional scope: its paths are interpreted together, while repeated
occurrences declare separate scopes. Both algorithms are computed for each
scope. For example, `prune --paths src lib --paths tests` protects the unscoped
state, the scope `["src", "lib"]`, and the scope `["tests"]`; it does not
implicitly protect `["src"]` or `["lib"]`. An empty `--paths` is a usage error.
`--` within a path group makes all remaining arguments literal paths in that
group, including paths beginning with `-`. Every scope the repository
declares (§3.1) is protected the same way, in both algorithms, as if it had
been given as a `--paths` group; a scope given both ways is protected once. No
scope is inferred from stored certificates.

All protected ids are computed from one fixed `HEAD` tree, including in a bare
repository; staged changes and working-tree edits do not affect them. They are
additional to the newest `n` directories, including with `--keep 0`, and apply
equally to the selected user root or system partition. Outside a repository,
or on an unborn branch, there is no automatic `HEAD` protection, and the
declared scopes are not read. An explicit scope without an available `HEAD`,
an invalid scope declaration (§3.1) in a repository with a `HEAD`, or a
failure computing a required id for an existing `HEAD`, is reported and aborts
pruning before any directory is removed, including interrupted-prune
leftovers. Scopes neither given to this invocation nor declared by the
repository, and algorithms it cannot compute, remain subject to ordinary
pruning.

`find` reports what it searched — both roots, the content id, the directories — so
"nothing found" can be told apart from "looked in the wrong place"
([Transport §5](./Transport.md#5-discovery)).

`find` uses the following exit statuses, in this order of precedence:

| Exit | Meaning |
| ---- | ------- |
| 64 | Usage error: missing or multiple state flags, an unknown argument, a missing option operand (including an empty `--paths`), or `--paths` / `--algorithm` with `--content`. Syntax is checked before computing an id or searching. |
| 2 | The content id could not be computed or an explicit `--content` id is malformed; neither root was searched. |
| 0 | At least one candidate was found, including when the other root could not be read or resolved. The problem is still reported. |
| 3 | No candidate was found and at least one root could not be read or resolved. A directory that cannot be read on the way to or at the content directory makes that root's search incomplete too. |
| 1 | No candidate was found and both roots were searched without a root resolution or directory reading failure. A missing root, missing content directory or empty directory counts as a completed empty search. |

An unreadable root does not stop the search of the other root. Status 3 says
that discovery was incomplete; it does not prove there are no certificates.
The library exposes the same distinction between a completed empty search and
an incomplete empty search. These statuses concern discovery, never whether a
candidate verifies (§1).

## 3. Propagating through git notes

The local store does not leave the machine. These commands move certificates
between it and the notes ref described in
[Transport §3](./Transport.md#3-git-notes-recommended-for-pushing).

The notes ref defaults to `refs/notes/test-certificates/certificates` and is
set per repository with `git config testCertificates.notesRef <ref>`, so a
project whose tooling already uses a vendor ref keeps it.

| Command | Does |
| ------- | ---- |
| `test-certificates notes publish <commit>…` | For each commit, and for each of the commit's trees (§3.1) — `<commit>^{tree}` and the scoped tree of every scope the repository declares — finds the store's certificates for that tree's content id and adds them to the note on that tree oid, framed per Transport §3.1 (canonical records, each preceded by the `# --- test-certificate ---` delimiter line). Records already in the note are kept; a record is identified by its payload hash, so publishing twice adds nothing. Accepts revision ranges. Writes the local ref only. |
| `test-certificates notes import [<commit>…]` | The reverse: copies certificates from the notes on each commit's trees (§3.1; default `HEAD`) into the user root. A fresh clone, or a reviewer's machine, gets the certificates that travelled with a push. |
| `test-certificates notes push <remote>` | Pushes the notes ref. When the remote ref has moved, fetches it, merges with the union of both sides' records — never one side's — and retries a bounded number of times. |
| `test-certificates notes fetch <remote>` | Fetches the remote notes ref into the local one, merging the same way. |

`notes push` runs the repository's `pre-push` hook like any ordinary git
push; it does not pass `--no-verify`. A caller that is itself a `pre-push`
hook must suppress that invocation with `--no-verify` instead (§4). The
library exposes this choice as `PushOptions.runHooks`, true by default;
the hook sets it to false.

For an identical payload, record publication, import and merging apply the
relay replacement rule (Transport §2.3, §3.1). A signed copy upgrades an
unsigned one, but a differing signed copy never replaces an existing signed
copy. A merge uses the remote, already published side as its base and keeps
that side's signed copy on a tie, reporting differing signed copies. The
byte-level union, leading-text containment, piece order and LF repairs are
specified in [Transport §3.1](./Transport.md#31-multiple-records-in-one-note). Fetching a descendant ref may fast-forward
to its published history; this is ref synchronization, rather than adding a
record to an existing note. These rules do not verify or repair signatures.

Merging is a union because a notes ref is shared: two developers pushing at
once each carry certificates the other lacks, and the standard's coverage rule
is a union too ([Verification §5](./Verification.md#5-coverage-is-a-union)).
A merge that let one side win would silently delete the other's certificates.

### 3.1 Declared scopes

A scoped certificate is keyed by its scoped tree
([Transport §3](./Transport.md#3-git-notes-recommended-for-pushing)), and
nobody can compute that tree without knowing the scope. A repository therefore
declares the scopes its certificates are issued for, in its git
configuration, one section per scope:

```ini
[testCertificatesScope "db"]
	path = Cargo.lock
	path = src/db-backend
[testCertificatesScope "docs"]
	path = docs
```

`git config --add testCertificatesScope.db.path src/db-backend` adds one
value.

- Each `testCertificatesScope.<name>` section declares **one scope**. Its
  `path` values are that scope's paths, interpreted together, as one
  `--paths` group of `find` or `prune` is (§2). Separate sections are
  separate scopes: the declaration above declares the scope
  `["Cargo.lock", "src/db-backend"]` and the scope `["docs"]`, and never
  `["src/db-backend"]` on its own.
- Each value is **one literal path**, as `--paths` takes it: no pathspec
  magic, no globbing, no splitting on whitespace or commas. It is a scope path
  as [Standard §3.2.1](./Standard.md#321-scoping-the-claim-to-paths) defines
  one: repo-relative and `/`-separated, not beginning or ending with `/`, with
  no empty, `.` or `..` component.
- `<name>` identifies the declaration in reports and has no other effect. The
  order of sections and of values does not matter. A path repeated within a
  section counts once, and two sections with the same set of paths declare
  the same scope.
- A `path` value that is not a valid scope path, or any other key under
  `testCertificatesScope` (a misspelt key, or one with no section name), makes
  the declaration **invalid**. An invalid declaration is reported, and
  `notes publish` and `notes import` then do nothing else: publishing only the
  unscoped trees would hide the error behind the certificates that did travel.
  The hook reports it and lets the push continue (§4). `prune` reports it and
  removes nothing (§2).
- The declaration is read from the repository's effective git configuration,
  as `testCertificates.notesRef` is: every configuration file git reads for
  that repository, includes too. git reads no configuration from the working
  tree, so a project that keeps its declaration under version control commits
  it as a file and has each clone include it — for a file at the top of the
  working tree, `git config include.path ../.test-certificates-scopes`, since
  an include path is relative to the file that names it (`.git/config`).

**The trees of a commit.** The trees of a commit `C` are `C^{tree}` and, for
every declared scope, the scoped tree computed from `T = C^{tree}` exactly as
[Content-Id §4.1](./Content-Id.md#41-git-tree-sha1-and-git-tree-sha256)
prescribes: the in-scope entries of `T` at their full paths, selected with
literal pathspecs, a scope matching nothing giving the empty tree. Their
content ids are in the repository's native `git-tree-*` algorithm, the only
one whose ids name a git object a note can be keyed by (Transport §3). Trees
that coincide — a scope that covers every entry, or two commits with the same
in-scope content — are one tree, and one note.

**Lookup.** A consumer looking up a scoped state computes that state's scoped
tree for the scope it requires and reads the note on that oid, never the note
on the unscoped tree (Transport §3). `notes import` does this for every
declared scope. A record found in the note on a tree whose content id it does
not name is misattached: it is reported and skipped.

A certificate stored for a scope the repository does not declare is never
published, by `notes publish` or by the hook. It stays in the local store,
where `find --paths` finds it. Declaring the scopes a project's producers use
is therefore part of adopting scoped certificates: a producer SHOULD only
scope when its consumers can find the result (Transport §3).

## 4. Hooks

`test-certificates hook pre-push` is a complete pre-push hook body. git runs a
pre-push hook with the remote's name and its URL as arguments — the URL twice
when the push names a URL rather than a configured remote — and one line per
pushed ref on standard input:
`<local ref> SP <local object> SP <remote ref> SP <remote object> LF`
([githooks(5)](https://git-scm.com/docs/githooks#_pre_push)).

### 4.1 Entries that introduce nothing

The hook skips, before discovering introduced commits:

- a **deletion**: an entry whose local object is all zeros;
- an entry whose local ref or remote ref is the configured notes ref (§3), or
  is any ref under `refs/notes/`. This includes other tools' notes refs, and
  applies even when the source and destination ref names differ. Notes commits
  describe the carrier, not the project content being certified;
- an entry whose local object is not a commit and does not peel to one (a tag
  of a tree or a blob).

If only such entries are pushed, the hook succeeds without publishing notes
or pushing any ref. In particular, a user's `notes push` must not trigger
another push of the same notes ref from inside its hook: that would race the
outer push. In a mixed push, only the remaining entries contribute introduced
commits.

### 4.2 The commits a push introduces

For each remaining entry, let `L` be the commit its local object names. The
commits the entry introduces are those reachable from `L` and from none of the
**exclusions**:

1. the remote object of **every** entry in the same push — skipped ones
   included — that the pushing repository has and that is or peels to a
   commit: the remote has each of them;
2. when **this** entry's remote object is all zeros, or is not a commit (or an
   object that peels to one) in the pushing repository, and the hook's first
   argument names a remote configured in the
   pushing repository (one `git remote` lists): every ref under
   `refs/remotes/<name>/`, the remote-tracking refs of that remote.

The commits a push introduces are the union over its entries. That gives:

| Push | Introduced commits of the entry |
| ---- | ------------------------------- |
| An existing branch whose remote object the pushing repository has | `<remote object>..L`, less what the other entries' remote objects reach |
| A new branch (remote object all zeros) to a configured remote | What none of that remote's remote-tracking refs reaches |
| A remote object the pushing repository has never fetched (a force-push over someone else's commit) | The same: the remote-tracking refs stand in for the unknown object |
| A push to a URL, or to a configured remote with no remote-tracking refs | The whole history of `L`, less what the other entries' remote objects reach |

The last row over-approximates. Publishing for content the remote already has
is harmless — a note's records are deduplicated (§3) — and costs nothing for
content nobody certified, because only trees with certificates in the store
are published.

### 4.3 Publishing, pushing and the time budget

For the introduced commits the hook publishes as `notes publish` does (§3),
including every declared scope (§3.1), then pushes the notes ref to the same
remote — by its name when it is a configured remote, so its configured push
URL applies, and otherwise to the URL — with `--no-verify`, so it does not
recurse. When no tree of an introduced commit has certificates in the store,
it publishes nothing and makes no network operation.

It never fails the push it is attached to: a certificate that could not be
propagated — including through an invalid scope declaration (§3.1) — is
reported, and the receiving gate decides what that means.

Not failing the push is not enough if the hook can hold it forever: a remote
that accepts the connection and never answers would keep the user's own push
waiting. So:

- The hook **MUST bound the time its network operations can add to a push**
  by a finite time budget, covering every push attempt, the fetches and merges
  between attempts, and the backoff. When the budget runs out it stops the
  operation in progress, reports that the certificates were not propagated,
  and lets the push continue — the outcome of any other propagation failure.
  The default budget and how a user changes it are the implementation's, and
  documented. There is no unlimited setting.
- An implementation **MAY** offer a documented **per-invocation opt-out**
  that disables only this hook body — for a user on a slow link, or a CI job
  that pushes the notes ref itself. When used, the hook says so on standard
  error, publishes nothing and pushes nothing. `--no-verify` is not such an
  opt-out: it skips every other pre-push gate as well.

### 4.4 Composition

It composes with other hooks the same way any hook body does; projects that
already have a pre-push hook — reprobuild's managed dispatcher, for one — call it
from theirs rather than installing it directly.

There is no pre-commit hook in this tool, because a pre-commit gate needs a
verifier and this tool has none (§1). A framework's pre-commit gate uses
`find --staged` — or the library equivalent — to locate candidates, then judges
them itself.

## 5. Library

Every command is a thin wrapper over a library call with the same name and
semantics — store root resolution, atomic put, find, prune, and the notes
operations — so producers and frameworks can link it instead of shelling out.
Errors are returned, never fatal; logging is the caller's.

## 6. Conformance

The tool's store paths are checked by the `store/` vector group
([Conformance §5](./Conformance.md#5-store-path-vectors)), like any
implementation's. Its notes handling is tested against real git repositories,
including concurrent publishers whose records must all survive a merge.

The hook and `notes push` tests also use real git repositories. Required cases
for the §3/§4 distinction are:

| Case | Expected behaviour |
| ---- | ------------------ |
| A user runs `notes push` with a refusing repository `pre-push` hook. | The hook runs and the notes push fails; the remote notes ref is unchanged. |
| A hook calls the library notes push with `PushOptions.runHooks = false`. | Its inner push uses `--no-verify` and does not invoke the repository hook again. |
| The only pushed ref is the default or a configured notes ref. | The propagation hook succeeds without publishing notes or starting another push. |
| Only unrelated refs under `refs/notes/` are pushed. | The same no-op applies; exclusion is not limited to the certificate notes ref. |
| A branch and a notes ref are pushed together. | Only the branch's introduced commits contribute certificates; the hook's notes push suppresses hooks. |
| A refspec has a notes ref on only its local or only its remote side. | That entry is ignored in either direction, including for a configured notes ref outside `refs/notes/`. |

The no-op cases must check that neither publication nor an inner push occurred,
rather than just checking a successful exit status: the hook also succeeds
after reporting a propagation failure.

The commits a push introduces (§4.2), the time budget (§4.3) and declared
scopes (§3.1) are tested the same way. Each case stores certificates for
several commits' trees and checks exactly which notes the hook or command
wrote and pushed, or which content directories `prune` kept:

| Case | Expected behaviour |
| ---- | ------------------ |
| An existing branch is pushed, and the pushing repository has its remote object. | Only commits in `<remote object>..<local object>` are published; a certified commit the remote object already reaches is not. |
| A new branch is pushed to a configured remote. | Commits a remote-tracking ref of that remote reaches are not published; the branch's other certified commits are. |
| A branch is force-pushed over a remote object the pushing repository has never fetched. | The remote-tracking refs stand in for the unknown object, as for a new branch; the hook still publishes and pushes. |
| Two refs are pushed together, and one's remote object reaches part of the other's history. | That part is excluded from both entries. |
| A branch is pushed to a URL that is no configured remote. | The branch's whole history is considered, and the notes ref is pushed to that URL. |
| Only deletions are pushed. | Nothing is published and no inner push starts. |
| The remote accepts the notes push's connection and never answers. | The hook stops within its budget (plus a small margin), reports that the certificates were not propagated, and exits successfully. |
| The implementation's opt-out, if it has one, is used. | Nothing is published or pushed, and the hook says so on standard error. |
| A certificate is stored for a declared scope's tree of a pushed commit. | It is published to the note on the scoped tree oid, not on `<commit>^{tree}`, and pushed. |
| A certificate is stored for a scope the repository does not declare. | It is not published. |
| One section declares `src` and `lib`, another declares `src`, and certificates are stored for the trees of `["src", "lib"]`, `["src"]` and `["lib"]`. | The first two are published, each on its own scoped tree; the third is not, since no section declares `lib` on its own. |
| `notes import` runs in a fresh clone after a scoped certificate was pushed. | The certificate is stored under its scoped content id. |
| The declaration is invalid: a malformed path, or an unknown key under `testCertificatesScope`. | `notes publish` and `notes import` report it and write nothing; the hook reports it, publishes and pushes nothing, and lets the push continue; `prune` reports it and removes nothing. |
| `prune --keep 0` runs with a declared scope and no `--paths`. | The content directories of `HEAD`'s scoped tree in that scope, in both algorithms, are kept; one for an undeclared scope is removed. |
