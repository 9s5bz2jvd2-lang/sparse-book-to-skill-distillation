# Changelog

## Unreleased — network→ring→sphere conceptual-core restoration

### Restored

- restored the original low-power design core as the repository's leading contract: 网 (cross-linked network gives reachability) → 环 (low-power return ring) → 球 (acceptance state where branches return as compressed reusable structure), including the motto 「网给 skill 以通达，环给 skill 以低功耗；分支出去，回流成丹」 and the structural invariant `shared-core + cross-linked top-k routed experts + missed-case sweep + budgeted references + cache-friendly layout + cyclic return-to-cache feedback loop`;
- restored the low-power acceptance gate (routing overhead must stay below the cost it saves; small tasks execute directly), the point-to-point-versus-traversal network principle, and the ring's return-to-cache leg in `CACHE.md`;
- restored the ring/sphere return-discipline mapping and the bounded micro-task-model analogy in `GRAPH.md`, and the return-loop product rule in `RULES.md`;
- integrated the restored core with the current executable system: the graph registry/vector index realize the network, the bounded closure plus append-only residual bank realize the executable inner ring, and `docs/self-evolution-loop.md` is explicitly the human-gated outer ring.

### Added

- `scripts/check_concept_continuity.py`, a phrase/binding conceptual-continuity regression gate wired into `scripts/validate.py`: repository validation now fails if the network/ring/sphere core, low-power anchors, return-to-cache invariant, implemented-versus-protocol-only status boundary, or named executable inner-ring bindings are removed; semantic non-contradiction still requires review;
- `docs/implementation-guide.md`, carrying the dense CLI/workspace/test inventory moved out of `README.md` so the README stays conclusion-first (no command or test was removed).

### Unchanged

- all contracts, schemas, lifecycle/graph/readiness behavior, safety boundaries, ownership, and the custom license text are unchanged; this is a documentation-and-gate restoration, not a contract change. Automatic self-modifying signatures/cache remain not implemented; outer improvement remains human-gated.

## 3.0.0 — atomic graph/vector Phase-1 upgrade (2026-07-19)

### Added

- atomic definition/formula/condition/counterexample/workflow/evidence/red-line contracts with exact source/chunk or explicit synthetic-fixture provenance;
- complete atom-coverage binding from validated v2 records to exact atom IDs, including reviewed no-atomizable decisions and fixture-laundering rejection;
- deterministic multi-stage lexical/vector routing with versioned semantic/task/risk channels, strict metadata/sidecar binding, symbolic rerank and pluggable future-backend failure policy;
- current-query-supported prior-only residual revisit, append-only versioned residual persistence, one bounded dependency/provenance/safety closure, exact final selected/rejected/load-plan state, and atomic per-file CLI output writes;
- ordinary authored-bundle installation of the complete `atoms/` + `atom-coverage.json` pair, graph build/query commands, one-command demo coverage, and a 42-case graph suite (41 active passes plus one explicitly deferred composition case).

### Changed

- made fine-grained atomic nodes—not whole L3 documents—the smallest addressable unit while retaining L3 as a human-facing depth view;
- made lexical/vector/residual candidates and scoped safety enter one fail-closed closure before final outputs are materialized;
- made the installer validate the full authored semantic/atomic bundle before copying and made demo cleanup refuse the build root itself;
- made lifecycle, graph, and CLI JSON artifacts use one unique-temp/fsync/replace writer instead of fixed-name temporary files;
- made resume refuse malformed or identity-mismatched existing chunk artifacts, and made graph routing reject mixed unknown vector channels while preserving valid single-channel queries;
- made graph atom-directory and atom-file binding failures explicit structured errors rather than incidental filesystem exceptions;
- made shebang-bearing scripts executable and consolidated duplicate Phase-2 instructions.

### Publication and license

- The repository owner confirmed the custom Runyuan Noncommercial Source-Available License 1.0 on 2026-07-19, with Dario Amodei as the excluded person. It is not an OSI-approved or Creative Commons license. Imported source rights remain separate and are never inferred from the repository license.

### Honest limits

The bundled vectors are deterministic synthetic interface fixtures, not learned embeddings. This phase does not prove real-book semantic quality, scale/performance, token savings, K3/neural equivalence, serial/parallel Skill composition, micro-model assembly, publication readiness for imported source material, or installation.

## Local source-to-sparse v2 proposal (2026-07-10)

### Historical publication gate — resolved in 3.0.0

- The local v2 working copy intentionally deferred the repository license choice. For 3.0.0, the owner confirmed the custom noncommercial source-available license recorded in `LICENSE`; external source rights remain separate.

### Added

- contract `2.0.0` source manifest, work queue, per-chunk semantic artifact, source map, built registry, compact index, query request/output, and lifecycle fixture schemas;
- standard-library intake, original-byte archive, normalized full text, stable line chunks, queue/templates, finalization, completeness/provenance validator, artifact-derived registry/index build, and lexical sparse query;
- query-time registry/index identity checks and selected shared-core/L3/chunk checksum verification;
- mandatory post-route sweep, high-risk/ambiguous safety activation outside semantic top-k, exact load plan, and audit trace;
- synthetic redistributable source, reviewed per-chunk semantic records, L3 modules, shared core, one-command demo, exact wrapper flow, and 28-case executable lifecycle suite;
- explicit untrusted-source, PDF adapter, generated-action, and human-gated evolution policies;
- manifest-bound contiguous review batches with interruption/resume checkpoints, an authored semantic-review quality contract, and an external real-material query-gold/trial report harness;
- a 300-chunk redistributable generated scale regression that is explicitly structural evidence only, not real-book semantic proof.

### Changed

- replaced stale prompt-only/v1 registry claims with a real two-phase source-to-sparse lifecycle;
- made `ROUTING.yaml` a v2 lifecycle locator rather than a competing expert registry;
- aligned README, Skill, rules, cache, graph, diagrams, templates, references, examples, eval overview, and self-evolution docs to contract `2.0.0`;
- made semantic distillation explicitly agent/human-performed for every chunk, never faked by deterministic keywords;
- made caller-supplied source-root symlinks reject before path resolution, with an executable regression and explicit non-pass skip reporting on platforms that cannot create symlinks;
- made the compact sparse index a required, validated query input matched to its registry;
- made selected L3/source chunks checksummed and the baseline safety sweep unconditional for every contract-valid route status;
- explicitly recorded Wang Runyuan / 圆酱's original design principle: retain complete reviewed knowledge capacity while sparsely activating only the smallest sufficient task-specific subset, without claiming model-weight MoE or unmeasured efficiency/quality gains.

### Compatibility

This is a breaking transition from the earlier unversioned/prompt-only design and the superseded local v1 hand-authored-registry attempt. There is no silent migration. Rebuild from authorized sources with the contract-v2 lifecycle; do not relabel a v1 registry as a complete v2 distillation.
