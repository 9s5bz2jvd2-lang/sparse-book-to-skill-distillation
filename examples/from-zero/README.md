# From-zero lifecycle fixture

This fixture is repository-authored and quotes no external book.

- `source/synthetic-field-guide.md` is the input source.
- `curated/records/` and `curated/l3/` are reviewed, hand-authored semantic artifacts. They demonstrate the required agent/human step; no script inferred them.
- `curated/shared-core.md` is the reviewed stable core; `curated/semantic-review.json` is the fixture authors' manifest-bound declaration and explicitly applies only to this synthetic source.
- `curated/atoms/` contains seven schema-valid atomic fixtures covering definition/formula/condition/counterexample/workflow/evidence/red-line kinds; `curated/atom-coverage.json` binds all fixture chunks to exact atom IDs. The ordinary installer copies this pair after validation and replaces only its manifest-hash placeholder.
- `request.json` is a versioned sparse-read query.

## One-command lifecycle

From the repository root:

```bash
python3 scripts/run_lifecycle_demo.py
```

The command creates a new `build/from-zero-demo/`, imports originals/full text/chunks, creates pending templates/queue, installs the pre-reviewed semantic + atomic artifacts, finalizes and validates completeness/provenance, builds the base registry/index and graph/vector registry, runs both sparse queries, prints exact checksummed traces, and removes the workspace in `finally` by default.

Use `--keep-workspace` only for inspection.

## Exact wrapper sequence

```bash
python3 scripts/intake.py --source examples/from-zero/source --workspace build/from-zero-manual --chunk-lines 6
python3 scripts/prepare_distillation.py --workspace build/from-zero-manual
python3 scripts/install_demo_artifacts.py --workspace build/from-zero-manual --curated examples/from-zero/curated
python3 scripts/finalize_distillation.py --workspace build/from-zero-manual
python3 scripts/validate_distillation.py --workspace build/from-zero-manual
python3 scripts/build_registry.py --workspace build/from-zero-manual
python3 scripts/query.py --registry build/from-zero-manual/build/expert-registry.v2.json --request examples/from-zero/request.json --print-load-plan --pretty
python3 scripts/graph_build.py --workspace build/from-zero-manual
python3 scripts/graph_query.py --graph-registry build/from-zero-manual/build/graph-registry.v1.json --request examples/from-zero/request.json --output build/from-zero-manual/routes/first.json --residual-output build/from-zero-manual/residual-bank.json --print-load-plan --pretty
# On a later query, pass --residual-bank build/from-zero-manual/residual-bank.json and write --residual-output back to that same bank.
```

Each command returns `0` on success and lifecycle/query contract errors return `2`. Remove `build/from-zero-manual/` after inspection.

The fixture installer is demo-only and only copies reviewed semantic/atomic files; it performs no semantic inference. For a real source, use `scripts/review_queue.py` to resume contiguous batches; an agent/human must read every generated `chunks/*.txt`, complete each record, write each L3 module/shared core and `semantic-review.json`, then run finalization and validation. Evaluate only with external authored query gold as described in `reference/real-material-trial.md`.
## Hash-stable pre-release wording

`source/synthetic-field-guide.md` is a byte-stable executable fixture: its hashes and derived chunk IDs are asserted by the regression suite. One sentence in that fixture retains the historical words “local proposal” solely to preserve those identifiers. It is not the current repository license. The root `LICENSE` file governs original repository content.
