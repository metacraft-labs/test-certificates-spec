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
  verifier judges them. A generic "is this covered?" command would be exactly
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
| `test-certificates find <state> [--paths <p>…]` | Prints the paths of the candidate certificates stored for a state's content id, from both roots. `<state>` is `--content <id>`, `--commit <rev>`, `--staged` or `--worktree`; the last three compute the content id as [Content-Id §5](./Content-Id.md#5-computing-the-id-of-the-state-under-evaluation) prescribes, with the repository's `git-tree-*` algorithm unless `--algorithm` says otherwise, scoped by `--paths`. Exit 0 when candidates exist, 1 when none were found, 2 when the content id could not be computed. |
| `test-certificates prune [--keep <n>] [--system <user>]` | Removes content directories beyond the newest `n` (default 20) from the user root — or from a system partition, when run by its owner — never the one for the current repository's `HEAD^{tree}` (Transport §2.5). |

`find` reports what it searched — both roots, the content id, the directories — so
"nothing found" can be told apart from "looked in the wrong place"
([Transport §5](./Transport.md#5-discovery)).

## 3. Propagating through git notes

The local store does not leave the machine. These commands move certificates
between it and the notes ref described in
[Transport §3](./Transport.md#3-git-notes-recommended-for-pushing).

The notes ref defaults to `refs/notes/test-certificates/certificates` and is
set per repository with `git config testCertificates.notesRef <ref>`, so a
project whose tooling already uses a vendor ref keeps it.

| Command | Does |
| ------- | ---- |
| `test-certificates notes publish <commit>…` | For each commit, finds the store's certificates for `<commit>^{tree}` and adds them to the note on that tree oid, framed per Transport §3.1. Records already in the note are kept; a record is identified by its payload hash, so publishing twice adds nothing. Accepts revision ranges. Writes the local ref only. |
| `test-certificates notes import [<commit>…]` | The reverse: copies certificates from the notes on each commit's tree (default `HEAD`) into the user root. A fresh clone, or a reviewer's machine, gets the certificates that travelled with a push. |
| `test-certificates notes push <remote>` | Pushes the notes ref. When the remote ref has moved, fetches it, merges with the union of both sides' records — never one side's — and retries a bounded number of times. |
| `test-certificates notes fetch <remote>` | Fetches the remote notes ref into the local one, merging the same way. |

Merging is a union because a notes ref is shared: two developers pushing at
once each carry certificates the other lacks, and the standard's coverage rule
is a union too ([Verification §5](./Verification.md#5-coverage-is-a-union)).
A merge that let one side win would silently delete the other's certificates.

## 4. Hooks

`test-certificates hook pre-push` is a complete pre-push hook body. It reads the
refs being pushed from standard input, as git supplies them, publishes notes for
every commit the push introduces, and pushes the notes ref to the same remote
with `--no-verify`, so it does not recurse. It never fails the push it is
attached to: a certificate that could not be propagated is reported, and the
receiving gate decides what that means.

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
