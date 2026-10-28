# Transport

How certificates travel from the machine that issued them to whoever needs to
check them.

## 1. The signed payload is the unit of trust

Transport is **not** a trust boundary. A certificate's integrity comes entirely
from its signature over the canonical payload; it does not come from where the
certificate was found, who put it there, or how it arrived.

This has one practical consequence worth stating plainly, because it is easy to
get backwards: **the existence of a certificate in a trusted location proves
nothing.** A verifier MUST check the signature regardless of provenance, and MUST
NOT accept a certificate merely because it appeared somewhere only authorised
parties can write.

It follows that carriers are interchangeable for trust, and that a project may
use several at once. They are not interchangeable for **discovery**: a gate can
only check what it can find. So this document defines one carrier every
conforming producer populates — the local certificate store (§2), which is how
a pre-commit gate or any other local tool finds a certificate without knowing
which producer issued it — and describes the rest (§3, §4) as options.

## 2. The local certificate store (required)

Certificates are **ephemeral**. A certificate attests content that, at the
moment of issuance, usually exists only in one working tree; it is needed for
as long as that content is being committed and pushed, and is worth nothing
once the content is gone. It therefore never belongs in the working tree — a
tracked certificate would change the content it attests — and it should not
depend on any particular producer staying alive to hand it out.

Producers are not standardized and cannot be: one is a test runner that exits
after a run, another a daemon that signs on behalf of many runs. Some keep
certificates in memory and offer them on request, which is fine, but a gate
cannot be expected to know every producer's interface. The local store is the
interface they share: a set of directories, addressed by content id, that every
conforming producer writes and any tool can read.

Some producers run as the user whose tests they observe — a test runner is
usually one. Others deliberately do not: a signing daemon that guards its key
runs under its own account, precisely so that the tested code cannot reach the
key ([Standard §6.2](./Standard.md#62-issuance-integrity)). The store therefore
has two roots per user — one the user owns, one the privileged producer owns —
and readers search both.

### 2.1 Location

A user's store has two roots, each holding the same layout (§2.2).

**The user root**, owned and written by the user, is, in order:

1. `$TEST_CERTIFICATES_DIR`, when set to a non-empty absolute path;
2. otherwise the platform's per-user state directory:

| Platform | User root |
| -------- | --------- |
| Linux and other Unix-likes | `$XDG_STATE_HOME/test-certificates`, when `XDG_STATE_HOME` is set to an absolute path; else `$HOME/.local/state/test-certificates` |
| macOS | `$HOME/Library/Application Support/test-certificates` |
| Windows | `%LOCALAPPDATA%\test-certificates` |

**The system root**, owned and written by privileged producers and readable by
the user, is the user's partition of a machine-wide directory:

1. `$TEST_CERTIFICATES_SYSTEM_DIR/<user>`, when set to a non-empty absolute
   path;
2. otherwise:

| Platform | System root |
| -------- | ----------- |
| Linux and other Unix-likes | `/var/lib/test-certificates/<uid>` |
| macOS | `/Library/Application Support/test-certificates/<uid>` |
| Windows | `%ProgramData%\test-certificates\<SID>` |

`<user>` is the numeric uid on POSIX systems and the account SID on Windows —
identifiers that do not change when an account is renamed.

Every environment variable read above MUST supply a non-empty absolute path
in the platform's terms to be used: `$TEST_CERTIFICATES_DIR`,
`$TEST_CERTIFICATES_SYSTEM_DIR`, `$XDG_STATE_HOME`, `$HOME`, `%LOCALAPPDATA%`
and `%ProgramData%`. An unset or empty value is unavailable. A relative value
MUST be ignored and reported, then resolution continues with the next fallback,
if any. This includes drive-relative Windows paths such as `C:state`. A store
whose location depends on the current directory would be a different store for
each process; the XDG specification already requires this treatment of
`XDG_STATE_HOME`.

When no applicable value yields an absolute path, that root is **unresolved**.
It MUST be reported, and MUST NOT be guessed or resolved against the current
directory. The two roots resolve independently: failure to resolve one does not
prevent use of the other. A reader finds no certificates in an unresolved root
and continues searching the other root; it reports that the search could not
cover the unresolved root (§5), rather than claiming that root was searched
and empty. A writer whose required destination root is unresolved MUST report
an error and MUST NOT write the certificate elsewhere as a fallback.

Neither root is shared between users. A user's system root holds only
certificates for runs made on that user's behalf. A CI runner, a container or a
sandbox has whichever roots its environment resolves to, and sets the variables
when it needs others.

### 2.2 Layout

```
<root>/v1/<algorithm>/<digest>/<payload-hash>.toml
```

- `v1` is the layout version, so a later layout can coexist with this one.
- `<algorithm>` and `<digest>` are the two halves of the certificate's
  `content`, split at the first `:`
  ([Content-Id §1](./Content-Id.md#1-form)). The id is split rather than used
  as one name because `:` is not a legal file-name character on Windows.
- `<payload-hash>` is the lowercase hex SHA-256 of the certificate's
  **canonical payload** ([Canonical-Payload](./Canonical-Payload.md)) — the
  bytes a signature covers, which excludes the signature block.
- The file holds the certificate as a TOML document, signature block included
  when there is one.

This is content-addressed twice over, and both halves do work:

- **By content id**, so a reader asks "is there anything for this content?" by
  listing one directory, and a certificate issued in one clone or worktree is
  found from another holding the same content — content ids do not depend on
  which repository computed them.
- **By payload hash**, so certificates never collide. Several frameworks,
  several platforms and several partial runs of one suite all attest the same
  content, and coverage is their union
  ([Verification §5](./Verification.md#5-coverage-is-a-union)); each is its own
  file, and none replaces another. Re-issuing an identical claim produces the
  same name, so publishing is idempotent.

A scoped certificate is stored under its **scoped** content id. As with git
notes (§3), a reader finds it only by computing that id, which requires knowing
the scope.

### 2.3 Writing

A conforming producer MUST deliver every certificate it issues to the store of
the user on whose behalf the tests ran, in addition to any other carrier it
uses. **A producer never writes into another account's directories**, and
which root it delivers to follows from that:

- **A producer running as the user** writes to the user root.
- **A producer running under its own account** — a signing daemon — returns the
  certificate to the client that requested or reported the run, and **the
  client**, running as the user, writes it to the user root. This is the normal
  path, and it keeps a privileged process out of directories the user controls,
  where following a user-planted symbolic link would let the user redirect a
  privileged write.
- **A privileged producer with no client to return to** — issuing for a run it
  observed on its own, such as a watch or a scheduled re-run — writes to the
  user's system root. It identifies the user from the operating system's
  authenticated credentials for the run (peer credentials on its socket, the
  owner of the observed process), never from a value the run supplied.

The system partition itself is provisioned by the privileged producer's
installer or a separate administrative setup step. A certificate writer MUST
NOT create a missing partition. Before any mutation, including creation of
`.write-lock`, a writer MUST establish that the partition is a directory owned
by its own effective account and that the user whose partition it is has
read/traverse access but **no write access**. The recipient and producer are
distinct accounts. These are effective-access checks: group membership and
access-control entries count, not just the owner or the displayed mode bits.
A partition the recipient can write is not safe for a privileged producer to
enter. Failure to establish any precondition MUST be reported and the write
refused without changing the partition or creating it elsewhere.

Directories created below a system partition (`v1`, algorithm and digest)
MUST preserve its access policy: producer ownership, and the same intended
reader access through group ownership or access-control entries. On a POSIX
mode-based partition they take the partition's read/write/execute permission
bits and group; regular record files take those bits with all execute bits
removed. An ACL-based partition requires equivalent effective access for new
directories and files, with traversal applying only to directories. Creation
MUST NOT grant the recipient write access, and a restrictive process umask
MUST NOT remove the intended reader access. This applies to the temporary
record as well as its published name. Synchronization metadata MUST remain
owned and writable by the producer and not writable by the recipient.
Before entering an existing directory below the partition, a system writer or
pruner MUST establish that it is producer-owned and gives the recipient
read/traverse but no write access. Existing synchronization metadata MUST be
a regular file owned by the producer and not writable by the recipient;
writers check it before using it. Unsafe entries are refused without repairing
their ownership or permissions.
A writer MUST establish the required access before publishing; it reports
failure if it cannot reproduce it, rather than publishing an unreadable record
or broadening access as a fallback. Merely copying mode bits does not preserve
an ACL policy.

A system writer MUST NOT follow symbolic links at the partition itself or
within it (or equivalent filesystem redirections such as Windows reparse
points). It MUST perform its checks and mutations on the same filesystem
objects, so replacing a pathname between checking and opening it cannot
redirect a privileged write. An implementation that cannot establish effective
access or enforce this confinement MUST report the unsupported access policy
or operation and refuse it.

An existing user root MUST be owned by the writer's effective account. A writer
MUST check this before any mutation and refuse and report a root owned by
another account, even when that root is writable by the caller. It MUST NOT
take ownership of, or repair permissions on, a foreign root. Existing roots
owned by the caller keep their configured permissions; this rule does not
require retroactively narrowing them.

Within whichever root, the write is atomic:

1. after the root checks above, create missing directories below it as needed
   — a user root, on platforms that have them, with permissions readable and
   writable by the owner only. On POSIX, newly created user-store directories
   (including the root) use `0700`, and new record files use `0600`. In a system
   store, use the partition's access policy as specified above;
2. write the file under a temporary name in the **same directory**, beginning
   with `.` and not ending in `.toml`;
3. flush it, then rename it to its final name.

Readers never see a partial file. Writers distinguish a **signing writer**, which
made the signature it is delivering, from a **relay**, which only received the
certificate. A signature table alone does not establish that its signature
verifies. A daemon's client and the reference helper are relays, even when the
certificate arrived directly from its signer.

When the final name already exists:

- a signing writer delivering its own **signed** certificate MUST replace the
  existing file: it knows its newly made signature verifies;
- a relay delivering a **signed** certificate MUST keep an existing signed
  copy, even if the copies' signature values differ. It MUST replace an
  existing unsigned copy of the same payload, including one with an empty
  signature block;
- a writer delivering an **unsigned** certificate MUST keep an existing copy.

Here, **signed** means a parsed certificate carrying non-empty signature
`algorithm` and `value`, not a verification result. A relay that cannot read or
parse the existing file, or finds a different payload under its name, MUST
report the problem and leave the file unchanged; it cannot establish that the
file is the unsigned copy it may replace. A signing writer may repair such a
file by replacing it with its own freshly signed certificate.

All writers to a store MUST serialize inspection of the existing file and
publication of its replacement with other writers, including signing writers.
Merely inspecting before an atomic rename is insufficient: a relay could
inspect an unsigned copy, then overwrite a signed copy published in between.
For interoperable local serialization, writers use the persistent file
`<root>/.write-lock`: on POSIX, open it without following symbolic links and
hold an exclusive `flock` lock; on Windows, open it with read/write access and
no sharing, waiting when another writer holds it. Create the file if absent,
never unlink or replace it, and hold the lock from before inspection until
after publication. The file is synchronization metadata, not a certificate.
A writer unable to acquire the lock reports an error without publishing.
Readers do not need the lock. Pruning still follows §2.5.

The name is the payload's hash, and the signature block is not part of the
payload, so a signed certificate and the same certificate with its signature
block removed or emptied share a name
([Canonical-Payload §6](./Canonical-Payload.md#6-unsigned-certificates)).
Keeping an unsigned copy over a signed one would silently discard the
signature. A relay preserves the first signed copy because it cannot distinguish
a valid signature from an invalid one. Consequently a relay cannot repair a
stored failing signature with another signed copy; the signer must deliver its
own replacement, or the old cache entry must be removed before redelivery.
Changing `key_id` changes the payload and therefore the name.

The two roots are not two levels of trust. A certificate found in the system
root is evaluated exactly like one found in the user root (§1): what makes a
daemon-signed certificate worth more is its signature under a key the consumer
registered, not the directory it was found in. The system root exists because a
privileged producer cannot safely write anywhere else, not to vouch for what it
holds.

### 2.4 Reading

A reader lists `<root>/v1/<algorithm>/<digest>/` **in both roots** and reads
every file whose name ends in `.toml` and does not begin with `.`. A name found
in both roots is the same payload, but the two files need not be the same
certificate: one copy may be signed and the other not (§2.3). A reader may skip
a copy byte-identical to one it has evaluated; otherwise it evaluates each, so
that neither an unsigned copy nor one whose signature fails hides a copy that
would have counted — coverage only grows
([Verification §5](./Verification.md#5-coverage-is-a-union)). Each file is one
candidate certificate, evaluated like any other
([Verification](./Verification.md)): the directory it was found in is a hint
for discovery, not evidence, and a record whose own `content` does not match
its directory is reported and ignored.

A missing root, a missing directory or an empty one all mean **no
certificates found** — never an error (§5). A system root that exists but
cannot be read is reported, since it usually means a misconfigured install;
the user root is still searched.

### 2.5 It is a cache

Any file in the store may disappear at any time. Nothing may depend on a
certificate staying there; whatever needs it beyond the local machine copies it
to a durable carrier — git notes at push time (§3), a CI artifact, a gateway
submission.

The store is bounded by **pruning**, which removes whole content directories.
Each root is pruned by whoever writes it — the user's tooling prunes the user
root, a privileged producer prunes the system partitions it writes:

- Before renaming or deleting anything, a pruner MUST apply the same root
  ownership and effective-access checks as a writer (§2.3). In particular,
  a system partition must already exist, be owned by the pruner's effective
  account, and be readable/traversable but not writable by its recipient;
  an existing user root must be owned by the pruner's effective account.
  Failed or unsupported root checks are reported and no mutation is attempted.
  Existing descendant directories must pass the checks in §2.3 before the
  pruner enters or mutates them; failure leaves the affected subtree unchanged.
  A system pruner MUST NOT follow symbolic links or equivalent filesystem
  redirections at the partition or within it, including while deleting a
  detached tree, and checks and mutations must refer to the same objects.
  A link encountered as an entry may be unlinked without traversing its
  target. Pruning never creates a missing root or changes its ownership or
  permissions to make it acceptable.

- A producer or tool that prunes SHOULD keep the content directories most
  recently written — the reference policy keeps the newest 20, by the
  directory's modification time, which writing a file updates — plus the
  directories for the current repository's `HEAD` content ids that the
  pruner can compute. Protection includes the unscoped state and each scope
  explicitly declared to the pruner, under each algorithm it computes for
  that repository. A scope is one set of paths, interpreted together under
  Standard §3.2.1; unrelated scopes are not combined. The reference tool
  computes the repository's native `git-tree-*` algorithm and
  `manifest-v1-sha256` for each of these states (Tooling §2). Undeclared
  scopes and algorithms the pruner cannot compute have no such protection;
  this is not a guarantee that every certificate for `HEAD` stays cached.
- Pruning MUST NOT remove a directory a producer is writing into. Removing a
  directory, then the producer's write or rename failing, is acceptable: the
  producer recreates it and retries once.
- A pruner MUST take a directory out of the store in one atomic step — by
  renaming it, within its parent, to a name beginning with `.` — and only
  then delete the renamed tree. Deleting it in place (its entries, then the
  directory) is not one step: a producer whose first attempt that deletion
  defeated retries into the same, still-present directory, and the same
  deletion goes on to remove the retry's temporary file and the directory
  under it, so retrying once would not be enough. A name beginning with `.`
  under `<root>/v1/<algorithm>/` is never a content directory: readers ignore
  it, and any pruner may delete it.

Pruning is a matter of disk space, not of correctness: a pruned certificate is
re-issued by running the tests again.

## 3. Git notes (recommended for pushing)

Certificates attach to the **tree object their content id names**, in a
dedicated notes ref:

```
refs/notes/<vendor>/certificates
```

The local store (§2) does not leave the machine. Git notes are how certificates
travel **with a push**, to a receiving-side gate or to collaborators. They are
populated from the local store by push tooling — the reference tooling
([Tooling](./Tooling.md)) copies the certificates covering each pushed commit's
tree into the notes ref — so a producer needs to do nothing beyond §2.3. A
producer MAY write notes itself as well.

A note is data attached to a git object without changing it, and the annotated
object may be any object — a tree as readily as a commit. For a certificate
whose `content` is `git-tree-sha1:<oid>` or `git-tree-sha256:<oid>`
([Content-Id §4.1](./Content-Id.md#41-git-tree-sha1-and-git-tree-sha256)), the
note is keyed by `<oid>`.

Keying by content rather than by commit is what the content binding requires:

- **The certificate predates the commit.** It was issued before the commit was
  made ([Standard §3.2.2](./Standard.md#322-certifying-before-the-commit)), so
  there is no commit identity it could have been keyed by.
- **One note serves every commit with that content.** A verifier evaluating
  commit `C` looks up the notes on `C^{tree}`, and needs to know nothing about
  which commit, if any, the producer was on.

Rules:

- The notes tree maps `<tree-oid>` to a blob holding the certificate(s).
- **Multiple certificates per content are normal**, typically one per platform.
  A carrier MUST support several, and a verifier MUST evaluate their union
  ([Verification §5](./Verification.md#5-coverage-is-a-union)).
- **A scoped certificate is keyed by its scoped tree**, the tree holding only
  the in-scope entries ([Content-Id §4.1](./Content-Id.md#41-git-tree-sha1-and-git-tree-sha256)).
  A consumer therefore finds it only by computing that scoped id for the state
  in front of it — which requires knowing the scope. Scopes a framework
  declares in its version-controlled configuration are known in advance; a
  consumer that accepts other scopes has to enumerate the notes ref instead.
  Scoping trades discoverability for a narrower claim, and a producer SHOULD
  only scope when its consumers can find the result.
- **Notes are not pushed or fetched by default.** Producers must push the notes
  ref explicitly, and verifiers must fetch it. Forgetting this is the most common
  operational failure with this carrier, and it presents as "no certificates"
  rather than as an error. A receiving-side gate needs the ref pushed alongside
  the commits it covers; a pre-commit gate reads the local store instead (§2).
- **Notes are mutable** — anyone with push access can rewrite them. This is
  exactly why §1 holds: a note's contents are worth what their signature is
  worth, and nothing more.
- **An annotated tree need not be reachable**, and the notes ref does not keep it
  alive. That costs nothing: a verifier computes the content id of the state in
  front of it and looks the note up by that id, so it never needs the producer's
  tree object.

A verifier MUST ignore a note whose certificate's `content` does not name the
object the note is attached to, and SHOULD report it. The content check would
reject such a certificate anyway; the rule is stated so that a misattached
record is reported as a carrier fault rather than as untested content.

`manifest-v1-sha256` content ids name no git object, and travel by the other
carriers (§4).

### 3.1 Multiple records in one note

Several certificates share one note blob whenever several frameworks,
platforms or partial runs attest the same content. Every tool that writes or
reads the note — any producer, the reference tooling, any verifier — must split
it the same way, so the framing is fixed:

- Each record in a note is written as its **canonical payload**
  ([Canonical-Payload §2](./Canonical-Payload.md#2-structure)), followed, when
  signed, by one blank line and the `[certificate.signature]` table with
  `algorithm` and `value`, in that order, in the payload's formatting rules.
  Nothing else: no comments, no multi-line strings, no other tables.
- Every record is **preceded** by the delimiter line

  ```
  # --- test-certificate ---
  ```

  exactly, followed by LF. The blob begins with a delimiter line; there is no
  delimiter after the last record, and nothing — not even a blank line — lies
  between the LF that ends one record and the delimiter before the next.
- A reader splits the blob on lines equal to the delimiter, drops the empty
  piece before the first one, and parses each remaining piece as one
  certificate. A piece that does not parse is reported and skipped; it does
  not invalidate its neighbours. A **non-empty** piece before the first
  delimiter — a blob framed some other way, or not framed at all — is
  reported and skipped in the same way, and never parsed as a record, even
  when it would parse. Lines end at LF, and a CR belongs to its line: a blob
  written with CRLF line endings has no delimiter line, so all of it is such a
  leading piece.

Writing records in canonical form is what makes the delimiter safe. Every line
of a canonical record is blank, a table header or `key = value`, and every
newline inside a value is escaped, so no line of a record can equal the
delimiter. Blank-line separation would not work, since a certificate
legitimately contains blank lines between its tables.

Two records whose payloads are byte-identical are the same claim. A writer
adding a record to a note MUST NOT add one whose payload is already present.
Replacement follows the writer's role in §2.3: a signing writer delivering its
own signature MUST replace the present copy; a relay delivering a signed copy
MUST replace an unsigned copy and MUST keep a signed one, regardless of whether
either signature verifies. An unsigned copy never replaces a present one. If
several parsed records carry that payload, a relay MUST keep the note unchanged
when any of them is signed; otherwise a replacement takes the first matching
record's place. A signing writer replaces the first matching record. No
duplicate is added, and other copies are preserved. A writer changes nothing
else: a new record goes after the last piece, behind its own delimiter; a replacement takes the replaced
record's place; and every other piece — a record it did not touch, one it
could not parse, or text before the first delimiter — is kept byte for byte.
A notes ref update MUST compare against the ref from which the note was read,
and retry the read and record addition if another writer moved it; an atomic
ref update alone must not publish a decision made from a stale note.

## 4. Other carriers

| Carrier | Notes |
| ------- | ----- |
| A dedicated ref (`refs/certificates/<algorithm>/<digest>`) | Keyed by content id, for any algorithm; immutable-by-convention; needs its own push/fetch discipline |
| A directory in the §2.2 layout outside the local store | Travels with an artifact rather than with history — a CI job can upload its store as one. Must never be inside a working tree: a tracked certificate would change the content it attests |
| A CI artifact | Natural where the issuer is CI; needs an out-of-band way to find it |
| An HTTP endpoint | Useful for central verification; the endpoint is not a trust input |

All are equally acceptable. The signature is what is checked in every case.

## 5. Discovery

A verifier needs to find candidate certificates before it can evaluate them.
Whatever the carrier, discovery MUST be:

- **Explicit** about what it searched. "No certificates found" and "certificates
  found but none matched" are different outcomes and MUST be reported
  differently — the first usually means a fetch or push was missed, the second
  means the state genuinely is not covered.
- **Non-fatal when empty.** An absent certificate store is a normal state for a
  project that does not use certificates, and MUST NOT be an error in itself.
  Whether *absence* blocks anything is a consumer policy decision, made after
  discovery, not during it.

### 5.1 Lookup is by the consumer's own content id

The local store (§2) and git notes (§3) are both keyed by content id, and a
consumer looks up the id **it computes** for the state in front of it. So it
finds only certificates whose `content` uses an algorithm it computes, over a
scope it asks for. A certificate in any other algorithm sits under another key
and is never found. It is reported as "none found", not as unverifiable.

Two consequences:

- **A producer SHOULD use the algorithm its consumers compute.** For a git
  repository that is the repository's `git-tree-*` algorithm
  ([Content-Id §4](./Content-Id.md#4-algorithms)). A certificate in another
  algorithm is valid, but no keyed lookup will ever surface it.
- **The "algorithm the consumer cannot compute" outcome**
  ([Verification §4.1.1](./Verification.md#411-matching-content)) arises only
  through a carrier read in full, such as a CI artifact or a directory handed
  to the verifier. There the record is in hand without a lookup. Keyed carriers
  never produce it.
