# verify/unknown-keys

**Pins:** unknown keys or tables make a v1 record malformed at every level,
including the root and the excluded signature block.

Standard.md §3.4 and Canonical-Payload.md §5 require rejection before
payload reconstruction, even when signatures are not required. Each record
has the same otherwise covering values as the earlier-draft vector after
replacing `commit` and `clean` with the state's `content`; no signature or
trust requirement can explain a rejection. The signature cases have the
valid empty unsigned block plus one unknown key or subtable. The `table`
case adds an unknown root table; the other cases add one key to each of the
five defined tables. Expected outcome and gaps are derived directly from
rejecting every candidate; malformed records have no canonical payload.

**Would be wrong if:** any unknown field or table were dropped, included in
an invented payload, or accepted because the signature block is excluded.
