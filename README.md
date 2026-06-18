# Sparse Book-to-Skill Distillation

把一本书、长资料、课程或项目方法论，蒸馏成一个可被 AI agent 稀疏调用的 Skill 包。

核心思想：

> 蒸馏全量不丢，渐进披露分层；调用稀疏激活，重料按需加载；路由留痕，越用越准。

**两阶段分离**：蒸馏阶段全量提取所有知识，按 L0–L3 渐进式披露分层存储，不采样不跳过；调用阶段稀疏激活，只加载当前任务需要的层和专家。

This repository contains a LingTai-style Skill package for **Book-to-Skill Sparse Distillation**: turning long-form knowledge into a callable, budget-aware, cross-linked, verifiable agent capability.


## Structure diagram

A visual structure diagram is available here:

- [`docs/structure-diagram.md`](docs/structure-diagram.md) — Mermaid architecture diagram
- [`assets/structure-diagram.mmd`](assets/structure-diagram.mmd) — raw Mermaid source
- [`docs/self-evolution-loop.md`](docs/self-evolution-loop.md) — proposal-based Skill-system evolution loop (not automatic mutation of a static folder)

## What is inside

```text
.
├── SKILL.md              # Main executable entry for agents
├── ROUTING.yaml          # Trigger / anti-trigger / budget / progressive disclosure / missed-case sweep
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

---

> **禁止抄袭商用，违者等同盗法，因果自负**
> **Plagiarism and commercial use are strictly prohibited. Violators shall be deemed as thieves of sacred scriptures and shall face divine karmic retribution themselves.**
>
> 公益开源项目，禁止商用 | Public welfare open-source project, commercial use prohibited
> License: CC BY-NC 4.0
