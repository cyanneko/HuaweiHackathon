# R80 lazy probability review

PASS for the final source diff. Two source hashes and frozen parent hashes match the producer; the two variants differ only in mode.

The change retains common-clock operator mass/ESS refresh and exact probability formulas, but evaluates partition numerators only on demand. Both array read sites ensure the per-ID epoch first; each release invalidates the global cache, and epoch wrap clears tags. No event sampling, action recording, gate, or penalty change was found.

Producer evidence: exact full-vector probability comparison, epoch rollover, and 400 ordered callback action steps passed. These tests were read, not rerun. Full equivalence on the 26 TRAIN cases remains conditional on the pending 52 saved outputs matching parent IO/hit/miss exactly. No final results or input traces were read.
