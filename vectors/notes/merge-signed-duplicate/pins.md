**Pins:** A signed published duplicate protects the payload even when an unsigned match precedes it.

Transport §3.1, “Merging two notes”. Inputs and expected bytes are assembled
by hand from the named payload vectors or existing notes records, never by a
merger. `base.txt` is published; the opposite direction may differ.

Would be wrong if a merger selected one whole side, sorted the pieces,
verified signatures to choose a winner, or repeatedly appended existing text.
