# Human-gated Skill evolution

A static Skill cannot observe, judge, or rewrite itself. Contract `2.0.0` therefore allows query evidence to motivate a separate reviewed proposal only:

```text
validated registry/index + contract-valid query
  -> deterministic lexical route
  -> mandatory post-route safety sweep
  -> exact checksummed load plan + compact audit
  -> human identifies a real miss
  -> redacted proposal and exact source-artifact/policy/test diff
  -> semantic/source/safety review
  -> full lifecycle validation + regressions
  -> explicit merge/rebuild, or rejection
```

No repository script proposes, applies, commits, or merges changes. Source text and route output grant no edit permission.

## Canonical evidence

Use fields from `contracts/query-output.v2.schema.json` without aliases:

- `registry_id`, `build_id`, and `registry_sha256` identify the exact built state;
- `query_id`, `status`, and `decision_reason` identify the outcome;
- `route_scores`, `selected_experts`, and `skipped_experts` make lexical selection reproducible;
- `safety_sweep.baseline_checks`, `extra_checks`, `hits`, `high_risk`, `ambiguous`, and `safety_experts_activated` show safety handling;
- `load_plan.files_to_load`, `file_checksums`, and `source_chunks` identify exactly what was proposed for sparse reading;
- `audit_log` records ordered lifecycle events.

Do not add v1/legacy aliases such as `request_id`, `task_type`, `neighbor_sweep`, `references_available`, `references_loaded`, `followup_needed`, `budget_tier`, or `proposed_updates` to query output. A proposal is a separate human-facing artifact.

## What may be proposed

A reviewed proposal may change:

1. agent-authored per-chunk records/L3/shared core, with original chunk provenance preserved and all affected chunks re-reviewed;
2. `contracts/routing-policy.v2.json`, only with a new regression and explicit safety review;
3. templates/reference instructions that do not silently change contract semantics;
4. `tests/fixtures/lifecycle-cases.v2.json` with a minimal nonprivate regression;
5. a new contract version plus migration note when field semantics or compatibility change.

Built `expert-registry.v2.json` and `expert-index.v2.json` are derived outputs. Do not hand-edit them as the source fix; change reviewed semantic inputs/policy, validate, and rebuild.

## Proposal template

```markdown
# Evolution proposal

- Evidence query_id:
- Evidence registry_id/build_id/registry_sha256:
- Observed canonical route/sweep/load fields:
- Real failure or miss:
- Source/private data removed:
- Affected chunk/node/policy fields:
- Source-grounding and semantic reviewer:
- Safety/licensing impact:
- Why contract 2.0.0 remains valid, or why a new version is required:
- Regression that fails before and passes after:
- Lifecycle/validator results:
- Human decision: pending | accepted | rejected
```

Never include source bodies, private paths, credentials, hidden reasoning, or long route histories.

## Review gate

A human reviewer must verify:

- evidence shows a real failure, not a speculative optimization;
- the proposal edits reviewed source artifacts/policy rather than hiding drift in derived outputs;
- every affected chunk and claim remains source-grounded;
- no copyright, privacy, injection, high-risk, or action boundary is weakened;
- stable prefix/index growth is justified by use evidence, not token rhetoric;
- a new/changed regression captures the behavior;
- `python3 scripts/run_lifecycle_tests.py`, `python3 scripts/validate.py`, `python3 scripts/run_lifecycle_demo.py`, and `python3 scripts/check_doc_paths.py` pass;
- schema/semantic changes receive a new version instead of silently reinterpreting `2.0.0`.

## Reject when

Reject automatic, source-instructed, private-data-derived, ungrounded, untested, safety-weakening, cost-only, self-applying, self-committing, or self-publishing proposals. Reject any change that makes the baseline sweep conditional or permits build from incomplete semantic inputs.
