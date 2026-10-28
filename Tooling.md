# Reference Tooling

> **Status:** Planned. This document specifies a helper tool; it is not yet
> implemented. It is not normative for producers or verifiers: anything it does
> can be done natively by following [Transport](./Transport.md), and conformance
> is decided by the vectors, not by using this tool.

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
group, including paths beginning with `-`. No scope is inferred from stored
certificates.

All protected ids are computed from one fixed `HEAD` tree, including in a bare
repository; staged changes and working-tree edits do not affect them. They are
additional to the newest `n` directories, including with `--keep 0`, and apply
equally to the selected user root or system partition. Outside a repository,
or on an unborn branch, there is no automatic `HEAD` protection. An explicit
scope without an available `HEAD`, or a failure computing a required id for an
existing `HEAD`, is reported and aborts pruning before any directory is removed,
including interrupted-prune leftovers. Scopes not declared to this invocation
and algorithms it cannot compute remain subject to ordinary pruning.

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
| `test-certificates notes publish <commit>…` | For each commit, finds the store's certificates for `<commit>^{tree}` and adds them to the note on that tree oid, framed per Transport §3.1 (canonical records, each preceded by the `# --- test-certificate ---` delimiter line). Records already in the note are kept; a record is identified by its payload hash, so publishing twice adds nothing. Accepts revision ranges. Writes the local ref only. |
| `test-certificates notes import [<commit>…]` | The reverse: copies certificates from the notes on each commit's tree (default `HEAD`) into the user root. A fresh clone, or a reviewer's machine, gets the certificates that travelled with a push. |
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

## 4. Hooks

`test-certificates hook pre-push` is a complete pre-push hook body. It reads the
refs being pushed from standard input, as git supplies them. Before discovering
introduced commits, it ignores each input entry whose local ref or remote ref
is the configured notes ref (§3), or is any ref under `refs/notes/`.
This includes other tools' notes refs, and applies even when the source and
destination ref names differ. Notes commits describe the carrier, not the
project content being certified.

If only such entries are pushed, the hook succeeds without publishing notes
or pushing any ref. In particular, a user's `notes push` must not trigger
another push of the same notes ref from inside its hook: that would race the
outer push. In a mixed push, only the remaining entries contribute introduced
commits. For those commits the hook publishes notes, then pushes the notes ref
to the same remote with `--no-verify`, so it does not recurse. It never fails
the push it is attached to: a certificate that could not be propagated is
reported, and the receiving gate decides what that means.

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
