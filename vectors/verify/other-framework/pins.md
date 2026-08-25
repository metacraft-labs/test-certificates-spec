# verify/other-framework

**Pins:** an unrecognised `framework` is **ignored** — neither
counted as evidence nor treated as an error.

| Rule | Where |
| ---- | ----- |
| Filter by `framework` before applying any framework-specific rule | Verification.md §2, Standard.md §4 |
| Certificates from unimplemented frameworks are ignored, not rejected | Verification.md §2 |
| Certificates from other frameworks MUST NOT contribute to the union | Verification.md §5 |

`b-other-framework.toml` is well-formed, correctly signed by the active key, and
covers both required targets. It is still worth nothing here, because two
frameworks may use the same target name for entirely different things.

This vector discriminates all three plausible wrong behaviours at once:

| Behaviour | Outcome it produces |
| --------- | ------------------- |
| Ignoring the framework field and counting it | covered — wrong |
| Rejecting the record as unrecognised, or failing to parse it | unverifiable or an error — wrong |
| Ignoring the certificate (correct) | not-covered, missing `t-integration` |
