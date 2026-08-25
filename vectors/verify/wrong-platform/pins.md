# verify/wrong-platform

**Pins:** certificates for another platform contribute nothing.

| Rule | Where |
| ---- | ----- |
| `platform` must match by exact equality | Verification.md §4.1 |
| Certificates for other platforms MUST NOT contribute to a platform's union | Verification.md §5 |
| A consumer MUST report *what* is missing, on which platform | Verification.md §5 |

The certificate is authentic, current, clean and complete. It is simply about a
different machine.

**Would be wrong if:** the implementation unioned targets across platforms, or
treated `platform` as a prefix or a family (`linux/amd64` matching `linux`).
