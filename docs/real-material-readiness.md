# What real-material readiness evidence means

The executable readiness additions are deliberately narrower than a semantic-quality claim.

## Proven by local deterministic tests

- an active review batch survives interruption and is returned unchanged;
- only the next contiguous queue slice can be checkpointed, and checkpoint commits the longest valid contiguous authored prefix (a pending head commits nothing; invalid prefix records and injected write faults leave state unchanged);
- out-of-order, tampered, or falsely complete progress is rejected;
- the default review batch size is 3 and may change only between batches; stored batch sizes from older workspaces (for example 20) remain loadable and drainable;
- 300 generated redistributable chunks can be processed in 17-item batches and cleaned up;
- build validation requires a manifest-bound, all-chunk semantic-review declaration with every review criterion affirmed;
- an external authored query-gold file can measure route/status recall and exact source-chunk loading while omitting source/query bodies and private paths from the report;
- existing source/security/integrity/query gates still execute.

## Not proven

The generated scale source does not prove understanding of a real book. The bundled fixture remains synthetic and pre-authored. No repository test proves faithful real-material interpretation, route gold quality, answer correctness, professional safety, PDF/OCR fidelity, legal reuse, model-token savings, latency, cost, or generalization.

A real claim requires an authorized external source, actual complete semantic reading, authored review evidence, independently authored query gold, human/domain scores, and inspection of failures. Follow `reference/real-material-trial.md`; do not commit restricted trial material.
