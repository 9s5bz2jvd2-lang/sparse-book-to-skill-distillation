# Executable lifecycle evaluation cases

The normative fixture set is `tests/fixtures/lifecycle-cases.v2.json`, shaped by `contracts/lifecycle-fixtures.v2.schema.json` and executed by:

```bash
python3 scripts/run_lifecycle_tests.py
```

No model, network, package installation, or untrusted generated-code execution occurs. The suite starts from the synthetic source repeatedly, uses the same public lifecycle functions as the CLIs, and cleans `build/lifecycle-tests/` in `finally`.

Real-material operational readiness has a separate executable suite:

```bash
python3 scripts/run_readiness_tests.py
```

Its four cases cover: 300 generated chunks in interruption-safe 17-item contiguous batches with pending/forged/out-of-order failures; longest-valid-contiguous-prefix checkpointing with invalid-prefix hard failure, injected write-fault recovery, the default batch size of 3, and stored-batch-size-20 compatibility; mandatory semantic-review criteria; and external query-gold success plus deliberate route/source-load mismatch reporting. This is generated structural evidence only. It does not establish real-book meaning, gold quality, or answer quality.

## Covered lifecycle cases

| Case ID | Required behavior |
|---|---|
| `intake-complete` | archives original bytes, normalized full text, three gap-free chunks, and three pending queue items |
| `unprocessed-chunk-rejected` | full validation rejects the pending workspace |
| `missing-manifest-chunk-rejected` | deletion of a declared chunk fails validation |
| `bad-artifact-chunk-hash-rejected` | a per-chunk semantic artifact bound to the wrong hash fails validation |
| `bad-imported-source-hash-rejected` | changed archived original bytes fail source identity |
| `bad-line-locator-rejected` | a claim locator outside its cited chunk fails provenance |
| `bad-source-provenance-rejected` | a claim whose source ID disagrees with its chunk fails provenance |
| `missing-required-l3-rejected` | a missing substantive L3 module blocks validation |
| `build-refuses-pending-workspace` | build reruns validation and refuses unprocessed input |
| `full-lifecycle-build-from-artifacts` | reviewed records finalize/validate and derive four experts plus a compact index |
| `positive-routing-exact-load-plan` | selects `coverage-ledger` and returns exact checksummed shared-core/L3/chunk paths and audit events |
| `stable-score-priority-id-tie` | equal scores resolve by priority then expert ID |
| `top-k-two-stable-order` | top-k retains two threshold-eligible experts in stable order |
| `derived-global-anti-trigger` | bypasses semantic selection for summary-only use while retaining baseline sweep |
| `derived-expert-anti-trigger` | a per-expert anti-trigger makes an otherwise threshold-eligible expert ineligible |
| `derived-global-reject-anti-trigger` | a global reject returns no semantic expert while retaining baseline sweep |
| `below-threshold-shared-core-and-safety` | selects no semantic expert, retains shared core, marks ambiguity, and activates built safety |
| `high-risk-injection-safety-sweep` | records injection/high-risk hits and loads safety outside semantic top-k |
| `ambiguous-tie-safety-sweep` | cutoff-tie ambiguity triggers extra checks and safety activation |
| `malformed-query-missing-field` | missing required query text returns `malformed_input` |
| `query-schema-version-mismatch` | unsupported contract version returns `schema_version_mismatch` |
| `tampered-index-rejected` | a schema-valid but registry-inconsistent sparse index is rejected |
| `tampered-registry-build-binding-rejected` | a schema-valid registry byte change invalidates its build-ID binding |
| `changed-planned-l3-rejected` | query refuses a selected L3 module changed after build |
| `changed-shared-core-rejected` | query refuses a shared core changed after build |
| `changed-planned-chunk-rejected` | query refuses a selected source chunk changed after build |
| `from-zero-demo-temp-cleanup` | the fresh demo workspace is absent after the default `finally` cleanup |

## What the suite proves

It proves deterministic local contract behavior, recomputed original/text/chunk hashes and gap-free intake, queue/source-map completeness, missing/tampered artifact and provenance failures, required L3 presence, build only after validation, registry/index/build binding, shared-core/L3/chunk checksum enforcement, threshold/top-k/stable ordering, global and expert anti-triggers, baseline sweep retention for selected/below-threshold/bypassed/rejected routes, high-risk/ambiguous escalation, exact load plans, malformed/version failures, and default demo cleanup for the bundled fixture.

## What it does not prove

It does not prove that arbitrary agent-authored semantics are correct, that a real PDF extraction is complete, or that routing has semantic recall. It does not measure model tokens, cost, latency, answer quality, or professional-domain safety. Those require reviewed real sources, a pinned model/tokenizer/workload, quality rubric, and domain/legal reviewers.

## Adding a regression

1. Add one minimal, nonprivate case to `tests/fixtures/lifecycle-cases.v2.json` and its category schema.
2. Exercise the same lifecycle or query function used by the CLI; do not assert narrative prose only.
3. For a bug fix, demonstrate failure before and pass after when practical.
4. Run `python3 scripts/run_lifecycle_tests.py` and `python3 scripts/validate.py`.
5. If contract semantics change, create a new version instead of silently reinterpreting `2.0.0`.
