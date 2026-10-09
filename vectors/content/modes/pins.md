# content/modes

**Pins:** all four entry kinds — regular file, executable file,
symbolic link, nested repository — and what each contributes.

| Rule | Where |
| ---- | ----- |
| `100644` regular and `100755` executable files contribute their bytes | Content-Id.md §4.2 |
| `120000` symbolic links contribute the link target, unresolved | Content-Id.md §4.2 |
| `160000` nested repositories contribute their checked-out revision id, in ASCII | Content-Id.md §4.2 |
| A nested repository appears as the gitlink git records for it | Content-Id.md §4.1 |
| The mode is part of each record | Content-Id.md §4.2 |

| Path | Mode | Content |
| ---- | ---- | ------- |
| `bin/run.sh` | `100755` | a two-line shell script |
| `lib.c` | `100644` | `int lib;\n` |
| `current` | `120000` | `lib.c` — the link target, no trailing newline |
| `vendor/dep` | `160000` | `3f2a9c1e5b7d4068a1c2e3f405162738495a6b7c` — 40 ASCII characters |

Two encodings of the nested repository differ, and both are pinned. In
`manifest-v1` its content is the **40-byte ASCII** revision id, hashed like any
other content. In a git tree the gitlink entry records the **20-byte binary**
commit id directly — it is not a blob, and git never hashes it. The commit need
not exist in the repository for the tree to be written.

**Would be wrong if:** the implementation followed the symlink and hashed
`lib.c`'s bytes, normalised `100755` to `100644` (a filesystem without an
executable bit tempts this), hashed the nested repository's working tree
instead of naming its revision, wrote the gitlink into a git tree as a blob of
its ASCII id, or hashed the revision id with a trailing newline.
