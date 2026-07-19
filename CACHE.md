# Cache and progressive-loading policy

This file governs invocation layout for contract `2.0.0`; it does not redefine machine fields or scores. The built `expert-index.v2.json`, its matching `expert-registry.v2.json`, `contracts/routing-policy.v2.json`, and contract-v2 schemas are normative.

## Phase boundary

Cache/sparsity policy applies only after one-time full distillation and validation. Phase 1 must read every declared source chunk and create/review all semantic artifacts; no cache goal may justify sampling or skipping L0–L3.

## Stable prefix

Keep only stable, compact rules:

- the Skill routing identity/invariant;
- the built `distilled/shared-core.md`;
- the compact built index needed for deterministic selection;
- mandatory baseline sweep semantics;
- the query-output/load contract.

Do not place current query text, source bodies, retrieved chunks, private data, absolute host paths, route output, or long task history in a reusable prompt prefix.

## Variable suffix and exact sparse plan

After validating the matching registry/index and scoring the current request, load exactly:

1. `load_plan.files_to_load`: shared core followed by selected semantic L3 modules and any high-risk/ambiguous safety L3 module;
2. `load_plan.source_chunks`: the selected experts' cited source chunks with exact source/line/page locators;
3. current task/draft state;
4. the compact audit record.

The query implementation verifies the registry SHA/build ID, index-registry equality, shared-core/L3 checksums, and selected chunk checksums before returning the plan. L3 is fully created in Phase 1 but only the selected/safety subset is loaded in Phase 2.

## Mandatory sweep placement

```text
validate request + registry/index
  -> lexical score / anti-trigger / threshold / stable top-k
  -> mandatory low-cost post-route baseline sweep
  -> high-risk/ambiguous extra checks and safety module when available
  -> exact checksummed module/chunk load plan
  -> output + compact audit
```

The baseline sweep runs for selected, below-threshold, bypassed, and rejected statuses. It is a short checklist/indicator pass, not a second full expert execution. A high-risk/ambiguous safety module is outside semantic top-k.

## Below threshold and anti-trigger

- Below threshold: keep shared core; mark the route ambiguous; run extra checks and load the built safety module when available. Do not invent a semantic expert.
- Bypass/reject anti-trigger: select no semantic expert, preserve the baseline sweep, and return only the load plan justified by safety state.
- Malformed input: fail before a query-output record exists.

## Audit/log placement

Retain only IDs, hashes, scores/hits, selected/skipped expert IDs, sweep checks/hits, exact load paths/checksums, status, and ordered event summaries. Do not retain source bodies, hidden reasoning, credentials, or private task histories. The host owns consent, access controls, retention, and deletion.

## Honest cost evidence

`scripts/benchmark.py` reports deterministic fixture proxies only:

- source and chunk character/whitespace-word counts;
- all registered versus selected L3 character counts;
- registered/selected experts and chunks plus ratios.

These are not model tokens, monetary cost, latency, semantic recall, or answer quality. No savings claim is valid without a separately pinned model/tokenizer, representative workload, direct baseline, and quality rubric.

## Common failures

1. **Sparse intake instead of sparse invocation.** Never skip Phase-1 chunks.
2. **Router larger than avoided work.** Keep signatures/index compact and measure rather than assume.
3. **Selected path changed after build.** Check checksums and fail; never load silently.
4. **Sweep becomes full re-execution.** Escalate to one safety module only on high-risk/ambiguity.
5. **L3 existence becomes all-L3 loading.** Load only selected/safety L3 paths.
6. **No-hit invents expertise.** Preserve shared core and safety, then ask for reviewed routing improvement if needed.
7. **Logs become a private cache.** Store compact audit fields only.
8. **Cache learns silently.** Evidence creates a human-reviewed proposal, never automatic mutation.
