# verify/coverage-union

**Pins:** required coverage is the **union** of several
certificates, not a property any single one has to satisfy.

| Rule | Where |
| ---- | ----- |
| For each required platform, union the `targets` of the survivors for that platform | Verification.md §5 |
| Coverage holds when every required target appears in that union | Verification.md §5 |
| Duplicate coverage is not an error | Verification.md §5 |

Neither certificate covers the requirement alone. `a-unit.toml` carries
`t-unit`; `b-integration.toml` carries `t-integration`; the requirement asks
for both on `linux/amd64`.

**Would be wrong if:** the implementation looked for one certificate matching
the whole requirement and reported not-covered, which is the shape most people
write first — Standard.md §8 exists because partial coverage is the normal
case, not a degraded one.
