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

A relative `$TEST_CERTIFICATES_DIR`, `$TEST_CERTIFICATES_SYSTEM_DIR` or
`$XDG_STATE_HOME` is ignored, as the XDG specification requires for the last: a
store whose location depends on the current directory would be a different
store for each process.

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

The system root's directories are created by the privileged producer or its
installer, owned by the producer's account, and **readable but not writable by
the user** whose partition it is — through group ownership or an access-control
entry, whichever the platform provides. A producer writing there MUST NOT follow
symbolic links within the root.

Within whichever root, the write is atomic:

1. create the directories as needed — a user root, on platforms that have them,
   with permissions readable and writable by the owner only;
2. write the file under a temporary name in the **same directory**, beginning
   with `.` and not ending in `.toml`;
3. flush it, then rename it to its final name.

Readers never see a partial file, and two producers publishing at once cannot
corrupt each other: they either write different names, or the same bytes under
the same name. When the final name already exists, a producer MAY keep the
existing file — **unless the existing file carries no signature and the new
one does**, in which case it MUST replace it. The name is the payload's hash,
and the signature block is not part of the payload, so a signed certificate and
the same certificate with its signature block removed or emptied share a name
([Canonical-Payload §6](./Canonical-Payload.md#6-unsigned-certificates));
keeping the unsigned copy would silently discard the signature. In every other
case the two files are interchangeable: two unsigned copies are the same claim,
and two signed copies carry signatures by the same key — `key_id` is part of
the payload — over the same bytes.

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
candidate certificate, evaluated like any other ([Verification](./Verification.md)): the
directory it was found in is a hint for discovery, not evidence, and a record
whose own `content` does not match its directory is reported and ignored.

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

- A producer or tool that prunes SHOULD keep the content directories most
  recently written — the reference policy keeps the newest 20, by the
  directory's modification time, which writing a file updates — plus the
  directory for the content of the current repository's `HEAD^{tree}` where
  the pruner knows one.
- Pruning MUST NOT remove a directory a producer is writing into. Removing a
  directory, then the producer's rename failing, is acceptable: the producer
  recreates it and retries once.

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

When several certificates share a note blob, they MUST be framed so a reader can
split them unambiguously without parsing TOML — a delimiter line that cannot
occur inside a certificate. Implementations MUST NOT rely on blank-line
separation, since a certificate may legitimately contain blank lines.

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
