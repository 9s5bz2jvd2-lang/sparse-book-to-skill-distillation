# Skill graph and control-flow reference

This document explains the contract-`2.0.0` lifecycle. It is not a second registry. Runtime expert IDs/terms/modules/provenance are derived from validated per-chunk artifacts into each workspace's registry/index; fixed scoring/sweep policy lives in `contracts/routing-policy.v2.json`.

## Two-phase graph

```text
PHASE 1 — COMPLETE ONCE
legally accessible local source set (untrusted data)
  -> original-byte archive + normalized full text + stable gap-free chunks
  -> one pending queue/template per chunk
  -> agent/human reads every complete chunk
  -> source-grounded L0 + L1 + L2 + substantive L3 (or reviewed no-reusable reason)
  -> finalize queue/source map
  -> hash/coverage/contract/provenance/L3/shared-core validation
  -> derived versioned expert registry + compact matching index

PHASE 2 — SPARSE REPEATEDLY
versioned query + built registry/index
  -> index/registry/hash validation
  -> lexical anti-trigger + score + threshold + stable top-k
  -> mandatory post-route baseline safety sweep
  -> high-risk/ambiguous extra checks + safety module outside semantic top-k
  -> exact checksummed shared-core/L3/source-chunk load plan
  -> compact audit
```

The Phase-1 branch cannot close while any declared chunk is pending, unreferenced, changed, or missing required L3. The Phase-2 branch cannot skip the baseline sweep for selected, below-threshold, bypassed, or rejected outcomes.

## Artifact relationships

```text
source-manifest.json
  ├── source-originals/<source-id>.*
  ├── sources/<source-id>.txt
  └── chunks/<chunk-id>.txt
          │
work-queue.json ── one item per chunk
          │
          ▼
distilled/records/<chunk-id>.json ── cites known chunks/lines
          ├── distilled/l3/*.md
          ├── distilled/shared-core.md
          └── distilled/source-map.json
                    │ full validation
                    ▼
build/expert-registry.v2.json ⇄ build/expert-index.v2.json
                    │ query
                    ▼
query-output: selection + mandatory sweep + exact load plan + audit
```

The compact index contains only routing/sweep fields, selected-file hashes, and chunk IDs. The registry carries L1/L2 details plus checksummed L3/chunk provenance. Query requires their exact correspondence.

## Safety edge

```text
route decision
  -> baseline checks (always)
  -> high-risk? OR below-threshold/cutoff-tie ambiguity?
       ├── yes: extra checks + built safety-governance if present
       └── no: no extra safety module
  -> checksummed sparse load plan
```

Safety activation is recorded separately and does not consume semantic top-k. The lexical sweep is a guard/checklist, not a sandbox or professional review.

## Conceptual neighbors

These are optional workflows, not runtime dependencies. Do not fetch or execute them silently.

| Neighbor | Relationship |
|---|---|
| 归一 | distills completed project experience into maintainable Skill instructions |
| skills-manual | validates Skill structure/frontmatter and progressive disclosure |
| textbook-distillation | study-oriented material processing rather than this callable-source lifecycle |
| legal/copyright/domain review | human gate for publication or consequential claims |
| human delivery renderer | presents already validated machine artifacts |

## Anti-use boundary

This package is not a summary service, source/copyright bypass, private-fact store, model-weight MoE, embedding/semantic search system, generated-code executor, or autonomous self-modifier. Its router is deterministic lexical indexing over agent-authored semantic artifacts.

## Ring and sphere — the return discipline

网给 skill 以通达，环给 skill 以低功耗；分支出去，回流成丹。 The graph above supplies reachability (网). The ring (环) is the low-power closed loop each query travels; the sphere (球) is the acceptance state: **a branch is incomplete until it returns as compressed reusable structure.**

| Cyclic-return language | This system's realization | Status |
|---|---|---|
| outward trajectory | one query, one expert/atom expansion, one sweep branch | executable |
| coarse-graining | compressing the excursion into signature/checklist/gotcha/eval/reference-brief updates | human-gated protocol |
| durable center | shared core, contracts, routing policy, `CACHE.md`, `GRAPH.md` | executable artifacts |
| return map | residual bank appends exact selected state; audit evidence feeds a reviewed proposal | inner loop executable; outer loop human-gated |
| continuity invariant | purpose, red lines, and output contract do not drift per call | mechanically guarded by contracts/tests; semantic continuity still requires review |
| low-power intuition | next call re-reads less: revisit supported residual nodes, hit shorter signatures | residual revisit executable; signature shortening human-gated |

At the end of every nontrivial call, ask: which hit could become a shorter signature; which sweep exposed a new cross edge; which explanation should sink to a brief; which gotcha/eval must be added; which detail is noise to prune. Those answers become proposal material, never silent edits.

## The Skill as a micro task model — analogy and its boundary

A Skill carrying judgments, triggers, workflows, atoms, scripts, and references can be read as an **externalized, editable, micro task model**:

| Model concept | This Skill's counterpart |
|---|---|
| parameter memory | validated records, L3 views, atoms, shared core |
| input interface | triggers, anti-triggers, query contract |
| gate | lexical/vector routing signatures and graph edges |
| expert | routed expert / atomic node working set |
| shared layers | shared core: copyright, privacy, safety, evidence lines |
| eval | lifecycle/graph/readiness suites and eval cases |
| continual learning | route evidence → human-reviewed proposal → merge |

The boundary stays hard: it is not a neural model, does not generalize, and never trains itself. It stays callable like a micro model only through short entries, a light gate, on-demand heavy material, and reviewed feedback — otherwise it degrades into a pile of long documents.

## Feedback edge

```text
compact query-output evidence
  -> redacted separate proposal
  -> human reviews exact artifact/policy/schema/test diff
  -> lifecycle regressions + repository validation
  -> explicit merge or rejection
```

No repository script edits semantic artifacts, routing policy, graph, cache, or tests from query output. See `docs/self-evolution-loop.md`.
