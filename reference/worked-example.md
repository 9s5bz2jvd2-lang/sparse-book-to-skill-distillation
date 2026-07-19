# Annotated from-zero example

The demo starts from `examples/from-zero/source/synthetic-field-guide.md`, an 18-line repository-authored source that quotes no external book.

## 1. Intake and templates

`scripts/run_lifecycle_demo.py` ingests the source directory with six lines per chunk. Deterministic output has:

- one byte-identical imported original with SHA-256;
- one complete normalized UTF-8 Markdown text with SHA-256;
- three gap-free chunks covering lines 1–6, 7–12, and 13–18;
- one pending queue item and record template per chunk;
- a source-map draft and shared-core placeholder.

## 2. Explicit semantic step

The demo then installs reviewed hand-authored records from `examples/from-zero/curated/records/`, four L3 modules from `examples/from-zero/curated/l3/`, and `examples/from-zero/curated/shared-core.md`.

This installer copies reviewed fixture files only. It performs no keyword extraction or semantic inference. The records demonstrate:

- source intake and coverage ledger;
- agent-reviewed chunk-complete semantic distillation;
- deterministic sparse reading;
- untrusted-source/high-risk safety.

Each contains L0/L1/L2/L3, uncertainty, anti-triggers where justified, and exact line provenance. The finalizer then derives queue statuses and source-map node IDs from those records.

## 3. Completeness validation and build

Validation rechecks imported originals, normalized text, chunk IDs/hashes/coverage, queue/source map, own-chunk provenance, substantive L3 files, and shared core. All three chunks pass with four knowledge nodes.

Build consumes only that validated state and creates four experts plus a compact index. Registry/index carry source-manifest, distillation, build, registry, shared-core, L3, and chunk hashes as applicable. Query requires index-registry equality.

## 4. Sparse query

The request “How do I create a complete source inventory and coverage ledger with stable chunks?” selects only `coverage-ledger` at top-k 1. Its exact plan contains:

1. the workspace `distilled/shared-core.md`;
2. `distilled/l3/coverage-ledger.md`;
3. source chunk `chunk-199c1e4f467e3bd46732`, lines 1–6.

File/chunk hashes are verified before output. The mandatory post-route sweep is active. Audit events cover query/index validation, scores, selection, sweep, and exact plan creation.

## Reproduce and cleanup

```bash
python3 scripts/run_lifecycle_demo.py
```

The default uses then removes `build/from-zero-demo/`. Pass `--keep-workspace` only when you need to inspect generated artifacts, then remove that workspace manually.

For each wrapper command separately, follow `examples/from-zero/README.md`. Executable positive and negative assertions live in `tests/fixtures/lifecycle-cases.v2.json` and run with:

```bash
python3 scripts/run_lifecycle_tests.py
```

The synthetic demo proves the local contract loop, not semantic correctness for arbitrary books or PDF extraction fidelity.
