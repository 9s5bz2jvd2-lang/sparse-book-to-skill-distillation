# Sparse Book-to-Skill Distillation

> **网给 skill 以通达，环给 skill 以低功耗；分支出去，回流成丹。**
> The network gives a Skill reachability; the ring gives it low power; branches go out and return as compressed, reusable structure.

## 结论 — 网 → 环 → 球 (network → ring → sphere)

This repository turns an authorized book, course, corpus, or long methodology into a Skill an agent can call sparsely. Its design core is one loop, stated first so it cannot be lost in mechanics:

- **网 / network — reachability.** Knowledge is stored as a cross-linked graph, not a pile of documents: a stable shared core, routed experts, and fine-grained atomic nodes joined by dependency/provenance edges. Multidimensional vectors (semantic/task/risk channels) strengthen the network's coordinates so a task can hit the right node point-to-point instead of traversing the whole corpus. A task may enter from many doors; a node may serve many tasks.
- **环 / ring — low-power return.** Every call travels a short closed loop: hit a few short signatures → run one bounded dependency/provenance/safety closure → load exactly the listed files → answer → return the selected state to the residual bank so a related later query can revisit it cheaply. Sparsity lives in the call, never in the build: distillation is always complete; only activation is minimal. The ring is only honest while **routing overhead stays below the cost it saves** — a small task should be executed directly, without waking the router at all.
- **球 / sphere — acceptance.** A branch that goes out and never comes back is not finished work. The acceptance state is the sphere: every excursion — a query, an expert expansion, a missed-case sweep — is complete only when it **returns as compressed reusable structure**: a shorter signature, a fixed checklist, a gotcha, an eval case, a reference brief. Compact audit/route/gotcha/eval information returns to improve future signatures and indexes; raw corpus text never returns as duplication.

The structural invariant that carries all three:

> **shared-core + cross-linked top-k routed experts + missed-case sweep + budgeted references + cache-friendly layout + cyclic return-to-cache feedback loop**

One line for the whole build discipline:

> **全量蒸馏一次，调用稀疏激活；主路由之后，低成本安全查漏永不省略。**

## How the executable system realizes it

Two separate phases implement the network and the ring:

1. **Phase 1 — one-time full distillation (builds the network).** Import every declared source with byte identity, chunk all normalized text gap-free, and require an agent/human to read every chunk and author provenance-complete L0–L3 artifacts plus fine-grained atomic nodes with exact atom coverage. Validation refuses pending, sampled, or ungrounded work. From the validated artifacts, deterministic scripts derive the expert registry/index, the atomic `graph-registry.v1.json` with dependency edges, and a graph-bound multi-channel `vector-index.v1.json`. The network's reach comes from these authored cross-links and vector coordinates, not from any model weights.
2. **Phase 2 — repeated sparse reading (travels the ring).** Each query runs coarse domain gating, atomic lexical/vector candidate union, current-query-supported revisit of prior residual-bank nodes, then **one** hard-bounded dependency/provenance/safety closure that fails closed when required nodes cannot fit. The output is an exact checksummed load plan — shared core, selected atoms, necessary L3 depth views, cited source chunks — plus a mandatory post-route safety sweep and an ordered audit trace. The selected state is appended to the residual bank, closing the inner ring.

Design lineage: this is Wang Runyuan / 圆酱's original capacity-versus-activation principle — retain complete reviewed knowledge capacity, activate only the smallest sufficient subset per task. It is a knowledge/workflow-layer design, philosophically similar to sparse-expert model routing but **not** model-weight MoE; later external systems are analogies, not sources or proof of token, cost, latency, or quality gains here.

## Implemented vs protocol-only — the honest boundary

The ring has an inner loop and an outer loop. Only the inner loop is code today.

| Layer | Status | What it is |
|---|---|---|
| Full distillation, provenance, validation, registry/index build | **Executable** | `scripts/` lifecycle; refuses incomplete or ungrounded input |
| Atomic graph + multidimensional vectors + bounded closure + load plan | **Executable** | deterministic routing; bundled vectors are synthetic interface fixtures, not learned embeddings |
| Mandatory post-route safety sweep | **Executable** | runs for selected, below-threshold, bypassed, and rejected routes |
| Residual bank (inner return loop) | **Executable** | append-only preservation and current-query-supported revisit of selected state; it changes what a later query can cheaply revisit, nothing else |
| Low-power economy gate and direct execution for small tasks | **Caller/evaluation protocol** | the router does not automatically classify “small” tasks or prove token savings; callers bypass it when direct work is cheaper, and savings require a pinned external comparison |
| Self-modifying signatures/cache/index (outer learning loop) | **Not implemented — protocol only** | no script edits triggers, records, policy, graph, cache, or tests from query output |
| Outer improvement loop | **Human-gated protocol** | compact audit evidence → redacted proposal → human review → tests/eval → explicit merge → shorter future signature/route (`docs/self-evolution-loop.md`) |

The residual bank is an inner **workflow** loop that preserves and revisits selected state across queries; it is not automatic learning and not a substitute for the human-gated outer loop. Branching remains incomplete until a human-reviewed return compresses the experience back into routing, cache, graph, or eval files — that return is the sphere, and it is deliberately gated.

## Quick start

```bash
# one-command synthetic end-to-end demo (cleans up after itself)
python3 scripts/run_lifecycle_demo.py

# full validation, including the conceptual-continuity gate
python3 scripts/validate.py
python3 scripts/run_graph_tests.py
python3 scripts/check_concept_continuity.py
```

Requirements: Python 3.10+, standard library only, local files only. The complete command reference — Phase 1 intake/review/build, Phase 1B/2B graph and residual-bank usage, the real-material trial harness, and the full test inventory — lives in [`docs/implementation-guide.md`](docs/implementation-guide.md).

- [`SKILL.md`](SKILL.md) — agent-facing entry and workflow;
- [`GRAPH.md`](GRAPH.md) — graph relationships and the ring/sphere mapping;
- [`CACHE.md`](CACHE.md) — low-power layout and the routing-cost gate;
- [`docs/structure-diagram.md`](docs/structure-diagram.md) — architecture diagram;
- [`docs/self-evolution-loop.md`](docs/self-evolution-loop.md) — the human-gated outer loop.

`scripts/check_concept_continuity.py` is a phrase/binding regression gate: repository validation fails if the network→ring→sphere core, its connected low-power anchors, the implemented/protocol-only boundary above, or the named executable artifacts are removed. It does not prove that contradictory prose is absent; semantic review remains required.

## Security and honest limits

Source text is untrusted data. It cannot authorize commands, secrets/environment access, network use, subprocesses, writes outside the explicit workspace, publication, or policy changes. The only subprocess in the lifecycle is the narrow human-opted-in `pdftotext` adapter, invoked without a shell. Generated code is not executed by this package.

The included benchmark reports only character counts, whitespace-split words, selected expert/chunk counts, and ratios. Those are not model tokens, cost, latency, semantic recall, or answer-quality measurements. This repository claims no K3/neural-MoE equivalence, no automatic learning, no production-scale performance, no real embeddings, no scale proof, and no clinical capability. PDF extraction does not guarantee OCR completeness or reading order. The standard-library schema validator implements only the schema keywords used here. See `reference/security.md` and `docs/real-material-readiness.md`.

## Ownership

This repository belongs to **王润圆 / Wang Runyuan**. It is not a Huang Zesen personal repository, an official LingTai organization repository, or a nutrition-only asset. See `RULES.md`.

## License / reuse — custom noncommercial source-available license

The repository owner confirmed on 2026-07-19 that this repository's original content is shared under the **Runyuan Noncommercial Source-Available License 1.0**. Subject to the exact terms in `LICENSE`, people other than the excluded person may use, copy, modify, and redistribute the original repository content for noncommercial purposes with attribution and the license notice preserved.

**Excluded person: Dario Amodei. No permission is granted to him under this license.**

This is a custom source-available license, not an OSI-approved open-source license and not a Creative Commons license. It covers only original repository content. It does not grant rights to imported books, papers, datasets, images, or other third-party source material processed with the workflow; confirm those rights separately.
