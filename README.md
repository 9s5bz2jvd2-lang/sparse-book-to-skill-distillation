# Sparse Book-to-Skill Distillation

把一本书、长资料、课程或项目方法论，蒸馏成一个可被 AI agent 稀疏调用的 Skill 包。

核心思想：

> 先炼核心，再分专家；先中主脉，再扫旁枝；预算分层，重料后置；路由留痕，越用越准。

This repository contains a LingTai-style Skill package for **Book-to-Skill Sparse Distillation**: turning long-form knowledge into a callable, budget-aware, cross-linked, verifiable agent capability.

## What is inside

```text
.
├── SKILL.md              # Main executable entry for agents
├── ROUTING.yaml          # Trigger / anti-trigger / budget / missed-case sweep hints
├── GRAPH.md              # Skill graph, neighboring skills, micro-LLM analogy
├── CACHE.md              # Cache-friendly layout and low-power gotchas
└── assets/
    ├── eval-cases.md     # Evaluation / self-check cases
    └── output-template.md
```

## Use cases

Use this when you want to distill a book, textbook, research corpus, course, project playbook, expert workflow, or domain-specific operating manual into an agent-native Skill that can be routed, checked, updated, and reused.

## Ownership and boundary

This repository is published under the GitHub account `9s5bz2jvd2-lang`.

It is **not** a Huang Zesen personal repository and **not** an official LingTai organization repository.

See [`RULES.md`](RULES.md) for contribution, attribution, and reuse boundaries.

## License / reuse

No open-source license is granted yet. The repository is public for reading and discussion, but copying, commercial use, redistribution, or publishing derivative systems requires explicit permission from the owner unless a license is added later.
