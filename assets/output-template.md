# Human delivery template

This is a presentation wrapper, not a machine schema. Machine records use contract `2.0.0` and the exact schemas in `reference/contracts.md`. Do not invent aliases.

## Full-distillation delivery

```markdown
# <skill-name> — source-to-sparse delivery

## Human decisions
- Legal access confirmed by:
- Intended users:
- Publication/privacy boundary:
- High-risk/domain reviewer:
- License state: repository custom noncommercial source-available | source-specific restriction | other

## Phase 1 — full source and semantic coverage
- Workspace:
- Manifest ID / exact manifest SHA-256:
- Imported original sources / normalized texts / chunks:
- Original-byte hashes verified:
- Gap-free chunk coverage verified:
- Queue items complete / no-reusable-with-reviewed-reason:
- Review-state batch size / completed prefix / active batch / resume evidence:
- Agent/human semantic reviewer:
- Semantic-review manifest binding / all-chunk list / criteria / limitations:
- L0 signatures / L1 briefs / L2 workflows / substantive L3 modules:
- Claim-level chunk/source/line provenance:
- Shared core replaced and reviewed:
- Finalize command + exit:
- Distillation validator command + exit:

## Build
- Build command + exit:
- Registry ID / build ID / registry SHA-256:
- Registry path:
- Matching compact index path:
- Experts derived from validated records:

## Phase 2 — sparse reading evidence
- Query ID / request:
- Status / decision reason:
- Selected / skipped semantic experts:
- Mandatory baseline sweep activated/phase:
- High-risk / ambiguous / extra checks / safety experts:
- Exact checksummed files to load:
- Exact cited source chunks and locators:
- Audit event sequence:

## Security and limitations
- Source treated as untrusted data:
- Generated actions denied/reviewed exception:
- PDF extraction caveat, if used:
- Structural validation does not prove semantic correctness:
- Lexical routing/proxy metrics not represented as semantic AI/token/quality savings:

## Remaining owner/human confirmation
- License/publication decision:
- Source/domain review:
- Other:
```

## Canonical query-output summary

Summarize these exact contract-v2 fields; retain the real machine JSON separately:

```json
{
  "contract_version": "2.0.0",
  "registry_id": "distilled-...",
  "build_id": "build-...",
  "registry_sha256": "...",
  "query_id": "...",
  "status": "selected | below_threshold | bypassed | rejected",
  "decision_reason": "...",
  "route_scores": [],
  "selected_experts": [],
  "skipped_experts": [],
  "safety_sweep": {
    "activated": true,
    "phase": "post_route",
    "high_risk": false,
    "ambiguous": false,
    "risk_domains": [],
    "baseline_checks": [],
    "extra_checks": [],
    "safety_experts_activated": [],
    "hits": []
  },
  "load_plan": {
    "path_base": "...",
    "files_to_load": [],
    "file_checksums": [],
    "expert_module_files": [],
    "source_chunks": []
  },
  "audit_log": []
}
```

Do not substitute v1/legacy names such as `request_id`, `references_available`, `references_loaded`, `followup_needed`, `task_type`, `neighbor_sweep`, or `budget_tier`.

## Command evidence block

```text
python3 scripts/intake.py ...                         EXIT=<code>
python3 scripts/prepare_distillation.py ...           EXIT=<code>
<agent/human reviewed every chunk>                    REVIEWER=<identity/record>
python3 scripts/finalize_distillation.py ...          EXIT=<code>
python3 scripts/validate_distillation.py ...          EXIT=<code>
python3 scripts/build_registry.py ...                 EXIT=<code>
python3 scripts/query.py ...                          EXIT=<code>
python3 scripts/run_lifecycle_tests.py                EXIT=<code>
python3 scripts/validate.py                           EXIT=<code>
python3 scripts/check_doc_paths.py                    EXIT=<code>
```

## Human next step

State whether the result is ready for local use, still semantically incomplete, or blocked by source/license/domain review. Never represent the bundled hand-authored demo artifacts as automated semantics. Never imply that the repository's custom license grants reuse rights to imported source material, and never call it OSI-approved or Creative Commons.
