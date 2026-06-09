# Proposal-Based Skill Self-Evolution

If a large Skill is like a small external task model, it should not remain static forever. But it also should not rewrite itself silently.

The safe pattern is **proposal-based self-evolution**:

```text
Skill call
  -> route / output / validation
  -> route log + gotcha + missed case
  -> proposed patch
  -> human / maintainer review
  -> eval pass
  -> merge
  -> next call has a better route/cache hit
```

## Why not fully automatic mutation?

A Skill package contains executable judgment: triggers, safety boundaries, evidence rules, scripts, templates, and references. If it mutates itself without review, it can:

- overfit to one unusual case;
- weaken safety or evidence boundaries;
- accidentally encode private data;
- introduce brittle routing rules;
- grow the prompt/cache layer until the “low-power” design becomes expensive.

So the Skill may **learn from use**, but the learning should be staged as reviewable changes.

## What the Skill should record

Each meaningful invocation can leave a small route record:

```yaml
route_log:
  task_signature: "short description of the task"
  selected_core: ["shared-core"]
  selected_experts: ["expert-a", "expert-b"]
  neighbor_sweep:
    checked: ["red-flags", "often-confused-with"]
    missed: ["special-population"]
  references_loaded: ["reference/x.md"]
  output_eval:
    passed: true
    weak_points: ["citation boundary could be clearer"]
  proposed_updates:
    routing: ["add trigger phrase ..."]
    graph: ["connect expert-a -> red-flag-y"]
    cache: ["move this stable rule into shared prefix"]
    evals: ["add case for ..."]
```

## Evolution targets

A mature Skill can improve in four places:

1. **ROUTING** — better trigger / anti-trigger / budget tiers.
2. **GRAPH** — better point-to-point neighbor links, fewer broad sweeps.
3. **CACHE** — shorter stable prefix, heavier details pushed behind references.
4. **EVALS** — more missed-case tests and regression cases.

## Review gate

Before merging an evolution patch, check:

- Does it reduce or justify token/attention cost?
- Does it preserve safety and evidence boundaries?
- Does it remove private/local information?
- Does it improve a real failed/missed case rather than a hypothetical one?
- Does the eval suite pass?

## One-line principle

> A Skill should not secretly rewrite itself; it should distill its usage experience into reviewable patches.

