# payload/targets-duplicates

**Pins:** duplicate target names are removed before sorting, while the
same repetition survives verbatim inside `argv`.

| Rule | Where |
| ---- | ----- |
| Duplicate target names MUST be removed before sorting | Canonical-Payload.md §3 |
| `argv` is never deduplicated — repeated arguments are meaningful | §2 rule 7 |

**Would be wrong if:** an implementation deduplicated after sorting but kept the
count wrong, emitted `t-unit` three times, or applied its `targets`
deduplication to `argv` as well.

**Paired with `targets-unsorted-input`:** the `targets` line is byte-identical
in both, from different inputs. Sort-then-dedup and dedup-then-sort must
converge.
