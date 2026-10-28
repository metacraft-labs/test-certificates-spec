# Opaque unknown content algorithm

**Pins:** Transport §2.2 and Tooling §2: a relay stores a well-formed unknown algorithm and digest verbatim, without computing the algorithm.

The payload is `store/unsigned` with only `content` replaced by `future-v2:a`; the one-hex-digit digest is valid because its algorithm defines its length, not the reader. This does not authorize issuance with an unknown algorithm.
