**Pins:** Published pieces retain their order; missing scoped payload and corrupt piece append in incoming order; the minimal payload is not duplicated.

Transport §3.1, “Merging two notes”. Inputs and expected bytes are assembled
by hand from the named payload vectors or existing notes records, never by a
merger. `base.txt` is published; the opposite direction may differ.

Would be wrong if a merger selected one whole side, sorted the pieces,
verified signatures to choose a winner, or repeatedly appended existing text.
