# Implementation guide — commands, workspaces, and test inventory

This guide carries the dense operational detail for the executable lifecycle so that
`README.md` can stay focused on the design core (network → ring → sphere). Nothing here
changes any contract; `contracts/` schemas and `contracts/routing-policy.v2.json` remain
normative. Conceptual background lives in `README.md`, `SKILL.md`, `CACHE.md`, and
`GRAPH.md`.

## Requirements

- Python 3.10 or newer;
- no third-party Python runtime packages;
- local files only; no network or dependency installation;
- optional PDF input only through an already-installed `pdftotext`, after explicit
  `--allow-pdftotext` authorization.

Git is used only for repository review gates such as `git diff --check`, not by the lifecycle.

## Phase 1 — full distillation once

From the repository root:

```bash
python3 scripts/intake.py \
  --source path/to/book-or-material-directory \
  --workspace build/my-book \
  --chunk-lines 80

python3 scripts/prepare_distillation.py --workspace build/my-book
```

Intake accepts one UTF-8 `.txt`/`.md` file or a recursively read directory. It rejects visible unsupported files, symlinks, invalid UTF-8, empty input, a nonempty workspace, more than 1,000 visible files, any file over 20 MiB, or more than 50 MiB total. Hidden files are deliberately outside the declared source set. Chunks contain 1–1,000 physical lines; this is not tokenization.

The workspace contains:

```text
build/my-book/
├── source-manifest.json
├── work-queue.json
├── review-state.json       # ordered durable batch/resume checkpoint
├── source-originals/       # byte-identical imported inputs
├── sources/                # normalized complete UTF-8 text
├── chunks/                 # gap-free stable line chunks
└── distilled/
    ├── shared-core.md
    ├── semantic-review.json # authored all-chunk quality declaration
    ├── source-map.json
    ├── records/            # one agent-authored record per chunk
    ├── l3/                 # substantive human-facing depth views
    ├── atoms/              # fine-grained authored nodes (graph layer)
    └── atom-coverage.json  # exact chunk/status/atom-ID accounting
```

### Required semantic step

For every item in `work-queue.json`, an agent or human must:

1. read the **entire** `chunk_path`, not a preview or extracted keywords;
2. verify its ID/hash and source/line/page locator against `source-manifest.json`;
3. complete the matching record with either `complete` or a reviewed `complete_no_reusable_knowledge` reason;
4. author source-grounded L0 triggers/anti-triggers, L1 brief/red lines/uncertainty, L2 workflow/escalation, and a substantive L3 module;
5. cite each reusable node with known chunk/source IDs and line ranges inside the cited chunk;
6. replace the shared-core placeholder;
7. author `distilled/semantic-review.json`, binding the manifest and every queue chunk while recording review criteria and limitations.

For long material, use durable contiguous batches:

```bash
python3 scripts/review_queue.py next --workspace build/my-book --batch-size 3
# read and author every returned item; interruption-safe `next` returns the same batch
python3 scripts/review_queue.py checkpoint --workspace build/my-book
```

The default batch size is 3; it may change only between batches, never on an active slice. Only checkpoint can advance: it commits the longest valid contiguous authored prefix of the active slice (a pending head commits nothing; an invalid non-pending prefix record hard-fails with state unchanged). Prefix validation is structural/identity/provenance only, not semantic truth. Out-of-order, tampered, or falsely complete progress is rejected. See `reference/full-distillation-workflow.md`, `reference/real-material-trial.md`, and the templates in `assets/`. Chunking or lexical extraction must never be described as semantic distillation.

After authoring:

```bash
python3 scripts/finalize_distillation.py --workspace build/my-book
python3 scripts/validate_distillation.py --workspace build/my-book
python3 scripts/build_registry.py --workspace build/my-book
```

`build_registry.py` reruns full validation; it cannot build from pending or invalid input. Successful build outputs:

- `build/my-book/build/expert-registry.v2.json`;
- `build/my-book/build/expert-index.v2.json`.

Both use contract `2.0.0`. The compact index and registry cross-check each other by registry SHA-256 and build ID. Selected L3 and source-chunk hashes are verified again at query time.

## Phase 2 — repeated sparse reading

```bash
python3 scripts/query.py \
  --registry build/my-book/build/expert-registry.v2.json \
  --query "your task" \
  --query-id local-001 \
  --top-k 2 \
  --print-load-plan \
  --pretty
```

Alternatively pass `--request` with `contracts/query-request.v2.schema.json`.

The reference router is deterministic lexical routing: Unicode NFKC, casefold, whitespace collapse, weighted substring hits at most once per term, expert anti-triggers, global bypass/reject anti-triggers, threshold, top-k, and stable score-descending → priority-ascending → ID-ascending ties. It does not use embeddings, an LLM, or semantic similarity.

Every contract-valid selected, below-threshold, bypassed, or rejected query emits:

- `safety_sweep.activated=true` and `phase=post_route`;
- baseline safety checks;
- high-risk/ambiguous extra checks and `safety-governance` outside semantic top-k when that distilled expert exists;
- exact checksummed `files_to_load` and source chunks;
- registry/build hashes, route scores, decision, and ordered audit events.

The agent then reads only the listed shared core, selected/safety L3 modules, and cited source chunks. Sparse reading begins **after** complete distillation; it never licenses sparse source ingestion.

### Phase 1B — author and build the fine-grained graph/vector layer

After the v2 distillation is valid, author one schema-valid atomic node per reusable definition/formula/variable-condition/counterexample/workflow/evidence/red-line unit under `distilled/atoms/`, plus an exact `distilled/atom-coverage.json`. External authored bundles may provide `atoms/` and `atom-coverage.json` together; the ordinary installer validates/copies the pair and changes only the workspace manifest binding.

```bash
python3 scripts/graph_build.py --workspace build/my-book
```

This deterministically rebuilds the validated base registry, then writes `build/graph-registry.v1.json` and a graph-bound `build/vector-index.v1.json`. Atomic authoring follows `contracts/atomic-node.v1.schema.json`; the bundled semantic/task/risk vectors are deterministic synthetic interface fixtures, not learned embeddings or semantic-quality proof.

### Phase 2B — query atoms repeatedly and preserve residual state

```bash
python3 scripts/graph_query.py \
  --graph-registry build/my-book/build/graph-registry.v1.json \
  --query "your task" \
  --query-id graph-001 \
  --output build/my-book/routes/graph-001.json \
  --residual-output build/my-book/residual-bank.json \
  --print-load-plan --pretty

python3 scripts/graph_query.py \
  --graph-registry build/my-book/build/graph-registry.v1.json \
  --query "follow-up task" \
  --query-id graph-002 \
  --residual-bank build/my-book/residual-bank.json \
  --output build/my-book/routes/graph-002.json \
  --residual-output build/my-book/residual-bank.json \
  --pretty
```

Routing performs coarse-domain gating, atomic lexical/vector union, current-query-supported prior-only residual revisit, then **one** hard-bounded dependency/provenance/safety closure. If required candidate or safety nodes cannot fit, it fails closed. The residual bank preserves all prior entries and appends the exact final selected state; full route and residual files are written atomically per file.

The residual bank is the executable inner return loop of the ring described in `README.md`: selected state flows back into the bank so a later related query can revisit it cheaply, but only when the current query itself supports the revisited nodes. It does not rewrite signatures, triggers, or the index; that outer improvement remains a human-gated proposal (`docs/self-evolution-loop.md`).

## Redistributable from-zero demonstration

The bundled source is synthetic and repository-authored. Its curated records/L3 files were written and reviewed in advance to demonstrate the otherwise manual semantic step; the installer does not infer them.

One command:

```bash
python3 scripts/run_lifecycle_demo.py
```

Exact wrapper sequence:

```bash
python3 scripts/intake.py --source examples/from-zero/source --workspace build/from-zero-manual --chunk-lines 6
python3 scripts/prepare_distillation.py --workspace build/from-zero-manual
python3 scripts/install_demo_artifacts.py --workspace build/from-zero-manual --curated examples/from-zero/curated
python3 scripts/finalize_distillation.py --workspace build/from-zero-manual
python3 scripts/validate_distillation.py --workspace build/from-zero-manual
python3 scripts/build_registry.py --workspace build/from-zero-manual
python3 scripts/query.py --registry build/from-zero-manual/build/expert-registry.v2.json --request examples/from-zero/request.json --print-load-plan --pretty
```

Remove `build/from-zero-manual/` after inspecting it. The one-command demo cleans its own `build/from-zero-demo/` workspace by default; `--keep-workspace` is inspection-only.

## Authorized real-material trial (external content only)

No real book is bundled. Use external authorized source/artifacts/query gold and keep restricted material outside the repository:

```bash
python3 scripts/real_material_trial.py prepare --source /authorized/material --workspace /private/trial --chunk-lines 80
# process all review_queue.py batches and author semantic-review.json
python3 scripts/real_material_trial.py evaluate --workspace /private/trial --query-gold /private/query-gold.json --report /private/trial-report.json
```

An optional external authored bundle (`records/`, `l3/`, `shared-core.md`, `semantic-review.json`, and optionally the complete `atoms/` + `atom-coverage.json` pair) is accepted with `--authored`. The report omits source/query bodies and workspace paths. It separately reports deterministic coverage/failures/route recall/source-load correctness and externally supplied semantic-review/human scores; absent semantic scores are never inferred. Full commands and interpretation are in `reference/real-material-trial.md` and `docs/real-material-readiness.md`.

## Validation and tests

```bash
python3 scripts/run_lifecycle_tests.py
python3 scripts/run_readiness_tests.py
python3 scripts/run_graph_tests.py
python3 scripts/validate.py
python3 scripts/check_concept_continuity.py
python3 scripts/run_lifecycle_demo.py
python3 scripts/benchmark.py
python3 scripts/check_doc_paths.py
python3 -m compileall -q .
```

The graph suite adds authored-atom installation, exact v2→atom coverage binding, multidimensional vector metadata/sidecar binding, lexical/vector union, scoped safety, one fail-closed closure, prior-only append-only residual revisit, deterministic rebuild, CLI persistence, and exact final load-state checks. Serial/parallel Skill composition remains explicitly deferred.

The executable lifecycle suite covers successful full lifecycle; recomputed original/text/chunk hashes and queue coverage; pending and missing chunks; bad artifact/imported-source hashes; bad line and source provenance; missing L3; build-before-validation refusal; artifact-derived registry/index; registry/build/index and shared-core/L3/chunk checksum binding; positive exact L3/chunk load plans; threshold, top-k, stable ties, global/per-expert anti-triggers; baseline sweeps for selected/below-threshold/bypassed/rejected routes; high-risk/ambiguous safety activation; malformed input; version mismatch; and default demo cleanup.

The readiness suite adds 300 generated chunks, interrupted-batch replay, longest-valid-prefix checkpointing with empty-prefix refusal and injected-fault recovery, out-of-order refusal, all-chunk semantic-review gating, and the external query-gold/report harness. It proves only these structural behaviors. It does not turn the generated source or pre-authored demo into evidence of real-book semantics.

`scripts/check_concept_continuity.py` is a phrase/binding conceptual-continuity regression gate: it fails repository validation if the network→ring→sphere design core, connected low-power anchors, implemented-versus-protocol-only status boundary, or named executable bindings are removed. It does not prove semantic non-contradiction; reviewers still own that judgment.

CLI contract/lifecycle errors are compact JSON on stderr and exit `2`. Test/repository validation failures are nonzero. Success is `0`. Structural checks cannot prove that an agent's semantic interpretation is correct; source-aware review remains mandatory.

## Repository map

- `SKILL.md` — agent-facing routing hub;
- `contracts/` — contract-v2 schemas and fixed routing policy;
- `scripts/` — standard-library lifecycle and validators;
- `reference/` — detailed workflow, contracts, trust, and worked example;
- `examples/from-zero/` — synthetic source plus reviewed demo artifacts;
- `tests/fixtures/lifecycle-cases.v2.json` — executable expectations;
- `CACHE.md`, `GRAPH.md`, `ROUTING.yaml`, and `RULES.md` — aligned non-duplicative policy/docs;
- `assets/output-template.md` and diagrams — delivery and architecture aids.
