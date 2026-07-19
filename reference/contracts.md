# Contract v2 and workspace layout

Contract `2.0.0` covers the full source-to-sparse lifecycle. JSON is normative and parsed by a deliberately small standard-library validator that supports only the schema keywords used here.

## Phase 1 contracts

- `contracts/source-manifest.v2.schema.json`: stable source/manifest IDs, imported-original and normalized-text paths/hashes, full-text status, chunks, lines/pages, and limits.
- `contracts/work-queue.v2.schema.json`: exactly one semantic item per manifest chunk.
- `contracts/review-state.v2.schema.json`: manifest/queue-bound ordered prefix plus one interruption-safe active batch.
- `contracts/distilled-chunk.v2.schema.json`: one agent-authored semantic record per chunk.
- `contracts/semantic-review.v2.schema.json`: authored all-chunk source-grounding/quality declaration and limitations.
- `contracts/source-map.v2.schema.json`: exact chunk → record/status/node mapping after finalization.
- `contracts/query-gold.v2.schema.json` and `contracts/trial-report.v2.schema.json`: external authored evaluation expectations and privacy-minimized structural/authored-evidence report.

Workspace:

```text
<workspace>/
├── source-manifest.json
├── work-queue.json
├── source-originals/<source-id>.*
├── sources/<source-id>.txt
├── chunks/<chunk-id>.txt
└── distilled/
    ├── shared-core.md
    ├── source-map.json
    ├── records/<chunk-id>.json
    └── l3/*.md
```

Source IDs derive from relative path plus original SHA-256. Chunk IDs derive from source ID, line range, and exact chunk bytes. Manifest ID derives from canonical manifest content. Queue paths are canonical and the queue/source map carry the SHA-256 of exact `source-manifest.json` bytes.

The validator rechecks archived original bytes, normalized text, text derivation for `.txt`/`.md`, gap-free line coverage, chunk bytes/hashes/IDs, queue paths/state, source-map state, and provenance. PDF normalized text is an explicitly authorized adapter output; validation can prove imported/output identity, not OCR/reading-order fidelity.

## Agent-authored semantic record

Each reusable node contains:

- L0: weighted lexical triggers, expert anti-triggers, and one-line purpose;
- L1: brief, safety red lines, and uncertainty;
- L2: imperative workflow and `load_more_if` conditions;
- L3: a workspace-relative substantive file under `distilled/l3/`;
- risk tags and claim-level chunk/source/line provenance.

Every `complete` record must cite its own chunk through at least one node. `complete_no_reusable_knowledge` requires no nodes and a nonempty reviewed reason. Global anti-trigger notes have `bypass`/`reject` actions; expert anti-triggers belong in node L0. Deterministic validation cannot prove the semantic claims are correct.

## Build contracts

- `contracts/expert-registry.v2.schema.json`: full artifact-derived registry with L1/L2, checksummed L3 files, and checksummed cited chunks.
- `contracts/expert-index.v2.schema.json`: compact routing/safety index matched to the registry SHA/build ID.
- `contracts/routing-policy.v2.json`: fixed normalization/scoring/top-k/sweep policy.

`scripts/build_registry.py` first calls full validation, merges nodes by expert ID, derives terms/anti-triggers/L1/L2/L3/chunks, computes distillation/build hashes, and writes both registry and index. Those build outputs are never substitutes for source records.

## Phase 2 query contracts

- `contracts/query-request.v2.schema.json`: query ID/text, explicit risk domains, and optional top-k.
- `contracts/query-output.v2.schema.json`: registry identity, scores/selection, mandatory sweep, exact checksummed files/chunks, and audit events.

Query requires `expert-index.v2.json` beside the supplied registry. It checks:

1. registry schema and build ID from canonical registry content;
2. actual registry SHA against index;
3. exact index projection against registry;
4. workspace source-manifest hash against registry;
5. selected shared-core/L3/chunk bytes against built hashes.

`load_plan` fields are operational:

- `path_base`: workspace root derived from `<workspace>/build/expert-registry.v2.json`;
- `files_to_load`: shared core, selected L3, and high-risk/ambiguous safety L3;
- `file_checksums`: SHA-256 and role for each listed file;
- `expert_module_files`: selected/safety L3 paths;
- `source_chunks`: exact selected chunk IDs/paths/hashes/source paths/line/page locators.

## Errors and exits

Stable codes include `unprocessed_chunk`, `source_hash_mismatch`, `source_text_hash_mismatch`, `chunk_hash_mismatch`, `chunk_coverage_failure`, `broken_provenance`, `unreferenced_chunk`, `missing_l3`, `manifest_hash_mismatch`, `index_registry_mismatch`, `schema_version_mismatch`, and `malformed_input`.

Lifecycle/query CLIs print compact JSON errors to stderr and exit `2`; success exits `0`. Test/repository validators return nonzero on assertion failure.

## Version discipline

Do not silently reinterpret contract-v2 fields. A breaking shape or semantic change requires a new version, schemas, templates, demo, migration note, and executable failing/passing regression. Skill package version `3.0.0` and lifecycle contract `2.0.0` are separate version axes.
