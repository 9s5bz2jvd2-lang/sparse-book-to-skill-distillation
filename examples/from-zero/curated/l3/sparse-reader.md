# L3: sparse expert reading

Sparse reading is allowed only after completeness validation and registry build.

## Runtime algorithm

1. Validate the versioned query and exact registry/index SHA/build correspondence.
2. Normalize query text with Unicode NFKC, case folding, and whitespace collapse, then apply derived global/per-expert anti-triggers.
3. Add each matched built trigger weight at most once.
4. Keep experts at or above the built threshold; sort score descending, priority ascending, ID ascending; cap at top-k.
5. Run the mandatory post-route sweep for selected, below-threshold, bypassed, and rejected outcomes.
6. Add the safety module outside semantic top-k for high-risk or ambiguous routes.
7. Verify and return exact checksummed shared-core, selected L3 module, and cited source-chunk paths with line provenance and audit events.

This is deterministic lexical routing, not semantic similarity or learned intelligence. Selected-file ratios and character counts do not prove token or answer-quality savings.

## Provenance

Derived from synthetic source chunk `chunk-142536ab10af131e3e9d`, lines 13–16.
