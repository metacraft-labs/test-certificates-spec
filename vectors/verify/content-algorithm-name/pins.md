# Non-portable algorithm names

**Pins:** Content-Id §1: invalid algorithm identifiers are malformed, even with a lowercase hexadecimal digest; they must not become unverifiable claims or store path components.

Separators, dot names, Windows device names, uppercase, underscores, non-ASCII and an overlong name are rejected before algorithm lookup.
